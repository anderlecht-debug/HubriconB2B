"""Chart pack: deliverable-shaped, JSON-safe, honest about what's missing."""

import json

from hubricon_engine import chart_pack


def _margins():
    mk = lambda sku, rev, fees, cogs, ads: {
        "sku": sku, "period_start": "2026-07-01", "period_end": "2026-07-30",
        "units": 300, "revenue": rev, "amazon_fees": fees, "cogs": cogs,
        "ad_spend_allocated": ads, "net_margin": rev - fees - cogs - ads,
    }
    old = {**mk("SKU-A", 8000.0, 2400.0, 1600.0, 400.0), "period_start": "2026-06-01"}
    return [old, mk("SKU-A", 9000.0, 2700.0, 1800.0, 450.0), mk("SKU-B", 4000.0, 1300.0, 900.0, 200.0)]


def _fits():
    pts = [{"price": 27.0, "units": 380}, {"price": 29.0, "units": 330},
           {"price": 30.0, "units": 300}, {"price": 32.0, "units": 255}]
    return [{"status": "ok", "level": "sku", "item_id": "SKU-A", "elasticity": -1.8,
             "r_squared": 0.94, "details": {"points": pts, "ci95": [-2.2, -1.4]}}]


def _inventory():
    return [{"sku": "SKU-A", "stockout_probability": 0.62, "days_of_cover": 8.0},
            {"sku": "SKU-B", "stockout_probability": 0.05, "days_of_cover": 140.0}]


def _ads():
    return [{"status": "ok", "campaign_name": "Auto", "curve_model": "hill",
             "curve_params": {"a": 9000.0, "h": 1.2, "k": 900.0},
             "current_spend": 1400.0, "breakeven_spend": 900.0, "marginal_roas": 0.7,
             "bleed_terms": [{"search_term": "waste one", "spend": 210.0},
                             {"search_term": "waste two", "spend": 90.0}]}]


def _pack():
    return chart_pack.build_pack(_margins(), _fits(), _inventory(), _ads(),
                                 search_terms=[], brand_terms=["acme"])


def test_waterfall_reconciles():
    w = chart_pack.waterfall(_margins())
    assert w["period"] == "2026-07-01"
    assert w["revenue"] == 13000.0
    assert abs(w["revenue"] - w["fees"] - w["cogs"] - w["ads"] - w["net"]) < 0.01


def test_stacks_sorted_by_revenue():
    rows = chart_pack.sku_stacks(_margins())
    assert [r["sku"] for r in rows] == ["SKU-A", "SKU-B"]


def test_elasticity_band_brackets_the_curve():
    fits = chart_pack.elasticity_curves(_fits())
    assert len(fits) == 1 and len(fits[0]["curve"]) == chart_pack.CURVE_POINTS
    for c, b in zip(fits[0]["curve"], fits[0]["band"]):
        assert b["lo"] <= c["u"] * 1.001 and b["hi"] >= c["u"] * 0.999


def test_profit_curve_carries_the_move():
    curves = chart_pack.profit_curves(_margins(), _fits())
    assert len(curves) == 1
    c = curves[0]
    assert c["sku"] == "SKU-A" and c["p_star"] is not None
    assert len(c["curve"]) == chart_pack.CURVE_POINTS


def test_bleed_totals_and_fold():
    b = chart_pack.bleed(_ads())
    assert b["total"] == 300.0 and b["terms"][0]["term"] == "waste one"
    assert b["other"] == 0.0 and b["n_terms"] == 2


def test_brand_absent_below_minimum():
    assert chart_pack.brand_range([], ["acme"]) is None


def test_pack_is_json_safe_and_sparse():
    pack = _pack()
    json.dumps(pack)
    assert "brand" not in pack          # no branded spend in fixture
    assert set(pack) >= {"waterfall", "sku_stacks", "elasticity", "profit_curves",
                         "ad_curves", "bleed", "risk_map"}
    assert pack["risk_map"][1]["cover"] == 90.0   # capped
