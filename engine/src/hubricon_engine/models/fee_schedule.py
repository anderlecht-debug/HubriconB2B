"""Amazon FBA fee schedule — the fallback rate card.

Doctrine: a client's own reports are ground truth. Where an export carries
Amazon's estimate (the Inventory Age report's estimated storage cost and
aged-inventory surcharge columns, the fee lines in a settlement file) the
models use it. These constants exist only so a number can still be
computed on day one, and every figure derived from them is labeled
"schedule estimate" in the payload so the Desk never presents a fallback
as a fact.

Figures are the US marketplace schedule in force 2026-01-15 (aged
surcharge and low-inventory fee) and the Oct–Dec peak storage rates.
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

# low-inventory-level fee, $ per unit shipped, when both the 30- and 90-day
# historical days of supply are under 28 (seller-FNSKU level)
LOW_INVENTORY_FEE_PER_UNIT = {
    "standard": {"lt14": 0.89, "14to21": 0.63, "21to28": 0.32},
    "oversize": {"lt14": 2.09, "14to21": 1.14, "21to28": 0.72},
}
LOW_INVENTORY_DAYS_THRESHOLD = 28

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


def low_inventory_fee(days_of_supply: float, size_tier: str = "standard") -> float:
    """$ per unit shipped while the low-inventory-level fee applies."""
    if days_of_supply >= LOW_INVENTORY_DAYS_THRESHOLD:
        return 0.0
    tier = LOW_INVENTORY_FEE_PER_UNIT.get(size_tier, LOW_INVENTORY_FEE_PER_UNIT["standard"])
    if days_of_supply < 14:
        return tier["lt14"]
    if days_of_supply < 21:
        return tier["14to21"]
    return tier["21to28"]


def months_until_peak(today: date) -> int:
    return 0 if today.month in PEAK_MONTHS else (PEAK_MONTHS[0] - today.month) % 12
