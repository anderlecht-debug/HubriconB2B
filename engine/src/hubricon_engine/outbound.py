"""Outbound: the one Instantly campaign, who goes into it, and what comes back.

The campaign is created once from the spec below (idempotent by name),
activated only when at least one warmed mailbox exists, and fed from two
sources: lead lists the founder builds in Instantly (any list whose name
contains "hubricon") and, best effort, Instantly's SuperSearch database.
Replies are pulled from the unibox into prospect_messages for triage.
"""

import os
from datetime import datetime, timezone

from . import triage
from .instantly import CAMPAIGN_ACTIVE, Instantly, InstantlyError
from .onboarding import guess_name_parts, is_internal

CAMPAIGN_NAME = "Hubricon — Profit Teardown (PL FBA $1M–$20M)"
CALENDLY_URL = os.environ.get("CALENDLY_URL", "https://calendly.com/hubricon/margin-audit")
PER_MAILBOX_DAILY = 20          # a two-month-old domain: slow is the only safe speed
CAMPAIGN_DAILY_CAP = 60
LIST_MATCH = os.environ.get("INSTANTLY_LIST_MATCH", "hubricon").lower()
SUPERSEARCH_DAILY = int(os.environ.get("SUPERSEARCH_DAILY", "25"))

SUPERSEARCH_LIST = "Hubricon SuperSearch (auto)"
# Instantly's own filter vocabulary (enums from api.instantly.ai/openapi/api_v2.json).
# Revenue bands are the ICP verbatim: $1M–$50M private-label brands run by their founder.
SUPERSEARCH_FILTERS = {
    "title": {"include": ["Founder", "Co-Founder", "CEO", "Owner", "President"], "includeMode": "CONTAINS"},
    "keyword_filter": {"include": "Amazon FBA, private label, Amazon brand, Amazon seller", "include_mode": "ANY"},
    "revenue": ["$1 - 10M", "$10 - 50M"],
    "employeeCount": ["0 - 25", "25 - 100"],
    "locations": {"include": [{"country": "United States"}]},
    "location_mode": "company",
    "skip_owned_leads": True,
    "show_one_lead_per_company": True,
}


def _footer(postal_address: str) -> str:
    return (f"<br/><br/>Hubricon · {postal_address}<br/>"
            "Reply \"no\" and I'll stop emailing. There's also an unsubscribe link in the header.")


