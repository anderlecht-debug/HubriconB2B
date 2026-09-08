"""The loop's own numbers: every arrow as a conversion, and what came back
from a teardown joined to the teardown it came from.

`pmf_scoreboard()` now runs past "paid" — asks, consents, testimonials,
referrals, speed. This module reads it as a chain of rates so a founder can
see which arrow is the weak one, and writes the two attributions nothing
wrote before: a reply or a booking from someone a teardown was sent to is
recorded against that teardown, so `hubricon teardown stats` can finally say
which finding kinds convert rather than only which were sent.
"""

from __future__ import annotations

from .cold import run as coldrun

# (stage, the stage it converts from). Order is the order the digest prints.
STAGES = (
    ("contacted", None),
    ("replied", "contacted"),
    ("interested", "replied"),
    ("bookings", "interested"),
    ("teardowns_delivered", "bookings"),
    ("paid", "teardowns_delivered"),
    ("renewed", "paid"),
    ("asks_sent", "paid"),
    ("consent_granted", "asks_sent"),
    ("testimonials", "consent_granted"),
    ("results_published", "consent_granted"),
    ("referral_links", "consent_granted"),
    ("referral_booked", "referral_links"),
    ("referral_paid", "referral_booked"),
)

TEARDOWN_STAGES = (("teardowns_sent", None), ("teardowns_replied", "teardowns_sent"),
                   ("teardowns_booked", "teardowns_replied"))


def rates(s: dict, stages=STAGES) -> list[tuple[str, int, float | None]]:
    """[(stage, count, share of the previous stage or None)]. Zero-safe."""
    out = []
    for stage, prev in stages:
        n = int(s.get(stage) or 0)
        base = int(s.get(prev) or 0) if prev else 0
        out.append((stage, n, round(n / base, 3) if base else None))
    return out


def table(s: dict) -> str:
    lines = ["The loop, stage by stage", ""]
    for stage, n, r in rates(s):
        pct = f"{r * 100:5.1f}% of prior" if r is not None else ""
        lines.append(f"  {stage:<20} {n:>5}   {pct}")
    lines += ["", "The cold teardown lane"]
    for stage, n, r in rates(s, TEARDOWN_STAGES):
        pct = f"{r * 100:5.1f}% of prior" if r is not None else ""
        lines.append(f"  {stage:<20} {n:>5}   {pct}")
    if s.get("median_hours_to_first_issue") is not None:
        lines += ["", f"  median hours, exports → Issue 001: {float(s['median_hours_to_first_issue']):.1f}"]
    if s.get("median_days_to_first_value") is not None:
        lines.append(f"  median days, exports → first dollar: {float(s['median_days_to_first_value']):.1f}")
    return "\n".join(lines)


def digest_lines(s: dict) -> list[str]:
    """Three lines for the daily digest: the arrows past paid."""
    if not s:
        return []
    return [
        "The loop past paid",
        f"  asks sent {s.get('asks_sent', 0)}   consented {s.get('consent_granted', 0)}   "
        f"testimonials {s.get('testimonials', 0)}   results published {s.get('results_published', 0)}",
        f"  referral links {s.get('referral_links', 0)}   referral bookings {s.get('referral_booked', 0)}   "
        f"referred clients paying {s.get('referral_paid', 0)}   partner bookings {s.get('partner_booked', 0)}",
        f"  teardowns sent {s.get('teardowns_sent', 0)}   replied {s.get('teardowns_replied', 0)}   "
        f"booked {s.get('teardowns_booked', 0)}",
        "",
    ]


# -- attribution -----------------------------------------------------------------------

def _teardown_for_email(db, email: str) -> str | None:
    email = (email or "").strip().lower()
    if not email:
        return None
    rows = (db.table("outreach_sends").select("teardown_id").eq("recipient_email", email)
            .order("sent_at", desc=True).limit(5).execute().data)
    for r in rows:
        if r.get("teardown_id"):
            return r["teardown_id"]
    return None


def _teardown_for_domain(db, email: str) -> str | None:
    domain = (email or "").split("@")[-1].strip().lower()
    if not domain or "." not in domain:
        return None
    sellers = (db.table("harvest_sellers").select("seller_id")
               .or_(f"website.ilike.%{domain}%,email.ilike.%@{domain}").limit(5).execute().data)
    for s in sellers:
        rows = (db.table("teardowns").select("id").eq("prospect_key", s["seller_id"])
                .in_("status", ["sent", "approved"]).order("created_at", desc=True).limit(1).execute().data)
        if rows:
            return rows[0]["id"]
    return None


def _already(db, teardown_id: str, kind: str) -> bool:
    return bool(db.table("teardown_events").select("id").eq("teardown_id", teardown_id)
                .eq("kind", kind).limit(1).execute().data)


def attribute_reply(db, sender: str, category: str | None = None) -> str | None:
    """A reply from an address a teardown went to is that teardown's reply.
    Returns the teardown id when an event was written, else None."""
    tid = _teardown_for_email(db, sender)
    if not tid or _already(db, tid, "reply"):
        return None
    coldrun.record_event(db, tid, "reply", {"email": sender, "category": category})
    return tid


def attribute_booking(db, email: str, booking_id: str | None = None) -> str | None:
    """A booking from an address or a domain a teardown went to is that
    teardown's booking. Marks the prospect's source as the teardown lane when
    nothing more specific was recorded."""
    tid = _teardown_for_email(db, email) or _teardown_for_domain(db, email)
    if not tid or _already(db, tid, "booked"):
        return None
    coldrun.record_event(db, tid, "booked", {"email": email, "booking_id": booking_id})
    try:
        db.table("prospects").update({"source": "teardown"}).eq("email", (email or "").lower()) \
            .in_("source", ["instantly_list", "inbound"]).execute()
    except Exception:
        pass
    return tid
