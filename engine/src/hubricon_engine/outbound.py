"""Outbound: the one Instantly campaign, who goes into it, and what comes back.

The campaign is created once from the spec below (idempotent by name),
activated only when at least one warmed mailbox exists, and fed from two
sources: lead lists the founder builds in Instantly (any list whose name
contains "hubricon") and, best effort, Instantly's SuperSearch database.
Replies are pulled from the unibox into prospect_messages for triage.
"""

import os
import hashlib
import html
from datetime import datetime, timezone

from . import icp, triage
from .instantly import CAMPAIGN_ACTIVE, Instantly, InstantlyError
from .onboarding import guess_name_parts, is_internal

CAMPAIGN_NAME = "Hubricon — Profit Teardown (PL FBA $3M–$20M)"
# Every name this campaign has carried starts with this. The ICP band in the
# suffix moves (the floor rose to $3M on 2026-09-13), and a lookup by the exact
# new name alone would miss the live campaign and create a second one mailing
# the same leads. The family finds it; ensure_campaign renames it in place.
CAMPAIGN_FAMILY = "Hubricon — Profit Teardown (PL FBA "
# instantly.py names 0-3; the interesting ones are negative and it does not.
# A campaign in any of these states accepts POST /activate with a 200 and then
# reads back at the same status, which is why the operator activated the
# campaign twelve times on 2026-09-03 and never sent an email.
CAMPAIGN_STATUS_NAMES = {
    0: "draft", 1: "active", 2: "paused", 3: "completed", 4: "running subsequences",
    -1: "accounts unhealthy", -2: "bounce protect", -99: "account suspended",
}
CALENDLY_URL = os.environ.get("CALENDLY_URL", "https://calendly.com/hubricon/margin-audit")
PER_MAILBOX_DAILY = 20          # a two-month-old domain: slow is the only safe speed
CAMPAIGN_DAILY_CAP = 60
LIST_MATCH = os.environ.get("INSTANTLY_LIST_MATCH", "hubricon").lower()
SUPERSEARCH_DAILY = int(os.environ.get("SUPERSEARCH_DAILY", "25"))

SUPERSEARCH_LIST = "Hubricon SuperSearch (auto)"
# Instantly's own filter vocabulary (enums from api.instantly.ai/openapi/api_v2.json).
# Revenue: the ICP is $3M–$20M, and Instantly's enum has no edge at either end.
# "$1 - 10M" straddles the floor, and nothing on a SuperSearch lead (or anywhere
# downstream of one) can tell a $2M brand from a $6M one, so asking for that band
# enrolls the brands whose every invoice voids. The floor is the guarantee's and
# the ceiling is a preference, so SuperSearch asks only for the band wholly above
# the floor and accepts that some of it is past $20M. $3–10M brands come from the
# harvest, which sizes every seller against icp.ICP_FLOOR_USD before a push.
SUPERSEARCH_FILTERS = {
    "title": {"include": ["Founder", "Co-Founder", "CEO", "Owner", "President"], "includeMode": "CONTAINS"},
    # The first 25 leads (2026-09-02) were half agencies, tools, 3PLs and
    # lenders that *talk about* Amazon FBA. Brands sell products; the
    # exclusions keep the people who sell services to brands out.
    "keyword_filter": {
        "include": "Amazon FBA, private label, Amazon brand, Amazon seller",
        "include_mode": "ANY",
        "exclude": "agency, agencies, consulting, consultant, marketing services, PPC management, "
                   "logistics, freight, 3PL, prep center, fulfillment services, software, SaaS, "
                   "platform, tool, analytics, aggregator, capital, lending, funding, investment, "
                   "accounting, bookkeeping, law firm, legal, coaching, course, mastermind",
    },
    "industry": {"exclude": ["Business Services", "Software & Internet", "Transportation & Storage",
                             "Financial Services", "Education", "Media & Entertainment"]},
    "revenue": ["$10 - 50M"],
    "employeeCount": ["0 - 25", "25 - 100"],
    "locations": {"include": [{"country": "United States"}]},
    "location_mode": "company",
    "skip_owned_leads": True,
    "show_one_lead_per_company": True,
}


