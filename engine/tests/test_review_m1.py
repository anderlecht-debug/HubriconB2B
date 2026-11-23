"""REVIEW_M1.md, one test per finding: each reproduces what the review found
on a16c603 and holds the fix."""

import base64
import json
import os
from datetime import UTC, date, datetime, timedelta

import pytest
from test_lookback import CLIENT
from test_shadow import ISSUED, WEEK, StoreDB, _before, _full

from hubricon_engine import hwm, seal, shadow, shopify_api, shopify_run, usage

SHOP = "acme.myshopify.com"
LINE = "gid://shopify/AppSubscriptionLineItem/9"


# ── 1. the same month is never charged twice ────────────────────────────────

class Shopify:
    """The Admin API's usage-record mutation, honouring the idempotency key the
    way Shopify does: the same key returns the record it already made."""

    def __init__(self):
        self.records, self.calls = {}, []

    def __call__(self, query, variables):
        self.calls.append(variables)
        key = variables["idempotencyKey"]
        if key not in self.records:
            self.records[key] = {"id": f"gid://shopify/AppUsageRecord/{len(self.records) + 1}",
                                 "price": {"amount": variables["price"]["amount"]}}
        return {"data": {"appUsageRecordCreate": {"appUsageRecord": self.records[key], "userErrors": []}}}

    def charged(self):
        return round(sum(float(r["price"]["amount"]) for r in self.records.values()), 2)


def _directive(did, usd, measured_at, grade="direct"):
    return {"id": did, "client_id": CLIENT, "module": "pricing", "measured_impact_usd": usd,
            "measured_at": measured_at, "attribution": grade}


def _meter_world(directives, monkeypatch, row=None):
    db = StoreDB(shopify_shops=[{"shop_domain": SHOP, "status": "active", "mode": "live", "client_id": CLIENT,
                                 "usage_line_item_id": LINE, "cap_usd": 500, **(row or {})}],
                 directives=directives)
    shop = Shopify()
    monkeypatch.setattr(shopify_run.shopify_api, "http_transport", lambda s, t: shop)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_x")
    return db, shop


def _meter(db, today):
    return shopify_run.main(["meter", "--shop", SHOP, "--send", "--today", today], db=db)


def test_1_idempotency_key_is_shop_month_line_only():
    s = hwm.run(SHOP, [{"month": "2026-10", "dollars": [{"id": "a", "usd": 100, "grade": "direct"}]}])[0]
    changed = {**s, "fee": 30.0, "net": 30.0, "cumulative": 150.0}
    assert usage.idempotency_key(s, LINE) == usage.idempotency_key(changed, LINE)
    assert usage.idempotency_key(s, LINE) != usage.idempotency_key({**s, "month": "2026-11"}, LINE)
    assert usage.idempotency_key(s, LINE) != usage.idempotency_key({**s, "shop": "b.myshopify.com"}, LINE)
    assert usage.idempotency_key(s, LINE) != usage.idempotency_key(s, LINE + "0")


def test_1_meter_bills_only_the_month_that_just_closed(monkeypatch):
    db, shop = _meter_world([_directive("a", 100, "2026-10-12"),
                             _directive("n", 1000, "2026-11-01T00:20:00Z")], monkeypatch)
    assert _meter(db, "2026-11-01") == 0
    assert [c["price"]["amount"] for c in shop.calls] == ["20.00"]       # October only
    assert "2026-10" in shop.calls[0]["description"]
    rows = {r["month"]: r for r in db.rows("shopify_fee_months")}
    assert set(rows) == {"2026-10"} and float(rows["2026-10"]["billed_usd"]) == 20.0


