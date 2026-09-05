"""What we can see of a seller's shelf, and where it sits in its category.

A teardown that names one SKU and one ounce count is credible and small. The
seller reads it, agrees, and does nothing, because one listing being a few cents
off is not a reason to reply to a stranger.

Two things change that, and both are computed from data already on file:

**The whole shelf.** Every listing the harvest holds for this seller, priced
against Amazon's published card in one table, with a total underneath. Three
listings each giving up twenty cents is a different conversation from one
listing giving up twenty cents, and it says we looked at the shelf rather than
at a lucky SKU.

**The category around it.** `harvest_products` holds the public weight of every
listing the crawl has ever read — six hundred and counting, across the
categories where founder-run brands live. Nobody else publishes that, because
nobody else built the crawl. Telling a seller that 38% of the Kitchen & Dining
listings we have measured sit within an ounce of a cheaper band, and that theirs
is one of them, is the sentence that makes them believe we measure this for a
living. It is also the dataset behind the public fee-cliff post in GROWTH.md, so
the page and the post say the same thing.

The arithmetic is the cold engine's own tier-aware ladder, not the flat
approximation `harvest.fee_cliff` uses for the report. The number on the chart
and the number in the finding have to be the same number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import priors
from ..harvest import shopify as shopify_harvest
from .snapshot import Item, ProspectSnapshot, parse_dims, size_tier

# Below this a percentage is noise dressed up as a finding, so the benchmark is
# left off the page rather than quoted from a handful of listings.
MIN_CATEGORY_SAMPLE = 30
# "Within an ounce of a cheaper band" — the same threshold as the public post.
NEAR_EDGE_OZ = 1.0


@dataclass(frozen=True)
class ShelfRow:
    """One listing, priced against its own platform's published card."""
    ref: str
    label: str
    title: str | None
    url: str
    price: float | None
    weight_oz: float | None
    tier: str | None
    fee: float | None
    edge: float | None
    over_by: float | None
    monthly_units: float | None
    platform: str = "amazon"

    @property
    def near_edge(self) -> bool:
        limit = CARRIER_NEAR_EDGE_OZ if self.platform == "shopify" else NEAR_EDGE_OZ
        return self.over_by is not None and self.over_by <= limit


def tier_label(tier: str | None) -> str:
    return {"small_standard": "small standard", "large_standard": "large standard",
            "oversize": "oversize"}.get(tier or "", "unknown")


def _label(ref: str, platform: str) -> str:
    """What to print in the table's first column.

    An ASIN is ten characters. A Shopify ref is the product's whole URL path,
    which at forty-odd characters forced the column so wide that every other one
    scrolled off the page — the table rendered as a list of URLs and nothing
    else. The handle alone identifies the product to its own owner.
    """
    if platform == "shopify" and "/products/" in ref:
        return ref.rsplit("/products/", 1)[-1]
    return ref


def describe(item: Item, platform: str = "amazon", today: date | None = None) -> ShelfRow:
    """One listing as its own platform's card sees it.

    Running Amazon's ladder over a Shopify catalogue was worse than useless: it
    returned None for every column, so the shelf table on a Shopify teardown
    printed a list of product handles with nothing beside them.
    """
    today = today or date.today()
    weight = item.billable_weight_oz
    if platform == "shopify":
        cliff = shopify_harvest.shipping_cliff(weight)
        edge = float(cliff[0]) if cliff else None
        return ShelfRow(
            ref=item.ref, label=_label(item.ref, platform), title=item.title, url=item.url,
            price=item.price, weight_oz=weight, tier=None, fee=None, edge=edge,
            over_by=cliff[1] if cliff else None,
            monthly_units=item.est_monthly_units, platform=platform)
    tier = item.tier
    fee = (priors.fulfilment_fee(tier, weight, item.price, today)
           if tier in ("small_standard", "large_standard") and weight else None)
    edge = priors.band_edge_below(tier, weight) if tier in ("small_standard", "large_standard") \
        else None
    return ShelfRow(
        ref=item.ref, label=_label(item.ref, platform), title=item.title, url=item.url,
        price=item.price, weight_oz=weight, tier=tier, fee=fee, edge=edge,
        over_by=round(weight - edge, 2) if (edge is not None and weight) else None,
        monthly_units=item.est_monthly_units, platform=platform)


def shelf(snap: ProspectSnapshot, today: date | None = None) -> list[ShelfRow]:
    """Every listing we hold, the ones with something to say about them first.

    A 250-product Shopify catalogue only prints its first ten rows, so the order
    decides what the reader sees. Listings sitting near an edge lead, then the
    dearest, then the heaviest — alphabetical by URL, which is what it used to
    be, put ten arbitrary handles at the top of the evidence.
    """
    rows = [describe(i, snap.platform, today) for i in snap.items]
    rows.sort(key=lambda r: (not r.near_edge, -(r.fee or 0), -(r.weight_oz or 0), r.ref))
    return rows


# -- the category around it ---------------------------------------------------------

