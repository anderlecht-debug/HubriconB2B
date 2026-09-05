"""The teardown page: one finding, its proof, and everything it assumed.

Styled from portal.html's tokens on purpose (COLD_ENGINE.md §3). A stranger
who clicks this link is being shown the product, not an advert for it — the
same serif, the same panels, the same restraint — and the page should read as
though it was cut out of the thing they would get as a client, because it was.

Two decisions worth defending:

**The assumptions are above the fold of the second screen, not in small print.**
A cold teardown is an unsolicited claim about someone's business. The honest
move is to hand the reader the means to reject it, immediately and in the same
type size as the claim. In practice it is also the persuasive move: this ICP
has been sent a hundred "you're losing $18,400!" emails, and the thing that
distinguishes a real analysis from those is that a real one shows its edges.

**There is a section saying what this page could not see.** It names the inputs
that would change the answer — real landed cost, real ad spend, the actual
packed weight — which is both true and the entire argument for the free
teardown the page asks for.
"""

from __future__ import annotations

import html
from datetime import date, datetime

from . import charts
from .findings import Finding
from .snapshot import ProspectSnapshot

MECHANISM = {
    "price_band_edge":
        "Amazon's 2026 schedule prices every fulfilment band three times, by sale price. "
        "A listing that crosses $10 or $50 pays the dearer column on every unit, and until "
        "the price rise covers that step the higher price nets less than the lower one.",
    "fee_band_edge":
        "FBA fulfilment is a staircase, not a slope. A unit an ounce over a band edge pays "
        "the whole of the next step, every time it ships.",
    "dim_weight_overage":
        "Past a cubic foot, carriers — and Amazon, on the same divisor — bill the greater of "
        "what a parcel weighs and what its dimensions imply. A light product in a large box "
        "pays for the air.",
    "size_tier_edge":
        "Size tier is decided on the packed box, not the product. A single dimension over the "
        "small-standard envelope moves every unit to large-standard rates.",
    "price_cut_no_rank_gain":
        "A price cut is a purchase: margin spent to buy units. When the rank does not move, "
        "nothing was bought.",
    "carrier_band_edge":
        "USPS rounds anything over a pound up to the next whole pound, so a parcel at 16.5 oz "
        "is billed at two pounds while the same parcel at 15.9 oz is billed at the flat "
        "sub-pound rate. How much that costs depends on how far it travels, which is why the "
        "chart shows every zone rather than an average.",
}

BLIND_SPOTS = [
    ("Your landed cost", "Every figure here is a fee, not a margin. What the change is worth "
                         "depends on what the unit costs you, which is not public."),
    ("Your packed weight", "Listings publish the item weight. Amazon bills the packed weight, "
                           "which adds its own packaging — so the band above is a floor."),
    ("Your ad spend", "Fulfilment is one line. Where the next ad dollar stops paying is usually "
                      "a larger number, and it is not visible from outside."),
    ("Everything else you sell", "This is one listing. A catalogue has the same arithmetic "
                                 "running on every SKU at once."),
]


def _e(s) -> str:
    return html.escape(str(s), quote=True) if s is not None else ""


def _money(v: float) -> str:
    return f"${v:,.0f}" if v >= 100 else f"${v:,.2f}"


def _cents(v: float) -> str:
    return f"{v * 100:.0f}¢" if v < 1 else f"${v:,.2f}"


def headline(f: Finding) -> tuple[str, str]:
    """(the big number, the line under it).

    A range leads with its floor rather than its midpoint. "at least 96¢" is a
    claim a reader can check and find conservative; a midpoint is a number they
    can find wrong in either direction.
    """
    wide = f.per_unit_high > f.per_unit_low
    per_unit = _cents(f.per_unit_low)
    tail = (f", and up to {_cents(f.per_unit_high)} depending how far it ships" if wide else "")
    least = "at least " if wide else ""
    if f.dollars_high > 0:
        return per_unit, (f"{least}per unit{tail} — which at this listing's estimated volume is "
                          f"{_money(f.dollars_low)} to {_money(f.dollars_high)} a month")
    return per_unit, f"{least}per unit{tail}, on every one you ship"


def render(f: Finding, snap: ProspectSnapshot, *, token: str, cta_url: str,
           expires_on: date, generated_on: date | None = None) -> str:
    """One self-contained HTML page: no external request, no font, no script.

    There is no tracking pixel and no beacon, and not only for taste. The view
    is already logged by the function that served the page and the CTA click by
    the redirect that follows it, so a script would double-count what the
    server already knows — and a page that loads nothing renders identically
    behind a corporate proxy, in a text client, and with scripting off.
    """
    generated_on = generated_on or date.today()
    brand = snap.display_name
    big, under = headline(f)
    chart = charts.render(f.evidence)
    listing_url = f.item_url or ""
    assumptions = "".join(f"<li>{_e(a)}</li>" for a in f.assumptions)
    blind = "".join(
        f'<div class="miss"><span class="miss-h">{_e(h)}</span>{_e(b)}</div>'
        for h, b in BLIND_SPOTS)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Profit Teardown — {_e(brand)}</title>
<style>
:root{{
  --bg: hsl(222 28% 96%); --panel: #fff; --panel-2: hsl(222 26% 94%);
  --amber: hsl(40 96% 33%); --ok: hsl(150 58% 28%); --serious: hsl(8 70% 42%);
  --c1:#4553C8; --ink: hsl(228 44% 11%); --ink-soft: hsl(228 26% 26%);
  --ink-faint: hsl(228 16% 42%); --hairline: hsl(228 30% 20% / .14);
  --rule: hsl(228 30% 20% / .30);
  --serif: "Iowan Old Style", Georgia, "Times New Roman", serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
}}
*{{ box-sizing: border-box; margin: 0; padding: 0; }}
body{{ background: var(--bg); color: var(--ink-soft); font-family: var(--sans);
  font-size: 15.5px; line-height: 1.65; -webkit-font-smoothing: antialiased;
  padding: 34px 20px 90px; }}
