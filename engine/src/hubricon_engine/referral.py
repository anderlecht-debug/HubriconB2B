"""The ask, and the month it earns.

terms.html §9 prices the free month in a testimonial and permission to publish
anonymised results. Until now that price was two unanswered rows the day-30
pass inserted and nobody read. This module:

  - decides WHEN to ask: the first Issue after the ledger crosses three times
    the fee, or after the first reimbursement lands — the moment the client
    has something to say thank you for, which is the only moment a referral
    ask is not an imposition;
  - gives the ask a surface: a tokenised page (/say/<token>, api/consent.js)
    where the client grants or refuses each consent, writes two lines, and
    finds their own referral link;
  - attributes a booking that arrived through that link to the client who
    sent it, and credits them one month when the brand they sent clears its
    OWN day-30 gate — never before, so the credit costs nothing until it has
    produced revenue.

The ask rides the fortnightly Issue email rather than going out alone: one
more paragraph in a letter the client already opens, sent once
(client_touches kind 'consent_ask'), never chased.
"""

from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timezone

from . import billing, onboarding, outbound
from . import value as valuemod

SITE = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com")
ASK_KIND = "consent_ask"
CONSENT_KINDS = ("testimonial", "anonymised_results", "calibration")

_REF = re.compile(r"\bref\s*[:=]\s*([A-Za-z0-9_-]{4,32})")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- codes and links -------------------------------------------------------------------

def new_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")[:8]


def ensure_code(db, client: dict) -> str:
    if client.get("referral_code"):
        return client["referral_code"]
    code = new_code()
    db.table("clients").update({"referral_code": code}).eq("id", client["id"]).execute()
    client["referral_code"] = code
    return code


def link(code: str) -> str:
    return f"{SITE}/?ref={code}"


def code_from_answers(answers: dict | None) -> str | None:
    """The `ref:` token the site appends to utm_content, in either shape the
    cloud routine stores (raw string or parsed key)."""
    if not answers:
        return None
    direct = str(answers.get("ref") or "").strip()
    if direct and re.fullmatch(r"[A-Za-z0-9_-]{4,32}", direct):
        return direct
    for value in answers.values():
        m = _REF.search(str(value))
        if m:
            return m.group(1)
    return None


# -- when to ask -----------------------------------------------------------------------

def ask_due(ledger: dict, claims: list[dict], consents: list[dict]) -> bool:
    """True at the moment of maximum value with nothing answered yet."""
    if any(k.get("answered_at") for k in consents):
        return False
    multiple = ledger.get("roi_multiple")
    strong = multiple is not None and float(multiple) >= valuemod.AT_RISK_MULTIPLE
    recovered = any(c.get("status") == "paid" and float(c.get("paid_amount") or 0) > 0
                    and (c.get("filed_at") or c.get("case_id")) for c in claims)
    return bool(strong or recovered) and float(ledger.get("value_total") or 0) > 0


def touched(db, client_id: str, kind: str = ASK_KIND) -> bool:
    return bool(db.table("client_touches").select("kind").eq("client_id", client_id)
                .eq("kind", kind).limit(1).execute().data)


def touch_once(db, client_id: str, kind: str = ASK_KIND) -> bool:
    if touched(db, client_id, kind):
        return False
    db.table("client_touches").upsert({"client_id": client_id, "kind": kind, "sent_at": _now()},
                                      on_conflict="client_id,kind").execute()
    return True


def ask_blocks(say_url: str, referral_url: str) -> list[dict]:
    """The paragraph that rides the Issue. No numbers: the letter above it
    carries the ledger."""
    return [
        {"p": "One more thing, and it is the whole price of your free month. We said we would ask "
              "for a short testimonial and for permission to publish your results with the numbers "
              "anonymised. Your Profit Record now says we have earned the asking. Either answer is fine, "
              "and it takes a minute:"},
        {"button": "Say yes, or no, here", "url": say_url},
        {"p": "On that page is also a link that is yours. If another founder should see their own "
              "numbers the way you have, send it to them: their first month is free exactly as "
              "yours was, and when their first invoice stands after their day thirty, your next month is on us. "
              f"It is {referral_url}"},
    ]


def ask_if_due(db, client: dict, ledger: dict, claims: list[dict], send: bool) -> list[dict]:
    """The blocks to append to this Issue's email, or []. Mints the consent
    token only when the mail will actually go, so a rehearsal leaves no
    stray links behind."""
    consents = db.table("consents").select("*").eq("client_id", client["id"]).execute().data
    if not ask_due(ledger, claims, consents) or touched(db, client["id"]):
        return []
    if not send:
        return [{"p": "[the consent and referral ask would ride this issue]"}]
    code = ensure_code(db, client)
    token = onboarding.mint_token(db, client["id"], "consent link", rotate=False)
    return ask_blocks(f"{SITE}/say/{token}", link(code))


def mark_asked(db, client: dict) -> None:
    """Record the ask: the touch, and the consent rows it opened."""
    touch_once(db, client["id"])
    for kind in CONSENT_KINDS:
        try:
            db.table("consents").upsert({"client_id": client["id"], "kind": kind, "asked_at": _now()},
                                        on_conflict="client_id,kind").execute()
        except Exception:
            pass
    outbound.log_event(db, "consent_asked", client_id=client["id"])


