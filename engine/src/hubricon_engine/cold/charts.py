"""Inline SVG for the teardown page. No matplotlib, no images, no fonts to load.

The client report renders matplotlib PNGs on a dark ground because it is
narrated over in a video. The teardown page is a light document a stranger
opens on their phone, so the chart is SVG in the page's own type and colours,
crisp at any zoom and about two kilobytes.

The chart is the proof (COLD_ENGINE.md §3), so the rule for all four of these
is the same: plot the *published rate card* as the background and the
prospect's own listing as a single marked point on it. The reader is meant to
see that the staircase is Amazon's, not ours, and that we have only pointed at
where they stand on it.
"""

from __future__ import annotations

import math

from . import priors

W, H = 660, 300
PAD_L, PAD_R, PAD_T, PAD_B = 62, 22, 26, 44

INK = "#171E33"
INK_SOFT = "#353F5B"
INK_FAINT = "#5A6480"
HAIRLINE = "#D5D9E4"
RULE = "#AEB5C6"
C1 = "#4553C8"          # the rate card
SERIOUS = "#B4361F"     # where they stand, and what it costs
OK = "#1D6B45"          # where they could stand
PANEL = "#FFFFFF"


def nice_ticks(lo: float, hi: float, target: int = 4) -> list[float]:
    """Round numbers inside a range. Axis labels a reader has to decode are
    labels they stop reading, and this chart's whole job is being checked."""
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), 10 * mag)
    first = math.ceil(lo / step) * step
    out, v = [], first
    while v <= hi + step * 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def _x(v, lo, hi):
    return PAD_L + (v - lo) / (hi - lo or 1) * (W - PAD_L - PAD_R)


def _y(v, lo, hi):
    return H - PAD_B - (v - lo) / (hi - lo or 1) * (H - PAD_T - PAD_B)


def _frame(x_label: str, y_label: str, ticks_x: list[tuple[float, str]],
           ticks_y: list[tuple[float, str]]) -> list[str]:
    out = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="{PANEL}"/>']
    for px, label in ticks_y:
        out.append(f'<line x1="{PAD_L}" y1="{px:.1f}" x2="{W - PAD_R}" y2="{px:.1f}" '
                   f'stroke="{HAIRLINE}" stroke-width="1"/>')
        out.append(f'<text x="{PAD_L - 9}" y="{px + 4:.1f}" text-anchor="end" font-size="11" '
                   f'fill="{INK_FAINT}">{label}</text>')
    for px, label in ticks_x:
        out.append(f'<text x="{px:.1f}" y="{H - PAD_B + 18}" text-anchor="middle" font-size="11" '
                   f'fill="{INK_FAINT}">{label}</text>')
    out.append(f'<line x1="{PAD_L}" y1="{H - PAD_B}" x2="{W - PAD_R}" y2="{H - PAD_B}" '
               f'stroke="{RULE}" stroke-width="1"/>')
    out.append(f'<text x="{W - PAD_R}" y="{H - 6}" text-anchor="end" font-size="10.5" '
               f'fill="{INK_FAINT}" letter-spacing="0.08em">{x_label.upper()}</text>')
    out.append(f'<text x="6" y="{PAD_T - 10}" font-size="10.5" '
               f'fill="{INK_FAINT}" letter-spacing="0.08em">{y_label.upper()}</text>')
    return out


def _svg(body: list[str], title: str) -> str:
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{title}" '
            f'style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
            f'font-variant-numeric:tabular-nums">'
            + "".join(body) + "</svg>")


