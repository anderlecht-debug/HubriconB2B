"""The rate cards and priors the cold engine prices a finding with.

Everything a cold finding claims in dollars comes from this file, and every
number in it is a *published* rate that the prospect can look up themselves.
That is the whole point: a stranger will not take our word for a figure, but
they will take Amazon's.

Two rules, both load-bearing:

1. **Nothing here is a guess.** Where a value would have to be estimated, it is
   absent and the detector that needed it returns nothing. A missing rate card
   costs us a send; a wrong one costs us the channel (COLD_ENGINE.md §0).
2. **Every table carries its effective window and its source.** Amazon reprices
   yearly and USPS more often than that. `stale()` says so out loud, and
   `hubricon teardown ratecard` prints the whole card beside the URL so the
   check takes two minutes.
"""

from __future__ import annotations

from datetime import date

from .. import calibration

# -- Amazon: US FBA fulfilment fees ------------------------------------------------
#
# The 2026 schedule prices every band three times, by the item's *sale price*:
# under $10 (the Low-Price FBA rates, applied automatically), $10–$50, over $50.
# That third dimension is new and it is where `price_band_edge` comes from — a
# listing at $10.20 pays roughly ninety cents more per unit than the same
# listing at $9.99.
#
# Source: Amazon's 2026 US FBA fulfilment fee schedule, non-peak window.
#         sellercentral.amazon.com → Fulfilment by Amazon fees → US
#         Cross-checked against two published reproductions of the same card
#         (warehousingcosts.com, goatconsulting.com) which agree to the cent.
FBA_SOURCE = "Amazon US FBA fulfilment fees, 2026 non-peak schedule"
FBA_EFFECTIVE = date(2026, 1, 15)
FBA_THROUGH = date(2026, 10, 14)   # the peak card below takes over on 15 Oct

# A 3.5% fuel and logistics surcharge applies to every US FBA fulfilment fee
# from 2026-04-17. It scales both sides of a band comparison, so it changes a
# delta by three and a half percent — small, but it is real money and it is
# published, so it is applied rather than ignored.
FUEL_SURCHARGE = 0.035
FUEL_SURCHARGE_FROM = date(2026, 4, 17)

PRICE_BANDS = ("low", "mid", "high")          # < $10, $10–$50, > $50
PRICE_BAND_EDGES = (10.0, 50.0)

# (upper edge of the band in oz, fee at each price band). A unit's band is the
# first row whose edge it does not exceed.
SMALL_STANDARD_OZ = (
    (2,  (2.43, 3.32, 3.58)),
    (4,  (2.49, 3.42, 3.68)),
    (6,  (2.56, 3.45, 3.71)),
    (8,  (2.66, 3.54, 3.80)),
    (10, (2.77, 3.68, 3.94)),
    (12, (2.82, 3.78, 4.04)),
    (14, (2.92, 3.91, 4.17)),
    (16, (2.95, 3.96, 4.22)),
)
LARGE_STANDARD_OZ = (
    (4,  (2.91, 3.73, 3.99)),
    (8,  (3.13, 3.95, 4.21)),
    (12, (3.38, 4.20, 4.46)),
    (16, (3.78, 4.60, 4.86)),
    (20, (4.22, 5.04, 5.30)),
    (24, (4.60, 5.42, 5.68)),
    (28, (4.75, 5.57, 5.83)),
    (32, (5.00, 5.82, 6.08)),
    (36, (5.10, 5.92, 6.18)),
    (40, (5.28, 6.10, 6.36)),
    (44, (5.44, 6.26, 6.52)),
    (48, (5.85, 6.67, 6.93)),
)
# Above 3 lb and up to 20 lb, large standard is a base plus a linear rate.
LARGE_STANDARD_OVER_3LB_BASE = (6.15, 6.97, 7.23)
LARGE_STANDARD_OVER_3LB_PER_4OZ = 0.08

