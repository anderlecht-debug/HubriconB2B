"""What waits for the founder's yes: the Monday note, and Profit Brief No. 002 on.

HUBRICON_SPEC.md, "Customer experience" 4: the human layer is a short, calm
weekly note, "drafted by the system from the real graded numbers and approved
by the founder, never written from scratch. That is the only way the rhythm
survives volume." Until 2026-10-01 nothing was approved: the fortnightly Brief
went out on its own from the daily issue job, and a quiet Monday sent nothing
at all, which is how a sealed leak becomes invisible (item 5).

So the machine drafts and the founder sends:

    the Monday note   drafted by the weekly sweep for every client who said yes
                      (lifecycle 'agreed'); three sections built from rows, not
                      prose: found, sealed and holding, watching. It replaces the
                      old "This week's watch" email; alerts fold into "watching".
    the Brief         from No. 002 on, `_publish_issue` makes a draft: letter,
                      report, video and the email exactly as it will go. Nothing
                      is in the portal or in an inbox until it is approved.
                      Issue 001, the first full read, is not held: its promise
                      is speed, and the operator publishes it the hour the files land.

`hubricon approve [client|all] [--show]` sends them. A draft older than ten
days, or one whose Profit Record figure has moved since it was drafted, is
refused without --stale: its facts are no longer this week's.

Without migration 20261001000004 there is nowhere to hold a draft: the Brief
publishes and emails itself as it did before, Monday sends the old watch email,
and the founder's digest says the gate is off.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from . import lifecycle

APPROVAL_STALE_DAYS = 10
MIGRATION = "20261001000004_notes_approved.sql"
NOTES = "weekly_notes"
# A held Brief's report and video are uploaded here, outside reports/{client}/
# (the one folder a client's sign-in may read), and moved there on approval.
DRAFT_FOLDER = "drafts"


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def week_of(today: date) -> date:
    """The Monday a note belongs to (the sweep runs Mondays, 11:00 UTC)."""
    return today - timedelta(days=today.weekday())


def missing_schema(err: Exception) -> bool:
    """Is this the migration not being applied, rather than a real failure?"""
    s = str(err).lower()
    return any(k in s for k in ("weekly_notes", "pgrst204", "pgrst205", "42703", "42p01", "schema cache",
                                "does not exist", "column", "'status'", "'facts'", "approved_at"))


def gate_status(db) -> dict:
    """Can drafts be held? Both halves of the migration, or neither counts."""
    try:
        db.table(NOTES).select("id").limit(1).execute()
        db.table("briefings").select("id, status, facts, approved_at").limit(1).execute()
        return {"ok": True, "reason": None}
    except Exception as err:
        return {"ok": False, "reason": f"apply supabase/migrations/{MIGRATION} ({str(err)[:90]})"}


def pending_notes(db, client_id: str | None = None) -> list[dict] | None:
    """Drafted Monday notes waiting for a yes, oldest first; None without the table."""
    try:
        q = db.table(NOTES).select("*").eq("status", "draft")
        if client_id:
            q = q.eq("client_id", client_id)
        return q.order("created_at").execute().data or []
    except Exception:
        return None


def brief_drafts(db, client_id: str | None = None) -> list[dict] | None:
    """Drafted Briefs waiting for a yes, oldest first; None without the column."""
    try:
        q = db.table("briefings").select("*").eq("status", "draft")
        if client_id:
            q = q.eq("client_id", client_id)
        return q.order("created_at").execute().data or []
    except Exception:
        return None


def age(row: dict, now: datetime | None = None) -> timedelta:
    made = _ts(row.get("created_at"))
    return ((now or _now()) - made) if made else timedelta(0)


def is_stale(row: dict, now: datetime | None = None) -> bool:
    return age(row, now) > timedelta(days=APPROVAL_STALE_DAYS)


def called_seals(db, client_id: str) -> dict[str, str]:
    """Each sealed move's short seal (seal.py), by directive id; {} when the
    Seal's table cannot be read, so a note is never held for its receipts."""
    try:
        from .seal import TABLE, short
        rows = (db.table(TABLE).select("entry, directive_id, leaf").eq("client_id", client_id)
                .eq("entry", "called").execute().data) or []
        return {str(r["directive_id"]): short(r["leaf"]) for r in rows if r.get("leaf") and r.get("directive_id")}
    except Exception:
        return {}


# -- drafting the Monday note ---------------------------------------------------------------

