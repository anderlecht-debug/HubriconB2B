"""Brand → website → the contact the brand itself publishes.

A private-label brand wants to be found: its site is usually <brand>.com,
and its contact page carries a hello@/info@/support@ address the founder or
their assistant reads. This module tries the obvious domains first, asks
Bing when that fails, then reads the contact and about pages for an address
and a founder's name. Pattern guesses (hello@, info@) are the fallback and
are flagged so Instantly's import verification can drop the ones that bounce.
"""

from __future__ import annotations

import base64
import html
import re
import socket
import subprocess
import urllib.parse

from .amazon import norm_name

SKIP_DOMAINS = (
    "amazon.", "walmart.com", "ebay.com", "target.com", "facebook.com", "instagram.com", "youtube.com",
    "linkedin.com", "tiktok.com", "pinterest.", "wikipedia.org", "reddit.com", "etsy.com", "bing.com",
    "microsoft.com", "apple.com", "google.", "twitter.com", "x.com", "yelp.com", "bbb.org", "trustpilot.com",
    "homedepot.com", "lowes.com", "costco.com", "bestbuy.com", "wayfair.com", "shopify.com", "temu.com",
    "aliexpress.com", "alibaba.com", "chewy.com", "overstock.com", "newegg.com", "kohls.com", "macys.com",
    "sephora.com", "ulta.com", "cvs.com", "walgreens.com", "petco.com", "petsmart.com", "samsclub.com",
    "zoominfo.com", "crunchbase.com", "dnb.com", "bloomberg.com", "glassdoor.com", "indeed.com",
    "importyeti.com", "trademarkia.com", "justia.com", "uspto.gov", "opencorporates.com", "bizapedia.com",
    "manta.com", "mapquest.com", "yellowpages.com", "aboutamazon.com",
)
PARKED_MARKERS = ("domain is for sale", "buy this domain", "this domain is parked", "hugedomains",
                  "sedo.com", "dan.com", "godaddy.com/domainsearch", "afternic", "domain parking",
                  "is available for purchase")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_LOCAL = ("noreply", "no-reply", "donotreply", "do-not-reply", "example", "test@", "privacy", "legal",
             "press", "careers", "jobs", "dmca", "abuse", "postmaster", "webmaster", "sentry", "affiliate",
             "wholesale", "unsubscribe", "billing", "returns", "warranty", "recall", "compliance", "hr@",
             "accounts", "invoice", "@2x", "@3x")
BAD_EMAIL_DOMAINS = ("sentry.io", "wixpress.com", "example.com", "domain.com", "email.com", "yourdomain",
                     "amazon.com", "shopify.com", "klaviyo", "mailchimp", "google.com", "apple.com",
                     "facebook.com", "instagram.com", "png", "jpg", "jpeg", "gif", "svg", "webp")
LOCAL_PREFERENCE = ("hello", "hi", "howdy", "hey", "info", "contact", "team", "support", "help",
                    "customerservice", "customercare", "service", "care", "sales", "orders", "shop", "office")
NAME_STOPWORDS = {"our", "the", "meet", "about", "amazon", "store", "family", "team", "read", "learn",
                  "contact", "shop", "free", "made", "since", "founder", "owner", "chief", "executive",
                  "officer", "ceo", "and", "with", "from", "story", "brand", "company", "why", "who",
                  "we", "us", "you", "your", "his", "her", "their", "new", "york", "los", "angeles",
                  "united", "states", "america", "american", "north", "south", "east", "west", "inc", "llc",
                  "customer", "service", "shipping", "returns", "policy", "privacy", "terms", "sign", "log",
                  "get", "join", "follow", "email", "phone", "call", "text", "chat", "quick", "links"}
CONTACT_PATHS = ("", "/pages/contact", "/pages/contact-us", "/contact", "/contact-us",
                 "/pages/about", "/pages/about-us", "/about", "/about-us", "/pages/our-story")


