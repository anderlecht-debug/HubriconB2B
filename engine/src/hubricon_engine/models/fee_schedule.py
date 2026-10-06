"""Amazon FBA fee schedule — the fallback rate card.

Doctrine: a client's own reports are ground truth. Where an export carries
Amazon's estimate (the Inventory Age report's estimated storage cost and
aged-inventory surcharge columns, the fee lines in a settlement file) the
models use it. These constants exist only so a number can still be
computed on day one, and every figure derived from them is labeled
"schedule estimate" in the payload so the Desk never presents a fallback
as a fact.

Figures are the US marketplace schedule in force 2026-01-15 (aged
surcharge and low-inventory fee; the low-inventory fee's size tiers re-read
2026-10-01, see below) and the Oct–Dec peak storage rates.
Amazon moves these roughly yearly; the EFFECTIVE date is surfaced so a
stale schedule is visible, not silent.
"""

from datetime import date

EFFECTIVE = "2026-01-15"

# monthly storage, $ per cubic foot
STORAGE_PER_CUFT = {
    "standard": {"offpeak": 0.78, "peak": 2.40},
    "oversize": {"offpeak": 0.56, "peak": 1.40},
}
PEAK_MONTHS = (10, 11, 12)

# aged-inventory surcharge, $ per cubic foot per month, by age bucket (days)
AGED_SURCHARGE_PER_CUFT = (
    (181, 210, 0.50),
    (211, 240, 1.00),
    (241, 270, 1.50),
    (271, 300, 5.45),
    (301, 330, 5.70),
    (331, 365, 5.90),
    (366, 10**6, 6.90),
)
AGED_SURCHARGE_MIN_PER_UNIT_365_PLUS = 0.15   # whichever is greater, 365+ tier

# Low-inventory-level fee, $ per unit shipped, by historical days of supply
# under 14 / 14–21 / 21–28. Re-read 2026-10-01, by size tier (until then the
# engine priced every standard item at the small-standard row, and oversize at
# 2.09/1.14/0.72).
#   The standard rows are Amazon's, corroborated on 2026-10-01 by a research
#   pass over Amazon's fee page and two third-party guides. The bulky rows are
#   from Amazon's page as that pass read it, corroborated 2026-10-04 by three
#   third-party 2026 guides (SellerMagnet, FBA Tactics, PrepVia), two giving the
#   rows and all three that bulky items are charged from January 15, 2026;
#   Amazon's own page not re-read (Seller Central needs a sign-in, and Amazon
#   refuses automated reads). Open: one guide says extra-large items are outside
#   the fee, and an extra-large item also reads "oversize" in Inventory Age, so
#   LOW_INVENTORY_ASSUMED_TIER may overstate it; confirm on Amazon's page or a
#   client's Fee Preview before changing anything.
#   The rule: the fee applies only when BOTH the 30-day and the 90-day
#   historical days of supply are under 28; the higher of the two sets the
#   band; it is measured per FNSKU. Exempt: fewer than 20 units shipped in the
#   past 7 days; new Professional sellers for 365 days; FBA New Selection
#   parents for 180 days; SKUs at least 70% auto-replenished through AWD;
#   Grocery. inventory_econ applies the exemptions an export can show and names
#   the rest.
#   NOT modelled: the storage utilization surcharge ($0.44–$1.88 per cubic foot
#   on stock past 30 days, for accounts more than 365 days old holding at least
#   25 cu ft with more than 22 weeks of supply). No figure here includes it.
LOW_INVENTORY_FEE_PER_UNIT = {
    "small_standard": {"lt14": 0.89, "14to21": 0.63, "21to28": 0.32},
    "large_standard_3lb": {"lt14": 0.97, "14to21": 0.70, "21to28": 0.36},     # large standard, up to 3 lb
    "large_standard_20lb": {"lt14": 1.11, "14to21": 0.87, "21to28": 0.47},    # large standard, 3 to 20 lb
    "small_bulky": {"lt14": 1.85, "14to21": 1.02, "21to28": 0.51},            # bulky: least certain, see above
    "large_bulky": {"lt14": 2.09, "14to21": 1.15, "21to28": 0.57},
}
LOW_INVENTORY_TIER_LABEL = {
    "small_standard": "small standard", "large_standard_3lb": "large standard, up to 3 lb",
    "large_standard_20lb": "large standard, 3 to 20 lb", "small_bulky": "small bulky", "large_bulky": "large bulky",
}
# When an export says only "standard" or "oversize" (Inventory Age's storage
# type), each takes the lowest row of its kind, so an assumed tier never
# overstates the fee: small standard, and small bulky (oversize was priced at
# 2.09/1.14/0.72 until 2026-10-01).
LOW_INVENTORY_ASSUMED_TIER = {"standard": "small_standard", "oversize": "small_bulky"}
LOW_INVENTORY_DAYS_THRESHOLD = 28
LOW_INVENTORY_MIN_UNITS_T7 = 20            # fewer shipped in the past 7 days: exempt
LARGE_STANDARD_SPLIT_LB = 3.0