# -- attribution -----------------------------------------------------------------------

def attribute(db, client: dict, booking: dict) -> dict | None:
    """A booking that carried a referral code: record who sent it. Returns
    what was recorded, or None when the booking carried no code."""
    code = code_from_answers(booking.get("answers"))
    if not code:
        return None
    referrer = db.table("clients").select("id, company_name").eq("referral_code", code).limit(1).execute().data
    partner = [] if referrer else db.table("partners").select("id, name").eq("code", code).limit(1).execute().data
    if not referrer and not partner:
        return {"code": code, "matched": None}
    patch: dict = {}
    if referrer and referrer[0]["id"] != client["id"] and not client.get("referred_by_client_id"):
        patch["referred_by_client_id"] = referrer[0]["id"]
    if partner and not client.get("referred_by_partner_id"):
        patch["referred_by_partner_id"] = partner[0]["id"]
    if patch:
        db.table("clients").update(patch).eq("id", client["id"]).execute()
        client.update(patch)
    db.table("bookings").update({"ref_code": code}).eq("id", booking["id"]).execute()
    source = "referral" if referrer else "partner"
    email = (booking.get("invitee_email") or client.get("contact_email") or "").strip().lower()
    row = {"email": email, "source": source, "status": "booked", "client_id": client["id"],
           "last_event_at": _now()}
    if referrer:
        row["referrer_client_id"] = referrer[0]["id"]
    else:
        row["partner_id"] = partner[0]["id"]
    db.table("prospects").upsert(row, on_conflict="email").execute()
    outbound.log_event(db, "referral_booked", booking_id=booking["id"], client_id=client["id"],
                       payload={"code": code, "source": source,
                                "referrer": (referrer or partner)[0].get("company_name")
                                or (referrer or partner)[0].get("name")})
    return {"code": code, "matched": source, "who": (referrer or partner)[0]}


# -- the month -------------------------------------------------------------------------

def credit_referrer(db, referred: dict, stripe=None) -> dict | None:
    """The brand that was referred just cleared its own day-30 gate. Give the
    client (or partner) who sent it what was promised, exactly once.

    A referrer who is already billing gets a Stripe customer-balance credit for
    one month, which applies itself to their next ACH invoice — no coupon
    object, and it works whether or not they are mid-cycle. A referrer still in
    their own free month (or one the gate came back `short` for) gets
    `free_months + 1`, which `billing.due_for_decision` honours. Idempotent
    on the referred client's `referral_credit_applied_at`.
    """
    if referred.get("referral_credit_applied_at"):
        return None
    pid, rid = referred.get("referred_by_partner_id"), referred.get("referred_by_client_id")
    if pid:
        db.table("clients").update({"referral_credit_applied_at": _now()}).eq("id", referred["id"]).execute()
        outbound.log_event(db, "partner_referral_paid", client_id=referred["id"],
                           payload={"partner_id": pid})
        return {"partner_id": pid, "how": "partner terms apply; pay by hand"}
    if not rid:
        return None
    rows = db.table("clients").select("*").eq("id", rid).limit(1).execute().data
    if not rows:
        return None
    referrer = rows[0]
    fee = float(referrer.get("monthly_fee_usd") or valuemod.DEFAULT_MONTHLY_FEE_USD)
    company = referred.get("company_name") or "a brand you sent"
    if referrer.get("stripe_subscription_id") and referrer.get("stripe_customer_id"):
        call = stripe or billing._stripe
        call(f"customers/{referrer['stripe_customer_id']}/balance_transactions",
             {"amount": int(round(-fee * 100)), "currency": "usd",
              "description": f"Referral month — {company}'s first invoice stands"},
             idempotency_key=f"referral-{referred['id']}")
        how = "credited against the next invoice"
    else:
        db.table("clients").update({"free_months": int(referrer.get("free_months") or 1) + 1}) \
            .eq("id", rid).execute()
        how = "added as a further free month"
    db.table("clients").update({"referral_credit_applied_at": _now()}).eq("id", referred["id"]).execute()
    outbound.log_event(db, "referral_credit", client_id=rid,
                       payload={"referred_client_id": referred["id"], "how": how, "amount_usd": fee})
    return {"referrer": referrer, "how": how, "fee": fee, "referred_company": company,
            "blocks": credit_email_blocks(company, how)}


def credit_email_blocks(company: str, how: str) -> list[dict]:
    return [
        {"p": f"{company} took the free month on your link and their first invoice now stands after their day thirty. "
              f"We said your next month would be on us when that happened, and it is: "
              f"{'it has been ' + how if 'credited' in how else 'it has been ' + how}."},
        {"p": "Thank you. A founder sending a founder is the only way Hubricon was ever going "
              "to grow, and you did it."},
    ]


# -- partners --------------------------------------------------------------------------

def add_partner(db, code: str, name: str, contact_email: str | None, kind: str,
                terms: str | None) -> dict:
    row = {"code": code.strip(), "name": name.strip(), "contact_email": (contact_email or "").strip().lower() or None,
           "kind": kind, "terms": terms}
    return db.table("partners").upsert(row, on_conflict="code").execute().data[0]
