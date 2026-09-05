"""Shopify stores: the second lead source, and the one nobody blocks.

Amazon fingerprints the crawl and answers with captchas — seven of them on
2026-09-03, then the 2 KB "Sorry! Something went wrong!" page — so the
harvest cannot depend on one company's tolerance for its only inventory.
Every Shopify store publishes its own shop record and its whole catalogue as
JSON, to anyone, with no captcha, no cookie and no login:

  /meta.json                 name, city, province, country, currency, primary domain
  /products.json?limit=250   every published product: vendor, type, created_at, variants
  /products/<handle>         the review app's JSON-LD aggregateRating
  /policies/contact-information, /pages/about …   the address and name the store publishes

That is the same chain the Amazon side walks (Best Sellers → product page →
seller profile → the brand's own site), one platform over, and it lands in
the same `harvest_sellers` rows (platform 'shopify', source 'shopify') so the
founder lane, the Instantly push and the SuperSearch owner lookup treat a
Shopify brand exactly like an Amazon one.

Two things genuinely differ, and both are recorded on the row:

  Size.  Amazon publishes a seller-feedback count; Shopify publishes nothing
         of the kind. The size signal is the review count the store's own
         review app (Judge.me, Loox, Yotpo, Stamped, Okendo, Shopify Reviews)
         prints as JSON-LD on a product page, scaled from the sampled
         products to the whole catalogue and divided by the store's age. It
         is rougher than the Amazon estimate and every figure derived from it
         is labeled an estimate. A store with no review count anywhere is
         still a candidate — unknown never disqualifies, exactly as on the
         Amazon side — and the push's revenue floor keeps such a row in the
         founder lane rather than the campaign.
  Hook.  The founder-lane hook on Amazon is the FBA fulfilment-fee band. A
         Shopify brand pays a carrier instead, so the hook is the USPS Ground
         Advantage / UPS weight band (`shipping_cliff`): the same arithmetic
         and the same thirty-second check by the seller, off a different rate
         card. outreach picks the function by the row's platform.

Discovery costs Shopify nothing either: the Wayback Machine's CDX index
lists the myshopify.com homepages the archive has captured, which is a free
list of store handles that never asks Shopify who we are.

Posture, unchanged from the Amazon side (GROWTH.md, OPERATIONS.md): public
pages only, a home connection, roughly one request a second, US founder-run
brands only, and a role inbox goes to the founder lane rather than the cold
campaign. `Blocked` is an Amazon concept and does not appear here; a 429 or
503 from a store goes through the fetcher's ordinary throttle-and-retry path.

Everything above `crawl` is a pure function over text or JSON. Only `crawl`,
`load_handles` and `download_cdx` fetch anything.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .. import icp
from . import amazon
from . import enrich as enrichmod
from .fetch import Fetcher
from .run import _keep_history, _log_event, _now

# -- knobs ----------------------------------------------------------------------

LIMIT = int(os.environ.get("HARVEST_SHOPIFY_LIMIT", "120"))          # stores per `hubricon harvest shopify`
CDX_PAGES = int(os.environ.get("HARVEST_SHOPIFY_CDX_PAGES", "40"))   # index pages of myshopify homepages to list
SAMPLE = int(os.environ.get("HARVEST_SHOPIFY_SAMPLE", "3"))          # product pages read per store, for reviews
# A review is left on roughly one order in fifty (review apps chase every
# order by email, so the rate is far higher than Amazon's ~1 in 500 seller
# feedback). Calibrated loosely and used only to band a store; the row says
# "est." everywhere it appears.
ORDERS_PER_REVIEW = float(os.environ.get("HARVEST_SHOPIFY_ORDERS_PER_REVIEW", "50"))
MIN_ANNUAL = float(os.environ.get("HARVEST_SHOPIFY_MIN_ANNUAL", "500000"))
MAX_ANNUAL = float(os.environ.get("HARVEST_SHOPIFY_MAX_ANNUAL", "40000000"))
MIN_PRODUCTS, MAX_PRODUCTS = 3, 2000   # under: a hobby store; over: a marketplace, not a brand
DOMINANT_SHARE = 0.7                   # one vendor this far into the catalogue is a private label
MAX_BRANDS = 5                         # distinct vendors kept on the row
PAUSE_BETWEEN_STORES = 1.0             # seconds; per-host pacing barely applies when every store is a host

GRAMS_PER_OZ = 28.3495


def seller_id(handle: str) -> str:
    """The row key for a store. The myshopify handle never changes, while the
    primary domain can be re-pointed, so the handle is what identifies a store."""
    return f"{handle}.myshopify.com"


def is_shopify_host(domain: str | None) -> bool:
    """True when the host is Shopify's own, not a brand's. A store that never
    bought a domain publishes nothing we can write to."""
    d = (domain or "").strip().lower().rstrip(".")
    return d == "myshopify.com" or d.endswith(".myshopify.com")


def store_fetcher() -> Fetcher:
    """The pace for a Shopify pass: 2–3.5 s per host, 30 s timeout, through the
    Mac's own Chrome.

    Amazon's fetcher waits 7–12 s because Amazon counts requests per client;
    here every store is a different host and a different company, so per-host
    pacing barely applies. `crawl` sleeps ~1 s between stores instead.

    Chrome is not optional. On 2026-09-04 every `/meta.json` and
    `/products.json` fetched with a plain urllib session answered 429 — large
    stores and small, custom domains and myshopify ones alike — while the same
    URLs returned their JSON in headless Chrome from the same connection. It is
    the Amazon lesson again: the client is fingerprinted, not just the pace.
    One Chrome process per page costs about six seconds, so a store's three
    pages take roughly twenty; `HARVEST_RUN_ALL_SHOPIFY` is sized for that.
    """
    return Fetcher(min_interval=2.0, jitter=1.5, timeout=30, chrome_hosts=("",))


# -- discovery: myshopify handles out of the Wayback CDX index ---------------------

# Shopify's own subdomains are on myshopify.com too and are not stores.
SHOPIFY_OWN = frozenset((
    "admin", "accounts", "shop", "checkout", "partners", "help", "cdn", "apps", "community",
    "changelog", "themes", "www", "status", "docs", "experts", "exchange", "app", "api",
))
HANDLE_RE = re.compile(r"^https?://([a-z0-9][a-z0-9.\-]*)\.myshopify\.com/?$", re.I)

# Shopify names an unclaimed development store after a random blob — the
# archive's listing is full of `0003bd-ca`, `0c2e44-cb`, `00dze5-yu`,
# `ctq2ua-gn`. They are not brands, they never carry a product, and on
# 2026-09-04 they were the majority of the handles a raw listing returned.
#
# A real name has at least one hyphen-separated part that reads as a word:
# three or more letters with a vowel in them, once a trailing number is set
# aside (`metrolix1` and `ctpremierwpc-1081` are real stores; the number is a
# suffix, not the name). A blob has no such part — `ctq2ua` carries its digit
# in the middle and `gn` is too short — so the whole handle is dropped.
_TRAILING_DIGITS = re.compile(r"\d+$")
_VOWELS = frozenset("aeiouy")


def _word_like(segment: str) -> bool:
    s = _TRAILING_DIGITS.sub("", segment)
    return len(s) >= 3 and s.isalpha() and bool(set(s) & _VOWELS)


def looks_like_a_dev_store(handle: str) -> bool:
    """True when the handle is a generated blob rather than somebody's brand."""
    return not any(_word_like(part) for part in (handle or "").lower().split("-"))
