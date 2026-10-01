"""Client provisioning and the journey's emails, in Python so the hourly
operator can do what scripts/new-client.mjs and scripts/invite-user.mjs do by
hand: find-or-create the client, mint a fresh intake link, give them a portal
seat, and send the branded email from Hagen's address through Resend.

Each email belongs to a stage (lifecycle.py): the call prep on booking, the
first read when files are in, the upload link again after the call, the letter
that confirms a yes. None of them assumes a yes that has not been given.
"""

import hashlib
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from . import lifecycle, notify

TOKEN_LIFETIME_DAYS = 90
INTAKE_BASE_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com")
PORTAL_URL = INTAKE_BASE_URL + "/portal"     # mirrors cli.PORTAL_URL and operator.PORTAL_URL
# A Calendly event whose name says kickoff is a client's follow-up call, not an
# application: the operator links it and sends nothing (operator.bookings), and
# the unit economics count it at the kickoff's length (economics.kickoff_dates).
KICKOFF_EVENT = re.compile(r"kick\s*-?\s*off", re.I)
EXEC_EMAIL = os.environ.get("EXECUTION_EMAIL", "hagen.simmons@hubricon.com")
CALENDLY_URL = os.environ.get("CALENDLY_URL", "https://calendly.com/hubricon/margin-audit")
FROM = os.environ.get("EMAIL_FROM", "Hagen Simmons <hagen.simmons@hubricon.com>")
# The weekly sweep (.github/workflows/sweep.yml: "0 11 * * 1"). A client is told
# the date of the next one; never an hour, because GitHub runs cron late.
SWEEP_WEEKDAY = 0
SWEEP_HOUR_UTC = 11
# The migration that adds the 'declined' status, clients.declined_at and the
# call_prep / agreed touch kinds. Code that writes any of them asks first.
LIFECYCLE_MIGRATION = "supabase/migrations/20261001000003_journey_lifecycle.sql"

# The founder's own addresses and the dry-run workspace: never a prospect,
# never a client, never counted.
INTERNAL_DOMAINS = ("hubricon.com", "gethubricon.com", "hubricon.internal")
INTERNAL_EMAILS = {"hagen.hds@gmail.com", "hagend.s25@gmail.com", "hagenhds@gmail.com"}
INTERNAL_NAMES = {"john doe", "jane doe", "dry runner", "test"}


def is_internal(email: str | None, name: str | None = None) -> bool:
    e = (email or "").strip().lower()
    if not e or e in INTERNAL_EMAILS:
        return True
    domain = e.rsplit("@", 1)[-1]
    if domain in INTERNAL_DOMAINS or domain.endswith(".internal") or domain in ("example.com", "test.com"):
        return True
    if (name or "").strip().lower() in INTERNAL_NAMES:
        return True
    return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint_token(db, client_id: str, label: str, rotate: bool = True) -> str:
    """Mints an intake link: raw token returned, only its hash stored. With
    rotate (the default) earlier links stop working; a nudge passes False so
    the link in the welcome email keeps working too."""
    if rotate:
        db.rpc("revoke_intake_tokens", {"p_client_id": client_id}).execute()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = (datetime.now(timezone.utc) + timedelta(days=TOKEN_LIFETIME_DAYS)).isoformat()
    db.rpc("create_intake_token", {
        "p_client_id": client_id, "p_token_hash": token_hash, "p_label": label, "p_expires_at": expires,
    }).execute()
    return token


def ensure_portal_seat(db, client_id: str, email: str) -> str | None:
    """Auth user (magic-link sign-in, no password) linked to the workspace.
    Returns the auth user id, or None if the admin API is unavailable."""
    try:
        existing = None
        page = 1
        while True:
            users = db.auth.admin.list_users(page=page, per_page=200)
            for u in users or []:
                if (u.email or "").lower() == email:
                    existing = u
                    break
            if existing or not users or len(users) < 200:
                break
            page += 1
        if existing:
            user_id = existing.id
        else:
            created = db.auth.admin.create_user({"email": email, "email_confirm": True})
            user_id = created.user.id
        db.table("client_users").upsert(
            {"user_id": user_id, "client_id": client_id, "role": "owner"}, on_conflict="user_id,client_id"
        ).execute()
        return user_id
    except Exception as err:  # portal seat is a nicety on day one; the upload link is what matters
        print(f"  portal seat for {email} not created: {err}")
        return None


_PLATFORM_WORDS = {"amazon": "amazon", "shopify": "shopify", "both": "both"}


