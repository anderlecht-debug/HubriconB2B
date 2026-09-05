"""Approved teardowns out through Instantly, which already does the hard part.

COLD_ENGINE.md §2.4 asks for sending-domain rotation, per-domain daily caps, and
automatic pause on bounce or complaint rate. Instantly does all three, on two
warmed domains this business already pays for, and it is where the reply triage
already reads from. Building a second dispatcher beside it would mean warming
domains twice, handling bounces twice, and reconciling two records of who was
contacted — for no gain.

**The campaign is a delivery shell and nothing else.** Its subject and body are a
single merge field each, so the bytes that reach a prospect are the bytes the
founder approved. The alternative — a campaign holding fixed prose with the
numbers merged into it — puts a second author between the finding and the inbox,
and every divergence between what `teardown show` prints and what Instantly
sends would be invisible until a stranger read it.

Nothing here decides who to contact. `compliance.authorise` does, for every lead,
immediately before it is pushed; a teardown that fails the check is left in the
queue with the reason rather than sent.
"""

from __future__ import annotations

import html
import os

from .. import outbound
from ..instantly import Instantly, InstantlyError
from . import compliance, copy as copymod, settings
from .sources.harvest import HarvestSource

CAMPAIGN_NAME = "Hubricon — Profit Teardown (per-prospect)"
STATE_KEY = "instantly.teardown_campaign"
# Per mailbox per day. The founder's two domains are warmed and on Instantly;
# 30 a day each is the number he is aiming at, and Instantly enforces it.
PER_MAILBOX_DAILY = int(os.environ.get("COLD_PER_MAILBOX_DAILY", "30"))


def as_html(body: str) -> str:
    """Plain text to the HTML Instantly wants, escaping first.

    A brand called `Barnes & Noble` or a title with a `<` in it would otherwise
    arrive as broken markup or, worse, as markup.
    """
    return html.escape(body, quote=False).replace("\n", "<br/>")


def campaign_spec(senders: list[str], daily_limit: int | None = None) -> dict:
    """One step, no follow-ups, both fields merged from the lead.

    Settings mirror the main campaign deliberately: plain text, no open or link
    tracking, stop on reply, stop for the whole company, unsubscribe header on,
    risky contacts refused. The founder's 2026-09-03 call that the first email
    is the one that gets answered holds here too — a teardown that did not land
    is not improved by sending it again.
    """
    limit = daily_limit or PER_MAILBOX_DAILY * max(1, len(senders))
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
                {"type": "email", "delay": 0,
                 "variants": [{"subject": "{{teardownSubject}}", "body": "{{teardownBody}}"}]},
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


def ensure_campaign(db, api: Instantly, dry: bool = False) -> tuple[str | None, list[str]]:
    """Find, create or re-point the teardown campaign. → (id, notes)."""
    notes: list[str] = []
    state = outbound.get_state(db, STATE_KEY, {}) or {}
    campaign = None
    if state.get("id"):
        campaign = next((c for c in api.campaigns() if c.get("id") == state["id"]), None)
    if campaign is None:
        campaign = api.find_campaign(CAMPAIGN_NAME)

    senders = [a["email"] for a in api.ready_senders()]
    if not senders:
        notes.append("No mailbox in Instantly is connected and past warmup, so no teardown "
                     "campaign was created.")
        return None, notes
    if campaign is None:
        if not compliance.postal_address():
            notes.append("POSTAL_ADDRESS is not set; CAN-SPAM needs a mailing address in every "
                         "cold email, and the body carries it.")
            return None, notes
        if dry:
            notes.append(f"[dry] would create '{CAMPAIGN_NAME}' across {len(senders)} mailbox(es)")
            return None, notes
        campaign = api.create_campaign(campaign_spec(senders))
        notes.append(f"Created '{CAMPAIGN_NAME}' across {len(senders)} mailbox(es).")
    cid = campaign.get("id")
    if not dry:
        # Keep the sender list and the caps current: a mailbox that finished
        # warming after the campaign was made would otherwise never be used.
        try:
            api.update_campaign(cid, {"email_list": senders,
                                      "daily_limit": PER_MAILBOX_DAILY * len(senders),
                                      "daily_max_leads": PER_MAILBOX_DAILY * len(senders)})
            api.activate_campaign(cid)
        except InstantlyError as err:
            notes.append(f"Campaign {cid} could not be activated: {err}")
        outbound.set_state(db, STATE_KEY, {"id": cid, "senders": senders})
    return cid, notes