def brand_token(brand: str | None) -> str:
    return norm_name(brand) or re.sub(r"[^a-z0-9]", "", (brand or "").lower())


def candidate_domains(brand: str | None) -> list[str]:
    t = brand_token(brand)
    raw = re.sub(r"[^a-z0-9]", "", (brand or "").lower())
    hyph = "-".join(re.findall(r"[a-z0-9]+", (brand or "").lower()))
    if len(t) < 3:
        return []
    out = [f"{t}.com", f"{raw}.com", f"{hyph}.com", f"{t}usa.com", f"shop{t}.com", f"get{t}.com",
           f"{t}brand.com", f"{t}store.com", f"{t}official.com", f"{t}.co", f"{t}products.com", f"my{t}.com"]
    return list(dict.fromkeys(d for d in out if not d.startswith((".", "-"))))


def _domain(url: str) -> str:
    host = urllib.parse.urlparse(url if "://" in url else "https://" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def skip_domain(domain: str) -> bool:
    return any(s in domain for s in SKIP_DOMAINS)


def site_matches(page: str | None, brand: str | None) -> bool:
    if not page:
        return False
    low = page.lower()
    if any(m in low for m in PARKED_MARKERS):
        return False
    t = brand_token(brand)
    head = norm_name(re.sub(r"<[^>]+>", " ", low[:6000]))
    m = re.search(r"<title>([^<]*)", page, re.I)
    title = norm_name(m.group(1)) if m else ""
    return bool(t) and (t in title or t in head)


def decode_bing_link(href: str) -> str | None:
    """Bing wraps results as /ck/a?…&u=a1<urlsafe-base64>; unwrap or pass through."""
    href = html.unescape(href)
    if "bing.com/ck/a" in href:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        u = (q.get("u") or [""])[0]
        if u.startswith("a1"):
            u = u[2:]
        try:
            return base64.urlsafe_b64decode(u + "=" * (-len(u) % 4)).decode("utf-8", "replace")
        except (ValueError, UnicodeDecodeError):
            return None
    return href if href.startswith("http") and "bing.com" not in href else None


def bing_results(page: str | None) -> list[str]:
    if not page:
        return []
    out: list[str] = []
    for blk in re.findall(r'<li class="b_algo".*?</li>', page, re.S):
        for href in re.findall(r'href="([^"]+)"', blk):
            u = decode_bing_link(href)
            if u and not u.endswith(".css") and u not in out:
                out.append(u)
                break
    return out


def find_website(fetcher, brand: str | None, business_name: str | None = None) -> tuple[str | None, str | None]:
    """→ (homepage url, how) trying <brand>.com and friends, then Bing."""
    if not brand or len(brand_token(brand)) < 3:
        return None, None
    for dom in candidate_domains(brand)[:4]:
        page = fetcher.get(f"https://{dom}/")
        if page and site_matches(page, brand):
            return f"https://{dom}/", "direct"
    queries = [f'"{brand}" official site'] + ([f"{brand} {business_name}"] if business_name else [])
    for q in queries:
        page = fetcher.get("https://www.bing.com/search?q=" + urllib.parse.quote(q))
        for url in bing_results(page)[:6]:
            dom = _domain(url)
            if skip_domain(dom):
                continue
            home = f"https://{dom}/"
            got = fetcher.get(home)
            if got and site_matches(got, brand):
                return home, "bing"
    return None, None


def founder_name(page: str | None) -> tuple[str | None, str | None]:
    if not page:
        return None, None
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))
    # keywords case-insensitive, the name itself strictly Capitalised Words
    pats = [
        r"(?i:founded|started|created|launched) (?i:by) ([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})",
        r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})\b,? (?i:is )?(?i:the |our )?(?i:co-?founder|founder|owner|ceo)\b",
        r"\b(?i:co-?founder|founder|owner|ceo)\b,? ([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})\b",
    ]
    for p in pats:
        for m in re.finditer(p, text):
            words = m.group(1).split()
            if 2 <= len(words) <= 3 and not any(w.lower() in NAME_STOPWORDS for w in words) \
                    and all(w[0].isupper() for w in words):
                return words[0], " ".join(words[1:])
    return None, None


