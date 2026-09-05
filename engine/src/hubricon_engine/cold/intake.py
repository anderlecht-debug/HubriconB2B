"""Leads the founder found, turned into teardowns.

The division of labour this module exists for: a person finds the company and,
crucially, the owner's *name*; the engine does the arithmetic and the page. That
split is not a compromise, it is the right way round. Every constraint the cold
lane hit was one a crawl cannot solve — the harvest found 1,000 sellers and two
named people, because a name lives on an About page in a sentence, or on
LinkedIn, or nowhere at all. A person finds one in ninety seconds. And it is far
less machinery than crawling categories: one store costs three or four requests
instead of a day of Best Sellers pages, and nothing is being fingerprinted.

What a lead needs to be:

    holtzleather.com                              a domain is enough
    holtzleather.com, nora@holtzleather.com, Nora  better: the engine skips enrichment
    A1TIL6RG80Z0E0                                an Amazon seller id also works

Given a domain, `add` fetches only that store — meta, catalogue, contact pages —
writes the same rows the crawl would have written, and hands them to the same
modelling path. Nothing downstream knows the lead came from a person, except the
provenance column, which is a GDPR record as much as a diagnostic.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ..harvest import shopify as shopify_harvest

# Amazon merchant ids are A + 12-13 upper-case alphanumerics. A domain never is.
SELLER_ID = re.compile(r"^A[A-Z0-9]{9,16}$")
SOURCE = "founder"


@dataclass(frozen=True)
class Lead:
    """One company the founder decided is worth a teardown."""
    ident: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    note: str | None = None

    @property
    def is_amazon(self) -> bool:
        return bool(SELLER_ID.match(self.ident))

    @property
    def handle(self) -> str:
        """The store handle a Shopify fetch wants: a bare domain, no scheme."""
        host = self.ident.split("//")[-1].split("/")[0].strip().lower()
        return host[4:] if host.startswith("www.") else host


def parse(text: str) -> tuple[list[Lead], list[str]]:
    """Whatever the founder pasted → leads, plus the lines that made no sense.

    Deliberately forgiving about shape, because the input is a person working
    quickly: one per line, comma or tab separated, a header row if you like,
    columns in any of the orders anyone would naturally type. Blank lines and
    anything starting with # are skipped.

    Returns the bad lines rather than raising on them: one malformed row out of
    forty should not throw away the other thirty-nine.
    """
    leads: list[Lead] = []
    bad: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [c.strip() for c in next(csv.reader(io.StringIO(line.replace("\t", ","))))]
        fields = [f for f in fields if f]
        if not fields:
            continue
        if fields[0].lower() in ("domain", "website", "store", "url", "seller", "seller_id"):
            continue                                      # a header row
        ident, email, first, last = None, None, None, None
        for f in fields:
            if "@" in f and "." in f.split("@")[-1]:
                email = f.lower()
            elif SELLER_ID.match(f) or "." in f:
                ident = ident or f
            elif first is None:
                first = f
            else:
                last = last or f
        if not ident and email:
            ident = email.split("@")[-1]                  # the address names the domain
        if not ident:
            bad.append(line)
            continue
        leads.append(Lead(ident=ident, email=email, first_name=first, last_name=last))
    # One company twice in a paste is a slip, not two leads.
    seen, unique = set(), []
    for lead in leads:
        key = lead.handle if not lead.is_amazon else lead.ident
        if key in seen:
            continue
        seen.add(key)
        unique.append(lead)
    return unique, bad


def _apply_known(row: dict, lead: Lead) -> dict:
    """What the founder found wins over what the fetch guessed.

    A person who has just read the About page knows the owner's name better than
    a pattern-matcher does, and the whole point of this lane is that they looked.
    """
    if lead.email:
        row["email"] = lead.email
        row["email_confidence"] = "published"
        row["contact_source"] = "founder, by hand"
    if lead.first_name:
        row["first_name"] = lead.first_name
        row["person_source"] = "founder, by hand"
    if lead.last_name:
        row["last_name"] = lead.last_name
    row["source"] = SOURCE
    return row


def resolve_handle(fetcher, ident: str) -> tuple[str | None, dict | None]:
    """A brand's own domain → its myshopify handle, the way discovery does it.

    The row key for a store is its myshopify handle, because a primary domain
    can be re-pointed and the handle cannot. A founder types the domain, so the
    domain has to be resolved before anything else: passing `brand.com` in where
    a handle belongs asks for `brand.com.myshopify.com`, which is nobody's store.
    Costs one request, and its answer is reused so `read_store` does not repeat it.
    """
    host = ident.split("//")[-1].split("/")[0].strip().lower()
    host = host[4:] if host.startswith("www.") else host
    if "." not in host:
        return host, None                       # already a bare handle
    if host.endswith(".myshopify.com"):
        return host[: -len(".myshopify.com")], None
    meta = shopify_harvest.parse_meta(fetcher.get(f"https://{host}/meta.json"))
    handle = shopify_harvest.handle_from_meta(meta)
    return handle, meta


def add_shopify(db, fetcher, lead: Lead, log=print) -> tuple[str | None, str]:
    """Fetch one store and write its rows. → (seller_id, what happened)."""
    handle, probed = resolve_handle(fetcher, lead.ident)
    if not handle:
        return None, (f"{lead.handle} does not answer as a Shopify store — no /meta.json. "
                      f"A headless storefront serves its own domain as an app; try the "
                      f"<name>.myshopify.com handle if you can find it.")
    got = shopify_harvest.read_store(fetcher, handle, meta=probed)
    meta = got["meta"]
    if meta is None and not lead.email:
        return None, f"no Shopify store at {lead.handle} ({got['note']})"
    sid = shopify_harvest.seller_id(handle)
    domain = shopify_harvest.store_domain(handle, meta or {})
    row = shopify_harvest.store_row(
        handle, meta or {"name": lead.handle}, got["products"], got["sampled"],
        got["vendors"] or {"vendors": [], "dominant": None, "category": None},
        got["est_annual"], got["contact"], got["status"],
        f"founder-sourced {datetime.now(timezone.utc).date()}; {got['note']}")
    # A store the crawl would have skipped for want of an address is fine here:
    # the founder brought one. Size and reseller verdicts still stand.
    if lead.email and row["status"] in ("no_email", "no_website"):
        row["status"] = "enriched"
    db.table("harvest_sellers").upsert([_apply_known(row, lead)], on_conflict="seller_id").execute()
    products = shopify_harvest.catalogue_rows(domain, sid, got)
    if products:
        db.table("harvest_products").upsert(products, on_conflict="asin").execute()
    return sid, (f"{row['status']}, {len(products)} product(s)"
                 + (f", {got['note']}" if got.get("note") else ""))


def add_amazon(db, fetcher, lead: Lead, log=print) -> tuple[str | None, str]:
    """One Amazon seller by merchant id: the public profile, then the storefront."""
    from ..harvest import run as harvest

    harvest.profiles(db, fetcher, ids=[lead.ident], limit=1, log=log)
    rows = (db.table("harvest_sellers").select("*").eq("seller_id", lead.ident).execute().data)
    if not rows:
        return None, f"no public seller profile for {lead.ident}"
    db.table("harvest_sellers").update(_apply_known({}, lead)).eq("seller_id", lead.ident).execute()
    harvest.listings(db, fetcher, limit=1, log=log)
    held = (db.table("harvest_products").select("asin")
            .eq("seller_id", lead.ident).execute().data)
    return lead.ident, f"{rows[0]['status']}, {len(held)} listing(s)"
