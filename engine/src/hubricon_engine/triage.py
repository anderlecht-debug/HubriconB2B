"""Reply triage: what a prospect's reply means, and what we say back.

Three tiers, cheapest first:
  1. Rules. Bounces, out-of-office, unsubscribes, "not interested", "later",
     the TEARDOWN keyword, and plain enthusiasm are unambiguous; each gets a
     fixed template so nothing we promise drifts from the website.
  2. Claude (when ANTHROPIC_API_KEY is set). Questions and anything the rules
     can't place. The model classifies and, for questions, drafts a reply
     using only the fact sheet below. No numbers, no promises beyond it.
  3. The cloud routine. Whatever is still pending_review after 1 and 2.

Replies are plain text, signed "Hagen", under 120 words.

Since 2026-10-01 the templates follow the prospect's platform when it is
known (prospect_platform): a Shopify founder is told what the call prices on
a Shopify store and sent to The Price Curve, an Amazon one to The Fee
Staircase, and anyone else to the library's front door.
"""

import json
import os
import re

from . import meter

CALENDLY_URL = os.environ.get("CALENDLY_URL", "https://calendly.com/hubricon/margin-audit")
EXEC_EMAIL = os.environ.get("EXECUTION_EMAIL", "hagen.simmons@hubricon.com")
MODEL = os.environ.get("HUBRICON_TRIAGE_MODEL", "claude-opus-5")

CATEGORIES = ("interested", "wants_teardown", "question", "not_now", "not_interested",
              "unsubscribe", "ooo", "bounce", "other")
# Categories that get no reply at all: the sequence stops and the prospect is closed.
SILENT = {"not_interested", "unsubscribe", "ooo", "bounce"}

LEARN_BASE = "https://www.hubricon.com/learn"
# Where a prospect not ready for a call is sent: the course that starts with
# their own store. The Fee Staircase is Amazon's fee card; The Price Curve is
# taught on Amazon and Shopify reports alike. Unknown platform: the library.
LEARN_URLS = {
    "amazon": f"{LEARN_BASE}/fee-staircase",
    "shopify": f"{LEARN_BASE}/price-curve",
}
LEARN_URL = os.environ.get("LEARN_URL", LEARN_BASE)

# What the call prices, by the prospect's platform, in apply.html's own words
# (its "prep-copy" block, which scripts/apply-page.test.mjs holds to what /call
# can read): Seller Central reports on Amazon; the Products export on Shopify,
# whose two leaks are the compare-at sitting as a permanent discount and the
# parcel just past a USPS pound line (lib/fees.js anchorGap, carrierBandEdge).
CALL_PRICES = {
    "amazon": ("we open your own Seller Central reports together and price, in your browser, what public pages "
               "can't show: aged stock, low-inventory fees, an ad target set wrong"),
    "shopify": ("we open your Shopify Products export together and price, in your browser, what it shows: prices "
                "sitting under their own compare-at, and parcels just past a USPS pound line"),
    None: ("we open your own reports together and price, in your browser, what public pages can't show: on "
           "Amazon, aged stock, low-inventory fees and an ad target set wrong; on Shopify, prices sitting under "
           "their own compare-at and parcels just past a USPS pound line"),
}


def _platform(platform: str | None) -> str | None:
    """'amazon' or 'shopify', or None when unknown. A brand on both is sent the
    general reading: the call covers both stores."""
    p = (platform or "").strip().lower()
    return p if p in LEARN_URLS else None


def learn_url(platform: str | None = None) -> str:
    p = _platform(platform)
    return LEARN_URLS[p] if p else LEARN_URL


def prospect_platform(db, email: str | None) -> str | None:
    """Where a prospect sells, from the cheapest row that knows: the harvest
    found their store (harvest_sellers.platform), else the 60-second calculator
    they ran (tool_runs.platform, latest). None when neither knows, or when
    the read fails: an unknown platform is answered generally, never guessed."""
    e = (email or "").strip().lower()
    if not e or db is None:
        return None
    for table, order in (("harvest_sellers", None), ("tool_runs", "created_at")):
        try:
            q = db.table(table).select("platform").eq("email", e)
            if order:
                q = q.order(order, desc=True)
            rows = q.limit(1).execute().data or []
        except Exception:
            continue
        p = _platform(rows[0].get("platform")) if rows else None
        if p:
            return p
    return None

