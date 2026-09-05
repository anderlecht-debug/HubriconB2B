"""Provider payloads in, one typed `ProspectSnapshot` out.

Nothing downstream of this module knows where a number came from. That is the
seam COLD_ENGINE.md §2.1 asks for: today the only source is the free harvest of
public pages this repo already runs, and the day a Keepa subscription exists it
becomes another module writing the same dataclass, with price and rank history
filling fields the harvest leaves empty.

The one piece of judgement in here is the difference between two weights:

  item weight      what the brand typed into their own listing
  billable weight  what the carrier actually charges on: the greater of the
                   packed weight and the dimensional weight

Amazon bills the second. A public page publishes the first, and the packed
dimensions, which is enough to compute the second. Keeping the two apart is
what stops the engine asserting a fee band it cannot see.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from . import priors

DIMS_RE = re.compile(
    r"([\d.]+)\s*[x×]\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*(inches|inch|in\b|cm|centimet\w*)?", re.I)


def parse_dims(s: str | None) -> tuple[float, float, float] | None:
    """'12.4 x 8.1 x 2 inches' → (12.4, 8.1, 2.0), longest first. cm converted."""
    if not s:
        return None
    m = DIMS_RE.search(s)
    if not m:
        return None
    vals = [float(m.group(i)) for i in (1, 2, 3)]
    unit = (m.group(4) or "").lower()
    if unit.startswith(("cm", "centi")):
        vals = [v / 2.54 for v in vals]
    if any(v <= 0 for v in vals):
        return None
    a, b, c = sorted(vals, reverse=True)
    return round(a, 2), round(b, 2), round(c, 2)


def dim_weight_oz(dims: tuple[float, float, float] | None) -> float | None:
    """Cubic inches over 139, in ounces — the ground carriers' arithmetic.

    Only applies once the parcel passes a cubic foot; under that, Amazon bills
    the real weight and quoting dimensional weight would be wrong.
    """
    if not dims:
        return None
    cubic_in = dims[0] * dims[1] * dims[2]
    if cubic_in < priors.DIM_WEIGHT_MIN_CUFT * 1728:
        return None
    return round(cubic_in / priors.DIM_DIVISOR * 16, 2)


def size_tier(dims: tuple[float, float, float] | None, weight_oz: float | None) -> str | None:
    """'small_standard' | 'large_standard' | 'oversize', or None when unknown.

    Returns None rather than a guess when the dimensions are missing: the tier
    is worth about a dollar a unit, so assuming one would be the single easiest
    way to put a wrong number in a stranger's inbox.
    """
    if dims is None or weight_oz is None:
        return None
    env_s, env_l = priors.SMALL_STANDARD_ENVELOPE_IN, priors.LARGE_STANDARD_ENVELOPE_IN
    fits = lambda env: all(d <= e for d, e in zip(dims, env))  # noqa: E731
    if weight_oz <= priors.SMALL_STANDARD_MAX_OZ and fits(env_s):
        return "small_standard"
    if weight_oz <= priors.LARGE_STANDARD_MAX_OZ and fits(env_l):
        return "large_standard"
    return "oversize"


@dataclass(frozen=True)
class Observation:
    """One reading of a listing's public price and rank, kept rather than
    overwritten. Repeat reads of the same page are the only price history this
    business has until a Keepa subscription exists."""
    seen_on: date
    price: float | None = None
    rank: int | None = None


@dataclass(frozen=True)
class Item:
    """One listing, as its own public page describes it."""
    ref: str                       # ASIN, or <domain>/products/<handle> on Shopify
    url: str
    title: str | None = None
    category: str | None = None
    price: float | None = None
    reviews: int | None = None
    rank: int | None = None
    item_weight_oz: float | None = None
    dims_in: tuple[float, float, float] | None = None
    est_monthly_units: float | None = None
    est_monthly_revenue: float | None = None
    fulfilled_by_amazon: bool | None = None
    history: tuple[Observation, ...] = ()

    @property
    def tier(self) -> str | None:
        # Decided on the billable weight, because that is what Amazon measures:
        # a light product in a big box can be pushed out of a tier by its own
        # dimensions alone.
        return size_tier(self.dims_in, self.billable_weight_oz)

    @property
    def dim_weight_oz(self) -> float | None:
        return dim_weight_oz(self.dims_in)

    @property
    def billable_weight_oz(self) -> float | None:
        """What a carrier charges on: the greater of packed and dimensional.

        A floor, not the truth — the packed weight also carries Amazon's own
        packaging, which no public page publishes. Everything downstream treats
        it as a lower bound and says so.
        """
        weights = [w for w in (self.item_weight_oz, self.dim_weight_oz) if w]
        return max(weights) if weights else None


@dataclass(frozen=True)
class ProspectSnapshot:
    """Everything public we hold about one company, at one moment."""
    key: str                       # seller id, or the myshopify handle
    platform: str                  # 'amazon' | 'shopify'
    provider: str                  # which source module produced this
    brand: str | None = None
    business_name: str | None = None
    website: str | None = None
    email: str | None = None
    email_confidence: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    est_monthly_revenue: float | None = None
    ratings_12mo: int | None = None
    items: tuple[Item, ...] = ()
    captured_at: datetime | None = None
    cost_usd: float = 0.0
    payload: dict = field(default_factory=dict, repr=False)

    @property
    def display_name(self) -> str:
        return self.brand or self.business_name or self.key

    @property
    def jurisdiction(self) -> str:
        """Resolved country, which decides the compliance path. Unknown is 'XX'."""
        return (self.country or "XX").strip().upper()[:2] or "XX"

    def priced_items(self) -> list[Item]:
        """Items with enough on file to price anything: a price and a volume."""
        return [i for i in self.items if i.price and i.est_monthly_units]


def as_of(snapshot: ProspectSnapshot) -> date:
    return (snapshot.captured_at or datetime.now()).date()