def _marker(x: float, y: float, label: str, colour: str, above: bool = True,
            align: str | None = None) -> list[str]:
    """A dot on the rate card with its label. `align` pushes the text off to one
    side, which is what keeps two markers a few pixels apart from colliding —
    the interesting case is always a listing sitting right beside a band edge."""
    dy = -14 if above else 22
    if align == "end":
        anchor, x_text = "end", x - 13
    elif align == "start":
        anchor, x_text = "start", x + 13
    elif x < PAD_L + 60:
        anchor, x_text = "start", x - 6
    elif x > W - PAD_R - 60:
        anchor, x_text = "end", x + 6
    else:
        anchor, x_text = "middle", x
    return [
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{colour}"/>',
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9.5" fill="none" stroke="{colour}" '
        f'stroke-width="1.5" opacity="0.4"/>',
        f'<text x="{x_text:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" font-size="12" '
        f'font-weight="600" fill="{colour}">{label}</text>',
    ]


# -- net per unit against sale price -----------------------------------------------

def net_vs_price(ev: dict) -> str:
    """The $10 (or $50) fee cliff, drawn. The line falls as the price rises.

    This is the most persuasive picture the engine makes, because the reader
    does not have to take anything on trust: net revenue is their own price
    minus two published rates, and it visibly steps down at the edge.

    Two versions, and the difference matters. When the listing's size tier and
    weight are known the fee is a number off the card, so the axis is what they
    actually keep per unit. When they are not, the *absolute* fee is unknown but
    the *step* between price columns is not — so the axis becomes the difference
    against pricing under the edge, where the unknown fee cancels out of both
    sides and every point on the curve is still exactly right. Plotting an
    absolute in that case would put a number on the page that is too high by
    the whole fulfilment fee, which is the one thing this page must never do.
    """
    edge, rate = ev["edge"], ev["referral_rate"]
    tier, weight = ev.get("tier"), ev.get("weight_oz")
    absolute = bool(tier and weight)
    target = ev["target_price"]
    lo_p, hi_p = edge - 1.5, max(ev["break_even_price"] + 0.9, ev["your_price"] + 0.6)

    def net(price: float) -> float:
        if absolute:
            fee = priors.fulfilment_fee(tier, weight, price)
            if fee is not None:
                return price * (1 - rate) - fee
        # Relative to the target price. The fee appears on both sides and
        # cancels, leaving only the published column step.
        step = ev["fee_jump_high"] if price >= edge else 0.0
        return (price - target) * (1 - rate) - step

    steps = [lo_p + (hi_p - lo_p) * i / 200 for i in range(201)]
    pts = [(p, net(p)) for p in steps]
    ys = [y for _, y in pts]
    y_lo, y_hi = min(ys) - 0.25, max(ys) + 0.25

    path, prev = [], None
    for p, n in pts:
        x, y = _x(p, lo_p, hi_p), _y(n, y_lo, y_hi)
        if prev is not None and abs(prev[1] - n) > 0.2:      # the cliff: draw it vertical
            path.append(f"L{_x(p, lo_p, hi_p):.1f},{_y(prev[1], y_lo, y_hi):.1f}")
        path.append(("M" if prev is None else "L") + f"{x:.1f},{y:.1f}")
        prev = (p, n)

    money = (lambda v: f"${v:,.2f}") if absolute else (lambda v: f"{v:+,.2f}".replace("+0.00", "0"))
    ticks_x = [(_x(v, lo_p, hi_p), f"${v:,.2f}") for v in nice_ticks(lo_p, hi_p)]
    ticks_y = [(_y(v, y_lo, y_hi), money(v)) for v in nice_ticks(y_lo, y_hi, 4)]

    label = ("you keep, per unit" if absolute
             else f"per unit, against pricing at ${target:,.2f}")
    body = _frame("your sale price", label, ticks_x, ticks_y)
    if not absolute and y_lo < 0 < y_hi:
        body.append(f'<line x1="{PAD_L}" y1="{_y(0, y_lo, y_hi):.1f}" x2="{W - PAD_R}" '
                    f'y2="{_y(0, y_lo, y_hi):.1f}" stroke="{RULE}" stroke-width="1"/>')
    body.append(f'<line x1="{_x(edge, lo_p, hi_p):.1f}" y1="{PAD_T}" '
                f'x2="{_x(edge, lo_p, hi_p):.1f}" y2="{H - PAD_B}" stroke="{RULE}" '
                f'stroke-width="1" stroke-dasharray="3 4"/>')
    body.append(f'<text x="{_x(edge, lo_p, hi_p) + 6:.1f}" y="{PAD_T + 12}" font-size="11" '
                f'fill="{INK_FAINT}">Amazon\'s ${edge:,.0f} fee band</text>')
    body.append(f'<path d="{"".join(path)}" fill="none" stroke="{C1}" stroke-width="2.5" '
                f'stroke-linejoin="round"/>')
    body += _marker(_x(target, lo_p, hi_p), _y(net(target), y_lo, y_hi),
                    f"at ${target:,.2f}", OK, align="end")
    body += _marker(_x(ev["your_price"], lo_p, hi_p), _y(net(ev["your_price"]), y_lo, y_hi),
                    f"you: ${ev['your_price']:,.2f}", SERIOUS, above=False, align="start")
    return _svg(body, "Net revenue per unit against sale price")


