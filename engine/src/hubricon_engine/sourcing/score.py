"""The qualification gate. This is the constraint, not discovery.

Domains are effectively free and effectively unlimited. Domains that do $3M+
and where a $6,000/month decision can actually be reached are the job. So the
score runs before contact resolution and before anything is written to, and
only what clears the threshold costs a request more.

Every signal here is free, and each one is a proxy for the same hidden number:

    tranco rank      traffic, which is the closest free thing to revenue
    stack weight     monthly software invoices, which only real budgets sign
    catalogue        15-300 coherent SKUs is a brand; 800 unrelated is a dropshipper
    price point      a median under $15 does not support a $6k/month engagement
    plus             $2,300/month floor, so a positive is strong (absence proves nothing)
    velocity         a dead store looks dead
    review estimate  the existing harvest heuristic, kept but weighted low

`score` returns the number *and* its parts, because a score nobody can take
apart is a score nobody can fix. Every rejection names the signal that sank it.

**Calibrate before trusting it.** `calibrate()` exists because an uncalibrated
scorer produces confident garbage: hand-label a hundred stores, run it, and
read the threshold off the output rather than guessing one. Two numbers in
particular are unverified until that happens — the rank bands below, and
`HARVEST_SHOPIFY_ORDERS_PER_REVIEW` (50), which OPERATIONS.md flags as a guess
that the whole $1.5M-$40M band rides on.
"""

from __future__ import annotations

import os

from ..harvest import shopify as shopify_harvest

MIN_SCORE = float(os.environ.get("SOURCING_MIN_SCORE", "55"))

# Rank -> points. The band is a *window*, not a ladder: the ICP is $3M-$20M,
# so a store can rank too well as easily as too poorly. The first live qualify
# pass (2026-09-07) scored barnesandnoble.com at 73 and passed it, because the
# bands then read "higher is better" — a national retailer three orders of
# magnitude past the ceiling looked like the best lead on the list.
#
# There is no other size signal at this stage. `est_annual` comes from review
# counts on product pages and `qualify` does not fetch product pages, so it is
# None for every row here; the rank is carrying the whole judgement and has to
# encode both ends of the band. These edges are still the least defended
# numbers in the module: calibrate them. When the floor moved from $1M to $3M
# (2026-09-13) the weight moved up the list with it: a $3M store out-ranks a $1M
# one, so the long tail that was carrying the old floor lost points and the
# large-but-in-band tier gained a little. The shift is directional, not measured.
RANK_BANDS = (
    (5_000, -25.0),        # Amazon, Barnes & Noble. Not a prospect, an advertiser.
    (30_000, -8.0),        # a national brand, comfortably past the $20M ceiling
    (80_000, 20.0),        # large, plausibly still in band
    (250_000, 34.0),       # where a $3M-$20M US DTC brand actually ranks
    (500_000, 24.0),
    (1_000_000, 8.0),      # the long tail: mostly under the floor
)
RANK_UNKNOWN = 14.0     # the search route finds real stores Tranco never ranked

# A brand's catalogue. Under 15 is usually one product and a colourway; over
# 800 unrelated items is a dropshipper importing a supplier feed wholesale.
IDEAL_SKUS = (15, 300)
MAX_SANE_SKUS = 800

MIN_MEDIAN_PRICE = 15.0
DEAD_STORE_DAYS = 180.0


def _rank_points(rank: int | None) -> tuple[float, str]:
    if rank is None:
        return RANK_UNKNOWN, "no Tranco rank (found by search, not by rank)"
    for edge, points in RANK_BANDS:
        if rank <= edge:
            if points < 0:
                return points, f"Tranco #{rank:,} — too big for the band, not too small"
            return points, f"Tranco #{rank:,}"
    return 4.0, f"Tranco #{rank:,}, past the million mark"


def _catalog_points(count: int, vendors: dict | None) -> tuple[float, str]:
    if not count:
        return 0.0, "no published products"
    if count > MAX_SANE_SKUS:
        return -10.0, f"{count} products: a supplier feed, not a catalogue"
    low, high = IDEAL_SKUS
    if low <= count <= high:
        points, why = 14.0, f"{count} products"
    elif count < low:
        points, why = 6.0, f"only {count} products"
    else:
        points, why = 8.0, f"{count} products, past the usual brand range"
    share = (vendors or {}).get("share")
    if share and share >= shopify_harvest.DOMINANT_SHARE:
        points += 6.0
        why += f", {share:.0%} one vendor"
    elif vendors and len(vendors.get("vendors") or []) >= 3 and not vendors.get("dominant"):
        points -= 8.0
        why += f", {len(vendors['vendors'])} vendors and none dominant"
    return points, why