def approved(db, limit: int = 100) -> list[dict]:
    """Teardowns the founder approved and that have not gone out."""
    return (db.table("teardowns").select("*").eq("status", "approved")
            .order("created_at").limit(limit).execute().data)


def push(db, api: Instantly | None, dry: bool = False, limit: int = 100,
         log=print) -> tuple[int, list[str]]:
    """Every approved teardown that clears compliance, into the campaign.

    Returns (sent, notes). A teardown that fails the check keeps its approved
    status and is reported: the founder decided to send it, and the reason it
    could not go is something he needs to see rather than a silent skip.
    """
    notes: list[str] = []
    rows = approved(db, limit)
    if not rows:
        return 0, notes
    if api is None:
        return 0, ["INSTANTLY_API_KEY is not set here, so nothing was dispatched. "
                   f"{len(rows)} teardown(s) are approved and waiting."]
    cid, made = ensure_campaign(db, api, dry)
    notes += made
    if not cid and not dry:
        return 0, notes
    if not cid:
        # A rehearsal is most useful before the campaign exists — it is the
        # first thing anyone runs. Carry on and name who would go; nothing is
        # written either way.
        cid = "(campaign not created yet)"

    source = HarvestSource(db)
    senders = (outbound.get_state(db, STATE_KEY, {}) or {}).get("senders") or []
    sent = 0
    for row in rows:
        snap = source.snapshot(row["prospect_key"])
        if snap is None:
            notes.append(f"{row['prospect_key']}: the prospect row is gone; not sent.")
            continue
        # The domain is Instantly's to choose from the pool, so the cap check is
        # against the pool rather than one name. Instantly enforces the per
        # mailbox limit itself; this is the belt to its braces.
        clearance = compliance.authorise(db, snap, sending_domain=_pool_domain(senders))
        if not clearance.ok:
            notes.append(f"{snap.display_name}: not sent — {clearance.reason}")
            continue
        if not row.get("subject") or not row.get("body"):
            notes.append(f"{snap.display_name}: no subject or body on the teardown; not sent.")
            continue
        if dry:
            notes.append(f"[dry] would send '{row['subject']}' to {snap.email}")
            sent += 1
            continue
        try:
            lead = api.create_lead(
                cid, snap.email,
                first_name=snap.first_name, last_name=snap.last_name,
                company_name=snap.display_name, website=snap.website,
                custom={"teardownSubject": row["subject"],
                        "teardownBody": as_html(row["body"]),
                        "teardownUrl": copymod.teardown_url(row["token"])})
        except InstantlyError as err:
            notes.append(f"{snap.display_name}: Instantly refused the lead — {err}")
            continue
        compliance.record_send(db, clearance.send, template_id=copymod.TEMPLATE_ID,
                               subject=row["subject"], teardown_id=row["id"],
                               provider_message_id=(lead or {}).get("id"))
        db.table("teardowns").update({"status": "sent"}).eq("id", row["id"]).execute()
        outbound.log_event(db, "cold.teardown_sent",
                           f"{snap.display_name} <{snap.email}>: {row['subject']}")
        sent += 1
    if sent and not dry:
        notes.append(f"Dispatched {sent} teardown(s) into '{CAMPAIGN_NAME}'.")
    return sent, notes


def _pool_domain(senders: list[str]) -> str | None:
    """One name for the whole sending pool, for the frequency ledger.

    Instantly picks the mailbox, so which domain a given teardown left from is
    not knowable here — recording a guess would make outreach_sends wrong. The
    pool is recorded instead, and Instantly's own per-mailbox limit is what
    actually paces the send.
    """
    domains = sorted({(s.split("@")[-1] or "").lower() for s in senders if "@" in s})
    return "+".join(domains) or None
