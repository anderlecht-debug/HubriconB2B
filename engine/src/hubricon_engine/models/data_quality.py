"""Garbage in: does the client's data agree with itself, and is it all there?

Every model above reads the exports as truth. Three things can make that
truth wrong before any estimator touches it: two exports that should say the
same thing and do not (a SKU Economics month whose sales differ from the
settlement file's orders by a fifth), a month that is simply missing from one
report, and a report nobody has refreshed since spring. None of those is a
modelling error, and every one of them lands in a directive if nothing
catches it. This module catches them and says which.

RECONCILIATION. Per calendar period, pairs of sources that measure the same
quantity two ways:

  sales      SKU Economics `sales`  vs  settlement Order `product_sales`
  sales      SKU Economics `sales`  vs  Business Report `ordered_product_sales`
  units      SKU Economics `units_sold`  vs  inventory-ledger Shipments
  ad spend   daily campaign spend  vs  search-term spend, over the same window

Each pair reports the relative gap |a − b| / max(a, b) and flags it above
RECONCILE_TOLERANCE. A gap is a fact about the exports, not a verdict on
which is right; the row names both figures.

COVERAGE AND STALENESS. Per report type, the calendar months present between
its first and last, the months missing, and the days since its latest period
ended against today. A report stale past STALE_DAYS is flagged.

WHAT IT DOES. Nothing to the numbers — this module never corrects a figure.
It publishes flags; every model payload that read a flagged source carries
`data_quality_flags`, the health score's signal sub-score subtracts for a
failed reconciliation the way it already subtracts for an unforecastable
catalogue, and the memo names the worst gap. A client who sees "your SKU
Economics and your settlement file disagree by 18% for July" can fix the
upload; a directive built on the wrong one of them could not be un-issued.

CONTAMINATED MONTHS (added 2026-09-24). A month can agree with every other
export and still lie to a price fit. Two patterns the exports themselves
reveal:

  stockout   the Business Report's Buy Box share for the SKU's ASIN falls
             below STOCKOUT_BUYBOX_RATIO of the SKU's own median — the
             listing was unbuyable part of the month, so the units are
             censored, and a seller who raised the price as stock ran out
             hands the fit a high price beside low units: elasticity reads
             steeper than it is
  promotion  the settlement file's promotional rebates reach PROMO_SHARE of
             the SKU's product sales in the month — a deal or coupon whose
             placement lifted units by more than the price explains:
             elasticity reads steeper again

Plus two row-level faults: the same SKU-period twice (a re-upload), and a
period whose length differs from the export's usual one (a month sent as two
half-months). `contaminated_periods` returns the SKU-months to leave out of
every price-response fit; `clean_for_fitting` returns the exports with them
removed and duplicates collapsed. Both are pure functions of the data, so a
fit reads the same cleaned history whoever calls it. Measured on the
Simons–Thorp–Griffin bench's dirty world (MATH_SCORECARD.md, iteration 38):
24 stockout months and 16 deal months across 160 SKUs. On the three test
seeds the catalogue's median elasticity error went from −0.26 / −0.17 / −0.06
at the baseline to −0.16 / −0.02 / +0.10 with every correction of that
iteration in place (−0.04 to +0.06 on three further seeds): inside three of
the engine's own stated common error each time, not inside ±0.1 as this
paragraph said when it was first written.

WHAT IT CANNOT TELL YOU. Which of two disagreeing exports is right; whether a
missing month was a month with no sales or a month nobody uploaded (the
payload says "missing", never "zero"); anything about a report type the
client has never uploaded.
"""

from datetime import date

import numpy as np

from .common import num, period_days

RECONCILE_TOLERANCE = 0.05
STALE_DAYS = 45
STOCKOUT_BUYBOX_RATIO = 0.75     # a month's Buy Box share under this share of the SKU's own median
STOCKOUT_MIN_MEDIAN_BUYBOX = 50.0  # a SKU that rarely holds the Buy Box is not judged by it
PROMO_SHARE = 0.05               # promotional rebates as a share of the month's product sales
IRREGULAR_PERIOD_DAYS = 5        # period length this far from the export's usual one
# Amazon settlement rows post at shipment and Business Report periods are the
# order date, so a month-edge slice of orders sits in the neighbouring month;
# under this many days of period the pair is not compared
MIN_PERIOD_DAYS_FOR_RECONCILE = 14
PAIRS = (
    ("sales", "sku_economics", "settlement_transactions"),
    ("sales", "sku_economics", "asin_traffic"),
    ("units", "sku_economics", "inventory_ledger"),
    ("ad_spend", "ppc_spend", "ppc_search_terms"),
)