def _price_points(ladder: dict) -> tuple[float, str]:
    median = ladder.get("median")
    if not median:
        return 0.0, "no prices published"
    if median < MIN_MEDIAN_PRICE:
        return -8.0, f"median price ${median:,.2f}, under the ${MIN_MEDIAN_PRICE:,.0f} floor"
    if median >= 60:
        return 12.0, f"median price ${median:,.2f}"
    return 8.0, f"median price ${median:,.2f}"


def _velocity_points(velocity: dict) -> tuple[float, str]:
    since = velocity.get("days_since_update")
    if since is None:
        return 0.0, "no catalogue dates"
    if since > DEAD_STORE_DAYS:
        return -12.0, f"nothing updated in {since:,.0f} days"
    new = velocity.get("new_last_year") or 0
    if new >= 5:
        return 8.0, f"{new} new products in the last year"
    return 4.0, f"last updated {since:,.0f} days ago"


def _size_points(est_annual: float | None) -> tuple[float, str]:
    if est_annual is None:
        # Unknown never disqualifies — the same rule the harvest applies. Many
        # stores render reviews client-side and publish no count at all.
        return 0.0, "no review-based size estimate"
    status, why = shopify_harvest.classify_size(est_annual)
    return (-15.0 if status else 10.0), why


def score(prospect: dict) -> tuple[float, dict]:
    """-> (0-100ish score, parts). Parts hold each signal's points and reason."""
    parts: dict[str, dict] = {}

    def add(name: str, pair: tuple[float, str]) -> None:
        points, why = pair
        parts[name] = {"points": round(points, 2), "why": why}

    add("rank", _rank_points(prospect.get("tranco_rank")))
    stack = prospect.get("stack") or {}
    weight = stack.get("weight") or 0.0
    add("stack", (min(24.0, weight * 2.0),
                  ", ".join(stack.get("apps") or []) or "no paid apps detected"))
    add("catalog", _catalog_points(prospect.get("products") or 0, prospect.get("vendors")))
    add("price", _price_points(prospect.get("ladder") or {}))
    add("velocity", _velocity_points(prospect.get("velocity") or {}))
    add("size", _size_points(prospect.get("est_annual")))
    if stack.get("plus"):
        add("plus", (10.0, "Shopify Plus artifacts in the theme"))
    total = round(sum(p["points"] for p in parts.values()), 2)
    return total, parts


def verdict(prospect: dict, threshold: float | None = None) -> tuple[str, str, float, dict]:
    """-> (status, note, score, parts). The repo's (verdict, reason) idiom, with
    the number kept so a borderline row can be re-judged without a re-crawl."""
    total, parts = score(prospect)
    bar = MIN_SCORE if threshold is None else threshold
    worst = min(parts.items(), key=lambda kv: kv[1]["points"], default=("", {"why": ""}))
    if total < bar:
        return "disqualified", f"score {total:,.0f} under {bar:,.0f} — {worst[1]['why']}", total, parts
    best = max(parts.items(), key=lambda kv: kv[1]["points"])
    return "qualified", f"score {total:,.0f} — {best[1]['why']}", total, parts


def calibrate(labelled: list[dict], thresholds: tuple[float, ...] = (40, 45, 50, 55, 60, 65, 70)) -> str:
    """Precision and recall at each threshold, over hand-labelled stores.

    `labelled` is [{"domain", "score", "good": bool}]. Do not skip the
    labelling: a hundred stores where somebody guessed revenue from public
    signals is the only thing standing between this module and confident
    garbage, and it is an afternoon's work.
    """
    rows = [r for r in labelled if r.get("score") is not None]
    good = sum(1 for r in rows if r.get("good"))
    if not rows or not good:
        return "nothing labelled good — cannot calibrate"
    out = [f"{len(rows)} labelled stores, {good} in-ICP", "",
           f"{'threshold':>9}  {'kept':>5}  {'precision':>9}  {'recall':>7}  {'f1':>5}"]
    for bar in thresholds:
        kept = [r for r in rows if r["score"] >= bar]
        hits = sum(1 for r in kept if r.get("good"))
        precision = hits / len(kept) if kept else 0.0
        recall = hits / good
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out.append(f"{bar:>9,.0f}  {len(kept):>5}  {precision:>8.0%}  {recall:>6.0%}  {f1:>5.2f}")
    out += ["", "Set SOURCING_MIN_SCORE to the threshold whose precision you can live with.",
            "Recall is cheap here — there are always more domains — so prefer precision."]
    return "\n".join(out)
