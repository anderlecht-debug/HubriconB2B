"""Issuing directives, and the veto window that makes issuing them honest.

terms.html §6 promises: "Every planned correction is stated in your brief with
its expected dollar impact BEFORE it goes live, and you may veto any of them by
reply." Nothing kept that promise. Drafts were invisible (RLS hides
status='draft'), promoting them was a manual `--issue` flag the sweep never
set, and no notification was ever sent — so a client had to happen to open the
desk to find a decision waiting.

The rule this module exists to enforce is in `issue_drafts` step 5: if the
notification did not actually go out, `veto_closes_at` stays NULL and the
directive can never auto-approve. Silence from someone who was never told is
not consent, and a veto window nobody was told about is worse than no window.
"""

from datetime import datetime, timedelta, timezone

VETO_HOURS = 72             # closes before the next weekly sweep, and always
                            # leaves a full working day plus the weekend
EXPLICIT_LAPSE_DAYS = 21    # an explicit-mandate directive nobody answered
MAX_ISSUED_PER_SWEEP = 5    # the offer is "your effort is zero"; a wall of
                            # twelve decisions is not zero effort


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# terms.html §6 states the defaults every client starts from. A stored mandate
# overrides them; nothing here invents an authority the client did not give.
DEFAULT_MANDATE = {
    "pricing": {"standing": True, "bound": 0.05,
                "bound_note": "price steps up to 5% per SKU per cycle"},
    "advertising": {"standing": True, "bound": None,
                    "bound_note": "negative matches, campaign trims and branded tests"},
    "inventory": {"standing": False, "bound": None, "bound_note": "purchase orders need a yes"},
    "margin": {"standing": False, "bound": None, "bound_note": "listing changes need a yes"},
    "recovery": {"standing": False, "bound": None,
                 "bound_note": "filing a case in your account needs a yes"},
    "general": {"standing": False, "bound": None, "bound_note": ""},
}


def load_mandate(db, client_id: str) -> dict:
    """What this client actually authorised, per module.

    Falls back to the published defaults so a client who has not had the
    kickoff conversation yet is governed by exactly what the Terms say — never
    by something more permissive."""
    out = {k: {**v, "veto_hours": VETO_HOURS} for k, v in DEFAULT_MANDATE.items()}
    try:
        rows = db.table("mandates").select("*").eq("client_id", client_id).execute().data
    except Exception:
        return out      # table not migrated yet: the Terms' defaults stand
    for r in rows:
        out[r["module"]] = {
            "standing": bool(r["standing"]),
            "bound": float(r["bound"]) if r.get("bound") is not None else None,
            "bound_note": r.get("bound_note") or "",
            "veto_hours": int(r.get("veto_hours") or VETO_HOURS),
        }
    return out


def close_veto_windows(db, client: dict, channel: str, dry: bool = False) -> dict:
    """Run at the TOP of a sweep, before drafting.

    A standing-mandate directive whose window closed is approved — that is what
    the mandate means. An explicit one is never auto-approved; after
    EXPLICIT_LAPSE_DAYS it lapses, because no answer is neither a yes nor a no
    and pretending otherwise in either direction misrepresents the client.
    """
    now = _now()
    out = {"auto_approved": 0, "lapsed": 0}

    ready = (db.table("directives")
             .select("id, action_text, mandate, veto_closes_at, notified_at, issued_at")
             .eq("client_id", client["id"]).eq("channel", channel).eq("status", "issued")
             .execute().data)
    for d in ready:
        # notified_at is the proof we told them. Without it the window is void.
        if d.get("mandate") == "standing" and d.get("notified_at") and d.get("veto_closes_at") \
                and datetime.fromisoformat(str(d["veto_closes_at"])) <= now:
            if not dry:
                db.table("directives").update({
                    "status": "approved",
                    "auto_approved_at": _iso(now),
                    "responded_at": _iso(now),
                }).eq("id", d["id"]).execute()
            out["auto_approved"] += 1
            continue
        if d.get("mandate") == "explicit" and d.get("issued_at") \
                and datetime.fromisoformat(str(d["issued_at"])) <= now - timedelta(days=EXPLICIT_LAPSE_DAYS):
            if not dry:
                db.table("directives").update({
                    "status": "lapsed",
                    "measurement_notes": "No answer within "
                                         f"{EXPLICIT_LAPSE_DAYS} days. Silence is not consent, so this was "
                                         "never executed.",
                }).eq("id", d["id"]).execute()
            out["lapsed"] += 1
    return out


