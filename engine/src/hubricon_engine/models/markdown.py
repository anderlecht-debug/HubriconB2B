"""Excess stock: hold, liquidate, or mark it down — and the mirror case, a
small rise that stretches thin stock until the replenishment lands.

inventory_econ used to answer "hold or liquidate" on two numbers: the NPV of
selling the excess at today's price, and what Amazon's liquidation program
returns. Two things were wrong with the comparison and one thing was missing.

THE CORRECTIONS (2026-09-23). Hold value subtracted landed cost per unit;
liquidation value was gross recovery. For units already on the shelf the
landed cost is SUNK — it is the same cash gone whichever way the units leave —
so the rule charged it on one side only and pushed thin-margin SKUs toward
liquidation that would have netted a fraction of what selling them would.
Every option here is valued as cash proceeds net of fees and carry, landed cost
excluded. (The order decision in inventory_econ.critical_fractile keeps landed
cost in C_u and capital in C_o, correctly: there the cost is cash yet to be
wired.) The second: the excess was sold from month one, though excess is by
definition the stock BEHIND the target cover; here the whole position sells
first-in-first-out and the excess sells last, which is what makes carry and
discounting bite on it. And carry no longer includes a capital charge on top
of discounting: the discount rate is the time value of money, and a per-unit
capital charge on sunk cost would count it twice.

THE MISSING OPTION. A markdown: the listing at p_0(1 − d) for the whole SKU
until the position is back to the target cover, then p_0 again. Demand at the
markdown follows the fitted constant-elasticity curve, r·(1 − d)^ε, with ε
drawn from its shrunk Student-t posterior, the rate drawn lognormal from the
SKU's own dispersion and the fees from their history — common random numbers
across every option, so two options differ by their economics and never by
which draws they got. A depth grid from 5% to 40%; a floor where the markdown
contribution p_d(1 − f) − F falls under what liquidation returns per unit,
because no one should sell for less than the dump price. The choice among
hold, liquidate and every depth is the certainty equivalent of the gain versus
hold, inside the same risk budget the price step uses, with hold always a
candidate at exactly zero.

EXTRAPOLATION. The elasticity is a local fit and MATH_METHODS.md §2 says it is
used inside a ±5% band. A 25% markdown is well outside it. The interval is the
honest mechanism — uncertainty in ε scales with |log(1 − d)|, so deep depths on
thin fits publish wide bands and lose the certainty-equivalent race — and the
row also says in words when the markdown price sits below 90% of the lowest
price the SKU has ever been observed at. A markdown deeper than the 5% standing
cap is an explicit decision for the client.

THE STRETCH. The mirror case: stockout likely, replenishment on its way, and a
small rise inside the cap that makes the stock last. Demand over the lead time
is Poisson at the base rate; at the higher price it is the same Poisson THINNED
by (1 + d)^ε — a binomial of the base draw — so the two are compared on the
same random numbers whether the stock binds or not. The profit over the window
is min(D, on hand) × contribution at each price, and the rise is chosen the
way every price step is: the certainty equivalent of that gain inside the risk
budget, standing still always a candidate. The first draft targeted the
smallest rise that brought P(stockout) under 25% and the simulation refused it:
on an elastic SKU the rise that stops the stockout throws away more sales than
the higher price recovers, so a stockout target on its own recommends losing
money. The avoided stockout's own value — rank, the low-inventory fee — is not
priced, because MATH_METHODS.md §10 says it cannot be honestly, so the decision
stands on the measurable gain and the change in P(stockout) is reported beside
it. When no rise inside the cap beats standing still the answer is
`no_stretch_pays`. The step is drafted as an ordinary price_step so the Profit
Record measures it as one.

WHAT IT CANNOT TELL YOU. Whether the markdown price will hold the Buy Box or
trigger a competitor; whether Amazon's excess estimate is right; and the
constant-elasticity form far from the observed range, which no interval tests.
"""

import hashlib
from datetime import date

import numpy as np

from . import dependence
from . import fee_schedule as fees
from .common import num
from .inventory_econ import (
    ANNUAL_CAPITAL_RATE, HOLD_HORIZON_DAYS, LIQUIDATION_RECOVERY_OF_PRICE, MAX_HOLD_MONTHS,
)
from .mc import quantiles_with_se
from .pricing_engine import (
    RISK_BUDGET_SHARE, STEP_CAP, _fee_dispersion, _has_stated_uncertainty, _posterior_se,
    certainty_equivalent, es5, trailing_monthly_net,
)

