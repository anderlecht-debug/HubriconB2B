"""The always-on layer's brain: turns model output into alerts worth waking
someone for. Factual model reads only — directives stay operator-gated.

Spam discipline: an alert fires when a condition is NEW (just crossed a
threshold) or has meaningfully worsened since the previous run, and an
identical message within the dedupe window is never re-sent.
"""

STOCKOUT_WARNING = 0.25
STOCKOUT_CRITICAL = 0.50
STOCKOUT_WORSENED = 0.10   # re-alert only if probability rose this much
BUYBOX_DROP_ALERT = 10.0   # percentage points, matches price_tests warning
CASH_RUIN_WARNING = 0.05   # mirror cashflow.RUIN_WARNING / RUIN_CRITICAL
CASH_RUIN_CRITICAL = 0.15
DEDUPE_DAYS = 14


def _sku_probs(inventory_rows: list[dict]) -> dict[str, float]:
    return {
        r["sku"]: float(r["stockout_probability"] or 0)
        for r in inventory_rows
        if r.get("stockout_probability") is not None
    }


def stockout_alerts(current_inventory: list[dict], previous_inventory: list[dict]) -> list[dict]:
    prev = _sku_probs(previous_inventory)
    alerts = []
    for row in current_inventory:
        p = float(row["stockout_probability"] or 0)
        if p < STOCKOUT_WARNING:
            continue
        p_before = prev.get(row["sku"], 0.0)
        newly_crossed = p_before < STOCKOUT_WARNING
        worsened = p - p_before >= STOCKOUT_WORSENED
        if not (newly_crossed or worsened):
            continue
        alerts.append({
            "severity": "critical" if p >= STOCKOUT_CRITICAL else "warning",
            "module": "inventory",
            "message": (
                f"{row['sku']}: {p:.0%} chance of stockout before a replenishment lands "
                f"(lead time {row['lead_time_days']}d). Suggested order: {row['reorder_qty']} units."
            ),
        })
    return alerts


def margin_flip_alerts(margin_rows: list[dict]) -> list[dict]:
    """A SKU whose net margin turned negative in the latest period after
    being positive the period before."""
    periods = sorted({r["period_start"] for r in margin_rows})
    if len(periods) < 2:
        return []
    latest, prior = periods[-1], periods[-2]
    by_period = {
        p: {r["sku"]: float(r["net_margin"]) for r in margin_rows
            if r["period_start"] == p and r["net_margin"] is not None}
        for p in (latest, prior)
    }
    alerts = []
    for sku, net in by_period[latest].items():
        if net < 0 and by_period[prior].get(sku, 0) >= 0:
            alerts.append({
                "severity": "warning",
                "module": "margin",
                "message": (
                    f"{sku} flipped to a loss last period: net -${abs(net):,.0f} after fees, "
                    f"COGS and ads. It was profitable the period before."
                ),
            })
    return alerts


def buybox_alerts(price_tests: list[dict]) -> list[dict]:
    alerts = []
    for t in price_tests:
        if t["status"] != "running":
            continue
        before, during = t.get("buy_box_share_before"), t.get("buy_box_share_during")
        if before is None or during is None:
            continue
        drop = float(before) - float(during)
        if drop >= BUYBOX_DROP_ALERT:
            alerts.append({
                "severity": "critical",
                "module": "pricing",
                "message": (
                    f"Price test on {t['sku']}: Buy Box share dropped {drop:.0f} points "
                    f"({float(before):.0f}% → {float(during):.0f}%) — Amazon is suppressing the "
                    f"Featured Offer at ${float(t['test_price']):.2f}. Consider stepping back."
                ),
            })
    return alerts


def cash_alerts(cash_row: dict | None) -> list[dict]:
    """Ruin-probability crossing from the cash-horizon model. Numbers are
    coarsened (nearest 5 points, week not day) so the message-level dedupe
    can actually suppress an unchanged condition."""
    from datetime import date, timedelta

    if not cash_row:
        return []
    p = float(cash_row["p_ruin"] or 0)
    if p < CASH_RUIN_WARNING:
        return []
    pct = max(5, int(round(p * 20) * 5))
    pinch = date.today() + timedelta(days=int(cash_row.get("min_p5_day") or 0))
    week = (pinch - timedelta(days=pinch.weekday())).strftime("%b %d")
    return [{
        "severity": "critical" if p >= CASH_RUIN_CRITICAL else "warning",
        "module": "cash",
        "message": (
            f"Cash horizon: roughly {pct}% of simulated paths dip below $0 inside "
            f"{cash_row['horizon_days']} days — tightest stretch the week of {week}. "
            f"Options before then: shift a PO wire, trim ad spend, or line up bridge capital."
        ),
    }]


def compute_alerts(current_inventory, previous_inventory, margin_rows, price_tests,
                   cash_row=None) -> list[dict]:
    return (
        cash_alerts(cash_row)
        + buybox_alerts(price_tests)
        + stockout_alerts(current_inventory, previous_inventory)
        + margin_flip_alerts(margin_rows)
    )


def dedupe(new_alerts: list[dict], recent_messages: set[str]) -> list[dict]:
    """Drop alerts whose exact message already fired inside the window."""
    return [a for a in new_alerts if a["message"] not in recent_messages]
