"""Snapshot in, every defensible finding out. Each one carries its own doubt.

The rule that shapes this whole module: **a finding that cannot be priced from
a published rate card does not exist.** Not "is estimated", not "is flagged" —
does not exist. `detect` returns fewer findings than a reader might expect, and
that is the design. Roughly half of the prospects that reach here produce
nothing at all (COLD_ENGINE.md §2.2).

Two kinds of uncertainty run through everything below, and they are kept apart
because they behave differently:

  *the per-unit figure*  comes off Amazon's published fee schedule. It is
                         arithmetic, and it is a point number when we know the
                         listing's size tier and a range when we do not.
  *the monthly figure*   multiplies that by a volume estimated from the public
                         sales rank, which is a power-law fit and wrong by a
                         factor either way. It is always a range, and the email
                         says where the range comes from.

So the copy leads with the per-unit number, which is nearly certain, and offers
the monthly one as a bracket. That ordering is deliberate: a seller can check
the per-unit claim against their own fee report in thirty seconds, and once
they have, the bracket reads as caution rather than hedging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .. import calibration
from ..harvest import shopify as shopify_harvest
from . import priors
from .snapshot import ProspectSnapshot, Item

# The public rank → units curve (harvest/amazon.py) is fitted to the published
# estimators and is comfortably wrong by a factor of two either way. Every
# monthly figure is bracketed with these and the email says so.
UNITS_LOW, UNITS_HIGH = 0.5, 1.5

# A weight band is only worth naming if a seller could plausibly shave under it.
# Six ounces into a band is a redesign, and nobody acts on a redesign because a
# stranger emailed them. The carrier limit is wider because its bands are: a
# pound is sixteen ounces, so trimming three off a nineteen-ounce parcel is a
# lighter box, while three off an FBA unit in a two-ounce band is the product.
MAX_SHAVEABLE_OZ = 2.0
MAX_SHAVEABLE_CARRIER_OZ = 3.0
# Below this the finding is real and not worth anybody's attention.
MIN_PER_UNIT_USD = 0.08
# A near miss on a size-tier envelope. Beyond this the box is the wrong box.
MAX_ENVELOPE_OVERAGE = 1.35
# Dimensional weight has to beat the real weight by enough to be worth saying.
MIN_DIM_WEIGHT_RATIO = 1.3

AXES = ("length", "width", "thickness")


@dataclass(frozen=True)
class Finding:
    """One thing we are willing to tell a stranger about their own business."""
    kind: str
    dollars_low: float
    dollars_high: float
    confidence: float
    assumptions: list[str]
    evidence: dict
    asin_or_sku: str | None = None
    item_title: str | None = None
    item_url: str | None = None
    # "calibrated on 3 client accounts (412 observations)" when a figure in
    # this finding came from consenting clients' real data rather than a
    # published card; None otherwise. The page prints it beside the assumption.
    provenance: str | None = None

    @property
    def per_unit_low(self) -> float:
        return self.evidence.get("per_unit_low", 0.0)

    @property
    def per_unit_high(self) -> float:
        return self.evidence.get("per_unit_high", 0.0)

    @property
    def priced(self) -> bool:
        return self.dollars_high > 0 or self.per_unit_high > 0


def _monthly(per_unit_low: float, per_unit_high: float, units: float | None) -> tuple[float, float]:
    """Per-unit range × a bracketed volume. No volume means no monthly claim."""
    if not units:
        return 0.0, 0.0
    return (round(per_unit_low * units * UNITS_LOW, 2),
            round(per_unit_high * units * UNITS_HIGH, 2))


def _volume_assumption(item: Item) -> str:
    return (f"about {item.est_monthly_units:,.0f} units a month, estimated from this listing's "
            f"public sales rank (#{item.rank:,} in {item.category}); the monthly range spans "
            f"half to one and a half times that"
            if item.est_monthly_units and item.rank else
            "no monthly volume — the per-unit figure is the whole claim")


def _card_assumption(today: date) -> str:
    return (f"Amazon's published US FBA fulfilment fee schedule, {priors.FBA_EFFECTIVE} to "
            f"{priors.FBA_THROUGH}, including the 3.5% fuel and logistics surcharge")


# -- price_band_edge ---------------------------------------------------------------

def _price_band_jump_range(tier: str | None, weight_oz: float | None,
                           band_from: int, band_to: int, today: date) -> tuple[float, float] | None:
    """What moving up one price column costs per unit, at this weight.

    With a known tier and weight it is one number off the card. Without them it
    is the range that column step takes across the whole standard schedule —
    which is narrow, because Amazon steps the columns almost uniformly. That is
    why this is the one finding that survives a listing with no published
    weight.
    """
    if tier in ("small_standard", "large_standard") and weight_oz:
        hi = priors.fulfilment_fee(tier, weight_oz, _mid_price(band_to), today)
        lo = priors.fulfilment_fee(tier, weight_oz, _mid_price(band_from), today)
        if hi is None or lo is None:
            return None
        return round(hi - lo, 4), round(hi - lo, 4)
    deltas = []
    for table in (priors.SMALL_STANDARD_OZ, priors.LARGE_STANDARD_OZ):
        deltas += [fees[band_to] - fees[band_from] for _, fees in table]
    deltas.append(priors.LARGE_STANDARD_OVER_3LB_BASE[band_to]
                  - priors.LARGE_STANDARD_OVER_3LB_BASE[band_from])
    mult = 1 + (priors.FUEL_SURCHARGE if today >= priors.FUEL_SURCHARGE_FROM else 0.0)
    return round(min(deltas) * mult, 4), round(max(deltas) * mult, 4)


def _mid_price(band: int) -> float:
    """A price that lands squarely in the given fee column."""
    return (9.99, 25.00, 99.00)[band]


def price_band_edge(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """A listing priced just above $10 or $50 nets less than one priced just below.

    Amazon's 2026 schedule prices every weight band three times, by sale price.
    Crossing $10 costs 82c to $1.01 a unit in fulfilment; crossing $50 costs
    26c. Until the price rise covers that jump net of the referral fee, the
    higher price is the worse price — and nothing about the listing has to
    change to fix it.

    This is the strongest finding the engine has. It needs no weight, no
    dimensions, no COGS and no volume: it is two published rates and the price
    the seller set themselves.
    """
    price = item.price
    if not price:
        return None
    band = priors.price_band(price)
    if band in (None, 0):
        return None
    edge = priors.PRICE_BAND_EDGES[band - 1]
    below = round(edge - 0.01, 2)
    jump = _price_band_jump_range(item.tier, item.billable_weight_oz, band - 1, band, today)
    if jump is None:
        return None
    rate = priors.referral_rate(item.category)
    given_up = (price - below) * (1 - rate)         # revenue lost by pricing below the edge
    per_unit_low = round(jump[0] - given_up, 4)
    per_unit_high = round(jump[1] - given_up, 4)
    if per_unit_low <= MIN_PER_UNIT_USD:            # conservative: the low end must clear the bar
        return None
    exact = jump[0] == jump[1]
    lo, hi = _monthly(per_unit_low, per_unit_high, item.est_monthly_units)
    learned = calibration.describe(f"amazon.referral_rate.{(item.category or '').strip().lower()}")
    assumptions = [
        _card_assumption(today),
        f"a {rate:.0%} referral fee, "
        + (f"the rate Amazon actually charged, {learned}" if learned
           else f"Amazon's published rate for {item.category or 'this category'}"),
        _volume_assumption(item),
    ]
    if not exact:
        assumptions.append(
            "your packed weight is not published, so the fee jump is the range that step "
            "takes across Amazon's whole standard-size schedule")
    return Finding(
        kind="price_band_edge",
        dollars_low=lo, dollars_high=hi,
        confidence=0.90 if exact else 0.80,
        assumptions=assumptions,
        evidence={
            "chart": "net_vs_price",
            "edge": edge, "your_price": price, "target_price": below,
            "fee_jump_low": jump[0], "fee_jump_high": jump[1],
            "referral_rate": rate,
            "per_unit_low": per_unit_low, "per_unit_high": per_unit_high,
            "monthly_units": item.est_monthly_units,
            "tier": item.tier, "weight_oz": item.billable_weight_oz,
            "break_even_price": round(below + jump[1] / (1 - rate), 2),
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
        provenance=learned,
    )


# -- fee_band_edge -----------------------------------------------------------------

def fee_band_edge(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """The published weight is an ounce or two over a fulfilment band edge.

    The honest version of the hook this business has been sending. What a
    product page publishes is the *item* weight; Amazon bills the *shipping*
    weight, which adds its own packaging and takes the greater of that and the
    dimensional weight. So the published weight is a floor: we know the unit is
    at least in the band we name, and we do not know it is not in a heavier one.

    The claim is therefore conditional and says so — 'if your packed weight
    lands in the band just above, this is what the edge costs' — which is both
    true and still checkable in thirty seconds against their own fee report.
    """
    weight, price = item.item_weight_oz, item.price
    if not weight or not price:
        return None
    tiers = [item.tier] if item.tier in ("small_standard", "large_standard") \
        else ["small_standard", "large_standard"]
    if item.tier == "oversize":
        return None
    edges = {t: priors.band_edge_below(t, weight) for t in tiers}
    if any(e is None for e in edges.values()):
        return None
    # With no dimensions we do not know which tier's ladder applies. Only claim
    # an edge both ladders agree on; where they disagree, say nothing.
    if len(set(edges.values())) != 1:
        return None
    edge = next(iter(edges.values()))
    over_by = round(weight - edge, 3)
    if over_by > MAX_SHAVEABLE_OZ:
        return None
    deltas = []
    for t in tiers:
        now = priors.fulfilment_fee(t, weight, price, today)
        at_edge = priors.fulfilment_fee(t, edge, price, today)
        if now is None or at_edge is None:
            continue
        deltas.append(round(now - at_edge, 4))
    if not deltas:
        return None
    per_unit_low, per_unit_high = min(deltas), max(deltas)
    if per_unit_high < MIN_PER_UNIT_USD:
        return None
    lo, hi = _monthly(per_unit_low, per_unit_high, item.est_monthly_units)
    exact = len(tiers) == 1
    assumptions = [
        _card_assumption(today),
        "your listing's published item weight, which is a floor: Amazon bills the packed "
        "weight, which adds its own packaging, so the unit is at least this heavy",
        _volume_assumption(item),
    ]
    if not exact:
        assumptions.append("your packed dimensions are not published, so the figure spans both "
                           "standard size tiers — the smaller number is the safe one")
    return Finding(
        kind="fee_band_edge",
        dollars_low=lo, dollars_high=hi,
        confidence=0.72 if exact else 0.60,
        assumptions=assumptions,
        evidence={
            "chart": "fee_vs_weight",
            "edge": edge, "your_weight_oz": weight, "over_by_oz": over_by,
            "tier": item.tier, "tiers_considered": tiers,
            "per_unit_low": per_unit_low, "per_unit_high": per_unit_high,
            "monthly_units": item.est_monthly_units, "price": price,
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
    )


# -- dim_weight_overage ------------------------------------------------------------

def dim_weight_overage(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """The box is billed on its volume, not on what is inside it.

    Once a parcel passes a cubic foot the carriers — and Amazon, on the same
    divisor of 139 — charge on length × width × height rather than weight. A
    light product in a large box therefore pays a fee set by air. Both numbers
    are on the seller's own page, which is what makes this defensible: we are
    not estimating the box, we are reading the box off their listing.
    """
    dim_w, item_w, price = item.dim_weight_oz, item.item_weight_oz, item.price
    tier = item.tier
    if not dim_w or not item_w or not price or tier not in ("small_standard", "large_standard"):
        return None
    if dim_w < item_w * MIN_DIM_WEIGHT_RATIO:
        return None
    billed = priors.fulfilment_fee(tier, dim_w, price, today)
    on_weight = priors.fulfilment_fee(tier, item_w, price, today)
    if billed is None or on_weight is None:
        return None
    per_unit = round(billed - on_weight, 4)
    if per_unit < MIN_PER_UNIT_USD:
        return None
    lo, hi = _monthly(per_unit, per_unit, item.est_monthly_units)
    return Finding(
        kind="dim_weight_overage",
        dollars_low=lo, dollars_high=hi,
        confidence=0.70,
        assumptions=[
            _card_assumption(today),
            f"the packed dimensions published on your listing ({item.dims_in[0]:g} × "
            f"{item.dims_in[1]:g} × {item.dims_in[2]:g} in) are the dimensions Amazon measures",
            f"dimensional weight at the standard divisor of {priors.DIM_DIVISOR:g}, which applies "
            f"once a parcel passes a cubic foot",
            _volume_assumption(item),
        ],
        evidence={
            "chart": "fee_vs_weight",
            "item_weight_oz": item_w, "dim_weight_oz": dim_w,
            "dims_in": list(item.dims_in), "tier": tier,
            "cubic_in": round(item.dims_in[0] * item.dims_in[1] * item.dims_in[2], 1),
            "per_unit_low": per_unit, "per_unit_high": per_unit,
            "monthly_units": item.est_monthly_units, "price": price,
            "edge": None, "your_weight_oz": dim_w,
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
    )


# -- size_tier_edge ----------------------------------------------------------------

def size_tier_edge(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """One dimension is all that stands between this and the cheaper size tier.

    Small standard is 15 × 12 × 0.75 inches and 16 ounces. A unit that clears
    the weight and misses the envelope on a single axis pays large-standard
    rates — around a dollar a unit — for a box that is a fraction of an inch
    too thick. That is a packaging change, not a product change, which is why
    it is worth an email.
    """
    dims, weight, price = item.dims_in, item.billable_weight_oz, item.price
    if not dims or not weight or not price:
        return None
    if weight > priors.SMALL_STANDARD_MAX_OZ or item.tier != "large_standard":
        return None
    over = [(i, d, lim) for i, (d, lim) in enumerate(zip(dims, priors.SMALL_STANDARD_ENVELOPE_IN))
            if d > lim]
    if len(over) != 1:
        return None
    axis, actual, limit = over[0]
    if actual / limit > MAX_ENVELOPE_OVERAGE:
        return None
    large = priors.fulfilment_fee("large_standard", weight, price, today)
    small = priors.fulfilment_fee("small_standard", weight, price, today)
    if large is None or small is None:
        return None
    per_unit = round(large - small, 4)
    if per_unit < MIN_PER_UNIT_USD:
        return None
    lo, hi = _monthly(per_unit, per_unit, item.est_monthly_units)
    return Finding(
        kind="size_tier_edge",
        dollars_low=lo, dollars_high=hi,
        confidence=0.78,
        assumptions=[
            _card_assumption(today),
            f"the dimensions published on your listing are the packed dimensions Amazon measures",
            f"Amazon's small-standard envelope: {priors.SMALL_STANDARD_ENVELOPE_IN[0]:g} × "
            f"{priors.SMALL_STANDARD_ENVELOPE_IN[1]:g} × "
            f"{priors.SMALL_STANDARD_ENVELOPE_IN[2]:g} in and "
            f"{priors.SMALL_STANDARD_MAX_OZ} oz",
            _volume_assumption(item),
        ],
        evidence={
            "chart": "size_tier",
            "axis": AXES[axis], "actual_in": actual, "limit_in": limit,
            "over_by_in": round(actual - limit, 3),
            "dims_in": list(dims), "weight_oz": weight,
            "small_fee": small, "large_fee": large,
            "per_unit_low": per_unit, "per_unit_high": per_unit,
            "monthly_units": item.est_monthly_units, "price": price,
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
    )


# -- price_cut_no_rank_gain (history) ----------------------------------------------

MIN_HISTORY_DAYS = 14       # under a fortnight cannot tell a cut from a lightning deal
MIN_PRICE_CUT = 0.05        # 5% — below this is repricer noise
MIN_RANK_GAIN = 0.10        # a cut that moved rank 10% did buy something


def price_cut_no_rank_gain(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """A price cut that bought no rank. Margin given away for nothing.

    COLD_ENGINE.md §2 names this detector first, and specifies Keepa for the
    history it needs. There is no Keepa subscription, so the history comes from
    the harvest's own repeat reads: the crawl passes the same best-selling
    listings twice a day and, since the observations table exists, keeps what
    it saw instead of overwriting it. Until a listing has been seen twice more
    than a fortnight apart this returns nothing, which is correct — a week of
    prices cannot tell a price cut from a lightning deal.
    """
    hist = [h for h in item.history if h.price]
    if len(hist) < 2 or not item.price:
        return None
    first, last = hist[0], hist[-1]
    span_days = (last.seen_on - first.seen_on).days
    if span_days < MIN_HISTORY_DAYS:
        return None
    if not first.price or last.price >= first.price * (1 - MIN_PRICE_CUT):
        return None
    if first.rank and last.rank and last.rank <= first.rank * (1 - MIN_RANK_GAIN):
        return None                                     # the cut did buy rank; not a finding
    per_unit = round(first.price - last.price, 4)
    rate = priors.referral_rate(item.category)
    per_unit = round(per_unit * (1 - rate), 4)          # the referral fee falls with the price too
    lo, hi = _monthly(per_unit, per_unit, item.est_monthly_units)
    return Finding(
        kind="price_cut_no_rank_gain",
        dollars_low=lo, dollars_high=hi,
        confidence=0.75,
        assumptions=[
            f"prices and sales rank read off your public listing on {first.seen_on} and "
            f"{last.seen_on}, {span_days} days apart",
            f"a {rate:.0%} referral fee, so the margin given up is net of Amazon's cut",
            _volume_assumption(item),
        ],
        evidence={
            "chart": "price_vs_rank",
            "series": [{"date": h.seen_on.isoformat(), "price": h.price, "rank": h.rank}
                       for h in hist],
            "from_price": first.price, "to_price": last.price,
            "from_rank": first.rank, "to_rank": last.rank, "span_days": span_days,
            "per_unit_low": per_unit, "per_unit_high": per_unit,
            "monthly_units": item.est_monthly_units,
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
    )


# -- the Shopify lane --------------------------------------------------------------

def carrier_band_edge(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """A Shopify parcel over a pound, priced off the USPS Ground Advantage card.

    USPS rounds anything over a pound up to the next whole pound, so a product
    at 16.5 oz is billed at two pounds while the same product at 15.9 oz is
    billed at the flat sub-pound rate. That is the largest single step on the
    card and the only one a brand can cross by trimming packaging.

    The figure is a range across zones 1 to 8 rather than a point, because a
    brand's zone mix is not public and guessing at it would be the one thing
    worth refusing. The low end is what a local shipper saves and the high end
    what a coast-to-coast one does, and the copy says exactly that.

    Before 2026-07-12 this also fired on the 4, 8 and 12 oz tiers. USPS
    collapsed them into one flat rate that day, so those edges are gone from
    harvest/shopify.py and cannot be quoted from anywhere.
    """
    weight = item.billable_weight_oz
    if not weight:
        return None
    cliff = shopify_harvest.shipping_cliff(weight)
    if not cliff:
        return None
    edge, over_by = cliff
    if over_by > MAX_SHAVEABLE_CARRIER_OZ:
        # Twelve ounces into the two-pound band is not a packaging change, it is
        # a different product. True, useless, and it reads as a machine talking.
        return None
    below, above = shopify_harvest.band_names(edge)
    priced = priors.CARRIER_GROUND_USD.get(edge)
    if not priced:
        # An edge the card holds no row for. Stated, never priced, and `select`
        # refuses an unpriced finding — so nothing is sent about it.
        per_unit_low, per_unit_high = 0.0, 0.0
    else:
        per_unit_low, per_unit_high = priced
    lo, hi = _monthly(per_unit_low, per_unit_high, item.est_monthly_units)
    assumptions = [
        f"the shipping weight set on your own product ({weight:g} oz) — the one Shopify hands "
        f"the carrier at checkout, so it is what gets billed rather than an estimate of it; "
        f"a carrier still bills the greater of that and dimensional weight",
        f"USPS rounds anything over {edge} oz up to {above}, so trimming {over_by:g} oz moves "
        f"every parcel to the {below} rate",
    ]
    if priced:
        assumptions += [
            f"{priors.CARRIER_SOURCE}",
            f"a range across zones 1 to 8, because your zone mix is not public: "
            f"${per_unit_low:,.2f} a parcel to the nearest zones and ${per_unit_high:,.2f} to "
            f"the farthest",
        ]
    else:
        assumptions.append("no rate card row for this weight, so this finding carries no "
                           "dollar figure and is not sent")
    return Finding(
        kind="carrier_band_edge",
        dollars_low=lo, dollars_high=hi,
        confidence=0.74 if priced else 0.55,
        assumptions=assumptions,
        evidence={
            "chart": "carrier_bands",
            "edge": edge, "your_weight_oz": weight, "over_by_oz": over_by,
            "band_below": below, "band_above": above,
            "per_unit_low": per_unit_low, "per_unit_high": per_unit_high,
            "monthly_units": item.est_monthly_units, "price": item.price,
            "rate_card": priors.CARRIER_SOURCE if priced else None,
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
    )


# -- permanent_discount ------------------------------------------------------------

# Below this the "sale" is a rounding error on the price, not a policy.
MIN_DISCOUNT_SHARE = 0.10
# A catalogue this far marked down is not running a promotion, it is running a
# price. One product on sale is marketing; two thirds of the shelf is a habit.
CATALOGUE_DISCOUNT_SHARE = 0.5
# What it takes to call the price settled rather than currently promoted: this
# many observations of the same price, spanning at least this many days.
STABLE_OBSERVATIONS = 3
STABLE_DAYS = 14


def _catalogue_discount_share(snap: ProspectSnapshot) -> float | None:
    """How much of the shelf is listed under its own anchor."""
    priced = [i for i in snap.items if i.price]
    if not priced:
        return None
    marked = [i for i in priced if i.discount_share]
    return round(len(marked) / len(priced), 3)


def _price_is_settled(item: Item) -> tuple[bool, int, int]:
    """-> (settled, observations at this price, days they span).

    "Permanent" is a claim about time, and time is the one thing a single
    snapshot cannot see. `harvest_product_observations` is appended on every
    pass precisely so that this can be answered later; until it can, the
    finding exists but is not confident enough to send, which is the correct
    behaviour rather than a gap.
    """
    seen = [o for o in item.history if o.price is not None]
    if len(seen) < STABLE_OBSERVATIONS:
        return False, len(seen), 0
    same = [o for o in seen if abs((o.price or 0) - (item.price or 0)) < 0.005]
    if len(same) < STABLE_OBSERVATIONS:
        return False, len(same), 0
    span = (max(o.seen_on for o in same) - min(o.seen_on for o in same)).days
    return span >= STABLE_DAYS, len(same), span


def permanent_discount(item: Item, snap: ProspectSnapshot, today: date) -> Finding | None:
    """A product listed under its own compare-at price, on a shelf where that
    is the norm rather than the exception.

    Shopify publishes both numbers, so the per-unit figure is subtraction, not
    estimation: the store says the product is worth $45 and sells it at $32,
    and the $13 is margin it has decided in advance to give away. What the
    anchor buys in return is supposed to be urgency — and an anchor that has
    been there every day for a month buys nothing, because no customer has
    ever seen the product at $45.

    Two things keep this honest. The catalogue share gate means one genuinely
    discounted product is never called a policy. And the confidence turns on
    price history: with three readings of the same price a fortnight apart the
    price is settled and we say so; without them the arithmetic is still right
    but "permanent" is not yet earned, and `select` will not send it.
    """
    share = item.discount_share
    if not share or share < MIN_DISCOUNT_SHARE:
        return None
    catalogue = _catalogue_discount_share(snap)
    if not catalogue or catalogue < CATALOGUE_DISCOUNT_SHARE:
        return None
    per_unit = round((item.compare_at_price or 0) - (item.price or 0), 2)
    if per_unit < MIN_PER_UNIT_USD:
        return None
    settled, readings, span = _price_is_settled(item)
    lo, hi = _monthly(per_unit, per_unit, item.est_monthly_units)
    assumptions = [
        f"your own two published numbers on this product: a compare-at of "
        f"${item.compare_at_price:,.2f} against a price of ${item.price:,.2f}, so the "
        f"difference is ${per_unit:,.2f} a unit and is not an estimate",
        f"{catalogue:.0%} of your published catalogue is listed below its own compare-at, "
        f"which is what makes this a price rather than a promotion",
    ]
    if settled:
        assumptions.append(
            f"this price has been the same on {readings} readings of your catalogue over "
            f"{span} days, so the anchor is not doing the job an anchor is for")
    else:
        assumptions.append(
            "we have not yet watched this price long enough to call it permanent — that "
            "takes a fortnight of readings, and this finding is held back until then")
    return Finding(
        kind="permanent_discount",
        dollars_low=lo, dollars_high=hi,
        # Below COLD_MIN_CONFIDENCE until the history earns it: the arithmetic
        # is certain, the word "permanent" is not.
        confidence=0.78 if settled else 0.55,
        assumptions=assumptions,
        evidence={
            "chart": "net_vs_price",
            "price": item.price, "compare_at": item.compare_at_price,
            "discount_share": share, "catalogue_discount_share": catalogue,
            "per_unit_low": per_unit, "per_unit_high": per_unit,
            "readings": readings, "days_observed": span, "settled": settled,
            "monthly_units": item.est_monthly_units,
        },
        asin_or_sku=item.ref, item_title=item.title, item_url=item.url,
    )


AMAZON_DETECTORS = (price_band_edge, fee_band_edge, dim_weight_overage, size_tier_edge,
                    price_cut_no_rank_gain)
SHOPIFY_DETECTORS = (carrier_band_edge, permanent_discount, price_cut_no_rank_gain)


def detect(snap: ProspectSnapshot, today: date | None = None) -> list[Finding]:
    """Every finding this snapshot supports, best first.

    Ordered by expected value — confidence times the middle of the dollar range —
    so the caller sees the strongest claim first even before `select` runs.
    """
    today = today or date.today()
    if snap.platform == "shopify":
        detectors = SHOPIFY_DETECTORS
    else:
        if priors.stale(today):
            return []          # off the rate card's window: price nothing
        detectors = AMAZON_DETECTORS
    out: list[Finding] = []
    for item in snap.items:
        for detector in detectors:
            found = detector(item, snap, today)
            if found is not None:
                out.append(found)
    out.sort(key=lambda f: -(f.confidence * ((f.dollars_low + f.dollars_high) / 2
                                             or f.per_unit_high)))
    return out