def _periods(rows: list[dict]) -> list[tuple[str, str]]:
    return sorted({(str(r["period_start"]), str(r["period_end"])) for r in rows
                   if r.get("period_start") and r.get("period_end")})


def _month_of(d: str) -> str:
    return str(d)[:7]


def _sum_in(rows, start, end, date_key, value_key, where=None) -> float | None:
    total, n = 0.0, 0
    for r in rows:
        d = str(r.get(date_key) or "")[:10]
        if not d or not (start <= d <= end):
            continue
        if where and not where(r):
            continue
        total += float(r.get(value_key) or 0)
        n += 1
    return total if n else None


def reconcile(data: dict) -> list[dict]:
    econ = data.get("sku_economics") or []
    out = []
    for start, end in _periods(econ):
        if period_days(start, end) < MIN_PERIOD_DAYS_FOR_RECONCILE:
            continue
        econ_sales = sum(float(r.get("sales") or 0) for r in econ if str(r["period_start"]) == start)
        econ_units = sum(float(r.get("units_sold") or 0) for r in econ if str(r["period_start"]) == start)
        settle = _sum_in(data.get("settlement_transactions") or [], start, end, "txn_date", "product_sales",
                         where=lambda r: (r.get("txn_type") or "").strip().lower() == "order")
        traffic = [r for r in (data.get("asin_traffic") or []) if str(r.get("period_start")) == start]
        traffic_sales = sum(float(r.get("ordered_product_sales") or 0) for r in traffic) if traffic else None
        shipped = _sum_in(data.get("inventory_ledger") or [], start, end, "event_date", "quantity",
                          where=lambda r: "ship" in (r.get("event_type") or "").lower())
        shipped = abs(shipped) if shipped is not None else None
        for label, a_name, b_name, a, b in (
                ("sales", "sku_economics", "settlement_transactions", econ_sales, settle),
                ("sales", "sku_economics", "asin_traffic", econ_sales, traffic_sales),
                ("units", "sku_economics", "inventory_ledger", econ_units, shipped)):
            if a is None or b is None or max(abs(a), abs(b)) <= 0:
                continue
            gap = abs(a - b) / max(abs(a), abs(b))
            out.append({"period_start": start, "period_end": end, "quantity": label, "a": a_name, "b": b_name,
                        "a_value": num(a), "b_value": num(b), "relative_gap": num(gap, 4),
                        "flagged": bool(gap > RECONCILE_TOLERANCE)})
    # ad spend: daily file vs search-term totals over each search-term window
    ppc = data.get("ppc_spend") or []
    for start, end in _periods(data.get("ppc_search_terms") or []):
        term_spend = sum(float(r.get("spend") or 0) for r in data["ppc_search_terms"]
                         if str(r["period_start"]) == start)
        daily = _sum_in(ppc, start, end, "report_date", "spend")
        if daily is None or max(term_spend, daily) <= 0:
            continue
        gap = abs(term_spend - daily) / max(term_spend, daily)
        out.append({"period_start": start, "period_end": end, "quantity": "ad_spend", "a": "ppc_spend",
                    "b": "ppc_search_terms", "a_value": num(daily), "b_value": num(term_spend),
                    "relative_gap": num(gap, 4), "flagged": bool(gap > RECONCILE_TOLERANCE)})
    return out


def coverage(data: dict, today: date) -> dict:
    """Per report type: months present, months missing inside the span, and
    days since the latest period ended."""
    spec = {"sku_economics": ("period_start", "period_end"), "asin_traffic": ("period_start", "period_end"),
            "ppc_search_terms": ("period_start", "period_end"), "ppc_spend": ("report_date", "report_date"),
            "settlement_transactions": ("txn_date", "txn_date"), "inventory_levels": ("snapshot_date", "snapshot_date"),
            "inventory_health": ("snapshot_date", "snapshot_date"), "inventory_ledger": ("event_date", "event_date"),
            "fba_returns": ("return_date", "return_date"), "fba_reimbursements": ("approval_date", "approval_date"),
            "customer_orders": ("order_date", "order_date")}
    out = {}
    for table, (start_key, end_key) in spec.items():
        rows = data.get(table) or []
        months = sorted({_month_of(r.get(start_key)) for r in rows if r.get(start_key)})
        if not months:
            out[table] = {"present": False}
            continue
        first, last = months[0], months[-1]
        y, m = int(first[:4]), int(first[5:7])
        span = []
        while f"{y:04d}-{m:02d}" <= last:
            span.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        missing = [x for x in span if x not in months]
        latest_end = max(str(r.get(end_key) or r.get(start_key))[:10] for r in rows if r.get(start_key))
        stale_days = (today - date.fromisoformat(latest_end)).days
        out[table] = {"present": True, "months": len(months), "first": first, "last": last, "missing_months": missing,
                      "latest": latest_end, "days_since_latest": stale_days, "stale": bool(stale_days > STALE_DAYS)}
    return out


