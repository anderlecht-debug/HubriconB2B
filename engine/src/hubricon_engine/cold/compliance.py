"""The only path to a cold send, and it is built so it cannot be walked around.

COLD_ENGINE.md §2.3 and §2.4 are the law here. The design point is that a send
is not a function you call carefully — it is an object you cannot construct
without a clearance:

    ticket = compliance.authorise(db, snap, sending_domain="…")
    if ticket.ok:
        deliver(ticket.send)          # SendTicket, and there is no other way to get one

`SendTicket.__post_init__` refuses to build without the private grant that only
`authorise` holds, so a future caller who forgets the check gets an exception
rather than a delivered email. That is the whole trick, and it is worth the
small amount of ceremony: every other guard in this file can be forgotten by
someone in a hurry, and this one cannot.

The checks, in the order they run and roughly in order of how much damage each
prevents:

    dry run          COLD_DRY_RUN defaults true; nothing sends while it is on
    an address       no email, no send
    internal         never mail ourselves or the founder's own accounts
    suppression      the global table, checked every time, with no bypass path
    jurisdiction     EU/UK need a legitimate-interest basis this business has
                     not established, so they are suppressed rather than risked
    postal address   CAN-SPAM requires one in the message; no address, no send
    frequency        90 days between touches, three touches ever
    domain cap       per sending domain per day, enforced in code not policy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .. import icp, onboarding
from . import settings
from .snapshot import ProspectSnapshot

_GRANT = object()


class NotAuthorised(PermissionError):
    """Raised when something tries to build a send without a clearance."""


@dataclass(frozen=True)
class SendTicket:
    """Proof that every guard in this module passed for one prospect, once."""
    grant: object = field(repr=False)
    prospect_key: str
    email: str
    sending_domain: str | None
    jurisdiction: str
    basis: str
    checked: tuple[str, ...]
    issued_at: datetime

    def __post_init__(self):
        if self.grant is not _GRANT:
            raise NotAuthorised(
                "a cold send may only be built by cold.compliance.authorise(). "
                "If you are reading this in a traceback, something tried to email a "
                "stranger without running the suppression, jurisdiction and frequency checks.")


@dataclass(frozen=True)
class Clearance:
    ok: bool
    reason: str
    checked: tuple[str, ...] = ()
    send: SendTicket | None = None


def _domain_of(email: str | None) -> str:
    return (email or "").split("@")[-1].strip().lower()


def is_suppressed(db, email: str | None, website: str | None = None) -> str | None:
    """The global table, by address and by domain. Reason string, or None."""
    email = (email or "").strip().lower()
    domains = {d for d in (_domain_of(email), _site_domain(website)) if d}
    rows = db.table("suppressions").select("email, domain, reason").execute().data
    for r in rows:
        if r.get("email") and r["email"].strip().lower() == email:
            return r.get("reason") or "on the suppression list"
        if r.get("domain") and r["domain"].strip().lower() in domains:
            return r.get("reason") or f"{r['domain']} is on the suppression list"
    return None


def _site_domain(website: str | None) -> str:
    if not website:
        return ""
    host = website.split("//")[-1].split("/")[0].lower()
    return host[4:] if host.startswith("www.") else host


def suppress(db, *, email: str | None = None, domain: str | None = None, reason: str) -> None:
    """Add to the global list. Objections are honoured immediately (§2.3)."""
    row = {"reason": reason}
    if email:
        row["email"] = email.strip().lower()
    if domain:
        row["domain"] = domain.strip().lower()
    if not (email or domain):
        raise ValueError("suppress needs an email or a domain")
    db.table("suppressions").insert(row).execute()


def touch_history(db, prospect_key: str) -> list[dict]:
    return (db.table("outreach_sends").select("sent_at, channel, template_id")
            .eq("prospect_key", prospect_key).order("sent_at", desc=True).execute().data)


def sends_today(db, sending_domain: str) -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    return len((db.table("outreach_sends").select("id")
                .eq("sending_domain", sending_domain).gte("sent_at", since).execute().data))


def postal_address() -> str | None:
    """CAN-SPAM's physical address, from the same secret the operator uses."""
    import os
    return (os.environ.get("POSTAL_ADDRESS") or "").strip() or None


