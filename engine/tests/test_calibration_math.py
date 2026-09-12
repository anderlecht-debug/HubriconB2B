"""Calibration: does a 90% range contain the truth 90% of the time?

Everything else in this engine is a claim about arithmetic. This file is the
only place that checks the claims are about reality — by building sellers whose
true elasticities and true demand we know, running the whole pipeline on their
exports, and counting how often the published range actually contained what
then happened.

A band that contains the truth 70% of the time is a lie with a decimal point on
it. A band that contains it 100% of the time is useless. The target is nominal.

WHAT THESE TESTS FOUND, so the numbers are on the record and not just in a
passing assertion:

    regime                     published 90% band    its 95% sibling    the old range
    7 periods, 20% noise              92.0%               96.4%         90.0% (claimed 95%)
    7 periods,  5% noise              92.5%               95.8%         84.7%
    7 periods, 45% noise              94.7%               97.0%         91.0%
    5 periods, any noise           95.6–96.7%          98.4%            83–86%

The band is correctly calibrated at seven periods and CONSERVATIVE at five.
The cause is identified, not mysterious: at five periods the residual degrees
of freedom are three, so HC3 (deliberately conservative in small samples,
measured at +10–15% on the standard error in test_elasticity_inference.py) and
a Student-t(3) draw (variance 3× a normal's) compound. Both choices are on the
safe side on purpose and their composition is safer still. We report that
rather than tune it: over-covering means the step the engine recommends on a
thin SKU is smaller than strictly necessary, which costs a little upside and
cannot cost a seller money.

The old construction — two elasticity endpoints pushed through the profit
function, labelled a 95% range — covered 83% to 91%. It was not conservative
and it was not calibrated; it was uncontrolled, because it never modelled the
demand shock that multiplies the whole delta.
"""

from functools import lru_cache

import numpy as np
import pytest

from hubricon_engine.models import elasticity
from hubricon_engine.models.pricing_engine import (
    delta_at,
    delta_draws,
    price_move,
    profit_delta,
)

N_SKUS = 1000
N_PERIODS = 7
TRUE_FEE_RATE = 0.15
TRUE_FIXED_FEE = 1.50
TRUE_UNIT_COST = 5.00
BASE_PRICE = 20.0


def _rows(sku, prices, units):
    out = []
    for i, (p, u) in enumerate(zip(prices, units), start=1):
        revenue = float(p) * float(u)
        out.append({
            "sku": sku, "asin": "B0" + sku,
            "period_start": f"2026-{i:02d}-01", "period_end": f"2026-{i:02d}-28",
            "units_sold": float(u), "avg_sales_price": float(p), "sales": revenue,
            "referral_fees": -TRUE_FEE_RATE * revenue,
            "fba_fulfillment_fees": -TRUE_FIXED_FEE * float(u),
            "storage_fees": 0.0, "other_fees": 0.0,
            "net_proceeds": revenue,
        })
    return out


def _margin_row(sku, price, units):
    """The latest-period margin row the engine would have built, with the
    itemised fee split the real margin model produces."""
    revenue = price * units
    return {
        "sku": sku, "period_start": f"2026-{N_PERIODS:02d}-01",
        "period_end": f"2026-{N_PERIODS:02d}-28",
        "units": units, "revenue": revenue,
        "amazon_fees": TRUE_FEE_RATE * revenue + TRUE_FIXED_FEE * units,
        "cogs": TRUE_UNIT_COST * units,
        "fee_split": {"basis": "itemized", "proportional_rate": TRUE_FEE_RATE,
                      "fixed_per_unit": TRUE_FIXED_FEE,
                      "proportional_fees": TRUE_FEE_RATE * revenue,
                      "fixed_fees": TRUE_FIXED_FEE * units},
    }


