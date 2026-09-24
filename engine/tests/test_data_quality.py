"""Garbage in: do the exports agree with each other, and are they all there?"""

from datetime import date

from hubricon_engine.models import data_quality as dq, health_score

TODAY = date(2026, 9, 10)


def _econ(month, sales, units=100, sku="A"):
    return {"sku": sku, "period_start": f"2026-{month:02d}-01", "period_end": f"2026-{month:02d}-28",
            "sales": sales, "units_sold": units}


def _orders(month, total, days=20):
    return [{"txn_date": f"2026-{month:02d}-{d + 1:02d}", "txn_type": "Order", "sku": "A", "quantity": 5,
             "product_sales": total / days} for d in range(days)]


def test_a_gap_between_two_sources_is_flagged_and_named_and_a_clean_pair_passes():
    data = {"sku_economics": [_econ(6, 2000.0), _econ(7, 2000.0)],
            "settlement_transactions": _orders(6, 2000.0) + _orders(7, 1600.0),     # July disagrees by 20%
            "asin_traffic": [{"child_asin": "B0A", "period_start": "2026-06-01", "period_end": "2026-06-28",
                              "ordered_product_sales": 2050.0}]}
    out = dq.run(data, TODAY)
    rec = {(r["period_start"], r["b"]): r for r in out["reconciliation"]}
    june = rec[("2026-06-01", "settlement_transactions")]
    july = rec[("2026-07-01", "settlement_transactions")]
    assert not june["flagged"] and july["flagged"] and july["relative_gap"] == 0.2
    assert rec[("2026-06-01", "asin_traffic")]["relative_gap"] < dq.RECONCILE_TOLERANCE
    assert out["status"] == "flags" and out["n_failed"] == 1
    assert out["worst_gap"]["period"] == "2026-07-01" and out["worst_gap"]["a"] == "sku_economics"
    assert "sku_economics" in out["flags"] and "settlement_transactions" in out["flags"]
    clean = dq.run({"sku_economics": [_econ(8, 2000.0)], "settlement_transactions": _orders(8, 2000.0)}, TODAY)
    assert clean["status"] == "ok" and clean["n_failed"] == 0 and clean["flags"] == {}


def test_missing_months_and_stale_reports_are_listed_never_zeroed():
    data = {"sku_economics": [_econ(3, 1000.0), _econ(4, 1000.0), _econ(6, 1000.0)],
            "ppc_spend": [{"report_date": "2026-05-03", "spend": 10.0, "campaign_name": "C"}]}
    out = dq.run(data, TODAY)
    assert out["coverage"]["sku_economics"]["missing_months"] == ["2026-05"]
    assert out["gaps"] == {"sku_economics": ["2026-05"]}
    assert out["coverage"]["ppc_spend"]["stale"] and "ppc_spend" in out["stale"]
    assert any(f.startswith("missing_months") for f in out["flags"]["sku_economics"])
    assert any(f.startswith("stale") for f in out["flags"]["ppc_spend"])
    assert out["coverage"]["asin_traffic"] == {"present": False}
    assert dq.run({}, TODAY)["status"] == "insufficient_data"


def test_ad_spend_reconciles_across_the_search_term_window_and_shopify_skips_amazon_pairs():
    data = {"ppc_spend": [{"report_date": f"2026-07-{d:02d}", "spend": 50.0, "campaign_name": "C"} for d in range(1, 29)],
            "ppc_search_terms": [{"period_start": "2026-07-01", "period_end": "2026-07-28", "spend": 1000.0},
                                 {"period_start": "2026-07-01", "period_end": "2026-07-28", "spend": 350.0}]}
    out = dq.run(data, TODAY)
    ad = [r for r in out["reconciliation"] if r["quantity"] == "ad_spend"][0]
    assert ad["a_value"] == 1400.0 and ad["b_value"] == 1350.0 and not ad["flagged"]   # a 3.6% gap: inside tolerance
    shop = dq.run({"sku_economics": [_econ(7, 2000.0)], "settlement_transactions": [], "asin_traffic": [],
                   "inventory_ledger": []}, TODAY)
    assert shop["reconciliation"] == [] and shop["status"] == "ok"


def test_the_health_signal_subtracts_for_disagreement_and_the_flags_reach_a_payload():
    margins = [{"sku": "A", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 100, "revenue": 2000.0,
                "amazon_fees": 300.0, "cogs": 500.0, "ad_spend_allocated": 100.0, "net_margin": 1100.0}]
    present = {"sku_economics": True, "asin_traffic": True, "ppc_search_terms": True, "inventory_levels": True}
    clean = health_score.compute(margins, None, None, [], None, [], [], None, present)
    bad = health_score.compute(margins, None, None, [], None, [], [], None, present,
                               data_quality={"status": "flags", "n_failed": 2, "gaps": {"sku_economics": ["2026-05"]}})
    sig_clean = next(s for s in clean["sub_scores"] if s["key"] == "signal")
    sig_bad = next(s for s in bad["sub_scores"] if s["key"] == "signal")
    assert sig_bad["score"] == max(0.0, sig_clean["score"] - 25.0) and "disagree" in sig_bad["note"]
    flagged = {"status": "flags", "flags": {"sku_economics": ["reconciliation:sales:2026-07-01"]}}
    assert dq.flags_for(flagged, "sku_economics", "ppc_spend") == ["sku_economics: reconciliation:sales:2026-07-01"]
    assert dq.flags_for({"status": "ok"}, "sku_economics") == []
