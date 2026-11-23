"""The Bulk Operations pull lands as EXACTLY the rows the CSV exports do.

The three JSONL fixtures describe the same store as
tests/fixtures/shopify_{orders,products,inventory}_clean.csv (the store keeps
New York time, so the API's UTC timestamps are four hours ahead of the
export's). The golden tests hold the two paths equal: orders and customer
orders in full, products and stock on every field the two sources share (the
products export's raw row is the CSV line itself, so only its parsed
`_variant` numbers compare; the inventory API has no line for a location an
item is not stocked at, where the export prints a blank one)."""

from datetime import date
from pathlib import Path

import pytest

from hubricon_engine import shopify_api as sa
from hubricon_engine.ingest import parse_all
from hubricon_engine.ingest.readers import read_table

FIX = Path(__file__).parent / "fixtures"
UPLOAD = {"id": "00000000-0000-0000-0000-00000000aaaa", "client_id": "00000000-0000-0000-0000-00000000cccc",
          "period_start": "2026-07-01", "period_end": "2026-08-31"}
NY = "America/New_York"


def _lines(name):
    return sa.parse_jsonl((FIX / name).read_bytes())


def _csv(report, name):
    return parse_all(report, read_table((FIX / name).read_bytes()), UPLOAD)


def _no_raw(rows, keep=()):
    return [{**{k: v for k, v in r.items() if k != "raw"}, **{k: r["raw"].get(k) for k in keep}} for r in rows]


# ── golden ───────────────────────────────────────────────────────────────────

def test_orders_golden_equal_to_the_csv_export():
    api = sa.orders_rows(_lines("shopify_bulk_orders.jsonl"), UPLOAD, NY)
    csv = _csv("shopify_orders", "shopify_orders_clean.csv")
    assert [t for t, _, _ in api] == ["sku_economics", "customer_orders"]
    assert api == csv                      # every row, raw included
    assert len(api[0][1]) == 5 and len(api[1][1]) == 5


def test_products_golden_on_the_shared_fields():
    api = sa.products_rows(_lines("shopify_bulk_products.jsonl"), UPLOAD)
    csv = _csv("shopify_products", "shopify_products_clean.csv")
    assert [(t, k) for t, _, k in api] == [(t, k) for t, _, k in csv]
    for (_, a, _), (_, b, _) in zip(api, csv):
        assert _no_raw(a, ("_variant",)) == _no_raw(b, ("_variant",))
        assert a
    cogs = {r["sku"]: r["unit_cost_usd"] for r in api[0][1]}
    assert cogs == {"WIDGET-BLUE": 4.1, "GADGET-PRO": 9.8}   # a variant with no cost writes no cost row
    grams = {r["sku"]: r["raw"]["_variant"]["grams"] for r in api[1][1]}
    assert grams["GADGET-PRO"] == 900.0                      # 0.9 kg


def test_inventory_golden_on_the_shared_fields():
    _, api, key = sa.inventory_rows(_lines("shopify_bulk_inventory.jsonl"), UPLOAD)
    _, csv, key2 = _csv("shopify_inventory", "shopify_inventory_clean.csv")[0]
    assert key == key2
    assert _no_raw(api, ("product_name", "on_hand")) == _no_raw(csv, ("product_name", "on_hand"))
    gadget = next(r for r in api if r["sku"] == "GADGET-PRO")
    assert gadget["fulfillable_quantity"] == 25            # on hand less committed less held, as the export
    assert gadget["reserved_quantity"] == 5


# ── the bulk flow ────────────────────────────────────────────────────────────