def platform_from_answers(answers: dict | None) -> str | None:
    """The 'Where you sell' answer from the site's application gate.

    The gate rides its answers along on the Calendly booking as one
    utm_content string ("rev:…|model:…|skus:…|fit:…|channel:Shopify"), and
    the cloud routine may store that raw string or a parsed key. Read both
    shapes; anything unrecognised returns None, which leaves the column's
    'amazon' default alone rather than guessing."""
    if not answers:
        return None
    direct = str(answers.get("channel") or answers.get("platform") or "").strip().lower()
    if direct in _PLATFORM_WORDS:
        return _PLATFORM_WORDS[direct]
    for value in answers.values():
        m = re.search(r"channel\s*[:=]\s*([A-Za-z]+)", str(value))
        if m and m.group(1).lower() in _PLATFORM_WORDS:
            return _PLATFORM_WORDS[m.group(1).lower()]
    return None


def provision(db, email: str, name: str | None = None, company: str | None = None,
              platform: str | None = None) -> tuple[dict, str, bool]:
    """Find-or-create the client, mint a fresh intake link, seat them in the
    portal. Returns (client, intake_link, created).

    `platform` is what the prospect said on the application gate. It is
    written on creation, and later only when the row still carries the
    column's 'amazon' default — a stated answer beats a default, but never
    overwrites a platform someone set deliberately."""
    email = email.strip().lower()
    rows = db.table("clients").select("*").eq("contact_email", email).execute().data
    created = False
    if rows:
        client = rows[0]
        patch = {}
        if name and not client.get("contact_name"):
            patch["contact_name"] = name
        if company and not client.get("company_name"):
            patch["company_name"] = company
        if platform and platform != "amazon" and (client.get("platform") or "amazon") == "amazon":
            patch["platform"] = platform
        if patch:
            client = db.table("clients").update(patch).eq("id", client["id"]).execute().data[0]
    else:
        insert = {"contact_email": email, "status": "pending", "platform": platform or "amazon"}
        if name:
            insert["contact_name"] = name
        if company:
            insert["company_name"] = company
        client = db.table("clients").insert(insert).execute().data[0]
        created = True
    token = mint_token(db, client["id"], "audit intake")
    ensure_portal_seat(db, client["id"], email)
    return client, f"{INTAKE_BASE_URL}/intake?t={token}", created


def lifecycle_schema_error(db) -> str | None:
    """None when migration 20261001000003 is applied, else the database's own
    words. It adds clients.declined_at and, in the same file, the call_prep and
    agreed touch kinds, so one probe answers for all three."""
    try:
        db.table("clients").select("declined_at").limit(1).execute()
        return None
    except Exception as err:
        return str(err)[:200] or type(err).__name__


# -- the first read: when it is ready -------------------------------------------

# The files a first read cannot do without, per channel it reads, as the intake
# names them (uploads.report_type, ingest.PARSERS). Amazon: sales and traffic,
# and the fee report. Shopify: the orders and the products.
CORE_FILES = {
    "amazon": ("business_report", "sku_economics"),
    "shopify": ("shopify_orders", "shopify_products"),
}
# Files may come in pieces; a read waits this long after the last one for the
# rest, then is written with what is in and says what is not.
FIRST_READ_GRACE_HOURS = 24
# What each core file is, and what a read without it does not have, in plain words.
FILE_GAPS = {
    "business_report": ("Sales and traffic by product (Business Reports)",
                        "this read has no sessions or conversion rate by product."),
    "sku_economics": ("SKU Economics (fees by SKU)",
                      "Amazon's fees are not split by SKU, so this read has no true net margin per SKU."),
    "shopify_orders": ("the Orders export",
                       "this read has no sales, refund or discount history, so no margins and no demand."),
    "shopify_products": ("the Products export",
                         "this read has no cost per item or stock on hand from Shopify, so unit costs rest on "
                         "your cost sheet, if you sent one, and it has no stockout odds."),
}


def _ts(v) -> datetime | None:
    return lifecycle.ts(v)


def first_read_ready(uploads: list[dict], channel: str | None, now: datetime | None = None) -> dict:
    """Whether Profit Brief No. 001 may be written now.

    Ready when the core files for the channel it reads are parsed, or
    FIRST_READ_GRACE_HOURS after the last upload, whichever comes first. A
    client whose data came through the seat has no upload rows and nothing to
    wait for. Returns {ready, missing, why, publish_by}."""
    now = now or datetime.now(timezone.utc)
    core = CORE_FILES.get((channel or "amazon").lower(), CORE_FILES["amazon"])
    parsed = {u.get("report_type") for u in uploads or [] if u.get("status") == "parsed"}
    missing = [k for k in core if k not in parsed]
    if not missing:
        return {"ready": True, "missing": [], "why": "core", "publish_by": None}
    stamps = [_ts(u.get("uploaded_at") or u.get("created_at")) for u in uploads or []
              if u.get("status") in ("uploaded", "parsed", "failed")]
    stamps = [s for s in stamps if s]
    if not stamps:
        return {"ready": True, "missing": [], "why": "no_uploads", "publish_by": None}
    by = max(stamps) + timedelta(hours=FIRST_READ_GRACE_HOURS)
    if now >= by:
        return {"ready": True, "missing": missing, "why": "waited", "publish_by": by}
    return {"ready": False, "missing": missing, "why": "waiting", "publish_by": by}


