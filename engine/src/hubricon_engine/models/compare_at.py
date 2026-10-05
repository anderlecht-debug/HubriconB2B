"""A price under its own compare-at: the arithmetic both lanes share.

Shopify publishes two numbers on every variant, a price and a compare-at
("was $45, now $32"). Before a call, cold/findings.permanent_discount reads
them off a stranger's public catalogue; after the yes,
models/shopify_findings.py reads the same two numbers off the client's own
Products export and the orders behind them. Both ask the same three
questions, so the answers live here once:

  * how far under its own anchor is the variant (`discount_share`), and is
    that far enough to be a price rather than a rounding (MIN_DISCOUNT_SHARE)
  * how much of the shelf is listed that way (`catalogue_share`)
  * has the price held long enough to call the discount permanent
    (`price_is_settled`): STABLE_OBSERVATIONS readings of the same price
    spanning at least STABLE_DAYS. The cold lane's readings are its own
    harvest passes; the client lane's are the months of their orders.

Pure functions, no I/O: the cold page and the client's first read cannot
disagree about what "below its own compare-at" means.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

# Below this the "sale" is a rounding error on the price, not a policy.
MIN_DISCOUNT_SHARE = 0.10
# A catalogue this far marked down is not running a promotion, it is running a
# price. One product on sale is marketing; two thirds of the shelf is a habit.
CATALOGUE_DISCOUNT_SHARE = 0.5
# What it takes to call the price settled rather than currently promoted: this
# many observations of the same price, spanning at least this many days.
STABLE_OBSERVATIONS = 3
STABLE_DAYS = 14
# Two readings of a published price are "the same price" within half a cent.
SAME_PRICE_USD = 0.005


def discount_share(price: float | None, compare_at: float | None) -> float | None:
    """How far under its own anchor a variant is listed, 0-1.

    None when there is no anchor, or the anchor is at or below the price —
    which is the ordinary state of a product that is not on sale."""
    if not price or not compare_at:
        return None
    if compare_at <= price:
        return None
    return round((compare_at - price) / compare_at, 4)


def per_unit_gap(price: float | None, compare_at: float | None) -> float:
    """The dollars a unit is sold under its own compare-at: subtraction of the
    store's own two published numbers, not an estimate."""
    if not price or not compare_at or compare_at <= price:
        return 0.0
    return round(float(compare_at) - float(price), 2)


def catalogue_share(pairs: Iterable[tuple[float | None, float | None]]) -> float | None:
    """Of the priced variants, the share listed under their own compare-at.
    `pairs` is (price, compare_at) per variant."""
    priced = [(p, c) for p, c in pairs if p]
    if not priced:
        return None
    marked = [1 for p, c in priced if discount_share(p, c)]
    return round(len(marked) / len(priced), 3)


def price_is_settled(price: float | None, observations: Iterable[tuple[date, float | None]],
                     tolerance: float = SAME_PRICE_USD) -> tuple[bool, int, int]:
    """-> (settled, observations at this price, days they span).

    "Permanent" is a claim about time, and time is the one thing a single
    snapshot cannot see. `observations` is (day, price) readings: the cold
    lane's harvest passes, or the months a client's orders sold the variant.
    With fewer than STABLE_OBSERVATIONS readings at today's price, or with
    those readings closer together than STABLE_DAYS, the arithmetic is still
    right but "permanent" is not yet earned."""
    seen = [(d, p) for d, p in observations if p is not None]
    if len(seen) < STABLE_OBSERVATIONS:
        return False, len(seen), 0
    same = [d for d, p in seen if abs((p or 0) - (price or 0)) < tolerance]
    if len(same) < STABLE_OBSERVATIONS:
        return False, len(same), 0
    span = (max(same) - min(same)).days
    return span >= STABLE_DAYS, len(same), span
