"""The harvest pipeline: crawl → enrich → push, plus status and the launchd install.

crawl   Best Sellers pages → product pages → seller profiles → harvest_sellers rows
enrich  candidate rows → website → published contact → 'enriched' (or why not)
push    enriched rows → the Instantly list "Hubricon harvest (auto)"; the hourly
        operator enrolls that list into the campaign like any other Hubricon list
requalify  re-read the live profile of rows already past the gate and apply
        today's size band (seller feedback counts); giants become skip_size
prune   skip_* rows that already sit in Instantly are deleted there (operator)
wayback  see wayback.py: archived seller profiles as a second, Amazon-free source
shopify  see shopify.py: US Shopify stores from their own public JSON, into the
        same rows (platform 'shopify') and the same founder lane. Nothing
        blocks it, so it runs whatever Amazon is doing to the crawl today.

Crawl and enrich need a home connection (Amazon captchas datacenter ranges),
so `hubricon harvest install` schedules them on the founder's Mac with
launchd. Push only needs the Instantly key, so the operator does it too.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from ..instantly import Instantly, InstantlyError
from ..onboarding import is_internal
from . import amazon
from . import enrich as enrichmod
from .fetch import Blocked, Cache, Fetcher

LIST_NAME = "Hubricon harvest (auto)"  # contains "hubricon" → the operator enrolls it
# A night's budget: ~400 product pages at a human's pace is about 40 minutes,
# and roughly one in twenty pages yields a pushable founder-run brand, so this
# keeps two mailboxes' 40 sends a day fed. Depth 2 reads the grandchildren
# of a category (e.g. Kitchen → Bakeware → Muffin Pans), which is where the
# $3M–$20M private-label brands rank; page 1 of a top category is the giants.
MAX_PRODUCTS = int(os.environ.get("HARVEST_MAX_PRODUCTS", "250"))  # per run; launchd runs twice a day
CATEGORIES_PER_RUN = int(os.environ.get("HARVEST_CATEGORIES_PER_RUN", "4"))
SUBCATS_PER_CATEGORY = int(os.environ.get("HARVEST_SUBCATS", "6"))
# Depth is the single biggest lever on lead quality. Measured over 1,834
# harvested sellers on 2026-09-04, the share still in play after screening
# rose monotonically with how deep the brand's best rank sits:
#   top 500        15%      2,001-10,000     30%
#   501-2,000      21%      deeper than 10k  56%
# A top-100 Best Sellers slot is a brand far past the $20M ceiling almost by
# definition — every one researched by hand that day (Rhino USA, Catchmaster,
# Dr. Bronner's, Eddie Bauer, American Soft Linen) failed on size. Narrow leaf
# categories are where a $3M-$20M founder-run brand actually ranks, so the
# crawl walks four levels down and reads the deepest lists first.
CRAWL_DEPTH = int(os.environ.get("HARVEST_DEPTH", "4"))
MIN_MONTHLY_REVENUE = float(os.environ.get("HARVEST_MIN_MONTHLY_REVENUE", "2500"))
# One listing alone doing $300k/mo (est.) marks a brand well past the $20M
# ceiling; the first pass showed $600k let Unilever-scale brands through.
MAX_ASIN_MONTHLY_REVENUE = float(os.environ.get("HARVEST_MAX_ASIN_MONTHLY_REVENUE", "300000"))
MEGA_REVIEWS = 150_000
ENRICH_LIMIT = int(os.environ.get("HARVEST_ENRICH_LIMIT", "60"))
PUSH_LIMIT = int(os.environ.get("HARVEST_PUSH_LIMIT", "200"))  # Instantly takes 100 a call; the operator runs hourly
REQUALIFY_LIMIT = int(os.environ.get("HARVEST_REQUALIFY_LIMIT", "60"))
SKIP_STATUSES = ("skip_reseller", "skip_non_us", "skip_amazon", "skip_size", "skip_internal")
PRODUCT_CACHE_DAYS, SELLER_CACHE_DAYS = 30, 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pick_categories(n: int = CATEGORIES_PER_RUN, today: date | None = None, slot: int | None = None) -> list[str]:
    """Rotate through the category list by half-day, so the 06:10 and 18:10
    runs read different slices and a week covers everything twice."""
    cats = amazon.CATEGORIES
    now = datetime.now()
    today = today or now.date()
    if slot is None:
        slot = 1 if now.hour >= 12 else 0
    start = ((today.timetuple().tm_yday * 2 + slot) * n) % len(cats)
    return [cats[(start + i) % len(cats)] for i in range(min(n, len(cats)))]


def _log_event(db, note: str, payload: dict) -> None:
    try:
        db.table("funnel_events").insert({"kind": "harvest", "note": note, "payload": payload}).execute()
    except Exception as err:  # the log must never stop the run
        print(f"  (could not log harvest event: {err})", file=sys.stderr)


# -- crawl ----------------------------------------------------------------------

def category_asins(fetcher: Fetcher, slug: str, subcats: int = SUBCATS_PER_CATEGORY,
                   depth: int = CRAWL_DEPTH, enough: int | None = None) -> list[str]:
    """The ASINs of `category_items`, without their titles."""
    return [i["asin"] for i in category_items(fetcher, slug, subcats, depth, enough)]


def category_items(fetcher: Fetcher, slug: str, subcats: int = SUBCATS_PER_CATEGORY,
                   depth: int = CRAWL_DEPTH, enough: int | None = None) -> list[dict]:
    """ASINs to read, mid-size brands first: the deepest child lists, then the
    shallower ones, then the category's page 2, then its page 1 (where the
    conglomerates sit). `depth` 1 reads the children, 2 the grandchildren.
    `enough` stops reading further lists once that many ASINs are in hand,
    so a small page budget does not pay for forty list pages."""
    root = fetcher.get(amazon.category_url(slug))
    if not root:
        return []
    top = amazon.bestseller_page(root)
    seen = {amazon.category_url(slug)}
    frontier = top["subcategories"][:subcats]
    levels: list[list[dict]] = []
    collected = 0
    for _ in range(max(0, depth)):
        this_level: list[dict] = []
        next_frontier: list[str] = []
        for url in frontier:
            if url in seen or (enough is not None and collected >= enough):
                continue
            seen.add(url)
            page = fetcher.get(url)
            if not page:
                continue
            parsed = amazon.bestseller_page(page)
            this_level += parsed["items"]
            collected += len(parsed["items"])
            next_frontier += [c for c in parsed["subcategories"] if c not in seen][:subcats]
        levels.append(this_level)
        frontier = next_frontier
        if not frontier:
            break
    items: list[dict] = []
    for level in reversed(levels):
        items += level
    if top["next"]:
        page2 = fetcher.get(top["next"])
        if page2:
            items += amazon.bestseller_page(page2)["items"]
    items += top["items"]
    out: dict[str, dict] = {}
    for i in items:
        out.setdefault(i["asin"], i)
    return list(out.values())


def known_brand_tokens(db) -> set[str]:
    """Every brand already judged, normalised. A Best Sellers list repeats the
    same brands across its child lists, and a product page costs the same
    whether it teaches us something or not."""
    tokens: set[str] = set()
    start, page = 0, 1000
    while True:
        rows = db.table("harvest_sellers").select("brand, brands").range(start, start + page - 1).execute().data
        for r in rows:
            names = list(r.get("brands") or [])
            if r.get("brand"):
                names.append(r["brand"])
            tokens.update(t for t in (amazon.norm_name(n) for n in names if n) if len(t) >= 4)
        if len(rows) < page:
            return tokens
        start += page


def already_judged(title: str | None, known: set[str]) -> bool:
    """True when the listing's opening words name a brand we have already
    decided about, or a conglomerate we would skip on sight."""
    if not title:
        return False
    tokens = amazon.leading_brand(title)
    if any(t in known for t in tokens):
        return True
    words = " ".join(re.findall(r"[A-Za-z0-9&']+", title)[:3])
    return amazon.looks_big_parent(words, None)


def classify(agg: dict, prof: dict | None) -> tuple[str, str]:
    """→ (status, note) for a seller seen this crawl."""
    prof = prof or {}
    seller_name = agg.get("seller_name") or prof.get("seller_name")
    business = prof.get("business_name")
    brands = agg["brands"]
    top = max(agg["asins"], key=lambda a: a.get("est_monthly_revenue") or 0, default={})
    if prof and prof.get("country") and prof["country"] != "US":
        return "skip_non_us", f"business address in {prof['country']}"
    if amazon.looks_offshore(business, prof.get("address")):
        return "skip_non_us", "offshore trading-company name"
    if amazon.looks_nonprofit(seller_name, business):
        return "skip_reseller", "charity or thrift resale operation, not a private-label brand"
    if amazon.looks_big_parent(seller_name, business):
        return "skip_size", "corporate parent or aggregator as seller of record"
    if amazon.looks_reseller(seller_name, business, len(brands)):
        return "skip_reseller", f"{len(brands)} brands or reseller wording"
    # The seller's own feedback count sizes the whole account; one listing
    # under the ceiling said nothing about the other two hundred.
    size, why = amazon.seller_size(prof.get("ratings_12mo"), prof.get("ratings_lifetime"))
    if size:
        return "skip_size", why
    if (top.get("est_monthly_revenue") or 0) > MAX_ASIN_MONTHLY_REVENUE or (agg["reviews_max"] or 0) > MEGA_REVIEWS:
        return "skip_size", "one listing alone is bigger than the $20M brand ceiling"
    if not amazon.looks_private_label(agg["brand"], seller_name, business):
        if len(brands) > 1:
            return "skip_reseller", "sells more than one brand, none matching its name"
        return "candidate", "brand name differs from seller name; single brand seen"
    return "candidate", "brand matches seller"


def seller_row(sid: str, agg: dict, prof: dict, status: str, note: str, source: str = "bestsellers",
               est_monthly_revenue: float | None = None) -> dict:
    """The harvest_sellers row for one seller: listing aggregate + public profile.
    `est_monthly_revenue` overrides the listing sum when the estimate comes from
    elsewhere (the seller's feedback count, for profile-only rows)."""
    est_units = sum((a.get("est_monthly_revenue") or 0) / (a.get("price") or 1) for a in agg["asins"] if a.get("price"))
    revenue = est_monthly_revenue if est_monthly_revenue is not None else \
        round(sum(a.get("est_monthly_revenue") or 0 for a in agg["asins"]), 2)
    return {
        "seller_id": sid, "seller_name": agg.get("seller_name") or prof.get("seller_name"), "brand": agg["brand"],
        "brands": agg["brands"], "business_name": prof.get("business_name"), "address": prof.get("address"),
        "city": prof.get("city"), "state": prof.get("state"), "country": prof.get("country"),
        "asins": agg["asins"], "top_bsr": agg.get("top_bsr"), "top_category": agg.get("top_category"),
        "reviews_max": agg.get("reviews_max"), "est_monthly_units": round(est_units, 1),
        "est_monthly_revenue": revenue, "ratings_12mo": prof.get("ratings_12mo"),
        "ratings_lifetime": prof.get("ratings_lifetime"), "source": source,
        "status": status, "notes": note, "updated_at": _now(),
    }


def _product_row(asin: str, prod: dict) -> dict:
    return {
        "asin": asin, "seller_id": prod["seller_id"], "brand": prod["brand"], "title": prod["title"],
        "category": prod["category"], "bsr": prod["bsr"], "price": prod["price"],
        "reviews": prod["reviews"], "weight_oz": prod["weight_oz"], "dims": prod["dims"],
        "fulfilled_by_amazon": prod["fba"], "est_monthly_units": prod["est_monthly_units"],
        "est_monthly_revenue": prod["est_monthly_revenue"], "seen_at": _now(),
    }


def _crawl_category(db, fetcher: Fetcher, slug: str, budget: int, subcats: int, depth: int,
                    cache: Cache, log=print) -> dict:
    """One category: its lists → product pages (up to `budget` fetches) → the
    profiles of the third-party FBA sellers seen → rows. Writes to the
    database at the end of the category, so a killed run keeps every
    category it finished."""
    part: dict = {"products_fetched": 0, "products_cached": 0, "sellers_seen": 0, "sellers_new": 0,
                  "skipped_known": 0, "statuses": {}, "blocked": False}
    sellers: dict[str, dict] = {}
    product_rows: list[dict] = []
    try:
        known = known_brand_tokens(db)
        for item in category_items(fetcher, slug, subcats, depth, enough=budget * 3):
            if part["products_fetched"] >= budget:
                break
            asin = item["asin"]
            if already_judged(item.get("title"), known):
                part["skipped_known"] += 1
                continue
            prod = cache.get("product", asin, PRODUCT_CACHE_DAYS)
            if prod is None:
                part["products_fetched"] += 1
                page = fetcher.get(f"{amazon.BASE}/dp/{asin}")
                if not page:
                    continue
                prod = amazon.product(page, asin)
                prod.pop("related", None)
                prod["slug"] = slug
                cache.put("product", asin, prod)
            else:
                part["products_cached"] += 1
            product_rows.append(_product_row(asin, prod))
            if prod["sold_by_amazon"] or not prod["seller_id"] or not prod["fba"] or not prod["brand"]:
                continue
            agg = sellers.setdefault(prod["seller_id"], {
                "seller_id": prod["seller_id"], "seller_name": prod["seller_name"], "brand": prod["brand"],
                "brands": [], "asins": [], "reviews_max": 0, "top_bsr": None, "top_category": None, "slug": slug,
            })
            if prod["brand"] not in agg["brands"]:
                agg["brands"].append(prod["brand"])
            agg["asins"].append({"asin": asin, "brand": prod["brand"], "bsr": prod["bsr"], "price": prod["price"],
                                 "reviews": prod["reviews"], "est_monthly_revenue": prod["est_monthly_revenue"]})
            agg["reviews_max"] = max(agg["reviews_max"], prod["reviews"] or 0)
            if prod["bsr"] and (agg["top_bsr"] is None or prod["bsr"] < agg["top_bsr"]):
                agg["top_bsr"], agg["top_category"] = prod["bsr"], prod["category"]
    except Blocked as err:
        log(f"  {err}")
        part["blocked"] = True
    if product_rows:
        db.table("harvest_products").upsert(product_rows, on_conflict="asin").execute()
        # harvest_products is overwritten in place; this keeps the reading too,
        # which is what gives the cold engine a price history (cold/run.py).
        _keep_history(db, product_rows, log)

    existing = {r["seller_id"]: r for r in
                db.table("harvest_sellers").select("seller_id, status, brands, asins").execute().data}
    rows: list[dict] = []
    for sid, agg in sellers.items():
        prof = cache.get("seller", sid, SELLER_CACHE_DAYS)
        if prof is None and not part["blocked"]:
            try:
                page = fetcher.get(amazon.seller_url(sid))
            except Blocked as err:
                log(f"  {err}")
                part["blocked"] = True
                page = None
            if page:
                prof = amazon.seller(page)
                cache.put("seller", sid, prof)
        prof = prof or {}
        old = existing.get(sid)
        if old:
            for b in old.get("brands") or []:
                if b not in agg["brands"]:
                    agg["brands"].append(b)
            seen = {a["asin"] for a in agg["asins"]}
            agg["asins"] += [a for a in (old.get("asins") or []) if a.get("asin") not in seen]
        status, note = classify(agg, prof)
        if old and old["status"] not in ("candidate",) and status == "candidate":
            status = old["status"]  # already enriched/pushed/skipped: keep the verdict
        rows.append(seller_row(sid, agg, prof, status, note))
        part["statuses"][status] = part["statuses"].get(status, 0) + 1
        if not old:
            part["sellers_new"] += 1
    part["sellers_seen"] = len(sellers)
    if rows:
        db.table("harvest_sellers").upsert(rows, on_conflict="seller_id").execute()
    log(f"  {slug}: {part['products_fetched']} pages, {part['skipped_known']} listings skipped as already judged, "
        f"{len(sellers)} sellers ({part['sellers_new']} new), "
        + ", ".join(f"{k} {v}" for k, v in sorted(part["statuses"].items())))
    return part


def crawl(db, fetcher: Fetcher, categories: list[str] | None = None, max_products: int = MAX_PRODUCTS,
          subcats: int = SUBCATS_PER_CATEGORY, cache: Cache | None = None, log=print,
          depth: int = CRAWL_DEPTH) -> dict:
    cache = cache or Cache()
    categories = categories or pick_categories()
    summary: dict = {"categories": categories, "products_fetched": 0, "products_cached": 0,
                     "sellers_seen": 0, "sellers_new": 0, "skipped_known": 0, "statuses": {}, "blocked": False}
    # Every category gets an equal share of the page budget; what one does not
    # use rolls over to the next, so one deep category cannot eat the night.
    per_category = max(10, max_products // max(1, len(categories)))
    carry = 0
    for slug in categories:
        remaining = max_products - summary["products_fetched"]
        if remaining <= 0 or summary["blocked"]:
            break
        budget = min(remaining, per_category + carry)
        log(f"Best Sellers: {slug} (budget {budget} pages)")
        part = _crawl_category(db, fetcher, slug, budget, subcats, depth, cache, log)
        carry = budget - part["products_fetched"]
        for k in ("products_fetched", "products_cached", "sellers_seen", "sellers_new", "skipped_known"):
            summary[k] += part.get(k, 0)
        for k, v in part["statuses"].items():
            summary["statuses"][k] = summary["statuses"].get(k, 0) + v
        summary["blocked"] = summary["blocked"] or part["blocked"]
    summary["fetch"] = dict(fetcher.stats)
    note = (f"crawl {', '.join(categories)}: {summary['products_fetched']} product pages, "
            f"{summary['sellers_seen']} sellers ({summary['sellers_new']} new), "
            + ", ".join(f"{k} {v}" for k, v in sorted(summary["statuses"].items())))
    log(note)
    _log_event(db, note, summary)
    return summary


# -- enrich ---------------------------------------------------------------------

def _rows(db, status: str, limit: int | None = None, min_revenue: float | None = None,
          us_only: bool = True) -> list[dict]:
    """Rows in a status, best first. US only by default: a seller whose profile
    could not be read (captcha day) has no country yet and waits for the
    next crawl of its category rather than being emailed blind."""
    q = db.table("harvest_sellers").select("*").eq("status", status)
    if us_only:
        q = q.eq("country", "US")
    if min_revenue is not None:
        q = q.gte("est_monthly_revenue", min_revenue)
    q = q.order("est_monthly_revenue", desc=True)
    if limit:
        q = q.limit(limit)
    return q.execute().data


def _update(db, seller_id: str, **fields) -> None:
    db.table("harvest_sellers").update({**fields, "updated_at": _now()}).eq("seller_id", seller_id).execute()


def enrich(db, fetcher: Fetcher, limit: int = ENRICH_LIMIT, resolver=None, log=print) -> dict:
    counts: Counter = Counter()
    for row in _rows(db, "candidate", limit):
        upd = enrichmod.enrich_seller(fetcher, row, resolver)
        if upd.get("email") and is_internal(upd["email"]):
            upd = {"status": "skip_internal", "notes": "internal address"}
        _update(db, row["seller_id"], **upd)
        counts[upd["status"]] += 1
        log(f"  {row['brand']}: {upd['status']} {upd.get('email') or ''} {upd.get('notes') or ''}")
    note = "enrich: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing to enrich")
    log(note)
    _log_event(db, note, dict(counts))
    return dict(counts)


# -- push -----------------------------------------------------------------------

def ensure_list(api: Instantly, name: str = LIST_NAME) -> str:
    for lst in api.lead_lists():
        if lst.get("name") == name:
            return lst["id"]
    return api.create_lead_list(name)["id"]


def lead_payload(row: dict) -> dict:
    first = row.get("first_name") or f"{row['brand']} team"
    return {
        "email": row["email"],
        "first_name": first,
        "last_name": row.get("last_name") or "",
        "company_name": row["brand"],
        "website": row.get("website") or "",
        "custom_variables": {
            "source": "harvest", "seller_id": row["seller_id"], "business_name": row.get("business_name") or "",
            # Which storefront the lead sells on: a Shopify brand must never be
            # sent copy about Amazon fees (channels.py holds the same rule for
            # clients), and the sequence can branch on it.
            "platform": row.get("platform") or "amazon",
            "est_monthly_revenue": row.get("est_monthly_revenue") or 0,
            "email_confidence": row.get("email_confidence") or "", "person_found": bool(row.get("first_name")),
        },
    }


def push(db, api: Instantly | None, limit: int = PUSH_LIMIT, dry: bool = False,
         min_revenue: float = MIN_MONTHLY_REVENUE, log=print) -> int:
    rows = [r for r in _rows(db, "enriched", limit, min_revenue) if r.get("email") and not is_internal(r["email"])]
    if not rows:
        log("push: nothing enriched and above the revenue floor")
        return 0
    if dry or api is None:
        log(f"push: {'[dry] would push' if dry else 'INSTANTLY_API_KEY not set; the hourly operator pushes'} "
            f"{len(rows)} lead(s)")
        return 0 if api is None and not dry else len(rows)
    list_id = ensure_list(api)
    pushed, dropped = 0, 0
    replies: list[dict] = []
    for i in range(0, len(rows), 100):
        batch = rows[i:i + 100]
        try:
            res = api.add_leads(list_id=list_id, leads=[lead_payload(r) for r in batch]) or {}
        except InstantlyError as err:
            log(f"push: {err}")
            break
        replies.append(res)
        # Instantly answers with counts, not names: uploaded / invalid / skipped
        # (already in the workspace) / duplicated / blocklisted. When nothing
        # was uploaded the whole batch was rejected and must not be retried
        # every hour; otherwise the rows are considered pushed and the counts
        # ride along in the notes for the digest.
        summary = ", ".join(f"{k} {res.get(k)}" for k in ("leads_uploaded", "invalid_email_count", "skipped_count",
                                                          "duplicated_leads", "in_blocklist") if res.get(k) is not None)
        if res.get("total_sent") and not res.get("leads_uploaded"):
            for r in batch:
                _update(db, r["seller_id"], status="no_email", notes=f"Instantly rejected the import: {summary}")
            dropped += len(batch)
            continue
        ids = {c.get("index"): c.get("id") for c in (res.get("created_leads") or []) if isinstance(c, dict)}
        for i, r in enumerate(batch):
            _update(db, r["seller_id"], status="pushed", pushed_at=_now(), instantly_lead_id=ids.get(i),
                    notes=((r.get("notes") or "") + f"; Instantly: {summary}").strip("; "))
        pushed += len(batch)
    note = f"push: {pushed} lead(s) → Instantly list '{LIST_NAME}'" + (f", {dropped} rejected on import" if dropped else "")
    if replies:
        note += " (" + "; ".join(", ".join(f"{k} {v}" for k, v in r.items() if k != "blocklist_used") for r in replies) + ")"
    log(note)
    _log_event(db, note, {"pushed": pushed, "dropped": dropped, "instantly": replies})
    return pushed


# -- listings: a live listing for a seller known only from its profile ---------------

LISTINGS_LIMIT = int(os.environ.get("HARVEST_LISTINGS_LIMIT", "60"))
LISTINGS_PER_SELLER = int(os.environ.get("HARVEST_LISTINGS_PER_SELLER", "2"))
LISTINGS_MAX_ASINS = int(os.environ.get("HARVEST_LISTINGS_MAX_ASINS", "4"))  # keep reading until one carries a weight
RUN_ALL_LISTINGS = int(os.environ.get("HARVEST_RUN_ALL_LISTINGS", "30"))  # per scheduled run, ~90 Amazon pages
# Shopify stores per scheduled run: ~5 requests each at ~1 s, so about five
# minutes on top of the Amazon hour, and none of it can draw a captcha.
RUN_ALL_SHOPIFY = int(os.environ.get("HARVEST_RUN_ALL_SHOPIFY", "60"))
MIN_HOOK_WEIGHT_OZ = 2.0  # the lightest FBA band has no cheaper band below it, so no fee-cliff hook


def _has_weighed_listing(asins: list[dict], weights: dict[str, float | None]) -> bool:
    return any((weights.get(a.get("asin")) or 0) > MIN_HOOK_WEIGHT_OZ for a in asins or [])


def storefront_url(seller_id: str) -> str:
    return f"{amazon.BASE}/s?me={seller_id}&marketplaceID=ATVPDKIKX0DER"


def _keep_history(db, product_rows: list[dict], log=print) -> None:
    """Append today's reading of each listing beside the overwritten row.

    Imported here rather than at module scope: harvest.shopify imports this
    module, and cold.findings imports harvest.shopify, so a top-level import of
    cold.run would close the cycle.
    """
    from ..cold.run import record_observations

    record_observations(db, product_rows, log=log)


def listings(db, fetcher: Fetcher, limit: int = LISTINGS_LIMIT, per_seller: int = LISTINGS_PER_SELLER,
             cache: Cache | None = None, log=print) -> dict:
    """An archived profile names the seller but no product, so the founder lane
    has nothing to quote. The seller's storefront (Amazon search by seller)
    lists its ASINs; the first `per_seller` product pages give rank, price,
    weight and the revenue estimate, and land in harvest_products like any
    crawled listing. Three Amazon pages per seller, at the fetcher's pace.

    Amazon rows only: a Shopify store has no Amazon storefront, and asking for
    one would spend an Amazon request per store to learn nothing. Its listings
    (and their shipping weights) come from its own /products.json.
    """
    cache = cache or Cache()
    counts: Counter = Counter()
    candidates = db.table("harvest_sellers").select("*").in_("status", ["candidate", "enriched", "pushed"]) \
        .eq("country", "US").neq("platform", "shopify").order("est_monthly_revenue", desc=True).execute().data
    # The founder lane's hook is the fee cliff, which needs a packed weight
    # above the lightest band: a row whose listings carry none is read again.
    weights = {p["asin"]: p.get("weight_oz") for p in
               db.table("harvest_products").select("asin, weight_oz").execute().data}
    rows = [r for r in candidates
            if not r.get("asins") or (not _has_weighed_listing(r["asins"], weights)
                                      and "storefront read" not in (r.get("notes") or ""))][:limit]
    if not rows:
        log("listings: every US row already carries a weighed listing")
        return {}
    for row in rows:
        try:
            page = fetcher.get(storefront_url(row["seller_id"]))
        except Blocked as err:
            log(f"  {err}")
            break
        if not page:
            counts["no_storefront"] += 1
            continue
        asins = list(dict.fromkeys(re.findall(r"/dp/([A-Z0-9]{10})", page)))[:LISTINGS_MAX_ASINS]
        agg_asins, brands, reviews_max, top = [], [], 0, (None, None)
        product_rows = []
        weighed = False
        for asin in asins:
            if len(agg_asins) >= per_seller and weighed:
                break
            prod = cache.get("product", asin, PRODUCT_CACHE_DAYS)
            if prod is None:
                try:
                    ppage = fetcher.get(f"{amazon.BASE}/dp/{asin}")
                except Blocked as err:
                    log(f"  {err}")
                    ppage = None
                if not ppage:
                    continue
                prod = amazon.product(ppage, asin)
                prod.pop("related", None)
                cache.put("product", asin, prod)
            if prod.get("sold_by_amazon") or (prod.get("seller_id") or row["seller_id"]) != row["seller_id"]:
                continue  # the buy box went to Amazon or another seller; not this seller's listing to quote
            product_rows.append(_product_row(asin, {**prod, "seller_id": row["seller_id"]}))
            weighed = weighed or (prod.get("weight_oz") or 0) > MIN_HOOK_WEIGHT_OZ
            agg_asins.append({"asin": asin, "brand": prod.get("brand"), "bsr": prod.get("bsr"), "price": prod.get("price"),
                              "reviews": prod.get("reviews"), "est_monthly_revenue": prod.get("est_monthly_revenue")})
            if prod.get("brand") and prod["brand"] not in brands:
                brands.append(prod["brand"])
            reviews_max = max(reviews_max, prod.get("reviews") or 0)
            if prod.get("bsr") and (top[0] is None or prod["bsr"] < top[0]):
                top = (prod["bsr"], prod.get("category"))
        if not agg_asins:
            counts["no_listing"] += 1
            _update(db, row["seller_id"], notes=((row.get("notes") or "") + "; storefront read, no listing parsed").strip("; "))
            continue
        counts["weighed" if weighed else "unweighed"] += 1
        db.table("harvest_products").upsert(product_rows, on_conflict="asin").execute()
        _keep_history(db, product_rows, log)
        upd = {"asins": agg_asins, "brands": brands or row.get("brands") or [], "reviews_max": reviews_max,
               "top_bsr": top[0], "top_category": top[1],
               "notes": ((row.get("notes") or "") + f"; storefront read, {len(agg_asins)} live listing(s)"
                         + ("" if weighed else ", none with a packed weight")).strip("; ")}
        if len(brands) == 1 and brands[0] and not amazon.looks_private_label(brands[0], row.get("seller_name"), row.get("business_name")):
            upd["notes"] += f"; sells brand {brands[0]!r}"
        if len(brands) == 1 and brands[0]:
            upd["brand"] = brands[0]  # the product's brand is what the founder's email should name
        _update(db, row["seller_id"], **upd)
        counts["paired"] += 1
        log(f"  {row['brand']}: {len(agg_asins)} listing(s), top rank {top[0]} in {top[1]}")
    note = "listings: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing read")
    log(note)
    _log_event(db, note, dict(counts))
    return dict(counts)


