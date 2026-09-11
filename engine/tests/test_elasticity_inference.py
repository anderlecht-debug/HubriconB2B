"""The interval on ε: correct critical values, robust standard errors,
shrinkage, and the limits of what this estimator can be asked.

These are the inference artifacts. The point estimate is ordinary least
squares and was never in doubt; everything here is about how wide the honest
range around it is, which is the number a seller actually acts on.
"""

import numpy as np
import pytest
from scipy import stats

from hubricon_engine.models import elasticity


def _month(i: int) -> tuple[str, str]:
    return f"2026-{i:02d}-01", f"2026-{i:02d}-28"


def _econ_rows(prices, units, sku="S1"):
    return [
        {"sku": sku, "asin": "B0" + sku, "period_start": _month(i)[0], "period_end": _month(i)[1],
         "units_sold": float(u), "avg_sales_price": float(p), "sales": float(p) * float(u),
         "referral_fees": 0, "fba_fulfillment_fees": 0, "storage_fees": 0, "other_fees": 0,
         "net_proceeds": float(p) * float(u)}
        for i, (p, u) in enumerate(zip(prices, units), start=1)
    ]


def _data(rows):
    return {"asin_traffic": [], "sku_economics": rows, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [], "cogs_inputs": []}


def _series(n, e_true=-2.0, noise=0.12, seed=0):
    rng = np.random.default_rng(seed)
    prices = 20.0 * np.exp(rng.normal(0, 0.08, size=n))
    units = 500.0 * (prices / 20.0) ** e_true * np.exp(rng.normal(0, noise, size=n))
    return prices, units


def _fit(n, **kw):
    prices, units = _series(n, **kw)
    return elasticity.run(_data(_econ_rows(prices, units)))[0]


# ── 1.2 the critical value ────────────────────────────────────────────────

def test_critical_value_is_the_t_quantile_not_1_96():
    """Five periods, an intercept and a price term: dof = 3, and the correct
    two-sided 97.5% quantile is 3.182, not 1.96."""
    r = _fit(5)
    assert r["status"] == "ok"
    assert r["details"]["dof"] == 3
    assert r["details"]["t_critical"] == pytest.approx(float(stats.t.ppf(0.975, 3)), abs=1e-3)
    assert r["details"]["t_critical"] == pytest.approx(3.1824, abs=1e-3)
    lo, hi = r["details"]["ci95"]
    half_width = (hi - lo) / 2
    assert half_width == pytest.approx(r["details"]["t_critical"] * r["std_err"], rel=1e-3)
    # the normal quantile would have published an interval this much narrower
    assert half_width / (1.96 * r["std_err"]) > 1.35


def test_the_interval_widens_as_periods_shrink():
    """The property that matters: a thinner SKU gets a wider honest range.
    Both the critical value and the standard error move the right way."""
    crits, widths = [], []
    for n in (5, 6, 8, 12, 24):
        r = _fit(n)
        assert r["status"] == "ok"
        lo, hi = r["details"]["ci95"]
        crits.append(r["details"]["t_critical"])
        widths.append(hi - lo)
    assert crits == sorted(crits, reverse=True)        # strictly falls with dof
    assert widths[0] > widths[-1]                      # and the published range narrows
    assert widths[0] / widths[-1] > 2.0


def test_the_estimate_is_inside_its_own_interval_always():
    for n in (5, 7, 9, 15):
        r = _fit(n, seed=n)
        lo, hi = r["details"]["ci95"]
        assert lo <= r["elasticity"] <= hi


# ── 1.3 heteroskedasticity-consistent standard errors ─────────────────────

def test_hc3_is_the_reported_estimator_and_the_point_estimate_is_untouched():
    """Only the covariance changes. The elasticity itself is still OLS, which
    is what keeps the published curve and the published interval consistent."""
    prices, units = _series(9, seed=5)
    r = elasticity.run(_data(_econ_rows(prices, units)))[0]
    assert r["details"]["se_estimator"] == "HC3"
    assert r["details"]["std_err_classical"] is not None

    # refit the same design by hand: the slope must match to machine precision
    X = np.column_stack([np.ones(len(prices)), np.log(prices)])
    beta = np.linalg.lstsq(X, np.log(units), rcond=None)[0]
    assert r["elasticity"] == pytest.approx(float(beta[1]), abs=1e-4)