# The buckets a distribution is drawn in, per ladder. FBA bands are two to four
# ounces wide, so half-ounce buckets are the right grain; a carrier pound is
# sixteen, so they are not.
FBA_BUCKETS = [0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
CARRIER_BUCKETS = [0, 1.0, 2.0, 4.0, 8.0, 12.0]
CARRIER_NEAR_EDGE_OZ = 2.0


@dataclass(frozen=True)
class Benchmark:
    category: str
    measured: int
    near: int
    share: float
    buckets: list[tuple[float, float, int]]     # (lo oz, hi oz, count)
    your_over_by: float | None

    @property
    def worth_showing(self) -> bool:
        return self.measured >= MIN_CATEGORY_SAMPLE


def _over_by_carrier(weight_oz: float | None) -> float | None:
    """Ounces above the pound boundary below this parcel, on the carrier ladder.

    Shopify's own product types are free text a merchant invents, so there is no
    shared taxonomy to slice by — and none is needed, because the pound boundary
    is the same for every parcel whatever is in it. The benchmark is therefore
    across every Shopify product the crawl has weighed rather than within a
    category.
    """
    cliff = shopify_harvest.shipping_cliff(weight_oz)
    return cliff[1] if cliff else None


def _over_by(weight_oz: float | None, dims: str | None = None) -> float | None:
    """Ounces above the nearest cheaper band edge, on the tier-aware ladder.

    Three cases, in order of how much we know:

    1. The listing publishes dimensions, so its size tier is certain and so is
       its ladder. Most of the crawl's rows carry dimensions and the first
       version of this threw them away, which cost about a third of the sample
       for no reason.
    2. No dimensions, but both standard ladders happen to agree on the edge
       below this weight — true at 4, 8, 12 and 16 oz — so the answer is certain
       without knowing the tier.
    3. No dimensions and the ladders disagree. Left out rather than assigned a
       guessed tier, which is the rule the finding itself follows.
    """
    if not weight_oz or weight_oz <= 0:
        return None
    tier = size_tier(parse_dims(dims), weight_oz) if dims else None
    if tier in ("small_standard", "large_standard"):
        edge = priors.band_edge_below(tier, weight_oz)
    elif tier == "oversize":
        return None                       # off the standard card entirely
    else:
        edges = {t: priors.band_edge_below(t, weight_oz)
                 for t in ("small_standard", "large_standard")}
        if weight_oz > priors.SMALL_STANDARD_MAX_OZ:
            edge = edges["large_standard"]
        elif len(set(edges.values())) == 1:
            edge = next(iter(edges.values()))
        else:
            return None
    return round(weight_oz - edge, 2) if edge is not None else None


def benchmark(rows: list[dict], category: str | None,
              your_weight_oz: float | None = None,
              your_dims: str | None = None,
              platform: str = "amazon") -> Benchmark | None:
    """How the ground around this seller behaves, from everything the crawl read.

    Two shapes, because the two platforms are billed on different ladders and
    mixing them would put an FBA band edge under a Shopify parcel:

      amazon    within the listing's own Best Sellers category, on the FBA
                weight bands. Categories are Amazon's taxonomy, so they mean
                the same thing across sellers.
      shopify   across every Shopify product on file, on the carrier's pound
                boundary. A merchant's product_type is free text they invented,
                so there is no shared category to slice by — and none is needed,
                because a pound is a pound whatever is in the box.

    `rows` are raw `harvest_products` records, passed in rather than queried so
    this stays a pure function the page can be rendered from a fixture.
    """
    shopify = (platform or "amazon").lower() == "shopify"
    if shopify:
        pool = [r for r in rows if (r.get("platform") or "amazon") == "shopify"]
        measure = lambda r: _over_by_carrier(float(r["weight_oz"]))    # noqa: E731
        label, edges, near_oz = "Shopify brands", CARRIER_BUCKETS, CARRIER_NEAR_EDGE_OZ
        mine = _over_by_carrier(your_weight_oz)
    else:
        if not category:
            return None
        wanted = category.strip().lower()
        pool = [r for r in rows
                if (r.get("platform") or "amazon") == "amazon"
                and (r.get("category") or "").strip().lower() == wanted]
        measure = lambda r: _over_by(float(r["weight_oz"]), r.get("dims"))   # noqa: E731
        label, edges, near_oz = category, FBA_BUCKETS, NEAR_EDGE_OZ
        mine = _over_by(your_weight_oz, your_dims)
    measured = [w for w in (measure(r) for r in pool if r.get("weight_oz")) if w is not None]
    if not measured:
        return None
    near = sum(1 for m in measured if m <= near_oz)
    buckets = [(lo, hi, sum(1 for m in measured if lo <= m < hi))
               for lo, hi in zip(edges, edges[1:] + [999.0])]
    return Benchmark(
        category=label, measured=len(measured), near=near,
        share=round(near / len(measured), 3), buckets=buckets, your_over_by=mine,
    )


def load_benchmark(db, category: str | None, your_weight_oz: float | None = None,
                   your_dims: str | None = None, platform: str = "amazon") -> Benchmark | None:
    if not category and (platform or "amazon").lower() != "shopify":
        return None
    from .. import db as dbmod

    rows = dbmod.fetch_rows(db, "harvest_products", "category, weight_oz, dims, platform")
    return benchmark(rows, category, your_weight_oz, your_dims, platform)


def shelf_total(findings_for_shelf) -> tuple[float, float]:
    """The monthly range across every finding on the page. Independent listings,
    so they add; a listing with no volume estimate contributes nothing rather
    than a guess."""
    lo = sum(f.dollars_low for f in findings_for_shelf)
    hi = sum(f.dollars_high for f in findings_for_shelf)
    return round(lo, 2), round(hi, 2)
