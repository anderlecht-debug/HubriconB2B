"""Daily price and volume from the settlement file — the only daily, per-SKU
series the engine has.

Every other revenue source is period-aggregated: SKU Economics and the Business
Report arrive as one row per item per upload period, usually a calendar month.
The Payments Transaction View is different: one row per settlement event with a
timestamp, the SKU, the quantity and the product sales, so it yields a realised
price per SKU per day. That is what a fortnight-long price step needs to be
visible to an estimator whose monthly price coefficient of variation would
otherwise blend it away (see price_tests.py and MATH_METHODS.md §2).

Two readings of the price are kept: gross (`product_sales / quantity`) and net
of `promotional_rebates`, because a coupon changes what the customer paid
without changing the listed price. The experiment analysis uses gross, which is
the price the seller set; net rides along so a coupon-heavy day is visible.

Only Order rows count. Refunds, adjustments and fees are settlement lines, not
demand. Shopify payout rows carry no SKU, so `daily_sku_series` refuses them and
`daily_totals` is the order-level fallback for that channel.
"""

from collections import defaultdict

from .common import num

ORDER_TYPES = {"order"}


def _is_order(row: dict) -> bool:
    return (row.get("txn_type") or "").strip().lower() in ORDER_TYPES


def _day(row: dict) -> str | None:
    d = row.get("txn_date") or row.get("txn_datetime")
    return str(d)[:10] if d else None


def daily_sku_series(settlement_rows: list[dict], sku: str, start: str, end: str) -> list[dict]:
    """[{date, units, revenue, price, price_net, orders}] for one SKU, one row per
    day with at least one order, sorted by date. Days with no orders are absent
    rather than zero: absence in a settlement file means no settlement, and the
    caller decides whether that is a zero-demand day or a gap in the export."""
    by_day: dict[str, dict] = defaultdict(lambda: {"units": 0, "revenue": 0.0, "rebates": 0.0, "orders": 0})
    for r in settlement_rows:
        if not _is_order(r) or (r.get("sku") or "") != sku:
            continue
        d = _day(r)
        if d is None or not (start <= d <= end):
            continue
        qty = int(r.get("quantity") or 0)
        if qty <= 0:
            continue
        b = by_day[d]
        b["units"] += qty
        b["revenue"] += float(r.get("product_sales") or 0)
        b["rebates"] += float(r.get("promotional_rebates") or 0)
        b["orders"] += 1
    out = []
    for d in sorted(by_day):
        b = by_day[d]
        if b["units"] <= 0:
            continue
        out.append({
            "date": d,
            "units": b["units"],
            "revenue": num(b["revenue"]),
            "price": num(b["revenue"] / b["units"], 4),
            # rebates are printed negative in the export; net = gross + rebate
            "price_net": num((b["revenue"] + b["rebates"]) / b["units"], 4),
            "orders": b["orders"],
        })
    return out


def daily_totals(settlement_rows: list[dict], start: str, end: str,
                 skus: set[str] | None = None) -> list[dict]:
    """[{date, units, revenue, orders}] across the account (or the given SKUs),
    one row per day with at least one order. Works on Shopify payout rows too,
    whose Order lines carry no SKU: `skus` then has no effect and the totals are
    the account's."""
    by_day: dict[str, dict] = defaultdict(lambda: {"units": 0, "revenue": 0.0, "orders": 0})
    for r in settlement_rows:
        if not _is_order(r):
            continue
        if skus is not None and r.get("sku") is not None and r.get("sku") not in skus:
            continue
        d = _day(r)
        if d is None or not (start <= d <= end):
            continue
        b = by_day[d]
        b["units"] += int(r.get("quantity") or 0)
        b["revenue"] += float(r.get("product_sales") or 0)
        b["orders"] += 1
    return [{"date": d, "units": by_day[d]["units"], "revenue": num(by_day[d]["revenue"]),
             "orders": by_day[d]["orders"]} for d in sorted(by_day)]
