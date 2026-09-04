"""Shopify Orders export -> sku_economics (channel shopify).

Shopify Admin > Orders > Export > "Orders by date" prints one line per line
item. The first line of an order carries the order-level fields (Financial
Status, Created at, Total, Refunded Amount, Cancelled at ...); the order's
further lines repeat Name and leave the rest blank, so order-level fields
are forward-filled within an order, grouped by Name in file order.

The export has no fee decomposition. The Shopify Payments transactions
export (shopify_payouts) is the ground truth for fees when it is on file;
until then referral_fees carries a labeled schedule estimate — Shopify
Payments' standard 2.9% + $0.30 per order (SHOPIFY_PAYMENTS_RATE and
SHOPIFY_PAYMENTS_FIXED state a negotiated rate) — and that estimate is what
runs on day one. raw summarises the aggregate and names the basis.

Rules, decided 2026-09-04:
  * an order with Cancelled at set, or Financial Status voided or pending,
    is dropped: no money moved.
  * a line without a Lineitem sku is keyed "name:" + Lineitem name, so a
    gift-wrap or custom line lands rather than vanishing.
  * line revenue = Lineitem price × quantity − Lineitem discount.
  * Refunded Amount is order-level and includes refunded shipping and tax;
    it is allocated across the order's lines by revenue share, capped at
    the order's line revenue so a fully refunded order nets to zero, and
    subtracted from each line's sales.
  * lines bucket by Created at calendar month, clipped to the upload's
    [period_start, period_end] so period_days stays honest; lines outside
    the window are skipped.
  * the per-order fixed fee is spread by each line's share of its order's
    revenue (orders_share), so a SKU that shares orders pays its part.
"""

import calendar
import os
from datetime import date

import pandas as pd

from .headers import as_int, clean_int, clean_money, clean_str, dedupe_last, map_columns, to_iso_date

SPEC = {
    "name": {"synonyms": ["name", "ordername", "order"], "required": True, "cleaner": clean_str},
    "financial_status": {"synonyms": ["financialstatus"], "cleaner": clean_str},
    "created_at": {"synonyms": ["createdat", "created"], "required": True, "cleaner": clean_str},
    "cancelled_at": {"synonyms": ["cancelledat", "canceledat"], "cleaner": clean_str},
    "refunded_amount": {"synonyms": ["refundedamount"], "cleaner": clean_money},
    "quantity": {"synonyms": ["lineitemquantity"], "required": True, "cleaner": clean_int},
    "line_name": {"synonyms": ["lineitemname"], "cleaner": clean_str},
    "price": {"synonyms": ["lineitemprice"], "required": True, "cleaner": clean_money},
    "sku": {"synonyms": ["lineitemsku"], "cleaner": clean_str},
    "discount": {"synonyms": ["lineitemdiscount"], "cleaner": clean_money},
}
ORDER_FIELDS = ("financial_status", "created_at", "cancelled_at", "refunded_amount")
DROP_STATUSES = {"voided", "pending"}
DEFAULT_PAYMENTS_RATE = 0.029
DEFAULT_PAYMENTS_FIXED = 0.30
CHANNEL = "shopify"


def payments_schedule() -> tuple[float, float]:
    """(rate, fixed per order): Shopify Payments' standard card rate unless
    the environment states the store's negotiated one."""
    return (
        float(os.environ.get("SHOPIFY_PAYMENTS_RATE", DEFAULT_PAYMENTS_RATE)),
        float(os.environ.get("SHOPIFY_PAYMENTS_FIXED", DEFAULT_PAYMENTS_FIXED)),
    )


def fee_basis(rate: float, fixed: float) -> str:
    return f"schedule estimate: {rate:.1%} + ${fixed:.2f} per order, allocated by revenue share"


def _month_bounds(day: date) -> tuple[date, date]:
    return day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1])


def group_orders(mapped: pd.DataFrame) -> dict[str, dict]:
    """Lines by order Name in file order, forward-filling the order-level
    fields the export prints on an order's first line only."""
    orders: dict[str, dict] = {}
    for record in mapped.to_dict(orient="records"):
        if not record["name"]:
            continue
        order = orders.setdefault(record["name"], {**{k: None for k in ORDER_FIELDS}, "lines": []})
        for k in ORDER_FIELDS:
            if order[k] is None and record[k] is not None:
                order[k] = record[k]
        order["lines"].append(record)
    return orders


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rate, fixed = payments_schedule()
    window_start = date.fromisoformat(upload["period_start"])
    window_end = date.fromisoformat(upload["period_end"])

    buckets: dict[tuple[str, str, str], dict] = {}
    for name, order in group_orders(mapped).items():
        status = (order["financial_status"] or "").strip().lower()
        if order["cancelled_at"] or status in DROP_STATUSES:
            continue
        created = to_iso_date(order["created_at"])
        if not created:
            continue
        day = date.fromisoformat(created)
        if not window_start <= day <= window_end:
            continue
        month_start, month_end = _month_bounds(day)
        period_start = max(month_start, window_start).isoformat()
        period_end = min(month_end, window_end).isoformat()

        lines = []
        for rec in order["lines"]:
            qty = as_int(rec["quantity"]) or 0
            sku = rec["sku"] or (f"name:{rec['line_name']}" if rec["line_name"] else None)
            if qty <= 0 or not sku:
                continue
            gross = (rec["price"] or 0.0) * qty
            lines.append((sku, qty, gross, gross - (rec["discount"] or 0.0)))
        if not lines:
            continue
        order_revenue = sum(revenue for _, _, _, revenue in lines)
        refund = max(0.0, min(order["refunded_amount"] or 0.0, order_revenue))
        for sku, qty, gross, revenue in lines:
            share = revenue / order_revenue if order_revenue > 0 else 1 / len(lines)
            b = buckets.setdefault(
                (sku, period_start, period_end),
                {"units": 0, "gross": 0.0, "revenue": 0.0, "refunds": 0.0, "orders_share": 0.0,
                 "orders": set(), "lines": 0},
            )
            b["units"] += qty
            b["gross"] += gross
            b["revenue"] += revenue
            b["refunds"] += refund * share
            b["orders_share"] += share
            b["orders"].add(name)
            b["lines"] += 1

    rows = []
    for (sku, period_start, period_end), b in sorted(buckets.items()):
        sales = b["revenue"] - b["refunds"]
        fee = -(rate * sales + fixed * b["orders_share"])
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": CHANNEL,
                "period_start": period_start,
                "period_end": period_end,
                "sku": sku,
                "asin": None,  # the products export bridges sku -> handle
                "units_sold": b["units"],
                "avg_sales_price": round(b["gross"] / b["units"], 2) if b["units"] else None,
                "sales": round(sales, 2),
                "referral_fees": round(fee, 2) or 0.0,
                "fba_fulfillment_fees": None,
                "storage_fees": None,
                "other_fees": None,
                "net_proceeds": round(sales + fee, 2),
                "raw": {
                    "orders": len(b["orders"]),
                    "lines": b["lines"],
                    "refunds": round(b["refunds"], 2),
                    "fee_basis": fee_basis(rate, fixed),
                },
            }
        )
    rows = dedupe_last(rows, ("sku", "period_start"))
    return "sku_economics", rows, "client_id,channel,sku,period_start,period_end"
