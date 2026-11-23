"""A store's orders, products and stock, pulled through Shopify's Admin GraphQL
Bulk Operations API and handed to the SAME parsers the CSV exports go through.

Why the CSV parsers and not new ones. ingest/shopify_orders, shopify_products
and shopify_inventory hold every rule this business decided about Shopify data:
a cancelled or pending order moved no money, a refund is spread by revenue
share, a blank stock count is not zero, a cost that is not stated never
overwrites one that is. Re-deriving those rules from JSON would make two
truths. So this module only translates: each bulk result becomes the table the
store's own CSV export would have printed (the same header names, every value a
string, a blank as ""), and the existing `parse` turns it into rows. Everything
downstream (the models, the look-back, shadow mode) sees exactly the rows an
upload would have given it. tests/test_shopify_api.py holds that to account
with a JSONL fixture that describes the same store as tests/fixtures/shopify_*_clean.csv.

How a bulk pull runs (Shopify's documented flow):
  1. bulkOperationRunQuery(query) starts the job and returns its id;
  2. currentBulkOperation(type: QUERY) is polled until COMPLETED (or FAILED,
     CANCELED, EXPIRED, which raise);
  3. the JSONL at `url` is downloaded. Nested connections arrive as their own
     lines carrying `__parentId` (a line item points at its order, an
     inventory level at its inventory item). A completed job with no objects
     has a null url, which is an empty result, not an error.

Both the GraphQL call and the download are injected: `transport(query,
variables) -> dict` and `downloader(url) -> bytes | str`. Tests pass doubles
and never reach the network; `http_transport` and `http_downloader` are the
real ones.

Where the API and the export disagree, and what is done about it.
  * createdAt is UTC; the export prints store-local time, and orders bucket by
    calendar day. Timestamps are converted to the shop's ianaTimezone first.
  * The products export prints Variant Inventory Qty only for a one-location
    store. The same rule is kept (`single_location`), and the inventory pull
    carries stock for every store.
  * An item not stocked at a location has no InventoryLevel in the API, where
    the inventory export prints a blank line. Both mean "nothing stated" and
    sum to the same totals.
  * Unavailable in the export is Shopify's damaged + quality_control +
    reserved + safety_stock quantities.
"""

from __future__ import annotations

import io
import json
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from .ingest import shopify_inventory, shopify_orders, shopify_products
from .ingest.headers import IngestError

API_VERSION = "2026-10"          # lib/shopify.js API_VERSION
DEFAULT_DAYS = 60
POLL_SECONDS = 2.0
POLL_TIMEOUT_SECONDS = 30 * 60
DONE = "COMPLETED"
BROKEN = {"FAILED", "CANCELED", "CANCELLED", "EXPIRED"}

Transport = Callable[[str, dict], dict]
Downloader = Callable[[str], "bytes | str"]


class ShopifyApiError(RuntimeError):
    """The API said no: a user error, a GraphQL error, or a failed job."""


# ── the queries ──────────────────────────────────────────────────────────────

def orders_query(since: date) -> str:
    return """
{
  orders(query: "created_at:>=%s") {
    edges { node {
      id name email createdAt cancelledAt displayFinancialStatus
      totalRefundedSet { shopMoney { amount } }
      lineItems { edges { node {
        id name sku quantity
        originalUnitPriceSet { shopMoney { amount } }
        totalDiscountSet { shopMoney { amount } }
      } } }
    } }
  }
}""" % since.isoformat()


PRODUCTS_QUERY = """
{
  products {
    edges { node {
      id handle title vendor productType status
      variants { edges { node {
        id sku price compareAtPrice inventoryQuantity
        selectedOptions { name value }
        inventoryItem { id unitCost { amount } measurement { weight { value unit } } }
      } } }
    } }
  }
}"""

QUANTITY_NAMES = ("available", "committed", "damaged", "incoming", "on_hand", "quality_control",
                  "reserved", "safety_stock")
UNAVAILABLE_NAMES = ("damaged", "quality_control", "reserved", "safety_stock")

INVENTORY_QUERY = """
{
  inventoryItems {
    edges { node {
      id sku
      variant { id selectedOptions { name value } product { handle title } }
      inventoryLevels { edges { node {
        id
        location { name }
        quantities(names: [%s]) { name quantity }
      } } }
    } }
  }
}""" % ", ".join(f'"{n}"' for n in QUANTITY_NAMES)

