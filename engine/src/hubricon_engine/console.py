"""The Briefing Console — a self-contained dark HTML deck the operator
opens full-screen and screen-shares while recording the 3-minute Loom.

Internal artifact, generated locally from the latest run (`hubricon
console <client>`): never deployed, never behind a login, never sent to
the client — they receive the Loom link. Palette and type follow the
report package (deep navy, amber, Fraunces + mono) so every surface a
client ever glimpses is the same instrument.

All charts are hand-built inline SVG: one axis each, direct labels, no
external libraries, no network dependency beyond an optional Google
Fonts link with real fallbacks.
"""

from datetime import date, timedelta
from html import escape

from .models.pricing_engine import price_move, profit

NAVY_DEEP = "#050A1F"
PANEL = "rgba(255,255,255,0.03)"
EDGE = "rgba(255,255,255,0.14)"
AMBER = "#FFC000"
GREEN = "#10B981"
RED = "#EF4444"
INK = "rgba(244,246,252,0.92)"
INK_60 = "rgba(244,246,252,0.60)"
INK_35 = "rgba(244,246,252,0.35)"
SLATE = "#39415E"

RISK_WARNING = 0.25
RISK_CRITICAL = 0.50
DANGER_COVER_DAYS = 15


def _money(v) -> str:
    v = float(v)
    sign = "−" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    """A few round-numbered axis ticks covering [lo, hi]."""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / max(1, n - 1)
    mag = 10 ** len(str(int(abs(raw)))) / 10 if abs(raw) >= 1 else 1
    step = max(mag, round(raw / mag) * mag)
    first = step * (lo // step)
    out, t = [], first
    while t <= hi + step / 2:
        if t >= lo - step / 2:
            out.append(t)
        t += step
    return out or [lo, hi]


class _Scale:
    def __init__(self, domain, rng):
        (self.d0, self.d1), (self.r0, self.r1) = domain, rng
        self.span = (self.d1 - self.d0) or 1

    def __call__(self, v) -> float:
        return self.r0 + (float(v) - self.d0) / self.span * (self.r1 - self.r0)


def _polyline(xs, ys, sx, sy) -> str:
    return " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in zip(xs, ys))


def cash_cone_svg(cash: dict, today: date) -> str:
    d = cash["details"]
    p5 = [float(v) for v in d["p5"]]
    p50 = [float(v) for v in d["p50"]]
    p95 = [float(v) for v in d["p95"]]
    days = list(range(1, len(p5) + 1))
    wires = d.get("wires") or []

    w, h, m = 960, 330, {"l": 86, "r": 24, "t": 30, "b": 44}
    lo = min(0.0, min(p5) * 1.08)
    hi = max(p95) * 1.06
    sx = _Scale((1, len(p5)), (m["l"], w - m["r"]))
    sy = _Scale((lo, hi), (h - m["b"], m["t"]))

    grid = "".join(
        f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/>'
        f'<text x="{m["l"] - 10}" y="{sy(t) + 4:.1f}" class="ax" text-anchor="end">{_money(t)}</text>'
        for t in _ticks(lo, hi) if lo <= t <= hi
    )
    xlabels = "".join(
        f'<text x="{sx(day):.1f}" y="{h - m["b"] + 26}" class="ax" text-anchor="middle">'
        f'{(today + timedelta(days=day)).strftime("%b %d")}</text>'
        for day in range(15, len(p5) + 1, 15)
    )
    band = (f'M {_polyline(days, p95, sx, sy).replace(" ", " L ")} '
            f'L {_polyline(list(reversed(days)), list(reversed(p5)), sx, sy).replace(" ", " L ")} Z')
    wire_ticks = "".join(
        f'<line x1="{sx(max(1, wi["day"])):.1f}" x2="{sx(max(1, wi["day"])):.1f}" '
        f'y1="{h - m["b"]}" y2="{h - m["b"] - 9}" stroke="{RED}" stroke-width="2" opacity="0.75">'
        f'<title>PO wire {_money(wi["amount"])} — {escape(str(wi["sku"]))}</title></line>'
        for wi in wires
    )
    ruin = ""
    if lo <= 0 <= hi:
        ruin = (f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{sy(0):.1f}" y2="{sy(0):.1f}" '
                f'stroke="{RED}" stroke-width="1.5" stroke-dasharray="7 5"/>'
                f'<text x="{w - m["r"]}" y="{sy(0) - 8:.1f}" class="lbl" fill="{RED}" '
                f'text-anchor="end">$0 — bridge-capital line</text>')

    mid = len(p5) * 2 // 3
    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="Simulated cash position, next {len(p5)} days">
  <defs><linearGradient id="cone" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{AMBER}" stop-opacity="0.28"/>
    <stop offset="1" stop-color="{AMBER}" stop-opacity="0.05"/>
  </linearGradient></defs>
  {grid}{xlabels}
  <path d="{band}" fill="url(#cone)"/>
  <polyline points="{_polyline(days, p5, sx, sy)}" fill="none" stroke="{AMBER}" stroke-width="1" opacity="0.5"/>
  <polyline points="{_polyline(days, p50, sx, sy)}" fill="none" stroke="{AMBER}" stroke-width="2.5"/>
  {ruin}{wire_ticks}
  <text x="{sx(mid):.1f}" y="{sy(p50[mid - 1]) - 12:.1f}" class="lbl" fill="{AMBER}">median path</text>
  <text x="{sx(mid):.1f}" y="{sy(p5[mid - 1]) + 18:.1f}" class="lbl" fill="{INK_60}">5th percentile — the bad quarter</text>
</svg>'''


def profit_curve_svg(sku: str, eps: float, p0: float, q0: float,
                     unit_cost: float, fee_rate: float, move: dict) -> str:
    lo_p, hi_p = p0 * 0.85, p0 * 1.15
    n = 80
    prices = [lo_p + (hi_p - lo_p) * i / (n - 1) for i in range(n)]
    profits = [profit(eps, p0, q0, unit_cost, fee_rate, p) for p in prices]

    w, h, m = 470, 300, {"l": 74, "r": 18, "t": 30, "b": 40}
    lo_y, hi_y = min(profits), max(profits)
    pad = (hi_y - lo_y) * 0.12 or 1
    sx = _Scale((lo_p, hi_p), (m["l"], w - m["r"]))
    sy = _Scale((lo_y - pad, hi_y + pad), (h - m["b"], m["t"]))

    star_p = move.get("destination")
    step_p = move["p_new"]
    peak_in_view = star_p is not None and lo_p <= star_p <= hi_p
    dot_p = star_p if peak_in_view else step_p
    dot_y = profit(eps, p0, q0, unit_cost, fee_rate, dot_p)
    if peak_in_view:
        dot_label = "P* — the optimum"
    elif star_p is not None:
        dot_label = f"next step (5% cap) → optimum ${star_p:.2f}"
    else:
        dot_label = "bounded test — inelastic, no interior optimum"

    grid = "".join(
        f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/>'
        f'<text x="{m["l"] - 8}" y="{sy(t) + 4:.1f}" class="ax" text-anchor="end">{_money(t)}</text>'
        for t in _ticks(lo_y - pad, hi_y + pad, 4)
    )
    xlabels = "".join(
        f'<text x="{sx(t):.1f}" y="{h - m["b"] + 24}" class="ax" text-anchor="middle">${t:,.2f}</text>'
        for t in _ticks(lo_p, hi_p, 4)
    )
    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="Profit versus price for {escape(sku)}">
  {grid}{xlabels}
  <polyline points="{_polyline(prices, profits, sx, sy)}" fill="none" stroke="{INK}" stroke-width="2"/>
  <line x1="{sx(p0):.1f}" x2="{sx(p0):.1f}" y1="{m["t"]}" y2="{h - m["b"]}"
        stroke="{INK_60}" stroke-width="1.2" stroke-dasharray="4 5"/>
  <text x="{sx(p0) + 6:.1f}" y="{m["t"] + 14}" class="lbl" fill="{INK_60}">today ${p0:.2f}</text>
  <circle cx="{sx(dot_p):.1f}" cy="{sy(dot_y):.1f}" r="6.5" fill="{AMBER}" class="glow"/>
  <text x="{sx(dot_p):.1f}" y="{sy(dot_y) - 14:.1f}" class="lbl" fill="{AMBER}"
        text-anchor="{'end' if dot_p > (lo_p + hi_p) / 2 else 'start'}">{escape(dot_label)}</text>
</svg>'''


def risk_scatter_svg(rows: list[dict]) -> str:
    w, h, m = 960, 320, {"l": 74, "r": 26, "t": 28, "b": 46}
    sx = _Scale((90, 0), (m["l"], w - m["r"]))  # reversed: time runs out to the right
    sy = _Scale((0, 1), (h - m["b"], m["t"]))

    grid = "".join(
        f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="grid"/>'
        f'<text x="{m["l"] - 10}" y="{sy(t) + 4:.1f}" class="ax" text-anchor="end">{t:.0%}</text>'
        for t in (0, 0.25, 0.5, 0.75, 1)
    )
    xlabels = "".join(
        f'<text x="{sx(t):.1f}" y="{h - m["b"] + 26}" class="ax" text-anchor="middle">{t}d</text>'
        for t in (90, 60, 30, 15, 0)
    )
    guide = (f'<line x1="{m["l"]}" x2="{w - m["r"]}" y1="{sy(RISK_WARNING):.1f}" y2="{sy(RISK_WARNING):.1f}" '
             f'stroke="{RED}" stroke-width="1" stroke-dasharray="6 6" opacity="0.55"/>'
             f'<text x="{w - m["r"]}" y="{sy(RISK_WARNING) - 7:.1f}" class="lbl" fill="{RED}" '
             f'text-anchor="end" opacity="0.8">directive threshold — {RISK_WARNING:.0%}</text>')

    dots = []
    for r in rows:
        p = float(r["stockout_probability"] or 0)
        cover = min(90.0, float(r["days_of_cover"] or 0))
        x, y = sx(cover), sy(p)
        danger = p >= RISK_CRITICAL and cover < DANGER_COVER_DAYS
        color = RED if danger else AMBER if p >= RISK_WARNING else SLATE
        tip = f'<title>{escape(str(r["sku"]))} — {p:.0%} stockout risk, {cover:.0f} days of cover</title>'
        if danger:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="none" stroke="{RED}" '
                        f'stroke-width="2" class="ping"/>')
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{7 if danger else 5.5}" fill="{color}" '
                    f'opacity="{1 if danger else 0.9}">{tip}</circle>')
        if p >= RISK_WARNING:
            dots.append(f'<text x="{x + 11:.1f}" y="{y + 4:.1f}" class="lbl" '
                        f'fill="{color}">{escape(str(r["sku"]))}</text>')
    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="Stockout probability vs days of cover per SKU">
  {grid}{xlabels}{guide}{"".join(dots)}
  <text x="{w - m["r"]}" y="{h - 6}" class="ax" text-anchor="end">days of cover — time runs out toward the right</text>