class FakeShopify:
    """A transport double: answers the shop query, starts jobs, reports them
    RUNNING `polls` times and then COMPLETED with a URL per job."""

    def __init__(self, results: dict, polls: int = 1, status: str = "COMPLETED", locations: int = 1):
        self.results, self.polls, self.status, self.locations = results, polls, status, locations
        self.calls, self.running, self.n, self.left = [], None, 0, 0

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if "bulkOperationRunQuery" in query:
            self.n += 1
            q = variables["query"]
            kind = "orders" if "orders(" in q else "products" if "products {" in q else "inventory"
            self.running, self.left = (f"gid://shopify/BulkOperation/{self.n}", kind), self.polls
            return {"data": {"bulkOperationRunQuery": {"bulkOperation": {"id": self.running[0], "status": "CREATED"},
                                                       "userErrors": []}}}
        if "currentBulkOperation" in query:
            op_id, kind = self.running
            if self.left > 0:
                self.left -= 1
                return {"data": {"currentBulkOperation": {"id": op_id, "status": "RUNNING", "url": None}}}
            url = None if self.results.get(kind) is None else f"https://storage.example/{kind}.jsonl"
            return {"data": {"currentBulkOperation": {"id": op_id, "status": self.status, "errorCode": None,
                                                      "objectCount": "3", "url": url}}}
        if "shop {" in query:
            return {"data": {"shop": {"name": "Acme", "myshopifyDomain": "acme.myshopify.com", "ianaTimezone": NY,
                                      "currencyCode": "USD"},
                             "locations": {"edges": [{"node": {"id": str(i)}} for i in range(self.locations)]}}}
        raise AssertionError(query)


def _results():
    return {k: (FIX / f"shopify_bulk_{k}.jsonl").read_text() for k in ("orders", "products", "inventory")}


def _downloader(results):
    seen = []

    def get(url):
        seen.append(url)
        return results[url.rsplit("/", 1)[1].split(".")[0]].encode()
    get.seen = seen
    return get


def test_pull_runs_three_bulk_jobs_and_polls_until_done():
    fake, sleeps = FakeShopify(_results(), polls=2), []
    dl = _downloader(_results())
    pulled = sa.pull(fake, dl, today=date(2026, 8, 31), days=61, sleep=sleeps.append)
    assert pulled["since"] == "2026-07-01" and pulled["shop"]["timezone"] == NY
    assert pulled["shop"]["single_location"] is True
    assert len(pulled["orders"]) == 17 and len(pulled["products"]) == 5 and len(pulled["inventory"]) == 7
    assert len(dl.seen) == 3 and len(sleeps) == 6               # two RUNNING polls per job
    started = [v["query"] for q, v in fake.calls if "bulkOperationRunQuery" in q]
    assert 'created_at:>=2026-07-01' in started[0]
    assert "unitCost" in started[1] and "inventoryLevels" in started[2]


def test_ingest_of_a_pull_equals_the_three_csv_uploads():
    pulled = sa.pull(FakeShopify(_results(), polls=0), _downloader(_results()), today=date(2026, 8, 31), days=61,
                     sleep=lambda s: None)
    out = {t: rows for t, rows, _ in sa.ingest(pulled, UPLOAD["client_id"])}
    csv_orders = {t: rows for t, rows, _ in _csv("shopify_orders", "shopify_orders_clean.csv")}
    strip = lambda rows: [{k: v for k, v in r.items() if k != "upload_id"} for r in rows]
    assert strip(out["sku_economics"]) == strip(csv_orders["sku_economics"])
    assert strip(out["customer_orders"]) == strip(csv_orders["customer_orders"])
    inv = {r["sku"]: r for r in out["inventory_levels"]}
    # the inventory pull's quantities, with the products export's variant numbers kept for the findings
    assert inv["WIDGET-BLUE"]["fulfillable_quantity"] == 412 and inv["WIDGET-BLUE"]["inbound_quantity"] == 100
    assert inv["WIDGET-BLUE"]["raw"]["_variant"]["compare_at_price"] == 24.99
    assert {r["snapshot_date"] for r in out["inventory_levels"]} == {"2026-08-31"}
    assert {r["upload_id"] for rows in out.values() for r in rows} == {None}


