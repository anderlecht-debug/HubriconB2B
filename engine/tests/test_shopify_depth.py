"""The engine does for a Shopify seller what it does for an Amazon one
(2026-10-01): the processing fee the store actually paid, fulfilment counted
once for a seller on both platforms, a cost sheet that reads for both, the
compare-at opener carried past the yes, and one first read per platform."""

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from fakedb import FakeDB
from hubricon_engine import cli, directives, measurement, notify, onboarding, operator
from hubricon_engine.cold import findings as cold_findings
from hubricon_engine.cold.snapshot import Item
from hubricon_engine.ingest import cogs, parse_all
from hubricon_engine.ingest.readers import read_table
from hubricon_engine.models import compare_at, data_quality, margin, shopify_findings

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
UPLOAD = {"client_id": "c", "id": "u", "period_start": "2026-07-01", "period_end": "2026-08-31"}


def _data(**tables):
    base = {"sku_economics": [], "cogs_inputs": [], "ppc_spend": [], "ppc_search_terms": [],
            "settlement_transactions": [], "inventory_levels": []}
    return {**base, **tables}


def _econ(sku, start, end, units, sales, *, channel="shopify", fee=None, fba=None, refunds=0.0, price=None,
          orders=None):
    return {"sku": sku, "asin": None, "channel": channel, "period_start": start, "period_end": end,
            "units_sold": units, "avg_sales_price": price if price is not None else round(sales / units, 2),
            "sales": sales, "referral_fees": fee if fee is not None else -(0.029 * sales + 0.30 * units),
            "fba_fulfillment_fees": fba, "storage_fees": None, "other_fees": None,
            "raw": {"refunds": refunds, "orders": orders if orders is not None else units,
                    "fee_basis": "schedule estimate: 2.9% + $0.30 per order, allocated by revenue share"}}


def _charge(day, amount, fee):
    return {"channel": "shopify", "txn_date": day, "txn_type": "charge", "product_sales": amount,
            "selling_fees": -fee, "total": amount - fee}


def _july_payouts(n=30, amount=50.0, fee=1.20):
    """A Payouts export spanning July: n charges, each $amount with $fee taken."""
    return [_charge(f"2026-07-{1 + (i % 31):02d}", amount, fee) for i in range(n)]


# -- 1. the processing fee the store paid ------------------------------------------------

def test_margin_uses_the_fee_the_payouts_export_shows_for_a_month_it_covers():
    econ = [_econ("A", "2026-07-01", "2026-07-31", 100, 2000.0, refunds=100.0)]
    est = margin.run(_data(sku_economics=econ))[0]
    assert est["fee_split"]["source"] == "schedule_estimate"
    assert est["amazon_fees"] == pytest.approx(0.029 * 2000 + 30.0)
    assert "estimate" in est["fee_split"]["note"] and "2.9% + $0.30" in est["fee_split"]["note"]

    paid = margin.run(_data(sku_economics=econ, settlement_transactions=_july_payouts()))[0]
    rate = 1.20 / 50.0                                   # 2.4%: a Grow-plan store, not the Basic rate
    assert paid["fee_split"]["source"] == "payouts"
    assert paid["fee_split"]["effective_rate"] == pytest.approx(rate)
    # on product sales before refunds: Shopify keeps the fee on a refunded charge
    assert paid["amazon_fees"] == pytest.approx(rate * 2100.0)
    assert paid["net_margin"] == pytest.approx(2000.0 - rate * 2100.0)
    assert paid["fee_split"]["note"].startswith("from your Payouts export")
    # the pricing engine reads the blended rate, as before for Shopify
    assert paid["fee_split"]["basis"] == "assumed_proportional"
    assert paid["fee_split"]["proportional_rate"] == pytest.approx(rate * 2100.0 / 2000.0, abs=1e-6)
    assert margin.fee_basis_line([paid]) == ("The Shopify fees in this read are the ones you paid, from your "
                                            "Payouts export: 2.40% of each charge in July 2026.")


