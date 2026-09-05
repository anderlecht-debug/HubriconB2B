"""Bleed reports: reimbursements, customer returns, inventory ledger,
inventory health and settlement transactions. Fixtures are small hand-built
exports carrying Amazon's real header names; every assertion is against a
planted value, and a duplicated source line in each fixture must collapse."""

import json
from pathlib import Path

import pytest

from hubricon_engine.ingest import PARSERS
from hubricon_engine.ingest.headers import IngestError, row_key, to_iso_date, to_iso_datetime
from hubricon_engine.ingest.readers import read_table

FIXTURES = Path(__file__).parent / "fixtures"
UPLOAD = {
    "id": "00000000-0000-0000-0000-00000000aaaa",
    "client_id": "00000000-0000-0000-0000-00000000cccc",
    "period_start": "2026-07-01",
    "period_end": "2026-07-31",
}
# The intake's whole vocabulary. It must match the report_type check on
# public.uploads (supabase/migrations/20260904000001_shopify_channel.sql):
# a type the constraint admits but no parser handles is an upload that can
# never be processed. "cogs" is the one template both platforms share.
AMAZON_REPORT_TYPES = {
    "business_report", "sku_economics", "ppc_search_terms", "ppc_campaign", "fba_inventory",
    "fba_reimbursements", "fba_returns", "inventory_ledger", "inventory_health", "transactions",
}
SHOPIFY_REPORT_TYPES = {
    "shopify_orders", "shopify_products", "shopify_inventory", "shopify_payouts",
    "meta_ads", "google_ads_campaign", "google_ads_search_terms",
}
ALL_REPORT_TYPES = AMAZON_REPORT_TYPES | SHOPIFY_REPORT_TYPES | {"cogs"}
BLEED_CASES = [
    ("fba_reimbursements", "fba_reimbursements_clean.csv"),
    ("fba_returns", "fba_returns_clean.csv"),
    ("inventory_ledger", "inventory_ledger_clean.csv"),
    ("inventory_health", "inventory_health_clean.csv"),
    ("transactions", "transactions_clean.csv"),
]


def _parse(report_type: str, fixture: str | None = None, data: bytes | None = None):
    raw = data if data is not None else (FIXTURES / fixture).read_bytes()
    return PARSERS[report_type].parse(read_table(raw), UPLOAD)


def test_parsers_registry_covers_every_report_type():
    assert set(PARSERS) == ALL_REPORT_TYPES
    assert len(PARSERS) == 18  # 10 Amazon + 7 Shopify-side + the shared COGS template


# --- shared date + key helpers ------------------------------------------------

def test_to_iso_date_accepts_amazon_variants():
    assert to_iso_date("2026-07-14") == "2026-07-14"
    assert to_iso_date("2026-07-14T10:21:00+00:00") == "2026-07-14"
    assert to_iso_date("14.07.2026") == "2026-07-14"
    assert to_iso_date("Jul 14, 2026") == "2026-07-14"
    assert to_iso_date("Aug 01, 2026") == "2026-08-01"
    assert to_iso_date("07/14/2026") == "2026-07-14"  # US order by default
    assert to_iso_date("14/07/2026") == "2026-07-14"  # day-first only when it must be
    assert to_iso_date("7/2/26") == "2026-07-02"
    assert to_iso_date("") is None
    assert to_iso_date("N/A") is None
    assert to_iso_date(None) is None


def test_to_iso_datetime_keeps_wall_clock_and_drops_zone_name():
    assert to_iso_datetime("Jul 1, 2026 3:12:44 AM PDT") == "2026-07-01T03:12:44"
    assert to_iso_datetime("Jul 3, 2026 11:48:02 PM PDT") == "2026-07-03T23:48:02"
    assert to_iso_datetime("Jul 5, 2026 12:00:00 AM PDT") == "2026-07-05T00:00:00"
    assert to_iso_datetime("7/6/2026 1:02:44 PM") == "2026-07-06T13:02:44"
    assert to_iso_datetime("2026-07-14 10:21:00 UTC") == "2026-07-14T10:21:00"
    assert to_iso_datetime("2026-07-14") == "2026-07-14T00:00:00"