RUN_MUTATION = """
mutation run($query: String!) {
  bulkOperationRunQuery(query: $query) {
    bulkOperation { id status }
    userErrors { field message }
  }
}"""

POLL_QUERY = """
{ currentBulkOperation(type: QUERY) { id status errorCode objectCount url partialDataUrl } }"""

SHOP_QUERY = """
{ shop { name myshopifyDomain ianaTimezone currencyCode } locations(first: 2) { edges { node { id } } } }"""


# ── transport ────────────────────────────────────────────────────────────────

def _data(response: dict) -> dict:
    """The `data` of a GraphQL response; raise on top-level errors."""
    if not isinstance(response, dict):
        raise ShopifyApiError(f"the transport returned {type(response).__name__}, not a dict")
    if response.get("errors"):
        msgs = [e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in response["errors"]]
        raise ShopifyApiError("Shopify GraphQL: " + "; ".join(msgs))
    return response["data"] if "data" in response else response


def http_transport(shop: str, token: str, api_version: str = API_VERSION, timeout: float = 60.0) -> Transport:
    """The real transport: one POST per call to the shop's Admin GraphQL endpoint."""
    endpoint = f"https://{shop}/admin/api/{api_version}/graphql.json"

    def call(query: str, variables: dict | None = None) -> dict:
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(endpoint, data=body, method="POST", headers={
            "content-type": "application/json", "x-shopify-access-token": token})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode())
    return call


def http_downloader(timeout: float = 300.0) -> Downloader:
    def get(url: str) -> bytes:
        if not url.startswith("https://"):
            raise ShopifyApiError("refusing a non-https bulk result URL")
        with urllib.request.urlopen(url, timeout=timeout) as res:
            return res.read()
    return get


# ── one bulk job ─────────────────────────────────────────────────────────────

def parse_jsonl(blob: bytes | str | None) -> list[dict]:
    if not blob:
        return []
    text = blob.decode("utf-8") if isinstance(blob, bytes) else blob
    return [json.loads(line) for line in io.StringIO(text) if line.strip()]


def run_bulk(transport: Transport, downloader: Downloader, query: str, sleep=time.sleep,
             poll_seconds: float = POLL_SECONDS, timeout_seconds: float = POLL_TIMEOUT_SECONDS) -> list[dict]:
    """Start one bulk query, wait for it, return its JSONL lines as dicts."""
    started = _data(transport(RUN_MUTATION, {"query": query}))["bulkOperationRunQuery"]
    errors = started.get("userErrors") or []
    if errors:
        raise ShopifyApiError("bulkOperationRunQuery: " + "; ".join(e.get("message", "") for e in errors))
    op_id = (started.get("bulkOperation") or {}).get("id")
    waited = 0.0
    while True:
        op = _data(transport(POLL_QUERY, {})).get("currentBulkOperation") or {}
        if op_id and op.get("id") and op["id"] != op_id:
            raise ShopifyApiError(f"another bulk operation ({op['id']}) replaced ours ({op_id})")
        status = str(op.get("status") or "").upper()
        if status == DONE:
            return parse_jsonl(downloader(op["url"])) if op.get("url") else []
        if status in BROKEN:
            raise ShopifyApiError(f"bulk operation {op_id} ended {status} ({op.get('errorCode')})")
        if waited >= timeout_seconds:
            raise ShopifyApiError(f"bulk operation {op_id} still {status or 'unknown'} after {timeout_seconds:.0f}s")
        sleep(poll_seconds)
        waited += poll_seconds


def shop_info(transport: Transport) -> dict:
    d = _data(transport(SHOP_QUERY, {}))
    shop = d.get("shop") or {}
    n_locations = len(((d.get("locations") or {}).get("edges")) or [])
    return {"name": shop.get("name"), "domain": shop.get("myshopifyDomain"),
            "timezone": shop.get("ianaTimezone") or "UTC", "currency": shop.get("currencyCode"),
            "single_location": n_locations <= 1}


