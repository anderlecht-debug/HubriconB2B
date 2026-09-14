"""Domains in, live Shopify stores out — cheapest test first.

LEAD_SOURCING.md ranks the Meta Ad Library first and Common Crawl second.
Neither survived contact:

  * **Meta Ad Library.** Meta's own `ads_archive` documentation: "Ads that did
    not reach any location in the EU will only return if they are about social
    issues, elections or politics." `ad_type=ALL` — the value that returns
    ordinary product ads — is an EU dataset. `cold/settings.py` suppresses
    EU/UK/EEA/CH outright for want of a documented legitimate-interest basis,
    so the only geography the API covers is the only one we will not write to.
    There is no ad-spend signal available here at any price we are paying;
    `stack.py` stands in for it.
  * **Common Crawl.** Real and free to read, but the columnar index wants
    Athena (billed) or a local pull measured in hundreds of gigabytes, and
    what comes back carries no size signal at all — a domain and nothing else.
    Tranco does the same job in a few megabytes *and* ranks what it returns.

What replaced them, measured 2026-09-05:

    tranco top-1M      free download, ~1M domains, ranked
    dns pass           free, no request touches a store, ~1 ms each
    http fingerprint   one request, only for what DNS could not settle

Every Shopify store on its own domain either resolves into 23.227.38.0/24 or
CNAMEs to shops.myshopify.com. Verified: allbirds.com -> 23.227.38.32,
gymshark.com -> 23.227.38.65, www.allbirds.com -> CNAME shops.myshopify.com. So
the DNS pass is precise but not complete — a store behind Cloudflare or Vercel
shows its proxy instead (ridge.com -> 104.20.21.75, bombas.com -> 76.76.21.21,
both Shopify stores). Those need the HTTP pass, which is why the cheap test
runs first and the expensive one only mops up.

And the rank is not a by-product. It is the traffic proxy that a bulk crawl of
the open web cannot give, and it does most of the work in `score.py`.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from ..harvest import shopify as shopify_harvest
from ..harvest.shopify import handle_from_meta, parse_meta

CACHE_DIR = Path.home() / ".hubricon" / "sourcing"

# Shopify's published storefront range. Every custom domain pointed at Shopify
# by an A record lands here; the block has been stable for years and a miss
# costs nothing, because the HTTP pass catches what DNS does not.
SHOPIFY_A_PREFIX = "23.227.38."
SHOPIFY_CNAME = "shops.myshopify.com"

TRANCO_API = "https://tranco-list.eu/api/lists/date/{date}"
TRANCO_LIMIT = int(os.environ.get("SOURCING_TRANCO_LIMIT", "1000000"))
DNS_WORKERS = int(os.environ.get("SOURCING_DNS_WORKERS", "32"))

# Where in the ranking the stores actually are. Measured 2026-09-07 over the
# full Tranco top-1M, 600 domains sampled per band, DNS only:
#
#         1 - 10,000    0.00%     Google, Microsoft, the CDNs. Nothing.
#    10,000 - 50,000    0.50%     Toys R Us, Native Instruments — brands, not DTC
#    50,000 - 150,000   1.00%     Smartwool, Orthofeet
#   150,000 - 400,000   2.83%     Scotch & Soda, Storelli
#   400,000 - 1,000,000 4.50%     the long tail, and increasingly non-US
#
# So the head of the list is pure waste and the tail is mostly foreign. The
# default window is where a US brand doing $3M-$20M can rank. Widen it
# by moving RANK_TO out; the cursor below will walk into the new ground on its
# own. Extrapolated, the whole list holds roughly 35,000 Shopify stores.
RANK_FROM = int(os.environ.get("SOURCING_RANK_FROM", "20000"))
RANK_TO = int(os.environ.get("SOURCING_RANK_TO", "600000"))
CURSOR_KEY = "sourcing.tranco_cursor"

# Country-code TLDs are a store somewhere we do not sell to: the engine is
# US-only (classify_meta) and EU/UK are suppressed outright. Dropping them
# before the DNS pass rather than after meta.json saves the deepest band's
# largest cost — mimao.eu, invicta.com.pe and courtorder.co.za were all real
# Shopify stores in the 2026-09-07 sample, and all three are unwritable.
# The generic-use ones a US brand really does buy are kept.
GENERIC_TWO_LETTER = frozenset(("co", "io", "ai", "me", "tv", "cc", "us", "to", "so", "fm"))

# Ranked high and never a DTC store. Cheap to skip, and it keeps the HTTP pass
# off hosts that would rather we did not knock.
NEVER_A_STORE = re.compile(
    r"(^|\.)(google|youtube|facebook|instagram|twitter|tiktok|amazon|apple|microsoft|"
    r"cloudflare|akamai|wikipedia|linkedin|reddit|github|gitlab|wordpress|blogspot|"
    r"bing|yahoo|baidu|yandex|whatsapp|telegram|zoom|netflix|spotify|"
    r"paypal|stripe|shopify|adobe|oracle|ibm|intel|nvidia|samsung|office|live|msn)\.",
    re.I)
NEVER_A_STORE_TLDS = (".gov", ".edu", ".mil", ".int", ".arpa")


# -- Tranco ------------------------------------------------------------------------

def tranco_url(on: date | None = None, opener=None) -> tuple[str, str]:
    """-> (list_id, download url) for a day's list.

    Tranco publishes a daily list and the API hands back the id and a download
    link rather than a stable file name. Today's is often not built yet, so
    the caller walks back a day at a time.
    """
    day = (on or date.today()).isoformat()
    raw = (opener or _open)(TRANCO_API.format(date=day))
    doc = json.loads(raw)
    if not doc.get("available") or doc.get("failed"):
        raise LookupError(f"tranco list for {day} is not available")
    return doc["list_id"], doc["download"]


def _open(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Hubricon-sourcing/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def tranco_list(limit: int = TRANCO_LIMIT, on: date | None = None, opener=None,
                cache_dir: Path | None = None, log=print) -> list[tuple[int, str]]:
    """-> [(rank, domain)] for the top `limit`, cached on disk by list id.

    Falls back up to a week: the day's list is built some hours into the day
    and a run at the wrong hour should not fail, it should use yesterday's.
    """
    root = Path(cache_dir) if cache_dir else CACHE_DIR
    root.mkdir(parents=True, exist_ok=True)
    start = on or date.today()
    last: Exception | None = None
    for back in range(0, 8):
        day = start - timedelta(days=back)
        try:
            list_id, url = tranco_url(day, opener)
        except Exception as err:            # noqa: BLE001 - any failure means try the day before
            last = err
            continue
        cached = root / f"tranco-{list_id}.csv"
        if not cached.exists():
            log(f"  tranco {list_id} ({day}): downloading")
            blob = (opener or _open)(url)
            # The download is a zip holding one csv of "rank,domain".
            if blob[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(blob)) as z:
                    blob = z.read(z.namelist()[0])
            cached.write_bytes(blob)
        rows = []
        with cached.open(newline="") as fh:
            for row in csv.reader(fh):
                if len(row) < 2:
                    continue
                try:
                    rank = int(row[0])
                except ValueError:
                    continue
                rows.append((rank, row[1].strip().lower()))
                if len(rows) >= limit:
                    break
        log(f"  tranco {list_id} ({day}): {len(rows):,} domains")
        return rows
    raise LookupError(f"no tranco list available in the week to {start}: {last}")


def worth_probing(domain: str) -> bool:
    """A cheap pre-filter, so the DNS and HTTP passes are not spent on hosts
    that are obviously not a merchant."""
    d = (domain or "").strip().lower()
    if not d or "." not in d or len(d) > 100:
        return False
    # Shopify's own hosts resolve into Shopify's own block, so the DNS pass
    # says yes to them every time. myshopify.com is ranked in Tranco and was
    # discovered as a "store" on the first live pass.
    if d == "shopify.com" or d.endswith(".shopify.com") or shopify_harvest.is_shopify_host(d):
        return False
    if d.endswith(NEVER_A_STORE_TLDS):
        return False
    tld = d.rsplit(".", 1)[-1]
    if len(tld) == 2 and tld not in GENERIC_TWO_LETTER:
        return False
    # ".com.au", ".co.uk", ".com.pe" and the rest of that shape.
    parts = d.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("com", "co", "net", "org"):
        return False
    return not NEVER_A_STORE.search("." + d)


# -- the DNS pass ------------------------------------------------------------------

def _dig(name: str, kind: str, timeout: int = 5) -> list[str]:
    try:
        out = subprocess.run(["dig", "+short", kind, name], capture_output=True,
                             text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip().rstrip(".") for line in out.splitlines() if line.strip()]


def is_shopify_dns(domain: str, resolver=None) -> tuple[bool, str]:
    """-> (verdict, evidence). An A record in Shopify's block, or a CNAME at
    `www` pointing at shops.myshopify.com.

    `resolver(name, kind) -> list[str]` is injectable; nothing here reaches the
    network in tests.
    """
    dig = resolver or _dig
    for value in dig(domain, "A"):
        if value.startswith(SHOPIFY_A_PREFIX):
            return True, f"A {value}"
    # A brand that points the apex at a redirect service still CNAMEs www.
    for value in dig("www." + domain, "CNAME"):
        if value.lower().endswith(SHOPIFY_CNAME):
            return True, f"CNAME {value}"
    return False, ""


def dns_pass(domains: list[str], resolver=None, workers: int = DNS_WORKERS,
             log=print) -> dict[str, str]:
    """Every domain that DNS alone proves is Shopify -> its evidence.

    Concurrent because a DNS lookup is milliseconds of waiting and no load on
    anybody's store: this is the one stage that can run at full width.
    """
    found: dict[str, str] = {}

    def check(d: str) -> tuple[str, bool, str]:
        ok, why = is_shopify_dns(d, resolver)
        return d, ok, why

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for domain, ok, why in pool.map(check, domains):
            if ok:
                found[domain] = why
    log(f"  dns: {len(found)} of {len(domains)} domains resolve to Shopify")
    return found


# -- the HTTP pass -----------------------------------------------------------------

HTML_MARKERS = ("cdn.shopify.com", "shopify.theme", "/cdn/shop/", "shopify-section",
                "x-shopify-stage", "myshopify.com")


def fingerprint_http(fetcher, domain: str) -> tuple[str | None, dict | None]:
    """-> (handle, meta) when the domain is a live Shopify store.

    `/meta.json` is the whole test: it is the store naming itself, it carries
    the myshopify handle that is the row key everywhere downstream, and one
    request settles both questions. A store that answers it is Shopify and is
    open; a store behind a password page or a headless storefront answers with
    something that is not JSON, and falls through to the HTML markers, which
    prove the platform but not the handle.
    """
    meta = parse_meta(_as_text(fetcher.get(f"https://{domain}/meta.json")))
    handle = handle_from_meta(meta)
    if handle:
        return handle, meta
    page = fetcher.get(f"https://{domain}/")
    low = (page or "").lower()
    if any(m in low for m in HTML_MARKERS):
        # Shopify, but not classic-storefront JSON: a Hydrogen front end, or an
        # edge that answers the homepage and refuses the endpoints. Recorded
        # without a handle so `qualify` can decide whether to spend more on it.
        return None, {"platform_only": True, "domain": domain}
    return None, None


def _as_text(got) -> str | None:
    """DualFetcher.get returns text; a caller may hand this a parsed payload."""
    if got is None or isinstance(got, str):
        return got
    return json.dumps(got)


# -- the whole pass ----------------------------------------------------------------

def discover(fetcher, limit: int = 2000, resolver=None, opener=None, log=print,
             tranco_limit: int | None = None, cache_dir: Path | None = None,
             rank_from: int | None = None, rank_to: int | None = None,
             dns_budget: int = 40_000) -> tuple[list[dict], int]:
    """Tranco window -> pre-filter -> DNS -> HTTP. -> (rows, rank reached).

    A run walks a slice of the ranking rather than the whole list: the head
    holds no stores at all and a million lookups in one pass is a quarter of an
    hour for ground the next run would only cover again. The caller keeps the
    returned rank as a cursor and starts there next time.

    Only DNS-negative domains reach the HTTP stage, and only the top `limit`
    survivors are probed there, because that is the stage that costs a stranger
    a request.
    """
    start = RANK_FROM if rank_from is None else rank_from
    stop = RANK_TO if rank_to is None else rank_to
    ranked = tranco_list(limit=tranco_limit or TRANCO_LIMIT, opener=opener,
                         cache_dir=cache_dir, log=log)
    window = [(r, d) for r, d in ranked if start <= r < stop and worth_probing(d)]
    window.sort()
    window = window[:dns_budget]
    if not window:
        log(f"  no domains left between ranks {start:,} and {stop:,} — "
            f"raise SOURCING_RANK_TO to walk further down the list")
        return [], start
    reached = window[-1][0] + 1
    ranks = {d: r for r, d in window}
    log(f"  ranks {window[0][0]:,}-{window[-1][0]:,}: {len(window):,} domains worth probing")
    hits = dns_pass([d for _, d in window], resolver=resolver, log=log)

    # Every DNS hit becomes a row, not just the ones this pass has budget to
    # probe. The lookups are already paid for and the cursor is about to move
    # past this slice of the ranking: keeping only `limit` of them threw away
    # 1,225 stores out of 1,250 on the first live run, and nothing would ever
    # have gone back for them. The unprobed ones carry no handle, and `qualify`
    # fills that in when it reaches them.
    out: list[dict] = []
    ordered = sorted(hits, key=lambda d: ranks[d])
    for i, domain in enumerate(ordered):
        row = {"domain": domain, "tranco_rank": ranks[domain], "is_shopify": True,
               "detected_via": "dns", "note": hits[domain], "status": "discovered",
               "myshopify_handle": None, "meta": None}
        if i < limit:
            handle, meta = fingerprint_http(fetcher, domain)
            row["myshopify_handle"], row["meta"] = handle, meta
            if handle is None and not (meta or {}).get("platform_only"):
                # DNS says Shopify and the store will not talk to us: closed, a
                # password page, or an edge that refuses everything.
                row["status"] = "no_contact"
                row["note"] = f"{hits[domain]}; store did not answer /meta.json"
        out.append(row)
    log(f"discover: {len(out)} Shopify store(s) from {len(ranks):,} domains "
        f"(ranks {window[0][0]:,}-{window[-1][0]:,}); {min(limit, len(out))} probed over HTTP, "
        f"the rest wait for qualify")
    return out, reached


def discover_search(search_fetcher, store_fetcher, terms: list[str] | None = None,
                    log=print) -> list[dict]:
    """The existing Bing/shop.app route, in this package's row shape.

    Kept because it reaches stores Tranco's top ranks do not: a $2M brand with
    a loyal list and no search footprint can sit well below a million.
    """
    from ..harvest import shopify as shopify_harvest

    handles, metas = shopify_harvest.discover(search_fetcher, store_fetcher, terms=terms, log=log)
    out = []
    for handle in handles:
        meta = metas.get(handle) or {}
        out.append({"domain": shopify_harvest.store_domain(handle, meta), "tranco_rank": None,
                    "is_shopify": True, "detected_via": "search", "note": "shop.app search",
                    "status": "discovered", "myshopify_handle": handle, "meta": meta})
    return out