def page_emails(page: str | None, domain: str | None = None) -> list[str]:
    if not page:
        return []
    found = {html.unescape(e).lower().rstrip(".") for e in EMAIL_RE.findall(html.unescape(page))}
    good = [e for e in found
            if not any(b in e for b in BAD_LOCAL)
            and not any(d in e.split("@", 1)[1] for d in BAD_EMAIL_DOMAINS)
            and len(e) < 60]
    return rank_emails(good, domain)


def rank_emails(emails: list[str], domain: str | None, first: str | None = None) -> list[str]:
    def score(e: str) -> tuple:
        local, dom = e.split("@", 1)
        same = domain is not None and (dom == domain or dom.endswith("." + domain))
        pref = LOCAL_PREFERENCE.index(local) if local in LOCAL_PREFERENCE else len(LOCAL_PREFERENCE)
        is_first = bool(first) and local.startswith(first.lower())
        return (not same, not is_first, pref, len(local))
    return sorted(dict.fromkeys(emails), key=score)


def guess_emails(domain: str, first: str | None = None, last: str | None = None) -> list[str]:
    """Best guess first: a found first name at the domain, then the generic inboxes."""
    out = []
    if first:
        f = re.sub(r"[^a-z]", "", first.lower())
        if f:
            out.append(f"{f}@{domain}")
    return out + [f"hello@{domain}", f"info@{domain}", f"contact@{domain}", f"support@{domain}"]


def mx_ok(domain: str, resolver=None) -> bool:
    """True when the domain can receive mail (MX, or at least an A record)."""
    if resolver:
        return bool(resolver(domain))
    try:
        out = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=10).stdout
        if out.strip():
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        socket.gethostbyname(domain)
        return True
    except OSError:
        return False


def site_contacts(fetcher, website: str, brand: str | None) -> dict:
    """Read the home, contact and about pages: published emails and a founder's name."""
    dom = _domain(website)
    emails: list[str] = []
    first = last = None
    source = None
    for path in CONTACT_PATHS:
        page = fetcher.get(website if not path else website.rstrip("/") + path)
        if not page:
            continue
        for e in page_emails(page, dom):
            if e not in emails:
                emails.append(e)
        if not first:
            first, last = founder_name(page)
            if first:
                source = "site" + (path or "/")
        if emails and first:
            break
    return {"emails": rank_emails(emails, dom, first), "first_name": first, "last_name": last,
            "person_source": source, "domain": dom}


def enrich_seller(fetcher, row: dict, resolver=None) -> dict:
    """One candidate → website, contact, name. Returns the columns to update."""
    brand = row.get("brand")
    site, how = find_website(fetcher, brand, row.get("business_name"))
    if not site:
        return {"status": "no_website", "notes": "no site matched the brand (direct guesses + Bing)"}
    c = site_contacts(fetcher, site, brand)
    dom = c["domain"]
    upd: dict = {"website": site, "first_name": c["first_name"], "last_name": c["last_name"],
                 "person_source": c["person_source"], "notes": f"site via {how}"}
    published = [e for e in c["emails"] if e.split("@", 1)[1].endswith(dom)] or c["emails"]
    if published:
        upd.update(email=published[0], email_confidence="published", status="enriched")
        return upd
    if mx_ok(dom, resolver):
        upd.update(email=guess_emails(dom, c["first_name"], c["last_name"])[0],
                   email_confidence="pattern", status="enriched",
                   notes=upd["notes"] + "; pattern address, Instantly verifies on import")
        return upd
    upd.update(status="no_email", notes=upd["notes"] + "; no published address and no MX")
    return upd