# referral fee: category-based, 15% for most categories; minimum $0.30/unit
REFERRAL_RATE_DEFAULT = 0.15
REFERRAL_MIN_PER_UNIT = 0.30

# per-unit storage volume when the inventory-age export is not on file
DEFAULT_ITEM_VOLUME_CUFT = {"standard": 0.08, "oversize": 1.20}

IPI_STORAGE_LIMIT_THRESHOLD = 400


def storage_rate(month: int, size_tier: str = "standard") -> float:
    tier = STORAGE_PER_CUFT.get(size_tier, STORAGE_PER_CUFT["standard"])
    return tier["peak"] if month in PEAK_MONTHS else tier["offpeak"]


def aged_surcharge_rate(age_days: int) -> float:
    """$ per cubic foot per month for a unit of the given age; 0 under 181."""
    for lo, hi, rate in AGED_SURCHARGE_PER_CUFT:
        if lo <= age_days <= hi:
            return rate
    return 0.0


def low_inventory_tier(size_tier: str | None, weight_lb: float | None = None) -> tuple[str | None, str]:
    """The low-inventory schedule row for a size tier as an export names it,
    and the basis to print beside the figure.

    `size_tier` is Fee Preview's product-size-tier ("Small standard", "Large
    standard", "Small bulky", "Large bulky", "Extra-large …", the older
    "… oversize" names) or Inventory Age's storage type ("Standard-Size",
    "Oversize"); `weight_lb` splits large standard at 3 lb. A large-standard
    item with no weight takes the up-to-3-lb row, the lower one. Extra-large
    has no row in the schedule and is not priced: (None, basis)."""
    s = " ".join(str(size_tier or "").lower().replace("-", " ").replace("_", " ").split())
    if not s or s in ("standard", "standard size"):
        tier = LOW_INVENTORY_ASSUMED_TIER["standard"]
        return tier, f"size tier assumed ({LOW_INVENTORY_TIER_LABEL[tier]})"
    if "extra" in s or "special" in s:
        return None, "extra-large: no low-inventory rate in the schedule, not priced"
    if "small" in s and "standard" in s:
        return "small_standard", "size tier from your export (small standard)"
    if "large" in s and "standard" in s:
        if weight_lb is None:
            return "large_standard_3lb", "size tier from your export (large standard); weight not on file, so the up-to-3 lb row"
        tier = "large_standard_3lb" if float(weight_lb) <= LARGE_STANDARD_SPLIT_LB else "large_standard_20lb"
        return tier, f"size tier from your export ({LOW_INVENTORY_TIER_LABEL[tier]})"
    if "bulky" in s:
        tier = "small_bulky" if "small" in s else "large_bulky"
        return tier, f"size tier from your export ({LOW_INVENTORY_TIER_LABEL[tier]}; bulky rates least certain)"
    if "over" in s:
        tier = LOW_INVENTORY_ASSUMED_TIER["oversize"]
        return tier, f"size tier assumed ({LOW_INVENTORY_TIER_LABEL[tier]}; your export says oversize)"
    tier = LOW_INVENTORY_ASSUMED_TIER["standard"]
    return tier, f"size tier assumed ({LOW_INVENTORY_TIER_LABEL[tier]}; your export says {size_tier!s})"


def low_inventory_fee(days_of_supply: float, size_tier: str | None = "standard") -> float:
    """$ per unit shipped while the low-inventory-level fee applies.

    `days_of_supply` is the figure that sets the band: the higher of the 30-
    and 90-day historical days of supply (low_inventory_band_days). `size_tier`
    is a schedule row, or "standard"/"oversize" (their assumed rows); None — a
    tier with no row, extra-large — is 0."""
    if days_of_supply is None or days_of_supply >= LOW_INVENTORY_DAYS_THRESHOLD or size_tier is None:
        return 0.0
    row = LOW_INVENTORY_ASSUMED_TIER.get(size_tier, size_tier)
    tier = LOW_INVENTORY_FEE_PER_UNIT.get(row, LOW_INVENTORY_FEE_PER_UNIT[LOW_INVENTORY_ASSUMED_TIER["standard"]])
    if days_of_supply < 14:
        return tier["lt14"]
    if days_of_supply < 21:
        return tier["14to21"]
    return tier["21to28"]


def low_inventory_band_days(dos_30: float | None, dos_90: float | None) -> float | None:
    """The days of supply that set the band: the higher of the 30- and 90-day
    historical figures, since the fee needs both under 28. One of them alone
    stands for both; neither is None."""
    known = [float(d) for d in (dos_30, dos_90) if d is not None]
    return max(known) if known else None


def months_until_peak(today: date) -> int:
    return 0 if today.month in PEAK_MONTHS else (PEAK_MONTHS[0] - today.month) % 12