def draft_weekly_note(db, client: dict, portal_url: str, fresh_alerts: list[dict] | None = None,
                      now: datetime | None = None, today: date | None = None) -> dict:
    """Draft (or re-draft) this week's note for one client from what the
    database holds now. Idempotent within a week: a two-channel client is swept
    twice, and the second pass re-drafts the same week's note with both
    channels in it. A note already sent, or discarded by the founder, is left
    alone. Returns {"status": drafted|redrafted|not_agreed|sent|discarded|unavailable, ...}."""
    from . import briefing, notify, value

    now = now or _now()
    today = today or now.date()
    stage = lifecycle.stage_of(db, client, now)
    if not lifecycle.may_send(stage, "weekly_note"):
        return {"status": "not_agreed", "stage": stage}
    wk = week_of(today)
    try:
        mine = db.table(NOTES).select("*").eq("client_id", client["id"]).execute().data or []
    except Exception as err:
        return {"status": "unavailable", "reason": f"apply supabase/migrations/{MIGRATION} ({str(err)[:80]})"}
    this = next((n for n in mine if str(n.get("week_of"))[:10] == wk.isoformat()), None)
    if this and this.get("status") in ("sent", "discarded"):
        return {"status": this["status"], "note": this}
    earlier = sorted((n for n in mine if str(n.get("week_of"))[:10] < wk.isoformat()),
                     key=lambda n: str(n.get("week_of")))
    # "This week" runs from the last note, so nothing is told twice and nothing falls between.
    since = (_ts(earlier[-1].get("created_at")) if earlier else None) or (now - timedelta(days=7))

    cid = client["id"]
    directives = db.table("directives").select("*").eq("client_id", cid).execute().data or []
    alerts = (db.table("alerts").select("*").eq("client_id", cid).gte("created_at", since.isoformat())
              .execute().data) or []
    seen = {a.get("id") for a in alerts}
    alerts += [a for a in (fresh_alerts or []) if a.get("id") not in seen]
    months = value.load_months(db, cid)
    ledger = value.load_ledger(db, client, today)
    proven = value.proven_from(client, ledger, months, today)
    seals = called_seals(db, cid)

    found = briefing.note_found_lines(directives, since, seals)
    holding = briefing.note_holding_lines(directives, months, client, seals, today)
    watching = briefing.note_watching_lines(alerts)
    record = value.record_line(ledger, proven)
    company = client.get("company_name") or client.get("contact_email") or "your account"
    note = briefing.weekly_note(company, found, holding, watching, record, portal_url,
                                n_live=len(briefing.live_moves(directives)))
    text, html = notify.letter(client.get("contact_name"), note["blocks"])
    facts = {"week_of": wk.isoformat(), "since": since.isoformat(), "subject": note["subject"],
             "found": found, "holding": holding, "watching": watching, "urgent": note["urgent"],
             "alert_ids": [a["id"] for a in alerts if a.get("id")], "proven": proven, "record_line": record}
    # created_at is when these facts were read: a re-draft resets it, so the
    # next week's "since" starts where this note's facts end.
    row = {"client_id": cid, "week_of": wk.isoformat(), "facts": facts, "body_text": text, "body_html": html,
           "status": "draft", "created_at": now.isoformat()}
    try:
        if this:
            db.table(NOTES).update(row).eq("id", this["id"]).execute()
            saved, status = {**this, **row}, "redrafted"
        else:
            saved, status = db.table(NOTES).insert(row).execute().data[0], "drafted"
        # A week's note is that week's: an older one never approved is superseded.
        for n in earlier:
            if n.get("status") == "draft":
                db.table(NOTES).update({"status": "discarded"}).eq("id", n["id"]).execute()
    except Exception as err:
        if missing_schema(err):
            return {"status": "unavailable", "reason": f"apply supabase/migrations/{MIGRATION} ({str(err)[:80]})"}
        raise
    return {"status": status, "note": saved, "week_of": wk.isoformat()}


# -- approving -----------------------------------------------------------------------------

def _money(v) -> str:
    v = float(v or 0)
    return ("−" if v < 0 else "") + f"${abs(v):,.0f}"


def _words(p: dict | None) -> str:
    if not p:
        return "nothing"
    from .value import proven_words
    return f"{_money(p.get('usd'))} {proven_words(p)[0]}"


