import pytest

from hubricon_engine.models import health_score as hs


def _margin_rows(n=8, margin_pct=0.20, losers=0):
    rows = []
    for i in range(n):
        rev = 1000.0
        net = rev * margin_pct if i >= losers else -150.0
        rows.append({"sku": f"S{i}", "period_start": "2026-08-01", "period_end": "2026-08-31", "units": 50,
                     "revenue": rev, "amazon_fees": 300.0, "cogs": 250.0, "ad_spend_allocated": 80.0, "net_margin": net})
    return rows


def test_healthy_catalog_scores_high_and_weights_renormalise():
    out = hs.compute(_margin_rows(), cash={"p_ruin": 0.0, "min_p5": 25000},
                     risk={"concentration": {"sku_revenue": {"hhi": 1250, "effective_n": 8, "top_item": "S0",
                                                               "top_share": 0.125, "dollar_at_risk_top_item": 200}}},
                     inventory_rows=[{"sku": f"S{i}", "stockout_probability": 0.02} for i in range(8)],
                     inv_econ={"summary": {"bleed": {"total_month": 40}}},
                     ads_rows=[], forecast_rows=[{"status": "ok", "mase": 0.7}],
                     data_present={k: True for k in hs.CORE_REPORTS + hs.BLEED_REPORTS})
    assert out["status"] == "ok" and out["score"] >= 85 and out["grade"] == "A"
    assert out["excluded"] == []
    assert sum(s["weight"] for s in out["sub_scores"]) == pytest.approx(1.0, abs=1e-3)
    assert {s["key"] for s in out["sub_scores"]} == set(hs.WEIGHTS)


def test_losses_and_missing_cash_lower_the_score_and_exclude_cash():
    out = hs.compute(_margin_rows(margin_pct=0.06, losers=3), data_present={"sku_economics": True})
    assert "cash" in out["excluded"] and "concentration" in out["excluded"]
    assert out["score"] < 60
    margin = next(s for s in out["sub_scores"] if s["key"] == "margin")
    assert margin["dollars_at_stake"] == 450.0          # three SKUs at −150
    assert out["top_drivers"][0]["key"] == "margin"


def test_grade_boundaries():
    assert hs.grade(85) == "A" and hs.grade(84.9) == "B" and hs.grade(55) == "C"
    assert hs.grade(40) == "D" and hs.grade(39) == "E"


def test_no_data_is_insufficient():
    assert hs.compute([])["status"] == "insufficient_data"


def test_interp_is_piecewise_linear():
    pts = [(0.0, 0), (0.10, 50), (0.20, 100)]
    assert hs._interp(0.05, pts) == 25 and hs._interp(0.3, pts) == 100 and hs._interp(-1, pts) == 0