def _population(seed=7, n_skus=N_SKUS, n_periods=N_PERIODS, demand_sd=0.20,
                eps_lo=-3.2, eps_hi=-1.3):
    """A synthetic catalog: each SKU a true elasticity, a noisy price history
    the engine will fit, and a held-out demand shock for the period the
    promise is about."""
    rng = np.random.default_rng(seed)
    truths = rng.uniform(eps_lo, eps_hi, size=n_skus)
    econ, meta = [], []
    for i, e_true in enumerate(truths):
        sku = f"S{i:04d}"
        prices = BASE_PRICE * np.exp(rng.normal(0, 0.09, size=n_periods))
        scale = 400.0
        units = scale * (prices / BASE_PRICE) ** e_true * np.exp(
            rng.normal(0, demand_sd, size=n_periods))
        econ += _rows(sku, prices, units)
        meta.append({
            "sku": sku, "eps_true": float(e_true), "scale": scale,
            "p0": float(prices[-1]), "q0": float(units[-1]),
            # the demand shock for the period the promise covers: unobserved
            # when the promise is made, common to both arms of the
            # counterfactual, exactly as measurement computes it
            "future_shock": float(np.exp(rng.normal(0, demand_sd))),
        })
    data = {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [], "cogs_inputs": []}
    return data, meta


def _realized_delta(m, p_new):
    """What actually happened: the profit difference between the two prices in
    the next period, under the SKU's TRUE elasticity and the one demand shock
    that period got. Both arms share the shock, so the shock cancels out of the
    comparison exactly the way the measurement pass makes it cancel."""
    a = m["scale"] * m["future_shock"] / BASE_PRICE ** m["eps_true"]

    def pi(p):
        q = a * p ** m["eps_true"]
        return q * (p * (1 - TRUE_FEE_RATE) - TRUE_UNIT_COST - TRUE_FIXED_FEE)

    return pi(p_new) - pi(m["p0"])


@lru_cache(maxsize=None)
def _run_population(**kw):
    """Cached: the whole pipeline on one synthetic catalog is deterministic, and
    several tests score the same population different ways."""
    data, meta = _population(**kw)
    fits = {f["item_id"]: f for f in elasticity.run(data)
            if f["level"] == "sku" and f["status"] == "ok"}
    out = []
    for m in meta:
        fit = fits.get(m["sku"])
        if not fit:
            continue
        row = _margin_row(m["sku"], m["p0"], m["q0"])
        move = price_move(row, fit)
        if not move:
            continue
        out.append((m, fit, row, move))
    return out


# ── the headline number ───────────────────────────────────────────────────

def _coverage(cases, lo_key="delta_p5", hi_key="delta_p95"):
    inside = sum(move[lo_key] <= _realized_delta(m, move["p_new"]) <= move[hi_key]
                 for m, _, _, move in cases)
    return inside / len(cases)


def test_ninety_percent_band_contains_the_realized_delta_about_ninety_percent_of_the_time():
    """1,000 synthetic SKUs, seven periods each, 20% demand noise — the engine's
    typical working conditions. The published P5-to-P95 range is a 90% band."""
    cases = _run_population()
    assert len(cases) >= 800, f"only {len(cases)} SKUs produced a move"
    coverage = _coverage(cases)
    assert 0.89 <= coverage <= 0.95, f"coverage {coverage:.3f} on {len(cases)} SKUs"


def test_the_same_band_at_the_ninety_five_percent_level_is_nominal_too():
    """The scorecard's calibration bar is stated for 95% intervals, so measure
    one: the same draws, read at P2.5 and P97.5."""
    cases = _run_population()
    inside = 0
    for m, fit, row, move in cases:
        d = fit["details"]
        draws = delta_at(delta_draws(
            eps=float(fit["elasticity"]), std_err=float(fit["std_err"]), dof=d["dof"],
            p0=m["p0"], q0=m["q0"], unit_cost=TRUE_UNIT_COST, fee_rate=TRUE_FEE_RATE,
            fixed_fee=TRUE_FIXED_FEE, demand_sd_log=d["residual_sd_log"]), move["p_new"])
        lo, hi = np.quantile(draws, [0.025, 0.975])
        inside += lo <= _realized_delta(m, move["p_new"]) <= hi
    coverage = inside / len(cases)
    assert 0.93 <= coverage <= 0.975, f"coverage {coverage:.3f}"


def test_coverage_holds_across_demand_noise_regimes():
    """A calibrated band stays calibrated when the world gets noisier. An
    uncontrolled one does not — which is the whole point of the comparison in
    the next test."""
    for sd in (0.05, 0.20, 0.45):
        cases = _run_population(seed=7, n_skus=500, demand_sd=sd)
        coverage = _coverage(cases)
        assert 0.89 <= coverage <= 0.96, f"demand_sd={sd}: coverage {coverage:.3f}"


