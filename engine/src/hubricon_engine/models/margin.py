"""True net margin per SKU per period, plus a simple velocity forecast.

Revenue and platform fees come from SKU Economics (Amazon) or the orders
export (Shopify); landed unit cost from the client's COGS sheet; ad spend is
allocated to SKUs proportional to revenue share within the period (v1
approximation — replace with the advertised-product report when SP-API
lands). Fee columns arrive with inconsistent signs across export versions,
so magnitudes are summed.

The arithmetic is channel-blind — a unit is a unit and a fee is a fee — and
the module takes no channel argument: where a rule differs by platform it
reads the `channel` every canonical row carries. Three things follow:

  * FULFILMENT IS COUNTED ONCE (2026-10-01). The cost sheet has one
    fulfillment_per_unit_usd column per SKU (pick, pack and postage, or a
    3PL's per-unit fee) and no channel column, because one SKU can sell on
    both platforms. So the rule is read off the sale, not the sheet: a
    Shopify sale carries the sheet's fulfilment (no Shopify export itemises
    it); an Amazon sale carries it only when Amazon charged no FBA
    fulfilment fee on the row (a merchant-fulfilled sale ships from the
    seller's own shelf or 3PL). When Amazon did charge an FBA fee, that fee
    IS the fulfilment and the sheet's figure is not added on top. Until
    2026-10-01 it was, on every channel, so a two-platform seller's 3PL cost
    landed on the Amazon margin beside the FBA fee. Unit cost, inbound
    freight, packaging and other per-unit costs belong to the unit and count
    on every channel. (A SKU sold both FBA and merchant-fulfilled in one
    month is read as FBA for that month: the export does not split it.)
  * SHOPIFY'S PROCESSING FEE IS THE ONE PAID WHEN IT IS ON FILE (2026-10-01).
    The Orders export carries no fees, so ingest/shopify_orders writes a
    labelled estimate at Shopify Payments' published 2.9% + 30¢ an order.
    When the Payouts export is on file (settlement_transactions, channel
    shopify) the margin replaces it with the rate the seller actually paid,
    fees ÷ charges, for each period the export covers, applied to that
    period's product sales before refunds: the export's refund rows carry no
    fee back, so the fee on a refunded charge stays paid. A period the export
    does not cover takes the export's whole-window rate, labelled an
    estimate. The rate is measured on Shopify Payments charges and applied to
    every sale, including any paid another way. Every margin row says which
    basis it carries in fee_split["source"] and fee_split["note"]: "export"
    (the platform's own fee lines), "payouts", "payouts_rate" (an estimate)
    or "schedule_estimate".
  * the output key stays `amazon_fees`. That is the column name in
    margin_results and it is older than the second platform; what a client
    is *told* it is called comes from channels.fee_label.
"""

import json
import re
from collections import defaultdict
from datetime import date, timedelta

from .common import num, period_days

FEE_FIELDS = ("referral_fees", "fba_fulfillment_fees", "storage_fees", "other_fees")
FORECAST_WINDOW = 3

# Which fee columns scale with the price and which do not. A referral fee is a
# percentage of the sale, so it belongs in the proportional rate f. FBA
# fulfilment is charged per unit by size and weight and does not move when the
# price does, so it belongs in the fixed per-unit term F; monthly storage is
# charged on cubic feet, which is also indifferent to price, and is allocated
# across the period's units. `other_fees` is a residual bucket whose
# composition the export does not name: it is left in the proportional rate,
# which biases the price optimum DOWN (see pricing_engine.optimal_price), the
# conservative direction.
PROPORTIONAL_FEE_FIELDS = ("referral_fees", "other_fees")
FIXED_FEE_FIELDS = ("fba_fulfillment_fees", "storage_fees")


