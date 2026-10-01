"""Where a client stands, and what the machine may send them because of it.

Before 2026-10-01 everyone who booked a call became a `pending` client the
moment the booking was read: "You're in" went out before the call, nudges and
the downsell ran off the booking date, and a prospect who uploaded files and
then said no on the call could still receive move emails that the standing
mandate approves after 72 hours. Terms §3 say the Proving Month "starts on the
day you say yes after the call"; nothing in the machine knew whether anyone had.

Five stages, read from rows that already exist:

    booked    a call is booked and has not happened yet (or has no time on it)
    called    the call has happened; no yes or no is recorded
    agreed    the client said yes: `retainer_started_at` is set (`hubricon retainer`)
    declined  the client said no: status 'declined' (`hubricon declined`)
    churned   the client left: status 'churned' (`hubricon cancel`)

Every automated client email asks `may_send(stage, kind)` first. The founder's
own replies, billing letters (which follow money, not a stage) and the exit
letter are outside this table on purpose.
"""

from __future__ import annotations

from datetime import datetime, timezone

STAGES = ("booked", "called", "agreed", "declined", "churned")

# What the machine may send, unasked, at each stage. Anything not listed waits.
#   call_prep   what the call is and the one thing to have ready (on booking)
#   first_read  Profit Brief No. 001, if they sent files (before or after the call)
#   nudge/files the upload link again, only once the call has happened
#   downsell    Recovery Only, once, two weeks after the call, Amazon only
#   agreed      the letter that confirms the yes and dates the Proving Month
#   moves       "before it goes live": sealed move notices under the mandate
#   brief       the fortnightly Profit Brief (No. 002 onward)
#   weekly_note the Monday note: found, sealed, watching
#   alerts      a watch alert between notes
ALLOWED: dict[str, frozenset[str]] = {
    "booked": frozenset({"call_prep", "first_read"}),
    "called": frozenset({"first_read", "nudge", "files", "downsell"}),
    "agreed": frozenset({"agreed", "first_read", "nudge", "files", "moves", "brief", "weekly_note", "alerts"}),
    "declined": frozenset(),
    "churned": frozenset(),
}


def _ts(v) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def stage(client: dict, call_at=None, now: datetime | None = None) -> str:
    """The client's stage from their row and the time of their call."""
    now = now or datetime.now(timezone.utc)
    status = (client.get("status") or "pending").lower()
    if status == "churned":
        return "churned"
    if status == "declined":
        return "declined"
    if client.get("retainer_started_at") or status in ("active", "past_due"):
        return "agreed"
    when = _ts(call_at)
    if when and when <= now:
        return "called"
    return "booked"


def may_send(stage_name: str, kind: str) -> bool:
    return kind in ALLOWED.get(stage_name, frozenset())


def call_at(db, client_id: str):
    """The time of the client's application call: their latest booking that is
    not a kickoff. A reschedule moves it; a kickoff (a client's follow-up) does
    not count as the call."""
    from .onboarding import KICKOFF_EVENT

    rows = (db.table("bookings").select("starts_at,event_type,created_at").eq("client_id", client_id)
            .order("created_at", desc=True).execute().data) or []
    for b in rows:
        if not KICKOFF_EVENT.search(b.get("event_type") or "") and b.get("starts_at"):
            return _ts(b["starts_at"])
    return None


def stage_of(db, client: dict, now: datetime | None = None) -> str:
    """`stage` with the call time looked up. Agreed, declined and churned need no lookup."""
    quick = stage(client, None, now)
    if quick != "booked":
        return quick
    return stage(client, call_at(db, client["id"]), now)