def test_a_month_the_export_does_not_cover_takes_its_rate_and_says_estimate():
    econ = [_econ("A", "2026-06-01", "2026-06-30", 50, 1000.0), _econ("A", "2026-07-01", "2026-07-31", 50, 1000.0)]
    rows = {r["period_start"]: r for r in margin.run(_data(sku_economics=econ,
                                                           settlement_transactions=_july_payouts()))}
    assert rows["2026-07-01"]["fee_split"]["source"] == "payouts"
    june = rows["2026-06-01"]["fee_split"]
    assert june["source"] == "payouts_rate" and june["note"].startswith("estimate:")
    assert "applied to a period the export does not cover" in june["note"]
    assert rows["2026-06-01"]["amazon_fees"] == pytest.approx(0.024 * 1000.0)
    # an export that starts on the 20th does not cover July
    late = [_charge("2026-07-20", 50.0, 1.2), _charge("2026-07-31", 50.0, 1.2)]
    july = margin.run(_data(sku_economics=econ[1:], settlement_transactions=late))[0]
    assert july["fee_split"]["source"] == "payouts_rate"
    assert margin.fee_basis_line([july]).startswith("The Shopify fees for July 2026 are an estimate")


def test_amazon_rows_never_read_a_shopify_payout_and_the_bench_shape_is_unchanged():
    amazon = [{"sku": "A", "asin": "B0A", "period_start": "2026-07-01", "period_end": "2026-07-31",
               "units_sold": 100, "avg_sales_price": 20.0, "sales": 2000.0, "referral_fees": -300.0,
               "fba_fulfillment_fees": -330.0, "storage_fees": -20.0, "other_fees": None}]
    orders = [{"txn_date": "2026-07-05", "txn_type": "Order", "sku": "A", "product_sales": 2000.0}]
    row = margin.run(_data(sku_economics=amazon, settlement_transactions=orders + _july_payouts()))[0]
    assert row["amazon_fees"] == 650.0 and row["fee_split"]["source"] == "export"
    assert row["fee_split"]["basis"] == "itemized"
    assert margin.fee_basis_line([row]) is None


def test_the_fixture_exports_before_and_after_the_payouts_export():
    """The two fixture exports end to end. The Payouts fixture runs Jul 20 to
    Aug 5, so neither month is covered: both take its whole-window rate,
    (2.14 + 2.19) / (63.50 + 65.00) = 3.37%, and say estimate."""
    def parse(rt, f):
        return parse_all(rt, read_table((FIX / f).read_bytes()), UPLOAD)[0][1]
    econ, pay = parse("shopify_orders", "shopify_orders_clean.csv"), parse("shopify_payouts", "shopify_payouts_clean.csv")
    before = margin.run(_data(sku_economics=econ))
    after = margin.run(_data(sku_economics=econ, settlement_transactions=pay))
    assert sum(r["amazon_fees"] for r in before) == pytest.approx(7.06)
    assert sum(r["amazon_fees"] for r in after) == pytest.approx(7.51)
    assert {r["fee_split"]["source"] for r in after} == {"payouts_rate"}
    assert all(r["fee_split"]["effective_rate"] == pytest.approx(4.33 / 128.5, abs=1e-6) for r in after)


# -- data quality: Shopify charges reach the sales cross-check --------------------------

def test_shopify_charges_feed_the_sales_cross_check_one_sided():
    econ = [_econ("A", "2026-07-01", "2026-07-31", 30, 1350.0, refunds=150.0)]   # $1,500 before refunds
    # charges carry shipping and tax on top: above product sales is never a fault
    over = data_quality.reconcile(_data(sku_economics=econ, settlement_transactions=_july_payouts(n=31, amount=55.0)))
    assert len(over) == 1 and over[0]["b"] == "settlement_transactions" and over[0]["flagged"] is False
    assert over[0]["a_value"] == 1500.0 and over[0]["b_value"] == pytest.approx(31 * 55.0)
    # a shortfall past the tolerance is: product sales no charge accounts for
    short = data_quality.reconcile(_data(sku_economics=econ, settlement_transactions=_july_payouts(n=31, amount=40.0)))
    assert short[0]["flagged"] is True and "shortfall" in short[0]["basis"]
    run = data_quality.run(_data(sku_economics=econ, settlement_transactions=_july_payouts(n=31, amount=40.0)),
                           today=date(2026, 8, 10))
    assert "reconciliation:sales:2026-07-01" in run["flags"]["settlement_transactions"]
    # a month the export does not cover is not compared at all
    partial = [_charge("2026-07-20", 40.0, 1.0), _charge("2026-07-31", 40.0, 1.0)]
    assert data_quality.reconcile(_data(sku_economics=econ, settlement_transactions=partial)) == []