def missing_note(missing: list[str]) -> str | None:
    """One paragraph, for the letter and the email: which core files were not in
    when the read was written, and what that leaves out."""
    if not missing:
        return None
    head = ("One file was not in when this read was written." if len(missing) == 1
            else f"{_count_word(len(missing))} files were not in when this read was written.")
    lines = []
    for k in missing:
        label, gap = FILE_GAPS.get(k, (k.replace("_", " "), "this read does without it."))
        lines.append(f"{label[0].upper() + label[1:]}: without it, {gap}")
    return " ".join([head, *lines, f"Your upload page stays open for {'it' if len(missing) == 1 else 'them'}."])


def _count_word(n: int) -> str:
    return {2: "Two", 3: "Three", 4: "Four"}.get(n, str(n))


# -- dates, the way a client reads them ----------------------------------------

def fmt_date(d, year: bool = True) -> str:
    """'October 1, 2026', or 'October 1'."""
    return f"{d:%B} {d.day}, {d.year}" if year else f"{d:%B} {d.day}"


def fmt_day(d) -> str:
    """'Thursday, October 1, 2026'."""
    return f"{d:%A}, {fmt_date(d)}"


def fmt_when(dt) -> str:
    """'Thursday, October 2 at 15:00 UTC'. Calendly's own invitation carries the
    client's time zone; this one is exact and the same for everyone."""
    u = dt.astimezone(timezone.utc)
    return f"{u:%A}, {fmt_date(u, year=False)} at {u:%H:%M} UTC"


