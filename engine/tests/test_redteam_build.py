"""REDTEAM_BUILD.md's pre-install items, one test each (engine side):
1 the meter bills only a shop that said yes to the fee, 2 the install-to-yes
rate is countable, 3 the seal's global head has a line to publish, 4 no profit
is billed on a product with no unit cost."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fakedb import FakeDB
from test_lookback import TODAY, TZ, store_data, synthetic_store
from test_review_m1 import CLIENT, SHOP, _directive, _meter, _meter_world

from hubricon_engine import lookback, meter_gate, seal, shopify_api, shopify_run

NOW = datetime(2026, 11, 23, 7, 0, tzinfo=UTC)


def _fee(db):
    return json.loads(db.files[f"shopify/{SHOP}/fee.json"])


# ── 1. the meter bills only a yes ───────────────────────────────────────────

@pytest.mark.parametrize("row, said", [
    ({"fee_question": "none"}, "not billed: you haven't said yes"),
    ({"fee_question": "ask", "fee_question_at": "2026-10-30T00:00:00Z"}, "not billed: you haven't said yes"),
    ({"fee_question": "declined"}, "not billed: you declined"),
    # silence past the window counts as declined
    ({"fee_question": "ask", "fee_question_at": "2026-09-01T00:00:00Z"}, "not billed: you declined"),
])
def test_1_a_shop_that_has_not_said_yes_is_never_sent_a_usage_record(monkeypatch, row, said):
    db, shop = _meter_world([_directive("a", 100, "2026-10-12")], monkeypatch, row=row)
    assert _meter(db, "2026-11-01") == 0
    assert shop.calls == [] and shop.charged() == 0.0
    closing = _fee(db)["closing"]
    assert closing["billed"] is False and closing["not_billed"] == said
    assert closing["fee"] == 20.0          # what the fee would have been, still shown
    assert not db.rows("shopify_fee_months")


def test_1_the_run_that_opens_the_question_never_bills(monkeypatch):
    db, shop = _meter_world([_directive("a", 100, "2026-10-12")], monkeypatch, row={"fee_question": "none"})
    assert _meter(db, "2026-11-01") == 0
    assert db.rows("shopify_shops")[0]["fee_question"] == "ask" and shop.calls == []


def test_1_a_yes_without_an_approved_shopify_charge_is_not_billed(monkeypatch):
    db, shop = _meter_world([_directive("a", 100, "2026-10-12")], monkeypatch,
                            row={"fee_question": "approved", "billing_status": "pending"})
    assert _meter(db, "2026-11-01") == 0 and shop.calls == []
    assert _fee(db)["closing"]["not_billed"].startswith("not billed: ")


def test_1_a_yes_is_billed(monkeypatch):
    db, shop = _meter_world([_directive("a", 100, "2026-10-12")], monkeypatch,
                            row={"fee_question": "approved", "billing_status": "active"})
    assert _meter(db, "2026-11-01") == 0 and shop.charged() == 20.0
    assert _fee(db)["closing"]["billed"] is True


# ── 2. install-to-yes is countable from install 1 ───────────────────────────

def test_2_install_to_yes_rate():
    rows = [{"shop_domain": "a.myshopify.com", "installed_at": "2026-11-01T00:00:00Z", "fee_question": "approved"},
            {"shop_domain": "b.myshopify.com", "installed_at": "2026-11-02T00:00:00Z", "fee_question": "declined"},
            {"shop_domain": "c.myshopify.com", "installed_at": "2026-11-03T00:00:00Z", "fee_question": "none"},
            {"shop_domain": "d.myshopify.com", "installed_at": "2026-11-04T00:00:00Z", "fee_question": "ask",
             "status": "uninstalled"}]
    r = meter_gate.install_to_yes(rows)
    assert (r["installs"], r["yes"], r["rate"]) == (4, 1, 0.25)
    db = FakeDB(shopify_shops=rows)
    assert any("Install to yes: 1 of 4" in line for line in meter_gate.digest_lines(db, NOW))


# ── 3. the seal's head, published outside our systems ───────────────────────

def test_3_the_line_to_publish_names_the_global_head_its_count_and_the_time():
    h1, h2 = "a" * 64, "b" * 64
    db = FakeDB(record_seals=[{"global_seq": 1, "global_head": h1}, {"global_seq": 2, "global_head": h2}])
    assert seal.publish_line(db, NOW) == f"2026-11-23 {h2} 2 2026-11-23T07:00:00Z"
    assert seal.publish_line(FakeDB(record_seals=[]), NOW) == f"2026-11-23 {seal.GENESIS} 0 2026-11-23T07:00:00Z"


def test_3_the_workflow_publishes_to_the_seal_log_branch_only():
    from pathlib import Path
    wf = (Path(__file__).resolve().parents[2] / ".github/workflows/seal-log.yml").read_text()
    assert "publish_line" in wf and "seal-log" in wf and "contents: write" in wf
    assert "ots stamp" in wf and "opentimestamps-client" in wf
    assert "push --force" not in wf and "HEAD:seal-log" in wf and "main" not in wf.split("on:")[1].split("jobs:")[0]


# ── 4. no unit cost, no bill ────────────────────────────────────────────────

def _sku_directive(did, usd, measured_at, sku):
    return {**_directive(did, usd, measured_at), "evidence": {"sku": sku}}


def test_4_months_of_leaves_out_a_sku_with_no_cost():
    ds = [_sku_directive("a", 100, "2026-10-12", "COSTED"), _sku_directive("b", 500, "2026-10-13", "BLANK")]
    months = shopify_run.months_of(ds, costed={"COSTED"})
    assert [d["id"] for d in months[0]["dollars"]] == ["a"]
    out = shopify_run.uncosted(ds, {"COSTED"})
    assert [(u["id"], u["sku"], u["label"]) for u in out] == [("b", "BLANK", "no cost on file: not billed")]


def test_4_the_meter_bills_nothing_on_a_sku_with_no_cost(monkeypatch):
    ds = [_sku_directive("a", 100, "2026-10-12", "COSTED"), _sku_directive("b", 500, "2026-10-13", "BLANK")]
    db, shop = _meter_world(ds, monkeypatch, row={"fee_question": "approved", "billing_status": "active"})
    db.store["cogs_inputs"] = [{"client_id": CLIENT, "sku": "COSTED", "unit_cost_usd": 8.0},
                               {"client_id": CLIENT, "sku": "BLANK", "unit_cost_usd": None, "freight_usd": 1.0}]
    assert _meter(db, "2026-11-01") == 0
    assert shop.charged() == 20.0              # 20% of the costed $100, nothing on the $500
    fee = _fee(db)
    assert fee["not_billed_no_cost"][0]["sku"] == "BLANK"
    assert any("BLANK" in line and "no cost on file: not billed" in line for line in fee["closing"]["explanation"])


def test_4_lookback_shows_a_sku_with_no_cost_as_unknown_margin():
    pulled = synthetic_store()
    data = store_data(pulled)
    # RAISE has a cost-sheet row with freight but no unit cost: still no cost on file
    data["cogs_inputs"] = [r if r["sku"] != "RAISE" else {**r, "unit_cost_usd": None, "freight_usd": 1.0}
                           for r in data["cogs_inputs"]]
    data["cogs_inputs"] = [r for r in data["cogs_inputs"] if r["sku"] != "GONE"]
    out = lookback.run(data, today=TODAY, window_days=60, last_sold=shopify_api.last_sold(pulled["orders"], TZ))
    for sku in ("RAISE", "GONE"):
        items = [i for i in out["items"] if i["sku"] == sku]
        assert items, sku
        for it in items:
            assert it["usd"] is None and it["margin"] == "unknown"
    assert any("RAISE" in s and "unknown margin" in s for s in out["summary"])
    slow = next(i for i in out["items"] if i["sku"] == "SLOW")
    assert slow["usd"] is not None and slow.get("margin") != "unknown"
