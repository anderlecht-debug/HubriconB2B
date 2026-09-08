"""One `/products.json` call, and most of what a teardown needs.

This is the fact LEAD_SOURCING.md is built around and it is worth restating:
every Shopify store publishes its whole catalogue, unauthenticated — every
product, every variant, every price, every compare-at price, the vendor, the
tags, `created_at` and `updated_at`. **A real pricing teardown can be run on a
store with no permission from the merchant and no guesswork about their
catalogue.** Not category priors — their actual ladder.

`harvest/shopify.py::parse_products` already reads that endpoint, but it keeps
only what the Amazon-shaped row needs and drops two fields this package cannot
do without: `compare_at_price`, which is the entire `permanent_discount`
finding, and `updated_at`, which is how a dead store gives itself away. So the
parse here is a superset rather than a second implementation — the shared
plumbing (`json_payload`, `grams_to_oz`) still comes from there.

Snapshot early and snapshot always. Price history cannot be recovered
retroactively: whatever is not captured today is gone, and it is the backbone
of the strongest finding available on this platform. `run.py` writes an
observation row on every pass for exactly this reason.
"""

from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone

from ..harvest.shopify import grams_to_oz, json_payload

# A ladder gap only means something if there is a ladder. Under this many
# distinct price points the store is a one-product brand and the finding is
# not about it.
MIN_LADDER_POINTS = 4
# Two adjacent price points this far apart, with nothing between them, is a
# hole a customer falls through rather than a step they climb.
LADDER_GAP_RATIO = 2.5