# -- the holiday peak card, 15 Oct 2026 – 14 Jan 2027 -------------------------------
#
# Same bands, same three price columns, dearer by $0.19–$0.54 a unit on the
# standard tiers (Amazon quotes the average increase as $0.32). Loaded on
# 2026-09-08 so the engine keeps pricing through Q4 instead of going dark on
# 15 October, and so the 60-second Teardown can tell a seller what the switch
# costs their exact unit before it happens.
#
# Source: Amazon's 2026 US holiday peak fulfilment fee schedule, reproduced at
#         amzprep.com/holiday-peak-fulfillment-fees (full table) and
#         cross-checked against Amazon's own worked example quoted by
#         forestshipping.com (small standard 2–4 oz under $10: $2.49 → $2.68,
#         which is this table's row exactly). Verify the rest against Seller
#         Central before 15 October; the per-4-oz step above 3 lb is assumed
#         unchanged at $0.08 because no reproduction prints it.
PEAK_SOURCE = "Amazon US FBA fulfilment fees, 2026 holiday peak schedule"
PEAK_EFFECTIVE = date(2026, 10, 15)
PEAK_THROUGH = date(2027, 1, 14)
SMALL_STANDARD_PEAK_OZ = (
    (2,  (2.62, 3.51, 3.77)),
    (4,  (2.68, 3.61, 3.87)),
    (6,  (2.76, 3.65, 3.91)),
    (8,  (2.86, 3.74, 4.00)),
    (10, (2.98, 3.89, 4.15)),
    (12, (3.03, 3.99, 4.25)),
    (14, (3.14, 4.13, 4.39)),
    (16, (3.17, 4.18, 4.44)),
)
LARGE_STANDARD_PEAK_OZ = (
    (4,  (3.15, 3.97, 4.23)),
    (8,  (3.39, 4.21, 4.47)),
    (12, (3.66, 4.48, 4.74)),
    (16, (4.07, 4.89, 5.15)),
    (20, (4.52, 5.34, 5.60)),
    (24, (4.91, 5.73, 5.99)),
    (28, (5.07, 5.89, 6.15)),
    (32, (5.33, 6.15, 6.41)),
    (36, (5.47, 6.29, 6.55)),
    (40, (5.67, 6.49, 6.75)),
    (44, (5.84, 6.66, 6.92)),
    (48, (6.26, 7.08, 7.34)),
)
LARGE_STANDARD_PEAK_OVER_3LB_BASE = (6.69, 7.51, 7.77)


class Card:
    """One FBA fee schedule with the window it is in force for."""
    __slots__ = ("name", "source", "effective", "through", "small", "large", "over_3lb_base")

    def __init__(self, name, source, effective, through, small, large, over_3lb_base):
        self.name, self.source, self.effective, self.through = name, source, effective, through
        self.small, self.large, self.over_3lb_base = small, large, over_3lb_base


CARDS = (
    Card("non_peak", FBA_SOURCE, FBA_EFFECTIVE, FBA_THROUGH,
         SMALL_STANDARD_OZ, LARGE_STANDARD_OZ, LARGE_STANDARD_OVER_3LB_BASE),
    Card("peak", PEAK_SOURCE, PEAK_EFFECTIVE, PEAK_THROUGH,
         SMALL_STANDARD_PEAK_OZ, LARGE_STANDARD_PEAK_OZ, LARGE_STANDARD_PEAK_OVER_3LB_BASE),
)


def card_for(today: date | None = None) -> Card | None:
    """The schedule in force on a day, or None when no loaded card covers it."""
    today = today or date.today()
    for card in CARDS:
        if card.effective <= today <= card.through:
            return card
    return None


def card_named(name: str) -> Card:
    for card in CARDS:
        if card.name == name:
            return card
    raise KeyError(name)

# Size tiers are decided on the *packed* dimensions and the shipping weight.
# Crossing an envelope is the expensive move: a unit that leaves small standard
# for large standard pays about a dollar more, which dwarfs any weight band
# inside a tier.
SMALL_STANDARD_MAX_OZ = 16
SMALL_STANDARD_ENVELOPE_IN = (15.0, 12.0, 0.75)    # longest, median, shortest
LARGE_STANDARD_MAX_OZ = 20 * 16
LARGE_STANDARD_ENVELOPE_IN = (18.0, 14.0, 8.0)