def test_amazon_settlement_orders_still_reconcile_as_before():
    econ = [{"sku": "A", "period_start": "2026-07-01", "period_end": "2026-07-31", "sales": 1000.0, "units_sold": 10}]
    txns = [{"txn_date": "2026-07-10", "txn_type": "Order", "product_sales": 800.0}]
    rec = data_quality.reconcile(_data(sku_economics=econ, settlement_transactions=txns))
    assert len(rec) == 1 and rec[0]["flagged"] is True and rec[0]["relative_gap"] == 0.2


# -- 2. fulfilment counted once -----------------------------------------------------------

def test_a_seller_on_both_platforms_pays_fulfilment_once():
    """One SKU, one cost sheet row with a $3.25 3PL fee: on Shopify it is the
    fulfilment; on an FBA sale Amazon's own fee is, and the sheet's is not
    added on top; on a merchant-fulfilled Amazon sale it is the seller's again."""
    sheet = [{"sku": "A", "unit_cost_usd": 4.0, "inbound_freight_per_unit_usd": 0.5, "packaging_per_unit_usd": 0.5,
              "fulfillment_per_unit_usd": 3.25, "other_cost_per_unit_usd": None}]
    shopify = _econ("A", "2026-07-01", "2026-07-31", 100, 2000.0)
    fba = {**_econ("A", "2026-07-01", "2026-07-31", 100, 2000.0, channel="amazon", fee=-300.0, fba=-330.0)}
    fbm = {**_econ("A", "2026-07-01", "2026-07-31", 100, 2000.0, channel="amazon", fee=-300.0, fba=None)}
    s = margin.run(_data(sku_economics=[shopify], cogs_inputs=sheet))[0]
    a = margin.run(_data(sku_economics=[fba], cogs_inputs=sheet))[0]
    m = margin.run(_data(sku_economics=[fbm], cogs_inputs=sheet))[0]
    assert s["cogs"] == 825.0          # 100 × (4 + 0.5 + 0.5 + 3.25)
    assert a["cogs"] == 500.0          # the FBA fee is the fulfilment: never both
    assert a["amazon_fees"] == 630.0
    assert m["cogs"] == 825.0          # Amazon fulfilled nothing: the seller shipped it
    assert margin.fulfilment_counted(shopify) and not margin.fulfilment_counted(fba)


# -- 3. the cost sheet reads for both platforms ------------------------------------------

def test_the_template_leads_with_sku_and_names_no_amazon_column_first():
    header = (ROOT / "cogs-template.csv").read_text().splitlines()[0].split(",")
    assert header[0] == "sku" and "asin" not in header and "listing_id" in header
    df = pd.read_csv(ROOT / "cogs-template.csv")
    assert cogs.parse(df, {"client_id": "c", "id": "u"})[1] == []          # the examples never land
    text = (ROOT / "cogs-template.csv").read_text()
    assert "Shopify" in text and "Amazon" in text and "never on top of an FBA fee" in text


def test_an_old_sheet_with_asin_still_parses_and_listing_id_lands_in_the_same_column():
    old = pd.DataFrame([{"sku": "A-1", "asin": "B0OLD", "unit_cost_usd": "4.20"}])
    new = pd.DataFrame([{"Variant SKU": "SHIRT-M", "listing_id": "linen-shirt", "unit_cost_usd": "9.40",
                         "fulfillment_per_unit_usd": "4.10"}])
    assert cogs.parse(old, {"client_id": "c", "id": "u"})[1][0]["asin"] == "B0OLD"
    row = cogs.parse(new, {"client_id": "c", "id": "u"})[1][0]
    assert row["sku"] == "SHIRT-M" and row["asin"] == "linen-shirt" and row["fulfillment_per_unit_usd"] == 4.10


# -- 4. compare-at: the opener carried past the yes -----------------------------------------