def record_moved(drafted: dict | None, now_proven: dict) -> str | None:
    """Why a draft's Record figure is no longer the Record's, or None."""
    if not drafted:
        return None
    if (drafted.get("basis") != now_proven.get("basis")
            or round(float(drafted.get("usd") or 0), 2) != round(float(now_proven.get("usd") or 0), 2)):
        return f"the Profit Record moved since it was drafted ({_words(drafted)} then, {_words(now_proven)} now)"
    return None


def refusal(db, client: dict, kind: str, row: dict, now: datetime | None = None) -> tuple[str | None, bool]:
    """(reason, overridable). A stage that no longer allows the mail is never
    overridden; age and a moved Record are, with --stale."""
    from . import value
    stage = lifecycle.stage_of(db, client, now)
    if not lifecycle.may_send(stage, "weekly_note" if kind == "note" else "brief"):
        return f"{client.get('company_name') or client.get('contact_email')} is '{stage}' now; this mail is only for clients who said yes", False
    redraft = (f"Re-draft it with `hubricon sweep --client {client.get('contact_email')}`" if kind == "note"
               else f"Re-draft it with `hubricon issue --client {client.get('contact_email')} --force`")
    if is_stale(row, now):
        return (f"drafted {age(row, now).days} days ago, more than {APPROVAL_STALE_DAYS}: the facts have moved "
                f"since. {redraft}."), True
    moved = record_moved((row.get("facts") or {}).get("proven"), value.proven_since_day_one(db, client))
    if moved:
        return f"{moved}. {redraft}.", True
    return None, False


def _brief_email(db, client: dict, brief: dict, send: bool) -> tuple[str, list[dict], str | None]:
    """The Brief's email as approved: the subject and blocks drafted with it,
    then the consent ask if one is due (minted only when it will really go)."""
    from . import referral, value
    facts = brief.get("facts") or {}
    subject = facts.get("subject") or f"Profit Brief No. {int(brief.get('issue_number') or 0):03d} is in Hubricon"
    blocks = list(facts.get("blocks") or [{"p": "Your Profit Brief is in Hubricon."}])
    try:
        ledger = value.load_ledger(db, client)
        claims = db.table("recovery_claims").select("*").eq("client_id", client["id"]).execute().data or []
        blocks += referral.ask_if_due(db, client, ledger, claims, send)
    except Exception as err:
        print(f"  consent ask skipped: {err}")
    return subject, blocks, facts.get("record_line")


def render(db, client: dict, kind: str, row: dict, now: datetime | None = None) -> str:
    """The draft in full, exactly as it would reach the client."""
    from . import notify
    who = client.get("company_name") or client.get("contact_email")
    days = age(row, now).days
    if kind == "note":
        facts = row.get("facts") or {}
        return "\n".join([f"== {who} · weekly note, week of {str(row.get('week_of'))[:10]} · to "
                          f"{client.get('contact_email')} · drafted {days}d ago",
                          f"Subject: {facts.get('subject')}", "", row.get("body_text") or "", ""])
    subject, blocks, record = _brief_email(db, client, row, send=False)
    text, _ = notify.letter(client.get("contact_name"), blocks + ([{"p": record}] if record else []))
    facts = row.get("facts") or {}
    out = [f"== {who} · Profit Brief No. {int(row.get('issue_number') or 0):03d}"
           + (f" ({facts['channel']})" if facts.get("channel") else "")
           + f" · to {client.get('contact_email')} · drafted {days}d ago",
           f"Subject: {subject}", "", "--- the email ---", text, "", "--- the letter in Hubricon ---",
           row.get("memo") or "(no letter)", ""]
    for label, key in (("Report", "report_path"), ("Video", "video_path")):
        out.append(f"{label}: {row.get(key) or 'none'}")
    return "\n".join(out) + "\n"


def send_note(db, client: dict, note: dict, now: datetime | None = None) -> dict:
    """Send the note exactly as drafted, once, and mark it sent."""
    from . import cli
    from .notify import email_configured
    now = now or _now()
    facts = note.get("facts") or {}
    try:
        done = (db.table("client_emails").select("id").eq("client_id", client["id"]).eq("kind", "weekly_note")
                .eq("ref_id", str(note["id"])).limit(1).execute().data)
    except Exception:
        done = []
    if not done:
        if not email_configured():
            return {"sent": False, "reason": "RESEND_API_KEY is not set, so nothing can be sent; it stays a draft"}
        if not client.get("contact_email"):
            return {"sent": False, "reason": "the client has no email address on file"}
        ok = cli._send_client_email(db, client, "weekly_note", note["id"], facts.get("subject") or "Your week",
                                    [], True, rendered=(note.get("body_text") or "", note.get("body_html")))
        if not ok:
            return {"sent": False, "reason": "the send failed (see the error above); it stays a draft"}
    stamp = now.isoformat()
    db.table(NOTES).update({"status": "sent", "approved_at": stamp, "sent_at": stamp}).eq("id", note["id"]).execute()
    ids = [i for i in facts.get("alert_ids") or [] if i]
    if ids:
        try:
            db.table("alerts").update({"emailed_at": stamp}).in_("id", ids).execute()
        except Exception:
            pass
    return {"sent": True}