.wrap{{ max-width: 760px; margin: 0 auto; }}
a{{ color: var(--amber); }}
h1,h2{{ font-family: var(--serif); font-weight: 500; color: var(--ink);
  letter-spacing: -.01em; line-height: 1.15; }}
h1{{ font-size: clamp(25px, 4.4vw, 33px); }}
h2{{ font-size: 20px; margin-bottom: 10px; }}
.label{{ font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
  font-weight: 600; color: var(--ink-faint); display: block; }}
.panel{{ background: var(--panel); border: 1px solid var(--hairline); border-radius: 14px;
  padding: 28px 32px; margin-bottom: 18px; box-shadow: 0 1px 2px hsl(228 40% 15% / .05); }}
.masthead{{ margin-bottom: 22px; }}
.masthead h1{{ margin: 6px 0 8px; }}
.sub{{ color: var(--ink-faint); font-size: 14px; }}
.fig{{ font-family: var(--serif); font-weight: 500; color: var(--serious);
  font-variant-numeric: tabular-nums; letter-spacing: -.03em;
  font-size: clamp(46px, 11vw, 72px); line-height: 1; display: block; }}
.under{{ font-size: 16px; color: var(--ink-soft); margin-top: 12px; max-width: 46ch; }}
.chart{{ border: 1px solid var(--hairline); border-radius: 10px; overflow: hidden;
  margin: 20px 0 12px; background: #fff; }}
.caption{{ font-size: 12.5px; color: var(--ink-faint); }}
.listing{{ display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap;
  border-top: 1px solid var(--hairline); margin-top: 20px; padding-top: 16px;
  font-size: 13.5px; }}
.mono{{ font-family: var(--mono); font-size: 12.5px; color: var(--ink-faint); }}
ul.assume{{ list-style: none; }}
ul.assume li{{ position: relative; padding-left: 20px; margin-bottom: 10px; }}
ul.assume li:before{{ content: ""; position: absolute; left: 2px; top: .66em;
  width: 7px; height: 7px; border: 1.5px solid var(--rule); border-radius: 2px; }}
.miss{{ border-top: 1px solid var(--hairline); padding: 12px 0; }}
.miss:first-child{{ border-top: 0; }}
.miss-h{{ display: block; color: var(--ink); font-weight: 600; font-size: 14px; }}
.cta{{ background: var(--ink); color: hsl(222 28% 96%); border-radius: 14px;
  padding: 30px 32px; margin-top: 26px; }}
.cta h2{{ color: #fff; }}
.cta p{{ color: hsl(222 22% 78%); max-width: 52ch; }}
.btn{{ display: inline-block; margin-top: 18px; background: var(--amber); color: #1a1205;
  font-weight: 650; padding: 13px 24px; border-radius: 9px; text-decoration: none;
  font-size: 15px; }}
footer{{ margin-top: 28px; font-size: 12.5px; color: var(--ink-faint); line-height: 1.7; }}
@media (max-width: 560px){{ .panel, .cta{{ padding: 22px 20px; }} body{{ padding: 22px 14px 70px; }} }}
</style>
</head><body>
<div class="wrap">

  <div class="masthead">
    <span class="label">Profit Teardown</span>
    <h1>{_e(brand)}</h1>
    <p class="sub">Built on {generated_on:%B %-d, %Y} from pages {_e(brand)} published.
       No account access, no seat, nothing you sent us.</p>
  </div>

  <section class="panel">
    <span class="label">What one listing is giving up</span>
    <span class="fig">{_e(big)}</span>
    <p class="under">{_e(under)}</p>
    <div class="chart">{chart}</div>
    <p class="caption">{_e(MECHANISM.get(f.kind, ""))}</p>
    <div class="listing">
      <span class="mono">{_e(f.asin_or_sku)}</span>
      <span>{_e(f.item_title or "")}</span>
      {f'<a class="mono" href="{_e(listing_url)}" rel="nofollow noopener">see the listing</a>'
       if listing_url else ""}
    </div>
  </section>

  <section class="panel">
    <h2>What this assumed</h2>
    <p class="sub" style="margin-bottom:16px">Every one of these is a place the number could be
       wrong. They are here rather than in a footnote because you have no reason to take our
       word for any of it.</p>
    <ul class="assume">{assumptions}</ul>
  </section>

  <section class="panel">
    <h2>What this page could not see</h2>
    <p class="sub" style="margin-bottom:8px">A teardown from the outside stops here. These are
       the inputs that would move the answer.</p>
    {blind}
  </section>

  <div class="cta">
    <h2>The same arithmetic, on your real numbers</h2>
    <p>Five exports, about fifteen minutes on your side, a written teardown back within 24 hours.
       No seat in your account, no card. If it finds nothing worth fixing, we say so — and the
       report is yours to keep either way.</p>
    <a class="btn" href="{_e(cta_url)}">Get the full teardown, free</a>
  </div>

  <footer>
    Hubricon &middot; margin math for {"founder-run Shopify brands" if snap.platform == "shopify"
                                      else "Amazon private-label brands"}.<br>
    This page was built for {_e(brand)} and expires on {expires_on:%B %-d, %Y}.
    It is not indexed and the link is not shared with anyone.<br>
    Reply to the email that brought you here with the word STOP and we will not write again.
  </footer>

</div>
</body></html>
"""
