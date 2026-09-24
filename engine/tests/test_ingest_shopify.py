"""The Shopify route: the store's own three exports plus the two ad platforms
a Shopify brand actually buys.

Fixtures are small hand-built exports carrying the real header names. Every
number below was worked out from the fixture by hand — line revenue, the
revenue-share refund allocation, the calendar-month buckets, the payment-fee
estimate — so a parser that quietly changes its arithmetic fails here instead
of re-stating itself. The window spans two months on purpose: the month
bucketing and its clipping are the part of shopify_orders most likely to
drift.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from hubricon_engine.ingest import PARSERS, parse_all
from hubricon_engine.ingest.headers import IngestError, is_total_row, row_key
from hubricon_engine.ingest.readers import read_table

FIXTURES = Path(__file__).parent / "fixtures"
UPLOAD = {
    "id": "00000000-0000-0000-0000-00000000aaaa",
    "client_id": "00000000-0000-0000-0000-00000000cccc",
    "period_start": "2026-07-01",
    "period_end": "2026-08-31",
}


def _parse(report_type: str, fixture: str, upload: dict | None = None):
    df = read_table((FIXTURES / fixture).read_bytes())
    return parse_all(report_type, df, upload or UPLOAD)


def _one(report_type: str, fixture: str, upload: dict | None = None):
    """The single (table, rows, on_conflict) triple of a one-table parser."""
    out = _parse(report_type, fixture, upload)
    assert len(out) == 1
    return out[0]


def _orders(upload: dict | None = None) -> dict[tuple[str, str], dict]:
    _, rows, _ = _parse("shopify_orders", "shopify_orders_clean.csv", upload)[0]
    return {(r["sku"], r["period_start"]): r for r in rows}


# --- shopify_orders -----------------------------------------------------------
# The fixture, order by order (line revenue = price x qty - line discount):
#   #1001 Jul 10  paid                1x WIDGET-BLUE @20        -> 20.00
#   #1002 Jul 20  paid                2x WIDGET-BLUE @20        -> 40.00
#                 (continuation line) 1x WIDGET-RED  @20 less 2 -> 18.00
#   #1003 Jul 25  partially_refunded  3x WIDGET-BLUE @20        -> 60.00, 20.00 refunded
#   #1004 Jul 28  refunded AND cancelled                        -> dropped
#   #1005 Aug 2   paid                1x WIDGET-BLUE @22        -> 22.00
#                 (continuation line) 1x "Gift Wrap" @5, no sku ->  5.00
#   #1006 Aug 15  partially_refunded  1x WIDGET-BLUE @22        -> 22.00, 11.60 refunded
#                 (continuation line) 2x WIDGET-RED  @20 less 4 -> 36.00
#   #1007 Aug 20  pending                                       -> dropped


def test_orders_land_as_monthly_sku_economics_rows():
    # the orders export feeds two tables since 2026-09-23; the first is the one under test here
    table, rows, key = _parse("shopify_orders", "shopify_orders_clean.csv")[0]
    assert table == "sku_economics"
    assert key == "client_id,channel,sku,period_start,period_end"
    assert {(r["sku"], r["period_start"], r["period_end"]) for r in rows} == {
        ("WIDGET-BLUE", "2026-07-01", "2026-07-31"),
        ("WIDGET-BLUE", "2026-08-01", "2026-08-31"),
        ("WIDGET-RED", "2026-07-01", "2026-07-31"),
        ("WIDGET-RED", "2026-08-01", "2026-08-31"),
        ("name:Gift Wrap", "2026-08-01", "2026-08-31"),
    }
    assert {r["channel"] for r in rows} == {"shopify"}
    # the Shopify export has no ASIN; the products export bridges sku -> handle
    assert {r["asin"] for r in rows} == {None}
    # no fee decomposition exists in the orders export
    for r in rows:
        assert r["fba_fulfillment_fees"] is None
        assert r["storage_fees"] is None
        assert r["other_fees"] is None


def test_orders_sum_units_and_sales_per_sku_per_month():
    o = _orders()
    # July WIDGET-BLUE: 1 + 2 + 3 units, 20 + 40 + 60 revenue, 20.00 refunded
    blue_jul = o[("WIDGET-BLUE", "2026-07-01")]
    assert blue_jul["units_sold"] == 6
    assert blue_jul["sales"] == 100.00
    assert blue_jul["avg_sales_price"] == 20.00       # 120 gross / 6 units, pre-discount
    assert blue_jul["raw"]["orders"] == 3 and blue_jul["raw"]["lines"] == 3
    # August WIDGET-BLUE: 1 + 1 units at $22, 44 revenue less 4.40 of refund
    blue_aug = o[("WIDGET-BLUE", "2026-08-01")]
    assert blue_aug["units_sold"] == 2
    assert blue_aug["sales"] == 39.60
    assert blue_aug["avg_sales_price"] == 22.00


def test_orders_forward_fill_the_order_level_fields_onto_later_lines():
    """#1002's second line carries only Name and the line item — no status, no
    Created at. It must still bucket into July under its order's date."""
    red_jul = _orders()[("WIDGET-RED", "2026-07-01")]
    assert red_jul["units_sold"] == 1
    assert red_jul["sales"] == 18.00                  # 20.00 less the $2 line discount
    assert red_jul["period_end"] == "2026-07-31"
    assert red_jul["raw"]["orders"] == 1