# Amazon bills the greater of unit weight and dimensional weight, and computes
# dimensional weight the way the ground carriers do: cubic inches over 139.
# Applied to standard-size units above one cubic foot and to everything larger.
DIM_DIVISOR = 139.0
DIM_WEIGHT_MIN_CUFT = 1.0

# Referral fee. 15% covers most of the categories the harvest crawls; the
# exceptions below are the ones it actually meets. A category we do not hold a
# rate for falls back to the default, and any finding that leans on the
# referral rate says which rate it used.
REFERRAL_DEFAULT = 0.15
REFERRAL_MIN_USD = 0.30
REFERRAL_BY_CATEGORY = {
    "grocery & gourmet food": 0.08,      # 8% under $15, 15% above; the low rate is the safe one
    "health & household": 0.15,
    "beauty & personal care": 0.15,
    "home & kitchen": 0.15,
    "kitchen & dining": 0.15,
    "pet supplies": 0.15,
    "baby": 0.15,
    "toys & games": 0.15,
    "sports & outdoors": 0.15,
    "patio, lawn & garden": 0.15,
    "arts, crafts & sewing": 0.15,
    "office products": 0.15,
    "industrial & scientific": 0.12,
    "tools & home improvement": 0.15,
    "automotive": 0.12,
    "musical instruments": 0.15,
    "electronics": 0.08,
    "cell phones & accessories": 0.08,
}

# -- Shopify: USPS Ground Advantage -------------------------------------------------
#
# Source: USPS Postal Explorer, Notice 123 Price List, Ground Advantage
#         Commercial prices, effective 2026-07-12. Zone 8 cross-checked against
#         two independent published reproductions, which agree to the cent.
#         Commercial rather than Retail because that is what a brand buying
#         labels through Shopify Shipping or Pirate Ship actually pays; Retail
#         is roughly two to four dollars dearer and would overstate every claim.
#
# **The ounce tiers are gone.** Until 2026-07-12 Ground Advantage priced 4, 8,
# 12 and 15.999 oz separately, and this repo's Shopify hook was built on that
# ladder. USPS collapsed all four into one: at published Commercial rates every
# parcel under a pound now costs the same within a zone, whatever it weighs. So
# "your product is 1.5 oz over the 8 oz band" stopped being true that day, and
# harvest/shopify.py no longer emits those edges.
#
# What survives is the pound boundary, and it is much larger than any ounce tier
# ever was, because USPS rounds anything over a pound up to the next whole
# pound. A parcel at 16.5 oz is billed at two pounds; the same parcel at 15.9 oz
# is billed at the flat sub-pound rate. The step below is measured between those
# two, which is what a brand would actually save by trimming the ounce.
#
#     under 1 lb   6.93  6.94  7.30  7.46  7.69  7.86  8.07  8.40   (zones 1-8)
#     1 lb         7.61  7.68  8.00  8.15  8.74  9.63  9.98 10.67
#     2 lb         7.99  8.08  8.26  8.51  9.95 11.58 12.00 12.87
#     3 lb         8.64  8.66  9.14  9.67 11.57 13.59 14.36 15.75
#
# The range at each edge is the spread across those eight zones. It is wide
# because a brand's zone mix is not public and we will not guess at it: the low
# end is what a purely local shipper saves and the high end what a coast-to-coast
# one does. The copy says exactly that.
CARRIER_SOURCE = ("USPS Ground Advantage Commercial prices, Notice 123, effective 2026-07-12 "
                  "(pe.usps.com)")
CARRIER_EFFECTIVE: date | None = date(2026, 7, 12)
CARRIER_ZONES = (1, 2, 3, 4, 5, 6, 7, 8)

# The card itself, keyed by the ounce weight a parcel is billed *at*. 0 is the
# flat sub-pound rate; 16 is the exactly-one-pound rate that only a 16.000 oz
# parcel ever pays; 32 and 48 are what a parcel over one and over two pounds
# rounds up to. Kept as the published rows rather than as deltas so the teardown
# page can draw the seller the actual card.
CARRIER_GROUND_COMMERCIAL: dict[int, list[float]] = {
    0:  [6.93, 6.94, 7.30, 7.46, 7.69, 7.86, 8.07, 8.40],
    16: [7.61, 7.68, 8.00, 8.15, 8.74, 9.63, 9.98, 10.67],
    32: [7.99, 8.08, 8.26, 8.51, 9.95, 11.58, 12.00, 12.87],
    48: [8.64, 8.66, 9.14, 9.67, 11.57, 13.59, 14.36, 15.75],
}