def _footer(postal_address: str) -> str:
    # Both opt-outs stay; the sentence is short because every word here is a
    # word the copy above cannot spend (the step is capped at 130).
    return (f"<br/><br/>Hubricon · {postal_address}<br/>"
            "Reply \"no\" and I'll stop emailing. Unsubscribe link in the header.")


# Bump when the copy below changes: the operator PATCHes the live campaign's
# sequence in place on its next pass (threads already sent keep their history).
COPY_VERSION = "2026-09-08 $6,000 offer: conditional invoice every month, month one at no charge"


def effective_copy_version(proof_line: str | None) -> str:
    """COPY_VERSION, plus a fingerprint of the proof line when there is one.

    The proof line is the first sentence in this email that changes without a
    commit — it moves when a client consents, or withdraws. Folding it into
    the version is what makes `sync_copy` PATCH the live campaign on the next
    hourly pass after the first result publishes, with nobody bumping a
    constant."""
    if not proof_line:
        return COPY_VERSION
    return f"{COPY_VERSION}+proof:{hashlib.sha1(proof_line.encode()).hexdigest()[:8]}"


def campaign_spec(senders: list[str], postal_address: str, calendly_url: str = CALENDLY_URL,
                  daily_limit: int | None = None, proof_line: str | None = None) -> dict:
    """One plain-text email, no follow-ups (the founder's call, 2026-09-03: the
    first email is the one that gets answered; the rest is noise on a young
    domain).

    The copy opens on the reader's experience, not on us and not on the offer:
    a founder whose price and ads are both fine and whose payout still comes in
    light knows that feeling before he knows what Hubricon is. Then the gap gets
    a name, the offer answers it, and one word closes. Every claim is on the
    website — no card, testimonial and anonymized results as the price, teardown
    back in 24 hours.

    THE FREE MONTH IS UNCONDITIONAL AND THE INVOICE IS NOT. This was conditioned
    ("if I find enough to work with") to match a line on the site, because a
    cold email must never promise more than the page it links to. That line is
    gone: terms.html §3 always said the free month is free regardless of
    outcome, and since 2026-09-05 the day-30 check is code — the operator
    compares the ledger to the fee and simply does not create a subscription
    below it. So the honest sentence is now the stronger one, and it keeps the
    reader's instinct that a giveaway has a catch by saying exactly where the
    catch sits: not on the month, on the invoice at the end of it.

    ONE CTA. The booking link came out: a cold first touch that offers two doors
    gets neither opened, and nobody books a call with a stranger before they
    know what he found. calendly_url stays in the signature because the link is
    still the second step — triage.draft_for sends it the moment someone replies.

    NOT A WORD ABOUT WHICH PLATFORM. The earlier version said "{{companyName}}'s
    Amazon account". Since 2026-09-04 the harvest pushes Shopify stores into
    "Hubricon harvest (auto)" too, and enroll_from_lists takes every list whose
    name matches — so that sentence told Shopify founders they sell on Amazon.
    The steps below name a weight band and a SKU, which are true on both rate
    cards (FBA weight bands; USPS/UPS bands), and name neither storefront.
    """
    foot = _footer(postal_address)
    # "The track record isn't [built]" is true until the day it is false, and
    # on that day it becomes the one claim in this email a reader can check.
    # With a published result the paragraph says what the record is instead.
    why_free = (
        "Why no charge: Hubricon's new; the engine's built, the track record isn't. The price: a "
        "testimonial and your anonymized numbers.<br/><br/>"
    )
    if proof_line:
        why_free = (
            f"{html.escape(proof_line, quote=False)}<br/><br/>"
            "Why no charge: the price of the seat is what it was for them — a testimonial and your "
            "anonymized numbers.<br/><br/>"
        )
    step1 = (
        "Hi {{firstName}},<br/><br/>"
        "Your price is right. Your ads work. The payout still lands lighter than the "
        "spreadsheet said.<br/><br/>"
        "Usually a few quiet numbers: a weight band you're an ounce over, a SKU that goes "
        "negative once ads are allocated honestly.<br/><br/>"
        "I find them in {{companyName}}'s numbers and fix them in your account. A short video every "
        "two weeks; you keep the margin.<br/><br/>"
        # 2026-09-08, the founder's call: the price leads and the guarantee is the
        # rule the ledger and billing.py actually keep (cumulative, terms §3), with
        # month one demoted from headline to feature. Same economics as before.
        "$6,000 a month, flat; month one free. Any invoice your Profit Record hasn't covered is void. "
        "No card, nothing owed.<br/><br/>"
        + why_free +
        "Reply TEARDOWN; yours is back 24 hours after your exports land.<br/><br/>"
        "Hagen Simmons<br/>Hubricon" + foot
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
                {"type": "email", "delay": 0,
                 # The old subject led with our offer ("first month free, here's
                 # why"), which reads as a pitch before it is read as anything
                 # else. This one is about their money, and it is a claim the
                 # email then makes good on.
                 "variants": [{"subject": "the margin {{companyName}} already earned", "body": step1}]},
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

def ensure_campaign(db, api: Instantly, postal_address: str | None, dry: bool,
                    proof_line: str | None = None) -> tuple[str | None, list[str]]:
    """Returns (campaign_id, notes). Creates and activates when it can; explains when it can't.

    The address is stripped here, once, for every path below. A secret pasted
    into GitHub's textarea keeps the newline that came with it — the 2026-09-05
    value arrived as `'…75035\\n\\n'` — and that trailing whitespace would
    otherwise be embedded in the footer's HTML, stored as the copy fingerprint,
    and re-pushed as a change the first time someone re-pasted it cleanly.
    """
    postal_address = (postal_address or "").strip() or None
    notes: list[str] = []
    state = get_state(db, "instantly.campaign", {}) or {}
    campaign = None
    if state.get("id"):
        campaign = next((c for c in api.campaigns() if c.get("id") == state["id"]), None)
    if campaign is None:
        campaign = api.find_campaign(CAMPAIGN_NAME) or next(
            (c for c in api.campaigns() if (c.get("name") or "").startswith(CAMPAIGN_FAMILY)), None)

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
        spec = campaign_spec(senders, postal_address, proof_line=proof_line)
        if dry:
            notes.append(f"[dry] would create campaign {CAMPAIGN_NAME!r} from {len(senders)} mailbox(es)")
            return None, notes
        campaign = api.create_campaign(spec)
        notes.append(f"Created campaign {CAMPAIGN_NAME!r} ({campaign.get('id')}) sending from {', '.join(senders)}")
        log_event(db, "campaign_created", payload={"id": campaign.get("id"), "senders": senders})
        state["copy_version"] = effective_copy_version(proof_line)  # born from the current copy
        state["copy_address"] = postal_address  # ...and from the address in it

    cid = campaign.get("id")
    old_name = campaign.get("name")
    if old_name and old_name != CAMPAIGN_NAME:
        if dry:
            notes.append(f"[dry] would rename campaign {cid} from {old_name!r} to {CAMPAIGN_NAME!r}")
        else:
            api.update_campaign(cid, {"name": CAMPAIGN_NAME})
            campaign = {**campaign, "name": CAMPAIGN_NAME}
            notes.append(f"Renamed campaign {cid} from {old_name!r} to {CAMPAIGN_NAME!r} (same campaign, same leads).")
            log_event(db, "campaign_renamed", payload={"id": cid, "from": old_name, "to": CAMPAIGN_NAME})
    state = {**state, "id": cid, "name": campaign.get("name"), "senders": senders}
    set_state(db, "instantly.campaign", state)
    notes += sync_copy(db, api, cid, state, postal_address, dry, proof_line)

    before = campaign.get("status")
    if "status" not in campaign:
        # A missing key is not the same as "not active": it would make the
        # comparison below true forever and re-activate an active campaign
        # every hour. Say so rather than silently looping.
        notes.append(f"Instantly returned no 'status' field for campaign {cid}; "
                     f"keys were {sorted(campaign)[:12]}.")
    if before != CAMPAIGN_ACTIVE:
        if not senders:
            notes.append("Campaign exists but stays paused: no warmed mailbox yet.")
        elif dry:
            notes.append(f"[dry] would activate campaign {cid}")
        else:
            api.activate_campaign(cid)
            # Read the status back. POST /activate answers 200 even when the
            # workspace refuses to send (suspended, unpaid, mailboxes
            # unhealthy), so the only way to know it took is to look again.
            after_obj = next((c for c in api.campaigns() if c.get("id") == cid), None) or {}
            after = after_obj.get("status")
            state["activation_attempts"] = int(state.get("activation_attempts") or 0) + 1
            state["status"], state["status_name"] = after, _status_name(after)
            state["activated_at"] = _now()
            set_state(db, "instantly.campaign", state)
            log_event(db, "campaign_activated",
                      payload={"id": cid, "status_before": before, "status_after": after,
                               "status_name": _status_name(after),
                               "attempt": state["activation_attempts"]})
            if after == CAMPAIGN_ACTIVE:
                notes.append(f"Activated campaign {cid}; Instantly now reports active.")
            else:
                notes.append(
                    f"ACTIVATION DID NOT STICK: asked Instantly to activate {cid}, it still reports "
                    f"status {after} ({_status_name(after)}) after attempt "
                    f"{state['activation_attempts']}. This is an account-side block, not a code bug — "
                    f"check billing, mailbox health and the campaign's sending accounts in the dashboard.")
    return cid, notes


def _status_name(status) -> str:
    return CAMPAIGN_STATUS_NAMES.get(status, f"unknown status {status!r}")


def sync_copy(db, api: Instantly, cid: str, state: dict, postal_address: str | None, dry: bool,
              proof_line: str | None = None) -> list[str]:
    """The live campaign follows campaign_spec. When COPY_VERSION moves, the
    sequence is PATCHed in place: threads already sent keep their history, and
    nobody receives a follow-up the new copy no longer has.

    The postal address is the second thing that decides those bytes, and it
    lives in a secret rather than in this file — so it is compared too. Gating
    on COPY_VERSION alone meant a corrected POSTAL_ADDRESS never reached the
    campaign: on 2026-09-05 the secret held a test fixture, 36 emails went out
    carrying a mailing address that does not exist, and fixing the secret would
    have changed nothing until someone thought to bump a constant. Comparing the
    address makes the correction land by itself on the next pass.
    """
    version = effective_copy_version(proof_line)
    address_changed = (state.get("copy_address") or None) != (postal_address or None)
    if state.get("copy_version") == version and not address_changed:
        return []
    if not postal_address:
        return ["Campaign copy not updated: POSTAL_ADDRESS is empty (the footer needs it)."]
    why = ("the postal address changed" if state.get("copy_version") == version
           else f"the copy moved to {version!r}")
    spec = campaign_spec(state.get("senders") or [], postal_address, proof_line=proof_line)
    if dry:
        return [f"[dry] would update the campaign copy — {why}"]
    api.update_campaign(cid, {"sequences": spec["sequences"]})
    set_state(db, "instantly.campaign", {**state, "copy_version": version,
                                         "copy_address": postal_address})
    log_event(db, "campaign_copy_updated", payload={"id": cid, "copy_version": version,
                                                    "postal_address": postal_address,
                                                    "steps": len(spec["sequences"][0]["steps"])})
    return [f"Updated the campaign copy — {why}: "
            f"{len(spec['sequences'][0]['steps'])} step(s), no follow-ups."]


# -- enrollment ----------------------------------------------------------------

def enroll_one(api: Instantly, campaign_id: str, email: str, first: str | None, last: str | None,
               company: str | None, website: str | None) -> dict:
    """Put one lead into the campaign, even though it is already in a list.

    THE BUG THIS EXISTS FOR. instantly.create_lead sends skip_if_in_workspace,
    which means "do not add anyone whose address exists anywhere in this
    workspace". Every lead source here writes to a lead list first — the
    harvest pushes to "Hubricon harvest (auto)", the SuperSearch job fills
    "Hubricon SuperSearch (auto)" — and enrollment then reads those lists and
    tries to add each address to the campaign. Instantly sees the address
    already in the workspace, in the very list we just read it from, and skips
    it. The campaign therefore stayed empty: on 2026-09-03 it was active, with a
    valid schedule, two warmed mailboxes attached and a daily limit of 40, and
    leads_in_campaign returned 0 while 88 prospects here believed they were
    enrolled. enroll_from_lists then stored the LIST lead's id as
    instantly_lead_id, which is why every row looked enrolled and none was.

    skip_if_in_campaign stays on: that is the guard that actually matters, and
    it keeps this idempotent. The one-word fix belongs in instantly.py, which
    another session owns, so this calls the endpoint directly and works either
    way.
    """
    body = {
        "campaign": campaign_id,
        "email": email,
        "skip_if_in_workspace": False,   # the list IS the workspace; see above
        "skip_if_in_campaign": True,
        "verify_leads_on_import": True,
    }
    for k, v in (("first_name", first), ("last_name", last),
                 ("company_name", company), ("website", website)):
        if v:
            body[k] = v
    return api._call("POST", "/leads", body=body) or {}


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
    held: dict = {}   # off-ICP rows, counted by reason and never enrolled
    for lst in lists:
        leads = api.leads_in_list(lst["id"])
        before = added
        skipped_no_name = 0
        skipped_no_company = 0
        for lead in leads:
            email = (lead.get("email") or "").strip().lower()
            if not email or email in known or is_internal(email):
                continue
            if added >= cap:
                break
            first, last = lead.get("first_name"), lead.get("last_name")
            if not first:
                first, last = guess_name_parts(lead.get("name") or lead.get("full_name"))
            if not first:
                skipped_no_name += 1
                continue  # "Hi {{firstName}}" must never render empty
            # The same rule for the company, which the copy leans on harder:
            # the subject IS "the margin {{companyName}} already earned", so an
            # unset variable sends "the margin  already earned" and a body that
            # says "I find them in 's numbers". enroll_one only sets the field
            # when it is truthy, so a lead with no company reaches Instantly
            # with the variable undefined. Harvest leads always carry a brand;
            # SuperSearch and hand-built lists do not always.
            if not (lead.get("company_name") or "").strip():
                skipped_no_company += 1
                continue
            # The ICP gate runs here rather than at push: a lead that never
            # enters the campaign cannot spend a send on a two-month-old domain.
            company, site = lead.get("company_name"), lead.get("website")
            bucket, why = icp.off_icp(company, email, site)
            if not bucket and icp.domain_mismatch(email, site):
                bucket, why = "domain_mismatch", f"{email} is not on {site}"
            if not bucket and icp.bad_greeting(first):
                bucket, why = "bad_greeting", f'"Hi {first}," reads as a mistake'
            if not bucket and icp.is_role_inbox(email):
                bucket, why = "role_inbox", "reaches a support queue; needs a named owner first"
            if bucket:
                held[bucket] = held.get(bucket, 0) + 1
                if not dry:
                    db.table("prospects").upsert({
                        "email": email, "first_name": first, "last_name": last,
                        "company_name": company, "website": site,
                        "source": "supersearch" if "supersearch" in (lst.get("name") or "").lower() else "instantly_list",
                        "status": "dq", "fit_notes": f"{bucket} — {why}", "last_event_at": _now(),
                    }, on_conflict="email").execute()
                    known[email] = {"email": email}
                continue
            if dry:
                added += 1
                continue
            try:
                created = enroll_one(api, campaign_id, email, first, last,
                                     lead.get("company_name"), lead.get("website"))
            except InstantlyError as err:
                notes.append(f"enroll {email}: {err}")
                continue
            # Store the campaign lead's id, not the list lead's. They are two
            # objects, and only the campaign one is ever emailed.
            new_id = created.get("id")
            if not new_id:
                notes.append(f"enroll {email}: Instantly returned no lead id; it may already be enrolled.")
            db.table("prospects").upsert({
                "email": email, "first_name": first, "last_name": last,
                "company_name": lead.get("company_name"), "website": lead.get("website"),
                "source": "supersearch" if "supersearch" in (lst.get("name") or "").lower() else "instantly_list",
                "instantly_lead_id": new_id or lead.get("id"),
                "instantly_campaign_id": campaign_id, "status": "queued", "last_event_at": _now(),
            }, on_conflict="email").execute()
            known[email] = {"email": email}
            added += 1
        notes.append(f"  list '{lst.get('name')}': {len(leads)} lead(s) in Instantly, {added - before} enrolled now"
                     + (f", {skipped_no_name} without a first name" if skipped_no_name else "")
                     + (f", {skipped_no_company} without a company name" if skipped_no_company else ""))
    notes.append(f"{'[dry] would enroll' if dry else 'Enrolled'} {added} lead(s) from {len(lists)} list(s).")
    if held:
        notes.append("  held back as off-ICP (never enrolled): "
                     + ", ".join(f"{k} {v}" for k, v in sorted(held.items())))
    return added, notes


def repair_enrollment(db, api: Instantly, campaign_id: str, dry: bool) -> tuple[int, list[str]]:
    """Enroll queued prospects that the campaign does not actually contain.

    enroll_from_lists skips any address already in `prospects`, so the 88 rows
    that were written as 'queued' while the create call was silently skipping
    them would never have been retried: permanently queued, permanently
    unsent. This reconciles the two sides — what we believe against what
    Instantly holds — and enrolls the difference.

    It is idempotent and self-limiting: once a prospect really is in the
    campaign it is never touched again, so this costs one roster read a pass
    and nothing else.
    """
    notes: list[str] = []
    queued = db.table("prospects").select("email, first_name, last_name, company_name, website") \
        .eq("status", "queued").execute().data
    if not queued:
        return 0, notes
    try:
        in_campaign = {(l.get("email") or "").lower() for l in api.leads_in_campaign(campaign_id)}
    except InstantlyError as err:
        return 0, [f"Could not read the campaign roster to repair enrollment: {err}"]
    missing = [p for p in queued if (p.get("email") or "").lower() not in in_campaign]
    if not missing:
        return 0, notes
    if dry:
        return 0, [f"[dry] would enroll {len(missing)} queued prospect(s) the campaign does not hold"]
    fixed = 0
    for p in missing:
        try:
            created = enroll_one(api, campaign_id, p["email"], p.get("first_name"), p.get("last_name"),
                                 p.get("company_name"), p.get("website"))
        except InstantlyError as err:
            notes.append(f"  repair {p['email']}: {err}")
            continue
        if created.get("id"):
            db.table("prospects").update({"instantly_lead_id": created["id"], "last_event_at": _now()}) \
                .eq("email", p["email"]).execute()
        fixed += 1
    if fixed:
        notes.append(f"Repaired enrollment: {fixed} queued prospect(s) were not in the campaign and now are. "
                     f"They had been sitting unsent because create_lead was skipping them as workspace duplicates.")
        log_event(db, "enrollment_repaired", payload={"count": fixed, "campaign": campaign_id})
    return fixed, notes


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
    new = contacted = held_off_icp = 0
    for lead in api.leads_in_campaign(campaign_id):
        email = (lead.get("email") or "").strip().lower()
        if not email or is_internal(email):
            continue
        touched = any(lead.get(k) for k in ("timestamp_last_contact", "last_contacted", "timestamp_last_touch",
                                              "email_open_count", "email_reply_count", "email_click_count"))
        if email not in known:
            first, last = lead.get("first_name"), lead.get("last_name")
            # Leads can reach the campaign roster without passing through
            # enroll_from_lists (the SuperSearch job, or the founder adding one
            # by hand in Instantly), so the ICP gate runs on this path too.
            # Already-contacted leads keep 'contacted': that is history, not a
            # decision, and rewriting it would corrupt the scoreboard.
            bucket, why = icp.off_icp(lead.get("company_name"), email, lead.get("website"))
            status = "contacted" if touched else ("dq" if bucket else "queued")
            db.table("prospects").upsert({
                "email": email, "first_name": first, "last_name": last,
                "company_name": lead.get("company_name"), "website": lead.get("website"),
                "source": "supersearch", "instantly_lead_id": lead.get("id"),
                "instantly_campaign_id": campaign_id,
                "status": status, "last_event_at": _now(),
                **({"fit_notes": f"{bucket} — {why}"} if bucket else {}),
            }, on_conflict="email").execute()
            if bucket:
                held_off_icp += 1
            new += 1
        elif touched and known[email]["status"] == "queued":
            db.table("prospects").update({"status": "contacted", "last_event_at": _now()}).eq("email", email).execute()
            contacted += 1
    if new or contacted:
        notes.append(f"Roster sync: {new} new prospect(s) from Instantly, {contacted} marked contacted"
                     + (f", {held_off_icp} of the new ones disqualified as off-ICP" if held_off_icp else "") + ".")
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
                  payload={"by": verdict["by"], "reply_status": verdict["reply_status"],
                           **({"reason": verdict["reason"]} if verdict.get("reason") else {})})
        # A reply from an address a teardown went to is that teardown's reply:
        # the one join that lets `teardown stats` say which findings convert.
        try:
            from . import loop
            loop.attribute_reply(db, sender, verdict["category"])
        except Exception as err:
            notes.append(f"teardown attribution for {sender}: {err}")
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


