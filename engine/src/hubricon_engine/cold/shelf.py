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
from .snapshot import Item, ProspectSnapshot, parse_dims, size_tier

# Below this a percentage is noise dressed up as a finding, so the benchmark is
# left off the page rather than quoted from a handful of listings.
MIN_CATEGORY_SAMPLE = 30
# "Within an ounce of a cheaper band" — the same threshold as the public post.
NEAR_EDGE_OZ = 1.0


@dataclass(frozen=True)
class ShelfRow:
    """One listing, priced against the published card."""
    ref: str
    title: str | None
    url: str
    price: float | None
    weight_oz: float | None
    tier: str | None
    fee: float | None
    edge: float | None
    over_by: float | None
    monthly_units: float | None

    @property
    def near_edge(self) -> bool:
        return self.over_by is not None and self.over_by <= NEAR_EDGE_OZ


def tier_label(tier: str | None) -> str:
    return {"small_standard": "small standard", "large_standard": "large standard",
            "oversize": "oversize"}.get(tier or "", "unknown")


def describe(item: Item, today: date | None = None) -> ShelfRow:
    """One listing as the fee schedule sees it. Every field may be None; a page
    that cannot show a column simply does not show it."""
    today = today or date.today()
    tier = item.tier
    weight = item.billable_weight_oz
    fee = (priors.fulfilment_fee(tier, weight, item.price, today)
           if tier in ("small_standard", "large_standard") and weight else None)
    edge = priors.band_edge_below(tier, weight) if tier in ("small_standard", "large_standard") \
        else None
    return ShelfRow(
        ref=item.ref, title=item.title, url=item.url, price=item.price,
        weight_oz=weight, tier=tier, fee=fee, edge=edge,
        over_by=round(weight - edge, 2) if (edge is not None and weight) else None,
        monthly_units=item.est_monthly_units,
    )


def shelf(snap: ProspectSnapshot, today: date | None = None) -> list[ShelfRow]:
    """Every listing we hold for this seller, dearest fee first."""
    rows = [describe(i, today) for i in snap.items]
    rows.sort(key=lambda r: (-(r.fee or 0), r.ref))
    return rows


# -- the category around it ---------------------------------------------------------

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
              your_dims: str | None = None) -> Benchmark | None:
    """How the seller's category behaves, from every listing the crawl has read.

    `rows` are raw `harvest_products` records — passed in rather than queried so
    this stays a pure function and the page can be rendered from a fixture.
    """
    if not category:
        return None
    wanted = category.strip().lower()
    measured = [w for w in
                (_over_by(float(r["weight_oz"]), r.get("dims")) for r in rows
                 if r.get("weight_oz") and (r.get("category") or "").strip().lower() == wanted)
                if w is not None]
    if not measured:
        return None
    near = sum(1 for m in measured if m <= NEAR_EDGE_OZ)
    edges = [0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
    buckets = []
    for lo, hi in zip(edges, edges[1:] + [999.0]):
        buckets.append((lo, hi, sum(1 for m in measured if lo <= m < hi)))
    return Benchmark(
        category=category, measured=len(measured), near=near,
        share=round(near / len(measured), 3), buckets=buckets,
        your_over_by=_over_by(your_weight_oz, your_dims),
    )


def load_benchmark(db, category: str | None, your_weight_oz: float | None = None,
                   your_dims: str | None = None) -> Benchmark | None:
    if not category:
        return None
    rows = db.table("harvest_products").select("category, weight_oz, dims").execute().data
    return benchmark(rows, category, your_weight_oz, your_dims)


def shelf_total(findings_for_shelf) -> tuple[float, float]:
    """The monthly range across every finding on the page. Independent listings,
    so they add; a listing with no volume estimate contributes nothing rather
    than a guess."""
    lo = sum(f.dollars_low for f in findings_for_shelf)
    hi = sum(f.dollars_high for f in findings_for_shelf)
    return round(lo, 2), round(hi, 2)
