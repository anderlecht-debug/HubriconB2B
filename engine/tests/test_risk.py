"""Actuarial layer: planted-truth recoveries, textbook checks, honesty guards."""

import json

import numpy as np
import pytest

from hubricon_engine.models import risk


def _month(i: int) -> tuple[str, str]:
    return f"2026-{i:02d}-01", f"2026-{i:02d}-28"


def _margin_row(sku, i, units, price=25.0, fee_rate=0.30, unit_cost=8.0, ads=60.0):
    start, end = _month(i)
    revenue = units * price
    fees = revenue * fee_rate
    cogs = units * unit_cost
    net = revenue - fees - cogs - ads
    return {"sku": sku, "asin": f"B0{sku}", "period_start": start, "period_end": end,
            "units": units, "revenue": revenue, "amazon_fees": fees, "cogs": cogs,
            "ad_spend_allocated": ads, "net_margin": net,
            "net_margin_pct": net / revenue if revenue > 0 else None}


def _data(**overrides):
    base = {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [], "ppc_spend": [],
            "inventory_levels": [], "cogs_inputs": [], "fba_returns": []}
    base.update(overrides)
    return base


def _catalog(rng, n_skus=10, n_periods=8):
    """10 SKUs × 8 periods. S09 dies (absent in the last two periods); S08
    collapses to 20% of its earlier rate over the last three periods."""
    margins, econ = [], []
    for k in range(n_skus):
        sku = f"S{k:02d}"
        base = 100 + 40 * k
        unit_cost = 6.0 + 0.8 * k  # margins genuinely differ across SKUs
        for i in range(1, n_periods + 1):
            if sku == "S09" and i > n_periods - 2:
                continue
            level = base // 5 if (sku == "S08" and i > n_periods - 3) else base
            units = int(max(1, rng.normal(level, 0.08 * level)))
            fee_rate = float(np.clip(rng.normal(0.30, 0.05), 0.1, 0.5))  # within-SKU noise
            margins.append(_margin_row(sku, i, units, fee_rate=fee_rate, unit_cost=unit_cost))
            start, end = _month(i)
            econ.append({"sku": sku, "asin": f"B0{sku}", "period_start": start, "period_end": end,
                         "units_sold": units, "avg_sales_price": 25.0, "sales": units * 25.0,
                         "referral_fees": 0, "fba_fulfillment_fees": 0, "storage_fees": 0,
                         "other_fees": 0, "net_proceeds": units * 25.0})
    return margins, econ


def _returns(rng, n=40):
    dispositions = ["SELLABLE", "SELLABLE", "CUSTOMER_DAMAGED", "DEFECTIVE", "WEIRD_CODE"]
    rows = []
    for j in range(n):
        rows.append({"return_date": f"2026-08-{1 + (j % 27):02d}", "order_id": f"O{j}",
                     "sku": f"S{int(rng.integers(0, 9)):02d}", "asin": None, "fnsku": None,
                     "product_name": None, "quantity": 1, "fulfillment_center_id": "X",
                     "detailed_disposition": dispositions[j % len(dispositions)],
                     "reason": None, "status": None, "license_plate_number": None,
                     "customer_comments": None})
    rows.append({"return_date": "2026-08-10", "sku": "NOT-IN-CATALOG", "quantity": 2,
                 "detailed_disposition": "DAMAGED"})  # priced at the catalog average
    return rows


# ── var / cvar ────────────────────────────────────────────────────────────

def test_var_cvar_matches_normal_tail():
    sigma = 10.0
    losses = np.random.default_rng(1).normal(0.0, sigma, size=200_000)
    r = risk.var_cvar(losses, alpha=0.95)
    assert r["n"] == 200_000 and r["alpha"] == 0.95
    assert r["var"] == pytest.approx(1.645 * sigma, rel=0.10)
    assert r["cvar"] == pytest.approx(2.063 * sigma, rel=0.10)  # phi(1.645)/0.05
    assert r["cvar"] >= r["var"]


def test_var_cvar_empty_is_none_not_zero():
    r = risk.var_cvar(np.array([]))
    assert r["var"] is None and r["cvar"] is None and r["n"] == 0