def test_unrecognized_date_raises_instead_of_guessing():
    with pytest.raises(IngestError):
        to_iso_date("sometime in July")
    with pytest.raises(IngestError):
        to_iso_date("13/13/2026")


def test_row_key_is_stable_and_treats_none_as_blank():
    assert row_key("a", None, 3) == row_key("a", "", "3")
    assert len(row_key("x")) == 40
    assert row_key("a", "b") != row_key("b", "a")


# --- reimbursements ------------------------------------------------------------

def test_fba_reimbursements():
    table, rows, key = _parse("fba_reimbursements", "fba_reimbursements_clean.csv")
    assert table == "fba_reimbursements"
    assert key == "client_id,row_key"
    assert len(rows) == 4  # five source lines; the last repeats the first
    by_id = {r["reimbursement_id"]: r for r in rows}
    lost = by_id["RM-1001"]
    assert lost["approval_date"] == "2026-07-14"
    assert lost["sku"] == "WIDGET-BLUE" and lost["fnsku"] == "X001ABC1"
    assert lost["reason"] == "Lost_Warehouse"
    assert lost["amount_per_unit"] == 14.20
    assert lost["amount_total"] == 28.40
    assert lost["quantity_reimbursed_cash"] == 2 and isinstance(lost["quantity_reimbursed_cash"], int)
    assert lost["quantity_reimbursed_total"] == 2
    assert lost["currency"] == "USD"
    assert lost["raw"]["approval-date"] == "2026-07-14"
    assert by_id["RM-1002"]["approval_date"] == "2026-07-14"  # 14.07.2026
    assert by_id["RM-1002"]["case_id"] == "12345678901"
    assert by_id["RM-1003"]["approval_date"] == "2026-07-15"  # Jul 15, 2026
    assert by_id["RM-1003"]["amazon_order_id"] == "111-2233445-6677889"
    assert by_id["RM-1004"]["approval_date"] == "2026-07-16"  # ISO datetime
    assert by_id["RM-1004"]["sku"] == "X001ABC4"  # blank sku falls back to fnsku
    assert by_id["RM-1004"]["quantity_reimbursed_inventory"] == 3
    assert by_id["RM-1004"]["amount_total"] == 0.0


def test_fba_reimbursements_skips_rows_without_any_sku():
    data = (
        b"approval-date,reimbursement-id,reason,sku,fnsku,amount-total\n"
        b"2026-07-14,RM-1,Lost_Warehouse,,,10.00\n"
        b"2026-07-14,RM-2,Lost_Warehouse,A-1,,10.00\n"
    )
    _, rows, _ = _parse("fba_reimbursements", data=data)
    assert [r["reimbursement_id"] for r in rows] == ["RM-2"]


# --- customer returns ----------------------------------------------------------

def test_fba_returns():
    table, rows, key = _parse("fba_returns", "fba_returns_clean.csv")
    assert table == "fba_returns" and key == "client_id,row_key"
    assert len(rows) == 4  # duplicated LPN line collapses
    damaged = next(r for r in rows if r["license_plate_number"] == "LPNRR100000002")
    assert damaged["return_date"] == "2026-07-05"  # from 2026-07-05T09:10:00+00:00
    assert damaged["order_id"] == "111-2222222-2222222"
    assert damaged["quantity"] == 1 and isinstance(damaged["quantity"], int)
    assert damaged["fulfillment_center_id"] == "ONT8"
    assert damaged["detailed_disposition"] == "CUSTOMER_DAMAGED"
    assert damaged["reason"] == "DEFECTIVE"
    assert damaged["status"] == "Reimbursed"
    assert damaged["customer_comments"] == "Stopped working after a week"
    gizmo = next(r for r in rows if r["license_plate_number"] == "LPNRR100000004")
    assert gizmo["sku"] == "X001ABC4"  # fnsku fallback
    assert gizmo["customer_comments"] is None
    gadget = next(r for r in rows if r["sku"] == "GADGET-PRO")
    assert gadget["quantity"] == 2