# -- profiles: seller ids from the archive index, read live --------------------------

PROFILES_LIMIT = int(os.environ.get("HARVEST_PROFILES_LIMIT", "150"))


def profiles(db, fetcher: Fetcher, ids: list[str] | None = None, limit: int = PROFILES_LIMIT,
             ids_file: Path | None = None, cache: Cache | None = None, log=print) -> dict:
    """Sellers the archive knows only by id: read the live profile page, one
    Amazon request each. That is the cheapest seller on the site — a Best
    Sellers crawl spends about fifteen product pages to reach one seller — and
    the rows are judged by the profile-only rules, since no listing is known
    yet (`listings` supplies one afterwards).

    MEASURED AND REJECTED, 2026-09-04. Cheap per seller turned out to be
    expensive per lead: ten of these read live gave one candidate, and that one
    was a reseller; five of the ten had no seller feedback at all in twelve
    months, meaning a dormant or dead account. That is ~120 Amazon pages per
    lead against ~20 through Best Sellers, which finds sellers who are actually
    ranking. The archive indexes whoever got captured, not whoever is trading.
    The step is kept because the enumeration is already paid for and the
    population may differ elsewhere, but do not spend the day's Amazon budget
    here without re-measuring first."""
    from .wayback import classify_profile, seller_ids

    cache = cache or Cache()
    ids = ids if ids is not None else seller_ids(fetcher, ids_file, log=log)
    existing = {r["seller_id"] for r in db.table("harvest_sellers").select("seller_id").execute().data}
    todo = [i for i in ids if i not in existing][:limit]
    if not todo:
        log("profiles: every known seller id is already on file")
        return {}
    log(f"profiles: {len(ids)} seller ids known, reading {len(todo)} not yet on file")
    counts: Counter = Counter()
    pending: list[dict] = []
    for sid in todo:
        try:
            page = fetcher.get(amazon.seller_url(sid))
        except Blocked as err:
            log(f"  {err}")
            break
        if not page:
            counts["unread"] += 1
            continue
        prof = amazon.seller(page)
        if not prof.get("business_name") and not prof.get("seller_name"):
            counts["unread"] += 1
            continue
        cache.put("seller", sid, prof)
        status, note, agg = classify_profile(sid, prof)
        pending.append(seller_row(sid, agg, prof, status, f"profile read live; {note}", source="profile",
                                  est_monthly_revenue=amazon.revenue_from_ratings(prof.get("ratings_12mo"))))
        counts[status] += 1
        log(f"  {(prof.get('seller_name') or sid)[:28]:<28} {status:<14} "
            f"{prof.get('ratings_12mo')} ratings/12mo, {prof.get('country')}")
        if len(pending) >= 25:
            db.table("harvest_sellers").upsert(pending, on_conflict="seller_id").execute()
            pending.clear()
    if pending:
        db.table("harvest_sellers").upsert(pending, on_conflict="seller_id").execute()
    note = "profiles: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing read")
    log(note)
    _log_event(db, note, dict(counts))
    return dict(counts)