# ── hhi ───────────────────────────────────────────────────────────────────

def test_hhi_levels():
    single = risk.hhi({"only": 500.0})
    assert single["hhi"] == 10000.0 and single["effective_n"] == 1.0
    assert single["level"] == "highly_concentrated" and single["top_share"] == 1.0

    ten = risk.hhi({f"i{k}": 10.0 for k in range(10)})
    assert ten["hhi"] == 1000.0 and ten["effective_n"] == 10.0 and ten["level"] == "moderate"

    twenty = risk.hhi({f"i{k}": 3.0 for k in range(20)})
    assert twenty["hhi"] == 500.0 and twenty["level"] == "diversified" and twenty["n"] == 20


def test_hhi_empty_or_zero_is_a_status():
    assert risk.hhi({})["status"] == "insufficient_data"
    zero = risk.hhi({"a": 0.0, "b": None})
    assert zero["status"] == "insufficient_data" and zero["hhi"] is None


# ── buhlmann ──────────────────────────────────────────────────────────────

def test_buhlmann_planted_shrinkage():
    rng = np.random.default_rng(11)
    mu, tau, sigma = 0.30, 0.03, 0.10  # true k = sigma^2 / tau^2 = 11.1
    groups = {}
    for g in range(40):
        n = [2, 3, 4, 6, 8, 12][g % 6]
        groups[f"g{g}"] = list(rng.normal(rng.normal(mu, tau), sigma, size=n))
    groups["thin"] = [mu + 0.25]  # one observation, 2.5 sigma above the catalog
    groups["mid"] = list(rng.normal(mu, sigma, size=4))
    groups["thick"] = list(rng.normal(mu, sigma, size=12))

    r = risk.buhlmann(groups)
    assert r["status"] == "ok" and not r["k_infinite"]
    assert r["within_var"] == pytest.approx(sigma**2, rel=0.25)
    assert r["k"] > 3.0
    by = r["by_group"]
    assert by["thin"]["z"] < by["mid"]["z"] < by["thick"]["z"]  # credibility grows with n
    thin = by["thin"]
    assert abs(thin["blended"] - r["mu"]) < 0.3 * abs(thin["raw_mean"] - r["mu"])  # shrunk ~to mu
    for vals in by.values():
        assert 0.0 < vals["z"] < 1.0


def test_buhlmann_no_between_variance_reports_catalog_mean():
    r = risk.buhlmann({"a": [1.0, 3.0], "b": [2.0, 2.0], "c": [3.0, 1.0]})
    assert r["status"] == "ok"
    assert r["between_var"] == 0.0 and r["k"] is None and r["k_infinite"] is True
    for vals in r["by_group"].values():
        assert vals["z"] == 0.0 and vals["blended"] == 2.0 == r["mu"]


def test_buhlmann_needs_a_within_variance():
    assert risk.buhlmann({"a": [1.0], "b": [2.0]})["status"] == "insufficient_data"
    assert risk.buhlmann({"a": [1.0, 2.0]})["status"] == "insufficient_data"


# ── compound poisson ──────────────────────────────────────────────────────

def test_compound_poisson_reserve_expectation():
    rng = np.random.default_rng(5)
    sev = rng.gamma(2.0, 5.0, size=50)
    lam, exposure = 0.05, 2000.0
    r = risk.compound_poisson_reserve(lam, exposure, sev, rng, n_paths=4000)
    assert r["status"] == "ok" and r["method"] == "bootstrap"
    assert r["expected"] == pytest.approx(lam * exposure * sev.mean(), rel=0.15)
    assert r["p99"] >= r["p95"] >= r["p50"] >= 0.0
    assert r["expected_claims"] == 100.0