def carrier_rows(edge_oz: int) -> tuple[list[float], list[float]] | None:
    """(what it pays now, what it would pay under the edge) across zones 1-8.

    The round-up is the whole point: a parcel over `edge_oz` bills at the *next*
    pound, and its realistic alternative is the band below the edge — for the
    16 oz edge that is the flat sub-pound rate, not the one-pound rate a
    16.000 oz parcel would pay.
    """
    now = CARRIER_GROUND_COMMERCIAL.get(edge_oz + 16)
    under = CARRIER_GROUND_COMMERCIAL.get(0 if edge_oz == 16 else edge_oz)
    return (now, under) if now and under else None


def _carrier_steps() -> dict[int, tuple[float, float]]:
    out = {}
    # Only real band edges. 0 is a row of the card, not somewhere a parcel can
    # sit above, and shipping_cliff never emits it.
    for edge in (e for e in CARRIER_GROUND_COMMERCIAL if e >= 16):
        rows = carrier_rows(edge)
        if not rows:
            continue
        steps = [round(a - b, 2) for a, b in zip(*rows)]
        out[edge] = (min(steps), max(steps))
    return out


# band edge oz -> (saving per parcel in the nearest zone, in the farthest).
# Derived, so the card above stays the single place a figure is edited. An edge
# with no row — 48 oz and up, which needs the 4 lb row — is absent, stays
# unpriced, and select refuses to send an unpriced finding.
CARRIER_GROUND_USD: dict[int, tuple[float, float]] = _carrier_steps()


def stale(today: date | None = None) -> str | None:
    """Plain English if no loaded Amazon card covers the day."""
    today = today or date.today()
    if card_for(today) is not None:
        return None
    first, last = CARDS[0], CARDS[-1]
    if today < first.effective:
        return f"the FBA rate card starts {first.effective}; today is {today}"
    return (f"the loaded FBA rate cards end {last.through} and today is {today}. "
            f"Amazon's next schedule must be read into priors.py before anything is priced.")


def price_band(price: float | None) -> int | None:
    """Which of the three fee columns a sale price falls in, or None."""
    if price is None or price <= 0:
        return None
    if price < PRICE_BAND_EDGES[0]:
        return 0
    if price <= PRICE_BAND_EDGES[1]:
        return 1
    return 2


def referral_rate(category: str | None) -> float:
    """The published rate for the category — or, where consenting clients'
    own fee lines have been read, the rate Amazon actually charged them
    (calibration.py). The finding says which it used."""
    cat = (category or "").strip().lower()
    learned = calibration.get(f"amazon.referral_rate.{cat}")
    if learned is not None:
        return float(learned)
    return REFERRAL_BY_CATEGORY.get(cat, REFERRAL_DEFAULT)


def _surcharged(fee: float, today: date) -> float:
    return round(fee * (1 + FUEL_SURCHARGE), 4) if today >= FUEL_SURCHARGE_FROM else round(fee, 4)