def next_sweep(now: datetime | None = None) -> datetime:
    """The next Monday 11:00 UTC sweep after `now`."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    at = (now + timedelta(days=(SWEEP_WEEKDAY - now.weekday()) % 7)).replace(
        hour=SWEEP_HOUR_UTC, minute=0, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=7)


def proving_month(client: dict) -> dict | None:
    """The Proving Month and the free months, dated exactly as the billing gate
    dates them (monthly.billing_months): month 0 starts the day of the yes and
    ends the day before the same date next month. None before a yes."""
    from . import monthly
    started = client.get("retainer_started_at")
    if not started:
        return None
    start = date.fromisoformat(str(started)[:10])
    free = int(client.get("free_months") or 1)
    first = monthly.billing_months(client, start)[0]
    last_free = monthly.billing_months(client, monthly.add_months(start, free - 1))[-1]
    return {"start": first["start"], "end": first["end"], "free_end": last_free["end"], "free_months": free}


# -- the yes, confirmed -----------------------------------------------------------

# The agreed letter goes within this many days of the yes, or not at all: it is
# what `hubricon retainer` sends, and what the operator sends if that could not.
AGREED_LETTER_DAYS = 14


def agreed_context(db, client: dict, now: datetime | None = None) -> dict:
    """Everything the agreed letter states, read from the rows as they are now."""
    from . import issue
    now = now or datetime.now(timezone.utc)
    pm = proving_month(client) or {}
    cid = client["id"]
    first_read = bool(db.table("briefings").select("id").eq("client_id", cid).eq("issue_number", 1)
                      .limit(1).execute().data)
    has_files = bool(db.table("uploads").select("id").eq("client_id", cid).in_("status", ["uploaded", "parsed"])
                     .limit(1).execute().data)
    drafts = len(db.table("directives").select("id").eq("client_id", cid).eq("status", "draft").execute().data or [])
    kickoff_at = None
    for b in (db.table("bookings").select("event_type,starts_at").eq("client_id", cid).execute().data or []):
        at = _ts(b.get("starts_at"))
        if KICKOFF_EVENT.search(b.get("event_type") or "") and at and at > now:
            kickoff_at = at if kickoff_at is None else min(kickoff_at, at)
    return {**pm, "fee": float(client.get("monthly_fee_usd") or 6000.0), "first_read": first_read,
            "has_files": has_files, "drafts": drafts, "next_sweep": next_sweep(now), "kickoff_at": kickoff_at,
            "veto_hours": issue.VETO_HOURS}


def deliver_agreed(db, client: dict, live: bool = True, now: datetime | None = None) -> tuple[bool, str]:
    """Send the letter that confirms the yes, once (client_touches 'agreed').

    Returns (sent, why); `live` False is an operator pass without --send.
    Nothing is sent to a client on Recovery Only (there is no Proving Month),
    to anyone whose stage is not 'agreed', twice, or before migration
    20261001000003 can record that it went: a letter the database cannot
    remember would go again on the next pass."""
    now = now or datetime.now(timezone.utc)
    if (client.get("plan") or "retainer") == "recovery":
        return False, "on Recovery Only, so there is no Proving Month to confirm"
    st = lifecycle.stage(client, None, now)
    if not lifecycle.may_send(st, "agreed"):
        return False, f"their stage is {st}, not agreed"
    yes = _ts(client.get("retainer_started_at"))
    if yes and now - yes > timedelta(days=AGREED_LETTER_DAYS):
        return False, (f"the yes is {(now - yes).days} days old, and a confirmation that late confirms nothing "
                       f"(the letter goes within {AGREED_LETTER_DAYS} days)")
    if not client.get("contact_email") or is_internal(client.get("contact_email"), client.get("contact_name")):
        return False, "an internal or empty address"
    done = (db.table("client_touches").select("sent_at").eq("client_id", client["id"]).eq("kind", "agreed")
            .execute().data)
    if done:
        return False, f"already sent on {str(done[0].get('sent_at') or '')[:10] or 'an earlier day'}"
    err = lifecycle_schema_error(db)
    if err:
        return False, f"the database cannot record it yet ({err}); apply {LIFECYCLE_MIGRATION}"
    if not live:
        return False, "--send not given"
    if not notify.email_configured():
        return False, "RESEND_API_KEY is not set"
    ctx = agreed_context(db, client, now)
    link = ""
    if not (ctx["first_read"] or ctx["has_files"]):
        link = f"{INTAKE_BASE_URL}/intake?t={mint_token(db, client['id'], 'agreed letter link', rotate=False)}"
    if not send("agreed", client["contact_email"], client.get("contact_name"), link, PORTAL_URL,
                platform=client.get("platform") or "amazon", **ctx):
        return False, "the send failed (the error is printed above)"
    try:
        db.table("client_touches").upsert({"client_id": client["id"], "kind": "agreed", "sent_at": now.isoformat()},
                                          on_conflict="client_id,kind").execute()
    except Exception as e:
        return True, f"sent, but client_touches would not record it ({str(e)[:120]})"
    try:
        db.table("funnel_events").insert({"kind": "agreed_letter_sent", "client_id": client["id"], "payload": {
            "proving_month": [str(ctx.get("start")), str(ctx.get("end"))], "first_read": ctx["first_read"],
            "drafts": ctx["drafts"]}}).execute()
    except Exception:
        pass
    return True, "sent"


# -- email copy --------------------------------------------------------------

def _first(name: str | None) -> str:
    return (name or "").strip().split(" ")[0] or "there"


AMAZON_EXPORTS = [
    'Sales & traffic by product — Reports → Business Reports → "Detail Page Sales and Traffic by Child Item". '
    "One file PER MONTH for the last 6 months (this is what lets us model your trend, not just a snapshot).",
    "Fees & SKU economics — Reports → SKU Economics → one file per month, same 6 months.",
    "Advertising — Advertising Console → Measurement & Reporting → Sponsored ads reports → "
    "Sponsored Products / Search term → last 60 days.",
    "Inventory — Reports → Fulfillment → FBA Inventory → today's snapshot.",
    "Your costs — the page has a one-row-per-SKU template (unit cost, freight, packaging, lead time). "
    "Estimates are fine.",
]
SHOPIFY_EXPORTS = [
    "Orders — Shopify admin → Orders → clear any filters → Export → Orders by date, last 6 months → "
    "Plain CSV file → Export orders (not \"Export transaction histories\"). Every order and line item; this is "
    "the sales, refund and discount history the models run on.",
    "Products — Products → Export → All products → Plain CSV file. Fill in Cost per item before you export if "
    "it is blank — it is the difference between a margin and a guess. On a single-location store this file is "
    "your stock snapshot too; with two or more locations also send Products → Inventory → Export → All "
    "locations, because Shopify leaves stock quantities out of the products file whenever a store has more "
    "than one location.",
    "Payouts — Finances → Payouts → View transactions → Export → last 90 days. The fee on every charge; "
    "without it we estimate at Shopify Payments' published rate. Only exists on Shopify Payments.",
    "Advertising — Meta Ads Manager → Campaigns → breakdown by Day → Export CSV; and/or Google Ads → "
    "Campaigns (segment by Day) → Download CSV, plus Insights & reports → Search terms → Download CSV.",
    "Your costs — the page has a one-row-per-SKU template (unit cost, freight, packaging, pick/pack/postage, "
    "lead time). Estimates are fine.",
]
# The two Shopify behaviours that otherwise cost a client an afternoon: an
# export sends only what a filter left on screen, and a dated export never
# downloads — Shopify emails it.
SHOPIFY_EXPORT_NOTE = (
    "Two things about Shopify exports, so nothing catches you out: clear any filter or search on the page "
    "first, because an export sends only what is on screen; and expect the file by email rather than in your "
    "browser — anything with a date range on it is emailed to you and to the store owner within a minute or "
    "two. The upload page checks each file's columns as you pick it and says so if something looks off."
)
SEAT_HINT = {
    "amazon": f"Add {EXEC_EMAIL} under Seller Central → Settings → User Permissions; the welcome page shows the exact four permissions.",
    "shopify": "Reply with your store URL and we send a collaborator request to approve under Settings → Users → Collaborators; "
               "the welcome page shows the exact permissions.",
}


def exports_for(platform: str | None) -> list[str]:
    """The export list for the client's platform; a two-platform client gets both, labelled."""
    p = (platform or "amazon").lower()
    if p == "shopify":
        return SHOPIFY_EXPORTS
    if p == "both":
        return ([f"Amazon — {e}" for e in AMAZON_EXPORTS[:-1]]
                + [f"Shopify — {e}" for e in SHOPIFY_EXPORTS[:-1]] + [SHOPIFY_EXPORTS[-1]])
    return AMAZON_EXPORTS