CDX_FILTER = "original:^https?://[a-z0-9-]+\\.myshopify\\.com/?$"
CDX = ("https://web.archive.org/cdx/search/cdx?url=myshopify.com&matchType=domain"
       "&filter=statuscode:200&filter=" + urllib.parse.quote(CDX_FILTER, safe="")
       + "&fl=original,timestamp&collapse=urlkey&from=2022")
DEFAULT_CDX_FILE = Path.home() / ".hubricon" / "harvest" / "shopify-stores.cdx"


def parse_cdx(text: str) -> list[str]:
    """CDX lines (original, timestamp) → store handles, newest capture first.

    A handle captured last month is likelier to still be trading than one
    captured in 2022, and the crawl reads the list from the top, so recency is
    the ordering. Shopify's own subdomains and anything with a dot inside the
    label (a store's custom sub-subdomain, a CDN host) are not stores.
    """
    newest: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        m = HANDLE_RE.match(parts[0].strip())
        if not m:
            continue
        label = m.group(1).lower()
        if "." in label or label in SHOPIFY_OWN or len(label) < 3 or looks_like_a_dev_store(label):
            continue
        ts = parts[1] if len(parts) > 1 and parts[1].isdigit() else ""
        if ts >= newest.get(label, ""):
            newest[label] = ts
    return [h for h, _ in sorted(newest.items(), key=lambda kv: kv[1], reverse=True)]


# `showNumPages` only answers with a number when it is asked on its own: add
# `fl=` or `collapse=` and the archive replies "- -" instead (checked against
# the live API on 2026-09-04, which is how the first version of this came to
# read zero pages). So the count is asked for without them, and the rows are
# fetched with them.
CDX_COUNT = ("https://web.archive.org/cdx/search/cdx?url=myshopify.com&matchType=domain"
             "&filter=statuscode:200&filter=" + urllib.parse.quote(CDX_FILTER, safe="")
             + "&showNumPages=true")


def sample_pages(total: int, pages: int) -> list[int]:
    """Which index pages to read, spread evenly across the whole index.

    The CDX index is sorted by URL key, so its 42,897 pages run alphabetically:
    page 0 is `0-5-yas-kiz-bebek-giysileri`, page 200 is `0c2e44-cb`. Reading
    the first N pages therefore returns nothing but handles beginning with a
    digit — overwhelmingly Shopify's own auto-generated dev stores, not brands.
    Spreading the same N pages across the index samples the whole alphabet
    instead, which is what makes the listing worth crawling at all.
    """
    if total <= 0 or pages <= 0:
        return []
    if total <= pages:
        return list(range(total))
    step = total / pages
    return sorted({int(i * step) for i in range(pages)})


def page_count(text: str | None) -> int:
    """The index-page count the archive answers with, bare or inside Chrome's
    viewer. Anything that is not a number — including the "- -" the API returns
    when `fl=` or `collapse=` ride along — is zero."""
    body = (text or "").strip()
    if not body.isdigit():
        m = _PRE_JSON.search(body)
        body = html.unescape(m.group(1)).strip() if m else ""
    return int(body) if body.isdigit() else 0


def download_cdx(fetcher, pages: int = CDX_PAGES, log=print) -> str:
    """The index, page by page, as wayback.download_cdx does it — but sampled
    across the whole index rather than swept from the front (see sample_pages).
    `pages` caps a listing that would otherwise run for days."""
    total = page_count(fetcher.get(CDX_COUNT))
    wanted = sample_pages(total, pages)
    log(f"shopify: {total} CDX index pages of archived myshopify homepages, "
        f"sampling {len(wanted)} across the whole index")
    chunks = []
    for i in wanted:
        text = fetcher.get(f"{CDX}&page={i}")
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def archive_fetcher() -> Fetcher:
    """The listing comes from web.archive.org, which is not Shopify and does not
    want a browser: plain HTTP at the pace wayback.py already found acceptable.

    This is a separate fetcher on purpose. `store_fetcher` routes every host
    through Chrome, and Chrome answers a plain-text CDX response with its
    viewer — `<pre>42897</pre>` instead of `42897` — which read as zero pages
    and made the first live run (2026-09-04) list nothing at all.
    """
    return Fetcher(min_interval=3.0, jitter=2.0, timeout=90, throttle_pause=60.0)