def test_orders_allocate_the_order_refund_by_revenue_share():
    """#1006 refunds $11.60 over lines worth 22.00 and 36.00 of 58.00:
    22/58 x 11.60 = 4.40 off the blue line, 36/58 x 11.60 = 7.20 off the red."""
    o = _orders()
    assert o[("WIDGET-BLUE", "2026-08-01")]["raw"]["refunds"] == 4.40
    red_aug = o[("WIDGET-RED", "2026-08-01")]
    assert red_aug["raw"]["refunds"] == 7.20
    assert red_aug["units_sold"] == 2
    assert red_aug["sales"] == 28.80                  # 36.00 - 7.20
    # a whole-order refund on one line is capped at that line's revenue
    assert o[("WIDGET-BLUE", "2026-07-01")]["raw"]["refunds"] == 20.00


def test_orders_drop_a_cancelled_order_and_an_unpaid_one():
    """#1004 (5x WIDGET-RED, cancelled the next day) and #1007 (pending) never
    moved money. July WIDGET-RED would show 6 units if #1004 leaked in."""
    o = _orders()
    assert ("WIDGET-RED", "2026-07-01") in o
    assert o[("WIDGET-RED", "2026-07-01")]["units_sold"] == 1
    assert o[("WIDGET-RED", "2026-08-01")]["units_sold"] == 2   # #1006 only, not #1007


def test_orders_keep_a_line_with_no_sku_under_its_item_name():
    """A gift-wrap line has no Variant SKU; keying it on the name lands the
    revenue instead of vanishing it."""
    wrap = _orders()[("name:Gift Wrap", "2026-08-01")]
    assert wrap["units_sold"] == 1
    assert wrap["sales"] == 5.00
    assert wrap["avg_sales_price"] == 5.00


def test_orders_estimate_the_payment_fee_and_name_the_basis():
    """Shopify Payments' standard card rate: 2.9% of net sales plus $0.30 an
    order, the fixed part split across an order's lines by revenue share.

    July WIDGET-BLUE carries #1001 (whole order), #1003 (whole order) and
    40/58 of #1002 = 2.6897 orders' worth of the fixed fee:
        0.029 x 100.00 + 0.30 x 2.6897 = 2.90 + 0.8069 = 3.7069 -> -3.71
    July WIDGET-RED carries only 18/58 of #1002:
        0.029 x 18.00 + 0.30 x 0.31034 = 0.522 + 0.0931 = 0.6151 -> -0.62
    """
    o = _orders()
    blue_jul = o[("WIDGET-BLUE", "2026-07-01")]
    assert blue_jul["referral_fees"] == -3.71
    assert blue_jul["net_proceeds"] == 96.29          # 100.00 - 3.7069
    red_jul = o[("WIDGET-RED", "2026-07-01")]
    assert red_jul["referral_fees"] == -0.62
    assert red_jul["net_proceeds"] == 17.38
    assert blue_jul["raw"]["fee_basis"] == (
        "schedule estimate: 2.9% + $0.30 per order, allocated by revenue share"
    )


