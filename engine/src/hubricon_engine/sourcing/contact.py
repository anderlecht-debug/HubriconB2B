"""Finding the person, and being honest about when we have not.

This is the stage where "thousands of free emails" stops being true, and the
whole channel depends on saying so plainly.

**Role accounts are not leads.** Every store publishes `info@`, `hello@` or
`support@`, they are trivially scraped, and they reach a customer-service queue
whose occupant cannot buy a $6,000/month engagement. Of the 35 harvest-sourced
prospects on file on 2026-09-03, all 35 were role inboxes — which is why the
founder's standing decision since that date is that role inboxes are never
cold-emailed. They are still written to the sheet, because a qualified brand is
worth a human's ninety seconds even when the crawler could not find its owner;
they are never pushed to Instantly.

**Guessed addresses are never sent to.** Shopify merchants overwhelmingly run
Google Workspace with catch-all enabled, so `first@brand.com` is accepted by
the domain whether or not anybody reads it, and every free check — syntax, MX,
disposable lists — passes it. Paid verification is the only thing that
separates a real mailbox from a catch-all, and there is no paid verification in
this build. So a guess is recorded with `email_confidence = 'pattern'`, written
to the sheet marked "do not send", and refused at the push. Bounces are the one
cost a two-month-old sending domain cannot absorb, and this is the cheapest
possible way not to pay it.

What is left is genuinely free and works more often than it sounds: DTC brands
are founder-branded almost by definition, and the founder's name is usually on
the About page with a photo next to it.
"""

from __future__ import annotations

import re

from .. import icp
from ..harvest import enrich as enrichmod
from ..harvest import shopify as shopify_harvest

LINKEDIN_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9\-_%.]+", re.I)

# Search engines are asked for the founder by name only after the store's own
# pages came up empty; the site is both cheaper and more reliable.
FOUNDER_QUERY = 'https://www.bing.com/search?q=%22{brand}%22+founder+OR+ceo+OR+owner&count=20'


def published_email(emails: list[str], domain: str) -> str | None:
    """The first address at the store's own domain.

    An address on somebody else's domain is somebody else's company — a
    supplier, an agency, a sister brand — and writing to them reads worse to
    the recipient than a guess at the right company would. Same rule the
    harvest applies, after a site published a supplier's address on 2026-09-04
    and we would have written to them.
    """
    dom = (domain or "").lower()
    for e in emails:
        if "@" not in e:
            continue
        at = e.split("@", 1)[1].lower()
        if at == dom or at.endswith("." + dom):
            return e
    return None


def founder_from_search(fetcher, brand: str | None, log=print) -> tuple[str | None, str | None, str | None]:
    """-> (first, last, source). One search, read for a name and a LinkedIn URL.

    This ICP does a lot of founder interviews and podcasts, so a brand name
    plus "founder" resolves a surprising share of the ones whose own site is
    coy about it.
    """
    if not brand:
        return None, None, None
    page = fetcher.get(FOUNDER_QUERY.format(brand=brand.replace(" ", "+")))
    if not page:
        return None, None, None
    first, last = enrichmod.founder_name(page)
    return first, last, ("search:bing" if first else None)


def linkedin_url(pages: dict[str, str], page: str | None = None) -> str | None:
    """A company or person URL, captured for a human to open.

    LinkedIn is not read here — it is recorded. The URL is the second channel
    LEAD_SOURCING.md points at, and a person opening one profile is both
    faster and better behaved than anything a crawler would do to get it.
    """
    for text in list(pages.values()) + ([page] if page else []):
        m = LINKEDIN_RE.search(text or "")
        if m:
            return m.group(0)
    return None


def resolve(fetcher, domain: str, brand: str | None, search_fetcher=None, log=print) -> dict:
    """Everything the store publishes about who to write to.

    Order is cheapest-first and stops early: the contact and policy pages
    usually carry both an address and a name, and `site_contacts` already
    breaks out as soon as it has the pair.
    """
    out = {
        "email": None, "email_confidence": None, "role_inbox": False,
        "first_name": None, "last_name": None, "contact_source": None,
        "linkedin_url": None, "business_name": None, "address": None,
        "city": None, "state": None, "status": "no_contact", "note": "",
    }
    if shopify_harvest.is_shopify_host(domain):
        # No custom domain means no inbox of its own: myshopify.com has an MX
        # record, so a guess there resolves and hard-bounces.
        out["note"] = "no custom domain: the store is only on myshopify.com, which has no inbox"
        return out

    contacts = enrichmod.site_contacts(fetcher, f"https://{domain}/", brand,
                                       paths=shopify_harvest.CONTACT_PATHS)
    dom = contacts["domain"]
    pages = contacts["pages"]
    out["first_name"], out["last_name"] = contacts["first_name"], contacts["last_name"]
    out["contact_source"] = contacts["person_source"]
    out["linkedin_url"] = linkedin_url(pages)
    for path in shopify_harvest.CONTACT_PATHS:
        page = pages.get(path)
        if not page:
            continue
        out["business_name"] = out["business_name"] or shopify_harvest.parse_business_name(page)
        addr = shopify_harvest.parse_us_address(page)
        if addr and not out["address"]:
            out.update(address=addr["address"], city=addr["city"], state=addr["state"])

    offshore = next(((e, enrichmod.offshore_domain(e)) for e in contacts["emails"]
                     if enrichmod.offshore_domain(e)), None)
    if enrichmod.offshore_domain(dom) or offshore:
        tld = enrichmod.offshore_domain(dom) or offshore[1]
        out.update(status="disqualified", note=f"contact on a {tld} domain")
        return out

    if not out["first_name"] and search_fetcher is not None:
        first, last, source = founder_from_search(search_fetcher, brand, log=log)
        if first:
            out.update(first_name=first, last_name=last, contact_source=source)

    found = published_email(contacts["emails"], dom)
    if found:
        out.update(email=found, email_confidence="published",
                   role_inbox=icp.is_role_inbox(found), status="contacted_found")
        out["note"] = ("published role inbox — founder lane only"
                       if out["role_inbox"] else "published contact address")
        return out

    # Nothing published. A pattern address is recorded so the row is not
    # re-crawled forever and so a future batch verification has something to
    # verify, but `sendable` refuses it and the sheet says so.
    if enrichmod.mx_ok(dom):
        guess = enrichmod.guess_emails(dom, out["first_name"], out["last_name"])[0]
        out.update(email=guess, email_confidence="pattern", role_inbox=icp.is_role_inbox(guess),
                   status="sheet_only",
                   note="pattern address, unverified — not sendable without paid verification")
        return out
    out["note"] = "no published address and no MX"
    return out


def sendable(row: dict) -> tuple[bool, str]:
    """-> (may we cold-email this row, why not). The single gate `push.py` asks.

    Three refusals, and each one is a decision that was made once and should
    not be re-argued per lead:
      * no address at all
      * a guessed address, which cannot be verified for free (see the module
        docstring)
      * a role inbox, which reaches a support queue — the founder's call on
        2026-09-03, and the reason the founder lane exists
    """
    email = (row.get("email") or "").strip()
    if not email or "@" not in email:
        return False, "no address"
    if (row.get("email_confidence") or "") != "published":
        return False, "pattern address — unverified, and there is no paid verification in this build"
    if row.get("role_inbox") or icp.is_role_inbox(email):
        return False, "role inbox — founder lane only, never the campaign"
    if icp.domain_mismatch(email, row.get("domain") or row.get("website")):
        return False, "address is not on the brand's own domain"
    return True, ""