def _promote_files(db, brief: dict) -> dict:
    """Move a held Brief's report and video into reports/{client}/, where the
    portal can open them. Returns the briefings patch for their new paths."""
    from .storage import BUCKET
    patch = {}
    for key, kind in (("report_path", "text/html"), ("video_path", "video/mp4")):
        path = brief.get(key)
        if not path or not str(path).startswith(DRAFT_FOLDER + "/"):
            continue
        final = "reports/" + str(path)[len(DRAFT_FOLDER) + 1:]
        bucket = db.storage.from_(BUCKET)
        bucket.upload(final, bucket.download(path), {"content-type": kind, "upsert": "true"})
        try:
            bucket.remove([path])
        except Exception:
            pass        # a leftover draft file is unreadable to the client and harmless
        patch[key] = final
    return patch


def publish_brief(db, client: dict, brief: dict, now: datetime | None = None) -> dict:
    """Publish the Brief to the portal and email it, as drafted. Its files move
    first; if they cannot, nothing is published and the reason is returned."""
    from . import cli, referral
    now = now or _now()
    try:
        moved = _promote_files(db, brief)
    except Exception as err:
        return {"published": False, "emailed": False,
                "reason": f"its report or video could not be moved where the portal reads them ({err})"}
    db.table("briefings").update({"status": "published", "approved_at": now.isoformat(), **moved}) \
        .eq("id", brief["id"]).execute()
    subject, blocks, record = _brief_email(db, client, brief, send=True)
    asked = len(blocks) > len((brief.get("facts") or {}).get("blocks") or [])
    sent = cli._send_client_email(db, client, "issue_ready", brief["id"], subject, blocks, True,
                                  footer=record)
    if sent and asked:
        try:
            referral.mark_asked(db, client)
        except Exception as err:
            print(f"  consent ask not recorded: {err}")
    return {"published": True, "emailed": sent}


def discard(db, kind: str, row: dict) -> None:
    """A note is kept, marked discarded. A Brief draft was never anyone's to
    read and its number is free again, so its row goes."""
    if kind == "note":
        db.table(NOTES).update({"status": "discarded"}).eq("id", row["id"]).execute()
    else:
        db.table("briefings").delete().eq("id", row["id"]).eq("status", "draft").execute()