</svg>'''


def _select_price_curves(margins: list[dict], elasticity_rows: list[dict], limit: int = 2) -> list[dict]:
    if not margins:
        return []
    latest = max(m["period_start"] for m in margins)
    by_sku = {m["sku"]: m for m in margins if m["period_start"] == latest}
    picks = []
    for fit in elasticity_rows:
        if fit.get("status") != "ok" or fit.get("level") != "sku":
            continue
        row = by_sku.get(fit["item_id"])
        if not row:
            continue
        move = price_move(row, fit)
        if not move:
            continue
        units, revenue = float(row["units"] or 0), float(row["revenue"] or 0)
        picks.append({
            "sku": fit["item_id"],
            "eps": float(fit["elasticity"]),
            "p0": revenue / units,
            "q0": units,
            "unit_cost": float(row["cogs"]) / units,
            "fee_rate": min(0.9, max(0.0, float(row["amazon_fees"] or 0) / revenue)),
            "move": move,
        })
    picks.sort(key=lambda p: abs(p["move"]["expected_delta"] or 0), reverse=True)
    return picks[:limit]


def build_console(company: str, directives: list[dict], cash: dict | None,
                  margins: list[dict], elasticity_rows: list[dict],
                  inventory_rows: list[dict], generated_on: date) -> str:
    measured_rows = [d for d in directives if d.get("measured_impact_usd") is not None]
    measured = sum(float(d["measured_impact_usd"]) for d in measured_rows)
    on_desk = [d for d in directives if d["status"] == "issued"]

    # — cash panel —
    if cash:
        p_ruin = float(cash["p_ruin"] or 0)
        min_p5 = float(cash["min_p5"] or 0)
        breach = min_p5 < 0
        chip = (f'<span class="chip red">5% path breaches $0 — move a wire or line up bridge capital</span>'
                if breach else
                f'<span class="chip green">worst realistic case stays {_money(min_p5)} above zero</span>')
        pinch = (generated_on + timedelta(days=int(cash["min_p5_day"] or 0))).strftime("%b %d")
        cash_section = f'''<section class="panel">
  <header><h2>The cash horizon</h2>{chip}</header>
  <p class="sub mono">{cash["n_paths"]:,} simulated 90-day paths · payouts every {cash["details"]["payout_cycle_days"]} day{"s" if int(cash["details"]["payout_cycle_days"]) != 1 else ""} ·
     p(dip below $0) = {p_ruin:.1%} · tightest around {pinch}</p>
  {cash_cone_svg(cash, generated_on)}
  <p class="note">Red ticks are supplier PO wires already on the schedule. Inputs — {_money(cash["starting_cash"])} on hand,
     {_money(cash["monthly_fixed_costs"])}/mo fixed — are as stated by the client.</p>