# -- the fulfilment fee staircase --------------------------------------------------

def fee_vs_weight(ev: dict) -> str:
    """Amazon's published fee ladder, with their listing standing on it."""
    tier = ev.get("tier") or "large_standard"
    if tier not in ("small_standard", "large_standard"):
        tier = "large_standard"
    price = ev.get("price") or 25.0
    here = ev.get("your_weight_oz") or 0
    target = ev.get("edge")
    lo_w = max(0.5, min(here, target or here) - 6)
    hi_w = max(here, target or here) + 6

    table = (priors.SMALL_STANDARD_OZ if tier == "small_standard" else priors.LARGE_STANDARD_OZ)
    edges = [e for e, _ in table if lo_w - 4 <= e <= hi_w + 4]
    samples = [lo_w + (hi_w - lo_w) * i / 240 for i in range(241)]
    fees = [(w, priors.fulfilment_fee(tier, w, price)) for w in samples]
    fees = [(w, f) for w, f in fees if f is not None]
    if not fees:
        return ""
    ys = [f for _, f in fees]
    y_lo, y_hi = min(ys) - 0.15, max(ys) + 0.25

    path, prev = [], None
    for w, f in fees:
        x, y = _x(w, lo_w, hi_w), _y(f, y_lo, y_hi)
        if prev is not None and abs(prev - f) > 0.005:
            path.append(f"L{x:.1f},{_y(prev, y_lo, y_hi):.1f}")
        path.append(("M" if prev is None else "L") + f"{x:.1f},{y:.1f}")
        prev = f

    ticks_x = [(_x(e, lo_w, hi_w), f"{e:g} oz") for e in edges]
    ticks_y = [(_y(v, y_lo, y_hi), f"${v:,.2f}") for v in nice_ticks(y_lo, y_hi, 4)]
    body = _frame("shipping weight", "amazon's fee, per unit", ticks_x, ticks_y)
    body.append(f'<path d="{"".join(path)}" fill="none" stroke="{C1}" stroke-width="2.5" '
                f'stroke-linejoin="round"/>')
    if target:
        fee_t = priors.fulfilment_fee(tier, target, price)
        if fee_t:
            body += _marker(_x(target, lo_w, hi_w), _y(fee_t, y_lo, y_hi),
                            f"under {target:g} oz", OK, align="end")
    fee_h = priors.fulfilment_fee(tier, here, price)
    if fee_h:
        body += _marker(_x(here, lo_w, hi_w), _y(fee_h, y_lo, y_hi),
                        f"you: {here:g} oz", SERIOUS, align="start")
    return _svg(body, "Amazon's published fulfilment fee by shipping weight")


# -- two bars: the size tier -------------------------------------------------------