# -- owners: the named person behind a harvested brand ------------------------------

OWNERS_LIST_NAME = "Hubricon harvest owners (auto)"  # contains "hubricon" → the operator enrolls it
OWNER_LOOKUPS_DAILY = int(os.environ.get("HARVEST_OWNER_LOOKUPS_DAILY", "50"))
OWNER_BATCH = 50
OWNER_TITLES = ["Founder", "Co-Founder", "CEO", "Owner", "President", "Managing Director"]


def owner_filters(domains: list[str]) -> dict:
    """SuperSearch filters: the founder/owner at exactly these company domains."""
    return {
        "domains": domains,
        "title": {"include": OWNER_TITLES, "includeMode": "CONTAINS"},
        "locations": {"include": [{"country": "United States"}]},
        "location_mode": "company",
        "skip_owned_leads": True,
        "show_one_lead_per_company": True,
    }


def owners(db, api: Instantly | None, dry: bool = False, daily: int = OWNER_LOOKUPS_DAILY, log=print,
           today: str | None = None) -> int:
    """Public pages give a brand's role inbox (hello@, info@), which the campaign
    gate treats as a support queue. The brand itself is the qualified part —
    US, private label, the right size — so the operator asks Instantly's
    SuperSearch for the named founder/owner at that brand's own domain, with a
    verified work email, into the list '{OWNERS_LIST_NAME}'. One request per
    batch of domains, capped at `daily` leads a day (Instantly lead credits);
    each row is asked about once (person_source records it)."""
    from ..outbound import get_state, set_state

    today = today or date.today().isoformat()
    state = get_state(db, "harvest.owner_lookups", {}) or {}
    used = state.get("count", 0) if state.get("date") == today else 0
    if used >= daily:
        log(f"owners: daily cap of {daily} lookups reached")
        return 0
    rows = [r for r in db.table("harvest_sellers").select("seller_id, brand, website, first_name, person_source, notes")
            .in_("status", ["pushed", "enriched"]).execute().data
            if r.get("website") and not r.get("first_name") and not (r.get("person_source") or "").startswith("supersearch")]
    rows = rows[:OWNER_BATCH]
    if not rows:
        log("owners: nothing to look up")
        return 0
    domains = list(dict.fromkeys(enrichmod._domain(r["website"]) for r in rows))
    if dry or api is None:
        log(f"owners: {'[dry] would ask' if dry else 'INSTANTLY_API_KEY not set; the operator asks'} SuperSearch for the "
            f"founder at {len(domains)} domain(s)")
        return 0 if api is None and not dry else len(domains)
    limit = min(daily - used, len(domains))
    filters = owner_filters(domains)
    try:
        pool = api.supersearch_count(filters)
        list_id = ensure_list(api, OWNERS_LIST_NAME)
        res = api.supersearch_enrich(list_id, filters, limit, search_name="Hubricon harvest owners")
    except InstantlyError as err:
        log(f"owners: SuperSearch unavailable: {err}")
        _log_event(db, f"owners: SuperSearch unavailable: {err}", {"domains": domains})
        return 0
    for r in rows:
        _update(db, r["seller_id"], person_source="supersearch:requested",
                notes=((r.get("notes") or "") + "; owner asked of SuperSearch").strip("; "))
    set_state(db, "harvest.owner_lookups", {"date": today, "count": used + limit, "list_id": list_id,
                                            "last_job": (res or {}).get("background_job_id")})
    note = (f"owners: asked SuperSearch for the founder at {len(domains)} domain(s), up to {limit} lead(s) "
            f"(pool {pool.get('number_of_leads', '?') if isinstance(pool, dict) else pool}) → list '{OWNERS_LIST_NAME}'")
    log(note)
    _log_event(db, note, {"domains": domains, "limit": limit, "pool": pool, "job": (res or {}).get("background_job_id")})
    return limit


