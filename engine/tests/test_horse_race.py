"""Does the robust policy actually beat trusting the point estimate?

DeMiguel, Garlappi and Uppal asked the question that ends most optimizer
arguments: out of sample, does the clever rule beat the naive one? This file
answers it, and the answer is not the flattering one.

The rules in the race:

    naive     — ±3% on every SKU the fit calls elastic or inelastic, no sizing,
                no refusal. The heuristic the engine shipped with.
    plugin    — walk to P*(ε̂) inside the ±5% cap, trusting the point estimate.
                What the engine did before this work.
    quantile  — maximise the 25th percentile of the profit-delta distribution.
    cvar      — maximise the mean of its worst decile.
    ce        — the shipped policy: certainty equivalent under a coherent
                shortfall constraint, which is the only one of the five whose
                step size responds to how much the engine actually knows.

Scored on realised profit in the period AFTER the fit, under each SKU's true
elasticity and a demand shock the rules never see. Three regimes, each making
the world harder in a way a real seller's data is hard: the seller reprices in
response to last month's demand (so ε̂ is biased), and the true elasticity drifts
between the fitting window and the period the promise covers (so the fit is
local, which is the engine's own stated reason for walking rather than
teleporting).

Scored PER MOVE, not per seller. The first version of this file scored the
5th-percentile seller out of twenty, which is essentially the worst seller and
moved by hundreds of dollars between seeds — it reported a tail advantage for
the robust policy that did not reproduce. Per-move statistics over a thousand
moves are stable to a couple of percent, so that is what is asserted. The
per-seller totals are still reported, and labelled as the noisy figure they are.

WHAT IT FOUND — the numbers the scorecard quotes, 40 sellers × 25 SKUs:

  regime       rule      moves   total $   $/move   worst-decile $  sum of losses
  no drift     plugin     1000   131,982    132.0        −109         −13,261
               ce          987   129,690    131.4         −91         −10,861
               quantile    601   101,834    169.4         −67          −4,151
               naive      1000    85,488     85.5         −44          −5,753
  ε drift 0.4  plugin     1000   131,271    131.3        −165         −21,109
               ce          987   129,442    131.1        −144         −17,897
               quantile    601   101,410    168.7        −110          −7,330
  ε drift 0.8  plugin     1000   130,380    130.4        −285         −39,332
               ce          987   129,242    130.9        −257         −34,289
               quantile    601   101,433    168.8        −205         −15,470

Read plainly:

  * Every rule that uses the elasticity fit beats the naive fixed step by more
    than 50% on total realised profit. The fit earns its keep.
  * The robust policy does NOT beat the plug-in on total realised profit. It is
    behind by 1–2% in every regime, because it declines a handful of moves the
    plug-in takes. Claiming otherwise would be the easiest lie in this
    repository. Per move issued the two are a dead heat: 131.4 against 132.0.
  * It does beat the plug-in in the tail, consistently and reproducibly: the
    mean of the worst decile of moves is 10–18% less bad in every regime, and
    the total dollars lost on losing moves is 13–18% lower. That is where
    trusting a point estimate costs a seller, and it is the only stable
    difference between the two.
  * The pure quantile objective earns 28% MORE per move and loses 69% fewer
    dollars, by declining 40% of the catalog. Fewer and truer, priced: it puts
    23% less money in the payout. It is available as `objective="quantile"` and
    is not the default, because "more money landed this month" is the first
    clause of what a seller is buying.

So the shipped default is a dead heat on money per directive, a reproducible
win in the tail, and the only rule whose step size is derived from the
uncertainty rather than asserted as a constant. That is the argument for it,
stated at its actual strength and no higher.
"""

from functools import lru_cache

import numpy as np

from hubricon_engine.models import elasticity
from hubricon_engine.models.pricing_engine import (
    STEP_CAP,
    fee_terms,
    optimal_price,
    price_move,
)

N_SELLERS = 40
SKUS_PER_SELLER = 25
N_PERIODS = 8
FEE_RATE, FIXED_FEE, UNIT_COST, BASE_PRICE = 0.15, 1.50, 5.00, 20.0
NAIVE_STEP = 0.03
# The race only has to rank five rules, so it runs the bootstrap at half size.
# Re-running it at the full MC_DRAWS does not change the ordering.
RACE_DRAWS = 3000
RULES = ("naive", "plugin", "quantile", "cvar", "ce")
OBJECTIVES = {"quantile": "quantile", "cvar": "cvar", "ce": "certainty_equivalent"}


def _period(i: int, length: int = 28) -> tuple[str, str]:
    """(start, end) for the i-th period, 1-indexed, rolling into the next year.

    Fixtures used to write f"2026-{i:02d}-01" directly, which produces month 13
    past a year of history. Nothing caught it until elasticity._fit began reading
    period_end to normalise units by period length (2026-09-12) — a real export
    never has a thirteenth month."""
    year, month = 2026 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{length:02d}"