def test_1_a_rerun_with_changed_numbers_never_charges_the_month_twice(monkeypatch):
    ds = [_directive("a", 100, "2026-10-12")]
    db, shop = _meter_world(ds, monkeypatch)
    assert _meter(db, "2026-11-01") == 0 and shop.charged() == 20.0
    # A late dollar lands in October and the job runs again the same day.
    ds.append(_directive("b", 50, "2026-10-30"))
    db.store["directives"] = [dict(d) for d in ds]
    assert _meter(db, "2026-11-01") == 0
    assert shop.charged() == 20.0 and len(shop.records) == 1             # no second October record
    # The correction flows through November's statement as an adjustment.
    assert _meter(db, "2026-12-01") == 0
    assert shop.charged() == 30.0                                         # 20% of $150, once
    rows = {r["month"]: r for r in db.rows("shopify_fee_months")}
    assert float(rows["2026-11"]["billed_usd"]) == 10.0 and float(rows["2026-11"]["adjustment_usd"]) == 10.0
    # Persisted, and read back: the peak each month was billed on.
    assert float(rows["2026-10"]["peak_usd"]) == 100.0 and float(rows["2026-11"]["peak_usd"]) == 150.0
    fee = db.files[f"shopify/{SHOP}/fee.json"]
    assert json.loads(fee)["billed"]["2026-10"]["peak_usd"] == 100.0
    # And a third run of November sends nothing new.
    assert _meter(db, "2026-12-01") == 0 and shop.charged() == 30.0


# ── 2. privacy: no customer email is pulled or stored ───────────────────────

def test_2_orders_pull_asks_for_no_customer_email():
    q = shopify_api.orders_query(date(2026, 10, 1))
    assert "email" not in q.lower()
    lines = [{"id": "gid://shopify/Order/1", "name": "#1", "email": "c@x.co", "createdAt": "2026-10-02T12:00:00Z",
              "displayFinancialStatus": "PAID"},
             {"id": "gid://shopify/LineItem/1", "__parentId": "gid://shopify/Order/1", "name": "W", "sku": "W",
              "quantity": 1, "originalUnitPriceSet": {"shopMoney": {"amount": "10.00"}}}]
    upload = shopify_api.upload_for(CLIENT, "2026-10-01", "2026-10-31")
    rows = {t: r for t, r, _ in shopify_api.orders_rows(lines, upload)}
    assert rows["customer_orders"] == [] and len(rows["sku_economics"]) == 1


# ── 3. --client only with --shop ────────────────────────────────────────────

def test_3_client_without_shop_is_refused_and_a_shop_row_keeps_its_own_client():
    db = StoreDB(shopify_shops=[{"shop_domain": SHOP, "status": "active", "token_enc": "v1:x"}])
    with pytest.raises(SystemExit):
        shopify_run.main(["ingest", "--client", "someone-else"], db=db)
    args = shopify_run.parser().parse_args(["ingest", "--all"])
    assert all(s["client_id"] is None for s in shopify_run.stores(db, args, env={"SHOPIFY_TOKEN_KEY": ""}))


# ── 4 and 5. disputes reach the meter, and a same-month dispute strikes ─────

def test_4_meter_applies_disputes(monkeypatch):
    db, shop = _meter_world([_directive("a", 100, "2026-10-12")], monkeypatch)
    assert _meter(db, "2026-11-01") == 0 and shop.charged() == 20.0
    db.store["shopify_disputes"] = [{"shop_domain": SHOP, "directive_id": "a", "disputed_at": "2026-11-05T10:00:00Z"}]
    assert _meter(db, "2026-12-01") == 0
    nov = {r["month"]: r for r in db.rows("shopify_fee_months")}["2026-11"]
    assert float(nov["refund_due_usd"]) == 20.0 and shop.charged() == 20.0


def test_5_a_dollar_disputed_in_its_own_month_is_struck_not_charged():
    out = hwm.run("s", [{"month": "2026-01", "dollars": [{"id": "a", "usd": 100, "grade": "direct"}],
                         "disputed": ["a"]}])[0]
    assert out["fee"] == 0.0 and out["refunded_ids"] == ["a"] and out["cumulative"] == 0.0


# ── 6 and 7. shadow calls: sealed before their week, never overwritten, whole ─

