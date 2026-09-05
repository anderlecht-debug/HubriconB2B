"""Every knob the cold engine has, in one place, all reading the environment.

Defaults are the cautious end of each range on purpose. The two that matter
most:

  COLD_DRY_RUN            true unless someone deliberately turns it off. There
                          is no code path that sends while this is on.
  COLD_MIN_CONFIDENCE     0.70. Raising it sends less and is always safe;
                          lowering it is the only knob here that can put a
                          number we are unsure of in a stranger's inbox.
"""

from __future__ import annotations

import os


def _f(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _i(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _b(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def min_confidence() -> float:
    return _f("COLD_MIN_CONFIDENCE", 0.70)


def min_monthly_usd() -> float:
    """Below this a finding is true and not worth a stranger's attention."""
    return _f("COLD_MIN_MONTHLY_USD", 250.0)


def max_claim_share() -> float:
    """A finding may not claim more than this share of the listing's own
    estimated monthly revenue. The volume curve occasionally produces a silly
    number for a head listing, and a silly number is the one thing that cannot
    reach a prospect."""
    return _f("COLD_MAX_CLAIM_SHARE", 0.25)


def daily_budget_usd() -> float:
    return _f("COLD_DAILY_BUDGET_USD", 25.0)


def domain_daily_cap() -> int:
    return _i("COLD_DOMAIN_DAILY_CAP", 40)


def dry_run() -> bool:
    return _b("COLD_DRY_RUN", True)


def teardown_ttl_days() -> int:
    return _i("COLD_TEARDOWN_TTL_DAYS", 45)


def teardown_base_url() -> str:
    return os.environ.get("COLD_TEARDOWN_BASE_URL", "https://hubricon.com/t").rstrip("/")


def recontact_days() -> int:
    return _i("COLD_RECONTACT_DAYS", 90)


def max_touches() -> int:
    return _i("COLD_MAX_TOUCHES", 3)


def suppressed_jurisdictions() -> set[str]:
    """EU/UK prospects need a documented legitimate-interest basis we do not yet
    have (COLD_ENGINE.md §2.3, open question 3). Suppressing costs little volume
    and is the cheap answer until someone decides otherwise."""
    raw = os.environ.get("COLD_SUPPRESSED_JURISDICTIONS")
    if raw is not None:
        return {c.strip().upper() for c in raw.split(",") if c.strip()}
    return {
        "GB", "IE", "FR", "DE", "ES", "IT", "NL", "BE", "LU", "PT", "AT", "DK", "SE", "FI",
        "PL", "CZ", "SK", "HU", "RO", "BG", "HR", "SI", "EE", "LV", "LT", "GR", "CY", "MT",
        "NO", "IS", "LI", "CH",
    }