# Rewritten 2026-10-01 to HUBRICON_SPEC.md and the terms as they stand. Until
# then it still offered the written Profit Teardown and the 60-second Teardown
# (both retired in September), the $3M–$20M band (now $1M–$30M) and the old
# cumulative invoice gate (now month by month).
FACTS = f"""Hubricon — what we may say to a prospect (nothing beyond this):
- Hubricon is Managed Profit for product brands doing $1M–$30M a year on Amazon, on Shopify, or both: the money decisions (prices, ads, inventory, and on Amazon the reimbursement claims) made for them inside their own account, run by the founder, Hagen Simmons. Every move is written on their Profit Record: the dollars expected before it goes live, and the dollars measured after, from their own exports.
- The way in is a 20-minute call: four short questions, then a time, at {CALENDLY_URL}. On the call we open their own reports together and price, in their browser, what public pages can't show. On Amazon: aged stock, low-inventory fees, an ad target set wrong. On Shopify, from the Products export: prices sitting under their own compare-at (when most of a catalogue sits there, the discount has become the price, given away on every order), and parcels just past a USPS pound line, each billed at the next pound. Nothing is uploaded on the call. Amazon sellers do best with Fee Preview and Inventory Age requested in Seller Central beforehand; Shopify sellers with their Products export to hand.
- The written Profit Teardown and the 60-second Teardown are retired. If someone asks for one, say so plainly: the call replaced it.
- Not ready for a call: the method is taught free, in full, at https://www.hubricon.com/learn: every lesson and its spreadsheet open, no email needed. A Shopify brand starts with The Price Curve ({LEARN_URLS['shopify']}); an Amazon brand with The Fee Staircase ({LEARN_URLS['amazon']}). Leave an email and we send the link and the spreadsheet to keep, and a note when Amazon changes its fee cards or a new course opens. Nothing is held back for a paid version.
- Price: $6,000 a month, flat, never a percentage of ad spend. The first month, the Proving Month, is free and starts the day they say yes after the call. After that each month is measured on its own exports: if that month's Profit Record shows more than $6,000, that month is invoiced (by email, paid by bank transfer, no card on file); if not, that month is free, with nothing credited and nothing carried. Leave any day by one email; any month they paid for that did not clear on its own number is refunded in full, the refund issued within seven days.
- Fit: their own brand, ten or more SKUs, $1M–$30M a year. We only take on accounts where the arithmetic clears the bill, and if theirs doesn't, Hagen says so on the call. Never say the bill is cleared at any size.
- After a yes: their exports through a private upload page, and one seat with narrow permissions (no banking, payouts or settings). Moves inside the standing mandate they set at kickoff (bounded price steps capped at 5% per cycle and ad corrections inside limits they set on the kickoff call) are emailed before they go live and go live after 72 hours unless they say no; a bigger price step, a new campaign or a reorder waits for their written yes, and lapses after three weeks without one. A short note each week, and their Profit Record in Hubricon, their private sign-in.
- No client results are published yet. Never imply any. Of the brands we have modeled from public pages, most show nothing worth fixing, and we say so.
- Referral: a client's own link gives another founder the same free Proving Month; one month of the client's fee is credited when that brand's first invoice is raised after its own thirtieth day.
- Data: files go to a private bucket and are read only by our models; never sold, never used to advise another client without a separate yes; everything we hold exports free, any day.
- If a question can't be answered from these facts, say so plainly and offer the 20-minute call."""

_QUOTE_MARKERS = (
    re.compile(r"^\s*>"),
    re.compile(r"^On .{5,120} wrote:\s*$"),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.I),
    re.compile(r"^From:\s.+$", re.I),
    re.compile(r"^Sent from my ", re.I),
)


def strip_quoted(text: str) -> str:
    """Drop quoted history and signatures so the TEARDOWN keyword in our own
    email never classifies the reply."""
    out = []
    for line in (text or "").replace("\r", "").split("\n"):
        if any(m.match(line) for m in _QUOTE_MARKERS):
            break
        out.append(line)
    return "\n".join(out).strip()


def _has(text: str, *phrases: str) -> bool:
    return any(p in text for p in phrases)


_TEARDOWN_ASKS = (
    "send me the teardown", "send the teardown", "send over the teardown", "send it over",
    "teardown please", "teardown pls", "want the teardown", "like the teardown", "do the teardown",
    "run the teardown", "the teardown link", "the upload page", "send the upload", "send me the upload",
    "yes to the teardown", "let's do the teardown", "lets do the teardown", "up for the teardown",
    "take the teardown", "take you up on the teardown", "sign me up for the teardown", "start the teardown",
)


def _wants_teardown(raw: str, t: str, words: list[str]) -> bool:
    """The keyword is a request only when it is used as one. A question that
    happens to mention the teardown ("how long does the teardown take?") is a
    question, and the auto-reply must not say the upload page is on its way."""
    if "teardown" not in t and "tear down" not in t:
        return False
    if "TEARDOWN" in raw:
        return True  # the keyword exactly as the email asked for it
    if _has(t, *_TEARDOWN_ASKS):
        return True
    return "?" not in t and len(words) <= 12  # "sure, teardown sounds good"