def test_coverage_is_not_an_artifact_of_which_skus_were_recommended():
    """The coverage above is conditional on the engine having recommended a
    move, and the robust policy recommends on fewer than half the catalog. So
    measure the band unconditionally too: a fixed 2% step on EVERY fitted SKU,
    recommended or not, scored the same way. If the conditional number were
    flattered by selection, this one would not hold up."""
    data, meta = _population(seed=23, n_skus=600)
    fits = {f["item_id"]: f for f in elasticity.run(data)
            if f["level"] == "sku" and f["status"] == "ok"}
    inside = total = 0
    for m in meta:
        fit = fits.get(m["sku"])
        if not fit:
            continue
        d = fit["details"]
        p_new = m["p0"] * 1.02
        draws = delta_at(delta_draws(
            eps=float(fit["elasticity"]), std_err=float(fit["std_err"]), dof=d["dof"],
            p0=m["p0"], q0=m["q0"], unit_cost=TRUE_UNIT_COST, fee_rate=TRUE_FEE_RATE,
            fixed_fee=TRUE_FIXED_FEE, demand_sd_log=d["residual_sd_log"]), p_new)
        lo, hi = np.quantile(draws, [0.05, 0.95])
        inside += lo <= _realized_delta(m, p_new) <= hi
        total += 1
    coverage = inside / total
    assert total >= 550
    assert 0.88 <= coverage <= 0.96, f"unconditional coverage {coverage:.3f} on {total}"


def test_the_band_is_conservative_at_five_periods_and_we_say_by_how_much():
    """Five periods is the engine's own floor, dof = 3, and the band over-covers
    there. This test pins the amount so it cannot drift unnoticed, and the
    module docstring names the cause."""
    cases = _run_population(seed=11, n_skus=600, n_periods=5, demand_sd=0.25)
    assert len(cases) >= 400
    coverage = _coverage(cases)
    assert 0.94 <= coverage <= 0.985, f"coverage {coverage:.3f} on {len(cases)} SKUs"
    # conservative, never the other way
    assert coverage > 0.90


def test_the_old_two_endpoint_construction_was_uncontrolled():
    """The same populations, scored against the range the engine used to
    publish: the raw unshrunk elasticity, a classical standard error, ±1.96,
    the blended fee rate, two endpoints through the profit function, labelled a
    95% range. Its coverage is below its claim in every regime and swings by
    seven points across them — not conservative, not calibrated, uncontrolled."""
    observed = []
    for sd in (0.05, 0.20, 0.45):
        cases = _run_population(seed=7, n_skus=500, demand_sd=sd)
        inside = 0
        for m, fit, row, move in cases:
            d = fit["details"]
            e_raw, se_classical = float(d["epsilon_raw"]), float(d["std_err_classical"])
            blended = row["amazon_fees"] / row["revenue"]
            lo, hi = sorted(
                float(profit_delta(e_raw + sign * 1.96 * se_classical, m["p0"], m["q0"],
                                   TRUE_UNIT_COST, blended, move["p_new"], 0.0))
                for sign in (-1, 1)
            )
            inside += lo <= _realized_delta(m, move["p_new"]) <= hi
        observed.append(inside / len(cases))
        # it claimed 95% and never got there
        assert observed[-1] < 0.92, f"demand_sd={sd}: {observed[-1]:.3f}"
    assert max(observed) - min(observed) > 0.04


def test_the_loss_probability_is_calibrated():
    """P(delta < 0) is read by a seller as "how often does this backfire".
    The aggregate forecast must match the aggregate outcome, and it must
    discriminate between SKUs rather than only average out."""
    cases = _run_population()
    predicted = np.array([float(move["p_loss"]) for _, _, _, move in cases])
    realized = np.array([_realized_delta(m, move["p_new"]) < 0 for m, _, _, move in cases])
    # the aggregate forecast tracks the aggregate outcome, slightly pessimistic
    assert predicted.mean() == pytest.approx(float(realized.mean()), abs=0.07)
    assert predicted.mean() >= float(realized.mean()) - 0.02
    # and it discriminates between SKUs rather than only averaging out
    risky = predicted > np.median(predicted)
    assert realized[risky].mean() > realized[~risky].mean() + 0.05