ANALYTICS_KEYS = ("leads_count", "contacted_count", "emails_sent_count", "reply_count", "bounced_count",
                  "unsubscribed_count", "total_opportunities", "completed_count")


def campaign_summary(api: Instantly, campaign_id: str) -> dict:
    """Instantly's own counters for the campaign, or a description of why not.

    This used to return {} on any error and the operator only stored a truthy
    result, so a failing analytics call left no trace anywhere: on 2026-09-03
    operator_state had no 'instantly.analytics' key at all after twenty hours
    of hourly passes. An error is now a value, so it lands in the digest.
    """
    try:
        a = api.campaign_analytics(campaign_id) or {}
    except InstantlyError as err:
        a = {}
        first_error = f"{err.status} on {err.path}: {(err.body or '')[:200]}"
    else:
        first_error = ""
    out = {k: a.get(k) for k in ANALYTICS_KEYS if a.get(k) is not None}
    if out:
        return out
    # instantly.py sends ?campaign_id=; the v2 docs name that parameter `id`.
    # A wrong name is either rejected or ignored, and when it is ignored the
    # endpoint answers for every campaign at once. Try the other spelling
    # before concluding anything. The one-word fix belongs in instantly.py,
    # which another session owns; this keeps working either way.
    try:
        alt = api._call("GET", "/campaigns/analytics", params={"id": campaign_id})
        if isinstance(alt, list):
            alt = next((c for c in alt if c.get("campaign_id") == campaign_id), alt[0] if alt else {})
        alt = alt or {}
        out = {k: alt.get(k) for k in ANALYTICS_KEYS if alt.get(k) is not None}
        if out:
            return {**out, "via": "id= (campaign_id= returned nothing)"}
        return {"error": first_error or "analytics returned no counts", "keys": sorted(alt)[:20]}
    except InstantlyError as err:
        return {"error": first_error or f"{err.status} on {err.path}: {(err.body or '')[:200]}"}
    except Exception as err:  # never let a diagnostic break the pass
        return {"error": first_error or f"{type(err).__name__}: {err}"}