def classify_rules(subject: str, body: str, sender: str | None = None) -> str | None:
    """Deterministic categories. Returns None when the rules can't tell."""
    s = (subject or "").lower()
    t = strip_quoted(body).lower()
    compact = re.sub(r"[^a-z ]", " ", t)
    words = compact.split()
    sender = (sender or "").lower()

    if "mailer-daemon" in sender or "postmaster" in sender or _has(
        s + " " + t, "delivery status notification", "undeliverable", "address not found",
        "mailbox unavailable", "delivery has failed", "550 5.1.1", "user unknown"
    ):
        return "bounce"
    if _has(s + " " + t, "out of office", "out of the office", "automatic reply", "auto-reply",
            "autoreply", "on vacation", "on leave", "currently out", "limited access to email",
            "away from my desk", "parental leave"):
        return "ooo"
    if _has(t, "unsubscribe", "remove me", "take me off", "stop emailing", "stop sending",
            "do not contact", "don't contact", "do not email", "don't email", "opt out", "opt-out"):
        return "unsubscribe"
    if words and words[0] == "no" and len(words) <= 4:
        return "not_interested"
    if _has(t, "not interested", "no thanks", "no thank you", "not a fit", "no need",
            "we're good", "we are good", "all set", "hard pass", "not for us"):
        return "not_interested"
    if _wants_teardown(strip_quoted(body), t, words):
        return "wants_teardown"
    if words and words[0] == "later" and len(words) <= 4:
        return "not_now"  # step 3 of the sequence invites exactly this one-word reply
    if _has(t, "not right now", "not now", "not at the moment", "circle back", "check back",
            "reach back", "next quarter", "next year", "later this year", "in a few months",
            "revisit", "touch base in", "after q", "busy season", "maybe later", "not yet"):
        return "not_now"
    if _has(t, "interested", "let's talk", "lets talk", "sounds good", "tell me more",
            "send it", "send me", "happy to chat", "let's do it", "lets do it", "let's chat",
            "book a", "booked", "calendar", "schedule a", "how does this work", "i'm in", "im in",
            "sign me up", "yes please", "sure,", "sure."):
        return "interested"
    if words and words[0] in ("yes", "yep", "yeah", "sure", "ok", "okay") and len(words) <= 6:
        return "interested"
    if "?" in t:
        return "question"
    return None


def draft_for(category: str, first_name: str | None, platform: str | None = None) -> str | None:
    """Fixed replies for the unambiguous categories; None means a human or
    the model has to write it (or that no reply goes out at all).

    `platform` is where the prospect sells, when known (prospect_platform):
    it decides what the call is said to price and which course they are
    sent to. Unknown, the reply names both stores and the library."""
    name = (first_name or "").strip().split(" ")[0] or "there"
    p = _platform(platform)
    if category == "interested":
        return (
            f"Good, {name}. The way in is a 20-minute call: {CALL_PRICES[p]}. Nothing is uploaded and there "
            "is no card.\n\n"
            f"{CALENDLY_URL}\n\n"
            f"If you would rather run the method yourself first, it is taught free, in full: {learn_url(p)}\n\nHagen"
        )
    if category == "wants_teardown":
        # The written Teardown is retired (HUBRICON_SPEC.md, "The Teardown is killed").
        # Someone still replying TEARDOWN to an old email is asking for a look at
        # their own numbers: the call is that look, and it goes further.
        return (
            f"Thanks, {name}. The written Teardown is retired; the 20-minute call replaced it, and it goes "
            f"further: {CALL_PRICES[p]}. Nothing is uploaded.\n\n"
            f"{CALENDLY_URL}\n\n"
            f"Or run the method yourself, free: {learn_url(p)}\n\nHagen"
        )
    if category == "not_now":
        # No "I'll check back": nothing schedules one, and a promise nobody keeps
        # is worse than silence. The prospect hears from us again only if they write.
        return (
            f"Understood, {name}. Nothing more from me unless you write. If margin becomes a now problem, "
            f"20 minutes is here whenever you want it: {CALENDLY_URL}\n\nHagen"
        )
    return None


def claude_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("HUBRICON_TRIAGE", "on").lower() != "off"