def campaign_spec(senders: list[str], postal_address: str, calendly_url: str = CALENDLY_URL,
                  daily_limit: int | None = None) -> dict:
    """Three plain-text steps over eight days. Every claim is on the website."""
    foot = _footer(postal_address)
    step1 = (
        "Hi {{firstName}},<br/><br/>"
        "Most private-label brands your size run five dashboards and none of them says what to do next: "
        "which SKU can take a price move, where the next ad dollar stops paying, which ASIN stocks out first.<br/><br/>"
        "I run Hubricon. Send five Seller Central exports through a private upload page and you get a written "
        "Profit Teardown back in 24 hours. Free, no seat in your account needed.<br/><br/>"
        f"Want one? Reply TEARDOWN and I'll send the upload page, or grab 20 minutes here: {calendly_url}<br/><br/>"
        "Hagen Simmons<br/>Hubricon" + foot
    )
    step2 = (
        "Hi {{firstName}},<br/><br/>"
        "Three numbers Seller Central never shows you: the stockout probability of each SKU (simulated, not a "
        "velocity average), how far each price can move before units fall off, and the ACoS where each campaign "
        "stops paying.<br/><br/>"
        "That's what the teardown is: those numbers for your catalog, written up, 24 hours after your last export "
        "lands.<br/><br/>"
        f"Reply TEARDOWN for the upload page, or book 20 minutes: {calendly_url}<br/><br/>"
        "Hagen" + foot
    )
    step3 = (
        "Hi {{firstName}},<br/><br/>"
        "Closing the loop. If margin is a next-year problem, reply \"later\" and I'll check back in Q1. If it's a "
        "now problem, the teardown is free and takes 15 minutes of exports on your side: reply TEARDOWN.<br/><br/>"
        "Either way, thanks for reading.<br/><br/>"
        "Hagen" + foot
    )
    limit = daily_limit or min(CAMPAIGN_DAILY_CAP, PER_MAILBOX_DAILY * max(1, len(senders)))
    return {
        "name": CAMPAIGN_NAME,
        "campaign_schedule": {
            "schedules": [{
                "name": "US business hours",
                "timing": {"from": "08:00", "to": "17:00"},
                "days": {"1": True, "2": True, "3": True, "4": True, "5": True},
                "timezone": "America/Chicago",
            }],
        },
        "sequences": [{
            "steps": [
                {"type": "email", "delay": 3, "variants": [{"subject": "{{companyName}} margin, quantified", "body": step1}]},
                {"type": "email", "delay": 4, "variants": [{"subject": "", "body": step2}]},
                {"type": "email", "delay": 0, "variants": [{"subject": "", "body": step3}]},
            ],
        }],
        "email_list": senders,
        "daily_limit": limit,
        "daily_max_leads": limit,
        "email_gap": 12,
        "random_wait_max": 8,
        "stop_on_reply": True,
        "stop_on_auto_reply": False,
        "stop_for_company": True,
        "link_tracking": False,
        "open_tracking": False,
        "text_only": True,
        "first_email_text_only": True,
        "insert_unsubscribe_header": True,
        "match_lead_esp": True,
        "prioritize_new_leads": False,
        "allow_risky_contacts": False,
        "disable_bounce_protect": False,
    }


# -- state helpers -----------------------------------------------------------

def get_state(db, key: str, default=None):
    rows = db.table("operator_state").select("value").eq("key", key).execute().data
    return rows[0]["value"] if rows else default


def set_state(db, key: str, value) -> None:
    db.table("operator_state").upsert(
        {"key": key, "value": value, "updated_at": datetime.now(timezone.utc).isoformat()}, on_conflict="key"
    ).execute()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(db, kind: str, note: str | None = None, **refs) -> None:
    payload = refs.pop("payload", {})
    db.table("funnel_events").insert({"kind": kind, "note": note, "payload": payload, **refs}).execute()


# -- campaign ----------------------------------------------------------------

def ensure_campaign(db, api: Instantly, postal_address: str | None, dry: bool) -> tuple[str | None, list[str]]:
    """Returns (campaign_id, notes). Creates and activates when it can; explains when it can't."""
    notes: list[str] = []
    state = get_state(db, "instantly.campaign", {}) or {}
    campaign = None
    if state.get("id"):
        campaign = next((c for c in api.campaigns() if c.get("id") == state["id"]), None)
    if campaign is None:
        campaign = api.find_campaign(CAMPAIGN_NAME)

    senders = [a["email"] for a in api.ready_senders()]
    if campaign is None:
        if not postal_address:
            notes.append("Campaign not created: POSTAL_ADDRESS secret is empty (CAN-SPAM needs a mailing "
                         "address in every cold email). Add it next to INSTANTLY_API_KEY.")
            return None, notes
        if not senders:
            notes.append("Campaign not created: no mailbox in Instantly is connected AND past warmup yet. "
                         "It will be created automatically on the first run after warmup finishes.")
            return None, notes
        spec = campaign_spec(senders, postal_address)
        if dry:
            notes.append(f"[dry] would create campaign {CAMPAIGN_NAME!r} from {len(senders)} mailbox(es)")
            return None, notes
        campaign = api.create_campaign(spec)
        notes.append(f"Created campaign {CAMPAIGN_NAME!r} ({campaign.get('id')}) sending from {', '.join(senders)}")
        log_event(db, "campaign_created", payload={"id": campaign.get("id"), "senders": senders})

    cid = campaign.get("id")
    set_state(db, "instantly.campaign", {"id": cid, "name": campaign.get("name"), "senders": senders})

    if campaign.get("status") != CAMPAIGN_ACTIVE:
        if not senders:
            notes.append("Campaign exists but stays paused: no warmed mailbox yet.")
        elif dry:
            notes.append(f"[dry] would activate campaign {cid}")
        else:
            api.activate_campaign(cid)
            notes.append(f"Activated campaign {cid}.")
            log_event(db, "campaign_activated", payload={"id": cid})
    return cid, notes