def test_orders_payment_schedule_can_be_stated_by_the_environment(monkeypatch):
    """A store on a negotiated rate states it rather than being told 2.9%."""
    monkeypatch.setenv("SHOPIFY_PAYMENTS_RATE", "0.02")
    monkeypatch.setenv("SHOPIFY_PAYMENTS_FIXED", "0")
    blue_jul = _orders()[("WIDGET-BLUE", "2026-07-01")]
    assert blue_jul["referral_fees"] == -2.00         # 2% of 100.00, no fixed part
    assert blue_jul["net_proceeds"] == 98.00
    assert blue_jul["raw"]["fee_basis"] == (
        "schedule estimate: 2.0% + $0.00 per order, allocated by revenue share"
    )


def test_orders_clip_the_month_buckets_to_the_upload_window():
    """A window that starts mid-July and ends mid-August keeps period_days
    honest: July's bucket opens on the 15th, August's closes on the 10th.
    #1001 (Jul 10) and #1006 (Aug 15) fall outside and are skipped."""
    window = {**UPLOAD, "period_start": "2026-07-15", "period_end": "2026-08-10"}
    o = _orders(window)
    assert set(o) == {("WIDGET-BLUE", "2026-07-15"), ("WIDGET-RED", "2026-07-15"),
                      ("WIDGET-BLUE", "2026-08-01"), ("name:Gift Wrap", "2026-08-01")}
    blue_jul = o[("WIDGET-BLUE", "2026-07-15")]
    assert blue_jul["period_end"] == "2026-07-31"
    assert blue_jul["units_sold"] == 5                # #1002's 2 and #1003's 3, not #1001's 1
    assert blue_jul["sales"] == 80.00                 # 100.00 revenue less the 20.00 refund
    blue_aug = o[("WIDGET-BLUE", "2026-08-01")]
    assert blue_aug["period_end"] == "2026-08-10"
    assert blue_aug["units_sold"] == 1                # #1005 only; #1006 is past the window
    assert blue_aug["sales"] == 22.00


# --- shopify_products ---------------------------------------------------------
# widget/WIDGET-BLUE  Blue variant,   412 on hand, cost 4.10
# widget/WIDGET-RED   Red  variant,    88 on hand, no cost stated
# widget              image-only line, no Variant SKU
# gadget-pro/GADGET-PRO  single variant ("Default Title"), 30 on hand, cost 9.80


def test_products_feed_both_the_cost_sheet_and_the_stock_snapshot():
    out = _parse("shopify_products", "shopify_products_clean.csv")
    assert [t for t, _, _ in out] == ["cogs_inputs", "inventory_levels"]
    (_, cogs_rows, cogs_key), (_, inv_rows, inv_key) = out
    assert cogs_key == "client_id,sku"
    assert inv_key == "client_id,channel,sku,snapshot_date"

    # only the two variants that state a Cost per item write a cost row
    assert {r["sku"] for r in cogs_rows} == {"WIDGET-BLUE", "GADGET-PRO"}
    blue = next(r for r in cogs_rows if r["sku"] == "WIDGET-BLUE")
    assert blue["unit_cost_usd"] == 4.10
    assert blue["asin"] == "widget"                   # the handle bridges sku -> product page
    assert blue["product_name"] == "Widget — Blue"
    pro = next(r for r in cogs_rows if r["sku"] == "GADGET-PRO")
    assert pro["unit_cost_usd"] == 9.80
    # Shopify's placeholder option value is not part of a product's name
    assert pro["product_name"] == "Gadget Pro"

    assert [(r["sku"], r["fulfillable_quantity"], r["asin"]) for r in inv_rows] == [
        ("WIDGET-BLUE", 412, "widget"),
        ("WIDGET-RED", 88, "widget"),
        ("GADGET-PRO", 30, "gadget-pro"),
    ]
    assert {r["channel"] for r in inv_rows} == {"shopify"}
    assert {r["snapshot_date"] for r in inv_rows} == {UPLOAD["period_start"]}
    # Shopify has no FBA warehouse: nothing inbound, nothing reserved, no FNSKU
    for r in inv_rows:
        assert r["fnsku"] is None and r["inbound_quantity"] is None and r["reserved_quantity"] is None