def test_the_products_export_keeps_compare_at_and_grams_on_every_row():
    out = parse_all("shopify_products", read_table((FIX / "shopify_products_clean.csv").read_bytes()), UPLOAD)
    (_, cost_rows, _), (_, inv_rows, _) = out
    blue = next(r for r in inv_rows if r["sku"] == "WIDGET-BLUE")["raw"]["_variant"]
    assert blue == {"price": 19.98, "compare_at_price": 24.99, "grams": 250.0, "handle": "widget",
                    "product_name": "Widget — Blue", "status": "active", "snapshot_date": "2026-07-01"}
    red = next(r for r in inv_rows if r["sku"] == "WIDGET-RED")["raw"]["_variant"]
    assert red["status"] == "active" and red["compare_at_price"] is None    # forward-filled, no anchor
    assert next(r for r in cost_rows if r["sku"] == "WIDGET-BLUE")["raw"]["_variant"]["compare_at_price"] == 24.99


def _variant_row(sku, price, anchor, grams=250.0, status="active", name=None):
    return {"sku": sku, "channel": "shopify", "snapshot_date": "2026-09-01",
            "raw": {"_variant": {"price": price, "compare_at_price": anchor, "grams": grams, "handle": sku.lower(),
                                 "product_name": name or sku, "status": status, "snapshot_date": "2026-09-01"}}}


def _months(sku, prices, units=60):
    starts = ["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"]
    ends = ["2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31"]
    return [_econ(sku, s, e, units, units * p, price=p, orders=units - 10)
            for s, e, p in zip(starts[-len(prices):], ends[-len(prices):], prices)]


def test_a_variant_under_its_own_compare_at_for_three_months_is_found_permanent():
    data = _data(inventory_levels=[_variant_row("TEE", 32.0, 45.0, name="Tee — Black"),
                                   _variant_row("CAP", 18.0, 24.0),            # only two months at this price
                                   _variant_row("MUG", 12.0, 12.5),            # 4% under: a rounding, not a policy
                                   _variant_row("OLD", 10.0, 20.0, status="archived")],
                 sku_economics=_months("TEE", [32.0, 32.0, 32.0]) + _months("CAP", [20.0, 18.0, 18.0])
                 + _months("MUG", [12.0, 12.0, 12.0]) + _months("OLD", [10.0, 10.0, 10.0]))
    f = shopify_findings.compare_at_finding(data)
    assert f["status"] == "found" and f["proof"] == "found" and f["n_variants"] == 1
    tee = f["rows"][0]
    assert tee["sku"] == "TEE" and tee["settled"] and tee["per_unit"] == 13.0 and tee["months_at_price"] == 3
    # face value: the gap times a 30-day month of those months' units
    assert tee["usd_month_face_value"] == pytest.approx(13.0 * (60 * 30 / 31 + 60 * 30 / 31 + 60) / 3, abs=0.01)
    cap = next(r for r in f["rows"] if r["sku"] == "CAP")
    assert cap["settled"] is False                     # watched, not yet earned
    assert {r["sku"] for r in f["rows"]} == {"TEE", "CAP"}
    assert "not what a price change would earn" in f["basis"]
    paras = shopify_findings.letter_paragraphs({"compare_at": f, "parcel_band": {"rows": []}})
    assert len(paras) == 1 and paras[0].startswith("Found in your own files, not yet proven: 1 variant has")
    assert "Tee — Black at $32.00 against $45.00" in paras[0] and "proven" not in paras[0].replace("not yet proven", "")
    assert "No step back toward the compare-at is drafted yet" in paras[0]
    assert "price step back toward the compare-at among the moves" in \
        shopify_findings.letter_paragraphs({"compare_at": f}, stepped={"TEE"})[0]


def test_the_parcel_band_is_found_not_measured_and_states_no_monthly_dollars():
    oz = 16.8
    data = _data(inventory_levels=[_variant_row("BOOT", 60.0, None, grams=oz * 28.3495, name="Boot"),
                                   _variant_row("HAT", 20.0, None, grams=200.0)],
                 sku_economics=_months("BOOT", [60.0, 60.0, 60.0]))
    f = shopify_findings.parcel_band_finding(data)
    assert f["status"] == "found" and f["measured"] is False and f["n_variants"] == 1
    row = f["rows"][0]
    assert row["sku"] == "BOOT" and row["edge_oz"] == 16 and row["band_above"] == "2 lb"
    assert row["per_parcel_low"] > 0 and row["per_parcel_high"] >= row["per_parcel_low"]
    assert "usd_month" not in str(f) and "label costs are not in the files you sent" in f["basis"]
    para = shopify_findings.letter_paragraphs({"parcel_band": f})[0]
    assert para.startswith("Found, not measured: 1 variant weighs just over a pound line")
    assert "we have not measured what this costs you" in para