# -- enrollment ----------------------------------------------------------------

def _known_emails(db) -> dict[str, dict]:
    rows = db.table("prospects").select("id, email, status").execute().data
    return {r["email"]: r for r in rows}


def enroll_from_lists(db, api: Instantly, campaign_id: str, dry: bool, cap: int = 200) -> tuple[int, list[str]]:
    """Every lead in an Instantly list whose name contains LIST_MATCH goes into
    the campaign once, and into prospects as 'queued'."""
    notes: list[str] = []
    lists = [l for l in api.lead_lists() if LIST_MATCH in (l.get("name") or "").lower()]
    if not lists:
        notes.append(f"No Instantly lead list named like '*{LIST_MATCH}*' — nothing to enroll from lists.")
        return 0, notes
    known = _known_emails(db)
    added = 0
    for lst in lists:
        for lead in api.leads_in_list(lst["id"]):
            email = (lead.get("email") or "").strip().lower()
            if not email or email in known or is_internal(email):
                continue
            if added >= cap:
                break
            first, last = lead.get("first_name"), lead.get("last_name")
            if not first:
                first, last = guess_name_parts(lead.get("name") or lead.get("full_name"))
            if not first:
                continue  # "Hi {{firstName}}" must never render empty
            if dry:
                added += 1
                continue
            try:
                created = api.create_lead(campaign_id, email, first, last, lead.get("company_name"), lead.get("website"))
            except InstantlyError as err:
                notes.append(f"enroll {email}: {err}")
                continue
            db.table("prospects").upsert({
                "email": email, "first_name": first, "last_name": last,
                "company_name": lead.get("company_name"), "website": lead.get("website"),
                "source": "supersearch" if "supersearch" in (lst.get("name") or "").lower() else "instantly_list",
                "instantly_lead_id": (created or {}).get("id") or lead.get("id"),
                "instantly_campaign_id": campaign_id, "status": "queued", "last_event_at": _now(),
            }, on_conflict="email").execute()
            known[email] = {"email": email}
            added += 1
    notes.append(f"{'[dry] would enroll' if dry else 'Enrolled'} {added} lead(s) from {len(lists)} list(s).")
    return added, notes


def enroll_from_supersearch(db, api: Instantly, campaign_id: str, dry: bool) -> tuple[int, list[str]]:
    """Once a day, ask Instantly's database for SUPERSEARCH_DAILY fresh founders."""
    notes: list[str] = []
    today = datetime.now(timezone.utc).date().isoformat()
    if SUPERSEARCH_DAILY <= 0:
        return 0, notes
    if (get_state(db, "supersearch.last_run", {}) or {}).get("date") == today:
        return 0, notes
    if dry:
        notes.append(f"[dry] would request {SUPERSEARCH_DAILY} SuperSearch leads into '{SUPERSEARCH_LIST}'")
        return 0, notes
    try:
        lst = next((l for l in api.lead_lists() if l.get("name") == SUPERSEARCH_LIST), None)
        if lst is None:
            lst = api.create_lead_list(SUPERSEARCH_LIST)
            notes.append(f"Created Instantly lead list '{SUPERSEARCH_LIST}' ({lst.get('id')}).")
        try:
            pool = api.supersearch_count(SUPERSEARCH_FILTERS)
        except InstantlyError as err:
            pool = {"error": err.body[:120]}
        out = api.supersearch_enrich(lst["id"], SUPERSEARCH_FILTERS, SUPERSEARCH_DAILY, search_name="Hubricon ICP")
        set_state(db, "supersearch.last_run", {"date": today, "list_id": lst.get("id"),
                                               "job": out.get("background_job_id"), "pool": str(pool)[:200]})
        notes.append(f"SuperSearch: asked for {SUPERSEARCH_DAILY} founders into '{SUPERSEARCH_LIST}' "
                     f"(pool {str(pool)[:80]}); they enroll into the campaign on the next pass.")
        log_event(db, "supersearch_requested",
                  payload={"limit": SUPERSEARCH_DAILY, "list_id": lst.get("id"), "job": out.get("background_job_id"),
                           "pool": str(pool)[:300]})
        return SUPERSEARCH_DAILY, notes
    except InstantlyError as err:
        set_state(db, "supersearch.last_run", {"date": today, "error": str(err)[:500]})
        notes.append(f"SuperSearch unavailable ({err.status}): {err.body[:160]} — lists are the lead source until "
                     "this works (build one in Instantly named 'Hubricon …').")
        return 0, notes