def export_note(platform: str | None) -> str | None:
    """What to know before clicking Export. Shopify has two behaviours worth
    a sentence; Seller Central just downloads the file."""
    return SHOPIFY_EXPORT_NOTE if (platform or "amazon").lower() in ("shopify", "both") else None


def seat_hint(platform: str | None) -> str:
    p = (platform or "amazon").lower()
    if p == "both":
        return SEAT_HINT["amazon"] + " On Shopify: " + SEAT_HINT["shopify"][0].lower() + SEAT_HINT["shopify"][1:]
    return SEAT_HINT.get(p, SEAT_HINT["amazon"])


def _call_prep_blocks(p: str, when, link: str) -> list[dict]:
    """On booking: what the 20-minute call is, the one thing to do before it,
    and, second and optional, the upload page. It assumes no yes."""
    amazon, shopify = p in ("amazon", "both"), p in ("shopify", "both")
    blocks = [{"p": (f"Your call is booked for {fmt_when(when)}. Calendly's invitation has it in your own time zone."
                     if when else "Your call is booked; Calendly's invitation has the time, in your own time zone.")}]
    if amazon:
        blocks.append({"p": "It is twenty minutes on your own reports. You drop them into a Hubricon page in your own "
                            "browser, and while we talk it prices the costs only your own data shows: aged stock "
                            "heading for day 271, the low-inventory-level fee, units just past a fee edge, and ads "
                            "spending past break-even. The page reads the files where they are. Nothing is uploaded, "
                            "and closing the tab forgets them."})
        blocks.append({"p": "The one thing to do beforehand: request two reports in Seller Central, today if you can. "
                            "Amazon builds them on request, and they can take a while to be ready."})
        blocks.append({"ol": ["Fee Preview: Reports → Fulfillment → Fee Preview. Amazon's own measurement and fee "
                              "for every SKU.",
                              "Inventory Age: Reports → Fulfillment → Manage Inventory Health. It downloads as a "
                              ".txt or .csv."]})
        if shopify:
            blocks.append({"p": "On Shopify, be signed in to your Shopify admin, with your Products export to hand "
                                "(Products → Export → All products → Plain CSV file; fill in Cost per item first if "
                                "it is blank)."})
        blocks.append({"p": "Then have three things to hand: your Sponsored Products campaign report by day "
                            "(Advertising → Reports, as a .csv; optional, and it is what prices your ads against "
                            "break-even), your landed cost as a percentage of price (unit cost, freight and "
                            "packaging), and the ACoS you aim for now. Estimates are fine."})
    else:
        blocks.append({"p": "It is twenty minutes on your own store. We open your numbers together, on your screen, "
                            "and work out while we talk the costs only your own data shows. Nothing is sent to us."})
        blocks.append({"p": "The one thing to do beforehand: be signed in to your Shopify admin, with your Products "
                            "export to hand (Products → Export → All products → Plain CSV file; fill in Cost per "
                            "item first if it is blank)."})
        blocks.append({"p": "And one number: your landed cost as a percentage of price (unit cost, freight and "
                            "packaging). An estimate is fine."})
    if link:
        blocks.append({"p": "If you would like your first full read, Profit Brief No. 001, before we speak, you can "
                            "send your exports through your private upload page; it is written once they are in. "
                            "This is optional. The call works without it."})
        blocks.append({"button": "Open your private upload page", "url": link})
    return blocks