def test_products_cost_rows_carry_only_the_cost_keys():
    """PostgREST upserts the columns provided. A COGS-template row already on
    file must keep its freight, packaging, fulfilment and lead time, so the
    products export writes unit_cost_usd and nothing else costed."""
    (_, cogs_rows, _), _ = _parse("shopify_products", "shopify_products_clean.csv")
    for row in cogs_rows:
        assert set(row) == {"client_id", "upload_id", "sku", "asin", "product_name",
                            "unit_cost_usd", "raw"}


def test_products_skip_image_lines_and_unstated_costs():
    (_, cogs_rows, _), (_, inv_rows, _) = _parse("shopify_products", "shopify_products_clean.csv")
    # the third fixture line is a Handle and an Image Src and nothing else
    assert len(inv_rows) == 3
    # WIDGET-RED states no cost: a blank must never overwrite a stated number
    assert "WIDGET-RED" not in {r["sku"] for r in cogs_rows}


def test_products_write_no_stock_row_for_a_variant_with_no_quantity():
    """Shopify prints Variant Inventory Qty only for a single-location store,
    so a multi-location export blanks it. A row of nulls would make the Health
    Score read 'inventory on file' while the models have nothing to run on —
    the stock has to come from the inventory export instead."""
    df = pd.DataFrame(
        [
            {"Handle": "kit", "Title": "Starter Kit", "Variant SKU": "KIT-S",
             "Variant Inventory Qty": "", "Cost per item": "3.00"},
            {"Handle": "kit", "Title": "Starter Kit", "Variant SKU": "KIT-OUT",
             "Variant Inventory Qty": "0", "Cost per item": "3.00"},
        ]
    )
    (_, cogs_rows, _), (_, inv_rows, _) = parse_all("shopify_products", df, UPLOAD)
    # the cost is still read from both: only the stock row is withheld
    assert {r["sku"] for r in cogs_rows} == {"KIT-S", "KIT-OUT"}
    # out of stock is a stated zero, and it is not the same as a blank
    assert [(r["sku"], r["fulfillable_quantity"]) for r in inv_rows] == [("KIT-OUT", 0)]


def test_products_say_what_is_missing_when_the_export_states_neither_cost_nor_stock():
    """The multi-location store that never filled in Cost per item: the file
    is well-formed and holds nothing we can use. 'No usable data rows' is true
    and useless, so the parse error names both things to go and do — it is
    what the founder reads off uploads.parse_error."""
    df = pd.DataFrame([{"Handle": "kit", "Title": "Starter Kit", "Variant SKU": "KIT-S",
                        "Variant Inventory Qty": "", "Cost per item": ""}])
    with pytest.raises(IngestError) as err:
        parse_all("shopify_products", df, UPLOAD)
    assert "Cost per item" in str(err.value) and "Inventory > Export" in str(err.value)


def test_products_forward_fill_the_title_onto_later_variants():
    """Shopify prints Title on a product's first line only; the variants
    beneath it inherit it, which is what makes their product_name readable."""
    df = pd.DataFrame(
        [
            {"Handle": "kit", "Title": "Starter Kit", "Option1 Value": "Small",
             "Variant SKU": "KIT-S", "Variant Inventory Qty": "10", "Cost per item": "3.00"},
            {"Handle": "kit", "Title": "", "Option1 Value": "Large",
             "Variant SKU": "KIT-L", "Variant Inventory Qty": "4", "Cost per item": "4.50"},
        ]
    )
    (_, cogs_rows, _), _ = parse_all("shopify_products", df, UPLOAD)
    assert [r["product_name"] for r in cogs_rows] == ["Starter Kit — Small", "Starter Kit — Large"]