# -- requalify / prune ----------------------------------------------------------

def requalify(db, fetcher: Fetcher, limit: int = REQUALIFY_LIMIT, statuses: tuple[str, ...] = ("pushed", "enriched", "candidate"),
              cache: Cache | None = None, log=print) -> dict:
    """Re-read the live profile of rows already past the gate and apply today's
    band. The first pass sized brands by one listing, which let Gorilla Grip
    (8,703 seller ratings a year) through; the seller's own feedback count
    catches that. Rows that fail become skip_*; `prune` then takes them off
    Instantly. One Amazon request per row, at the fetcher's pace.

    Shopify rows are skipped: there is no Amazon seller profile to re-read for
    a store, and its size signal (the review count on its own product pages)
    is re-derived by re-running `harvest shopify`, not here. They keep the
    verdict the Shopify pass gave them.
    """
    cache = cache or Cache()
    counts: Counter = Counter()
    rows = db.table("harvest_sellers").select("*").in_("status", list(statuses)) \
        .neq("platform", "shopify").order("est_monthly_revenue", desc=True).limit(limit).execute().data
    for row in rows:
        try:
            page = fetcher.get(amazon.seller_url(row["seller_id"]))
        except Blocked as err:
            log(f"  {err}")
            break
        if not page:
            counts["unread"] += 1
            continue
        prof = amazon.seller(page)
        cache.put("seller", row["seller_id"], prof)
        agg = {"seller_id": row["seller_id"], "seller_name": row.get("seller_name"), "brand": row.get("brand"),
               "brands": row.get("brands") or [row.get("brand")], "asins": row.get("asins") or [],
               "reviews_max": row.get("reviews_max") or 0}
        if row.get("source") == "wayback":
            from .wayback import classify_profile  # profile-only rows keep their stricter rules
            status, note, _ = classify_profile(row["seller_id"], prof)
        else:
            status, note = classify(agg, prof)
        tld = enrichmod.offshore_domain(row.get("email")) or enrichmod.offshore_domain(
            enrichmod._domain(row["website"]) if row.get("website") else None)
        if status not in SKIP_STATUSES and tld:
            status, note = "skip_non_us", f"site or contact address on a {tld} domain"
        upd = {"ratings_12mo": prof.get("ratings_12mo"), "ratings_lifetime": prof.get("ratings_lifetime"),
               "business_name": prof.get("business_name") or row.get("business_name"),
               "country": prof.get("country") or row.get("country")}
        if status in SKIP_STATUSES:
            upd.update(status=status, notes=f"requalified: {note}")
            counts[status] += 1
        else:
            counts["kept"] += 1
        _update(db, row["seller_id"], **upd)
        log(f"  {row['brand']}: {'kept' if status not in SKIP_STATUSES else status} "
            f"({prof.get('ratings_12mo')} ratings/12mo, {prof.get('ratings_lifetime')} lifetime) {note if status in SKIP_STATUSES else ''}".rstrip())
    note = "requalify: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing to re-read")
    log(note)
    _log_event(db, note, dict(counts))
    return dict(counts)