def _agreed_blocks(c: dict, p: str, link: str, welcome: str, portal: str) -> list[dict]:
    """On the yes: the Proving Month's first and last day (monthly.billing_months),
    and what happens next, each step with its real timing."""
    start, end, free_end = c["start"], c["end"], c.get("free_end") or c["end"]
    fee = float(c.get("fee") or 6000.0)
    months = (f"Your Proving Month runs from {fmt_date(start, year=False)} to {fmt_date(end)}, and it is free "
              "whatever it measures." if free_end == end else
              f"Your Proving Month runs from {fmt_date(start, year=False)} to {fmt_date(end)}, and your free "
              f"months run to {fmt_date(free_end)}; they are free whatever they measure.")
    steps = []
    moves_with_read = ("Any moves it finds come in their own notice, sent with it, before anything in your "
                       "account changes.")
    if not c.get("first_read") and not c.get("has_files"):
        steps.append("Your files: about fifteen minutes of exports through your private upload page, linked below. "
                     "The list for your store is on the page.")
        steps.append("Your first full read, Profit Brief No. 001: written once your files are in, and emailed to you "
                     f"when it is in Hubricon. {moves_with_read}")
    elif not c.get("first_read"):
        steps.append("Your first full read, Profit Brief No. 001: written from the files you sent, and emailed to "
                     f"you when it is in Hubricon. {moves_with_read}")
    elif c.get("drafts"):
        steps.append("Your first full read, Profit Brief No. 001, is already in Hubricon. The moves it found come in "
                     "their own notice, sent separately after this letter, before anything in your account changes.")
    else:
        steps.append("Your first full read, Profit Brief No. 001, is already in Hubricon. It found no move to make "
                     "yet.")
    sweep = c.get("next_sweep")
    steps.append("Every Monday your models run again on your latest data and write any new moves"
                 + (f"; the first of those Mondays is {fmt_date(sweep, year=False)}." if sweep else "."))
    steps.append("Every notice lists each move with its expected dollars before it goes live. Until your kickoff "
                 "agrees your standing yes, the defaults in the terms (§6) hold: price steps of up to 5% a SKU and "
                 f"ad corrections go live {int(c.get('veto_hours') or 72)} hours after the notice unless you reply "
                 "no, and anything else waits for your yes in writing. If a notice does not reach you, nothing in it "
                 "goes live.")
    kickoff = c.get("kickoff_at")
    steps.append(f"Your kickoff is booked for {fmt_when(kickoff)}: your 90-day plan, and your standing yes."
                 if kickoff else
                 "Your kickoff, 45 minutes: your 90-day plan, and your standing yes. Book it on your welcome page, "
                 "linked below.")
    blocks = [
        {"p": f"This confirms your yes. Managed Profit started on {fmt_day(start)}."},
        {"p": f"{months} After that, each month runs from the same date, is measured about a week after it ends, "
              f"and is invoiced only if your Profit Record shows it cleared the ${fee:,.0f} fee."},
        {"p": "What happens next, and when:"},
        {"ol": steps},
    ]
    if link:
        blocks.append({"button": "Open your private upload page", "url": link})
    blocks.append({"p": ("Your welcome page has the kickoff calendar. " if not kickoff else "")
                        + f"If you would rather we read your account than send files: {seat_hint(p)}"})
    blocks.append({"button": "Open your welcome page", "url": welcome})
    blocks.append({"p": "Hubricon is where your Profit Record lives. Sign in with this email address; the link "
                        "arrives in seconds and works once."})
    blocks.append({"button": "Open Hubricon", "url": portal})
    return blocks


def _read_ready_close(stage: str | None, call_at) -> str:
    """The first read's last line, for where the client stands."""
    if stage == "booked":
        return ("We go through it together on your call"
                + (f", {fmt_when(call_at)}." if call_at else ".")
                + " Read it before then if you can, and tell me where you disagree.")
    if stage == "agreed":
        return ("Read it, then tell me where you disagree. Any moves it found come in their own notice, each with "
                "its expected dollars, before anything in your account changes.")
    return "Read it, then tell me where you disagree; a reply reaches me."