# --- shopify_inventory --------------------------------------------------------
# The fixture is the export a two-location store produces (Main Warehouse and
# 3PL East), worked out by hand:
#   WIDGET-BLUE  300 + 112 available, 100 incoming, 12 + 3 committed, 5 + 0 unavailable
#   WIDGET-RED    88 available at one location, a second location line entirely blank
#   GADGET-PRO   no Available column value at all: 30 on hand less 4 committed, 1 unavailable
#   GHOST-1      every state blank -> no row
#   (one line carries a Handle and quantities but no SKU -> no row)


def _inventory(fixture: str = "shopify_inventory_clean.csv") -> dict[str, dict]:
    table, rows, on_conflict = _one("shopify_inventory", fixture)
    assert (table, on_conflict) == ("inventory_levels", "client_id,channel,sku,snapshot_date")
    return {r["sku"]: r for r in rows}


def test_inventory_sums_a_variant_across_its_locations():
    rows = _inventory()
    blue = rows["WIDGET-BLUE"]
    assert blue["fulfillable_quantity"] == 412        # 300 + 112 sellable
    assert blue["inbound_quantity"] == 100            # on a transfer, not landed
    assert blue["reserved_quantity"] == 20            # (12 + 3) committed + 5 held back
    assert blue["raw"]["on_hand"] == 432
    assert blue["asin"] == "widget"                   # the handle bridges sku -> product page
    assert blue["raw"]["product_name"] == "Widget — Blue"
    assert [loc["location"] for loc in blue["raw"]["locations"]] == ["Main Warehouse", "3PL East"]


def test_inventory_quantities_are_integers_not_floats():
    """pandas promotes an int column that also holds blanks to float; an
    integer column and a row-key hash both care."""
    for row in _inventory().values():
        for key in ("fulfillable_quantity", "inbound_quantity", "reserved_quantity"):
            assert row[key] is None or isinstance(row[key], int)


def test_inventory_ignores_a_location_line_that_states_nothing():
    red = _inventory()["WIDGET-RED"]
    assert red["fulfillable_quantity"] == 88
    assert len(red["raw"]["locations"]) == 2
    assert all(v is None for k, v in red["raw"]["locations"][1].items() if k != "location")


def test_inventory_derives_sellable_stock_when_the_export_omits_available():
    """Shopify's own identity: on hand = available + committed + unavailable.
    Passing On hand off as sellable would promise units already spoken for."""
    pro = _inventory()["GADGET-PRO"]
    assert pro["fulfillable_quantity"] == 25          # 30 on hand - 4 committed - 1 unavailable
    assert pro["reserved_quantity"] == 5
    assert pro["raw"]["product_name"] == "Gadget Pro"  # Shopify's placeholder option is not a name


def test_inventory_skips_a_variant_with_no_stated_state_and_a_line_with_no_sku():
    rows = _inventory()
    assert set(rows) == {"WIDGET-BLUE", "WIDGET-RED", "GADGET-PRO"}


def test_inventory_never_lets_derived_stock_go_negative():
    df = pd.DataFrame([{"SKU": "ODD-1", "Location": "Main", "On hand": "3", "Committed": "5"}])
    _, rows, _ = parse_all("shopify_inventory", df, UPLOAD)[0]
    assert rows[0]["fulfillable_quantity"] == 0


def test_inventory_rows_carry_the_shopify_channel_and_the_snapshot_date():
    for row in _inventory().values():
        assert row["channel"] == "shopify"
        assert row["snapshot_date"] == UPLOAD["period_start"]
        assert row["fnsku"] is None


# --- shopify_payouts ----------------------------------------------------------