</section>'''
    else:
        cash_section = f'''<section class="panel">
  <header><h2>The cash horizon</h2></header>
  <p class="note">Not armed yet — record the client's cash on hand and monthly fixed costs with
     <span class="mono">hubricon cash &lt;client&gt; --balance --opex</span> and this becomes the opening chart.</p>
</section>'''

    # — pricing panel —
    curves = _select_price_curves(margins, elasticity_rows)
    if curves:
        charts = "".join(
            f'''<figure><figcaption class="mono">{escape(c["sku"])} · ε = {c["eps"]:.2f} ·
  expected {"+" if (c["move"]["expected_delta"] or 0) >= 0 else "−"}{_money(c["move"]["expected_delta"])}/period</figcaption>
  {profit_curve_svg(c["sku"], c["eps"], c["p0"], c["q0"], c["unit_cost"], c["fee_rate"], c["move"])}</figure>'''
            for c in curves
        )
        pricing_section = f'''<section class="panel">
  <header><h2>The profit curve — dΠ/dP = 0</h2></header>
  <p class="sub mono">gross profit vs price from the fitted demand curve · moves capped at 5% per cycle, Buy Box watched</p>
  <div class="row">{charts}</div>
</section>'''
    else:
        pricing_section = ""

    # — inventory panel —
    scatter_rows = [r for r in inventory_rows
                    if r.get("stockout_probability") is not None and r.get("days_of_cover") is not None]
    inventory_section = f'''<section class="panel">
  <header><h2>The inventory map</h2></header>
  <p class="sub mono">every SKU: chance of stockout before a replenishment lands vs days of cover · Monte Carlo over demand and lead time</p>
  {risk_scatter_svg(scatter_rows)}