def contaminated_periods(data: dict) -> dict[str, dict[str, str]]:
    """{sku: {period_start: "stockout" | "promotion"}} for the SKU-months a
    price-response fit should not read."""
    econ = data.get("sku_economics") or []
    asin_of = {}
    periods_of: dict[str, list[tuple[str, str]]] = {}
    for r in econ:
        if r.get("sku") and r.get("period_start") and r.get("period_end"):
            if r.get("asin"):
                asin_of.setdefault(r["sku"], r["asin"])
            periods_of.setdefault(r["sku"], []).append((str(r["period_start"])[:10], str(r["period_end"])[:10]))
    out: dict[str, dict[str, str]] = {}
    # stockouts, from the Business Report's Buy Box share
    by_asin: dict[str, list[dict]] = {}
    for t in data.get("asin_traffic") or []:
        if t.get("child_asin") and t.get("buy_box_pct") is not None and t.get("period_start"):
            by_asin.setdefault(t["child_asin"], []).append(t)
    for sku, asin in asin_of.items():
        rows = by_asin.get(asin) or []
        if len(rows) < 3:
            continue
        med = float(np.median([float(t["buy_box_pct"]) for t in rows]))
        if med < STOCKOUT_MIN_MEDIAN_BUYBOX:
            continue
        for t in rows:
            if float(t["buy_box_pct"]) < STOCKOUT_BUYBOX_RATIO * med:
                out.setdefault(sku, {})[str(t["period_start"])[:10]] = "stockout"
    # promotions, from the settlement file's rebates
    promo: dict[tuple[str, str], list[float]] = {}
    for t in data.get("settlement_transactions") or []:
        if (t.get("txn_type") or "").strip().lower() != "order" or not t.get("sku") or not t.get("txn_date"):
            continue
        day = str(t["txn_date"])[:10]
        for start, end in periods_of.get(t["sku"], []):
            if start <= day <= end:
                acc = promo.setdefault((t["sku"], start), [0.0, 0.0])
                acc[0] += -float(t.get("promotional_rebates") or 0.0)
                acc[1] += float(t.get("product_sales") or 0.0)
                break
    for (sku, start), (rebates, sales) in promo.items():
        if sales > 0 and rebates / sales >= PROMO_SHARE:
            out.setdefault(sku, {}).setdefault(start, "promotion")
    return out


def duplicate_rows(data: dict) -> list[tuple[str, str]]:
    seen, dups = set(), []
    for r in data.get("sku_economics") or []:
        key = (r.get("sku"), str(r.get("period_start")), str(r.get("period_end")))
        if key in seen:
            dups.append((key[0], key[1]))
        seen.add(key)
    return dups


def clean_for_fitting(data: dict) -> tuple[dict, dict]:
    """The exports a price-response fit should read: contaminated SKU-months
    removed, duplicated SKU-periods collapsed to their last row. Returns
    (data, notes) — the input untouched when nothing is found."""
    bad = contaminated_periods(data)
    dups = duplicate_rows(data)
    if not bad and not dups:
        return data, {"excluded": {}, "duplicates": 0}
    kept: dict[tuple, dict] = {}
    for r in data.get("sku_economics") or []:
        if str(r.get("period_start"))[:10] in bad.get(r.get("sku"), {}):
            continue
        kept[(r.get("sku"), str(r.get("period_start")), str(r.get("period_end")))] = r
    asin_bad = set()
    for r in data.get("sku_economics") or []:
        if r.get("asin") and str(r.get("period_start"))[:10] in bad.get(r.get("sku"), {}):
            asin_bad.add((r["asin"], str(r["period_start"])[:10]))
    traffic = [t for t in data.get("asin_traffic") or []
               if (t.get("child_asin"), str(t.get("period_start"))[:10]) not in asin_bad]
    return ({**data, "sku_economics": list(kept.values()), "asin_traffic": traffic},
            {"excluded": bad, "duplicates": len(dups)})