def approve(db, client_ids: list[str] | None = None, show: bool = False, stale: bool = False,
            discard_all: bool = False, ask=None, out=print, now: datetime | None = None) -> dict:
    """The approval pass behind `hubricon approve`.

    Without --show every fresh draft is sent: the founder has read them (the
    digest carries their first lines; --show prints them whole). With --show
    each is printed in full first; on a terminal he answers y (send), d
    (discard) or anything else (leave it), and with no terminal it is a
    preview only and nothing is sent."""
    now = now or _now()
    summary = {"sent": 0, "published": 0, "emailed": 0, "refused": [], "discarded": 0, "left": 0, "gate": True}
    notes = pending_notes(db)
    briefs = brief_drafts(db)
    if notes is None or briefs is None:
        summary["gate"] = False
        out(f"Nothing is held for approval on this database: {gate_status(db)['reason'] or MIGRATION}.")
        return summary
    want = set(client_ids) if client_ids else None
    items = [("note", n) for n in notes] + [("brief", b) for b in briefs]
    items = [(k, r) for k, r in items if want is None or r.get("client_id") in want]
    if not items:
        out("Nothing is waiting for your approval.")
        return summary
    ids = sorted({r["client_id"] for _, r in items})
    clients = {c["id"]: c for c in (db.table("clients").select("*").in_("id", ids).execute().data or [])}
    for kind, row in items:
        client = clients.get(row["client_id"])
        if not client:
            continue
        who = client.get("company_name") or client.get("contact_email")
        what = (f"weekly note, week of {str(row.get('week_of'))[:10]}" if kind == "note"
                else f"Profit Brief No. {int(row.get('issue_number') or 0):03d}")
        if discard_all:
            discard(db, kind, row)
            summary["discarded"] += 1
            out(f"{who} · {what}: discarded.")
            continue
        if show:
            out(render(db, client, kind, row, now))
        reason, overridable = refusal(db, client, kind, row, now)
        if reason and not (stale and overridable):
            summary["refused"].append(f"{who} · {what}: {reason}")
            out(f"{who} · {what}: NOT SENT — {reason}"
                + (" Pass --stale to send it as drafted anyway." if overridable else ""))
            continue
        if show:
            if ask is None:
                summary["left"] += 1
                out(f"{who} · {what}: shown only (no terminal to answer on). "
                    f"`hubricon approve {client.get('contact_email')}` sends it as shown.")
                continue
            answer = (ask(f"Send this to {client.get('contact_email')}? [y]es / [d]iscard / anything else leaves it: ")
                      or "").strip().lower()
            if answer.startswith("d"):
                discard(db, kind, row)
                summary["discarded"] += 1
                out(f"{who} · {what}: discarded.")
                continue
            if not answer.startswith("y"):
                summary["left"] += 1
                out(f"{who} · {what}: left as a draft.")
                continue
        if kind == "note":
            res = send_note(db, client, row, now)
            if res["sent"]:
                summary["sent"] += 1
                out(f"{who} · {what}: sent.")
            else:
                summary["left"] += 1
                out(f"{who} · {what}: NOT SENT — {res['reason']}.")
        else:
            res = publish_brief(db, client, row, now)
            if not res["published"]:
                summary["left"] += 1
                out(f"{who} · {what}: NOT PUBLISHED — {res['reason']}.")
                continue
            summary["published"] += 1
            summary["emailed"] += 1 if res["emailed"] else 0
            out(f"{who} · {what}: published in Hubricon"
                + (" and emailed." if res["emailed"] else
                   "; NOT emailed (no RESEND_API_KEY, no address, or already sent)."))
    return summary


# -- the founder's digest ------------------------------------------------------------------

def _first_line(kind: str, row: dict) -> str:
    if kind == "note":
        facts = row.get("facts") or {}
        for key, head in (("found", "Found"), ("holding", "Holding"), ("watching", "Watching")):
            if facts.get(key):
                return f"{head}: {facts[key][0]}"
        return "Found nothing new; nothing live yet; nothing new crossed a line."
    for para in (row.get("memo") or "").split("\n\n"):
        p = para.strip()
        if p and not p.startswith(("Profit Brief No.", "Dear ")):
            return p.replace("\n", " ")
    return row.get("headline") or ""


def digest_lines(db, now: datetime | None = None) -> list[str]:
    """'Waiting for your approval: N notes, M briefs', the first lines of each,
    and a loud line when the gate cannot hold anything."""
    now = now or _now()
    notes, briefs = pending_notes(db), brief_drafts(db)
    if notes is None or briefs is None:
        return [f"APPROVAL GATE OFF: {gate_status(db)['reason'] or 'apply supabase/migrations/' + MIGRATION}. "
                "Until it is applied, Profit Briefs from No. 002 publish and email themselves unapproved, and "
                "Monday sends the old watch email instead of a note.", ""]
    if not notes and not briefs:
        return []
    ids = sorted({r["client_id"] for r in notes + briefs})
    names = {c["id"]: c.get("company_name") or c.get("contact_email")
             for c in (db.table("clients").select("id, company_name, contact_email").in_("id", ids).execute().data or [])}
    n, m = len(notes), len(briefs)
    lines = [f"Waiting for your approval: {n} note{'s' if n != 1 else ''}, {m} brief{'s' if m != 1 else ''} "
             f"— `hubricon approve all --show`"]
    for kind, row in [("note", r) for r in notes] + [("brief", r) for r in briefs]:
        stale = f" (STALE, {age(row, now).days}d: re-draft)" if is_stale(row, now) else ""
        if kind == "note":
            head = f"weekly note, week of {str(row.get('week_of'))[:10]}{stale}: {(row.get('facts') or {}).get('subject')}"
        else:
            head = (f"Profit Brief No. {int(row.get('issue_number') or 0):03d}{stale}: "
                    f"{(row.get('facts') or {}).get('subject') or row.get('headline')}")
        lines.append(f"  - {names.get(row['client_id'], row['client_id'])} · {head}")
        first = _first_line(kind, row)
        if first:
            lines.append(f"      {first[:160]}")
    lines.append("")
    return lines
