"""A Finding becomes a subject line, an email and a ninety-second script.

**No number in here is written by a language model.** Every figure is
interpolated from the `Finding` object, and the sentences around them are
templates. COLD_ENGINE.md §2 allows an LLM to write the connective prose; this
module does not use one, because the connective prose is four sentences long
and a template that cannot hallucinate is worth more than a template that
sounds slightly warmer. The seam is here if that changes: `hook()` returns the
paragraph, and only that paragraph would ever be model-written.

The shape of the email, and why:

  the number      first line, in their own units, checkable against a page they
                  published themselves. Nothing about Hubricon appears until
                  after it.
  the mechanism   two sentences of arithmetic. This ICP checks arithmetic; it
                  is the reason they believe the rest.
  the range       the monthly figure, bracketed, with where the bracket comes
                  from. Stating the uncertainty is what makes the point
                  estimate credible.
  the page        one link, which carries the chart and the assumptions in full
  one ask         the free teardown. One ask, no second CTA, no PS.
  the footer      CAN-SPAM: who this is, where we are, how to stop it.

The assumptions are rendered verbatim in the message (§2.2). They are not
small print — they are the reason a stranger believes the number, and the
teardown page repeats them under the chart.
"""

from __future__ import annotations

from .. import onboarding
from . import compliance, settings
from .findings import Finding
from .snapshot import ProspectSnapshot

TEMPLATE_ID = "cold-teardown-v1"
SIGNATURE = "Hagen Simmons\nHubricon"


def _money(v: float) -> str:
    return f"${v:,.0f}" if v >= 100 else f"${v:,.2f}"


def _cents(v: float) -> str:
    """Per-unit money reads better in cents under a dollar: '57c', '$1.08'."""
    return f"{v * 100:.0f}c" if v < 1 else f"${v:,.2f}"


def _short_title(finding: Finding) -> str:
    """Amazon titles are keyword stuffing. Quote enough to be recognised, no more."""
    title = (finding.item_title or "").strip()
    if not title:
        return finding.asin_or_sku or "listing"
    words = title.replace(",", " ").split()
    return " ".join(words[:6]).rstrip(" -") or (finding.asin_or_sku or "listing")


def _monthly_phrase(f: Finding) -> str | None:
    if not (f.dollars_high > 0):
        return None
    if f.dollars_low <= 0:
        return f"up to {_money(f.dollars_high)} a month"
    return f"somewhere between {_money(f.dollars_low)} and {_money(f.dollars_high)} a month"


# -- the hook, one per finding kind ------------------------------------------------

def _price_band_hook(f: Finding) -> tuple[str, str]:
    e = f.evidence
    per_unit = _cents(f.per_unit_low)
    item = _short_title(f)
    subject = f"{_money(e['your_price'])} nets you less than {_money(e['target_price'])} does"
    body = (
        f"Your {item} is listed at {_money(e['your_price'])}. At "
        f"{_money(e['target_price'])} you would keep about {per_unit} more per unit — not less.\n\n"
        f"Amazon's 2026 schedule prices every weight band three times: under $10, $10 to $50, and "
        f"over $50. Crossing {_money(e['edge'])} adds about "
        f"{_cents(e['fee_jump_high'])} a unit in fulfilment, and the "
        f"{_cents(e['your_price'] - e['target_price'])} of extra price does not cover it after the "
        f"{e['referral_rate']:.0%} referral fee. Break-even is {_money(e['break_even_price'])}: "
        f"anywhere between {_money(e['edge'])} and that, the higher price is the worse price."
    )
    return subject, body


def _fee_band_hook(f: Finding) -> tuple[str, str]:
    e = f.evidence
    item = _short_title(f)
    subject = f"{e['over_by_oz']:g} oz is costing {{brand}} on every unit"
    body = (
        f"Your {item} publishes an item weight of {e['your_weight_oz']:g} oz. The FBA fulfilment "
        f"band below it ends at {e['edge']:g} oz — and that is before Amazon adds its own "
        f"packaging, so the unit is at least {e['over_by_oz']:g} oz into the band above.\n\n"
        f"That band step is {_cents(f.per_unit_low)} a unit"
        + (f" to {_cents(f.per_unit_high)}" if f.per_unit_high > f.per_unit_low else "")
        + f" on the published schedule. I read the weight off your own listing; I have no access "
        f"to your account."
    )
    return subject, body