def fulfilment_fee(tier: str, weight_oz: float, price: float | None,
                   today: date | None = None, card: Card | None = None) -> float | None:
    """$ per unit Amazon charges to fulfil one of these, or None off the card.

    `tier` is 'small_standard' or 'large_standard'; anything bigger is off this
    card and returns None rather than a plausible number. The card is the one
    in force on `today` unless one is passed — the 60-second Teardown prices
    the same unit on both cards to show what 15 October costs.
    """
    today = today or date.today()
    card = card or card_for(today)
    band = price_band(price)
    if card is None or band is None or weight_oz is None or weight_oz <= 0:
        return None
    if tier == "small_standard":
        if weight_oz > SMALL_STANDARD_MAX_OZ:
            return None
        for edge, fees in card.small:
            if weight_oz <= edge:
                return _surcharged(fees[band], today)
        return None
    if tier == "large_standard":
        if weight_oz > LARGE_STANDARD_MAX_OZ:
            return None
        for edge, fees in card.large:
            if weight_oz <= edge:
                return _surcharged(fees[band], today)
        over_4oz_steps = -(-(weight_oz - 48) // 4)          # ceil: part of a step bills whole
        fee = card.over_3lb_base[band] + LARGE_STANDARD_OVER_3LB_PER_4OZ * over_4oz_steps
        return _surcharged(fee, today)
    return None


def ratecard_dict(today: date | None = None) -> dict:
    """Every published figure the engine prices with, as plain data.

    Written to /ratecard.json by `hubricon teardown ratecard --json` so the
    60-second Teardown in the browser prices a unit off exactly this table.
    The JSON is generated, never edited: this file stays the single source.
    """
    from ..harvest import amazon as harvest_amazon
    today = today or date.today()
    fba = {
        "cards": {
            c.name: {
                "source": c.source, "effective": c.effective.isoformat(),
                "through": c.through.isoformat(),
                "small_standard": [[e, list(f)] for e, f in c.small],
                "large_standard": [[e, list(f)] for e, f in c.large],
                "over_3lb_base": list(c.over_3lb_base),
                "over_3lb_per_4oz": LARGE_STANDARD_OVER_3LB_PER_4OZ,
            } for c in CARDS
        },
        "fuel_surcharge": FUEL_SURCHARGE, "fuel_surcharge_from": FUEL_SURCHARGE_FROM.isoformat(),
        "price_band_edges": list(PRICE_BAND_EDGES),
        "small_standard_max_oz": SMALL_STANDARD_MAX_OZ,
        "small_standard_envelope_in": list(SMALL_STANDARD_ENVELOPE_IN),
        "large_standard_max_oz": LARGE_STANDARD_MAX_OZ,
        "large_standard_envelope_in": list(LARGE_STANDARD_ENVELOPE_IN),
        "dim_divisor": DIM_DIVISOR, "dim_weight_min_cuft": DIM_WEIGHT_MIN_CUFT,
        "referral_default": REFERRAL_DEFAULT, "referral_min_usd": REFERRAL_MIN_USD,
        "referral_by_category": dict(REFERRAL_BY_CATEGORY),
    }
    carrier = {
        "source": CARRIER_SOURCE,
        "effective": CARRIER_EFFECTIVE.isoformat() if CARRIER_EFFECTIVE else None,
        "zones": list(CARRIER_ZONES),
        "ground_commercial": {str(k): v for k, v in CARRIER_GROUND_COMMERCIAL.items()},
    }
    units = {
        "a": harvest_amazon.CURVE_A, "b": harvest_amazon.CURVE_B,
        "head_knee": harvest_amazon.HEAD_KNEE, "head_exp": harvest_amazon.HEAD_EXP,
        "category_scale": dict(harvest_amazon.CATEGORY_SCALE),
        "default_scale": harvest_amazon.DEFAULT_SCALE,
        "bracket": [0.5, 1.5],
        "note": "monthly units from a top-level category rank; a power-law fit that is wrong by "
                "a factor of two either way, so every monthly figure is a bracket",
    }
    return {"generated": today.isoformat(), "fba": fba, "carrier": carrier, "units_curve": units}


def band_edge_below(tier: str, weight_oz: float | None) -> float | None:
    """The heaviest band edge this unit is *above*, within its tier.

    None when the unit is in the tier's lightest band (nothing to shave down to)
    or off the card entirely.
    """
    if not weight_oz:
        return None
    table = SMALL_STANDARD_OZ if tier == "small_standard" else LARGE_STANDARD_OZ
    edges = [e for e, _ in table]
    if tier == "large_standard" and weight_oz > edges[-1]:
        # Above 3 lb the card is linear in 4 oz steps, so the edge below is the
        # last whole step boundary rather than a row in the table. Bands are
        # half-open — (48, 52] bills as one step — so a unit sitting exactly on
        # a boundary belongs to the band below it, like every table row does.
        steps = -(-(weight_oz - 48) // 4)                  # ceil
        return 48.0 + 4 * (steps - 1)
    below = [e for e in edges if e < weight_oz]
    return float(max(below)) if below else None
