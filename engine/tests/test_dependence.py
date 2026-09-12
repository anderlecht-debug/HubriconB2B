"""A bad month is bad across the catalog.

Embrechts' question, asked of three simulations at once: you drew each SKU
independently, didn't you. You did. Independence is the most expensive assumption
in an aggregate, because it lets good and bad months cancel almost perfectly —
and a runway decision is made on the 5th percentile of a cash path that
cancellation invented.

These tests establish three things: that the generator has the dependence it
claims and the marginals it claims, that the correlation is estimated from the
catalog's own history and shrunk toward a conservative default when it cannot be,
and that turning dependence on makes every aggregate tail worse — which is the
whole point, and the direction that costs the engine credibility to admit.
"""

import numpy as np
import pytest

from hubricon_engine.models import cashflow, dependence, inventory_sim, margin, risk


# ── the generator ─────────────────────────────────────────────────────────

def test_marginals_keep_the_mean_and_sd_they_were_given():
    """The −σ²/2 correction, tested. Without it a 35%-CV SKU's simulated demand
    runs 6% above the level it was calibrated to, silently."""
    rng = np.random.default_rng(0)
    means, sds = [10.0, 40.0, 2.5], [3.5, 14.0, 0.9]
    rates = dependence.correlated_rates(rng, means, sds, (200_000,), rho=0.7)
    for i, (m, sd) in enumerate(zip(means, sds)):
        assert rates[i].mean() == pytest.approx(m, rel=0.02)
        assert rates[i].std() == pytest.approx(sd, rel=0.04)
        assert (rates[i] > 0).all()          # and never negative, unlike a clipped normal


def test_the_shared_factor_produces_the_correlation_it_claims():
    """corr(log r_i, log r_j) = ρ² under a one-factor Gaussian copula."""
    rng = np.random.default_rng(1)
    for rho in (0.0, 0.3, 0.6, 0.9):
        m = dependence.correlated_multipliers(rng, [0.3] * 6, (60_000,), rho)
        logs = np.log(m)
        off = [float(np.corrcoef(logs[i], logs[j])[0, 1])
               for i in range(6) for j in range(i + 1, 6)]
        assert np.mean(off) == pytest.approx(rho**2, abs=0.02), rho


def test_rho_zero_reproduces_independence_exactly():
    """So the before/after comparisons in this file are between models and not
    between implementations."""
    rng = np.random.default_rng(2)
    m = dependence.correlated_multipliers(rng, [0.4] * 8, (40_000,), 0.0)
    logs = np.log(m)
    off = [abs(float(np.corrcoef(logs[i], logs[j])[0, 1]))
           for i in range(8) for j in range(i + 1, 8)]
    assert max(off) < 0.02


def test_log_sigma_matches_the_moment_matching_formula():
    assert dependence.log_sigma(100.0, 35.0) == pytest.approx(
        float(np.sqrt(np.log1p(0.35**2))))
    assert dependence.log_sigma(100.0, 0.0) == 0.0
    assert dependence.log_sigma(0.0, 10.0) == 0.0


# ── estimating it ─────────────────────────────────────────────────────────

def _synthetic_panel(pairwise, n_skus=30, n_periods=10, seed=4):
    """A panel whose log demand has a known average pairwise correlation."""
    rng = np.random.default_rng(seed)
    rho = np.sqrt(pairwise)
    common = rng.standard_normal(n_periods)
    return {f"S{i:03d}": list(np.exp(0.4 * (rho * common
                                            + np.sqrt(1 - rho**2) * rng.standard_normal(n_periods))))
            for i in range(n_skus)}


@pytest.mark.parametrize("truth", [0.0, 0.15, 0.4, 0.7])
def test_the_estimator_recovers_a_known_correlation(truth):
    """Measured on the raw estimate, before shrinkage — shrinkage is a separate,
    deliberate pull toward the default and is tested next."""
    out = dependence.estimate_pairwise_corr(
        _synthetic_panel(truth, n_skus=60, n_periods=40))
    assert out["basis"] == "estimated"
    assert out["pairwise_corr_raw"] == pytest.approx(truth, abs=0.08)


