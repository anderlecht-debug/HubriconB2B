"""What the anomaly sweep says when there is nothing to say.

This is the Harvey / López de Prado question: how many tests did you run before
that alert fired? `anomaly.py` runs four detectors over every fee line, traffic
metric, campaign and settlement bucket, which on a real catalog is thousands of
tests a sweep. A detector threshold calibrated for one series, applied to
thousands, produces confident dollar figures about noise every cycle.

The artifact is a panel of pure noise. 500 synthetic SKUs whose fees, units and
sales are random walks around a constant with no planted shift of any kind. If
the sweep is honest, almost nothing survives.
"""

import numpy as np
import pytest

from hubricon_engine.models import anomaly
from hubricon_engine.models.null_calibration import (
    NULL_REPLICATES,
    benjamini_hochberg,
    null_distribution,
    p_value,
)


def _noise_panel(n_skus=500, n_periods=10, seed=5):
    """Fees that wander, units that wander, nothing that steps."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_skus):
        sku = f"N{i:04d}"
        units = np.clip(rng.normal(100, 12, size=n_periods), 1, None)
        fee_per_unit = np.clip(rng.normal(3.0, 0.22, size=n_periods), 0.1, None)
        referral = rng.normal(0.15, 0.008, size=n_periods)
        price = np.clip(rng.normal(20.0, 1.0, size=n_periods), 1, None)
        for j in range(n_periods):
            sales = float(price[j] * units[j])
            rows.append({
                "sku": sku, "asin": "A" + sku,
                "period_start": f"2026-{j + 1:02d}-01", "period_end": f"2026-{j + 1:02d}-28",
                "units_sold": float(units[j]), "avg_sales_price": float(price[j]),
                "sales": sales,
                "referral_fees": -float(referral[j]) * sales,
                "fba_fulfillment_fees": -float(fee_per_unit[j]) * float(units[j]),
                "storage_fees": -float(rng.normal(12.0, 1.5)),
                "other_fees": 0.0, "net_proceeds": sales,
            })
    return {"sku_economics": rows, "asin_traffic": [], "ppc_spend": [],
            "ppc_search_terms": [], "settlement_transactions": []}


def _traffic_noise(n_asins=150, n_periods=10, seed=9):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_asins):
        for j in range(n_periods):
            rows.append({
                "child_asin": f"B{i:04d}", "parent_asin": None,
                "period_start": f"2026-{j + 1:02d}-01", "period_end": f"2026-{j + 1:02d}-28",
                "sessions": float(rng.normal(4000, 450)),
                "unit_session_pct": float(rng.normal(9.0, 0.9)),
                "buy_box_pct": float(np.clip(rng.normal(92, 4), 0, 100)),
                "units_ordered": float(rng.normal(360, 45)),
                "ordered_product_sales": float(rng.normal(7200, 900)),
            })
    return rows


# ── the headline artifact ─────────────────────────────────────────────────

def test_five_hundred_noise_skus_produce_almost_no_alerts():
    """The number that matters. With false-discovery control the expected count
    of surviving alerts on a pure-noise panel is near zero; without it the
    detectors fire dozens of times with dollar figures attached."""
    rows = anomaly.run(_noise_panel())
    surviving = [r for r in rows if r["flagged"]]
    detector_only = [r for r in rows if r["detector_flagged"]]

    assert rows[0]["n_tests"] > 2000, "the panel should be thousands of tests"
    # the detectors, left to themselves, call noise a finding many times over
    assert len(detector_only) >= 20, len(detector_only)
    # with the control, essentially nothing survives
    assert len(surviving) <= 3, [
        (r["item_id"], r["metric"], r["detector"], r["p_value"], r["q_value"])
        for r in surviving
    ]


def test_the_cost_of_the_control_is_reported_not_hidden():
    """A seller is told how many tests stood behind the alerts they did get."""
    rows = anomaly.run(_noise_panel(n_skus=120))
    summary = anomaly.summarize(rows)
    assert summary["n_tests"] > 0
    assert summary["detector_flagged"] >= summary["flagged"]
    assert summary["fdr_q"] == anomaly.FDR_Q
    assert summary["fdr_p_threshold"] is not None
    for row in rows:
        if row["p_value"] is not None:
            assert row["n_tests"] == summary["n_tests"]


def test_a_demoted_row_says_why_and_keeps_no_dollar_figure():
    """The demotion has to be legible: no direction, no dollars, and a sentence
    naming the multiplicity rather than a blank."""
    rows = anomaly.run(_noise_panel(n_skus=200))
    demoted = [r for r in rows if r["detector_flagged"] and not r["flagged"]]
    assert demoted, "a noise panel should produce demotions"
    for r in demoted:
        assert r["dollar_impact"] is None
        assert r["direction"] is None and r["since"] is None
        assert r["delta"] is None
        assert "noise alone produces" in r["details"]["basis"]
        assert r["q_value"] is not None


def test_traffic_and_conversion_noise_is_quiet_too():
    """The robust-z detector on short series is the worst offender — at n = 6 its
    threshold of 3.5 sits near the 88th percentile of its own null. 150 ASINs of
    pure noise across three metrics must still come back empty."""
    data = {"sku_economics": [], "asin_traffic": _traffic_noise(), "ppc_spend": [],
            "ppc_search_terms": [], "settlement_transactions": []}
    rows = anomaly.run(data)
    surviving = [r for r in rows if r["flagged"]]
    assert rows[0]["n_tests"] > 500
    assert len(surviving) <= 2, [(r["item_id"], r["metric"], r["detector"]) for r in surviving]


# ── a real shift still gets through ───────────────────────────────────────

def test_a_real_fee_step_survives_the_control_on_a_large_catalog():
    """False-discovery control that suppressed real findings would be worse than
    the problem. One planted $1.20 FBA fee step, hidden inside 500 noise SKUs."""
    data = _noise_panel(n_skus=500)
    planted = []
    for j in range(10):
        units, price = 100.0, 20.0
        sales = units * price
        fee = 3.0 if j < 6 else 4.2
        planted.append({
            "sku": "REAL", "asin": "AREAL",
            "period_start": f"2026-{j + 1:02d}-01", "period_end": f"2026-{j + 1:02d}-28",
            "units_sold": units, "avg_sales_price": price, "sales": sales,
            "referral_fees": -0.15 * sales, "fba_fulfillment_fees": -fee * units,
            "storage_fees": -12.0, "other_fees": 0.0, "net_proceeds": sales,
        })
    data["sku_economics"] = data["sku_economics"] + planted
    rows = anomaly.run(data)
    hits = [r for r in rows if r["flagged"] and r["item_id"] == "REAL"
            and r["metric"] == "fba_fee_per_unit"]
    assert hits, "a planted step must still clear the control"
    r = hits[0]
    assert r["direction"] == "up" and r["dollar_impact"] == pytest.approx(120.0, abs=1.0)
    assert r["q_value"] < anomaly.FDR_Q
    assert r["p_basis"] in ("mc", "mc_tail")


# ── the p-values themselves ───────────────────────────────────────────────

@pytest.mark.parametrize("statistic", ["robust_z", "cusum", "changepoint", "spikes"])
def test_null_p_values_are_uniform(statistic):
    """A p-value that is not uniform under the null makes the whole procedure a
    guess. Draw fresh noise, compute the statistic through the same code path the
    detectors use, and check the p-values land uniformly."""
    rng = np.random.default_rng(77)
    n = 12
    ps = []
    for _ in range(600):
        y = rng.normal(50.0, 3.0, size=n)
        if statistic == "robust_z":
            stat = abs(anomaly.robust_z(y)["z"])
        elif statistic == "cusum":
            stat = anomaly.cusum(y)["s_max"]
        elif statistic == "changepoint":
            stat = anomaly.changepoint(y)["statistic"]
        else:
            stat = anomaly.spikes(y)["max_abs_z"]
        p, _ = p_value(statistic, n, stat)
        ps.append(p)
    ps = np.array(ps)
    # mean of a uniform is 0.5, and the 5% tail should hold about 5%
    assert 0.42 <= ps.mean() <= 0.58, ps.mean()
    assert 0.02 <= (ps <= 0.05).mean() <= 0.10, (ps <= 0.05).mean()
    assert 0.15 <= (ps <= 0.20).mean() <= 0.26, (ps <= 0.20).mean()


def test_the_tail_extrapolation_exists_because_the_counting_floor_is_too_coarse():
    """Why the peaks-over-threshold fit is there at all: a counted Monte Carlo
    p-value cannot go below 1/(R+1), and Benjamini–Hochberg on a 3,000-test sweep
    needs resolution an order of magnitude finer at the first rank."""
    floor = 1.0 / (NULL_REPLICATES + 1)
    first_rank_threshold = 0.05 / 3000
    assert floor > first_rank_threshold

    p_big, basis = p_value("changepoint", 10, 60.0)
    assert basis == "mc_tail"
    assert p_big < first_rank_threshold
    # and it is monotone: a bigger statistic is never a bigger p-value
    p_bigger, _ = p_value("changepoint", 10, 80.0)
    assert p_bigger < p_big


def test_a_counted_p_value_is_never_exactly_zero():
    """(1 + exceedances) / (R + 1): a statistic nothing in the null exceeded is
    still not proof."""
    draws, threshold, _ = null_distribution("cusum", 10)
    just_under = threshold * 0.999
    p, basis = p_value("cusum", 10, just_under)
    assert basis == "mc" and 0 < p <= 0.02


def test_null_distributions_are_deterministic_and_cached_by_length():
    a = null_distribution("changepoint", 14)
    b = null_distribution("changepoint", 14)
    assert a is b                      # the cache, not a coincidence
    assert a != null_distribution("changepoint", 15)


def test_benjamini_hochberg_matches_the_textbook_step_up():
    """Worked by hand: m = 5, q = 0.05. Thresholds are i·q/m = .01 .02 .03 .04
    .05; the largest rank whose p clears is 2 (0.019 ≤ 0.02), so the two
    smallest are rejected and 0.04 is not, even though 0.04 ≤ 0.05."""
    ps = [0.004, 0.019, 0.04, 0.3, 0.9]
    rejected, adjusted, cutoff = benjamini_hochberg(ps, 0.05)
    assert rejected == [True, True, False, False, False]
    assert cutoff == pytest.approx(0.02)
    assert adjusted[0] == pytest.approx(0.02)       # 0.004 * 5/1, capped monotone
    assert adjusted[1] == pytest.approx(0.0475)     # 0.019 * 5/2


def test_benjamini_hochberg_rejects_nothing_when_there_is_nothing():
    rejected, adjusted, cutoff = benjamini_hochberg([0.2, 0.5, 0.9], 0.05)
    assert rejected == [False, False, False]
    assert cutoff == 0.0
    assert benjamini_hochberg([], 0.05) == ([], [], 0.0)


def test_the_whole_sweep_is_reproducible():
    data = _noise_panel(n_skus=60)
    first = anomaly.run(data)
    second = anomaly.run(data)
    assert [(r["item_id"], r["metric"], r["detector"], r["p_value"], r["q_value"],
             r["flagged"]) for r in first] == [
        (r["item_id"], r["metric"], r["detector"], r["p_value"], r["q_value"],
         r["flagged"]) for r in second]