def sync_campaign_leads(db, api: Instantly, campaign_id: str) -> list[str]:
    """Pull the campaign's lead roster so prospects the SuperSearch job added
    (or the founder added by hand in Instantly) exist here too, and mark
    anyone Instantly has already emailed as 'contacted'."""
    notes: list[str] = []
    known = _known_emails(db)
    new = contacted = 0
    for lead in api.leads_in_campaign(campaign_id):
        email = (lead.get("email") or "").strip().lower()
        if not email or is_internal(email):
            continue
        touched = any(lead.get(k) for k in ("timestamp_last_contact", "last_contacted", "timestamp_last_touch",
                                              "email_open_count", "email_reply_count", "email_click_count"))
        if email not in known:
            first, last = lead.get("first_name"), lead.get("last_name")
            db.table("prospects").upsert({
                "email": email, "first_name": first, "last_name": last,
                "company_name": lead.get("company_name"), "website": lead.get("website"),
                "source": "supersearch", "instantly_lead_id": lead.get("id"),
                "instantly_campaign_id": campaign_id,
                "status": "contacted" if touched else "queued", "last_event_at": _now(),
            }, on_conflict="email").execute()
            new += 1
        elif touched and known[email]["status"] == "queued":
            db.table("prospects").update({"status": "contacted", "last_event_at": _now()}).eq("email", email).execute()
            contacted += 1
    if new or contacted:
        notes.append(f"Roster sync: {new} new prospect(s) from Instantly, {contacted} marked contacted.")
    return notes


# -- replies -------------------------------------------------------------------