def size_tier(ev: dict) -> str:
    small, large = ev["small_fee"], ev["large_fee"]
    y_hi = large * 1.28
    bar_w, gap = 120, 78
    x0 = PAD_L + 70
    body = _frame("size tier", "amazon's fee, per unit",
                  [], [(_y(v, 0, y_hi), f"${v:,.2f}") for v in nice_ticks(0, y_hi, 4)])
    for i, (label, fee, colour) in enumerate((
            (f"small standard\n{priors.SMALL_STANDARD_ENVELOPE_IN[2]:g} in and under", small, OK),
            (f"large standard\nyour {ev['axis']}: {ev['actual_in']:g} in", large, SERIOUS))):
        x = x0 + i * (bar_w + gap)
        y = _y(fee, 0, y_hi)
        body.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{H - PAD_B - y:.1f}" '
                    f'fill="{colour}" opacity="0.16"/>')
        body.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="3" fill="{colour}"/>')
        body.append(f'<text x="{x + bar_w / 2:.0f}" y="{y - 10:.1f}" text-anchor="middle" '
                    f'font-size="15" font-weight="600" fill="{colour}">${fee:,.2f}</text>')
        head, sub = label.split("\n")
        body.append(f'<text x="{x + bar_w / 2:.0f}" y="{H - PAD_B + 17}" text-anchor="middle" '
                    f'font-size="11.5" fill="{INK_SOFT}">{head}</text>')
        body.append(f'<text x="{x + bar_w / 2:.0f}" y="{H - PAD_B + 31}" text-anchor="middle" '
                    f'font-size="10.5" fill="{INK_FAINT}">{sub}</text>')
    # A bracket across the two bar tops, so the gap reads as one difference
    # rather than as two unrelated numbers.
    left, right = x0 + bar_w / 2, x0 + bar_w + gap + bar_w / 2
    top = _y(large, 0, y_hi) - 34
    body.append(f'<path d="M{left:.0f},{_y(small, 0, y_hi) - 26:.0f} L{left:.0f},{top:.0f} '
                f'L{right:.0f},{top:.0f} L{right:.0f},{_y(large, 0, y_hi) - 26:.0f}" '
                f'fill="none" stroke="{RULE}" stroke-width="1"/>')
    body.append(f'<rect x="{(left + right) / 2 - 52:.0f}" y="{top - 11:.0f}" width="104" '
                f'height="22" rx="4" fill="{PANEL}"/>')
    body.append(f'<text x="{(left + right) / 2:.0f}" y="{top + 5:.0f}" text-anchor="middle" '
                f'font-size="12.5" font-weight="600" fill="{INK}">'
                f'+${large - small:,.2f} a unit</text>')
    return _svg(body, "Fulfilment fee by size tier")


# -- price against rank over time --------------------------------------------------