def _f(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _dt(value) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def parse_catalog(text_or_doc) -> list[dict]:
    """`/products.json` -> one dict per product, with the fields the harvest drops.

    `price` is the cheapest published variant, as everywhere else in the repo,
    and `compare_at` is that same variant's anchor — comparing the cheapest
    variant's price against a different variant's compare-at would invent a
    discount the store is not offering.
    """
    doc = json_payload(text_or_doc) if isinstance(text_or_doc, (str, type(None))) else text_or_doc
    if not isinstance(doc, dict):
        return []
    out = []
    for p in doc.get("products") or []:
        if not isinstance(p, dict) or not p.get("handle"):
            continue
        variants = [v for v in (p.get("variants") or []) if isinstance(v, dict)]
        priced = [(v, _f(v.get("price"))) for v in variants]
        priced = [(v, price) for v, price in priced if price]
        cheapest, price = min(priced, key=lambda pair: pair[1]) if priced else (None, None)
        available = sum(1 for v in variants if v.get("available"))
        out.append({
            "handle": p["handle"],
            "title": (p.get("title") or "").strip()[:200] or None,
            "vendor": (p.get("vendor") or "").strip() or None,
            "product_type": (p.get("product_type") or "").strip() or None,
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "published_at": p.get("published_at"),
            "tags": p.get("tags") or [],
            "price": price,
            "compare_at": _f((cheapest or {}).get("compare_at_price")),
            "weight_oz": grams_to_oz((cheapest or {}).get("grams")),
            "sku": (cheapest or {}).get("sku"),
            "variants": len(variants),
            "variants_available": available,
        })
    return out


def price_ladder(products: list[dict]) -> dict:
    """The shape of the catalogue's price points.

    `gap_ratio` is the largest step between adjacent distinct prices, and
    `gap_at` the pair it sits between. A store whose ladder runs 12, 14, 16
    then jumps to 89 has nothing to sell the customer who was ready to spend
    forty, and that hole is visible in one API call.
    """
    prices = sorted({round(p["price"], 2) for p in products if p.get("price")})
    if not prices:
        return {"points": 0, "min": None, "max": None, "median": None, "asp": None,
                "gap_ratio": None, "gap_at": None}
    gap_ratio, gap_at = None, None
    if len(prices) >= MIN_LADDER_POINTS:
        for low, high in zip(prices, prices[1:]):
            ratio = high / low
            if gap_ratio is None or ratio > gap_ratio:
                gap_ratio, gap_at = round(ratio, 2), (low, high)
    every = [p["price"] for p in products if p.get("price")]
    return {"points": len(prices), "min": prices[0], "max": prices[-1],
            "median": round(statistics.median(every), 2),
            "asp": round(sum(every) / len(every), 2),
            "gap_ratio": gap_ratio, "gap_at": gap_at}


def discount_profile(products: list[dict]) -> dict:
    """How much of the catalogue is permanently "on sale".

    A compare-at above the price on a handful of products is a promotion. A
    compare-at above the price on most of the catalogue, month after month, is
    the real price with a decoration on it — the anchor has stopped doing
    anything and the discount is straight margin.
    """
    priced = [p for p in products if p.get("price")]
    if not priced:
        return {"share": None, "mean_depth": None, "discounted": 0, "priced": 0}
    marked = [p for p in priced if p.get("compare_at") and p["compare_at"] > p["price"]]
    depths = [(p["compare_at"] - p["price"]) / p["compare_at"] for p in marked]
    return {
        "share": round(len(marked) / len(priced), 3),
        "mean_depth": round(sum(depths) / len(depths), 3) if depths else None,
        "discounted": len(marked), "priced": len(priced),
    }


def velocity(products: list[dict], now: datetime | None = None) -> dict:
    """How recently the catalogue moved. A dead store looks dead: nothing
    created in two years and nothing updated in six months."""
    now = now or datetime.now(timezone.utc)
    created = [d for d in (_dt(p.get("created_at")) for p in products) if d]
    updated = [d for d in (_dt(p.get("updated_at")) for p in products) if d]
    if not created and not updated:
        return {"days_since_new": None, "days_since_update": None, "new_last_year": None}
    year_ago = now.timestamp() - 365 * 86400
    return {
        "days_since_new": round((now - max(created)).total_seconds() / 86400, 1) if created else None,
        "days_since_update": round((now - max(updated)).total_seconds() / 86400, 1) if updated else None,
        "new_last_year": sum(1 for d in created if d.timestamp() > year_ago) if created else None,
    }


def stockouts(products: list[dict]) -> dict:
    """Variants published but unavailable. Sustained, that is either a supply
    problem or a catalogue nobody maintains — both worth knowing before a
    stranger is told how to price."""
    total = sum(p.get("variants") or 0 for p in products)
    out = sum((p.get("variants") or 0) - (p.get("variants_available") or 0) for p in products)
    return {"variants": total, "unavailable": out,
            "share": round(out / total, 3) if total else None}


# Shopify caps the endpoint at 250 products a page. Reading one page and
# stopping made every large catalogue look like exactly 250 items, which
# silently disabled the single most useful junk filter there is: `score.py`
# throws out a catalogue over 800 SKUs as a supplier feed rather than a brand,
# and no store could ever reach 800. Four pages tells a 300-SKU brand from a
# 2,000-SKU dropshipper, which is all the distinction that is needed, and the
# extra requests are only spent on stores that filled the first page.
PAGE = 250
MAX_PAGES = int(os.environ.get("SOURCING_CATALOG_PAGES", "4"))


def read(fetcher, domain: str, handle: str | None = None, max_pages: int = MAX_PAGES) -> dict:
    """The catalogue for one store, with the metrics computed over it.

    The endpoint is read from the myshopify host when we know it: a headless
    (Hydrogen) storefront serves a React app at the brand's own domain and
    answers `/products.json` there with HTML, while the myshopify host is
    always the classic storefront. Same lesson `harvest/shopify.py` records
    from 2026-09-04, and the same order.
    """
    hosts = [f"{handle}.myshopify.com"] if handle else []
    if domain and domain not in hosts:
        hosts.append(domain)
    products: list[dict] = []
    read_from = None
    truncated = False
    for host in hosts:
        products = parse_catalog(fetcher.get(f"https://{host}/products.json?limit={PAGE}"))
        if not products:
            continue
        read_from = host
        page = 2
        while len(products) % PAGE == 0 and page <= max_pages:
            more = parse_catalog(
                fetcher.get(f"https://{host}/products.json?limit={PAGE}&page={page}"))
            if not more:
                break
            products += more
            page += 1
        # Still full at the last page we were willing to read: the count is a
        # floor, and `score.py` reads it as "at least this many".
        truncated = len(products) >= PAGE * max_pages
        break
    return {
        "products": products, "read_from": read_from, "count": len(products),
        "truncated": truncated,
        "ladder": price_ladder(products), "discounts": discount_profile(products),
        "velocity": velocity(products), "stockouts": stockouts(products),
    }