def health(db, api: Instantly, campaign_id: str | None) -> dict:
    """Everything we can learn about why the campaign is or is not sending.

    Read-only. Written to operator_state['instantly.health'] every pass so the
    answer is in the database rather than in a GitHub Actions log: the founder's
    Mac has no INSTANTLY_API_KEY and no gh CLI, so the DB is the only channel
    that reaches both machines.
    """
    out: dict = {"as_of": _now(), "campaign_id": campaign_id}
    verdicts: list[str] = []

    try:
        accounts = api.accounts()
    except InstantlyError as err:
        accounts, verdicts = [], verdicts + [f"could not read mailboxes: {err}"]
    out["mailboxes"] = [{"email": a.get("email"), "status": a.get("status"),
                         "warmup_status": a.get("warmup_status"),
                         "daily_limit": a.get("daily_limit")} for a in accounts]
    ready = [a.get("email") for a in accounts if a.get("status") == 1 and a.get("warmup_status") == 1]
    if not ready:
        verdicts.append("no mailbox is both connected and past warmup — nothing can send")

    campaign = None
    if campaign_id:
        try:
            campaign = next((c for c in api.campaigns() if c.get("id") == campaign_id), None)
        except InstantlyError as err:
            verdicts.append(f"could not read the campaign: {err}")
    if campaign is None:
        verdicts.append("the campaign does not exist in Instantly")
    else:
        status = campaign.get("status")
        attached = campaign.get("email_list") or []
        out["campaign"] = {"status": status, "status_name": _status_name(status),
                           "email_list": attached, "daily_limit": campaign.get("daily_limit"),
                           "has_schedule": bool(campaign.get("campaign_schedule")),
                           "keys": sorted(campaign)[:30]}
        if status != CAMPAIGN_ACTIVE:
            verdicts.append(f"campaign status {status} ({_status_name(status)}) — not sending")
        if not attached:
            verdicts.append("no sending accounts are attached to the campaign (email_list is empty)")
        else:
            missing = [e for e in ready if e not in attached]
            if missing:
                verdicts.append(f"warmed mailbox not attached to the campaign: {', '.join(missing)}")
        if not campaign.get("campaign_schedule"):
            verdicts.append("the campaign has no sending schedule — an active campaign with no schedule never sends")

    if campaign_id:
        try:
            leads = api.leads_in_campaign(campaign_id)
        except InstantlyError as err:
            leads = []
            verdicts.append(f"could not read campaign leads: {err}")
        contacted = sum(1 for l in leads if l.get("timestamp_last_contact"))
        verif: dict = {}
        for l in leads:
            v = l.get("verification_status")
            verif[str(v)] = verif.get(str(v), 0) + 1
        out["leads"] = {"total": len(leads), "contacted": contacted, "verification_status": verif,
                        "keys": sorted(leads[0])[:30] if leads else []}
        if leads and contacted == 0:
            verdicts.append(f"{len(leads)} leads are enrolled and not one has ever been contacted")

    out["analytics"] = campaign_summary(api, campaign_id) if campaign_id else {"error": "no campaign"}
    if out["analytics"].get("error") and out.get("leads"):
        # /campaigns/analytics has never returned counts for this workspace.
        # The lead roster is better evidence anyway: it is what Instantly will
        # actually send to, counted one row at a time, and we have already read
        # it. Derive the numbers rather than reporting a blank.
        lv = out["leads"]
        out["analytics"] = {
            "leads_count": lv["total"],
            "contacted_count": lv["contacted"],
            "reply_count": sum(1 for l in leads if l.get("email_reply_count")),
            "via": "counted from the campaign's lead roster; "
                   f"/campaigns/analytics said: {out['analytics']['error']}",
        }
    elif out["analytics"].get("error"):
        verdicts.append(f"analytics unavailable: {out['analytics']['error']}")

    try:
        rows = db.table("prospects").select("status").execute().data
        by_status: dict = {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        out["prospects"] = by_status
        if by_status.get("contacted", 0) == 0 and sum(by_status.values()) > 0:
            verdicts.append(f"{sum(by_status.values())} prospects on file, none marked contacted")
    except Exception as err:
        verdicts.append(f"could not read prospects: {err}")

    out["verdicts"] = verdicts
    return out