def test_payouts_type_the_amounts_and_flip_the_fee_sign():
    table, rows, key = _one("shopify_payouts", "shopify_payouts_clean.csv")
    assert table == "settlement_transactions"
    assert key == "client_id,row_key"
    assert len(rows) == 5                             # the sixth line repeats the first
    by_type = {r["txn_type"]: r for r in rows}
    assert set(by_type) == {"charge", "refund", "adjustment", "chargeback"}

    charge = next(r for r in rows if r["order_id"] == "#1003" and r["txn_type"] == "charge")
    assert charge["product_sales"] == 65.00 and charge["other"] is None
    assert charge["selling_fees"] == -2.19            # Shopify prints 2.19; fees are stored negative
    assert charge["total"] == 62.81
    assert charge["txn_datetime"] == "2026-07-25T16:40:03"   # offset dropped, not converted
    assert charge["txn_date"] == "2026-07-25"
    assert charge["settlement_id"] == "2026-07-27"    # the payout date reconciles the batch
    assert charge["description"] == "charge · Shopify Payments"
    assert charge["marketplace"] == "shopify" and charge["channel"] == "shopify"

    # everything that is not a charge is `other`, so product_sales stays sales
    refund = by_type["refund"]
    assert refund["product_sales"] is None and refund["other"] == -20.00
    assert refund["selling_fees"] == 0.0              # a zero fee, never -0.0
    chargeback = by_type["chargeback"]
    assert chargeback["other"] == -63.50 and chargeback["selling_fees"] == -15.00
    assert chargeback["total"] == -78.50
    adjustment = by_type["adjustment"]
    assert adjustment["order_id"] is None and adjustment["other"] == -15.00
    assert adjustment["description"] == "adjustment"  # no payment method on the line


def test_payouts_row_key_is_channel_led_and_stable():
    _, rows, _ = _one("shopify_payouts", "shopify_payouts_clean.csv")
    charge = next(r for r in rows if r["order_id"] == "#1002" and r["txn_type"] == "charge")
    assert charge["row_key"] == row_key(
        "shopify", "2026-07-20T10:15:22", "2026-07-22", "charge", "#1002", 63.5, 2.14, 61.36)
    assert len({r["row_key"] for r in rows}) == 5
    # re-uploading the same export must upsert, not duplicate
    _, again, _ = _one("shopify_payouts", "shopify_payouts_clean.csv")
    assert [r["row_key"] for r in again] == [r["row_key"] for r in rows]
    # and a Shopify line can never collide with an Amazon settlement line
    assert charge["row_key"] != row_key(
        "amazon", "2026-07-20T10:15:22", "2026-07-22", "charge", "#1002", 63.5, 2.14, 61.36)


# --- meta_ads and google_ads_campaign -----------------------------------------


def test_meta_ads_prefixes_the_campaign_and_skips_the_totals_line():
    table, rows, key = _one("meta_ads", "meta_ads_clean.csv")
    assert table == "ppc_spend"
    assert key == "client_id,campaign_id,report_date"
    assert len(rows) == 4                             # the fifth line is Meta's totals row
    assert {r["campaign_name"] for r in rows} == {"Meta · Prospecting - Broad", "Meta · Retargeting - DPA"}
    # Meta's export carries no campaign id, so the prefixed name is the id
    assert all(r["campaign_id"] == r["campaign_name"] for r in rows)
    assert {r["channel"] for r in rows} == {"shopify"}

    first = next(r for r in rows if r["campaign_name"] == "Meta · Prospecting - Broad"
                 and r["report_date"] == "2026-07-01")
    assert first["spend"] == 120.50 and first["sales"] == 410.20
    assert first["clicks"] == 233 and first["impressions"] == 18204
    # "Purchases conversion value" is blank on the retargeting lines, so the
    # older "Website purchases conversion value" column carries them
    dpa = next(r for r in rows if r["campaign_name"] == "Meta · Retargeting - DPA"
               and r["report_date"] == "2026-07-02")
    assert dpa["sales"] == 180.40 and dpa["spend"] == 51.25