def test_row_key_dedupe_keeps_last_occurrence():
    """Re-exports repeat lines; the last wins so a corrected line replaces its predecessor."""
    data = (
        b"return-date,order-id,sku,fnsku,quantity,fulfillment-center-id,detailed-disposition,license-plate-number\n"
        b"2026-07-03,111-1,A-1,X1,1,PHX7,SELLABLE,LPN1\n"
        b"2026-07-03,111-1,A-1,X1,1,PHX7,DAMAGED,LPN1\n"
    )
    _, rows, _ = _parse("fba_returns", data=data)
    assert len(rows) == 1
    assert rows[0]["detailed_disposition"] == "DAMAGED"


# --- inventory ledger ----------------------------------------------------------

def test_inventory_ledger_detail_report():
    table, rows, key = _parse("inventory_ledger", "inventory_ledger_clean.csv")
    assert table == "inventory_ledger" and key == "client_id,row_key"
    assert len(rows) == 4
    lost = next(r for r in rows if r["reference_id"] == "ADJ-77001")
    assert lost["event_date"] == "2026-07-06"  # 7/6/2026
    assert lost["event_type"] == "Adjustments"
    assert lost["quantity"] == -3 and isinstance(lost["quantity"], int)
    assert lost["reason"] == "M"
    assert lost["disposition"] == "SELLABLE"
    assert lost["unreconciled_qty"] == 3 and lost["reconciled_qty"] == 0
    assert lost["sku"] == "WIDGET-BLUE" and lost["fnsku"] == "X001ABC1" and lost["asin"] == "B0CHILD001"
    assert lost["title"] == "Widget, Blue 2-Pack"
    assert lost["fulfillment_center"] == "ONT8"
    assert lost["country"] == "US"
    receipt = next(r for r in rows if r["event_type"] == "Receipts")
    assert receipt["quantity"] == 200 and receipt["reason"] is None
    assert receipt["event_date"] == "2026-07-02"
    found = next(r for r in rows if r["reason"] == "F")
    assert found["quantity"] == 2 and found["event_date"] == "2026-07-15"


def test_inventory_adjustments_variant_maps_to_ledger():
    data = (
        b"adjusted-date,transaction-item-id,fnsku,sku,product-name,fulfillment-center-id,quantity,reason,disposition,unreconciled\n"
        b"2026-07-06T13:02:44+00:00,ADJ-77001,X001ABC1,WIDGET-BLUE,\"Widget, Blue 2-Pack\",ONT8,-3,M,SELLABLE,3\n"
        b"14.07.2026,ADJ-77009,X001ABC2,WIDGET-RED,\"Widget, Red 2-Pack\",PHX7,1,F,SELLABLE,0\n"
    )
    _, rows, _ = _parse("inventory_ledger", data=data)
    assert len(rows) == 2
    first, second = sorted(rows, key=lambda r: r["event_date"])
    assert first["event_date"] == "2026-07-06" and second["event_date"] == "2026-07-14"
    assert {r["event_type"] for r in rows} == {"Adjustments"}  # absent Event Type -> Adjustments
    assert first["reference_id"] == "ADJ-77001"  # from transaction-item-id
    assert first["unreconciled_qty"] == 3 and first["reconciled_qty"] is None
    assert first["title"] == "Widget, Blue 2-Pack"
    assert first["fulfillment_center"] == "ONT8"
    # the same event in both layouts hashes to the same row_key, so a client
    # who sends both exports does not double count
    _, detail, _ = _parse("inventory_ledger", "inventory_ledger_clean.csv")
    detail_lost = next(r for r in detail if r["reference_id"] == "ADJ-77001")
    assert first["row_key"] == detail_lost["row_key"]


