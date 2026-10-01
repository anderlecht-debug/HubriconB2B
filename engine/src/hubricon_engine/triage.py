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

FACTS = f"""Hubricon — what we may say to a prospect (nothing beyond this):
- Hubricon is Managed Profit for product brands doing $3M–$20M/yr on Amazon, on Shopify, or both: the money decisions (prices, ads, inventory, and on Amazon the reimbursement claims) made for them inside their own account by the founder, Hagen Simmons, with every move written on a Profit Record — dollars expected before it goes live, dollars measured after, from their own exports.
- The offer: a free, written Profit Teardown. Amazon sellers export five reports from Seller Central through a private upload page (Business Reports by child item, SKU Economics, Sponsored Products search-term report, FBA inventory snapshot, and a one-row-per-SKU cost template). Shopify brands export their orders, products (with cost per item), payouts, and their Meta or Google ads reports through the same page. No seat on either platform is required for the teardown.
- The models run when the last file lands; the written teardown is in Hubricon (their private sign-in) within 24 hours.
- What the models compute: per-SKU stockout probability from simulation (not velocity averages), how far each price can move before units fall off (elasticity), the ACoS or ROAS where each ad campaign stops paying (break-even), true net margin per SKU after every platform fee (Amazon referral, FBA and storage; Shopify payments, shipping and apps), and a 90-day cash horizon. Reimbursement recovery applies to Amazon accounts only.
- After the teardown, Managed Profit is $6,000/month, flat. Month one (the Proving Month) is free. Every invoice is conditional: it is held until the Profit Record has proven and found more value since day one than we have billed, and voided before it is sent if not. If we don't find more than we cost, they walk away owing nothing. Cancel any time by one email; they are trued up on the way out (billed more than the Record shows, the difference is refunded) and can export everything the day they leave. A Teardown later than 24 hours after their files makes their first paid month free too.
- Ongoing execution works under a standing mandate the seller sets: bounded price steps capped at 5% per cycle and ad corrections inside limits they set on the kickoff call; a bigger price step, a new campaign or a reorder waits for their written yes, and lapses after three weeks without one. They get a short video every two weeks, an email three days before any move goes live, and a Profit Record of every move with its measured impact.
- Best fit: their own brand with real pricing power and 10+ SKUs, $3M–$20M/yr, on Amazon, Shopify, or both. The floor comes from the guarantee: below $3M, or on wholesale or arbitrage inventory, the Profit Record cannot cover $6,000 a month, so every invoice would void. The application on the site still books them: a brand under $3M or on someone else's label is tagged for the call, and Hagen settles fit there. If a prospect says they are under $3M or do not sell their own brand, say so plainly, without apology, offer the 20-minute call anyway, and mention the 60-second Teardown. Otherwise offer the 20-minute call and Hagen judges fit live.
- The 60-second Teardown at https://www.hubricon.com/teardown prices one Amazon listing or Shopify product off the published rate card in the browser, no call, nothing stored unless they ask us to send it.
- Referral: a client's own link gives another founder the same free Proving Month; when that founder's first invoice stands after their day 30, the referring client's next month is credited.
- Two ways in: reply TEARDOWN to get the upload page by email, or book 20 minutes at {CALENDLY_URL}.
- Data handling: reports are uploaded to a private bucket, read only by the engine; nothing is shared or resold.
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


def draft_for(category: str, first_name: str | None) -> str | None:
    """Fixed replies for the unambiguous categories; None means a human or
    the model has to write it (or that no reply goes out at all)."""
    name = (first_name or "").strip().split(" ")[0] or "there"
    if category == "interested":
        return (
            f"Great, {name}. Two ways in:\n\n"
            "1. Reply TEARDOWN and I'll send your private upload page. Five exports, about 15 minutes, "
            "and the written Profit Teardown is back within 24 hours of the last file.\n"
            f"2. Or grab 20 minutes and I'll walk you through it live: {CALENDLY_URL}\n\n"
            "Either way it's free, and no Seller Central seat is needed.\n\nHagen"
        )
    if category == "wants_teardown":
        return (
            f"Done, {name}. Your private upload page is on its way in a separate email from {EXEC_EMAIL} "
            "(subject: \"Your Profit Teardown — 15 minutes of exports and you're done\"). Five exports, "
            "and the written teardown is in Hubricon within 24 hours of the last file landing.\n\n"
            "If it hasn't shown up in a few minutes, check spam or reply here.\n\nHagen"
        )
    if category == "not_now":
        return (
            f"Understood, {name}. I'll check back in about 90 days. If margin becomes a now problem "
            "before then, the teardown offer stands: reply TEARDOWN any time.\n\nHagen"
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


def classify_claude(subject: str, body: str, first_name: str | None) -> dict | None:
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
           use_claude: bool = True) -> dict:
    """Returns {'category', 'draft', 'by', 'reply_status'}.

    reply_status: 'approved' when a draft is ready to send, 'skipped' for the
    silent categories, 'pending_review' when a human/routine must write it.
    """
    cat = classify_rules(subject, body, sender)
    by = "rules"
    draft = draft_for(cat, first_name) if cat else None
    reason = None

    if cat in (None, "question", "other") and use_claude:
        verdict = classify_claude(subject, body, first_name)
        if verdict and verdict.get("category"):
            cat, by = verdict["category"], "claude"
            reply = verdict.get("reply")
            if reply and len(reply.split()) > 160:
                reply = None  # too long to trust unread; leave it for review
            draft = draft_for(cat, first_name) or reply
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
    "wants_teardown": "wants_teardown",
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