def test_google_ads_campaign_skips_the_preamble_and_the_total_trailers():
    """The download opens with "Campaign report" and a date range, then the
    header; it closes with two "Total: ..." sum lines."""
    table, rows, key = _one("google_ads_campaign", "google_ads_campaign_clean.csv")
    assert table == "ppc_spend"
    assert key == "client_id,campaign_id,report_date"
    assert len(rows) == 4
    assert {r["campaign_name"] for r in rows} == {"Google · Brand - Search", "Google · Shopping - All Products"}
    assert all(r["campaign_id"] == r["campaign_name"] for r in rows)
    brand = next(r for r in rows if r["campaign_name"] == "Google · Brand - Search"
                 and r["report_date"] == "2026-07-01")
    assert brand["spend"] == 41.20 and brand["sales"] == 310.55
    assert brand["clicks"] == 88 and brand["impressions"] == 1204      # "1,204" is one number
    shopping = next(r for r in rows if r["campaign_name"] == "Google · Shopping - All Products"
                    and r["report_date"] == "2026-07-02")
    assert shopping["spend"] == 49.10 and shopping["impressions"] == 8566
    # the trailers sum to 187.95; leaking one would double the day's spend
    assert sum(r["spend"] for r in rows) == pytest.approx(187.95)


def test_google_ads_search_terms_take_the_amazon_shaped_row():
    table, rows, key = _one("google_ads_search_terms", "google_ads_search_terms_clean.csv")
    assert table == "ppc_search_terms"
    assert key == ("client_id,period_start,period_end,campaign_name,ad_group_name,"
                   "targeting,search_term")
    assert len(rows) == 3                             # two "Total: ..." trailers dropped
    assert {r["campaign_name"] for r in rows} == {"Google · Brand - Search"}
    assert {r["ad_group_name"] for r in rows} == {"Widgets"}
    # the download has no Keyword column; the key needs a value, not a NULL
    assert {r["targeting"] for r in rows} == {""}
    assert {(r["period_start"], r["period_end"]) for r in rows} == {("2026-07-01", "2026-08-31")}

    bleed = next(r for r in rows if r["search_term"] == "free widget sample")
    assert bleed["spend"] == 118.32 and bleed["sales_7d"] == 0.0 and bleed["orders_7d"] == 0
    assert bleed["impressions"] == 904 and bleed["clicks"] == 61
    assert bleed["match_type"] == "Broad match"
    assert bleed["units_7d"] is None                  # Google does not report units
    winner = next(r for r in rows if r["search_term"] == "widget blue 2 pack")
    assert winner["sales_7d"] == 310.55 and winner["orders_7d"] == 4   # "4.00" conversions
    assert {r["channel"] for r in rows} == {"shopify"}


def test_is_total_row_matches_googles_trailers_and_not_a_real_search_term():
    assert is_total_row("Total: Account")
    assert is_total_row("Total: Filtered campaigns")
    assert is_total_row(" total ")
    assert not is_total_row("total gym mat")          # a real search term, not a sum
    assert not is_total_row("Total Store - Shopping") # a real campaign name
    assert not is_total_row("") and not is_total_row(None)


# --- the parser contract ------------------------------------------------------


def test_parse_all_normalises_one_and_two_table_parsers():
    """One export may feed two tables; the CLI never has to care which."""
    for report_type, fixture, n_tables in [
        ("shopify_orders", "shopify_orders_clean.csv", 2),
        ("shopify_products", "shopify_products_clean.csv", 2),
        ("shopify_inventory", "shopify_inventory_clean.csv", 1),
        ("shopify_payouts", "shopify_payouts_clean.csv", 1),
        ("meta_ads", "meta_ads_clean.csv", 1),
        ("google_ads_campaign", "google_ads_campaign_clean.csv", 1),
        ("google_ads_search_terms", "google_ads_search_terms_clean.csv", 1),
        ("business_report", "business_report_clean.csv", 1),
    ]:
        out = _parse(report_type, fixture)
        assert len(out) == n_tables
        for table, rows, on_conflict in out:
            assert isinstance(table, str) and rows and isinstance(on_conflict, str)
            assert all(r["client_id"] == UPLOAD["client_id"] for r in rows)
            json.dumps(rows, allow_nan=False)


def test_every_shopify_parser_is_registered():
    assert {"shopify_orders", "shopify_products", "shopify_inventory", "shopify_payouts",
            "meta_ads", "google_ads_campaign", "google_ads_search_terms"} <= set(PARSERS)