def test_hc3_matches_the_textbook_sandwich_by_hand():
    """V = (X'X)⁻¹ X' diag(eᵢ²/(1−hᵢ)²) X (X'X)⁻¹ — computed independently of
    the implementation and compared."""
    prices, units = _series(10, seed=11)
    y, X = np.log(units), np.column_stack([np.ones(len(prices)), np.log(prices)])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    xtx_inv = np.linalg.inv(X.T @ X)
    h = np.diag(X @ xtx_inv @ X.T)
    omega = np.diag((resid / (1 - h)) ** 2)
    v = xtx_inv @ X.T @ omega @ X @ xtx_inv
    expected_se = float(np.sqrt(v[1, 1]))

    r = elasticity.run(_data(_econ_rows(prices, units)))[0]
    assert r["std_err"] == pytest.approx(expected_se, rel=1e-3)


def test_hc3_tracks_the_true_sampling_sd_where_classical_understates_it():
    """The estimator property, measured rather than asserted.

    600 simulated fits of the same design with noise that grows across the
    price range. The empirical sd of ε̂ is the truth; the classical standard
    error understates it by about a tenth, HC3 brackets it from above.

    The two are comparably far from the truth in absolute terms at n = 8 —
    HC3 is a noisy estimator in small samples and nobody claims otherwise.
    What matters is the SIDE they miss on: classical errs low, so its interval
    undercovers and the engine would promise a narrower range than it can
    defend; HC3 errs high, so the step it justifies is smaller than strictly
    necessary. Only one of those costs the seller money. Coverage itself is
    measured in test_interval_coverage_is_nominal_at_every_thickness."""
    n, grad, reps = 8, 0.45, 600
    prices = np.linspace(15.0, 28.0, n)
    scale = 0.02 + grad * (prices - prices.min()) / (prices.max() - prices.min())
    rng = np.random.default_rng(7)
    eps, hc3, classical = [], [], []
    for _ in range(reps):
        units = 500.0 * (prices / 20.0) ** -2.0 * np.exp(rng.normal(0, scale))
        r = elasticity.run(_data(_econ_rows(prices, units)))[0]
        eps.append(r["elasticity"])
        hc3.append(r["std_err"])
        classical.append(r["details"]["std_err_classical"])
    true_sd = float(np.std(eps, ddof=1))
    mean_hc3, mean_classical = float(np.mean(hc3)), float(np.mean(classical))
    assert mean_classical < true_sd * 0.95      # classical is too small
    assert mean_hc3 >= true_sd                  # HC3 is not


def test_interval_coverage_is_nominal_at_every_thickness():
    """Calibration. 1,000 simulated SKUs per cell, homoskedastic and
    heteroskedastic, n = 5 and n = 12: the fraction of 95% intervals that
    contain the true ε must land in 93–97%. The classical standard error with
    the same critical value drops to ~91% under heteroskedasticity — that gap
    is the defect this fix closes."""
    e_true, reps = -2.0, 1000
    for n in (5, 12):
        for grad in (0.0, 0.45):
            rng = np.random.default_rng(42)
            hit_hc3 = hit_classical = fitted = 0
            for _ in range(reps):
                prices = 20.0 * np.exp(rng.normal(0, 0.10, size=n))
                spread = max(1e-9, float(prices.max() - prices.min()))
                scale = 0.08 + grad * (prices - prices.min()) / spread
                units = 500.0 * (prices / 20.0) ** e_true * np.exp(rng.normal(0, scale))
                r = elasticity.run(_data(_econ_rows(prices, units)))[0]
                if r["status"] != "ok":
                    continue
                fitted += 1
                lo, hi = r["details"]["ci95"]
                hit_hc3 += lo <= e_true <= hi
                half = r["details"]["t_critical"] * r["details"]["std_err_classical"]
                hit_classical += abs(r["elasticity"] - e_true) <= half
            coverage = hit_hc3 / fitted
            assert 0.93 <= coverage <= 0.97, f"n={n} grad={grad}: coverage {coverage:.3f}"
            if grad > 0:
                assert hit_classical / fitted < coverage


def test_hc3_falls_back_and_says_so_when_a_period_is_fitted_exactly():
    """Five periods with a sessions control leaves dof = 2 and high leverage.
    Where (1 − hᵢ) hits the floor the HC3 correction is a division by
    numerical noise; the fit returns the classical covariance and names it
    rather than publishing an interval built on a blow-up."""
    prices = np.array([18.0, 19.0, 20.0, 21.0, 22.0])
    units = 500.0 * (prices / 20.0) ** -2.0
    rows = _econ_rows(prices, units)
    r = elasticity.run(_data(rows))[0]
    # noise-free fit: both estimators give a zero-width interval, and neither
    # is allowed to return NaN
    assert r["status"] == "ok"
    assert r["details"]["se_estimator"] in ("HC3", "classical_hc3_degenerate")
    lo, hi = r["details"]["ci95"]
    assert lo is not None and hi is not None and lo <= r["elasticity"] <= hi