def pull(transport: Transport, downloader: Downloader, today: date | None = None, days: int = DEFAULT_DAYS,
         sleep=time.sleep, poll_seconds: float = POLL_SECONDS) -> dict:
    """Everything one nightly ingest needs, raw: the shop, its last `days` of
    orders, its products, its stock. Three bulk jobs, one after another (a
    shop runs one bulk query at a time)."""
    today = today or datetime.now(UTC).date()
    since = today - timedelta(days=days)
    info = shop_info(transport)
    return {
        "shop": info, "since": since.isoformat(), "today": today.isoformat(),
        "orders": run_bulk(transport, downloader, orders_query(since), sleep, poll_seconds),
        "products": run_bulk(transport, downloader, PRODUCTS_QUERY, sleep, poll_seconds),
        "inventory": run_bulk(transport, downloader, INVENTORY_QUERY, sleep, poll_seconds),
    }


# ── JSONL -> the export's own table ──────────────────────────────────────────

def _s(v) -> str:
    """A cell as read_table hands it to a parser: always a string, blank as ""."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _amount(money_set: dict | None) -> str:
    return _s(((money_set or {}).get("shopMoney") or {}).get("amount"))


def _kind(gid: str | None) -> str:
    """'gid://shopify/LineItem/1' -> 'LineItem'."""
    parts = str(gid or "").split("/")
    return parts[3] if len(parts) > 3 else ""


def _children(lines: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """(top-level objects, {parent id: [child lines]}) in file order."""
    tops, kids = [], {}
    for line in lines:
        parent = line.get("__parentId")
        if parent:
            kids.setdefault(parent, []).append(line)
        else:
            tops.append(line)
    return tops, kids


def local_time(stamp: str | None, tz: str = "UTC") -> str:
    """An API timestamp as the export prints it: store-local, with its offset."""
    if not stamp:
        return ""
    dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(ZoneInfo(tz or "UTC")).strftime("%Y-%m-%d %H:%M:%S %z")


ORDER_COLUMNS = ("Name", "Email", "Financial Status", "Created at", "Cancelled at", "Refunded Amount",
                 "Lineitem quantity", "Lineitem name", "Lineitem price", "Lineitem sku", "Lineitem discount")


def orders_frame(lines: list[dict], tz: str = "UTC") -> pd.DataFrame:
    """The Orders export: one row per line item, order-level fields on the
    order's first line only, as Shopify prints it."""
    orders, kids = _children(lines)
    rows = []
    for o in orders:
        if _kind(o.get("id")) not in ("Order", ""):
            continue
        items = [k for k in kids.get(o.get("id"), []) if _kind(k.get("id")) in ("LineItem", "")]
        for i, li in enumerate(items):
            first = i == 0
            rows.append({
                "Name": _s(o.get("name")),
                "Email": _s(o.get("email")) if first else "",
                "Financial Status": _s(o.get("displayFinancialStatus")).lower() if first else "",
                "Created at": local_time(o.get("createdAt"), tz) if first else "",
                "Cancelled at": local_time(o.get("cancelledAt"), tz) if first else "",
                "Refunded Amount": _amount(o.get("totalRefundedSet")) if first else "",
                "Lineitem quantity": _s(li.get("quantity")),
                "Lineitem name": _s(li.get("name")),
                "Lineitem price": _amount(li.get("originalUnitPriceSet")),
                "Lineitem sku": _s(li.get("sku")),
                "Lineitem discount": _amount(li.get("totalDiscountSet")) or "0.00",
            })
    return pd.DataFrame(rows, columns=list(ORDER_COLUMNS), dtype=str)


GRAMS_PER = {"GRAMS": 1.0, "KILOGRAMS": 1000.0, "OUNCES": 28.349523125, "POUNDS": 453.59237}

PRODUCT_COLUMNS = ("Handle", "Title", "Vendor", "Type", "Option1 Name", "Option1 Value", "Option2 Name",
                   "Option2 Value", "Option3 Name", "Option3 Value", "Variant SKU", "Variant Grams",
                   "Variant Inventory Qty", "Variant Price", "Variant Compare At Price", "Cost per item", "Status")


def _grams(item: dict | None) -> str:
    w = (((item or {}).get("measurement") or {}).get("weight")) or {}
    if w.get("value") is None:
        return ""
    g = float(w["value"]) * GRAMS_PER.get(str(w.get("unit") or "GRAMS").upper(), 1.0)
    return _s(round(g, 2))