def prune(db, api: Instantly | None, dry: bool = False, log=print) -> int:
    """Sellers re-qualified out after they were pushed still sit in the
    Instantly list (and, once enrolled, in the campaign). Delete both leads
    before a mailbox spends a send on them; the prospect row becomes 'dq'."""
    # A row that was pushed carries the list lead's id when Instantly returned
    # one; the enrolled campaign lead is a second object, found by address.
    # Any skip_* row that ever had an address may be in Instantly (pushed_at
    # was not always kept); each is looked up once and the note records it.
    rows = [r for r in db.table("harvest_sellers").select("seller_id, brand, email, status, notes, instantly_lead_id, pushed_at")
            .in_("status", list(SKIP_STATUSES)).execute().data
            if (r.get("instantly_lead_id") or r.get("email"))
            and not any(m in (r.get("notes") or "") for m in ("removed from Instantly", "not in Instantly"))]
    if not rows:
        return 0
    if dry or api is None:
        log(f"prune: {'[dry] would remove' if dry else 'INSTANTLY_API_KEY not set; the operator removes'} "
            f"{len(rows)} lead(s) from Instantly: " + ", ".join(r["brand"] or r["seller_id"] for r in rows))
        return 0 if api is None and not dry else len(rows)
    removed = 0
    for r in rows:
        ids = [r["instantly_lead_id"]] if r.get("instantly_lead_id") else []
        prospects = db.table("prospects").select("id, instantly_lead_id").eq("email", (r.get("email") or "").lower()).execute().data \
            if r.get("email") else []
        ids += [p["instantly_lead_id"] for p in prospects if p.get("instantly_lead_id") and p["instantly_lead_id"] not in ids]
        if r.get("email"):
            try:
                ids += [l["id"] for l in api.leads_by_email(r["email"]) if l.get("id") and l["id"] not in ids]
            except InstantlyError as err:
                log(f"prune {r['brand']}: lookup failed: {err}")
        for lead_id in ids:
            try:
                api.delete_lead(lead_id)
            except InstantlyError as err:
                if err.status != 404:  # gone already is fine
                    log(f"prune {r['brand']}: {err}")
                    break
        else:
            for p in prospects:
                db.table("prospects").update({"status": "dq", "fit_notes": f"harvest: {r['status']} — {r.get('notes') or ''}"[:500],
                                              "updated_at": _now()}).eq("id", p["id"]).execute()
            if not ids:
                _update(db, r["seller_id"], notes=((r.get("notes") or "") + "; not in Instantly").strip("; "))
                continue
            _update(db, r["seller_id"], instantly_lead_id=None, pushed_at=None,
                    notes=((r.get("notes") or "") + f"; removed from Instantly ({len(ids)} lead object(s))").strip("; "))
            removed += 1
            log(f"  removed {r['brand']} from Instantly ({r['status']}, {len(ids)} lead object(s))")
    note = f"prune: {removed} lead(s) removed from Instantly"
    log(note)
    _log_event(db, note, {"removed": removed, "brands": [r["brand"] for r in rows[:removed]]})
    return removed