def issue_drafts(db, client: dict, channel: str, portal_url: str,
                 send: bool = False, dry: bool = False, limit: int = MAX_ISSUED_PER_SWEEP) -> dict:
    """Promote the highest-value drafts, tell the client, then open the window.

    Order matters: the email goes out BEFORE veto_closes_at is set, and the
    window is only opened for the directives the email actually reached."""
    from .notify import directive_email_body, email_configured, send_email

    mandate = load_mandate(db, client["id"])
    drafts = (db.table("directives").select("*")
              .eq("client_id", client["id"]).eq("channel", channel).eq("status", "draft")
              .execute().data)
    # A directive drafted as "standing" is only standing if THIS client's
    # mandate says that module is. Downgrading here means a client who narrowed
    # their mandate on the kickoff call is never auto-approved into something
    # they pulled back.
    for d in drafts:
        if d.get("mandate") == "standing" and not mandate.get(d.get("module"), {}).get("standing"):
            d["mandate"] = "explicit"
    # Expected dollars first, so a promise with a number beats one without; the
    # drafting score (carried in evidence since 2026-09-23) breaks ties, which is
    # what lets an information purchase — a price experiment, a switchback —
    # reach the client at all rather than sorting last forever behind zero.
    drafts.sort(key=lambda d: (float(d.get("expected_impact_usd") or 0),
                               float((d.get("evidence") or {}).get("score") or 0)), reverse=True)
    chosen = drafts[:limit]
    out = {"issued": 0, "notified": False, "held": max(0, len(drafts) - len(chosen))}
    if not chosen:
        return out

    now = _now()
    ids = [d["id"] for d in chosen]
    if dry:
        out["issued"] = len(ids)
        return out

    db.table("directives").update({"status": "issued", "issued_at": _iso(now)}).in_("id", ids).execute()
    downgraded = [d["id"] for d in chosen if d["mandate"] == "explicit"]
    if downgraded:
        db.table("directives").update({"mandate": "explicit"}).in_("id", downgraded).execute()
    out["issued"] = len(ids)

    # The window is the client's own, not a constant.
    window_hours = min((mandate.get(d.get("module"), {}).get("veto_hours") or VETO_HOURS)
                       for d in chosen)
    notified = False
    if send and email_configured() and client.get("contact_email"):
        closes = now + timedelta(hours=window_hours)
        text, html = directive_email_body(client, chosen, closes, portal_url,
                                          record_line=_record_line(db, client))
        notified = send_email(
            client["contact_email"],
            veto_subject(chosen, closes),
            text, html=html,
        )
    out["notified"] = notified

    if notified:
        # The window only exists for people who were actually told.
        db.table("directives").update({
            "notified_at": _iso(now),
            "veto_closes_at": _iso(now + timedelta(hours=window_hours)),
        }).in_("id", ids).execute()
    else:
        # Issued and visible in the desk, but nothing will ever auto-approve.
        db.table("directives").update({"veto_closes_at": None}).in_("id", ids).execute()
    return out


def _record_line(db, client: dict) -> str | None:
    """The Profit Record footer for the veto email. Never blocks the notice:
    the window only opens for people who were told, so a footer failure must
    not turn into a missed email."""
    try:
        from . import value
        from .cli import _fetch_claims, _fetch_invoices   # lazy: cli imports the world
        directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
        return value.record_line(value.compute(client, directives, _fetch_claims(db, client["id"]),
                                               _fetch_invoices(db, client["id"])))
    except Exception:
        return None


def veto_subject(chosen: list[dict], closes) -> str:
    """The subject is the picture of the fortnight: how many moves, when they go
    live, and what they are expected to earn. Explicit-mandate moves never go
    live on their own, so a batch of only those says what it waits for."""
    n = len(chosen)
    noun = f"{n} move{'s' if n != 1 else ''}"
    total = sum(float(d.get("expected_impact_usd") or 0) for d in chosen)
    money = f" — ${total:,.0f} expected" if total > 0 else ""
    if all(d.get("mandate") != "standing" for d in chosen):
        return f"{noun} waiting for your yes{money}"
    when = closes.strftime("%A") if hasattr(closes, "strftime") else str(closes)
    return f"{noun} in your account go live {when} unless you say no{money}"


EXECUTION_SLA_DAYS = 7      # welcome.html: "Weeks 1–2 — first moves go live"; terms §3: inside fourteen days. We hold ourselves to seven.


def overdue_executions(db, client: dict, channel: str, today=None) -> list[dict]:
    """Approved, past the Week-1 SLA, and still not recorded as executed.

    The client was told this would go live in their first week. Nothing tracked
    whether it did, so the only way a slip surfaced was the client noticing."""
    from datetime import date as _date
    today = today or _date.today()
    rows = (db.table("directives")
            .select("id, action_text, responded_at, auto_approved_at, executed_at, expected_impact_usd")
            .eq("client_id", client["id"]).eq("channel", channel).eq("status", "approved")
            .execute().data)
    late = []
    for d in rows:
        if d.get("executed_at"):
            continue
        stamp = d.get("responded_at") or d.get("auto_approved_at")
        if not stamp:
            continue
        age = (today - _date.fromisoformat(str(stamp)[:10])).days
        if age >= EXECUTION_SLA_DAYS:
            late.append({**d, "days": age})
    return sorted(late, key=lambda d: -d["days"])