def email_spec(kind: str, first_name: str | None, link: str, portal_url: str | None = None,
               platform: str | None = "amazon", **ctx) -> dict:
    """One email's subject and blocks. `ctx` carries what a stage email states:
    call_at (call_prep, teardown_ready), stage and missing (teardown_ready), and
    agreed_context's dates and facts (agreed)."""
    p = (platform or "amazon").lower()
    # The welcome page leads with the seat the client actually has to grant.
    welcome = f"{INTAKE_BASE_URL}/welcome" + (f"?p={p}" if p in ("shopify", "both") else "")
    portal = portal_url or f"{INTAKE_BASE_URL}/portal"
    greeting = f"Hi {_first(first_name)},"
    exports = exports_for(platform)
    note = export_note(platform)
    n = "five" if len(exports) == 5 else str(len(exports))
    if kind == "call_prep":
        when = ctx.get("call_at")
        return {
            "subject": (f"Your call on {when.astimezone(timezone.utc):%A}, "
                        f"{fmt_date(when.astimezone(timezone.utc), year=False)}: the one thing to do first"
                        if when else "Your call: the one thing to do first"),
            "greeting": greeting,
            "blocks": _call_prep_blocks(p, when, link),
        }
    if kind == "agreed":
        start, end = ctx["start"], ctx["end"]
        return {
            "subject": f"Confirmed: your Proving Month runs {fmt_date(start, year=False)} to {fmt_date(end)}",
            "greeting": greeting,
            "blocks": _agreed_blocks(ctx, p, link, welcome, portal),
        }
    if kind == "files":
        return {
            "subject": "15 minutes of exports and you're done",
            "greeting": greeting,
            "blocks": [
                {"p": f"No seat needed — {n} exports through your private upload page and we're off (no account required):"},
                {"button": "Open your private upload page", "url": link},
                {"ol": exports},
                *([{"p": note}] if note else []),
                {"p": "Your first full read, Profit Brief No. 001, is written once your files are in, and you get an "
                      "email when it is in Hubricon."},
                {"p": "Managed Profit is $6,000 a month, flat, and month one is free. If we don't find you more than we cost, "
      "walk away owing nothing — and after that, any invoice your Profit Record hasn't covered is void."},
            ],
        }
    if kind == "nudge":
        return {
            "subject": "15 minutes and your models start",
            "greeting": greeting,
            "blocks": [
                {"p": "Quick nudge — your models are waiting on your files."},
                {"button": "Open your secure upload page", "url": link},
                {"p": f"{n[0].upper() + n[1:]} exports, about 15 minutes; the list is on the page. If something's in the way "
                      "(a report you can't find, a seat you'd rather grant instead), reply here and I'll sort it."},
            ],
        }
    if kind == "teardown_ready":
        missing = missing_note(ctx.get("missing") or [])
        return {
            "subject": "Your first full read is ready",
            "greeting": greeting,
            "blocks": [
                {"p": "The models have run on your files. Your first full read, Profit Brief No. 001, is in Hubricon:"},
                {"button": "Open Hubricon", "url": portal},
                {"p": "Sign in with this email address; the link arrives in seconds and works once."},
                # Before a yes there is no Record to start, only the baseline it would start from.
                {"p": ("The baseline is recorded today, before anything is touched: if you go ahead, every move "
                       "is measured against it." if ctx.get("stage") in ("booked", "called") else
                       "Your Profit Record starts today at $0: the baseline is recorded before anything is "
                       "touched, so every later move is measured against it.")},
                *([{"p": missing}] if missing else []),
                {"p": _read_ready_close(ctx.get("stage"), ctx.get("call_at"))},
            ],
        }
    if kind == "downsell":
        # The smaller door, named once, two weeks after the call, to an Amazon
        # seller whose exports never came. No retainer to commit to: a share of the
        # reimbursements Amazon actually pays on claims we file, nothing else.
        from .billing import RECOVERY_SHARE
        pct = f"{RECOVERY_SHARE * 100:.0f}%"
        return {
            "subject": "A smaller door, if the $6,000 is the hurdle",
            "greeting": greeting,
            "blocks": [
                {"p": "Two weeks since our call and your exports have not landed, which usually means one of two things: "
                      "the fifteen minutes has not come free, or committing $6,000 a month to a stranger "
                      "does not sit right yet. Both are fair."},
                {"p": f"So here is the smaller door. Skip Managed Profit for now. Grant the seat or send three exports "
                      f"(the reimbursement, returns and inventory ledger reports), and we file every "
                      f"reimbursement Amazon owes you. You pay {pct} of what actually lands in your account — "
                      f"nothing else, nothing up front, and nothing at all in a month where nothing lands."},
                {"button": "Open your secure upload page", "url": link},
                {"p": "Reply RECOVERY and I will set you up on that plan. Managed Profit stays open to you "
                      "whenever the numbers make the case for it, and your Profit Record will say when they do."},
            ],
        }
    if kind == "recovery_welcome":
        # A Recovery Only request that reached api/gate.js (no page on the site posts
        # there since 2026-09-18). The same plan as the day-14 downsell, named as the thing
        # they asked for rather than as a consolation.
        from .billing import RECOVERY_SHARE
        pct = f"{RECOVERY_SHARE * 100:.0f}%"
        return {
            "subject": "Recovery Only: the reimbursements Amazon owes you",
            "greeting": greeting,
            "blocks": [
                {"p": "You asked for Recovery Only. Here is the whole of it."},
                {"p": f"Grant the seat or send three exports (the reimbursement, returns and inventory ledger "
                      f"reports), and we file every reimbursement Amazon owes you and did not pay on its own. "
                      f"You pay {pct} of what actually lands in your account — nothing else, nothing up front, "
                      f"and nothing at all in a month where nothing lands."},
                {"button": "Open your secure upload page", "url": link},
                {"p": "Reply to this email to confirm and I will put your account on that plan. Nothing is "
                      "invoiced before you do."},
                {"p": "Managed Profit stays open to you whenever the numbers make the case for it, and your "
                      "Profit Record will say when they do."},
            ],
        }
    raise ValueError(f"unknown email kind {kind!r}")


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