def _seller(seed, phi, rho, drift, n_skus=SKUS_PER_SELLER, n_periods=N_PERIODS, sd=0.22):
    """One seller's exports plus the private truth used only for scoring.

    phi   — how hard the seller reprices in response to LAST period's demand.
    rho   — persistence of the demand shock. Reaction only biases ε̂ when demand
            is persistent, because only then does last month's demand predict
            this month's.
    drift — sd of the change in true elasticity between the fitting window and
            the period the promise covers.
    """
    rng = np.random.default_rng(seed)
    econ, truth = [], []
    for i in range(n_skus):
        sku = f"S{i:03d}"
        eps = float(rng.uniform(-3.4, -1.2))
        shock = np.zeros(n_periods + 1)
        shock[0] = rng.normal(0, sd)
        for t in range(1, n_periods + 1):
            shock[t] = rho * shock[t - 1] + rng.normal(0, sd * np.sqrt(1 - rho**2))
        noise = rng.normal(0, 0.05, size=n_periods)
        prices = np.array([BASE_PRICE * np.exp(noise[t] + (phi * shock[t - 1] if t else 0.0))
                           for t in range(n_periods)])
        units = 400.0 * (prices / BASE_PRICE) ** eps * np.exp(shock[:n_periods])
        for j, (p, u) in enumerate(zip(prices, units), start=1):
            revenue = float(p) * float(u)
            econ.append({
                "sku": sku, "asin": "B0" + sku,
                "period_start": _period(j)[0], "period_end": _period(j)[1],
                "units_sold": float(u), "avg_sales_price": float(p), "sales": revenue,
                "referral_fees": -FEE_RATE * revenue,
                "fba_fulfillment_fees": -FIXED_FEE * float(u),
                "storage_fees": 0.0, "other_fees": 0.0, "net_proceeds": revenue,
            })
        truth.append({"sku": sku, "eps_true": eps,
                      "eps_future": eps + float(rng.normal(0, drift)),
                      "p0": float(prices[-1]), "q0": float(units[-1]), "scale": 400.0,
                      "future_shock": float(np.exp(shock[n_periods]))})
    data = {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [], "cogs_inputs": []}
    return data, truth


def _margin_row(t):
    revenue = t["p0"] * t["q0"]
    return {"sku": t["sku"], "period_start": f"2026-{N_PERIODS:02d}-01",
            "period_end": f"2026-{N_PERIODS:02d}-28",
            "units": t["q0"], "revenue": revenue,
            "amazon_fees": FEE_RATE * revenue + FIXED_FEE * t["q0"],
            "cogs": UNIT_COST * t["q0"],
            "fee_split": {"basis": "itemized", "proportional_rate": FEE_RATE,
                          "fixed_per_unit": FIXED_FEE,
                          "proportional_fees": FEE_RATE * revenue,
                          "fixed_fees": FIXED_FEE * t["q0"]}}


def _realised(t, p_new):
    eps = t["eps_future"]
    a = t["scale"] * t["future_shock"] / BASE_PRICE ** eps

    def pi(p):
        return a * p ** eps * (p * (1 - FEE_RATE) - UNIT_COST - FIXED_FEE)

    return pi(p_new) - pi(t["p0"])


def _plugin_price(t, fit, row):
    eps = float(fit["elasticity"])
    f, big_f, _ = fee_terms(row)
    if eps < -1:
        star = optimal_price(eps, UNIT_COST, f, big_f)
        if star is None or star <= 0:
            return None
        return t["p0"] * min(1 + STEP_CAP, max(1 - STEP_CAP, star / t["p0"]))
    if -1 < eps < 0:
        return t["p0"] * (1 + STEP_CAP)
    return None