def authorise(db, snap: ProspectSnapshot, *, sending_domain: str | None = None,
              allow_dry_run: bool = False) -> Clearance:
    """Every guard, in order. Returns a Clearance carrying a SendTicket or a reason.

    `allow_dry_run` exists for the founder lane, which does not send anything:
    it prints an email for a human to paste into their own mailbox. Every other
    guard still runs, so a suppressed or out-of-jurisdiction prospect never even
    gets a draft written about them.
    """
    checked: list[str] = []

    def deny(reason: str) -> Clearance:
        return Clearance(ok=False, reason=reason, checked=tuple(checked))

    checked.append("dry-run flag")
    if settings.dry_run() and not allow_dry_run:
        return deny("COLD_DRY_RUN is on, so nothing sends. Set COLD_DRY_RUN=false to send.")

    checked.append("an address on file")
    email = (snap.email or "").strip().lower()
    if not email or "@" not in email:
        return deny("no contact address on file")

    checked.append("not an internal address")
    if onboarding.is_internal(email, snap.brand):
        return deny(f"{email} is one of ours")

    checked.append("global suppression list")
    reason = is_suppressed(db, email, snap.website)
    if reason:
        return deny(f"suppressed: {reason}")

    checked.append("jurisdiction")
    jurisdiction = snap.jurisdiction
    if jurisdiction in settings.suppressed_jurisdictions():
        return deny(f"{jurisdiction} needs a documented GDPR basis this business has not "
                    f"established; suppressed rather than risked")

    checked.append("CAN-SPAM postal address")
    if not postal_address():
        return deny("POSTAL_ADDRESS is not set, and CAN-SPAM requires one in every message")

    checked.append("contact frequency")
    history = touch_history(db, snap.key)
    if len(history) >= settings.max_touches():
        return deny(f"already contacted {len(history)} times; the cap is {settings.max_touches()}")
    if history:
        last = history[0].get("sent_at")
        if last:
            when = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - when).days
            if days < settings.recontact_days():
                return deny(f"last contacted {days} days ago; the floor is "
                            f"{settings.recontact_days()} days")

    if sending_domain:
        checked.append("sending-domain daily cap")
        used = sends_today(db, sending_domain)
        if used >= settings.domain_daily_cap():
            return deny(f"{sending_domain} has sent {used} today; the cap is "
                        f"{settings.domain_daily_cap()}")

    basis = (f"legitimate interest, B2B: publicly listed seller of record on "
             f"{'Amazon' if snap.platform == 'amazon' else 'Shopify'}, contact address published "
             f"at {snap.website or 'the brand site'} ({snap.email_confidence or 'unknown'} source)")
    ticket = SendTicket(
        grant=_GRANT, prospect_key=snap.key, email=email, sending_domain=sending_domain,
        jurisdiction=jurisdiction, basis=basis, checked=tuple(checked),
        issued_at=datetime.now(timezone.utc))
    return Clearance(ok=True, reason="clear", checked=tuple(checked), send=ticket)


def record_send(db, ticket: SendTicket, *, template_id: str, subject: str,
                teardown_id: str | None = None, channel: str = "email",
                provider_message_id: str | None = None) -> None:
    """Write the send down. This is what makes the frequency guard real.

    A hand-sent email that is never recorded is a prospect who can be mailed
    again next week by the automated lane, which is exactly the failure the
    90-day rule exists to prevent.
    """
    db.table("outreach_sends").insert({
        "prospect_key": ticket.prospect_key,
        "teardown_id": teardown_id,
        "channel": channel,
        "sending_domain": ticket.sending_domain,
        "template_id": template_id,
        "subject": subject[:300] if subject else None,
        "provider_message_id": provider_message_id,
        "recipient_email": ticket.email,
        "jurisdiction": ticket.jurisdiction,
        "basis": ticket.basis,
    }).execute()


def off_icp(snap: ProspectSnapshot) -> tuple[str | None, str]:
    """The existing ICP gate, on the fields a snapshot carries."""
    return icp.off_icp(snap.brand or snap.business_name, snap.email, snap.website)