def load_handles(fetcher=None, cdx_file: Path | None = None, log=print) -> list[str]:
    """The store list, from disk when it was saved, else listed once and saved.
    Delete ~/.hubricon/harvest/shopify-stores.cdx to re-list.

    `fetcher` defaults to archive_fetcher(): pass one only in tests, or when the
    caller has a plain-HTTP fetcher of its own."""
    path = Path(cdx_file) if cdx_file else DEFAULT_CDX_FILE
    if path.exists():
        return parse_cdx(path.read_text())
    text = download_cdx(fetcher or archive_fetcher(), log=log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return parse_cdx(text)


# -- discovery, the good one: Shopify's own marketplace, through a search engine ----
#
# The archive's myshopify listing is free and nearly worthless: a store that
# succeeds buys a domain, so the archive captures *that* and the myshopify
# index keeps the dev stores, the abandoned shops and the hobby projects. The
# first live run (2026-09-04) read five of its handles and found no lead with
# both a size estimate and a real inbox.
#
# shop.app is Shopify's consumer marketplace. Every brand on it is a paying
# Shopify merchant that is actually trading, and search engines index those
# pages along with the brand's own domain. `site:shop.app <category>` is
# therefore a list of real Shopify stores, filtered by what they sell — and
# they all have their own domain, which is the difference between a lead we
# can write to and `hello@…myshopify.com`, which bounces.
#
# Measured on 2026-09-04: five category queries produced 23 candidate domains,
# of which corgicandle.com, pourandpenchant.com, thefoggydog.com and
# ruffwear.com answered /meta.json as live US stores. The misses cost one
# request each and are what the probe is for.

SEARCH_HOST = "shop.app"
SEARCH_URL = "https://www.bing.com/search?q={q}&count=30"
# Categories where founder-run product brands live. Rotated by half-day like
# the Amazon side, so a week's runs cover the list rather than re-reading it.
SEARCH_CATEGORIES = [
    "candles", "skincare", "dog collars", "coffee", "kitchen tools", "jewelry",
    "supplements", "tea", "hot sauce", "leather goods", "socks", "bath soap",
    "cutting boards", "water bottles", "yoga mats", "baby clothes", "pet treats",
    "hair care", "sunglasses", "backpacks", "candle holders", "cookware",
    "beard oil", "planners", "phone cases", "grill tools", "camping gear",
]
SEARCH_TERMS_PER_RUN = int(os.environ.get("HARVEST_SHOPIFY_SEARCH_TERMS", "6"))
# Domains that turn up beside real stores and can never be one. Measured over
# all 27 category searches on 2026-09-04: 116 candidate domains, and the
# publishers alone were a fifth of them — nytimes, forbes, consumerreports,
# goodhousekeeping, seriouseats, gq, even stackoverflow and a Texas government
# site under "tea". Each costs a six-second Chrome probe to learn nothing.
#
# Retailers and household brands are deliberately NOT here: rei.com,
# williams-sonoma.com and bombas.com really are stores, and it is the
# classifier's job to size them out — Barnes & Noble was caught on its 131
# vendors, which is the honest reason to reject it. A name list would only be
# guessing at the same verdict a request away.
SEARCH_SKIP_WORDS = ("wikipedia", "britannica", "review", "blog", "magazine", "guide",
                     "digest", "news", "vogue", "tripadvisor", "superpages", "yellowpages",
                     "dictionary", "thespruce", "dogster", "petfinder", "wikihow",
                     "nytimes", "forbes", "consumerreports", "goodhousekeeping", "seriouseats",
                     "foodnetwork", "menshealth", "stackoverflow", "outdoorgearlab",
                     "findthisbest", "epicurious", "bonappetit", "allrecipes", "wirecutter",
                     "buzzfeed", "reddit", "quora", "pinterest", "youtube", "medium.com")
# A shop is never on one of these. Cheaper and more durable than naming sites.
NEVER_A_STORE_TLDS = (".gov", ".edu", ".mil", ".int")


def search_terms(n: int = SEARCH_TERMS_PER_RUN, today=None, slot: int | None = None) -> list[str]:
    """Rotate the category list by half-day, exactly as run.pick_categories does."""
    now = datetime.now()
    today = today or now.date()
    if slot is None:
        slot = 1 if now.hour >= 12 else 0
    start = ((today.timetuple().tm_yday * 2 + slot) * n) % len(SEARCH_CATEGORIES)
    return [SEARCH_CATEGORIES[(start + i) % len(SEARCH_CATEGORIES)] for i in range(min(n, len(SEARCH_CATEGORIES)))]


def search_url(term: str) -> str:
    return SEARCH_URL.format(q=urllib.parse.quote(f"site:{SEARCH_HOST} {term}"))


def search_domains(page: str | None) -> list[str]:
    """A search page → the brand domains worth probing, in result order."""
    out: list[str] = []
    for url in enrichmod.bing_results(page):
        d = enrichmod._domain(url)
        if not d or d == SEARCH_HOST or d in out:
            continue
        if enrichmod.skip_domain(d) or enrichmod.offshore_domain(d):
            continue
        if d.endswith(NEVER_A_STORE_TLDS) or any(w in d for w in SEARCH_SKIP_WORDS):
            continue
        out.append(d)
    return out


def handle_from_meta(meta: dict | None) -> str | None:
    """The myshopify handle a store names in its own metadata. That handle is
    the row key, so a store found by domain and the same store found in the
    archive are one row, not two."""
    host = ((meta or {}).get("myshopify_domain") or "").strip().lower()
    return host[: -len(".myshopify.com")] if host.endswith(".myshopify.com") else None


def discover(search_fetcher, store_fetcher, terms: list[str] | None = None,
             log=print) -> tuple[list[str], dict[str, dict]]:
    """Category searches → candidate domains → the ones that really are stores.

    Returns (handles, metas). Two fetchers because they want different
    clients: the search engine is happy with plain HTTP, a Shopify store
    answers 429 to anything but a browser.
    """
    terms = terms if terms is not None else search_terms()
    domains: list[str] = []
    for term in terms:
        found = search_domains(search_fetcher.get(search_url(term)))
        for d in found:
            if d not in domains:
                domains.append(d)
        # A term that returns nothing is reported, not passed over: a barren
        # search and a broken one look identical from here, and the Amazon side
        # lost five category slugs to exactly that silence.
        log(f"  shopify search '{term}': {len(found)} candidate domain(s)"
            + ("  <- nothing; check the term" if not found else ""))
    handles: list[str] = []
    metas: dict[str, dict] = {}
    for d in domains:
        meta = parse_meta(store_fetcher.get(f"https://{d}/meta.json"))
        handle = handle_from_meta(meta)
        if not handle or handle in metas:
            continue
        handles.append(handle)
        metas[handle] = meta
    log(f"shopify search: {len(domains)} domain(s) probed, {len(handles)} live Shopify store(s)")
    return handles, metas


# -- /meta.json ------------------------------------------------------------------

# A store that is closed, unpaid or not launched answers every path with the
# password page instead of JSON. It is not a lead and it is not an error.
PASSWORD_MARKERS = ('name="password"', "name='password'", 'action="/password"', "opening soon",
                    "store is currently unavailable", "this shop will be available")


def looks_password_page(text: str | None) -> bool:
    low = (text or "").lower()
    return any(m in low for m in PASSWORD_MARKERS)


_PRE_JSON = re.compile(r"<pre[^>]*>(.*?)</pre>", re.S | re.I)


def json_payload(text: str | None) -> dict | list | None:
    """The JSON in `text`, whether it arrived bare or inside Chrome's viewer.

    These endpoints are fetched through headless Chrome (see store_fetcher),
    and `--dump-dom` hands back the browser's JSON viewer rather than the
    bytes: `<html>…<body><pre>{…}</pre></body></html>`, with the entities
    escaped. Unwrap that, then parse. A page that is not JSON at all — a
    password page, an error, a redirect to a marketing site — returns None.
    """
    if not text:
        return None
    body = text.lstrip()
    if not body.startswith(("{", "[")):
        m = _PRE_JSON.search(text)
        if not m:
            return None
        body = html.unescape(m.group(1)).strip()
        if not body.startswith(("{", "[")):
            return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def parse_meta(text: str | None) -> dict | None:
    """/meta.json → the shop record, or None when the store is closed.

    The Shopify analogue of the Amazon seller profile: it is the store saying
    who and where it is, in its own words, on a public URL.
    """
    doc = json_payload(text)
    if doc is None:
        return None
    if not isinstance(doc, dict) or not doc.get("name"):
        return None
    return {
        "name": (doc.get("name") or "").strip(),
        "city": (doc.get("city") or "").strip() or None,
        "province": (doc.get("province") or "").strip() or None,
        "country": (doc.get("country") or "").strip().upper() or None,
        "currency": (doc.get("currency") or "").strip().upper() or None,
        "domain": (doc.get("domain") or "").strip().lower() or None,
        "myshopify_domain": (doc.get("myshopify_domain") or "").strip().lower() or None,
        "description": (doc.get("description") or "").strip() or None,
        "published_products_count": doc.get("published_products_count"),
    }


# Shopify's own checkout host. A store whose primary domain is configured as
# `checkout.<brand>.com` reports that in meta.json — hydrojug.myshopify.com did
# on 2026-09-04 — and it is never the storefront a customer or a founder-lane
# email should be pointed at.
_NON_STOREFRONT_LABELS = ("checkout.", "checkouts.", "pay.")


def store_domain(handle: str, meta: dict | None) -> str:
    """The brand's own storefront host: the primary domain the store names,
    with Shopify's checkout label stripped, else its myshopify host. This is
    what the row records as the website and where the contact pages are read."""
    domain = ((meta or {}).get("domain") or "").strip().lower()
    for label in _NON_STOREFRONT_LABELS:
        if domain.startswith(label):
            domain = domain[len(label):]
            break
    return domain or seller_id(handle)


# -- /products.json --------------------------------------------------------------

def _price(variants: list | None) -> float | None:
    """The cheapest published variant: the price a first order is likeliest to pay."""
    out = []
    for v in variants or []:
        try:
            p = float(v.get("price"))
        except (TypeError, ValueError):
            continue
        if p > 0:
            out.append(p)
    return min(out) if out else None


def grams_to_oz(grams) -> float | None:
    """Shipping weight in ounces. Shopify stores grams; 0 means the merchant
    never entered one, not a weightless product, so it reads as unknown."""
    try:
        g = float(grams)
    except (TypeError, ValueError):
        return None
    return round(g / GRAMS_PER_OZ, 3) if g > 0 else None


def parse_products(text: str | None) -> list[dict]:
    """/products.json → one flat dict per published product, catalogue order.

    Shopify caps the endpoint at 250 a page; the harvest reads one page, so a
    bigger catalogue is truncated there and the size estimate floors with it.
    """
    doc = json_payload(text)
    if not isinstance(doc, dict):
        return []
    out = []
    for p in (doc.get("products") or []) if isinstance(doc, dict) else []:
        if not isinstance(p, dict) or not p.get("handle"):
            continue
        variants = p.get("variants") or []
        out.append({
            "handle": p["handle"],
            "title": (p.get("title") or "").strip()[:200] or None,
            "vendor": (p.get("vendor") or "").strip() or None,
            "product_type": (p.get("product_type") or "").strip() or None,
            "created_at": p.get("created_at"),
            "tags": p.get("tags") or [],
            "price": _price(variants),
            "weight_oz": grams_to_oz((variants[0] or {}).get("grams") if variants else None),
            "sku": (variants[0] or {}).get("sku") if variants else None,
        })
    return out


def vendor_profile(products: list[dict]) -> dict:
    """→ {vendors, dominant, share, category}: who makes what is in this catalogue.

    A private-label brand's catalogue is its own name over and over; a
    dropshipper's or a boutique's is thirty other people's brands. The share
    of the dominant vendor is the cheapest available separator.
    """
    counts = Counter(p["vendor"] for p in products if p.get("vendor"))
    total = sum(counts.values())
    dominant, n = counts.most_common(1)[0] if counts else (None, 0)
    share = (n / total) if total else 0.0
    types = Counter(p["product_type"] for p in products if p.get("product_type"))
    return {
        "vendors": [v for v, _ in counts.most_common()],
        "dominant": dominant if share >= DOMINANT_SHARE else None,
        "top_vendor": dominant,
        "share": round(share, 3),
        "category": types.most_common(1)[0][0] if types else None,
    }


def store_age_years(products: list[dict], now: datetime | None = None) -> float:
    """Years since the oldest product was published — the best public proxy for
    how long the store has been selling. Floored at half a year so a brand-new
    store's lifetime reviews do not annualise into a fantasy."""
    now = now or datetime.now(timezone.utc)
    oldest = None
    for p in products:
        stamp = p.get("created_at")
        if not stamp:
            continue
        try:
            dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if oldest is None or dt < oldest:
            oldest = dt
    if oldest is None:
        return 0.5
    return max(0.5, (now - oldest).days / 365.25)


# -- /products/<handle>: the review count -----------------------------------------

# The six review apps that cover almost every store. Their markup differs but
# they all inject JSON-LD, and they all leave a class or a script name behind
# even when the rating is rendered client-side (in which case we know there
# ARE reviews but not how many).
REVIEW_APP_MARKERS = ("judge.me", "jdgm-", "loox.io", "loox-", "yotpo", "stamped.io", "stamped-",
                      "okendo", "oke-", "spr-badge", "shopify-product-reviews", "reviewsio",
                      "junip", "fera.ai", "rivyo")
AGGREGATE_RE = re.compile(r'"aggregateRating"\s*:\s*\{(.*?)\}', re.S)
COUNT_RE = re.compile(r'"(?:reviewCount|ratingCount)"\s*:\s*"?([\d,]+)"?')
RATING_RE = re.compile(r'"ratingValue"\s*:\s*"?([\d.]+)"?')


def _int(s: str | None) -> int | None:
    digits = re.sub(r"[^\d]", "", s or "")
    return int(digits) if digits else None


def review_count(page: str | None) -> int | None:
    """The reviewCount out of a product page's JSON-LD aggregateRating.

    A page carries several JSON-LD blocks (Product, Organization, Breadcrumbs)
    and an app may repeat the rating in each; the largest is the product's own
    total. The number arrives bare (1204), quoted ("1204") or quoted with
    separators ("1,204") depending on the app, so all three are read.
    Returns None when the page carries no aggregateRating at all — which is
    not the same as zero reviews and is never treated as zero.
    """
    if not page:
        return None
    counts = [_int(m) for block in AGGREGATE_RE.findall(page) for m in COUNT_RE.findall(block)]
    if not counts:
        counts = [_int(m) for m in COUNT_RE.findall(page)]
    counts = [c for c in counts if c is not None]
    return max(counts) if counts else None


def rating_value(page: str | None) -> float | None:
    m = RATING_RE.search(page or "")
    try:
        return round(float(m.group(1)), 2) if m else None
    except ValueError:
        return None


def has_reviews(page: str | None) -> bool:
    """True when a review app is on the page at all. A store whose app renders
    the count in JavaScript still shows its widget's markup, so this separates
    "no reviews to find" from "reviews exist, the number is not in the HTML"."""
    low = (page or "").lower()
    return any(m in low for m in REVIEW_APP_MARKERS)


def estimate_annual(review_counts: list[int | None], n_products: int, asp: float | None,
                    age_years: float, orders_per_review: float = ORDERS_PER_REVIEW) -> float | None:
    """Annual sales estimate, in dollars, from the sampled review counts.

        Σ reviews(sampled) × (catalogue / sampled) × orders-per-review × ASP
        ────────────────────────────────────────────────────────────────────
                              store age in years

    Reviews are lifetime, so the numerator is lifetime revenue and the divisor
    turns it into a year. Every step is an approximation — the sample may miss
    the store's one hit product, the orders-per-review rate varies by category
    and by how hard the app chases — so the result exists to put a store in or
    out of a band, and the row calls it an estimate.

    A sampled page with no aggregateRating counts as a sampled product but
    contributes nothing; when no sampled page carried one at all the answer is
    None (unknown), never zero.
    """
    known = [c for c in review_counts if c is not None]
    if not known or not asp or not n_products:
        return None
    sampled = max(1, len(review_counts))
    lifetime = sum(known) * (n_products / sampled) * orders_per_review * asp
    return round(lifetime / max(0.5, age_years), 2)


# -- the shipping cliff: the founder-lane hook on this platform --------------------

# Where a Shopify brand's parcel actually changes price.
#
# This list used to start at 4, 8 and 12 oz, because until 2026-07-12 USPS
# Ground Advantage priced those tiers separately and the founder-lane hook was
# built on them. On that date USPS collapsed all four sub-pound tiers into one:
# at published Commercial rates every parcel under a pound costs the same within
# a zone, whatever it weighs. "You are 1.5 oz over the 8 oz band" became a false
# statement about a stranger's business, so those edges are gone from here —
# which removes the claim from `hubricon outreach` and the cold engine at once,
# since both read this list.
#
# The pound boundary survives and is worth far more than any ounce tier was,
# because USPS rounds anything over a pound up to the next whole pound: a parcel
# at 16.5 oz is billed at two pounds, and the same parcel at 15.9 oz is billed
# at the flat sub-pound rate. cold/priors.py prices that step from Notice 123.
SHIPPING_BAND_EDGES_OZ = [16 * lb for lb in range(1, 71)]
MIN_HOOK_WEIGHT_OZ = 16.0  # under a pound the rate is flat: nothing to drop into


def shipping_cliff(weight_oz: float | None) -> tuple[int, float] | None:
    """→ (band edge below, ounces above it), or None when unknown or already
    under a pound. Mirrors amazon.fee_cliff so outreach can pick one by platform."""
    if not weight_oz or weight_oz <= SHIPPING_BAND_EDGES_OZ[0]:
        return None
    below = max(e for e in SHIPPING_BAND_EDGES_OZ if e < weight_oz)
    return below, round(weight_oz - below, 3)


def band_names(edge_oz: int) -> tuple[str, str]:
    """(what it would pay under the edge, what it pays now) for the 16 oz edge
    and every pound after it.

    The pair is not two adjacent rows of the rate card, because of the round-up:
    a parcel over one pound bills at *two*, so the brand's realistic alternative
    to the 2 lb rate is the flat sub-pound rate rather than the 1 lb rate that
    only an exactly-16.000 oz parcel ever pays. Naming the 1 lb rate here would
    understate the saving by about half.
    """
    pounds = edge_oz // 16
    below = "under a pound" if pounds == 1 else f"{pounds} lb"
    return below, f"{pounds + 1} lb"


# -- classification ---------------------------------------------------------------

def classify_meta(meta: dict) -> tuple[str | None, str]:
    """The shop record alone: US and dollars, or not a prospect.

    Runs before the catalogue is fetched, so a Canadian store costs one
    request rather than five. (None, "") means nothing disqualifying yet.
    """
    country, currency = meta.get("country"), meta.get("currency")
    if country and country != "US":
        return "skip_non_us", f"store country {country}, currency {currency or '?'}"
    if currency and currency != "USD":
        return "skip_non_us", f"store currency {currency}, country {country or '?'}"
    return None, ""


def big_parent_word(*names: str | None) -> str | None:
    """Which conglomerate name matched, for the note. amazon.looks_big_parent
    answers yes or no; a row that was skipped on a name should record which
    one, so the judgement can be checked later."""
    joined = " ".join(n or "" for n in names).lower()
    return next((w for w in amazon.BIG_PARENT_WORDS if w in joined), None)


def classify_catalog(meta: dict, products: list[dict], vendors: dict | None = None) -> tuple[str, str]:
    """The catalogue: is this one founder's brand, and is it brand-sized?"""
    vendors = vendors or vendor_profile(products)
    name = meta.get("name") or ""
    n = len(products)
    if n == 0:
        return "no_website", "no published products"
    if n < MIN_PRODUCTS:
        return "skip_size", f"catalog too small ({n} product{'s' if n != 1 else ''})"
    if n > MAX_PRODUCTS:
        return "skip_size", f"marketplace-scale catalog ({n} products)"
    dominant = vendors["dominant"]
    # Private label is the whole ICP: the store and the brand are the same
    # company. Most DTC stores put their own name in `vendor`, so one vendor
    # covering the catalogue is the signal whether or not the string matches
    # the shop name (a store called "Shop Riverbend" sells vendor "Riverbend").
    if not dominant and len(vendors["vendors"]) >= 3:
        return "skip_reseller", f"multi-brand catalog ({len(vendors['vendors'])} vendors, " \
                                f"top {vendors['share']:.0%})"
    word = big_parent_word(name, dominant)
    if word:
        # Say that this came off a list, not off the store's own numbers. A
        # name list is a cost optimisation — it saves the pages a real
        # measurement would cost — and it must never read like a finding, or
        # nobody can tell a wrong skip from a right one.
        return "skip_size", f"name on the conglomerate list ({word!r}), not a measured size"
    bucket, why = icp.off_icp(name, None, meta.get("domain"))
    if bucket:
        return "skip_reseller", why
    if dominant and amazon.looks_private_label(dominant, name, None):
        return "candidate", f"private label: {vendors['share']:.0%} of the catalog is vendor {dominant!r}, " \
                            f"matching the store name"
    if dominant:
        return "candidate", f"{vendors['share']:.0%} of the catalog is vendor {dominant!r}"
    return "candidate", f"{len(vendors['vendors'])} vendor(s), none dominant"


def classify_size(est_annual: float | None) -> tuple[str | None, str]:
    """The revenue band, from the review estimate. Unknown never disqualifies:
    the row stays a candidate with no estimate, and push's revenue floor keeps
    it out of the campaign and in the founder lane."""
    if est_annual is None:
        return None, "no review count on the sampled product pages"
    if est_annual > MAX_ANNUAL:
        return "skip_size", f"est. ${est_annual:,.0f}/yr from reviews, over the ${MAX_ANNUAL:,.0f} ceiling"
    if est_annual < MIN_ANNUAL:
        return "skip_size", f"est. ${est_annual:,.0f}/yr from reviews, under the ${MIN_ANNUAL:,.0f} floor"
    return None, f"est. ${est_annual:,.0f}/yr from reviews"


def classify(meta: dict, products: list[dict] | None, est_annual: float | None = None) -> tuple[str, str]:
    """The whole verdict for one store, as a pure function over what was read."""
    status, note = classify_meta(meta)
    if status:
        return status, note
    if products is None:
        return "candidate", "catalog not read"
    status, note = classify_catalog(meta, products)
    if status != "candidate":
        return status, note
    size_status, size_note = classify_size(est_annual)
    if size_status:
        return size_status, size_note
    return "candidate", f"{note}; {size_note}"


# -- contact: what the store publishes about itself -------------------------------

# The two /policies/ pages are Shopify's own: every store has them, the
# contact-information one is the page Shopify's own merchant terms tell a
# store to fill in with a legal name and address, and neither is behind a
# theme's navigation. They are read before the themed pages.
CONTACT_PATHS = ("/policies/contact-information", "/policies/legal-notice", "/pages/contact",
                 "/pages/contact-us", "/pages/about", "/pages/about-us", "/pages/our-story", "")
US_ADDRESS_RE = re.compile(
    r"(\d{1,6}[-\w]*\s+[A-Za-z0-9.,'#\- ]{2,80}?),\s*([A-Za-z][A-Za-z .'-]{1,39}),\s*"
    r"([A-Z]{2})[ ,]+(\d{5})(?:-\d{4})?(?!\d)")
LEGAL_NAME_RE = re.compile(
    r"(?:trade|legal|company|business|registered|entity)\s+name\s*[:\-]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9&.,'\- ]{1,60}?"
    r"(?:LLC|L\.L\.C\.?|Inc\.?|Incorporated|Corp\.?|Corporation|Co\.|Ltd\.?|Limited|LP|LLP))(?=[\s.,;|]|$)",
    re.I)


def detag(page: str | None) -> str:
    """Page text with the markup, scripts and styles gone. The scripts matter:
    a Shopify theme inlines the whole cart and analytics config as JSON, and an
    address regex run over that finds nonsense."""
    if not page:
        return ""
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()


def parse_us_address(page_or_text: str | None) -> dict | None:
    """A US postal address out of a contact page: number + street, City, ST zip.

    Returns None for anything that is not unambiguously US-shaped, which is
    the point — a store that publishes no US address does not get one invented
    from a partial match.
    """
    text = detag(page_or_text) if "<" in (page_or_text or "") else (page_or_text or "")
    m = US_ADDRESS_RE.search(text)
    if not m:
        return None
    street, city, state, zip_code = (g.strip(" ,") for g in m.groups())
    return {"address": f"{street}, {city}, {state} {zip_code}", "city": city,
            "state": state, "zip": zip_code}


def parse_business_name(page_or_text: str | None) -> str | None:
    """The legal name off a 'Trade name: … LLC' line on the contact-information
    policy. Requires an entity suffix: without one the line is prose, not a
    legal name, and a wrong legal name in the founder's brief is worse than none."""
    text = detag(page_or_text) if "<" in (page_or_text or "") else (page_or_text or "")
    m = LEGAL_NAME_RE.search(text)
    return m.group(1).strip(" ,.") if m else None


def store_contact(fetcher, website: str, brand: str | None, resolver=None) -> dict:
    """The store's own contact pages → address, legal name, person, email.

    Reuses the generic enrichment (enrich.site_contacts, which stops as soon as
    it has both an email and a name) with the Shopify path list in front, then
    reads the US address and legal name out of the pages it already fetched.
    """
    c = enrichmod.site_contacts(fetcher, website, brand, paths=CONTACT_PATHS)
    dom = c["domain"]
    out: dict = {"email": None, "email_confidence": None, "first_name": c["first_name"],
                 "last_name": c["last_name"], "person_source": c["person_source"],
                 "business_name": None, "address": None, "city": None, "state": None,
                 "status": "candidate", "note": ""}
    for path in CONTACT_PATHS:
        page = c["pages"].get(path)
        if not page:
            continue
        out["business_name"] = out["business_name"] or parse_business_name(page)
        addr = parse_us_address(page)
        if addr and not out["address"]:
            out.update(address=addr["address"], city=addr["city"], state=addr["state"])
    tld = enrichmod.offshore_domain(dom)
    if tld:
        out.update(status="skip_non_us", note=f"store domain is a {tld} domain")
        return out
    # An offshore address anywhere on the site is a fact about the company,
    # whether or not it sits at the company's own domain.
    offshore = next(((e, enrichmod.offshore_domain(e)) for e in c["emails"]
                     if enrichmod.offshore_domain(e)), None)
    if offshore:
        out.update(email=offshore[0], status="skip_non_us",
                   note=f"contact address on a {offshore[1]} domain")
        return out
    # Only an address at the store's own domain counts as published. A contact
    # page often carries someone else's — a supplier, an agency, a sister brand
    # — and emailing it reaches the wrong company, which reads worse to the
    # recipient than a guess at the right one. Same rule enrich.py applies to
    # the Amazon side, and for the same reason: a site there published a
    # supplier's address and we would have written to them (2026-09-04).
    published = [e for e in c["emails"] if e.split("@", 1)[1].endswith(dom)]
    if published:
        out.update(email=published[0], email_confidence="published", status="enriched",
                   note="published contact address")
        return out
    # Never guess an address at Shopify's own host. A store with no custom
    # domain has no inbox of its own: `hello@beantones.myshopify.com` resolves
    # (myshopify.com has an MX) and hard-bounces, and bounces are the one thing
    # a two-month-old sending domain cannot afford. The first live run
    # (2026-09-04) produced two such rows out of five, so this is the common
    # case for the stores this listing is full of, not an edge case.
    if is_shopify_host(dom):
        out.update(status="no_email",
                   note="no custom domain: the store is only on myshopify.com, which has no inbox")
        return out
    if enrichmod.mx_ok(dom, resolver):
        out.update(email=enrichmod.guess_emails(dom, c["first_name"], c["last_name"])[0],
                   email_confidence="pattern", status="enriched",
                   note="pattern address, Instantly verifies on import")
        return out
    out["note"] = "no published address and no MX"
    return out


# -- rows -------------------------------------------------------------------------

PIPELINE = ("candidate", "enriched", "pushed")


def keep_verdict(old: str | None, fresh: str) -> str:
    """The status to write when a store is read again.

    A row is never walked back down the pipeline: a re-read that finds a
    published address must not turn a `pushed` row into `enriched` and send
    the lead to Instantly a second time, and a status this pass cannot
    reproduce (skip_internal, a verdict a human or `requalify` wrote) is kept.
    A fresh skip is new evidence about the store and wins — that is how a
    brand that has outgrown the band, or gone quiet, leaves the campaign.
    Same rule as run._crawl_category, spelled out because this pass can
    produce `enriched` on its own and the Amazon one cannot.
    """
    if not old or old == fresh:
        return fresh
    if fresh not in PIPELINE:
        return fresh
    if old in PIPELINE:
        return old if PIPELINE.index(old) > PIPELINE.index(fresh) else fresh
    return old


def store_row(handle: str, meta: dict, products: list[dict], sampled: list[dict],
              vendors: dict, est_annual: float | None, contact: dict | None,
              status: str, note: str) -> dict:
    """The harvest_sellers row for one store.

    Same shape as an Amazon row so everything downstream is platform-blind;
    the columns that only Amazon can fill (top_bsr, ratings_12mo,
    ratings_lifetime, est_monthly_units) stay null rather than being faked,
    and `asins` holds product handles because that is this platform's item id.
    """
    contact = contact or {}
    name = meta.get("name")
    dominant = vendors.get("dominant")
    brand = dominant if (dominant and dominant != name
                         and amazon.looks_private_label(dominant, name, None)) else name
    return {
        "seller_id": seller_id(handle), "platform": "shopify", "source": "shopify",
        "seller_name": name, "brand": brand, "brands": vendors.get("vendors", [])[:MAX_BRANDS],
        "business_name": contact.get("business_name") or name,
        "address": contact.get("address"),
        "city": meta.get("city") or contact.get("city"),
        "state": meta.get("province") or contact.get("state"),
        # What the store said, so a skip_non_us row records the country that
        # disqualified it. A store that publishes no country at all has
        # already passed classify_meta, and 'US' is what lets the generic
        # enrich pass (which is US-only) pick the row up.
        "country": meta.get("country") or "US",
        "website": f"https://{store_domain(handle, meta)}/",
        "email": contact.get("email"), "email_confidence": contact.get("email_confidence"),
        "first_name": contact.get("first_name"), "last_name": contact.get("last_name"),
        "person_source": contact.get("person_source"),
        "asins": [{"asin": p["handle"], "brand": p.get("vendor"), "bsr": None, "price": p.get("price"),
                   "reviews": p.get("reviews"), "est_monthly_revenue": None} for p in sampled],
        "reviews_max": max((p.get("reviews") or 0 for p in sampled), default=0),
        "top_bsr": None, "top_category": vendors.get("category"),
        "est_monthly_units": None,
        "est_monthly_revenue": round(est_annual / 12, 2) if est_annual else None,
        "ratings_12mo": None, "ratings_lifetime": None,
        "status": status, "notes": note, "updated_at": _now(),
    }


def product_row(domain: str, sid: str, product: dict) -> dict:
    """One published product, in harvest_products. `asin` holds
    '<domain>/products/<handle>' — the item's public URL path, which is what
    this platform has instead of an ASIN and is unique across stores."""
    return {
        "asin": f"{domain}/products/{product['handle']}", "seller_id": sid,
        "brand": product.get("vendor"), "title": product.get("title"),
        "category": product.get("product_type"), "bsr": None, "price": product.get("price"),
        "reviews": product.get("reviews"), "weight_oz": product.get("weight_oz"), "dims": None,
        "fulfilled_by_amazon": False, "platform": "shopify",
        "est_monthly_units": None, "est_monthly_revenue": None, "seen_at": _now(),
    }


def catalogue_rows(domain: str, sid: str, got: dict) -> list[dict]:
    """Every product the store publishes, not the three we read pages for.

    `/products.json` returns the whole catalogue — up to 250 items with their
    vendor, type, price and weight — in *one* request, and the first version of
    this wrote only the three products it had also fetched HTML pages for, to
    attach a review count. The other two hundred were parsed, held in memory and
    thrown away.

    Keeping them costs nothing and pays twice: a teardown can show the brand its
    whole shelf rather than a sample of it, and the weights feed the category
    benchmark that makes the page credible. Only the sampled products carry a
    review count; the rest carry None, which is honest and is what the page
    already renders.

    Gated on the store having got past catalogue classification, so a reseller
    or a marketplace still contributes nothing.
    """
    if not got.get("sampled"):
        return []
    reviews = {p["handle"]: p.get("reviews") for p in got["sampled"]}
    rows = []
    for p in got.get("products") or []:
        row = product_row(domain, sid, p)
        row["reviews"] = reviews.get(p["handle"])
        rows.append(row)
    return rows


# -- the crawl ---------------------------------------------------------------------

def read_store(fetcher, handle: str, sample: int = SAMPLE, resolver=None, meta: dict | None = None) -> dict:
    """Everything one store publishes, in five requests or fewer.

    meta.json → products.json → up to `sample` product pages for the review
    count → the contact pages. Stops as soon as a verdict is settled, so a
    Canadian store costs one request and a password-protected one costs one.
    Returns the row fields and the product rows; nothing is written here.
    """
    meta_text = None if meta else fetcher.get(f"https://{seller_id(handle)}/meta.json")
    meta = meta or parse_meta(meta_text)
    if meta is None:
        note = "closed or password-protected" if (meta_text is None or looks_password_page(meta_text)) \
            else "no shop metadata published"
        return {"meta": None, "status": "no_website", "note": note, "products": [], "sampled": [],
                "vendors": {}, "est_annual": None, "contact": None}
    status, note = classify_meta(meta)
    if status:
        return {"meta": meta, "status": status, "note": note, "products": [], "sampled": [],
                "vendors": {}, "est_annual": None, "contact": None}

    # The catalogue and the product pages are read from the myshopify host, not
    # the brand's own domain. A headless storefront (Hydrogen/Oxygen) serves a
    # React app at its custom domain, so `/products.json` there answers with
    # HTML — thehydrojug.com did exactly that on 2026-09-04, while
    # hydrojug.myshopify.com returned all 250 products. The myshopify host is
    # always the classic storefront. The custom domain is still what the brand
    # publishes, so it stays the row's website and is where the contact and
    # policy pages are read from.
    domain = store_domain(handle, meta)
    store = seller_id(handle)
    products = parse_products(fetcher.get(f"https://{store}/products.json?limit=250"))
    if not products and domain != store:
        products = parse_products(fetcher.get(f"https://{domain}/products.json?limit=250"))
    vendors = vendor_profile(products)
    status, note = classify_catalog(meta, products, vendors)
    if status != "candidate":
        return {"meta": meta, "status": status, "note": note, "products": products, "sampled": [],
                "vendors": vendors, "est_annual": None, "contact": None}

    sampled = [dict(p) for p in products[:max(1, sample)]]
    for p in sampled:
        page = fetcher.get(f"https://{store}/products/{p['handle']}")
        p["reviews"] = review_count(page)
        p["has_review_app"] = has_reviews(page)
    prices = [p["price"] for p in sampled if p.get("price")]
    asp = sum(prices) / len(prices) if prices else None
    est_annual = estimate_annual([p["reviews"] for p in sampled], len(products), asp,
                                 store_age_years(products))
    size_status, size_note = classify_size(est_annual)
    if size_status:
        return {"meta": meta, "status": size_status, "note": size_note, "products": products,
                "sampled": sampled, "vendors": vendors, "est_annual": est_annual, "contact": None}

    contact = store_contact(fetcher, f"https://{domain}/", meta.get("name"), resolver)
    status = contact["status"]
    note = f"{note}; {size_note}" + (f"; {contact['note']}" if contact["note"] else "")
    return {"meta": meta, "status": status, "note": note, "products": products, "sampled": sampled,
            "vendors": vendors, "est_annual": est_annual, "contact": contact}


def crawl(db, fetcher, handles: list[str], limit: int = LIMIT, log=print, resolver=None,
          recheck: bool = False, metas: dict[str, dict] | None = None) -> dict:
    """Store handles → harvest_sellers / harvest_products rows, one store at a time.

    Handles already on file are skipped: a store's catalogue moves slowly and
    the point of a scheduled pass is new inventory. `recheck=True` reads them
    again anyway (a store's prices, weights and review counts age), and then
    an existing row's non-candidate verdict wins over a fresh 'candidate' —
    the same rule run._crawl_category applies to a re-crawled Amazon seller,
    so a row that is already enriched, pushed or deliberately skipped is not
    quietly reset to the start of the pipeline.

    Rows are written as each store finishes, so a killed run keeps everything
    it read. No captcha handling: Shopify does not block this. A 429 or 503
    from a store goes through the fetcher's ordinary wait-once-and-retry path,
    and a dead store is a 404, which reads as "closed".
    """
    existing = {r["seller_id"]: r.get("status") for r in
                db.table("harvest_sellers").select("seller_id, status").execute().data}
    fresh = [h for h in dict.fromkeys(handles) if recheck or seller_id(h) not in existing]
    todo = fresh[:limit]
    log(f"shopify: {len(handles)} store handles, {len(fresh)} not yet on file, reading {len(todo)}")
    counts: Counter = Counter()
    summary: dict = {"handles": len(handles), "read": 0, "products": 0, "statuses": {}}
    today = datetime.now(timezone.utc).date().isoformat()
    for i, handle in enumerate(todo):
        if i:
            fetcher.sleep(PAUSE_BETWEEN_STORES)
        got = read_store(fetcher, handle, resolver=resolver, meta=(metas or {}).get(handle))
        meta, status = got["meta"] or {"name": handle}, got["status"]
        vendors = got["vendors"] or {"vendors": [], "dominant": None, "category": None}
        est = got["est_annual"]
        head = (f"shopify store, {len(got['products'])} products, {len(vendors.get('vendors') or [])} vendors, "
                + (f"est ${est:,.0f}/yr from reviews" if est else "no revenue estimate")
                + f"; read {today}")
        status = keep_verdict(existing.get(seller_id(handle)), status)
        row = store_row(handle, meta, got["products"], got["sampled"], vendors, est,
                        got["contact"], status, f"{head}; {got['note']}")
        domain = store_domain(handle, got["meta"])
        product_rows = catalogue_rows(domain, seller_id(handle), got)
        if product_rows:
            db.table("harvest_products").upsert(product_rows, on_conflict="asin").execute()
            _keep_history(db, product_rows, log)
            summary["products"] += len(product_rows)
        db.table("harvest_sellers").upsert([row], on_conflict="seller_id").execute()
        counts[status] += 1
        summary["read"] += 1
        log(f"  {meta.get('name') or handle}: {status} "
            + (f"est ${est / 12:,.0f}/mo " if est else "") + got["note"])
    summary["statuses"] = dict(counts)
    note = (f"shopify: {summary['read']} store(s) read, {summary['products']} product(s), "
            + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing classified"))
    log(note)
    _log_event(db, note, summary)
    return summary