# --- inventory health ----------------------------------------------------------

def test_inventory_health_snapshot():
    table, rows, key = _parse("inventory_health", "inventory_health_clean.csv")
    assert table == "inventory_health" and key == "client_id,sku,snapshot_date"
    assert len(rows) == 4
    gadget = next(r for r in rows if r["sku"] == "GADGET-PRO")
    assert gadget["snapshot_date"] == "2026-07-01"  # from the upload, like inventory_levels
    assert gadget["available"] == 240 and isinstance(gadget["available"], int)
    assert gadget["pending_removal"] == 10
    assert (
        gadget["inv_age_0_to_90"], gadget["inv_age_91_to_180"], gadget["inv_age_181_to_270"],
        gadget["inv_age_271_to_365"], gadget["inv_age_365_plus"],
    ) == (0, 60, 80, 60, 40)
    assert (gadget["units_shipped_t7"], gadget["units_shipped_t30"], gadget["units_shipped_t60"],
            gadget["units_shipped_t90"]) == (15, 72, 140, 210)
    assert gadget["sell_through"] == 0.30
    assert gadget["days_of_supply"] == 100
    assert gadget["estimated_excess_quantity"] == 95
    assert gadget["item_volume"] == 0.125 and gadget["storage_volume"] == 30.0
    assert gadget["estimated_storage_cost_next_month"] == 21.75
    assert gadget["estimated_aged_surcharge"] == 48.30  # seven estimated-ais-* buckets summed
    assert gadget["recommended_action"] == "Create removal order"
    assert gadget["low_inventory_level_fee_applied"] is False
    assert gadget["your_price"] == 30.99 and gadget["sales_price"] == 30.99
    assert gadget["currency"] == "USD"
    assert gadget["healthy_inventory_level"] == 90
    assert gadget["storage_type"] == "Standard-Size"
    assert gadget["weeks_of_cover_t30"] == 14.3
    assert "ais_181_210" not in gadget  # buckets are folded, not stored
    red = next(r for r in rows if r["sku"] == "WIDGET-RED")
    assert red["low_inventory_level_fee_applied"] is True
    assert red["estimated_aged_surcharge"] == 3.60
    blue = next(r for r in rows if r["sku"] == "WIDGET-BLUE")
    assert blue["estimated_aged_surcharge"] == 0.0
    gizmo = next(r for r in rows if r["sku"] == "X001ABC4")  # fnsku fallback
    assert gizmo["available"] == 8


def test_inventory_health_without_ais_columns_leaves_surcharge_none():
    data = b"sku,fnsku,asin,available,inv-age-0-to-90-days\nA-1,X1,B0X,5,5\n"
    _, rows, _ = _parse("inventory_health", data=data)
    assert rows[0]["estimated_aged_surcharge"] is None
    assert rows[0]["low_inventory_level_fee_applied"] is None
    assert rows[0]["available"] == 5
    assert rows[0]["inv_age_365_plus"] is None


# --- settlement transactions ---------------------------------------------------

def test_transactions_reader_skips_prose_preamble():
    df = read_table((FIXTURES / "transactions_clean.csv").read_bytes())
    assert list(df.columns)[:4] == ["date/time", "settlement id", "type", "order id"]
    assert list(df.columns)[-1] == "total"
    assert len(df) == 6


def test_reader_prefers_line_matching_modal_width_over_first_wide_line():
    """Unquoted prose with commas splits into 3+ fields; the modal-width rule
    still lands on the real header because the rows beneath are wider."""
    data = (
        b"Includes Amazon Marketplace, FBA, and Webstore transactions\n"
        b"Other: see the Type, Description, and Total columns for each order ID\n"
        b"date/time,type,sku,total\n"
        b"\"Jul 1, 2026 3:12:44 AM PDT\",Order,A-1,10.00\n"
        b"\"Jul 2, 2026 3:12:44 AM PDT\",Refund,A-1,-10.00\n"
    )
    df = read_table(data)
    assert list(df.columns) == ["date/time", "type", "sku", "total"]
    assert len(df) == 2