def fee_split(row: dict, revenue: float, units: float) -> dict:
    """Split a period's fees into a proportional rate and a fixed per-unit
    charge, or say plainly that the export did not separate them.

    A channel whose export itemises fees (Amazon SKU Economics) gets
    basis "itemized". A channel that reports one blended fee line (Shopify
    Orders, whose processing fee is 2.9% of the sale plus $0.30 an order and
    arrives summed) gets basis "assumed_proportional": the whole fee is
    treated as price-proportional, which is what the engine did before this
    split existed, and the report says so.
    """
    itemized = row.get("referral_fees") is not None and any(
        row.get(f) is not None for f in FIXED_FEE_FIELDS
    )
    if not itemized or revenue <= 0 or units <= 0:
        total = sum(abs(row[f] or 0) for f in FEE_FIELDS)
        return {
            "basis": "assumed_proportional",
            "proportional_rate": num(total / revenue, 6) if revenue > 0 else None,
            "fixed_per_unit": 0.0,
            "proportional_fees": num(total),
            "fixed_fees": 0.0,
        }
    proportional = sum(abs(row.get(f) or 0) for f in PROPORTIONAL_FEE_FIELDS)
    fixed = sum(abs(row.get(f) or 0) for f in FIXED_FEE_FIELDS)
    return {
        "basis": "itemized",
        "proportional_rate": num(proportional / revenue, 6),
        "fixed_per_unit": num(fixed / units, 6),
        "proportional_fees": num(proportional),
        "fixed_fees": num(fixed),
    }


# -- landed cost: fulfilment counted once --------------------------------------

# The per-unit costs that belong to the unit wherever it sells.
UNIT_COST_FIELDS = (
    "unit_cost_usd",
    "inbound_freight_per_unit_usd",
    "packaging_per_unit_usd",
    "other_cost_per_unit_usd",
)
# Pick, pack and postage, or a 3PL's fee: counted only on a sale the platform
# did not fulfil (see the module docstring).
FULFILMENT_FIELD = "fulfillment_per_unit_usd"


def _channel(row: dict) -> str:
    return str(row.get("channel") or "amazon").lower()


def fulfilment_counted(econ_row: dict) -> bool:
    """Whether the cost sheet's fulfilment belongs on this sale: always on
    Shopify, and on Amazon only when Amazon charged no FBA fulfilment fee."""
    if _channel(econ_row) == "shopify":
        return True
    return abs(float(econ_row.get("fba_fulfillment_fees") or 0)) == 0


def landed_unit_cost(cogs_row: dict | None, econ_row: dict) -> float | None:
    """The unit's landed cost on this sale; None when the sheet has no row."""
    if not cogs_row:
        return None
    cost = sum(float(cogs_row.get(f) or 0) for f in UNIT_COST_FIELDS)
    if fulfilment_counted(econ_row):
        cost += float(cogs_row.get(FULFILMENT_FIELD) or 0)
    return cost


# -- Shopify's processing fee: the one paid, when the Payouts export is in -------

# A Payouts export "covers" a margin period when its transactions reach within
# this many days of both of the period's ends: an export whose first line is on
# the 3rd still covers the month (the 1st and 2nd may simply have had no
# charge); one that starts on the 20th does not.
PAYOUT_EDGE_SLACK_DAYS = 3


