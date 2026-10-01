"""The Record, month by month: what each move earned in one closed month.

HUBRICON_SPEC.md ("The mechanics"): each month closes on a fixed date, the
attribution runs once on the closed month, and that produces one number,
attributed profit for the month. If it clears the fee the month is billed; if
not, the month is free, with nothing credited or carried. This module makes
that number. It is pure, like measurement.py: dicts in, verdicts out.

How a month is measured, without a second measurement engine
------------------------------------------------------------
measurement.py measures a move once, over the window after it went live, and
every family takes its baseline from the evidence recorded when the move was
issued (the terms' spend, the price and units before, the fee before). Only
the after-window comes from the data, and only through rows whose
`period_start` falls after the day the move was made.

So a month is measured by handing each family the same move with a different
start and different data: the move's start becomes the day before the month
(or the day it was made, if that was inside the month), and the data keeps the
rows on or before the day the move was made (its baseline) plus the rows that
start inside the month, and nothing in between. Every guard comes with it:
the cap at the promise (a promise is thirty days, and so is a month), the $25
floor, and one dollar, one move. And one guard arrives that the single
measurement never had: **persistence**. A leak that stopped holding measures
nothing in the month it stopped, so it earns nothing that month.

A reimbursement is direct and one-off: it counts in the month Amazon paid it,
on a claim we filed, and never again.

Each export row belongs to the month its period starts in, so no row is ever
counted in two months.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from . import measurement

# A month is measured once its exports can have landed: this many days after
# it ends. The result then stands (disputes aside); it is never re-run.
CLOSE_LAG_DAYS = 7

# Moves that carry no dollars in any month: the work is on the Record, the
# money is not ours to claim (measurement.UNBANKABLE_KINDS), or the move bought
# information rather than profit.
NO_DOLLARS = set(measurement.UNBANKABLE_KINDS) | {"ad_switchback", "price_experiment", "liquidation"}


def add_months(d: date, n: int) -> date:
    """The same day n months on, clamped to the month's last day (Jan 31 → Feb 28)."""
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def billing_months(client: dict, today: date) -> list[dict]:
    """Every month of the retainer that has begun, oldest first.

    Month 0 starts the day the client said yes. The first `free_months` of them
    are free whatever they measure (the Proving Month, plus any month a
    referral earned). A month is `closed` once CLOSE_LAG_DAYS have passed after
    its last day."""
    started = client.get("retainer_started_at")
    if not started:
        return []
    start = date.fromisoformat(str(started)[:10])
    free = int(client.get("free_months") or 1)
    out = []
    k = 0
    while True:
        m_start = add_months(start, k)
        if m_start > today:
            break
        m_end = add_months(start, k + 1) - timedelta(days=1)
        out.append({"index": k, "start": m_start, "end": m_end, "free": k < free,
                    "closed": today >= m_end + timedelta(days=CLOSE_LAG_DAYS)})
        k += 1
    return out


def _starts(row: dict) -> date | None:
    s = row.get("period_start")
    return date.fromisoformat(str(s)[:10]) if s else None


def _slice(rows: list[dict], made: date, month: dict) -> list[dict]:
    """The rows one move is measured on for one month: its baseline (rows that
    start on or before the day it was made) and the month's own rows. A row with
    no period is not time-bound and is kept."""
    out = []
    for r in rows or []:
        s = _starts(r)
        if s is None or s <= made or month["start"] <= s <= month["end"]:
            out.append(r)
    return out


def _paid_in(claims: list[dict], month: dict) -> list[dict]:
    """Claims Amazon paid inside the month. A claim pays once, so it counts once."""
    out = []
    for c in claims or []:
        paid = c.get("paid_at")
        if c.get("status") == "paid" and paid and month["start"] <= date.fromisoformat(str(paid)[:10]) <= month["end"]:
            out.append(c)
    return out


def measure_month(directives: list[dict], data: dict, margins: list[dict], ads_rows: list[dict],
                  claims: list[dict], month: dict, inv_econ: dict | None = None) -> list[dict]:
    """One verdict per move that could have earned something in `month`.

    A move made after the month ended has nothing to say about it and is left
    out. The verdicts are measurement.py's own: `measured` carries dollars,
    `not_yet` and `closed` carry none and say why."""
    verdicts = []
    paid_claims = _paid_in(claims, month)
    for d in directives:
        kind = d.get("kind")
        if d.get("status") not in measurement.MEASURABLE_STATUSES or not kind or kind in NO_DOLLARS:
            continue
        made = measurement._acted_on(d)
        if made is None or made > month["end"]:
            continue
        since = max(made, month["start"] - timedelta(days=1))
        moved = {**d, "executed_at": since.isoformat(), "measured_at": None, "measured_impact_usd": None}
        sliced = {k: (_slice(v, made, month) if isinstance(v, list) else v) for k, v in (data or {}).items()}
        out = measurement.measure([moved], sliced, _slice(margins, made, month), ads_rows or [],
                                  paid_claims, today=month["end"], inv_econ=inv_econ)
        for v in out:
            verdicts.append({**v, "month_index": month["index"]})
    # One dollar, one move, across every move in the month: the oldest keeps it.
    by_id = {d["id"]: d for d in directives if d.get("id")}
    ordered = sorted(verdicts, key=lambda v: str((by_id.get(v["directive_id"]) or {}).get("issued_at") or ""))
    return measurement._dedupe_overlapping(ordered, by_id)


def month_total(verdicts: list[dict]) -> float:
    """Attributed profit for the month: every measured dollar, and only those."""
    return round(sum(float(v["measured_impact_usd"]) for v in verdicts
                     if v.get("verdict") == "measured" and v.get("measured_impact_usd") is not None), 2)


def month_row(client: dict, month: dict, verdicts: list[dict], fee: float | None = None,
              channel: str = "amazon") -> dict:
    """The record_months row for one closed month on one channel. Written once; it
    stands. A two-platform client has one row per channel, summed by the gate."""
    fee = float(fee if fee is not None else client.get("monthly_fee_usd") or 6000.0)
    total = month_total(verdicts)
    return {
        "client_id": client["id"],
        "channel": channel,
        "month_index": month["index"],
        "month_start": month["start"].isoformat(),
        "month_end": month["end"].isoformat(),
        "free": bool(month["free"]),
        "attributed_usd": total,
        "fee_usd": fee,
        "clears": total > fee,
        "moves": [{"directive_id": v["directive_id"], "kind": v.get("kind"), "verdict": v["verdict"],
                   "usd": v.get("measured_impact_usd"), "attribution": v.get("attribution"),
                   "notes": v.get("measurement_notes"), "window": v.get("window")} for v in verdicts],
    }


def standing(row: dict) -> float:
    """A month's attributed profit after any disputed dollars came off it."""
    return round(float(row.get("attributed_usd") or 0) - float(row.get("disputed_usd") or 0), 2)