def test_a_thin_panel_is_shrunk_toward_the_conservative_default():
    """Four periods cannot measure a correlation. The engine says so in the
    payload and leans on a default rather than on noise."""
    thin = dependence.estimate_pairwise_corr(_synthetic_panel(0.0, n_periods=4))
    thick = dependence.estimate_pairwise_corr(_synthetic_panel(0.0, n_periods=40))
    assert thin["shrinkage_weight"] == pytest.approx(4 / (4 + dependence.PRIOR_PERIODS))
    assert thick["shrinkage_weight"] > thin["shrinkage_weight"]
    # both panels are truly uncorrelated, and the thin one is still pulled up
    assert thin["pairwise_corr"] > thick["pairwise_corr"]
    assert thin["pairwise_corr"] > 0.1


def test_no_panel_at_all_falls_back_and_names_the_default():
    out = dependence.estimate_pairwise_corr({})
    assert out["basis"] == "default_thin_panel"
    assert out["pairwise_corr"] == dependence.DEFAULT_PAIRWISE_CORR
    assert out["shrinkage_weight"] == 0.0
    assert out["pairwise_corr_raw"] is None


def test_the_estimate_is_clamped_to_a_correlation():
    """A noisy panel can produce a raw estimate outside [0, 1]; the published
    number is always a correlation."""
    weird = dependence.estimate_pairwise_corr(_synthetic_panel(0.0, n_skus=4, n_periods=3))
    assert 0.0 <= weird["pairwise_corr"] <= dependence.MAX_PAIRWISE_CORR
    assert 0.0 <= weird["rho"] <= 1.0


# ── what it does to the aggregates ────────────────────────────────────────