# -- status / all / install -----------------------------------------------------

def all_rows(db, table: str, columns: str, page: int = 1000) -> list[dict]:
    """Every row, paged. PostgREST caps a response at 1,000 and says nothing
    about it, so from 2026-09-04 the harvest reported exactly "1000 sellers on
    file" every morning while the table actually held 1,837 — the digest looked
    frozen when the crawl was working fine."""
    out: list[dict] = []
    start = 0
    while True:
        rows = db.table(table).select(columns).range(start, start + page - 1).execute().data
        out.extend(rows)
        if len(rows) < page:
            return out
        start += page


def status(db) -> dict:
    rows = all_rows(db, "harvest_sellers", "status, est_monthly_revenue, pushed_at, source, platform")
    counts = Counter(r["status"] for r in rows)
    return {"total": len(rows), "by_status": dict(counts),
            "by_source": dict(Counter(r.get("source") or "bestsellers" for r in rows)),
            # Rows written before 2026-09-04 carry no platform and are Amazon.
            "by_platform": dict(Counter(r.get("platform") or "amazon" for r in rows)),
            "pushed": counts.get("pushed", 0), "ready": counts.get("enriched", 0),
            "candidates": counts.get("candidate", 0)}


def status_text(db) -> str:
    s = status(db)
    groups = [", ".join(f"{k} {v}" for k, v in sorted(s[key].items()))
              for key in ("by_source", "by_platform") if s.get(key)]
    lines = [f"Harvest: {s['total']} sellers on file — "
             + ", ".join(f"{k} {v}" for k, v in sorted(s["by_status"].items()))
             + (" (" + "; ".join(groups) + ")" if groups else "")]
    for r in _rows(db, "enriched", 10):
        lines.append(f"  ready  {r['brand']:<28} {r.get('email') or '':<34} est ${(r.get('est_monthly_revenue') or 0):,.0f}/mo")
    return "\n".join(lines)


