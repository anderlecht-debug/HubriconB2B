"""The always-on layer's brain: turns model output into alerts worth waking
someone for. Factual model reads only — directives stay operator-gated.

Spam discipline: an alert fires when a condition is NEW (just crossed a
threshold) or has meaningfully worsened since the previous run, and an
identical message within the dedupe window is never re-sent.
"""

from . import channels

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


RECOVERY_EXPIRING_MIN = 100.0   # dollars closing inside the window
RECOVERY_LIVE_MIN = 500.0
ANOMALY_ALERT_MIN = 100.0       # dollars per period
HEALTH_DROP_ALERT = 8.0         # points between sweeps
ANOMALY_LABELS = {
    "fee_per_unit": "Amazon fees per unit", "fba_fee_per_unit": "FBA fee per unit",
    "referral_rate": "referral fee rate", "storage_fee": "storage fee", "monthly_total": "monthly charges",
    "sessions": "traffic", "unit_session_pct": "conversion", "buy_box_pct": "Buy Box share", "spend": "daily ad spend",
}


def anomaly_labels(channel: str | None = "amazon") -> dict:
    """The metric labels with the platform named: a Shopify brand's fee line
    is Shopify Payments, not Amazon. The FBA/referral/Buy Box metrics only
    ever come from Amazon data, so their labels stand."""
    return {**ANOMALY_LABELS, "fee_per_unit": f"{channels.fee_label(channel)} per unit"}


def _round_to(v: float, step: float) -> float:
    return round(float(v) / step) * step


def recovery_alerts(recovery: dict | None) -> list[dict]:
    """Coarsened to the nearest $50/$100 so an unchanged condition dedupes."""
    if not recovery or recovery.get("status") != "ok":
        return []
    s = recovery["summary"]
    alerts = []
    if s["n_expiring"] and float(s["expiring_value"] or 0) >= RECOVERY_EXPIRING_MIN:
        alerts.append({
            "severity": "warning", "module": "recovery",
            "message": (
                f"{s['n_expiring']} reimbursement claim{'s' if s['n_expiring'] != 1 else ''} worth about "
                f"${_round_to(s['expiring_value'], 50):,.0f} close within two weeks — filing now, not at month-end."
            ),
        })
    if s["n_live"] and float(s["live_value"] or 0) >= RECOVERY_LIVE_MIN:
        alerts.append({
            "severity": "info", "module": "recovery",
            "message": (
                f"Reconciliation found {s['n_live']} open reimbursement claim{'s' if s['n_live'] != 1 else ''} — "
                f"about ${_round_to(s['live_value'], 100):,.0f} at face value, "
                f"${_round_to(s['live_ev'], 100):,.0f} expected after approval odds."
            ),
        })
    return alerts


def anomaly_alerts(anomaly_rows: list[dict] | None, channel: str | None = "amazon") -> list[dict]:
    labels = anomaly_labels(channel)
    seen, alerts = set(), []
    for r in sorted((r for r in anomaly_rows or [] if r.get("flagged")),
                    key=lambda r: r.get("dollar_impact") or 0, reverse=True):
        key = (r.get("scope"), r.get("item_id"), r.get("metric"))
        if key in seen:
            continue
        adverse_up = r["metric"] in ("fee_per_unit", "fba_fee_per_unit", "referral_rate", "storage_fee", "spend", "monthly_total")
        if (adverse_up and r.get("direction") != "up") or (not adverse_up and r.get("direction") != "down"):
            continue
        impact = float(r.get("dollar_impact") or 0)
        if r["metric"] != "buy_box_pct" and impact < ANOMALY_ALERT_MIN:
            continue
        seen.add(key)
        since = str(r["since"])[:7] if r.get("since") else "recently"
        pct = abs(float(r.get("delta_pct") or 0)) * 100
        label = labels.get(r["metric"], r["metric"])
        alerts.append({
            "severity": "critical" if r["metric"] == "buy_box_pct" else "warning",
            "module": "anomaly",
            "message": (
                f"{label[0].upper() + label[1:]} on {r['item_id']} moved {r.get('direction')} "
                f"{pct:.0f}% since {since}"
                + (f" — about ${_round_to(impact, 10):,.0f} per period." if impact else ".")
            ),
        })
    return alerts


def health_alerts(health: dict | None, previous_health: dict | None) -> list[dict]:
    if not health or not previous_health:
        return []
    if health.get("status") != "ok" or previous_health.get("status") != "ok":
        return []
    drop = float(previous_health["score"]) - float(health["score"])
    if drop < HEALTH_DROP_ALERT:
        return []
    top = (health.get("top_drivers") or [{}])[0]
    driver = f" Largest deduction now: {top['label'].lower()} (${float(top.get('dollars_at_stake') or 0):,.0f})." if top else ""
    return [{
        "severity": "warning", "module": "system",
        "message": f"Health Score fell from {float(previous_health['score']):.0f} to {float(health['score']):.0f} since the last sweep.{driver}",
    }]


def compute_alerts(current_inventory, previous_inventory, margin_rows, price_tests,
                   cash_row=None, recovery=None, anomaly_rows=None, health=None,
                   previous_health=None, channel: str | None = "amazon") -> list[dict]:
    return (
        cash_alerts(cash_row)
        + buybox_alerts(price_tests)
        + recovery_alerts(recovery)
        + anomaly_alerts(anomaly_rows, channel)
        + health_alerts(health, previous_health)
        + stockout_alerts(current_inventory, previous_inventory)
        + margin_flip_alerts(margin_rows)
    )


def dedupe(new_alerts: list[dict], recent_messages: set[str]) -> list[dict]:
    """Drop alerts whose exact message already fired inside the window."""
    return [a for a in new_alerts if a["message"] not in recent_messages]