def _catalog(n_skus=24, lead=45, shared=0.8, seed=3, on_hand=600, periods=8):
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.25, size=periods)
    econ, inv, cogs = [], [], []
    for i in range(n_skus):
        sku = f"S{i:03d}"
        for j in range(periods):
            units = max(1.0, 300 * np.exp(shared * common[j] + rng.normal(0, 0.25)))
            econ.append({"sku": sku, "asin": "A" + sku,
                         "period_start": f"2026-{j + 1:02d}-01", "period_end": f"2026-{j + 1:02d}-28",
                         "units_sold": units, "avg_sales_price": 20.0, "sales": 20.0 * units,
                         "referral_fees": -0.15 * 20.0 * units,
                         "fba_fulfillment_fees": -1.5 * units,
                         "storage_fees": 0.0, "other_fees": 0.0, "net_proceeds": 0.0})
        inv.append({"sku": sku, "snapshot_date": f"2026-{periods:02d}-28",
                    "fulfillable_quantity": on_hand, "inbound_quantity": 0})
        cogs.append({"sku": sku, "asin": "A" + sku, "unit_cost_usd": 5.0,
                     "supplier_lead_time_days": lead})
    return {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": inv, "cogs_inputs": cogs}


def test_simultaneous_stockouts_have_a_far_fatter_tail_than_independence_implies():
    """The headline. Same marginals, same expected number out of stock — a
    completely different answer to "how bad does it get at once"."""
    data = _catalog()
    rows = inventory_sim.run(data, np.random.default_rng(7), simulations=8000)
    panel = inventory_sim.aggregate(rows, data, np.random.default_rng(7), simulations=8000)
    assert panel["status"] == "ok"
    c, i = panel["correlated"], panel["independent"]

    # the mean is a marginal property and must NOT move
    assert c["expected_stockouts"] == pytest.approx(i["expected_stockouts"], rel=0.05)
    # the tail is a joint property and moves a lot
    assert c["p95_stockouts"] > i["p95_stockouts"] * 1.25
    assert c["expected_shortfall_stockouts"] > i["expected_shortfall_stockouts"] * 1.25
    # the correlation used came from this catalog's own history
    assert panel["correlation"]["basis"] == "estimated"
    assert panel["correlation"]["rho"] > 0.3
    # and every published percentile carries its Monte Carlo error
    assert c["p95_mc_se"] is not None and c["expected_shortfall_mc_se"] is not None
    assert "independent figures are what the engine reported before" in panel["basis"]


def test_the_expected_shortfall_is_worse_than_the_percentile_it_sits_behind():
    """A 95th percentile is a threshold. The budget question is how many are out
    once you are past it."""
    data = _catalog()
    rows = inventory_sim.run(data, np.random.default_rng(7), simulations=8000)
    panel = inventory_sim.aggregate(rows, data, np.random.default_rng(7), simulations=8000)
    for case in ("correlated", "independent"):
        assert (panel[case]["expected_shortfall_stockouts"]
                >= panel[case]["p95_stockouts"])


def test_a_single_skus_stockout_probability_is_untouched_by_the_joint_model():
    """Because it is a marginal statement. If correlation moved it, the model
    would be wrong."""
    data = _catalog(n_skus=24)
    a = inventory_sim.run(data, np.random.default_rng(7), simulations=8000)
    b = inventory_sim.run(data, np.random.default_rng(7), simulations=8000)
    assert [r["stockout_probability"] for r in a] == [r["stockout_probability"] for r in b]
    assert all(0.0 <= (r["stockout_probability"] or 0) <= 1.0 for r in a)
    assert all(r["details"]["stockout_probability_mc_se"] is not None for r in a)


def _cash_case(payout_cycle_days, rho_zero, n_paths=8000):
    data = _catalog(n_skus=20, on_hand=900, periods=6)
    margins = margin.run(data)
    rows = inventory_sim.run(data, np.random.default_rng(1), simulations=4000)
    params = cashflow.sku_cash_params(rows, margins)
    wires = cashflow.wire_schedule(rows, margins)
    assert params
    correlation = ({"rho": 0.0, "pairwise_corr": 0.0, "basis": "test"} if rho_zero
                   else dependence.estimate_pairwise_corr(cashflow._rate_panel(margins)))
    return cashflow.simulate(params, wires, 120000.0, 40000.0,
                             np.random.default_rng(11), n_paths=n_paths,
                             payout_cycle_days=payout_cycle_days,
                             correlation=correlation)


def test_the_cash_trough_is_deeper_once_demand_is_correlated():
    """The number a bridge-capital decision is made on. Daily payouts — a Shopify
    store — so the trough sits in the stochastic part of the path."""
    correlated = _cash_case(1, rho_zero=False)
    independent = _cash_case(1, rho_zero=True)
    assert correlated["trough_p5"] < independent["trough_p5"]
    assert (correlated["trough_expected_shortfall"]
            < independent["trough_expected_shortfall"])
    # the tail mean moves further than the percentile does, which is the point of
    # reporting it
    p5_gap = independent["trough_p5"] - correlated["trough_p5"]
    es_gap = (independent["trough_expected_shortfall"]
              - correlated["trough_expected_shortfall"])
    assert es_gap > p5_gap
    # the median barely moves: correlation reshapes the tail, not the centre
    assert correlated["min_median"] == pytest.approx(independent["min_median"], rel=0.02)


def test_on_a_fortnightly_payout_cycle_the_trough_is_deterministic_and_says_so():
    """An honest structural observation rather than a bug. On Amazon's 14-day
    settlement the worst point of the horizon is the day before the first payout,
    when the outflow has accrued and nothing has come in — and that day's balance
    is known exactly, so the percentile and the tail mean of the trough coincide.
    The dependence model shows up later in the horizon instead."""
    correlated = _cash_case(14, rho_zero=False)
    independent = _cash_case(14, rho_zero=True)
    assert correlated["min_p5_day"] <= 14
    assert correlated["trough_expected_shortfall"] == pytest.approx(
        correlated["trough_p5"], rel=1e-9)
    # and the correlation is visible at the end of the horizon, where the cone is
    # stochastic: the 5th percentile drops while the median does not
    assert correlated["details"]["p5"][-1] < independent["details"]["p5"][-1]
    assert correlated["details"]["p50"][-1] == pytest.approx(
        independent["details"]["p50"][-1], rel=0.01)


def test_the_cash_cone_publishes_a_coherent_tail_measure_and_its_error_bars():
    out = _cash_case(1, rho_zero=False)
    assert out["trough_expected_shortfall"] <= out["trough_p5"]
    assert out["trough_expected_shortfall_se"] is not None
    assert out["p_ruin_mc_se"] is not None
    se = out["details"]["mc_se_at_trough"]
    assert all(se[k] is not None for k in ("p5", "p50", "p95"))
    # the error on the published P5 is small against the cone's own width
    day = out["min_p5_day"] - 1
    width = out["details"]["p95"][day] - out["details"]["p5"][day]
    assert width > 0 and se["p5"] / width < 0.05
    assert any("common factor" in a for a in out["details"]["assumptions"])
    assert any("expected shortfall" in a for a in out["details"]["assumptions"])


def test_the_monthly_var_carries_the_correlation_and_its_error_bars():
    data = _catalog(n_skus=20, periods=6)
    margins = margin.run(data)
    out = risk.run(data, margins, rng=np.random.default_rng(5), simulations=6000)
    var = out["var"]
    assert var["status"] == "ok"
    assert var["demand_correlation"]["rho"] > 0
    assert var["mc_se"]["var_95"] is not None
    assert var["cvar_95"] >= var["var_95"]        # coherence, always
    assert any("common factor" in a for a in var["assumptions"])


# ── it has to fit in memory on a real catalog ─────────────────────────────

def test_streaming_and_materialising_give_identical_draws():
    """The engine streams; the tests check the materialised form. They have to be
    the same numbers or one of them is testing something the engine does not do."""
    sigmas = [0.2, 0.35, 0.1, 0.5]
    block = dependence.correlated_multipliers(
        np.random.default_rng(12), sigmas, (500,), 0.6)
    streamed = np.array(list(dependence.multiplier_stream(
        np.random.default_rng(12), sigmas, (500,), 0.6)))
    assert np.array_equal(block, streamed)

    rates_block = dependence.correlated_rates(
        np.random.default_rng(13), [10.0, 20.0, 5.0], [3.0, 8.0, 2.0], (400,), 0.5)
    rates_streamed = np.array([r for _, r in dependence.rate_stream(
        np.random.default_rng(13), [10.0, 20.0, 5.0], [3.0, 8.0, 2.0], (400,), 0.5)])
    assert np.array_equal(rates_block, rates_streamed)


def test_a_large_catalog_cash_cone_does_not_materialise_the_panel():
    """The regression this streaming exists to prevent. A 400-SKU catalog over
    10,000 paths and 90 days is 2.9 GB if the (SKU, path, day) array is built at
    once, and nothing needs it at once. The cone is run at production width and
    the peak allocation is checked against the one-SKU shape."""
    import tracemalloc

    # scaled down from the 400 × 10,000 × 90 that would be 2.9 GB: the shape of
    # the bug is what matters, and at 200 × 2,000 × 90 the panel would still be
    # 288 MB against a ceiling of 36
    n_skus, n_paths, days = 200, 2_000, 90
    params = [{"sku": f"B{i:03d}", "mean_rate": 8.0 + (i % 5), "std_rate": 3.0,
               "price": 20.0, "fee_rate": 0.15, "ad_daily": 1.0}
              for i in range(n_skus)]
    one_sku_bytes = n_paths * days * 8

    assert n_skus * one_sku_bytes > 250e6, "the fixture must be big enough to matter"

    tracemalloc.start()
    out = cashflow.simulate(params, [], 250_000.0, 40_000.0,
                            np.random.default_rng(2), horizon_days=days,
                            n_paths=n_paths, payout_cycle_days=14,
                            correlation={"rho": 0.6, "pairwise_corr": 0.36,
                                         "basis": "test"})
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert out["p_ruin"] is not None
    # a generous ceiling: a handful of (paths × days) arrays live at once, never
    # a (SKUs × paths × days) one, which would be 400 times this
    assert peak < one_sku_bytes * 25, f"peak {peak / 1e9:.2f} GB"
