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
FBA_THROUGH = date(2026, 10, 14)   # 15 Oct – 14 Jan is the peak card, which is dearer

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

# -- Shopify: the carrier side -----------------------------------------------------
#
# Deliberately empty. A Shopify brand's shipping cost is a zone-priced,
# often-negotiated rate, and the published USPS Ground Advantage and UPS Ground
# cards are per-zone tables this repo does not hold. Inventing a step cost to
# make the Shopify lane produce a dollar figure is exactly the failure mode
# COLD_ENGINE.md §0 names, so the Shopify detector states the billable-weight
# fact and prices nothing — which means `select` never lets it out.
#
# To turn the Shopify lane on: download the Ground Advantage retail price list
# (usps.com/business/prices.htm → Ground Advantage CSV), fill the table below
# with the zone-1–4 price for each band edge, and set CARRIER_EFFECTIVE. The
# detector picks it up with no other change.
CARRIER_SOURCE = "USPS Ground Advantage retail price list (not yet loaded)"
CARRIER_EFFECTIVE: date | None = None
CARRIER_GROUND_USD: dict[int, tuple[float, float]] = {}   # band edge oz -> (zone 1-4 low, high)


def stale(today: date | None = None) -> str | None:
    """Plain English if the Amazon card is outside the window it was priced for."""
    today = today or date.today()
    if today < FBA_EFFECTIVE:
        return f"the FBA rate card starts {FBA_EFFECTIVE}; today is {today}"
    if today > FBA_THROUGH:
        return (f"the FBA rate card covers {FBA_EFFECTIVE} to {FBA_THROUGH} and today is {today}. "
                f"Amazon's peak card (15 Oct – 14 Jan) is dearer, so every figure below it is low. "
                f"Re-read the schedule before sending anything.")
    return None


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
    return REFERRAL_BY_CATEGORY.get((category or "").strip().lower(), REFERRAL_DEFAULT)


def _surcharged(fee: float, today: date) -> float:
    return round(fee * (1 + FUEL_SURCHARGE), 4) if today >= FUEL_SURCHARGE_FROM else round(fee, 4)


def fulfilment_fee(tier: str, weight_oz: float, price: float | None,
                   today: date | None = None) -> float | None:
    """$ per unit Amazon charges to fulfil one of these, or None off the card.

    `tier` is 'small_standard' or 'large_standard'; anything bigger is off this
    card and returns None rather than a plausible number.
    """
    today = today or date.today()
    band = price_band(price)
    if band is None or weight_oz is None or weight_oz <= 0:
        return None
    if tier == "small_standard":
        if weight_oz > SMALL_STANDARD_MAX_OZ:
            return None
        for edge, fees in SMALL_STANDARD_OZ:
            if weight_oz <= edge:
                return _surcharged(fees[band], today)
        return None
    if tier == "large_standard":
        if weight_oz > LARGE_STANDARD_MAX_OZ:
            return None
        for edge, fees in LARGE_STANDARD_OZ:
            if weight_oz <= edge:
                return _surcharged(fees[band], today)
        over_4oz_steps = -(-(weight_oz - 48) // 4)          # ceil: part of a step bills whole
        fee = LARGE_STANDARD_OVER_3LB_BASE[band] + LARGE_STANDARD_OVER_3LB_PER_4OZ * over_4oz_steps
        return _surcharged(fee, today)
    return None


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