</section>''' if scatter_rows else ""

    # — moves on the desk —
    chips = {"issued": "amber", "approved": "green", "done": "green", "declined": "red"}
    moves = "".join(
        f'<li><span class="chip {chips.get(d["status"], "")}">{escape(d["status"])}</span> '
        f'{escape((d["action_text"] or "")[:160])}</li>'
        for d in directives[:6]
    )
    moves_section = f'''<section class="panel">
  <header><h2>This cycle&rsquo;s moves</h2></header>
  <ul class="moves">{moves}</ul>
</section>''' if directives else ""

    assumptions = ""
    if cash:
        assumptions = " · ".join(escape(a) for a in cash["details"].get("assumptions", []))

    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(company)} — Briefing Console</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&display=swap">
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ background: {NAVY_DEEP}; color: {INK}; font-family: Fraunces, Georgia, serif;
         padding: 48px clamp(20px, 5vw, 72px) 80px; }}
  .mono, .ax, .lbl, .chip {{ font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }}
  .masthead {{ display: flex; justify-content: space-between; align-items: baseline;
               border-bottom: 1px solid {EDGE}; padding-bottom: 18px; margin-bottom: 30px; }}
  .masthead h1 {{ font-size: 26px; font-weight: 600; letter-spacing: 0.01em; }}
  .masthead .mono {{ color: {INK_60}; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; }}
  .ledger {{ margin: 8px 0 34px; }}
  .ledger .big {{ font-size: clamp(44px, 7vw, 74px); font-weight: 600; color: {GREEN};
                  font-variant-numeric: tabular-nums; text-shadow: 0 0 34px rgba(16,185,129,0.35); }}
  .ledger .sub {{ color: {INK_60}; font-size: 13px; margin-top: 6px; }}
  section.panel {{ background: {PANEL}; border: 1px solid {EDGE}; border-radius: 10px;
                   backdrop-filter: blur(8px); padding: 24px 26px 18px; margin-bottom: 26px; }}
  section.panel header {{ display: flex; justify-content: space-between; align-items: center;
                          gap: 16px; flex-wrap: wrap; margin-bottom: 4px; }}
  h2 {{ font-size: 19px; font-weight: 600; }}
  .sub {{ color: {INK_60}; font-size: 12px; margin: 4px 0 14px; }}
  .note {{ color: {INK_60}; font-size: 12.5px; margin-top: 10px; font-style: italic; }}
  .chip {{ font-size: 11px; padding: 4px 10px; border-radius: 99px; border: 1px solid {EDGE};
           color: {INK_60}; white-space: nowrap; }}
  .chip.green {{ color: {GREEN}; border-color: rgba(16,185,129,0.5); }}
  .chip.red   {{ color: {RED}; border-color: rgba(239,68,68,0.55); }}
  .chip.amber {{ color: {AMBER}; border-color: rgba(255,192,0,0.5); }}
  svg {{ width: 100%; height: auto; display: block; }}
  svg .grid {{ stroke: rgba(255,255,255,0.07); stroke-width: 1; }}
  svg .ax {{ fill: {INK_35}; font-size: 11px; font-variant-numeric: tabular-nums; }}
  svg .lbl {{ font-size: 11.5px; }}
  .glow {{ filter: drop-shadow(0 0 7px {AMBER}); }}
  .row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 22px; }}
  figure figcaption {{ color: {INK_60}; font-size: 12px; margin-bottom: 6px; }}
  ul.moves {{ list-style: none; display: grid; gap: 10px; padding: 4px 0 8px; }}
  ul.moves li {{ font-size: 14.5px; line-height: 1.5; display: flex; gap: 12px; align-items: baseline; }}
  footer {{ color: {INK_35}; font-size: 11px; margin-top: 34px; line-height: 1.7; }}
  @keyframes ping {{ 0% {{ r: 7; opacity: 0.9; }} 100% {{ r: 16; opacity: 0; }} }}
  .ping {{ animation: ping 1.6s cubic-bezier(0, 0, 0.2, 1) infinite; }}
  @media (prefers-reduced-motion: reduce) {{ .ping {{ animation: none; opacity: 0.5; }} }}
</style></head><body>
<div class="masthead">
  <h1>{escape(company)}</h1>
  <span class="mono">Briefing console · {generated_on.strftime("%B %d, %Y")} · internal</span>
</div>
<div class="ledger">
  <div class="big">{_money(measured)}</div>
  <div class="sub mono">measured on the Decision Ledger across {len(measured_rows)} executed directive(s) ·
    {len(on_desk)} on the desk this cycle · measured, never projected</div>
</div>
{cash_section}
{pricing_section}
{inventory_section}
{moves_section}
<footer>{assumptions}{" · " if assumptions else ""}Generated by the Hubricon engine from the latest model run.
This console is the operator&rsquo;s instrument — the client receives the three-minute brief.</footer>
</body></html>'''