def sync_replies(db, api: Instantly, campaign_id: str, dry: bool) -> tuple[int, list[str]]:
    """New inbound emails → prospect_messages (pending) → triage → approved/skipped/pending_review."""
    notes: list[str] = []
    seen = {r["instantly_email_id"] for r in
            db.table("prospect_messages").select("instantly_email_id").not_.is_("instantly_email_id", "null")
            .execute().data}
    prospects = _known_emails(db)
    new = 0
    for em in api.received_emails(campaign_id):
        eid = em.get("id")
        if not eid or eid in seen:
            continue
        sender = (em.get("from_address_email") or "").strip().lower()
        if not sender:
            continue
        if dry:
            new += 1
            continue
        prospect = prospects.get(sender)
        if prospect is None:
            row = db.table("prospects").upsert({
                "email": sender, "source": "inbound", "instantly_campaign_id": campaign_id,
                "status": "replied", "last_event_at": _now(),
            }, on_conflict="email").execute().data[0]
            prospect = {"id": row["id"], "email": sender, "status": "replied"}
            prospects[sender] = prospect
        full = db.table("prospects").select("first_name, instantly_lead_id").eq("id", prospect["id"]).execute().data[0]
        body = (em.get("body") or {}).get("text") or (em.get("body") or {}).get("html") or ""
        verdict = triage.triage(em.get("subject") or "", body, full.get("first_name"), sender=sender)
        db.table("prospect_messages").insert({
            "prospect_id": prospect["id"], "direction": "in", "instantly_email_id": eid,
            "instantly_thread_id": em.get("thread_id"), "eaccount": em.get("eaccount"),
            "subject": em.get("subject"), "body": body[:20000],
            "category": verdict["category"], "triaged_by": verdict["by"],
            "draft_reply": verdict["draft"], "reply_status": verdict["reply_status"],
            "received_at": em.get("timestamp_email"),
        }).execute()
        after = triage.STATUS_AFTER.get(verdict["category"])
        patch = {"last_reply_at": em.get("timestamp_email") or _now(), "last_event_at": _now()}
        if after and prospect["status"] not in ("client", "booked"):
            patch["status"] = after
        if verdict["category"] == "not_now":
            from datetime import timedelta
            patch["follow_up_at"] = (datetime.now(timezone.utc) + timedelta(days=90)).date().isoformat()
        db.table("prospects").update(patch).eq("id", prospect["id"]).execute()
        interest = triage.INTEREST_AFTER.get(verdict["category"])
        if interest is not None and full.get("instantly_lead_id"):
            try:
                api.set_interest(full["instantly_lead_id"], interest)
            except InstantlyError as err:
                notes.append(f"interest status for {sender}: {err}")
        log_event(db, "reply_received", note=verdict["category"], prospect_id=prospect["id"],
                  payload={"by": verdict["by"], "reply_status": verdict["reply_status"]})
        new += 1
    if new:
        notes.append(f"{'[dry] would ingest' if dry else 'Ingested'} {new} new repl{'y' if new == 1 else 'ies'}.")
    return new, notes


def send_approved(db, api: Instantly, dry: bool) -> tuple[int, list[str]]:
    """Every approved draft goes out from the mailbox that started the thread."""
    notes: list[str] = []
    rows = (db.table("prospect_messages").select("*, prospects(email, first_name, status)")
            .eq("reply_status", "approved").eq("direction", "in").execute().data)
    sent = 0
    for m in rows:
        if not m.get("draft_reply") or not m.get("instantly_email_id") or not m.get("eaccount"):
            db.table("prospect_messages").update({"reply_status": "failed"}).eq("id", m["id"]).execute()
            notes.append(f"reply {m['id'][:8]} missing draft/eaccount — marked failed")
            continue
        if dry:
            sent += 1
            continue
        subject = m.get("subject") or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}" if subject else "Re: Hubricon"
        try:
            api.reply(m["instantly_email_id"], m["eaccount"], subject, m["draft_reply"])
        except InstantlyError as err:
            db.table("prospect_messages").update({"reply_status": "failed"}).eq("id", m["id"]).execute()
            notes.append(f"reply to {m['prospects']['email']} failed: {err}")
            continue
        db.table("prospect_messages").update({"reply_status": "sent", "sent_at": _now()}).eq("id", m["id"]).execute()
        db.table("prospect_messages").insert({
            "prospect_id": m["prospect_id"], "direction": "out", "eaccount": m["eaccount"],
            "subject": subject, "body": m["draft_reply"], "reply_status": "sent", "sent_at": _now(),
            "instantly_thread_id": m.get("instantly_thread_id"),
        }).execute()
        log_event(db, "reply_sent", note=m.get("category"), prospect_id=m["prospect_id"])
        sent += 1
    if sent:
        notes.append(f"{'[dry] would send' if dry else 'Sent'} {sent} repl{'y' if sent == 1 else 'ies'}.")
    return sent, notes


def campaign_summary(api: Instantly, campaign_id: str) -> dict:
    try:
        a = api.campaign_analytics(campaign_id) or {}
    except InstantlyError:
        return {}
    keys = ("leads_count", "contacted_count", "emails_sent_count", "reply_count", "bounced_count",
            "unsubscribed_count", "total_opportunities", "completed_count")
    return {k: a.get(k) for k in keys if a.get(k) is not None}