def test_the_cold_lane_and_the_client_lane_share_one_definition():
    assert cold_findings.MIN_DISCOUNT_SHARE is compare_at.MIN_DISCOUNT_SHARE
    assert cold_findings.STABLE_OBSERVATIONS == compare_at.STABLE_OBSERVATIONS
    item = Item(ref="x/products/y", url="https://x/products/y", price=32.0, compare_at_price=45.0)
    assert item.discount_share == compare_at.discount_share(32.0, 45.0) == 0.2889
    assert compare_at.discount_share(45.0, 45.0) is None and compare_at.per_unit_gap(45.0, 40.0) == 0.0


def _step(sku="TEE", frac=0.04, p0=32.0, expected=180.0, **ev):
    return {"module": "pricing", "kind": "price_step", "score": 21.8, "expected_impact_usd": expected,
            "action_text": f"Move {sku} ${p0:.2f} → ${p0 * (1 + frac):.2f}.", "mandate": "standing",
            "dedupe_key": directives.dedupe_key("pricing", "price_step", sku),
            "evidence": {"sku": sku, "p0": p0, "p_new": round(p0 * (1 + frac), 2), "step_fraction": frac,
                         "status": "optimum", "delta_range": (40.0, 320.0), "p_loss": 0.03,
                         "elasticity": -1.8, "std_err": 0.3, "ci95": [-2.4, -1.2], **ev}}


def _finding_rows():
    return {"compare_at": {"rows": [{"sku": "TEE", "product_name": "Tee — Black", "price": 32.0, "compare_at": 45.0,
                                     "settled": True, "months_at_price": 3, "discount_share": 0.2889,
                                     "per_unit": 13.0, "usd_month_face_value": 780.0}]}}


def test_a_price_step_up_on_a_permanent_discount_becomes_a_step_back_toward_the_compare_at():
    up, cut, other = _step(), _step(frac=-0.03), _step(sku="CAP")
    out = directives.compare_at_directives([up, other], _finding_rows())
    tee = out[0]
    assert tee["kind"] == "price_step" and tee["mandate"] == "standing"
    assert tee["dedupe_key"] == up["dedupe_key"]                  # one SKU, one open price move
    assert tee["expected_impact_usd"] == 180.0                     # the promise is the step's own
    assert tee["evidence"]["reason"] == "compare_at" and tee["evidence"]["compare_at"] == 45.0
    assert tee["evidence"]["list_price_new"] == 33.28
    assert "back toward its own compare-at of $45.00" in tee["action_text"]
    assert "Buy Box" not in tee["action_text"] and "conversion" not in tee["action_text"]
    assert out[1] is other                                         # no finding, untouched
    assert directives.compare_at_directives([cut], _finding_rows())[0] is cut   # the curve says lower: no restore
    assert directives.compare_at_directives([up], None) == [up]


def test_draft_directives_takes_the_findings_and_measurement_values_the_step_as_a_price_step():
    plan = {"drafts": {"TEE": _step()}, "multipliers": {}}
    fit = {"item_id": "TEE", "level": "sku", "status": "ok", "elasticity": -1.8}
    margins = [{"sku": "TEE", "period_start": "2026-08-01", "period_end": "2026-08-31", "units": 60,
                "revenue": 1920.0, "amazon_fees": 70.0, "cogs": 600.0, "net_margin": 1250.0,
                "ad_spend_allocated": 0.0}]
    drafts = directives.draft_directives([], [], [fit], margins, channel="shopify", price_plan=plan,
                                         shopify_findings=_finding_rows())
    tee = next(d for d in drafts if (d["evidence"] or {}).get("sku") == "TEE")
    assert tee["evidence"]["reason"] == "compare_at"
    without = directives.draft_directives([], [], [fit], margins, channel="shopify", price_plan=plan)
    assert not (next(d for d in without if (d["evidence"] or {}).get("sku") == "TEE")["evidence"].get("reason"))
    # measured by the price-step family, on the store's own orders after the move
    after = [{**margins[0], "period_start": "2026-09-01", "period_end": "2026-09-30", "units": 56,
              "revenue": 56 * 33.28, "amazon_fees": 0.024 * 56 * 33.28, "cogs": 560.0}]
    v = measurement.measure_price_step({**tee, "id": "d1"}, after, [], date(2026, 8, 31), date(2026, 10, 5))
    assert v["verdict"] == "measured" and v["attribution"] == "attributable"


