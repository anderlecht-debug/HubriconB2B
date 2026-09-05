"""True net margin per SKU per period, plus a simple velocity forecast.

Revenue and platform fees come from SKU Economics (Amazon) or the orders
export (Shopify); landed unit cost from the client's COGS sheet; ad spend is
allocated to SKUs proportional to revenue share within the period (v1
approximation — replace with the advertised-product report when SP-API
lands). Fee columns arrive with inconsistent signs across export versions,
so magnitudes are summed.

The arithmetic is channel-blind — a unit is a unit and a fee is a fee — so
this module takes no channel. Two things follow from that:

  * landed unit cost sums fulfillment_per_unit_usd alongside freight,
    packaging and the rest (2026-09-04). A Shopify store's pick, pack and
    postage is a real per-unit cost no export itemises; an Amazon seller
    leaves the column blank because FBA fees already arrive as fees.
  * the output key stays `amazon_fees`. That is the column name in
    margin_results and it is older than the second platform; what a client
    is *told* it is called comes from channels.fee_label.
"""

from collections import defaultdict
from datetime import date

from .common import num, period_days

FEE_FIELDS = ("referral_fees", "fba_fulfillment_fees", "storage_fees", "other_fees")
FORECAST_WINDOW = 3


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

    history: dict[str, list[tuple[str, int]]] = defaultdict(list)
    results = []
    for (start, end), rows in sorted(by_period.items()):
        ad_total = _period_ad_spend(data, start, end)
        revenue_total = sum(r["sales"] or 0 for r in rows)
        for row in rows:
            revenue = row["sales"] or 0
            fees = sum(abs(row[f] or 0) for f in FEE_FIELDS)
            units = row["units_sold"] or 0
            cogs_row = cogs_by_sku.get(row["sku"])
            unit_cost = (
                sum(
                    cogs_row.get(f) or 0
                    for f in (
                        "unit_cost_usd",
                        "inbound_freight_per_unit_usd",
                        "packaging_per_unit_usd",
                        "fulfillment_per_unit_usd",
                        "other_cost_per_unit_usd",
                    )
                )
                if cogs_row
                else None
            )
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