def test_compound_poisson_thin_severities_fit_gamma():
    rng = np.random.default_rng(5)
    r = risk.compound_poisson_reserve(0.05, 2000.0, [4.0, 6.0, 8.0], rng, n_paths=4000)
    assert r["method"] == "gamma_mom"
    assert r["expected"] == pytest.approx(100 * 6.0, rel=0.15)
    single = risk.compound_poisson_reserve(0.05, 2000.0, [5.0], rng, n_paths=4000)
    assert single["method"] == "constant"
    assert single["expected"] == pytest.approx(500.0, rel=0.15)
    assert risk.compound_poisson_reserve(0.0, 2000.0, [5.0], rng)["status"] == "insufficient_data"


# ── kaplan-meier ──────────────────────────────────────────────────────────

def test_kaplan_meier_textbook():
    # t=1: 4 at risk, 1 event -> 0.75; t=2 censored; t=3: 2 at risk, 1 event -> 0.375; t=4 -> 0
    r = risk.kaplan_meier([1, 2, 3, 4], [True, False, True, True])
    assert r["status"] == "ok" and r["n"] == 4 and r["events"] == 3
    assert r["t"] == [0.0, 1.0, 3.0, 4.0]
    assert r["s"] == [1.0, 0.75, 0.375, 0.0]
    assert r["median"] == 3.0


def test_kaplan_meier_all_censored_has_no_median():
    r = risk.kaplan_meier([5, 5, 5], [False, False, False])
    assert r["s"] == [1.0] and r["median"] is None and r["events"] == 0


# ── run() ─────────────────────────────────────────────────────────────────

def test_run_on_synthetic_catalog():
    margins, econ = _catalog(np.random.default_rng(3))
    out = risk.run(_data(sku_economics=econ), margins, rng=np.random.default_rng(7), simulations=3000)
    assert out["status"] == "ok"

    var = out["var"]
    assert var["status"] == "ok" and var["skus_modeled"] == 9  # S09 is gone from the latest period
    assert var["cvar_95"] >= var["var_95"] >= 0.0
    assert var["cvar_99"] >= var["cvar_95"]
    assert var["worst_5pct_net"] == pytest.approx(var["expected_net"] - var["cvar_95"], abs=0.02)
    assert var["p5_net"] <= var["p50_net"] and var["revenue_p5"] <= var["revenue_p50"]
    assert var["rate_source"] == {"forecast": 0, "observed": 9}

    conc = out["concentration"]
    assert conc["status"] == "ok"
    rev = conc["sku_revenue"]
    assert rev["status"] == "ok" and rev["dimension"] == "sku_revenue"
    assert rev["top_item"] == "S08" or rev["top_item"] == "S07"  # biggest live seller
    assert rev["dollar_at_risk_top_item"] is not None and 0 < rev["top_share"] < 1
    assert conc["campaign_spend"]["status"] == "insufficient_data"  # no ppc data supplied

    cred = out["credibility"]
    assert cred["status"] == "ok" and cred["k"] > 0 and len(cred["by_sku"]) == 10
    for vals in cred["by_sku"].values():
        assert 0.0 < vals["z"] < 1.0
    assert len(cred["largest_adjustments"]) == 5

    surv = out["survival"]
    assert surv["status"] == "ok" and surv["n"] == 10 and surv["events"] == 1
    assert [d["sku"] for d in surv["dead"]] == ["S09"]
    assert surv["s"] == [1.0, 0.9] and surv["median"] is None
    assert [d["sku"] for d in surv["declining"]] == ["S08"]
    assert surv["declining"][0]["drop_pct"] > 50.0

    assert out["returns_reserve"]["status"] == "insufficient_data"
    json.dumps(out)  # numpy types or NaN would raise


def test_run_returns_reserve_with_returns():
    rng = np.random.default_rng(3)
    margins, econ = _catalog(rng)
    data = _data(sku_economics=econ, fba_returns=_returns(rng))
    out = risk.run(data, margins, rng=np.random.default_rng(7), simulations=3000)
    rr = out["returns_reserve"]
    assert rr["status"] == "ok" and rr["method"] == "bootstrap"
    assert rr["expected"] > 0 and rr["p99"] >= rr["p95"] >= rr["p50"] >= 0
    assert rr["returned_units"] == 42 and rr["return_rate_pct"] > 0
    assert rr["returns_window"]["overlap_with_economics"] is True
    assert rr["by_disposition"]["SELLABLE"]["loss_fraction"] == 0.20
    assert rr["by_disposition"]["WEIRD_CODE"]["loss_fraction"] == 0.60
    assert 1 <= len(rr["by_sku"]) <= 5 and rr["by_sku"][0]["units_returned"] >= rr["by_sku"][-1]["units_returned"]
    assert any("catalog average price" in a for a in rr["assumptions"])
    json.dumps(out)


