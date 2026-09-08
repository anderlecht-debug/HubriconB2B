"""Speed to value, as a number rather than an impression.

welcome.html: "your written Profit Teardown is in your desk within 24 hours"
of the exports landing. The operator kept that promise on its next hourly
pass, usually, and nothing recorded whether it had. Three set-once
timestamps on the client row — exports landed, Issue 001 out, first measured
or recovered dollar — turn it into a line in the digest and a row in the
promise check that can actually fail.

The promise is Issue 001 inside 24 hours. Time to the first *dollar* is
reported beside it and never promised: a reimbursement pays when Amazon pays
it, and a price step is measured from the client's next export.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median

SLA_HOURS = 24


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def hours(a, b) -> float | None:
    x, y = _parse(a), _parse(b)
    if not x or not y:
        return None
    return round((y - x).total_seconds() / 3600, 1)


def set_once(db, client: dict, column: str, when: datetime | None = None) -> bool:
    """Write the timestamp only if the row still has none. Returns True when
    this call was the one that set it."""
    if client.get(column):
        return False
    stamp = (when or datetime.now(timezone.utc)).isoformat()
    db.table("clients").update({column: stamp}).eq("id", client["id"]).is_(column, "null").execute()
    client[column] = stamp
    return True


def breaches(clients: list[dict], now: datetime | None = None, sla_h: float = SLA_HOURS) -> list[dict]:
    """Clients whose exports landed, who have no Issue 001, and who have waited
    longer than the promise allows."""
    now = now or datetime.now(timezone.utc)
    out = []
    for c in clients:
        landed = _parse(c.get("exports_landed_at"))
        if not landed or c.get("first_issue_at"):
            continue
        waited = round((now - landed).total_seconds() / 3600, 1)
        if waited > sla_h:
            out.append({"client": c, "hours": waited})
    return out


def summary(clients: list[dict]) -> dict:
    to_issue = [h for h in (hours(c.get("exports_landed_at"), c.get("first_issue_at")) for c in clients)
                if h is not None]
    to_value = [h for h in (hours(c.get("exports_landed_at"), c.get("first_value_at")) for c in clients)
                if h is not None]
    waiting = [c for c in clients if c.get("exports_landed_at") and not c.get("first_issue_at")]
    return {
        "n_measured": len(to_issue),
        "median_hours_to_first_issue": round(median(to_issue), 1) if to_issue else None,
        "n_with_value": len(to_value),
        "median_days_to_first_value": round(median(to_value) / 24, 1) if to_value else None,
        "n_waiting": len(waiting),
    }


def digest_lines(clients: list[dict], now: datetime | None = None) -> list[str]:
    s = summary(clients)
    late = breaches(clients, now)
    lines = ["Speed to value"]
    if s["n_measured"]:
        lines.append(f"  Issue 001 landed a median {s['median_hours_to_first_issue']}h after the exports "
                     f"({s['n_measured']} client(s); the promise is {SLA_HOURS}h)")
    else:
        lines.append("  no client has had exports land and Issue 001 publish yet")
    if s["n_with_value"]:
        lines.append(f"  first measured or recovered dollar: median {s['median_days_to_first_value']}d "
                     f"after the exports ({s['n_with_value']} client(s))")
    for b in late:
        c = b["client"]
        lines.append(f"  LATE: {c.get('company_name') or c.get('contact_email')} has waited "
                     f"{b['hours']}h for Issue 001 — the site promises {SLA_HOURS}h")
    return lines
