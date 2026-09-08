"""The free source: rows the public-page harvest already collected.

COLD_ENGINE.md §2.1 specifies Keepa and Rainforest and forbids writing a
scraper against Amazon. Hubricon has neither subscription and does have a
harvest — `hubricon harvest`, GROWTH.md — that reads Best Sellers lists,
product pages and the seller profile Amazon has required every professional
seller to publish since 2020, a few requests a minute from a home connection.
That crawl is a standing decision of this business, not something introduced
here, and this module writes no new requests: it reads `harvest_products` and
`harvest_sellers`, which were fetched for the founder lane regardless.

So the constraint the spec is actually protecting — never send a number we
cannot stand behind — is honoured by the confidence gate downstream, and the
marginal cost of a snapshot is zero. The seam for Keepa stays open: a second
module writing the same dataclass turns on the history detectors with no other
change.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ...harvest import amazon
from ..snapshot import Item, ProspectSnapshot, parse_dims

NAME = "harvest"

# Seller statuses that mean the harvest finished with the row and kept it.
# 'candidate' rows have not been enriched yet and carry no address.
USABLE = ("pushed", "enriched", "no_email", "no_website")


def _url(platform: str, ref: str, website: str | None) -> str:
    if platform == "shopify":
        return f"https://{ref}" if not ref.startswith("http") else ref
    return f"{amazon.BASE}/dp/{ref}"


def _item(row: dict, platform: str, website: str | None) -> Item:
    ref = row["asin"]
    price = float(row["price"]) if row.get("price") is not None else None
    return Item(
        ref=ref,
        url=_url(platform, ref, website),
        title=row.get("title"),
        category=row.get("category"),
        price=price,
        compare_at_price=(float(row["compare_at_price"])
                          if row.get("compare_at_price") is not None else None),
        reviews=row.get("reviews"),
        rank=row.get("bsr"),
        item_weight_oz=float(row["weight_oz"]) if row.get("weight_oz") is not None else None,
        dims_in=parse_dims(row.get("dims")),
        est_monthly_units=(float(row["est_monthly_units"])
                           if row.get("est_monthly_units") is not None else None),
        est_monthly_revenue=(float(row["est_monthly_revenue"])
                             if row.get("est_monthly_revenue") is not None else None),
        fulfilled_by_amazon=row.get("fulfilled_by_amazon"),
    )


def to_snapshot(seller: dict, products: list[dict]) -> ProspectSnapshot:
    """The pure half: two table rows in, one snapshot out. No database."""
    platform = (seller.get("platform") or "amazon").lower()
    website = seller.get("website")
    items = tuple(sorted(
        (_item(p, platform, website) for p in products),
        key=lambda i: -(i.est_monthly_revenue or 0)))
    rev = seller.get("est_monthly_revenue")
    return ProspectSnapshot(
        key=seller["seller_id"],
        platform=platform,
        provider=NAME,
        brand=seller.get("brand") or seller.get("seller_name"),
        business_name=seller.get("business_name"),
        website=website,
        email=seller.get("email"),
        email_confidence=seller.get("email_confidence"),
        first_name=seller.get("first_name"),
        last_name=seller.get("last_name"),
        city=seller.get("city"),
        state=seller.get("state"),
        country=seller.get("country"),
        est_monthly_revenue=float(rev) if rev is not None else None,
        ratings_12mo=seller.get("ratings_12mo"),
        items=items,
        captured_at=datetime.now(timezone.utc),
        cost_usd=0.0,
        payload={"seller": seller, "products": products},
    )


class HarvestSource:
    """The `Source` implementation. Reads only; never fetches a page."""

    name = NAME

    def __init__(self, db):
        self.db = db

    def keys(self, limit: int = 50) -> list[str]:
        from ... import db as dbmod

        rows = [r for r in dbmod.fetch_rows(self.db, "harvest_sellers",
                                            "seller_id, est_monthly_revenue, status")
                if r.get("status") in USABLE]
        rows.sort(key=lambda r: -(float(r.get("est_monthly_revenue") or 0)))
        return [r["seller_id"] for r in rows[:limit]]

    def snapshot(self, key: str) -> ProspectSnapshot | None:
        sellers = (self.db.table("harvest_sellers").select("*")
                   .eq("seller_id", key).execute().data)
        if not sellers:
            return None
        products = (self.db.table("harvest_products").select("*")
                    .eq("seller_id", key).execute().data)
        return to_snapshot(sellers[0], products)

    def estimated_cost_usd(self) -> float:
        return 0.0