def _dim_weight_hook(f: Finding) -> tuple[str, str]:
    e = f.evidence
    d = e["dims_in"]
    item = _short_title(f)
    subject = "{brand} is paying fulfilment on the box, not the product"
    body = (
        f"Your {item} weighs {e['item_weight_oz'] / 16:.2f} lb and ships in a box your listing "
        f"gives as {d[0]:g} x {d[1]:g} x {d[2]:g} inches. That is "
        f"{e['cubic_in']:,.0f} cubic inches, which past a cubic foot means Amazon bills it on "
        f"dimensional weight — {e['dim_weight_oz'] / 16:.1f} lb — rather than on what is inside "
        f"it.\n\n"
        f"On the published schedule that is {_cents(f.per_unit_low)} a unit more than the same "
        f"product billed on its real weight. Both numbers are on your own product page."
    )
    return subject, body


def _size_tier_hook(f: Finding) -> tuple[str, str]:
    e = f.evidence
    item = _short_title(f)
    subject = f"{e['over_by_in']:g} of an inch is moving {{brand}} into a dearer size tier"
    body = (
        f"Your {item} is {e['weight_oz']:g} oz, which is inside Amazon's small-standard weight "
        f"limit. The box is not: your listing gives the {e['axis']} as {e['actual_in']:g} in "
        f"against a {e['limit_in']:g} in limit, and that single dimension puts the unit into "
        f"large standard.\n\n"
        f"Large standard costs {_cents(f.per_unit_low)} a unit more at this weight "
        f"({_money(e['large_fee'])} against {_money(e['small_fee'])}). Every other dimension "
        f"already fits, so it is a packaging change rather than a product one."
    )
    return subject, body


def _price_cut_hook(f: Finding) -> tuple[str, str]:
    e = f.evidence
    item = _short_title(f)
    rank = (f"and its rank moved from #{e['from_rank']:,} to #{e['to_rank']:,}"
            if e.get("from_rank") and e.get("to_rank") else "and its rank did not move with it")
    subject = f"{{brand}} cut {_money(e['from_price'])} to {_money(e['to_price'])} and got nothing for it"
    body = (
        f"Your {item} went from {_money(e['from_price'])} to {_money(e['to_price'])} over "
        f"{e['span_days']} days, {rank}.\n\n"
        f"That is {_cents(f.per_unit_low)} a unit of margin, net of the referral fee, given away "
        f"for volume that did not arrive. I read both prices off the public listing on the two "
        f"dates below."
    )
    return subject, body


def _carrier_band_hook(f: Finding) -> tuple[str, str]:
    e = f.evidence
    item = _short_title(f)
    subject = f"{e['over_by_oz']:g} oz is costing {{brand}} on every parcel"
    body = (
        f"Your {item} publishes a weight of {e['your_weight_oz']:g} oz. The {e['band_below']} "
        f"band ends at {e['edge']} oz, so every unit ships on the {e['band_above']} rate at USPS "
        f"and UPS.\n\n"
        f"I read that off your own product page. I have no access to your store."
    )
    return subject, body


HOOKS = {
    "price_band_edge": _price_band_hook,
    "fee_band_edge": _fee_band_hook,
    "dim_weight_overage": _dim_weight_hook,
    "size_tier_edge": _size_tier_hook,
    "price_cut_no_rank_gain": _price_cut_hook,
    "carrier_band_edge": _carrier_band_hook,
}


def hook(f: Finding, brand: str) -> tuple[str, str]:
    """(subject, opening paragraphs) for one finding. Numbers are templated."""
    subject, body = HOOKS[f.kind](f)
    return subject.replace("{brand}", brand), body.replace("{brand}", brand)


# -- the whole message -------------------------------------------------------------

EXPORTS = {"amazon": "Five Seller Central exports",
           "shopify": "Five exports out of your Shopify admin"}
NO_ACCESS = {"amazon": "No seat in your account", "shopify": "No staff account in your store"}
AUDIENCE = {"amazon": "Amazon private-label brands", "shopify": "founder-run Shopify brands"}


