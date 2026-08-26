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


def compute_alerts(current_inventory, previous_inventory, margin_rows, price_tests) -> list[dict]:
    return (
        buybox_alerts(price_tests)
        + stockout_alerts(current_inventory, previous_inventory)
        + margin_flip_alerts(margin_rows)
    )


def dedupe(new_alerts: list[dict], recent_messages: set[str]) -> list[dict]:
    """Drop alerts whose exact message already fired inside the window."""
    return [a for a in new_alerts if a["message"] not in recent_messages]