_P = 'style="font-size:16px;margin:0 0 20px"'
_SMALL = 'style="font-size:14px;color:#555;margin:0 0 20px"'


def _html_block(b: dict) -> str:
    if "p" in b:
        return f"  <p {_P}>{_esc(b['p'])}</p>"
    if "path" in b:
        return ('  <p style="font-family:Menlo,Consolas,monospace;font-size:14px;background:#f2f2f2;'
                f'padding:10px 14px;margin:0 0 20px">{_esc(b["path"])}</p>')
    if "button" in b:
        return "\n".join([
            '  <p style="margin:0 0 10px">',
            f'    <a href="{_esc(b["url"])}"',
            '       style="display:inline-block;background:#1a1a1a;color:#ffffff;text-decoration:none;'
            'padding:12px 24px;font-size:15px">',
            f"      {_esc(b['button'])}",
            "    </a>",
            "  </p>",
            f'  <p {_SMALL}><a href="{_esc(b["url"])}" style="color:#555;word-break:break-all">{_esc(b["url"])}</a></p>',
        ])
    if "ol" in b:
        items = "\n".join(f'    <li style="margin:0 0 10px">{_esc(i)}</li>' for i in b["ol"])
        return f'  <ol style="font-size:15px;padding-left:22px;margin:0 0 20px">\n{items}\n  </ol>'
    raise ValueError(f"unknown block {b}")


def render_html(spec: dict) -> str:
    parts = [
        '<div style="max-width:520px;margin:0 auto;padding:32px 24px;font-family:Georgia,\'Times New Roman\','
        'serif;color:#1a1a1a;line-height:1.6">',
        '  <p style="font-size:15px;letter-spacing:0.08em;text-transform:uppercase;color:#8a8a8a;margin:0 0 28px">Hubricon</p>',
        f"  <p {_P}>{_esc(spec['greeting'])}</p>",
        *[_html_block(b) for b in spec["blocks"]],
        f"  <p {_P}>Best,</p>",
        '  <p style="font-size:14px;margin:0">Hagen Simmons<br><span style="color:#8a8a8a">Hubricon</span></p>',
        "</div>",
    ]
    return "\n".join(parts)


def _text_block(b: dict) -> str:
    if "p" in b:
        return b["p"]
    if "path" in b:
        return f"  {b['path']}"
    if "button" in b:
        return f"  {b['url']}"
    if "ol" in b:
        return "\n".join(f"{n + 1}. {i}" for n, i in enumerate(b["ol"]))
    raise ValueError(f"unknown block {b}")


def render_text(spec: dict) -> str:
    return "\n\n".join([spec["greeting"], *[_text_block(b) for b in spec["blocks"]], "Best,\nHagen — Hubricon"])


def send(kind: str, to: str, first_name: str | None, link: str, portal_url: str | None = None,
         platform: str | None = "amazon", **ctx) -> bool:
    spec = email_spec(kind, first_name, link, portal_url, platform, **ctx)
    return notify.send_email(to, spec["subject"], render_text(spec), html=render_html(spec),
                             sender=FROM, reply_to=os.environ.get("EMAIL_REPLY_TO", FROM))


def guess_name_parts(full: str | None) -> tuple[str | None, str | None]:
    parts = re.split(r"\s+", (full or "").strip())
    if not parts or not parts[0]:
        return None, None
    return parts[0], (" ".join(parts[1:]) or None)