def _options(selected: list[dict] | None) -> list[tuple[str, str]]:
    return [(_s(o.get("name")), _s(o.get("value"))) for o in (selected or [])][:3]


def products_frame(lines: list[dict], single_location: bool = True) -> pd.DataFrame:
    """The Products export: one row per variant, product columns forward-filled
    by the parser. Variant Inventory Qty only for a one-location store, as
    Shopify prints it."""
    products, kids = _children(lines)
    rows = []
    for p in products:
        if _kind(p.get("id")) not in ("Product", ""):
            continue
        for v in kids.get(p.get("id"), []):
            if _kind(v.get("id")) not in ("ProductVariant", ""):
                continue
            item = v.get("inventoryItem") or {}
            row = {c: "" for c in PRODUCT_COLUMNS}
            for n, (name, value) in enumerate(_options(v.get("selectedOptions")), start=1):
                row[f"Option{n} Name"], row[f"Option{n} Value"] = name, value
            row.update({
                "Handle": _s(p.get("handle")), "Title": _s(p.get("title")), "Vendor": _s(p.get("vendor")),
                "Type": _s(p.get("productType")), "Variant SKU": _s(v.get("sku")), "Variant Grams": _grams(item),
                "Variant Inventory Qty": _s(v.get("inventoryQuantity")) if single_location else "",
                "Variant Price": _s(v.get("price")), "Variant Compare At Price": _s(v.get("compareAtPrice")),
                "Cost per item": _s((item.get("unitCost") or {}).get("amount")),
                "Status": _s(p.get("status")).lower(),
            })
            rows.append(row)
    return pd.DataFrame(rows, columns=list(PRODUCT_COLUMNS), dtype=str)


INVENTORY_COLUMNS = ("Handle", "Title", "Option1 Name", "Option1 Value", "Option2 Name", "Option2 Value",
                     "Option3 Name", "Option3 Value", "SKU", "Location", "Incoming", "Unavailable", "Committed",
                     "Available", "On hand")


def inventory_frame(lines: list[dict]) -> pd.DataFrame:
    """The Inventory export: one row per variant per location it is stocked at."""
    items, kids = _children(lines)
    rows = []
    for it in items:
        if _kind(it.get("id")) not in ("InventoryItem", ""):
            continue
        variant = it.get("variant") or {}
        product = variant.get("product") or {}
        base = {c: "" for c in INVENTORY_COLUMNS}
        for n, (name, value) in enumerate(_options(variant.get("selectedOptions")), start=1):
            base[f"Option{n} Name"], base[f"Option{n} Value"] = name, value
        base.update({"Handle": _s(product.get("handle")), "Title": _s(product.get("title")),
                     "SKU": _s(it.get("sku"))})
        for level in kids.get(it.get("id"), []):
            if _kind(level.get("id")) not in ("InventoryLevel", ""):
                continue
            q = {x.get("name"): x.get("quantity") for x in level.get("quantities") or []}
            held = [q[n] for n in UNAVAILABLE_NAMES if q.get(n) is not None]
            rows.append({**base, "Location": _s((level.get("location") or {}).get("name")),
                         "Incoming": _s(q.get("incoming")), "Committed": _s(q.get("committed")),
                         "Unavailable": _s(sum(held)) if held else "",
                         "Available": _s(q.get("available")), "On hand": _s(q.get("on_hand"))})
    return pd.DataFrame(rows, columns=list(INVENTORY_COLUMNS), dtype=str)


# ── frames -> the rows the CSV ingest writes ─────────────────────────────────

def upload_for(client_id: str, period_start: str, period_end: str, upload_id: str | None = None) -> dict:
    """What a parser reads off an upload. An API pull has no uploads row, so
    upload_id is None (the column is a nullable reference)."""
    return {"id": upload_id, "client_id": client_id, "period_start": period_start, "period_end": period_end}


def orders_rows(lines: list[dict], upload: dict, tz: str = "UTC"):
    df = orders_frame(lines, tz)
    return shopify_orders.parse(df, upload) if len(df) else [
        ("sku_economics", [], "client_id,channel,sku,period_start,period_end"),
        ("customer_orders", [], "client_id,channel,order_name")]


