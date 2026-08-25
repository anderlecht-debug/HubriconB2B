from pathlib import Path

import pytest

from hubricon_engine.ingest import PARSERS
from hubricon_engine.ingest.headers import IngestError
from hubricon_engine.ingest.readers import read_table

FIXTURES = Path(__file__).parent / "fixtures"
UPLOAD = {
    "id": "00000000-0000-0000-0000-00000000aaaa",
    "client_id": "00000000-0000-0000-0000-00000000cccc",
    "period_start": "2026-07-01",
    "period_end": "2026-07-31",
}


def _parse(report_type: str, fixture: str):
    df = read_table((FIXTURES / fixture).read_bytes())
    return PARSERS[report_type].parse(df, UPLOAD)


def test_business_report():
    table, rows, key = _parse("business_report", "business_report_clean.csv")
    assert table == "asin_traffic"
    assert key == "client_id,child_asin,period_start,period_end"
    assert len(rows) == 3
    blue = next(r for r in rows if r["child_asin"] == "B0CHILD001")
    assert blue["units_ordered"] == 310
    assert blue["ordered_product_sales"] == 6193.90
    assert blue["sessions"] == 1204
    assert blue["buy_box_pct"] == 92.5
    assert blue["period_start"] == "2026-07-01"
    assert blue["raw"]["Ordered Product Sales"] == "US$6,193.90"


def test_sku_economics_bridges_sku_to_asin():
    table, rows, _ = _parse("sku_economics", "sku_economics_clean.csv")
    assert table == "sku_economics"
    blue = next(r for r in rows if r["sku"] == "WIDGET-BLUE")
    assert blue["asin"] == "B0CHILD001"
    assert blue["units_sold"] == 310
    assert blue["referral_fees"] == -929.09  # signs preserved; models use magnitudes
    assert blue["net_proceeds"] == 4200.61


def test_ppc_search_terms():
    table, rows, _ = _parse("ppc_search_terms", "ppc_search_terms_clean.csv")
    assert table == "ppc_search_terms"
    assert len(rows) == 4
    bleed = next(r for r in rows if r["search_term"] == "free widget sample")
    assert bleed["spend"] == 118.32
    assert bleed["sales_7d"] == 0.0


def test_ppc_campaign_parses_amazon_dates():
    table, rows, _ = _parse("ppc_campaign", "ppc_campaign_clean.csv")
    assert table == "ppc_spend"
    assert len(rows) == 4
    first = next(r for r in rows if r["campaign_name"] == "Widget - Exact" and r["report_date"] == "2026-08-01")
    assert first["spend"] == 41.20
    assert first["campaign_id"] == "Widget - Exact"  # falls back to name


def test_fba_inventory_sums_inbound():
    table, rows, _ = _parse("fba_inventory", "fba_inventory_clean.csv")
    assert table == "inventory_levels"
    blue = next(r for r in rows if r["sku"] == "WIDGET-BLUE")
    assert blue["fulfillable_quantity"] == 412
    assert blue["inbound_quantity"] == 200  # 0 working + 200 shipped + 0 receiving
    assert blue["snapshot_date"] == "2026-07-01"


def test_cogs_drops_example_row():
    table, rows, _ = _parse("cogs", "cogs_clean.csv")
    assert table == "cogs_inputs"
    assert {r["sku"] for r in rows} == {"WIDGET-BLUE", "WIDGET-RED", "GADGET-PRO"}
    blue = next(r for r in rows if r["sku"] == "WIDGET-BLUE")
    assert blue["unit_cost_usd"] == 4.10
    assert blue["supplier_lead_time_days"] == 38


def test_all_parsed_rows_are_json_serializable():
    """NaN from pandas must never reach the PostgREST payload."""
    import json

    cases = [
        ("business_report", "business_report_clean.csv"),
        ("sku_economics", "sku_economics_clean.csv"),
        ("ppc_search_terms", "ppc_search_terms_clean.csv"),
        ("ppc_campaign", "ppc_campaign_clean.csv"),
        ("fba_inventory", "fba_inventory_clean.csv"),
        ("cogs", "cogs_clean.csv"),
    ]
    for report_type, fixture in cases:
        _, rows, _ = _parse(report_type, fixture)
        json.dumps(rows, allow_nan=False)  # raises on NaN/inf


def test_missing_required_column_reports_found_headers():
    with pytest.raises(IngestError) as err:
        _parse("business_report", "business_report_missing_units.csv")
    assert "units_ordered" in str(err.value)
    assert "(Child) ASIN" in str(err.value)  # tells the operator what WAS there