def test_run_concentration_dimensions_and_windows():
    margins, econ = _catalog(np.random.default_rng(3))
    ppc_spend = [  # 2026-06-01 is outside the 30-day window ending 2026-08-28
        {"report_date": "2026-06-01", "campaign_id": "old", "campaign_name": "Old", "spend": 9999.0},
        {"report_date": "2026-08-27", "campaign_id": "a", "campaign_name": "Brand", "spend": 300.0},
        {"report_date": "2026-08-28", "campaign_id": "a", "campaign_name": "Brand", "spend": 300.0},
        {"report_date": "2026-08-28", "campaign_id": "b", "campaign_name": "Generic", "spend": 400.0},
    ]
    terms = [
        {"campaign_name": "Brand", "search_term": "t1", "spend": 50.0,
         "period_start": "2026-08-01", "period_end": "2026-08-28"},
        {"campaign_name": "Brand", "search_term": "t2", "spend": 50.0,
         "period_start": "2026-08-01", "period_end": "2026-08-28"},
        {"campaign_name": "Brand", "search_term": "stale", "spend": 5000.0,
         "period_start": "2026-07-01", "period_end": "2026-07-28"},
    ]
    traffic = [
        {"child_asin": "B0S07", "sessions": 900, "period_start": "2026-08-01", "period_end": "2026-08-28"},
        {"child_asin": "B0S01", "sessions": 100, "period_start": "2026-08-01", "period_end": "2026-08-28"},
    ]
    data = _data(sku_economics=econ, ppc_spend=ppc_spend, ppc_search_terms=terms, asin_traffic=traffic)
    conc = risk.run(data, margins, rng=np.random.default_rng(7), simulations=500)["concentration"]
    camp = conc["campaign_spend"]
    assert camp["status"] == "ok" and camp["n"] == 2  # "Old" excluded by the 30-day window
    assert camp["hhi"] == 5200.0 and camp["top_item"] == "Brand" and camp["top_share"] == 0.6
    term = conc["search_term_spend"]
    assert term["n"] == 2 and term["hhi"] == 5000.0 and term["top_share"] == 0.5  # stale window ignored
    sess = conc["asin_sessions"]
    assert sess["top_item"] == "B0S07" and sess["top_share"] == 0.9 and sess["level"] == "highly_concentrated"
    for d in (camp, term, sess):
        assert d["basis"]


def test_run_prefers_forecast_rates():
    margins, econ = _catalog(np.random.default_rng(3))
    latest = {m["sku"] for m in margins if m["period_start"] == "2026-08-01"}
    forecasts = [{"item_id": sku, "daily_rate_point": 5.0, "details": {"error_sd": 0.5}} for sku in latest]
    out = risk.run(_data(sku_economics=econ), margins, forecast_rows=forecasts,
                   rng=np.random.default_rng(7), simulations=2000)
    assert out["var"]["rate_source"] == {"forecast": 9, "observed": 0}


def test_run_empty_inputs_are_statuses_not_numbers():
    out = risk.run(_data(), [], rng=np.random.default_rng(7), simulations=500)
    assert out["status"] == "insufficient_data"
    for key in ("var", "concentration", "credibility", "returns_reserve", "survival"):
        assert out[key]["status"] == "insufficient_data"
    assert "expected_net" not in out["var"]
    json.dumps(out)


def test_run_is_reproducible():
    margins, econ = _catalog(np.random.default_rng(3))
    a = risk.run(_data(sku_economics=econ), margins, rng=np.random.default_rng(7), simulations=1000)
    b = risk.run(_data(sku_economics=econ), margins, rng=np.random.default_rng(7), simulations=1000)
    assert a == b