# -- 5. "both": a read per platform --------------------------------------------------------------

def _ago(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _both(**kw):
    return {"id": "b", "contact_email": "b@brand.com", "contact_name": "Bo Both", "company_name": "Both Co",
            "status": "pending", "platform": "both", "created_at": _ago(24 * 30), **kw}


def _up(kind, hours_ago):
    return {"client_id": "b", "report_type": kind, "status": "parsed", "uploaded_at": _ago(hours_ago)}


class Stored(FakeDB):
    def __init__(self, **tables):
        super().__init__(**tables)
        self.files = {}
        bucket = SimpleNamespace(upload=lambda path, data, opts=None: self.files.__setitem__(path, data))
        self.storage = SimpleNamespace(from_=lambda _name: bucket)


def _reads(monkeypatch, tmp_path, **tables):
    base = dict(clients=[_both()], briefings=[], funnel_events=[], prospects=[], client_touches=[], bookings=[],
                margin_results=[], elasticity_results=[], directives=[], asin_traffic=[], model_runs=[],
                model_outputs=[])
    db = Stored(**{**base, **tables})
    sent, runs = [], []
    monkeypatch.setattr(notify, "email_configured", lambda: True)
    monkeypatch.setattr(operator, "email_configured", lambda: True)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, text, html=None, **k:
                        sent.append({"to": to, "subject": subject, "text": text}) or True)
    page = tmp_path / "r.html"
    page.write_text("<p>read</p>")

    def run_models(db_, c, wanted, sims, seed, channel=None):
        runs.append(channel)
        db_.store.setdefault("model_runs", []).append({"id": f"run-{channel}", "params": {"channel": channel}})
        return f"run-{channel}"
    monkeypatch.setattr(cli, "_run_models", run_models)
    monkeypatch.setattr(cli, "_ingest_client", lambda *a, **k: (0, 0))
    monkeypatch.setattr(cli, "_draft_for_run", lambda *a, **k: [])
    monkeypatch.setattr(cli, "draft_plan_for_run", lambda *a, **k: None)
    monkeypatch.setattr("hubricon_engine.narrate.available", lambda: False)
    monkeypatch.setattr("hubricon_engine.report.html_report.generate", lambda *a, **k: page)
    monkeypatch.setattr("hubricon_engine.video.render", lambda *a, **k: None)
    p = operator.Pass(db, send=True, dry=False)
    p.teardowns()
    return db, p, sent, runs


def test_a_shopify_only_upload_from_a_both_client_gets_a_shopify_read_and_never_an_empty_amazon_one(
        monkeypatch, tmp_path):
    shop = [_variant_row("TEE", 32.0, 45.0, name="Tee — Black") | {"client_id": "b"}]
    econ = [r | {"client_id": "b"} for r in _months("TEE", [32.0, 32.0, 32.0])]
    # the Shopify core is in but the Amazon one is not, and the day has not passed: wait
    db, p, sent, runs = _reads(monkeypatch, tmp_path, uploads=[_up("shopify_orders", 2), _up("shopify_products", 2)],
                               sku_economics=econ, inventory_levels=shop)
    assert runs == [] and any("waits for Sales and traffic by product" in n for n in p.notes)
    # a day after the last upload: the Shopify read alone, as Profit Brief No. 001
    db, p, sent, runs = _reads(monkeypatch, tmp_path, uploads=[_up("shopify_orders", 25), _up("shopify_products", 25)],
                               sku_economics=econ, inventory_levels=shop)
    assert runs == ["shopify"]
    brief = db.rows("briefings")[0]
    assert brief["issue_number"] == 1 and brief["title"] == "Your first full read · Shopify"
    assert brief["headline"] == "Profit Brief No. 001 — your first full read of your Shopify store"
    assert "This read covers your Shopify store only." in brief["memo"]
    assert "Your Amazon files are not in yet" in brief["memo"]
    assert "Amazon fees" not in brief["memo"]
    assert "not yet proven" in brief["memo"] and "Tee — Black at $32.00 against $45.00" in brief["memo"]
    assert [s["subject"] for s in sent] == ["Your first full read is ready"]
    saved = next(o for o in db.rows("model_outputs") if o["model"] == "shopify_findings")
    assert saved["run_id"] == "run-shopify" and saved["payload"]["compare_at"]["n_variants"] == 1