@lru_cache(maxsize=None)
def _race(phi, rho, drift, sellers=N_SELLERS):
    """{rule: {"mean", "p5", "moves", "loss_rate"}} over `sellers` simulated
    sellers. Cached because several tests read the same race."""
    totals = {r: [] for r in RULES}
    deltas = {r: [] for r in RULES}
    for seed in range(600, 600 + sellers):
        data, truth = _seller(seed, phi, rho, drift)
        fits = {f["item_id"]: f for f in elasticity.run(data)
                if f["level"] == "sku" and f["status"] == "ok"}
        per_seller = dict.fromkeys(RULES, 0.0)
        for t in truth:
            fit = fits.get(t["sku"])
            if not fit:
                continue
            row = _margin_row(t)
            eps = float(fit["elasticity"])
            prices = {
                "naive": t["p0"] * ((1 - NAIVE_STEP) if eps < -1 else (1 + NAIVE_STEP)),
                "plugin": _plugin_price(t, fit, row),
            }
            for rule, objective in OBJECTIVES.items():
                move = price_move(row, fit, objective=objective, draws=RACE_DRAWS)
                prices[rule] = None if move is None else move["p_new"]
            for rule, price in prices.items():
                if price is None:
                    continue
                delta = _realised(t, price)
                per_seller[rule] += delta
                deltas[rule].append(delta)
        for rule in RULES:
            totals[rule].append(per_seller[rule])
    out = {}
    for rule in RULES:
        arr = np.array(deltas[rule]) if deltas[rule] else np.array([0.0])
        worst = np.sort(arr)[:max(1, len(arr) // 10)]
        out[rule] = {
            "moves": len(deltas[rule]),
            "total": float(arr.sum()),
            "per_move": float(arr.mean()),
            "worst_decile": float(worst.mean()),
            "losses": float(arr[arr < 0].sum()),
            "loss_rate": float((arr < 0).mean()),
            # reported, never asserted: the 5th percentile of forty sellers is
            # close to the worst seller and moves by hundreds between seeds
            "seller_mean": float(np.mean(totals[rule])),
            "seller_p5": float(np.percentile(totals[rule], 5)),
        }
    return out


REGIMES = {"no_drift": (0.6, 0.6, 0.0),
           "drift_0.4": (0.6, 0.6, 0.4),
           "drift_0.8": (0.6, 0.6, 0.8)}


# ── what the fit is worth at all ──────────────────────────────────────────

def test_fitting_elasticity_beats_a_fixed_three_percent_step_decisively():
    """The first thing the race has to establish: the elasticity model earns its
    keep against a rule that does not use it. If this failed, the honest product
    would be a +3% heuristic and a much shorter report."""
    for name, params in REGIMES.items():
        result = _race(*params)
        assert result["ce"]["total"] > result["naive"]["total"] * 1.3, name
        assert result["plugin"]["total"] > result["naive"]["total"] * 1.3, name


# ── the uncomfortable finding, asserted as found ──────────────────────────

def test_the_robust_policy_does_not_beat_the_plug_in_on_total_profit():
    """Asserted in the direction it actually came out, so nobody can later read
    the scorecard as claiming a win it never had."""
    for name, params in REGIMES.items():
        result = _race(*params)
        ratio = result["ce"]["total"] / result["plugin"]["total"]
        assert 0.96 < ratio < 1.0, f"{name}: ce/plugin total = {ratio:.4f}"


def test_per_move_the_two_are_a_dead_heat():
    """The total gap is entirely the moves the robust policy declines. Per
    directive issued there is nothing between them, which is what makes the
    tail comparison below the only real difference."""
    for name, params in REGIMES.items():
        result = _race(*params)
        ratio = result["ce"]["per_move"] / result["plugin"]["per_move"]
        assert 0.99 < ratio < 1.02, f"{name}: ce/plugin per move = {ratio:.4f}"


def test_the_robust_policy_loses_less_in_the_tail_in_every_regime():
    """The reproducible advantage, measured on a thousand moves rather than on
    the worst of forty sellers: the mean of the worst decile of outcomes, and
    the total dollars lost on losing moves."""
    for name, params in REGIMES.items():
        result = _race(*params)
        ce, plugin = result["ce"], result["plugin"]
        assert ce["worst_decile"] > plugin["worst_decile"], f"{name} worst decile"
        assert ce["losses"] > plugin["losses"], f"{name} sum of losses"
        # and the margin is material, not a rounding artifact
        assert ce["worst_decile"] > plugin["worst_decile"] * 0.95, name


def test_the_tail_objective_is_fewer_and_truer_and_we_price_it():
    """The quantile objective earns more per move and loses far less, by
    declining a large share of the catalog. Both halves of that trade are
    asserted so the scorecard's argument for the default is checkable."""
    result = _race(*REGIMES["no_drift"])
    q, plugin = result["quantile"], result["plugin"]
    assert q["per_move"] > plugin["per_move"] * 1.2          # truer
    assert q["losses"] > plugin["losses"] * 0.5              # far less lost
    assert q["moves"] < plugin["moves"] * 0.7               # fewer
    assert q["total"] < plugin["total"] * 0.85              # and it costs money


def test_the_race_is_reported_not_just_asserted():
    """The scorecard quotes this table, so print it for anyone running with -s."""
    print("\n  regime      rule      moves    total $   $/move  worst-dec  "
          "sum losses  (seller mean)")
    for name, params in REGIMES.items():
        result = _race(*params)
        for rule in sorted(RULES, key=lambda r: -result[r]["total"]):
            r = result[rule]
            print(f"  {name:11s} {rule:8s} {r['moves']:6d} {r['total']:10,.0f} "
                  f"{r['per_move']:8.1f} {r['worst_decile']:10.0f} {r['losses']:11,.0f} "
                  f"  {r['seller_mean']:10,.0f}")
    best = max(RULES, key=lambda r: _race(*REGIMES["no_drift"])[r]["total"])
    assert best == "plugin"      # the finding, pinned