def fee_cliff_report(db, within_oz: float = 1.0) -> dict:
    """The weekly data post, from public weights: how many best-selling FBA
    listings sit within `within_oz` of a lighter fee band.

    Amazon only. The post's claim is about the FBA fee schedule, and a Shopify
    product's weight sits against a carrier's rate card instead (see
    shopify.shipping_cliff), so mixing the two would make the headline number
    mean nothing. A Shopify version of this post is its own post.
    """
    rows = [r for r in db.table("harvest_products").select(
        "asin, brand, category, weight_oz, price, est_monthly_units, fulfilled_by_amazon, platform").execute().data
        if (r.get("platform") or "amazon") == "amazon"]
    weighed = [r for r in rows if r.get("weight_oz")]
    near = []
    for r in weighed:
        c = amazon.fee_cliff(r["weight_oz"])
        if c and c[1] <= within_oz:
            near.append({**r, "edge_oz": c[0], "over_by_oz": c[1]})
    total_by_cat = Counter(r.get("category") or "?" for r in weighed)
    near_by_cat = Counter(r.get("category") or "?" for r in near)
    by_category = sorted(
        ({"category": cat, "near": near_by_cat.get(cat, 0), "total": n,
          "share": round(near_by_cat.get(cat, 0) / n, 3)} for cat, n in total_by_cat.items()),
        key=lambda d: (-d["share"], -d["total"]))
    examples = sorted(near, key=lambda r: r.get("est_monthly_units") or 0, reverse=True)[:10]
    return {"products": len(rows), "with_weight": len(weighed), "near_cliff": len(near),
            "share": round(len(near) / len(weighed), 3) if weighed else 0.0,
            "within_oz": within_oz, "by_category": by_category, "examples": examples}