def test_a_both_client_with_all_four_core_files_gets_two_reads_and_one_email(monkeypatch, tmp_path):
    uploads = [_up(k, 1) for k in ("business_report", "sku_economics", "shopify_orders", "shopify_products")]
    econ = [{"id": 1, "client_id": "b", "channel": "amazon"}, {"id": 2, "client_id": "b", "channel": "shopify"}]
    db, p, sent, runs = _reads(monkeypatch, tmp_path, uploads=uploads, sku_economics=econ)
    assert runs == ["amazon", "shopify"]
    by = {b["issue_number"]: b for b in db.rows("briefings")}
    assert by[1]["title"] == "Your first full read · Amazon" and by[2]["title"] == "Your first full read · Shopify"
    assert "Your Shopify store has its own read, Profit Brief No. 002." in by[1]["memo"]
    assert "Your Amazon account has its own read, Profit Brief No. 001." in by[2]["memo"]
    assert len(sent) == 1
    assert set(db.files) >= {"reports/b/issue-001.html", "reports/b/issue-002.html"}
    # the next pass sees both platforms read and writes nothing more
    _, _, sent2, runs2 = _reads(monkeypatch, tmp_path, uploads=uploads, sku_economics=econ,
                                briefings=db.rows("briefings"), model_runs=db.rows("model_runs"))
    assert runs2 == [] and sent2 == []


def test_a_platform_whose_files_come_later_gets_its_own_read_without_the_001_email(monkeypatch, tmp_path):
    earlier = {"id": "i1", "client_id": "b", "issue_number": 1, "title": "Your first full read · Shopify",
               "run_id": "run-shopify"}
    uploads = [_up("shopify_orders", 24 * 9), _up("shopify_products", 24 * 9), _up("business_report", 1)]
    econ = [{"id": 1, "client_id": "b", "channel": "shopify"}, {"id": 2, "client_id": "b", "channel": "amazon"}]
    db, p, sent, runs = _reads(monkeypatch, tmp_path, uploads=uploads, sku_economics=econ, briefings=[earlier])
    assert runs == [] and any("Amazon first read waits for SKU Economics" in n for n in p.notes)
    uploads.append(_up("sku_economics", 1))
    db, p, sent, runs = _reads(monkeypatch, tmp_path, uploads=uploads, sku_economics=econ, briefings=[earlier])
    assert runs == ["amazon"]
    late = next(b for b in db.rows("briefings") if b.get("title") == "Your first full read · Amazon")
    assert late["issue_number"] == 2 and "This read covers your Amazon account only." in late["memo"]
    assert sent == [] and any("published as Profit Brief No. 002" in h for h in p.human)


def test_the_upload_page_counts_the_files_the_operator_waits_for():
    js = (ROOT / "lib" / "intake.js").read_text()
    core = {k: re.findall(r'"(\w+)"', v) for k, v in re.findall(r"(\w+): \[([^\]]*)\]",
                                                              js.split("export const CORE = {")[1].split("};")[0])}
    assert core == {k: list(v) for k, v in onboarding.CORE_FILES.items()}
    uploads = [_up(k, 1) for k in core["amazon"]]
    both = operator.Pass._first_read_ready(uploads, ("amazon", "shopify"), datetime.now(timezone.utc))
    assert both["ready"] is False and both["missing"] == core["shopify"]   # four in all, as the page says