# ── recovery of a known elasticity, including at the pole ─────────────────

def _recovery(e_true, n_skus=400, n_periods=9, demand_sd=0.18, seed=31):
    """Fit a catalog whose every SKU has the SAME true elasticity, so recovery
    and interval coverage can both be measured against one number."""
    rng = np.random.default_rng(seed)
    econ = []
    for i in range(n_skus):
        prices = BASE_PRICE * np.exp(rng.normal(0, 0.10, size=n_periods))
        units = 400.0 * (prices / BASE_PRICE) ** e_true * np.exp(
            rng.normal(0, demand_sd, size=n_periods))
        econ += _rows(f"R{i:04d}", prices, units)
    data = {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [], "cogs_inputs": []}
    return [f for f in elasticity.run(data)
            if f["level"] == "sku" and f["status"] == "ok"]


@pytest.mark.parametrize("e_true", [-3.0, -2.0, -1.5, -1.05, -0.95, -0.4])
def test_the_pipeline_recovers_a_known_elasticity(e_true):
    """Across the whole range, including either side of the pole at −1: the
    median raw fit lands on the truth and the interval covers it nominally.

    The raw estimate is the one checked for unbiasedness. The shrunk estimate is
    deliberately biased toward the pool — that is what shrinkage is — and on a
    catalog where every SKU shares one true ε the pool IS the truth, so shrinkage
    makes it more accurate, not less. Both are asserted."""
    fits = _recovery(e_true)
    assert len(fits) > 350
    raw = np.array([f["details"]["epsilon_raw"] for f in fits])
    shrunk = np.array([f["details"]["epsilon_shrunk"] for f in fits])

    assert np.median(raw) == pytest.approx(e_true, abs=0.12)
    # shrinkage toward a pool centred on the truth tightens the spread
    assert shrunk.std() < raw.std()
    assert abs(np.median(shrunk) - e_true) <= abs(np.median(raw) - e_true) + 0.05

    covered = np.mean([f["details"]["ci95_raw"][0] <= e_true <= f["details"]["ci95_raw"][1]
                       for f in fits])
    assert 0.92 <= covered <= 0.99, f"eps={e_true}: raw interval coverage {covered:.3f}"


def test_near_the_pole_the_engine_recovers_epsilon_and_still_refuses_a_destination():
    """Recovery and refusal are not in tension. At ε = −1.05 the fit finds the
    elasticity, and the pole guard still declines to name a price — because
    ε/(1+ε) is 21 there and the interval spans values where it is 3 and values
    where it is unbounded."""
    from hubricon_engine.models.pricing_engine import near_unit_elastic

    fits = _recovery(-1.05)
    raw = np.array([f["details"]["epsilon_raw"] for f in fits])
    assert np.median(raw) == pytest.approx(-1.05, abs=0.12)

    guarded = np.mean([near_unit_elastic(float(f["elasticity"]), f["std_err"],
                                        f["details"]["ci95"]) for f in fits])
    assert guarded > 0.95, f"only {guarded:.1%} of pole-adjacent fits were guarded"

    # and the destination is withheld end to end
    margin_rows = [_margin_row(f["item_id"], BASE_PRICE, 400.0) for f in fits[:40]]
    moves = [price_move(row, fit) for row, fit in zip(margin_rows, fits[:40])]
    assert moves.count(None) < len(moves)
    assert all(m["destination"] is None for m in moves if m)


def test_a_clearly_elastic_catalog_is_not_over_guarded():
    """The guard must not swallow the cases it was not built for: at ε = −3 with
    nine periods, most fits should name a destination."""
    from hubricon_engine.models.pricing_engine import near_unit_elastic

    fits = _recovery(-3.0, n_skus=300, n_periods=14, demand_sd=0.12)
    guarded = np.mean([near_unit_elastic(float(f["elasticity"]), f["std_err"],
                                        f["details"]["ci95"]) for f in fits])
    assert guarded < 0.2, f"{guarded:.1%} of clearly elastic fits were guarded"