def _day(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _is_shopify_payout(row: dict) -> bool:
    ch = row.get("channel")
    return ch == "shopify" or (ch is None and _is_charge(row))


def _is_charge(row: dict) -> bool:
    return str(row.get("txn_type") or "").strip().lower() == "charge"


def payout_fee_terms(settlement_rows: list[dict] | None) -> dict | None:
    """The Payouts export as fee evidence: its window and its charges, or None
    when no Shopify charge is on file. Fees are summed as magnitudes (stored
    negative, printed positive)."""
    rows = [r for r in settlement_rows or [] if _is_shopify_payout(r) and _day(r.get("txn_date"))]
    charges = [r for r in rows if _is_charge(r) and float(r.get("product_sales") or 0) > 0]
    if not charges:
        return None
    days = sorted(_day(r["txn_date"]) for r in rows)
    fees = sum(abs(float(r.get("selling_fees") or 0)) for r in charges)
    amount = sum(float(r["product_sales"]) for r in charges)
    return {"first": days[0], "last": days[-1], "rate": fees / amount, "fees": fees, "charges": amount,
            "n": len(charges), "rows": charges}


def payout_covers(terms: dict | None, start: str, end: str) -> bool:
    """Whether the export's window spans the period, within the edge slack."""
    if not terms:
        return False
    slack = timedelta(days=PAYOUT_EDGE_SLACK_DAYS)
    return terms["first"] <= _day(start) + slack and terms["last"] >= _day(end) - slack


def period_fee_rate(terms: dict | None, start: str, end: str) -> dict | None:
    """The processing rate for one period: the period's own fees ÷ charges when
    the export covers it, else the export's whole-window rate (an estimate).
    None when there is no export."""
    if not terms:
        return None
    if payout_covers(terms, start, end):
        s, e = _day(start), _day(end)
        inside = [r for r in terms["rows"] if s <= _day(r["txn_date"]) <= e]
        amount = sum(float(r["product_sales"]) for r in inside)
        if amount > 0:
            fees = sum(abs(float(r.get("selling_fees") or 0)) for r in inside)
            n = len(inside)
            return {"source": "payouts", "rate": fees / amount, "fees": fees, "charges": amount, "n": n,
                    "note": (f"from your Payouts export: Shopify took ${fees:,.2f} on ${amount:,.2f} of charges "
                             f"in this period ({n} charge{'s' if n != 1 else ''}), {fees / amount:.2%} of each")}
    window = f"{terms['first']:%b} {terms['first'].day}, {terms['first'].year} to " \
             f"{terms['last']:%b} {terms['last'].day}, {terms['last'].year}"
    return {"source": "payouts_rate", "rate": terms["rate"], "fees": terms["fees"], "charges": terms["charges"],
            "n": terms["n"],
            "note": (f"estimate: the {terms['rate']:.2%} of each charge your Payouts export shows for {window}, "
                     f"applied to a period the export does not cover")}


def _raw(row: dict) -> dict:
    raw = row.get("raw")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _schedule_note(row: dict) -> str:
    """The estimate ingest wrote, in words: its own rate when it named one."""
    m = re.search(r"([\d.]+)% \+ \$([\d.]+)", str(_raw(row).get("fee_basis") or ""))
    rate, fixed = (m.group(1), m.group(2)) if m else ("2.9", "0.30")
    return (f"estimate: Shopify Payments' published {rate}% + ${fixed} an order, not what you paid; "
            f"your Payouts export replaces it with the fees Shopify actually took")


def _shopify_fees(row: dict, revenue: float, period_rate: dict | None) -> tuple[float, dict, dict]:
    """(fee dollars, the row as fee_split should read it, its source) for one
    Shopify margin row."""
    if period_rate is None:
        fees = sum(abs(row[f] or 0) for f in FEE_FIELDS)
        return fees, row, {"source": "schedule_estimate", "note": _schedule_note(row)}
    gross = float(revenue) + float(_raw(row).get("refunds") or 0)
    fees = period_rate["rate"] * max(gross, 0.0)
    adjusted = {**row, "referral_fees": -fees, "fba_fulfillment_fees": None, "storage_fees": None,
                "other_fees": None}
    return fees, adjusted, {"source": period_rate["source"], "note": period_rate["note"],
                            "effective_rate": num(period_rate["rate"], 6)}


def _split_of(row: dict) -> dict:
    split = row.get("fee_split") or {}
    if isinstance(split, str):
        try:
            split = json.loads(split)
        except ValueError:
            return {}
    return split if isinstance(split, dict) else {}


def fee_basis_line(margins: list[dict]) -> str | None:
    """One sentence for a Shopify read: where the latest period's processing
    fees came from. None for a read whose fees are the platform's own fee
    lines (Amazon), which need no caveat."""
    if not margins:
        return None
    latest = max(str(m["period_start"]) for m in margins)
    by_source: dict = {}
    for m in margins:
        if str(m["period_start"]) == latest:
            split = _split_of(m)
            by_source.setdefault(split.get("source"), split)
    d = _day(latest)
    month = f"{d:%B} {d.year}" if d else latest
    if "payouts" in by_source:
        rate = by_source["payouts"].get("effective_rate")
        return ("The Shopify fees in this read are the ones you paid, from your Payouts export"
                + (f": {float(rate):.2%} of each charge in {month}." if rate is not None else "."))
    if "payouts_rate" in by_source:
        how = str(by_source["payouts_rate"].get("note") or "").removeprefix("estimate: ")
        return (f"The Shopify fees for {month} are an estimate: {how}. A Payouts export that covers {month} "
                f"replaces it with the fees you paid.")
    if "schedule_estimate" in by_source:
        return ("The Shopify fees in this read are an estimate at Shopify Payments' published 2.9% + 30¢ an "
                "order (the Basic-plan card rate), not what you paid. Send your Payouts export and the next read "
                "uses the fees Shopify actually took.")
    return None


def _period_ad_spend(data: dict, start: str, end: str) -> float:
    daily = [
        r["spend"] or 0
        for r in data["ppc_spend"]
        if start <= r["report_date"] <= end
    ]
    if daily:
        return float(sum(daily))
    total = 0.0
    for row in data["ppc_search_terms"]:
        overlap_days = (
            (min(date.fromisoformat(end), date.fromisoformat(row["period_end"]))
             - max(date.fromisoformat(start), date.fromisoformat(row["period_start"]))).days + 1
        )
        if overlap_days <= 0:
            continue
        share = overlap_days / period_days(row["period_start"], row["period_end"])
        total += (row["spend"] or 0) * share
    return total


def run(data: dict, rng=None, simulations=None) -> list[dict]:
    cogs_by_sku = {r["sku"]: r for r in data["cogs_inputs"]}
    by_period: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in data["sku_economics"]:
        by_period[(row["period_start"], row["period_end"])].append(row)
    payouts = payout_fee_terms(data.get("settlement_transactions"))

    history: dict[str, list[tuple[str, int]]] = defaultdict(list)
    results = []
    for (start, end), rows in sorted(by_period.items()):
        ad_total = _period_ad_spend(data, start, end)
        revenue_total = sum(r["sales"] or 0 for r in rows)
        period_rate = period_fee_rate(payouts, str(start), str(end))
        for row in rows:
            revenue = row["sales"] or 0
            units = row["units_sold"] or 0
            if _channel(row) == "shopify":
                fees, split_row, source = _shopify_fees(row, revenue, period_rate)
            else:
                fees = sum(abs(row[f] or 0) for f in FEE_FIELDS)
                split_row, source = row, {"source": "export", "note": "the fee lines in the platform's own export"}
            unit_cost = landed_unit_cost(cogs_by_sku.get(row["sku"]), row)
            cogs_total = units * unit_cost if unit_cost is not None else None
            ads = ad_total * (revenue / revenue_total) if revenue_total > 0 else 0.0
            net = revenue - fees - (cogs_total or 0) - ads
            history[row["sku"]].append((start, units))
            results.append(
                {
                    "sku": row["sku"],
                    "asin": row["asin"],
                    "period_start": start,
                    "period_end": end,
                    "units": units,
                    "revenue": num(revenue),
                    "amazon_fees": num(fees),
                    "fee_split": {**fee_split(split_row, float(revenue), float(units)), **source},
                    "cogs": num(cogs_total),
                    "ad_spend_allocated": num(ads),
                    "net_margin": num(net),
                    "net_margin_pct": num(net / revenue, 4) if revenue > 0 else None,
                }
            )

    # naive velocity forecast: recent average plus per-period trend
    for row in results:
        series = [u for _, u in sorted(history[row["sku"]])]
        if row["period_start"] != max(p for p, _ in history[row["sku"]]):
            continue  # forecast only on each SKU's latest period row
        recent = series[-FORECAST_WINDOW:]
        trend = (series[-1] - series[0]) / (len(series) - 1) if len(series) >= 2 else 0.0
        row["forecast"] = {
            "next_period_units": num(max(0.0, sum(recent) / len(recent) + trend), 1),
            "method": f"mean of last {len(recent)} periods + linear trend",
            "observed_periods": len(series),
        }
    return results


def average_margin(results: list[dict]) -> float | None:
    """Revenue-weighted contribution margin across everything — feeds the
    ad-efficiency break-even threshold."""
    revenue = sum(r["revenue"] or 0 for r in results)
    net = sum(r["net_margin"] or 0 for r in results)
    # Nullable column, and callers pass margin rows from several places (a run,
    # a chart pack, a fixture) — an absent allocation is zero, not a crash.
    ads = sum(r.get("ad_spend_allocated") or 0 for r in results)
    if revenue <= 0:
        return None
    # margin before ad spend: ads are the lever being evaluated
    return (net + ads) / revenue