def row_faults(data: dict) -> dict:
    """Row-level faults: duplicates, SKUs selling with no landed cost, and
    periods whose length is off the export's usual one."""
    econ = data.get("sku_economics") or []
    lengths = [period_days(str(r["period_start"]), str(r["period_end"])) for r in econ
               if r.get("period_start") and r.get("period_end")]
    usual = float(np.median(lengths)) if lengths else None
    irregular = sorted({(r["sku"], str(r["period_start"])) for r in econ
                        if usual and r.get("period_start") and r.get("period_end")
                        and abs(period_days(str(r["period_start"]), str(r["period_end"])) - usual) > IRREGULAR_PERIOD_DAYS})
    costed = {c.get("sku") for c in data.get("cogs_inputs") or [] if c.get("unit_cost_usd") is not None}
    selling = {r["sku"] for r in econ if float(r.get("units_sold") or 0) > 0}
    no_cost = sorted(selling - costed) if data.get("cogs_inputs") else []
    return {"duplicates": duplicate_rows(data), "irregular_periods": irregular, "no_landed_cost": no_cost}


def run(data: dict, today: date | None = None) -> dict:
    today = today or date.today()
    rec = reconcile(data)
    cov = coverage(data, today)
    failed = [r for r in rec if r["flagged"]]
    gaps = {t: c["missing_months"] for t, c in cov.items() if c.get("present") and c.get("missing_months")}
    stale = [t for t, c in cov.items() if c.get("stale")]
    contaminated = contaminated_periods(data)
    faults = row_faults(data)
    flags = {}
    n_stockout = sum(1 for v in contaminated.values() for why in v.values() if why == "stockout")
    n_promo = sum(1 for v in contaminated.values() for why in v.values() if why == "promotion")
    if n_stockout:
        flags.setdefault("asin_traffic", set()).add(f"stockout_suspected:{n_stockout} SKU-months")
    if n_promo:
        flags.setdefault("settlement_transactions", set()).add(f"promotion:{n_promo} SKU-months")
    if faults["duplicates"]:
        flags.setdefault("sku_economics", set()).add(f"duplicate_rows:{len(faults['duplicates'])}")
    if faults["irregular_periods"]:
        flags.setdefault("sku_economics", set()).add(f"irregular_period:{len(faults['irregular_periods'])}")
    if faults["no_landed_cost"]:
        flags.setdefault("cogs_inputs", set()).add(f"no_landed_cost:{len(faults['no_landed_cost'])} SKUs")
    for r in failed:
        for t in (r["a"], r["b"]):
            flags.setdefault(t, set()).add(f"reconciliation:{r['quantity']}:{r['period_start']}")
    for t, months in gaps.items():
        flags.setdefault(t, set()).add(f"missing_months:{','.join(months[:3])}{'…' if len(months) > 3 else ''}")
    for t in stale:
        flags.setdefault(t, set()).add(f"stale:{cov[t]['days_since_latest']}d")
    worst = max(failed, key=lambda r: r["relative_gap"]) if failed else None
    status = "ok" if not (failed or gaps or stale or contaminated or any(faults.values())) else "flags"
    if not any(c.get("present") for c in cov.values()):
        status = "insufficient_data"
    return {
        "status": status, "as_of": today.isoformat(),
        "reconciliation": rec, "n_reconciled": len(rec), "n_failed": len(failed),
        "coverage": cov, "gaps": gaps, "stale": stale,
        "contaminated": contaminated, "row_faults": {k: v[:50] for k, v in faults.items()},
        "flags": {t: sorted(v) for t, v in flags.items()},
        "worst_gap": ({"quantity": worst["quantity"], "period": worst["period_start"], "a": worst["a"], "b": worst["b"],
                       "a_value": worst["a_value"], "b_value": worst["b_value"], "relative_gap": worst["relative_gap"]}
                      if worst else None),
        "basis": (f"{len(rec)} source pairs reconciled at a {RECONCILE_TOLERANCE:.0%} tolerance, {len(failed)} failed; "
                  f"{sum(len(v) for v in gaps.values())} missing month(s) across {len(gaps)} report(s); "
                  f"{len(stale)} report(s) older than {STALE_DAYS} days"),
    }


def flags_for(dq: dict | None, *tables: str) -> list[str]:
    """The flags a model should carry for the sources it read."""
    if not dq or dq.get("status") in ("ok", "insufficient_data", None):
        return []
    out = []
    for t in tables:
        out += [f"{t}: {f}" for f in (dq.get("flags") or {}).get(t, [])]
    return out