def fee_cliff_text(db, within_oz: float = 1.0) -> str:
    r = fee_cliff_report(db, within_oz)
    if not r["with_weight"]:
        return "Fee-cliff report: no product weights on file yet — run a crawl first."
    lines = [f"Fee-cliff report (public listing weights, {r['with_weight']} of {r['products']} products carry one)",
             f"  {r['near_cliff']} listings ({r['share']:.0%}) sit within {within_oz:g} oz of a lighter FBA weight band", ""]
    for c in r["by_category"][:12]:
        lines.append(f"  {c['category'][:34]:<34} {c['near']:>4} of {c['total']:<5} {c['share']:.0%}")
    if r["examples"]:
        lines += ["", "  Biggest movers (est. units/mo, ounces over the edge):"]
        for e in r["examples"]:
            lines.append(f"    {(e.get('brand') or '?')[:24]:<24} {e['asin']}  {e['weight_oz']:>6.1f} oz  "
                         f"+{e['over_by_oz']:.2f} over {e['edge_oz']} oz  ~{(e.get('est_monthly_units') or 0):,.0f}/mo")
    lines += ["", "  Every figure is an estimate from public pages; the post says so."]
    return "\n".join(lines)


def acquire_lock(path: Path | None = None) -> Path | None:
    """One harvest at a time on this machine: two crawls would double the pace
    Amazon sees. Returns the lock path, or None when a live run holds it."""
    path = path or Cache().root / "run.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            pid = int(path.read_text().strip() or 0)
            os.kill(pid, 0)  # raises when the process is gone
            return None
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    path.write_text(str(os.getpid()))
    return path


def run_all(db, fetcher: Fetcher | None = None, dry: bool = False, max_products: int = MAX_PRODUCTS,
            categories: list[str] | None = None, log=print, lock: Path | None = None,
            store_fetcher: Fetcher | None = None, shopify: bool = True) -> dict:
    """`store_fetcher` and `shopify` exist so a caller can keep this offline.
    The Shopify pass builds its own live fetcher and reads the cached listing
    from ~/.hubricon when neither is given, which is right in production and
    is a live crawl inside a test — pass `shopify=False` there."""
    held = acquire_lock(lock)
    if held is None:
        log("harvest: another run is in progress on this machine; not starting a second one")
        return {"skipped": "locked"}
    try:
        fetcher = fetcher or Fetcher()
        out = {"crawl": crawl(db, fetcher, categories, max_products, log=log)}
        out["listings"] = listings(db, fetcher, limit=RUN_ALL_LISTINGS, log=log)  # archived sellers get a listing to quote
        # The Shopify pass is the one source Amazon cannot switch off, but it
        # depends on the Internet Archive being up. An archive outage must not
        # cost the night's Amazon work, so it is fenced: the pass is skipped
        # with a line in the log and the run carries on to enrich and push.
        if shopify:
            try:
                from . import shopify as shopifymod

                # Its own fetcher: stores go through Chrome, the archive does not.
                stores = store_fetcher or shopifymod.store_fetcher()
                # Category searches of Shopify's own marketplace, not the
                # archive: real trading brands at their own domains.
                handles, metas = shopifymod.discover(shopifymod.archive_fetcher(), stores, log=log)
                out["shopify"] = shopifymod.crawl(db, stores, handles, limit=RUN_ALL_SHOPIFY,
                                                  log=log, metas=metas)
            except Exception as err:  # noqa: BLE001 — any failure here is one source being down
                log(f"shopify: skipped this run ({err})")
                out["shopify"] = {"error": str(err)}
        out["enrich"] = enrich(db, fetcher, log=log)
        api = Instantly() if os.environ.get("INSTANTLY_API_KEY") else None
        out["pushed"] = push(db, api, dry=dry, log=log)
        return out
    finally:
        held.unlink(missing_ok=True)


RUN_HOURS = (6, 18)  # two gentle runs beat one long one: Amazon rate-limits by the hour


def launchd_plist(engine_dir: Path, uv: str = "/opt/homebrew/bin/uv", hours: tuple[int, ...] = RUN_HOURS,
                  minute: int = 10) -> dict:
    log_dir = Path.home() / "Library" / "Logs"
    return {
        "Label": "com.hubricon.harvest",
        "ProgramArguments": [uv, "run", "hubricon", "harvest", "all"],
        "WorkingDirectory": str(engine_dir),
        "StartCalendarInterval": [{"Hour": h, "Minute": minute} for h in hours],
        "StandardOutPath": str(log_dir / "hubricon-harvest.log"),
        "StandardErrorPath": str(log_dir / "hubricon-harvest.err"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
                                 "PYTHONUNBUFFERED": "1"},  # the log is readable while the run is going
    }


def install_launchd(engine_dir: Path | None = None, hours: tuple[int, ...] = RUN_HOURS, minute: int = 10,
                    runner=subprocess.run) -> str:
    engine_dir = engine_dir or Path(__file__).resolve().parents[3]
    uv = subprocess.run(["which", "uv"], capture_output=True, text=True).stdout.strip() or "/opt/homebrew/bin/uv"
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.hubricon.harvest.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(plistlib.dumps(launchd_plist(engine_dir, uv, hours, minute)))
    domain = f"gui/{os.getuid()}"
    runner(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
    res = runner(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
    state = "loaded" if res.returncode == 0 else f"launchctl said: {(res.stderr or res.stdout).strip()}"
    when = " and ".join(f"{h:02d}:{minute:02d}" for h in hours)
    return (f"{plist_path}\n  runs `uv run hubricon harvest all` daily at {when} local "
            f"(missed while asleep → runs at next wake); logs in ~/Library/Logs/hubricon-harvest.log\n  {state}")