_SYSTEM = (
    "You triage replies to a cold email from Hagen Simmons (Hubricon) to the founders of product brands that sell on Amazon or Shopify. "
    "Return only JSON: {\"category\": one of " + json.dumps(list(CATEGORIES)) + ", "
    "\"reply\": string or null, \"reason\": short string}. "
    "Rules: use the fact sheet as the only source of claims; never invent numbers, case studies, "
    "or guarantees; never discount; keep replies under 120 words, plain text, friendly and direct, "
    "signed \"Hagen\" on its own last line; if the prospect asked something the facts don't cover, "
    "say you'll answer it on a call and include the booking link. For interested/wants_teardown/"
    "not_now set reply to null (templates exist). For not_interested/unsubscribe/ooo/bounce set "
    "reply to null."
)


def classify_claude(subject: str, body: str, first_name: str | None, platform: str | None = None) -> dict | None:
    """Model tier. Returns {'category', 'reply', 'reason'} or None if unavailable/failed."""
    if not claude_available():
        return None
    try:
        import anthropic
    except ImportError:
        return None
    text = strip_quoted(body)
    prompt = (
        f"{FACTS}\n\n---\nProspect first name: {first_name or 'unknown'}\n"
        f"Prospect sells on: {_platform(platform) or 'unknown'}\n"
        f"Subject: {subject or ''}\nReply body:\n{text[:4000]}\n---\nJSON only."
    )
    try:
        # Identity-linked API keys must name the workspace they act in on
        # every request (same header the narrator sends; the Console shows
        # the wrkspc_… id beside the key). Without it the API answers 400
        # and every question waited for the cloud routine.
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        client = anthropic.Anthropic(
            default_headers={"anthropic-workspace-id": workspace} if workspace else None,
        )
        msg = client.messages.create(
            model=MODEL, max_tokens=2000, system=_SYSTEM,
            output_config={"effort": "low"},  # a classification; thinking is on by default
            messages=[{"role": "user", "content": prompt}],
        )
        meter.anthropic(msg, "triage", requested_model=MODEL)  # never raises; the reply is the work
        if msg.stop_reason == "refusal":
            return {"category": None, "reply": None, "reason": "claude declined the request"}
        raw = "".join(b.text for b in msg.content if b.type == "text")
        raw = raw.strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        data = json.loads(raw)
    except Exception as err:  # network, auth, malformed JSON: fall through to the routine
        return {"category": None, "reply": None, "reason": f"claude failed: {err}"}
    cat = data.get("category")
    if cat not in CATEGORIES:
        return {"category": None, "reply": None, "reason": f"claude returned {cat!r}"}
    reply = data.get("reply")
    if reply and len(reply.split()) > 160:
        reply = None  # too long to trust; leave for review
    return {"category": cat, "reply": reply, "reason": data.get("reason", "")}


def triage(subject: str, body: str, first_name: str | None, sender: str | None = None,
           use_claude: bool = True, platform: str | None = None) -> dict:
    """Returns {'category', 'draft', 'by', 'reply_status'}.

    `platform` is the prospect's, when the caller knows it (prospect_platform);
    the templates and the model's prompt follow it.

    reply_status: 'approved' when a draft is ready to send, 'skipped' for the
    silent categories, 'pending_review' when a human/routine must write it.
    """
    cat = classify_rules(subject, body, sender)
    by = "rules"
    draft = draft_for(cat, first_name, platform) if cat else None
    reason = None

    if cat in (None, "question", "other") and use_claude:
        verdict = classify_claude(subject, body, first_name, platform)
        if verdict and verdict.get("category"):
            cat, by = verdict["category"], "claude"
            reply = verdict.get("reply")
            if reply and len(reply.split()) > 160:
                reply = None  # too long to trust unread; leave it for review
            draft = draft_for(cat, first_name, platform) or reply
        elif verdict:
            reason = verdict.get("reason")  # why the model tier passed; lands in funnel_events

    if cat is None:
        cat = "other"
    if cat in SILENT:
        status = "skipped"
    elif draft:
        status = "approved"
    else:
        status = "pending_review"
    return {"category": cat, "draft": draft, "by": by, "reply_status": status, "reason": reason}


# prospects.status after a reply of each category
STATUS_AFTER = {
    "interested": "interested",
    # A TEARDOWN reply is interest in the call now that the Teardown is retired.
    "wants_teardown": "interested",
    "question": "replied",
    "other": "replied",
    "not_now": "not_now",
    "not_interested": "not_interested",
    "unsubscribe": "unsubscribed",
    "ooo": None,       # unchanged; the sequence pauses on its own
    "bounce": "bounced",
}

# Instantly lt_interest_status to set so the campaign stops for good.
INTEREST_AFTER = {
    "interested": 1,
    "wants_teardown": 1,
    "not_interested": -1,
    "unsubscribe": -1,
    "bounce": -3,
}