def footer(unsubscribe_hint: str = "reply with the word STOP and I will not write again") -> str:
    """CAN-SPAM: who is writing, where they are, how to make it stop.

    The automated lane adds a List-Unsubscribe header on top of this; a
    hand-sent founder email cannot carry one, so the in-body mechanism is the
    one that has to work. It is a real instruction, not decoration: the reply
    triage closes the lead and writes a suppression row.
    """
    address = compliance.postal_address() or "[POSTAL_ADDRESS is not set]"
    return (f"{SIGNATURE}\n{address}\n\n"
            f"This is a one-off note about a public listing, not a subscription. "
            f"If you would rather not hear from me, {unsubscribe_hint}.")


def assumptions_block(f: Finding) -> str:
    lines = "\n".join(f"  - {a}" for a in f.assumptions)
    return f"What that figure assumes, in full:\n{lines}"


def email(f: Finding, snap: ProspectSnapshot, first_name: str | None,
          teardown_url: str | None, calendly_url: str) -> dict:
    """The message the founder reads, edits and sends.

    Returns `complete=False` when something is missing that a human must supply
    — today that is only the recipient's first name. An incomplete draft is
    never sendable and says why on its face rather than going out addressed to
    'there'.
    """
    brand = snap.display_name
    subject, opening = hook(f, brand)
    greeting = first_name or snap.first_name
    monthly = _monthly_phrase(f)
    parts = [f"Hi {greeting or '[FIRST NAME — find it before sending]'},", "", opening]
    if monthly:
        parts += ["", f"At the volume that listing looks to do, {monthly}. That range is wide "
                      f"because the volume is estimated from your public rank, not measured — "
                      f"the per-unit figure is the part I would stand behind."]
    if teardown_url:
        parts += ["", f"The arithmetic, the chart and every assumption behind it are on one "
                      f"page:\n{teardown_url}"]
    else:
        parts += ["", assumptions_block(f)]
    parts += [
        "",
        f"That is the sort of thing I do at Hubricon — the margin math for "
        f"{AUDIENCE.get(snap.platform, AUDIENCE['amazon'])}. What your price can take before "
        f"units drop. Where the next ad dollar stops paying. Which SKU stocks out first.",
        "",
        f"If it is useful I will run the same thing on your real numbers and send it back free. "
        f"{EXPORTS.get(snap.platform, EXPORTS['amazon'])}, about fifteen minutes on your side, "
        f"report within 24 hours. {NO_ACCESS.get(snap.platform, NO_ACCESS['amazon'])}, no card. "
        f"If it finds nothing worth fixing I will say so, and the report is yours either way.",
        "",
        f"Want it? Reply, or take 20 minutes here: {calendly_url}",
        "",
        footer(),
    ]
    return {
        "to": snap.email,
        "subject": subject,
        "body": "\n".join(parts),
        "template_id": TEMPLATE_ID,
        "complete": bool(greeting) and not onboarding.is_internal(snap.email, brand),
        "missing": None if greeting else "a first name — the founder lane does not send 'Hi there'",
    }


def script(f: Finding, snap: ProspectSnapshot) -> str:
    """The ninety-second narration for the Phase 5 video.

    Written now because it is the same numbers in a different order, and
    because writing it here keeps the video from inventing a figure later.
    """
    brand = snap.display_name
    _, opening = hook(f, brand)
    monthly = _monthly_phrase(f)
    lines = [
        f"This is a teardown of one {brand} listing, built entirely from pages {brand} published.",
        "",
        opening.replace("\n\n", " "),
        "",
    ]
    if monthly:
        lines += [f"At the volume that listing looks to do, that is {monthly}. The range is wide "
                  f"because the volume is estimated from public rank rather than measured.", ""]
    lines += [
        "Here is what I had to assume to get there.",
        *[f"{a.capitalize()}." for a in f.assumptions],
        "",
        f"If the numbers are close, the same arithmetic on {brand}'s real exports is a great deal "
        f"sharper, and the first one is free.",
    ]
    return "\n".join(lines)


def teardown_url(token: str) -> str:
    return f"{settings.teardown_base_url()}/{token}"