def test_a_multi_location_store_prints_no_variant_quantity():
    pulled = sa.pull(FakeShopify(_results(), polls=0, locations=2), _downloader(_results()),
                     today=date(2026, 8, 31), sleep=lambda s: None)
    assert pulled["shop"]["single_location"] is False
    frame = sa.products_frame(pulled["products"], single_location=False)
    assert set(frame["Variant Inventory Qty"]) == {""}
    out = {t: rows for t, rows, _ in sa.ingest(pulled, "c")}
    assert {r["sku"] for r in out["inventory_levels"]} == {"WIDGET-BLUE", "WIDGET-RED", "GADGET-PRO"}


def test_a_completed_job_with_no_url_is_empty_not_an_error():
    fake = FakeShopify({"orders": None, "products": None, "inventory": None}, polls=0)
    pulled = sa.pull(fake, lambda url: pytest.fail("nothing to download"), today=date(2026, 8, 31),
                     sleep=lambda s: None)
    assert pulled["orders"] == [] and pulled["products"] == []
    assert all(rows == [] for _, rows, _ in sa.ingest(pulled, "c"))


@pytest.mark.parametrize("status", ["FAILED", "CANCELED", "EXPIRED"])
def test_a_broken_job_raises(status):
    with pytest.raises(sa.ShopifyApiError, match=status):
        sa.run_bulk(FakeShopify(_results(), polls=0, status=status), _downloader(_results()), sa.PRODUCTS_QUERY,
                    sleep=lambda s: None)


def test_user_errors_and_graphql_errors_raise():
    def refuses(q, v):
        return {"data": {"bulkOperationRunQuery": {"bulkOperation": None,
                                                   "userErrors": [{"field": None, "message": "already running"}]}}}
    with pytest.raises(sa.ShopifyApiError, match="already running"):
        sa.run_bulk(refuses, None, sa.PRODUCTS_QUERY, sleep=lambda s: None)
    with pytest.raises(sa.ShopifyApiError, match="Throttled"):
        sa.run_bulk(lambda q, v: {"errors": [{"message": "Throttled"}]}, None, sa.PRODUCTS_QUERY)


def test_a_job_that_never_finishes_times_out():
    fake = FakeShopify(_results(), polls=10 ** 6)
    with pytest.raises(sa.ShopifyApiError, match="still RUNNING"):
        sa.run_bulk(fake, None, sa.PRODUCTS_QUERY, sleep=lambda s: None, poll_seconds=60, timeout_seconds=300)


def test_utc_timestamps_become_store_local_days():
    # 02:30 UTC on Aug 1 is still Jul 31 in New York: the export would bucket it in July
    assert sa.local_time("2026-08-01T02:30:00Z", NY) == "2026-07-31 22:30:00 -0400"
    assert sa.local_time(None) == ""


def test_weekly_economics_reuses_the_parser_per_week():
    lines = _lines("shopify_bulk_orders.jsonl")
    rows = sa.weekly_economics(lines, "c", date(2026, 7, 1), date(2026, 8, 31), NY)
    monthly = sa.orders_rows(lines, UPLOAD, NY)[0][1]
    for sku in ("WIDGET-BLUE", "WIDGET-RED"):
        assert sum(r["units_sold"] for r in rows if r["sku"] == sku) == \
            sum(r["units_sold"] for r in monthly if r["sku"] == sku)
    assert all(r["period_start"] <= r["period_end"] for r in rows)
    assert sa.weeks(date(2026, 7, 1), date(2026, 7, 13)) == [
        (date(2026, 7, 1), date(2026, 7, 5)), (date(2026, 7, 6), date(2026, 7, 12)), (date(2026, 7, 13), date(2026, 7, 13))]


def test_last_sold_skips_cancelled_and_pending_orders():
    got = sa.last_sold(_lines("shopify_bulk_orders.jsonl"), NY)
    # #1004 (cancelled) and #1007 (pending) do not count
    assert got == {"WIDGET-BLUE": "2026-08-15", "WIDGET-RED": "2026-08-15", "name:Gift Wrap": "2026-08-02"}