def test_6_shadow_calls_are_sealed_before_their_week_and_never_overwritten():
    full = _full()
    db = StoreDB()
    store = {"shop": SHOP, "token": "t", "client_id": CLIENT, "row": {}}
    monday = WEEK                                   # the job runs Mondays
    at = datetime(2026, 11, 16, 9, 45, tzinfo=UTC)
    out = shopify_run.shadow_store(db, store, monday, 60, pulled={**full, "today": monday.isoformat()}, now=at)
    path = f"shopify/{SHOP}/shadow/{(monday + timedelta(days=7)).isoformat()}.json"
    assert out["week_start"] == (monday + timedelta(days=7)).isoformat() and path in db.files
    calls = json.loads(db.files[path])
    assert calls and all(seal.stamp(c["issued_at"]) < f"{c['evidence']['week_start']}T00:00:00" for c in calls)
    # A second run the same week, on other numbers, leaves the stored calls alone.
    before = db.files[path]
    later = {**full, "today": monday.isoformat(), "orders": full["orders"][: len(full["orders"]) // 2]}
    shopify_run.shadow_store(db, store, monday + timedelta(days=1), 60, pulled=later, now=at + timedelta(days=1))
    assert db.files[path] == before
    _, bad = shopify_run.untampered(db, CLIENT, json.loads(db.files[path]))
    assert bad == []


def test_7_untampered_checks_the_whole_call_not_only_its_evidence():
    db = StoreDB()
    calls = shadow.run(db, _before(_full()), CLIENT, WEEK, issued_at=ISSUED)["calls"]
    edited = json.loads(json.dumps(calls))
    target = next(c for c in edited if c["expected_impact_usd"] is not None)
    target["expected_impact_usd"] = float(target["expected_impact_usd"]) + 1000
    ok, bad = shopify_run.untampered(db, CLIENT, edited)
    assert bad == [target["id"]] and len(ok) == len(calls) - 1


# ── 9. the token key reads the same in Python as in Node ────────────────────

# A key whose base64 spelling needs base64url's '-' and '_', and a token Node's
# encryptToken sealed with it (lib/shopify_review_m1.test.mjs holds the same pair).
URL_KEY = "-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_8"
VECTOR = "v1:AAECAwQFBgcICQoL8KLOxuzDkfwBGQ_RCdBEPnSjwSS77pIjnN_U_g"


def test_9_a_base64url_token_key_works_in_python_as_in_node():
    assert len(shopify_run.token_key(URL_KEY)) == 32
    std = URL_KEY.replace("-", "+").replace("_", "/")
    assert shopify_run.token_key(std) == shopify_run.token_key(URL_KEY)
    assert shopify_run.decrypt_token(VECTOR, URL_KEY, SHOP) == "shpat_vector"
    junk = base64.b64encode(os.urandom(32)).decode()
    for bad in ("not*a*key", junk[:10] + "*" + junk[10:], ""):
        with pytest.raises(ValueError):
            shopify_run.token_key(bad)


# ── 10. refunds only for fees actually collected ────────────────────────────

def test_10_a_dispute_refunds_only_what_was_collected():
    months = [{"month": "2026-01", "dollars": [{"id": "a", "usd": 1000, "grade": "direct"}], "collected": 0.0},
              {"month": "2026-02", "dollars": [], "disputed": ["a"]}]
    out = hwm.run("s", months)
    assert out[0]["fee"] == 200.0 and out[1]["refunds"] == 0.0 and out[1]["refunded_ids"] == ["a"]


def test_10_meter_feeds_capped_and_failed_sends_back(monkeypatch):
    db, _ = _meter_world([_directive("a", 100, "2026-10-12")], monkeypatch)
    refused = lambda q, v: {"data": {"appUsageRecordCreate": {"appUsageRecord": None, "userErrors": [
        {"field": ["price"], "message": "Total price exceeds balance remaining"}]}}}
    monkeypatch.setattr(shopify_run.shopify_api, "http_transport", lambda s, t: refused)
    assert _meter(db, "2026-11-01") == 0
    db.store["shopify_disputes"] = [{"shop_domain": SHOP, "directive_id": "a", "disputed_at": "2026-11-05T10:00:00Z"}]
    shop = Shopify()
    monkeypatch.setattr(shopify_run.shopify_api, "http_transport", lambda s, t: shop)
    assert _meter(db, "2026-12-01") == 0
    nov = {r["month"]: r for r in db.rows("shopify_fee_months")}["2026-11"]
    assert float(nov["refund_due_usd"]) == 0.0 and shop.calls == []
