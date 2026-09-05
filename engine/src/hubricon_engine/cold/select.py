"""Findings in, the one worth leading with out — or nothing at all.

`None` is the most common correct answer here and the module is built around
saying it. Four gates, in order, and a finding has to clear all four:

  confidence   below COLD_MIN_CONFIDENCE we do not know it well enough to say
  priced       a finding with no dollar figure is an observation, not a finding
  size         below COLD_MIN_MONTHLY_USD it is true and not worth reading — or,
               where no volume is on file and there is no monthly figure to
               judge, below COLD_MIN_PER_UNIT_ONLY_USD per unit
  plausible    a claim worth more than a quarter of the listing's own estimated
               revenue is the volume curve misbehaving, not a discovery

`review` keeps the reason each finding lost, which is the only way the gate
gets tuned: when the founder rejects a generated email, the question is always
which gate should have caught it.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import settings
from .findings import Finding
from .snapshot import ProspectSnapshot


# Why a finding lost, as a code rather than a sentence, because two different
# callers need to act on it: the founder's diagnostics read the sentence, and
# the teardown page needs to know which of the losers are still safe to print.
SHOWABLE = ("too_small", "outranked")


@dataclass(frozen=True)
class Rejection:
    finding: Finding
    code: str
    reason: str

    @property
    def showable(self) -> bool:
        """Safe to print on the page as a secondary finding.

        A finding that lost on *size* or to a *stronger sibling* is true; it
        just was not worth leading with, and on a shelf table it is useful
        context. A finding that lost on confidence or plausibility is one we do
        not stand behind, and it never appears anywhere a prospect can read it.
        """
        return self.code in SHOWABLE


@dataclass(frozen=True)
class Verdict:
    chosen: Finding | None
    rejected: list[Rejection]

    @property
    def sendable(self) -> bool:
        return self.chosen is not None

    @property
    def also(self) -> list[Finding]:
        """The runners-up the page may show beside the leading finding."""
        return [r.finding for r in self.rejected if r.showable]


def score(f: Finding) -> float:
    """Expected value: how much it is worth, discounted by how sure we are.

    Falls back to the per-unit figure when no volume is on file, which is every
    Shopify row — the harvest reads a catalogue, not a sales rank. Without the
    fallback every candidate for those prospects scores zero and the winner is
    whichever the sort happened to leave first, so the strongest finding about a
    company would be chosen by luck.
    """
    mid = (f.dollars_low + f.dollars_high) / 2
    if mid <= 0:
        mid = (f.per_unit_low + f.per_unit_high) / 2
    return f.confidence * mid


def _listing_revenue(f: Finding, snap: ProspectSnapshot) -> float | None:
    for item in snap.items:
        if item.ref == f.asin_or_sku:
            return item.est_monthly_revenue
    return None


def _reject_reason(f: Finding, snap: ProspectSnapshot) -> tuple[str, str] | None:
    """(code, why) if this finding cannot lead, in the words the founder reads."""
    floor = settings.min_confidence()
    if f.confidence < floor:
        return "confidence", f"confidence {f.confidence:.2f} is under the {floor:.2f} floor"
    if not f.priced:
        return "unpriced", "no rate card is loaded for this platform, so it carries no dollar figure"
    if not f.evidence.get("monthly_units"):
        # No volume on file, so there is no monthly claim to make and the
        # per-unit figure has to stand alone. Common on Shopify, where the
        # harvest reads a catalogue rather than a sales rank.
        floor = settings.min_per_unit_only_usd()
        if f.per_unit_low < floor:
            return "too_small", (f"${f.per_unit_low:,.2f} a unit is under the ${floor:,.2f} floor "
                                 f"for a finding with no volume estimate behind it")
    elif f.dollars_high < settings.min_monthly_usd():
        return "too_small", (f"${f.dollars_high:,.0f} a month at the top of the range is under "
                             f"the ${settings.min_monthly_usd():,.0f} floor")
    revenue = _listing_revenue(f, snap)
    share = settings.max_claim_share()
    if revenue and f.dollars_high > revenue * share:
        return "implausible", (f"${f.dollars_high:,.0f} a month is more than {share:.0%} of what "
                               f"this listing is estimated to make (${revenue:,.0f}) — the volume "
                               f"estimate is misbehaving")
    return None


def review(candidates: list[Finding], snap: ProspectSnapshot) -> Verdict:
    """The full decision, with a reason recorded against everything that lost."""
    ranked = sorted(candidates, key=score, reverse=True)
    chosen: Finding | None = None
    rejected: list[Rejection] = []
    for f in ranked:
        verdict = _reject_reason(f, snap)
        if verdict:
            rejected.append(Rejection(f, verdict[0], verdict[1]))
        elif chosen is None:
            chosen = f
        else:
            rejected.append(Rejection(f, "outranked", "a stronger finding leads instead"))
    return Verdict(chosen=chosen, rejected=rejected)


def best(candidates: list[Finding], snap: ProspectSnapshot) -> Finding | None:
    return review(candidates, snap).chosen