def products_rows(lines: list[dict], upload: dict, single_location: bool = True):
    df = products_frame(lines, single_location)
    empty = [("cogs_inputs", [], "client_id,sku"),
             ("inventory_levels", [], "client_id,channel,sku,snapshot_date")]
    if not len(df):
        return empty
    try:
        return shopify_products.parse(df, upload)
    except IngestError:
        # no cost and no one-location quantity anywhere: the inventory pull
        # carries the stock, and nothing about cost was said
        return empty


def inventory_rows(lines: list[dict], upload: dict):
    df = inventory_frame(lines)
    if not len(df):
        return "inventory_levels", [], "client_id,channel,sku,snapshot_date"
    return shopify_inventory.parse(df, upload)


def merge_inventory(from_products: list[dict], from_inventory: list[dict]) -> list[dict]:
    """One stock row per SKU and snapshot. The inventory pull's quantities win
    (they cover every location); the products row's raw["_variant"] (price,
    compare-at, grams, which models/shopify_findings reads) is kept on it."""
    by_sku = {r["sku"]: r for r in from_products}
    out = []
    for r in from_inventory:
        p = by_sku.pop(r["sku"], None)
        if p and isinstance(p.get("raw"), dict) and shopify_products.VARIANT_KEY in p["raw"]:
            r = {**r, "raw": {**(r.get("raw") or {}), shopify_products.VARIANT_KEY: p["raw"][shopify_products.VARIANT_KEY]}}
        out.append(r)
    return out + list(by_sku.values())


def ingest(pulled: dict, client_id: str) -> list[tuple[str, list[dict], str]]:
    """A pull as the (table, rows, on_conflict) triples cli._ingest_client
    upserts. Orders bucket by month over [since, today]; the products and
    stock are a snapshot dated today."""
    shop = pulled.get("shop") or {}
    tz = shop.get("timezone") or "UTC"
    today = pulled["today"]
    out = list(orders_rows(pulled.get("orders") or [], upload_for(client_id, pulled["since"], today), tz))
    snap = upload_for(client_id, today, today)
    (cogs_t, cogs, cogs_k), (_, prod_inv, inv_k) = products_rows(
        pulled.get("products") or [], snap, bool(shop.get("single_location", True)))
    _, inv, _ = inventory_rows(pulled.get("inventory") or [], snap)
    out.append((cogs_t, cogs, cogs_k))
    out.append(("inventory_levels", merge_inventory(prod_inv, inv), inv_k))
    return out


def weeks(start: date, end: date) -> list[tuple[date, date]]:
    """Monday-to-Sunday weeks covering [start, end], the first and last clipped."""
    out, d = [], start
    while d <= end:
        stop = min(end, d + timedelta(days=6 - d.weekday()))
        out.append((d, stop))
        d = stop + timedelta(days=1)
    return out


def weekly_economics(lines: list[dict], client_id: str, start: date, end: date, tz: str = "UTC") -> list[dict]:
    """The orders as sku_economics rows per week rather than per month, for the
    weekly shadow calls and the look-back: the same parser, run once per week
    (a week that crosses a month end comes back as two rows, as the parser
    buckets by calendar month inside its window)."""
    df = orders_frame(lines, tz)
    if not len(df):
        return []
    rows = []
    for a, b in weeks(start, end):
        rows += shopify_orders.parse(df, upload_for(client_id, a.isoformat(), b.isoformat()))[0][1]
    return rows


def last_sold(lines: list[dict], tz: str = "UTC") -> dict[str, str]:
    """{sku: the store-local date of its latest paid sale}: when a SKU now out
    of stock last sold, which bounds how long it has been out."""
    df = orders_frame(lines, tz)
    out: dict[str, str] = {}
    current = {}
    for rec in df.to_dict(orient="records"):
        if rec["Created at"] or rec["Financial Status"]:
            current = rec
        status = (current.get("Financial Status") or "").lower()
        if current.get("Cancelled at") or status in shopify_orders.DROP_STATUSES:
            continue
        sku = rec["Lineitem sku"] or (f"name:{rec['Lineitem name']}" if rec["Lineitem name"] else None)
        day = (current.get("Created at") or "")[:10]
        if sku and day and day > out.get(sku, ""):
            out[sku] = day
    return out