def test_settlement_transactions():
    table, rows, key = _parse("transactions", "transactions_clean.csv")
    assert table == "settlement_transactions" and key == "client_id,row_key"
    assert len(rows) == 5  # duplicated Order line collapses
    order = next(r for r in rows if r["txn_type"] == "Order")
    assert order["txn_datetime"] == "2026-07-01T03:12:44"
    assert order["txn_date"] == "2026-07-01"
    assert order["settlement_id"] is None
    assert order["order_id"] == "111-1234567-1234567"
    assert order["sku"] == "WIDGET-BLUE"
    assert order["description"] == "Widget, Blue 2-Pack"
    assert order["quantity"] == 2 and isinstance(order["quantity"], int)
    assert order["marketplace"] == "amazon.com"
    assert order["account_type"] == "Standard Orders"
    assert order["fulfillment"] == "Amazon"
    assert order["product_sales"] == 39.96 and order["product_sales_tax"] == 3.60
    assert order["shipping_credits"] == 0.0
    assert order["promotional_rebates"] == -2.00
    assert order["marketplace_withheld_tax"] == -3.60
    assert order["selling_fees"] == -5.69 and order["fba_fees"] == -6.60
    assert order["other_transaction_fees"] == 0.0 and order["other"] == 0.0
    assert order["total"] == 25.67
    refund = next(r for r in rows if r["txn_type"] == "Refund")
    assert refund["txn_date"] == "2026-07-03" and refund["txn_datetime"] == "2026-07-03T23:48:02"
    assert refund["product_sales"] == -19.95 and refund["total"] == -17.53
    fees = [r for r in rows if r["txn_type"] == "FBA Inventory Fee"]
    assert {r["description"] for r in fees} == {"FBA Long-Term Storage Fee", "FBA storage fee"}
    ltsf = next(r for r in fees if r["description"] == "FBA Long-Term Storage Fee")
    assert ltsf["other"] == -38.10 and ltsf["total"] == -38.10
    assert ltsf["quantity"] is None and ltsf["sku"] is None and ltsf["order_id"] is None
    assert ltsf["txn_datetime"] == "2026-07-05T00:00:00"
    subscription = next(r for r in rows if r["txn_type"] == "Service Fee")
    assert subscription["txn_date"] == "2026-07-12" and subscription["total"] == -39.99
    assert len({r["row_key"] for r in rows}) == 5


def test_transactions_missing_total_column_reports_found_headers():
    data = b"date/time,type,sku\n\"Jul 1, 2026 3:12:44 AM PDT\",Order,A-1\n"
    with pytest.raises(IngestError) as err:
        _parse("transactions", data=data)
    assert "total" in str(err.value)
    assert "date/time" in str(err.value)


# --- cross-cutting -------------------------------------------------------------

def test_bleed_rows_are_json_serializable_and_carry_provenance():
    for report_type, fixture in BLEED_CASES:
        _, rows, _ = _parse(report_type, fixture)
        json.dumps(rows, allow_nan=False)  # raises on NaN/inf or numpy scalars
        for row in rows:
            assert row["client_id"] == UPLOAD["client_id"]
            assert row["upload_id"] == UPLOAD["id"]
            assert isinstance(row["raw"], dict)


def test_bleed_row_keys_are_sha1_and_unique_within_file():
    for report_type, fixture in BLEED_CASES:
        if report_type == "inventory_health":
            continue  # keyed on (sku, snapshot_date), no row_key
        _, rows, _ = _parse(report_type, fixture)
        keys = [r["row_key"] for r in rows]
        assert all(len(k) == 40 for k in keys)
        assert len(set(keys)) == len(keys)