DEPTH_GRID = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
TARGET_COVER_DAYS = HOLD_HORIZON_DAYS
RANGE_GUARD = 0.90
MD_DRAWS = 4000
MD_SEED = 20260911
STOCKOUT_ALERT = 0.25
STRETCH_GRID = tuple(round(0.005 * k, 4) for k in range(1, int(STEP_CAP / 0.005) + 1))
MIN_EXCESS_UNITS = 1


def _rng(sku: str) -> np.random.Generator:
    tag = int(hashlib.sha1(sku.encode()).hexdigest()[:8], 16)
    return np.random.default_rng([MD_SEED, tag])


def position_value(position: float, rate: np.ndarray, eps: np.ndarray | None, f: np.ndarray, big_f: np.ndarray,
                   p0: float, depth: float | None, liquidate_excess: bool, vol: float, age0: float,
                   today: date, size_tier: str = "standard", cliffs: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """NPV per draw of selling `position` units under one option, and the
    month the excess is cleared. Cash proceeds net of fees and carry, landed
    cost sunk, discounted monthly; leftovers past MAX_HOLD_MONTHS go to
    liquidation at the end."""
    n = rate.size
    remaining = np.full(n, float(position))
    target = rate * TARGET_COVER_DAYS
    npv = np.zeros(n)
    cleared = np.full(n, np.nan)
    if liquidate_excess:
        excess = np.maximum(0.0, remaining - target)
        npv += excess * p0 * LIQUIDATION_RECOVERY_OF_PRICE
        remaining = remaining - excess
        cleared[:] = 0.0
    contrib0 = p0 * (1 - f) - big_f
    if depth:
        p_d = p0 * (1 - depth)
        contrib_d = p_d * (1 - f) - big_f
        rate_d = rate * (1 - depth) ** eps
    month, age = today.month, age0
    discount = 1 + ANNUAL_CAPITAL_RATE / 12
    for m in range(1, MAX_HOLD_MONTHS + 1):
        month = month % 12 + 1
        age += 30
        in_markdown = (remaining > target) if depth else np.zeros(n, dtype=bool)
        rate_m = np.where(in_markdown, rate_d, rate) if depth else rate
        contrib_m = np.where(in_markdown, contrib_d, contrib0) if depth else contrib0
        sold = np.minimum(remaining, rate_m * 30.0)
        carry = 0.0
        if cliffs:
            carry = remaining * vol * (fees.storage_rate(month, size_tier) + fees.aged_surcharge_rate(int(age)))
            if age > 365:
                carry = np.maximum(carry, remaining * fees.AGED_SURCHARGE_MIN_PER_UNIT_365_PLUS)
        npv += (sold * contrib_m - carry) / discount ** m
        remaining = remaining - sold
        newly = np.isnan(cleared) & (remaining <= target + 1e-9)
        cleared[newly] = m
        if not (remaining > 1e-9).any():
            break
    npv += remaining * p0 * LIQUIDATION_RECOVERY_OF_PRICE / discount ** MAX_HOLD_MONTHS
    cleared = np.where(np.isnan(cleared), MAX_HOLD_MONTHS, cleared)
    return npv, cleared


def value_options(position: float, p0: float, rate_mean: float, rate_sd: float, fee_rate: float,
                  fixed_fee: float, vol: float, age0: float, today: date, *, elasticity_row: dict | None = None,
                  fee_history=None, min_observed_price: float | None = None, size_tier: str = "standard",
                  cliffs: bool = True, draws: int = MD_DRAWS, rng: np.random.Generator | None = None) -> dict:
    """Every option's NPV on the same draws. Markdowns only when an elasticity
    with stated uncertainty exists; the floor and the range flag per depth."""
    rng = rng or np.random.default_rng(MD_SEED)
    n = int(draws)
    rate = dependence.correlated_rates(rng, [max(rate_mean, 1e-9)], [max(rate_sd, 0.0)], (n,), 0.0)[0]
    eps = None
    eps_inputs = None
    if elasticity_row is not None and elasticity_row.get("status") == "ok" and _has_stated_uncertainty(elasticity_row):
        se, dof = _posterior_se(elasticity_row)
        shock = rng.standard_t(dof, size=n) if dof and dof >= 1 else rng.standard_normal(n)
        eps = float(elasticity_row["elasticity"]) + se * shock
        eps_inputs = {"eps": float(elasticity_row["elasticity"]), "eps_se": round(se, 6), "eps_dof": dof}
    sd_f, sd_big = _fee_dispersion(fee_history)
    f = np.clip(fee_rate + sd_f * rng.standard_normal(n), 0.0, 0.9) if sd_f > 0 else np.full(n, fee_rate)
    big_f = np.clip(fixed_fee + sd_big * rng.standard_normal(n), 0.0, None) if sd_big > 0 else np.full(n, fixed_fee)
    common = dict(vol=vol, age0=age0, today=today, size_tier=size_tier, cliffs=cliffs)
    options = {}
    hold, hold_m = position_value(position, rate, eps, f, big_f, p0, None, False, **common)
    liq, liq_m = position_value(position, rate, eps, f, big_f, p0, None, True, **common)
    options["hold"] = {"npv": hold, "months": hold_m}
    options["liquidate"] = {"npv": liq, "months": liq_m}
    depths = {}
    if eps is not None:
        liquidation_per_unit = p0 * LIQUIDATION_RECOVERY_OF_PRICE
        for d in DEPTH_GRID:
            p_d = p0 * (1 - d)
            if p_d * (1 - fee_rate) - fixed_fee < liquidation_per_unit:
                depths[d] = {"status": "below_floor"}
                continue
            npv, months = position_value(position, rate, eps, f, big_f, p0, d, False, **common)
            depths[d] = {"status": "ok", "npv": npv, "months": months, "price": round(p_d, 2),
                         "beyond_observed_range": bool(min_observed_price and p_d < RANGE_GUARD * float(min_observed_price))}
    return {"hold": options["hold"], "liquidate": options["liquidate"], "markdown": depths,
            "inputs": {"draws": n, "seed": MD_SEED, "rate_mean": rate_mean, "rate_sd": rate_sd,
                       "fee_rate_sd": round(sd_f, 6), "fixed_fee_sd": round(sd_big, 6), **(eps_inputs or {})}}


def choose(options: dict, tol: float) -> dict:
    """The certainty-equivalent winner against hold, inside the shortfall
    budget; hold itself is the zero candidate."""
    hold = options["hold"]["npv"]
    best = {"decision": "hold", "depth": None, "objective_value": 0.0}
    candidates = [("liquidate", None, options["liquidate"]["npv"])]
    candidates += [("markdown", d, v["npv"]) for d, v in options["markdown"].items() if v.get("status") == "ok"]
    feasible = 1
    for name, depth, npv in candidates:
        gain = npv - hold
        if es5(gain) < -tol:
            continue
        feasible += 1
        score = certainty_equivalent(gain, tol)
        if score > best["objective_value"]:
            best = {"decision": name, "depth": depth, "objective_value": float(score)}
    best["feasible_candidates"] = feasible
    best["candidates"] = len(candidates) + 1
    best["risk_budget"] = round(float(tol), 2)
    return best


def _summ(arr: np.ndarray) -> dict:
    q = quantiles_with_se(arr, (0.05, 0.50, 0.95))
    return {"p5": num(q[0.05]["value"]), "p50": num(q[0.50]["value"]), "p95": num(q[0.95]["value"]),
            "mc_se": {"p5": num(q[0.05]["se"], 3), "p50": num(q[0.50]["se"], 3), "p95": num(q[0.95]["se"], 3)}}


def stretch(on_hand: int, lead_days: float, rate_mean: float, rate_sd: float, elasticity_row: dict | None,
            p0: float, fee_rate: float, fixed_fee: float, rng: np.random.Generator | None = None,
            draws: int = MD_DRAWS, tol: float = 0.0) -> dict:
    """The rise inside the cap, if any, that pays over the lead-time window on
    thinned common random numbers; P(stockout) before and after reported."""
    if elasticity_row is None or elasticity_row.get("status") != "ok" or not _has_stated_uncertainty(elasticity_row):
        return {"status": "insufficient_data", "basis": "no elasticity with stated uncertainty"}
    if not lead_days or lead_days <= 0:
        return {"status": "insufficient_data", "basis": "no lead time on file"}
    rng = rng or np.random.default_rng(MD_SEED)
    n = int(draws)
    rate = dependence.correlated_rates(rng, [max(rate_mean, 1e-9)], [max(rate_sd, 0.0)], (n,), 0.0)[0]
    lead = rng.lognormal(mean=np.log(max(1.0, lead_days)), sigma=0.2, size=n)
    se, dof = _posterior_se(elasticity_row)
    eps = float(elasticity_row["elasticity"]) + se * (rng.standard_t(dof, size=n) if dof and dof >= 1 else rng.standard_normal(n))
    eps = np.minimum(eps, 0.0)   # a rise cannot raise demand under this curve
    d0 = rng.poisson(rate * lead)
    p_before = float(np.mean(d0 > on_hand))
    contrib0 = p0 * (1 - fee_rate) - fixed_fee
    base_profit = np.minimum(d0, on_hand) * contrib0
    best = {"d": 0.0, "score": 0.0}
    ladder = []
    # one uniform draw per (draw, step) would break the coupling across steps;
    # thinning from ONE uniform per draw keeps every step on the same numbers
    u = rng.random(n)
    for d in STRETCH_GRID:
        keep = np.clip((1 + d) ** eps, 0.0, 1.0)
        # binomial thinning by inversion on the shared uniform: monotone in keep
        dd = _thin(d0, keep, u, rng)
        p_out = float(np.mean(dd > on_hand))
        p_d = p0 * (1 + d)
        gain = np.minimum(dd, on_hand) * (p_d * (1 - fee_rate) - fixed_fee) - base_profit
        feasible = es5(gain) >= -abs(tol)
        score = certainty_equivalent(gain, tol) if feasible else float("-inf")
        ladder.append({"d": d, "p_stockout": num(p_out, 4), "gain_p50": num(float(np.quantile(gain, 0.5))),
                       "feasible": bool(feasible)})
        if score > best["score"]:
            best = {"d": d, "score": float(score), "p_out": p_out, "gain": gain, "p_new": p_d}
    if best["d"] == 0.0:
        return {"status": "no_stretch_pays", "p_stockout_before": num(p_before, 4),
                "p_stockout_at_cap": ladder[-1]["p_stockout"] if ladder else None, "cap": STEP_CAP,
                "ladder": ladder,
                "basis": (f"no rise inside {STEP_CAP:.0%} beats standing still on the window's profit: the units "
                          f"the rise loses cost more than the higher price recovers")}
    gain = best["gain"]
    return {"status": "ok", "step_fraction": best["d"], "p_new": round(best["p_new"], 2), "p0": round(p0, 2),
            "p_stockout_before": num(p_before, 4), "p_stockout_after": num(best["p_out"], 4),
            "p_stockout_mc_se": num(float(np.sqrt(best["p_out"] * (1 - best["p_out"]) / n)), 5),
            "gain": _summ(gain), "p_loss": num(float(np.mean(gain < 0)), 4),
            "objective_value": num(best["score"]), "ladder": ladder,
            "mc_inputs": {"draws": n, "seed": MD_SEED, "eps_se": round(se, 6), "eps_dof": dof,
                          "lead_days": lead_days, "thinning": "binomial on the base Poisson draw, one uniform per draw",
                          "risk_budget": round(float(tol), 2)}}


def _thin(counts: np.ndarray, keep: np.ndarray, u: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Binomial(counts, keep) coupled across `keep` values through one uniform
    per draw: the thinned count is non-increasing in the price, which is what
    makes two steps comparable on the same numbers."""
    # binomial quantile by inversion is expensive; a normal approximation with
    # continuity correction is exact enough at these counts and keeps the coupling
    mean = counts * keep
    sd = np.sqrt(np.maximum(counts * keep * (1 - keep), 1e-12))
    z = np.sqrt(2.0) * _erfinv(2.0 * u - 1.0)
    out = np.rint(mean + sd * z)
    return np.clip(out, 0, counts).astype(int)


def _erfinv(x: np.ndarray) -> np.ndarray:
    from scipy.special import erfinv
    return erfinv(np.clip(x, -0.999999, 0.999999))


def run(data: dict, inv_econ: dict | None, elasticity_rows: list[dict] | None, margin_rows: list[dict] | None,
        inventory_rows: list[dict] | None, today: date | None = None, channel: str = "amazon",
        draws: int = MD_DRAWS) -> dict:
    from .. import channels

    today = today or date.today()
    cliffs = channels.has_fee_cliffs(channel)
    rows_in = (inv_econ or {}).get("rows") or []
    fits = {r["item_id"]: r for r in (elasticity_rows or []) if r.get("level") == "sku" and r.get("status") == "ok"}
    inv_by_sku = {r["sku"]: r for r in (inventory_rows or [])}
    latest_margin: dict[str, dict] = {}
    fee_hist: dict[str, list] = {}
    from .pricing_engine import fee_terms
    for m in margin_rows or []:
        if float(m.get("units") or 0) > 0 and float(m.get("revenue") or 0) > 0:
            f, big_f, _ = fee_terms(m)
            fee_hist.setdefault(m["sku"], []).append((f, big_f))
        if m["sku"] not in latest_margin or str(m["period_start"]) > str(latest_margin[m["sku"]]["period_start"]):
            latest_margin[m["sku"]] = m

    out_rows = []
    for r in rows_in:
        sku = r["sku"]
        if r.get("status") != "ok" or r.get("price") is None:
            out_rows.append({"sku": sku, "status": "no_unit_economics"})
            continue
        fit = fits.get(sku)
        m = latest_margin.get(sku)
        p0 = float(r["price"])
        f, big_f = float(r.get("fee_rate") or 0), float(r.get("fixed_fee") or 0)
        rate_mean, rate_sd = float(r.get("rate_mean") or 0), float(r.get("rate_sd") or 0)
        excess = int(r.get("excess_units") or 0)
        # the excess plus the target cover: the model's excess is then exactly
        # the row's, whether Amazon's estimate or the cover rule produced it
        position = float(excess) + rate_mean * TARGET_COVER_DAYS
        rng = _rng(sku)
        row = {"sku": sku, "p0": round(p0, 2), "excess_units": excess, "position": position,
               "fee_rate": round(f, 6), "fixed_fee_per_unit": round(big_f, 6),
               "elasticity": fit.get("elasticity") if fit else None,
               "std_err": fit.get("std_err") if fit else None,
               "ci95": (fit.get("details") or {}).get("ci95") if fit else None,
               "min_observed_price": r.get("min_observed_price"),
               "carry_month_now": num(float(r.get("aged_surcharge_month") or 0) + float(r.get("storage_next_month") or 0))}
        inv = inv_by_sku.get(sku, {})
        if excess < MIN_EXCESS_UNITS or rate_mean <= 0:
            row["status"] = "no_excess"
        else:
            opts = value_options(position, p0, rate_mean, rate_sd, f, big_f, float(r.get("item_volume_cuft") or 0),
                                 float(r.get("weighted_age") or 90.0), today, elasticity_row=fit,
                                 fee_history=fee_hist.get(sku), min_observed_price=r.get("min_observed_price"),
                                 size_tier=r.get("size_tier") or "standard", cliffs=cliffs, draws=draws, rng=rng)
            tol = RISK_BUDGET_SHARE * max(trailing_monthly_net(m), 0.0) if m else 0.0
            pick = choose(opts, tol)
            hold, liq = opts["hold"]["npv"], opts["liquidate"]["npv"]
            row.update({
                "status": "ok" if fit else "no_elasticity",
                "decision": pick["decision"], "depth": pick["depth"], "policy": pick,
                "npv": {"hold": _summ(hold), "liquidate": _summ(liq),
                        **({f"markdown_{int(d * 100)}": _summ(v["npv"]) for d, v in opts["markdown"].items() if v.get("status") == "ok"})},
                "months_to_clear": {"hold": num(float(np.median(opts["hold"]["months"])), 1)},
                "depths": {str(d): {k: v for k, v in val.items() if k in ("status", "price", "beyond_observed_range")}
                           for d, val in opts["markdown"].items()},
                "mc_inputs": opts["inputs"],
                "delta_liquidate_vs_hold": _summ(liq - hold),
            })
            if pick["decision"] == "markdown":
                v = opts["markdown"][pick["depth"]]
                gain = v["npv"] - hold
                row.update({"p_new": v["price"], "beyond_observed_range": v["beyond_observed_range"],
                            "months_to_clear": {**row["months_to_clear"], "markdown": num(float(np.median(v["months"])), 1)},
                            "delta_vs_hold": _summ(gain), "delta_vs_liquidate": _summ(v["npv"] - liq),
                            "delta_p5": num(float(np.quantile(gain, 0.05))), "delta_p50": num(float(np.quantile(gain, 0.5))),
                            "delta_p95": num(float(np.quantile(gain, 0.95))), "p_loss": num(float(np.mean(gain < 0)), 4),
                            "mc_se": _summ(gain)["mc_se"],
                            # carry the markdown avoids: the hold path's months of surcharge and storage beyond the markdown's
                            "carry_saving_p50": num(max(0.0, (float(np.median(opts["hold"]["months"])) - float(np.median(v["months"])))
                                                        * float(row["carry_month_now"] or 0)))})
            elif pick["decision"] == "liquidate":
                gain = liq - hold
                row.update({"delta_vs_hold": _summ(gain), "delta_p5": num(float(np.quantile(gain, 0.05))),
                            "delta_p50": num(float(np.quantile(gain, 0.5))), "delta_p95": num(float(np.quantile(gain, 0.95))),
                            "p_loss": num(float(np.mean(gain < 0)), 4)})
            row["basis"] = (
                f"{'three' if fit else 'two'}-way valuation of {position:.0f} units on hand as cash proceeds net of fees "
                f"and carry, landed cost sunk, {opts['inputs']['draws']:,} common draws of rate{', elasticity' if fit else ''} "
                f"and fees; chosen by certainty equivalent inside a ${tol:,.0f} risk budget; "
                f"{'' if cliffs else 'no marketplace carry on this channel; '}decision {pick['decision']}"
                + (f" at {pick['depth']:.0%}" if pick["depth"] else "") + ".")
        # the mirror case
        p_out = float(inv.get("stockout_probability") or r.get("stockout_probability") or 0)
        if p_out >= STOCKOUT_ALERT and inv.get("lead_time_days"):
            tol_s = RISK_BUDGET_SHARE * max(trailing_monthly_net(m), 0.0) if m else 0.0
            row["stretch"] = stretch(int(inv.get("on_hand_units") or 0), float(inv["lead_time_days"]), rate_mean, rate_sd,
                                     fit, p0, f, big_f, rng=_rng(sku + "|stretch"), draws=draws, tol=tol_s)
        out_rows.append(row)

    decided = [r for r in out_rows if r.get("decision")]
    return {
        "status": "ok" if decided else "insufficient_data",
        "as_of": today.isoformat(),
        "rows": out_rows,
        "seed": MD_SEED,
        "summary": {
            "n_valued": len(decided),
            "markdown_candidates": [{"sku": r["sku"], "depth": r["depth"], "p_new": r.get("p_new"),
                                     "gain_vs_hold": r.get("delta_p50")} for r in decided if r["decision"] == "markdown"],
            "liquidation_candidates": [{"sku": r["sku"], "units": r["excess_units"],
                                        "liquidate_value": r["npv"]["liquidate"]["p50"], "hold_npv": r["npv"]["hold"]["p50"]}
                                       for r in decided if r["decision"] == "liquidate"],
            "liquidation_value": num(sum(r["npv"]["liquidate"]["p50"] or 0 for r in decided if r["decision"] == "liquidate")),
            "stretch_candidates": [{"sku": r["sku"], "p_new": r["stretch"]["p_new"], "step_fraction": r["stretch"]["step_fraction"]}
                                   for r in out_rows if (r.get("stretch") or {}).get("status") == "ok"],
            "n_no_elasticity": sum(1 for r in decided if r["status"] == "no_elasticity"),
        },
        "assumptions": [
            "Units on hand are valued as cash proceeds net of fees and carry; landed cost is sunk and excluded on every option",
            f"Markdown demand follows the fitted constant-elasticity curve; depths from {DEPTH_GRID[0]:.0%} to {DEPTH_GRID[-1]:.0%}, "
            f"floored where the markdown nets less per unit than liquidation",
            f"Discounting at {ANNUAL_CAPITAL_RATE:.0%}/yr is the only capital charge; leftovers after {MAX_HOLD_MONTHS} months liquidate",
            f"A markdown price under {RANGE_GUARD:.0%} of the lowest observed price is flagged as beyond the fitted range",
        ],
    }