def price_vs_rank(ev: dict) -> str:
    series = ev.get("series") or []
    if len(series) < 2:
        return ""
    prices = [s["price"] for s in series if s.get("price")]
    ranks = [s["rank"] for s in series if s.get("rank")]
    n = len(series)
    p_lo, p_hi = min(prices) * 0.96, max(prices) * 1.04
    body = _frame("", "your price", [(_x(i, 0, n - 1), series[i]["date"][5:])
                                     for i in (0, n // 2, n - 1)],
                  [(_y(v, p_lo, p_hi), f"${v:,.2f}") for v in nice_ticks(p_lo, p_hi, 3)])
    pts = " ".join(f"{_x(i, 0, n - 1):.1f},{_y(s['price'], p_lo, p_hi):.1f}"
                   for i, s in enumerate(series) if s.get("price"))
    body.append(f'<polyline points="{pts}" fill="none" stroke="{SERIOUS}" stroke-width="2.5"/>')
    if len(ranks) >= 2:
        r_lo, r_hi = min(ranks) * 0.9, max(ranks) * 1.1
        rpts = " ".join(f"{_x(i, 0, n - 1):.1f},{_y(s['rank'], r_lo, r_hi):.1f}"
                        for i, s in enumerate(series) if s.get("rank"))
        body.append(f'<polyline points="{rpts}" fill="none" stroke="{C1}" stroke-width="2" '
                    f'stroke-dasharray="5 4" opacity="0.85"/>')
        body.append(f'<text x="{W - PAD_R}" y="{PAD_T + 2}" text-anchor="end" font-size="11" '
                    f'fill="{C1}">sales rank (dashed) — flat</text>')
    return _svg(body, "Price and sales rank over time")


# -- the carrier card, zone by zone ------------------------------------------------

def carrier_bands(ev: dict) -> str:
    """What they pay against what they would pay, across all eight zones.

    The zone spread is the honest part of this finding — we do not know where a
    brand ships — so the chart shows the whole spread rather than hiding it
    behind an average. The shaded gap between the two lines *is* the claim.
    """
    rows = priors.carrier_rows(ev.get("edge"))
    if not rows:
        return ""
    now, under = rows
    zones = priors.CARRIER_ZONES
    lo_z, hi_z = zones[0], zones[-1]
    y_lo, y_hi = min(under) - 0.6, max(now) + 0.8

    pts = lambda series: " ".join(  # noqa: E731
        f"{_x(z, lo_z, hi_z):.1f},{_y(v, y_lo, y_hi):.1f}" for z, v in zip(zones, series))
    body = _frame("delivery zone — 1 is local, 8 is coast to coast",
                  "usps ground advantage, per parcel",
                  [(_x(z, lo_z, hi_z), str(z)) for z in zones],
                  [(_y(v, y_lo, y_hi), f"${v:,.2f}") for v in nice_ticks(y_lo, y_hi, 4)])
    band = (pts(now) + " " +
            " ".join(f"{_x(z, lo_z, hi_z):.1f},{_y(v, y_lo, y_hi):.1f}"
                     for z, v in reversed(list(zip(zones, under)))))
    body.append(f'<polygon points="{band}" fill="{SERIOUS}" opacity="0.10"/>')
    body.append(f'<polyline points="{pts(now)}" fill="none" stroke="{SERIOUS}" stroke-width="2.5"/>')
    body.append(f'<polyline points="{pts(under)}" fill="none" stroke="{OK}" stroke-width="2.5" '
                f'stroke-dasharray="5 4"/>')
    body.append(f'<text x="{_x(zones[-1], lo_z, hi_z):.0f}" y="{_y(now[-1], y_lo, y_hi) - 12:.0f}" '
                f'text-anchor="end" font-size="12" font-weight="600" fill="{SERIOUS}">'
                f'you: {ev.get("band_above", "")} rate</text>')
    body.append(f'<text x="{_x(zones[-1], lo_z, hi_z):.0f}" y="{_y(under[-1], y_lo, y_hi) + 20:.0f}" '
                f'text-anchor="end" font-size="12" font-weight="600" fill="{OK}">'
                f'{ev.get("band_below", "")}</text>')
    mid = len(zones) // 2
    gap = now[mid] - under[mid]
    body.append(f'<text x="{_x(zones[mid], lo_z, hi_z):.0f}" '
                f'y="{(_y(now[mid], y_lo, y_hi) + _y(under[mid], y_lo, y_hi)) / 2 + 4:.0f}" '
                f'text-anchor="middle" font-size="12" font-weight="600" fill="{INK}">'
                f'${gap:,.2f}</text>')
    return _svg(body, "USPS Ground Advantage cost per parcel by zone")


CHARTS = {
    "net_vs_price": net_vs_price,
    "carrier_bands": carrier_bands,
    "fee_vs_weight": fee_vs_weight,
    "size_tier": size_tier,
    "price_vs_rank": price_vs_rank,
}


def render(evidence: dict) -> str:
    fn = CHARTS.get(evidence.get("chart", ""))
    return fn(evidence) if fn else ""
