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
