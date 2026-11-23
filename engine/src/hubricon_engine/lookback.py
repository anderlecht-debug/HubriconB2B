"""The free look-back: what a brand's own past decisions cost or earned, in
hindsight, from the rows its store already holds.

Three kinds of past decision, each priced with a model the engine already
runs and nothing new:

  price changes   a SKU whose list price moved between periods
                  (models/shopify_findings.history). What the new price earned
                  against keeping the old one = profit per unit at the new
                  price times the units sold, less profit per unit at the old
                  price times the units the old price would have sold. Those
                  counterfactual units come from the SKU's own fitted demand
                  curve (models/elasticity.run) when one fits, its 95% interval
                  giving the range. When no curve fits, the range is the two
                  readings the store's own numbers allow: demand did not answer
                  the price at all, or every change in volume was the price.
                  Profit per unit is models/margin.run's net margin over units.

  stockout days   a SKU at zero sellable stock in the latest snapshot. Days out
                  = today less the day it last sold (a lower bound: it may have
                  run out after its last sale). The units missed are the
                  demand models/forecast.run fits on the periods BEFORE it ran
                  out, P10 to P90; profit per unit as above.

  slow stock      a SKU holding more than inventory_econ.HOLD_HORIZON_DAYS of
                  cover at its forecast rate. The excess is what sits past that
                  horizon; what it cost over the window is the capital it tied
                  up at inventory_econ.ANNUAL_CAPITAL_RATE. The range is the
                  excess at the forecast's P90 rate (less excess) and its P10.

Every figure is HINDSIGHT, NOT A SEALED CALL, and says so on itself: nothing
here was written down before the fact, so none of it is a promise kept and
none of it enters the Profit Record. A before/after on a store's own history
is confounded by whatever else changed that month; the ranges say how wide
the honest reading is, not that the truth must sit inside them.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import elasticity, forecast, margin, shopify_findings
from .models.common import latest_snapshot, num, period_days
from .models.inventory_econ import ANNUAL_CAPITAL_RATE, HOLD_HORIZON_DAYS

LABEL = "hindsight, not a sealed call"
UNKNOWN_MARGIN = "unknown"
DEFAULT_WINDOW_DAYS = 60
DATA_TABLES = ("asin_traffic", "sku_economics", "ppc_search_terms", "ppc_spend", "inventory_levels",
               "settlement_transactions", "customer_orders", "cogs_inputs", "fba_reimbursements",
               "fba_returns", "inventory_ledger", "inventory_health")


def complete(data: dict) -> dict:
    """Every table a model may read, present; a Shopify store fills four."""
    return {t: list(data.get(t) or []) for t in DATA_TABLES} | {k: v for k, v in data.items() if k not in DATA_TABLES}


def _safe(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:          # a model that cannot run on this store is a missing figure, not a crash
        return default


def unit_margins(margins: list[dict]) -> dict[str, float]:
    """{sku: net margin per unit}, over every period with a stated cost."""
    tot: dict[str, list[float]] = {}
    for m in margins:
        if m.get("cogs") is None or not m.get("units"):
            continue
        t = tot.setdefault(m["sku"], [0.0, 0.0])
        t[0] += float(m["net_margin"] or 0)
        t[1] += float(m["units"])
    return {s: v[0] / v[1] for s, v in tot.items() if v[1] > 0}


def _period_margin(margins: list[dict], sku: str, starts: set) -> float | None:
    rows = [m for m in margins if m["sku"] == sku and str(m["period_start"])[:10] in starts
            and m.get("cogs") is not None and m.get("units")]
    units = sum(float(m["units"]) for m in rows)
    return sum(float(m["net_margin"] or 0) for m in rows) / units if units else None


def _fit(rows: list[dict], sku: str) -> dict | None:
    f = next((r for r in rows if r.get("level") == "sku" and r.get("item_id") == sku), None)
    return f if f and f.get("status") == "ok" and f.get("elasticity") is not None else None


def _item(kind: str, sku: str, point, low, high, basis: str, **extra) -> dict:
    lo, hi = (None, None) if low is None or high is None else sorted((float(low), float(high)))
    return {"kind": kind, "sku": sku, "usd": num(point), "usd_low": num(lo), "usd_high": num(hi),
            "label": LABEL, "basis": basis, **extra}


# ── price changes ────────────────────────────────────────────────────────────

def price_changes(data: dict, margins: list[dict], fits: list[dict]) -> list[dict]:
    out = []
    for sku, hist in shopify_findings.history(data).items():
        regimes: list[list[dict]] = []
        for h in hist:
            if regimes and shopify_findings._same_price(regimes[-1][0]["price"], h["price"]):
                regimes[-1].append(h)
            else:
                regimes.append([h])
        # A single period priced between its neighbours, moving the same way,
        # is the week the change happened in: part old price, part new. It
        # belongs to neither side, so it is left out of both.
        i = 1
        while i < len(regimes) - 1:
            a, mid, b = regimes[i - 1][0]["price"], regimes[i][0]["price"], regimes[i + 1][0]["price"]
            if len(regimes[i]) == 1 and min(a, b) < mid < max(a, b):
                del regimes[i]
            else:
                i += 1
        econ = {str(r["period_start"])[:10]: r for r in data.get("sku_economics") or [] if r.get("sku") == sku}
        for before, after in zip(regimes, regimes[1:]):
            out.append(_price_change(sku, before, after, econ, margins, _fit(fits, sku)))
    return out


def _span(regime: list[dict], econ: dict) -> tuple[float, int, set]:
    starts = {h["day"].isoformat() for h in regime}
    units = sum(float(econ[s]["units_sold"] or 0) for s in starts if s in econ)
    days = sum(period_days(str(econ[s]["period_start"])[:10], str(econ[s]["period_end"])[:10]) for s in starts if s in econ)
    return units, days, starts


def _price_change(sku, before, after, econ, margins, fit) -> dict:
    p_old = sum(h["price"] for h in before) / len(before)
    p_new = sum(h["price"] for h in after) / len(after)
    q_old, d_old, s_old = _span(before, econ)
    q_new, d_new, s_new = _span(after, econ)
    m_old, m_new = _period_margin(margins, sku, s_old), _period_margin(margins, sku, s_new)
    head = dict(price_from=num(p_old), price_to=num(p_new), since=min(s_new), days_after=d_new,
                units_after=num(q_new, 1), units_per_day_before=num(q_old / d_old, 3) if d_old else None,
                units_per_day_after=num(q_new / d_new, 3) if d_new else None)
    if m_old is None or m_new is None or not d_new:
        return _item("price_change", sku, None, None, None,
                     "no unit cost on file for these periods, so the change cannot be priced", **head)
    earned = lambda q_cf: m_new * q_new - m_old * q_cf
    if fit:
        eps = float(fit["elasticity"])
        ci = (fit.get("details") or {}).get("ci95") or [eps, eps]
        cf = lambda e: q_new * (p_old / p_new) ** float(e)
        vals = [earned(cf(e)) for e in ci]
        return _item("price_change", sku, earned(cf(eps)), min(vals), max(vals),
                     f"your demand curve (elasticity {eps:.2f}, 95% interval {ci[0]:.2f} to {ci[1]:.2f}) says what "
                     f"the old price would have sold over the same {d_new} days", elasticity=num(eps, 4), **head)
    flat = earned(q_new)                                    # demand did not answer the price
    moved = earned(q_old / d_old * d_new) if d_old else flat  # every change in volume was the price
    return _item("price_change", sku, (flat + moved) / 2, flat, moved,
                 "no demand curve fits yet, so the range runs from 'demand ignored the price' to 'every change "
                 "in volume was the price'; the point is their midpoint", elasticity=None, **head)


# ── stockout days ────────────────────────────────────────────────────────────

def _last_sale(data: dict, sku: str) -> str | None:
    ends = [str(r["period_end"])[:10] for r in data.get("sku_economics") or []
            if r.get("sku") == sku and float(r.get("units_sold") or 0) > 0]
    return max(ends) if ends else None


def stockouts(data: dict, margins: list[dict], today: date, last_sold: dict | None = None) -> list[dict]:
    snap = latest_snapshot([r for r in data.get("inventory_levels") or [] if shopify_findings._is_shopify(r)])
    per_unit = unit_margins(margins)
    out = []
    for sku, inv in sorted(snap.items()):
        if inv.get("fulfillable_quantity") is None or int(inv["fulfillable_quantity"]) > 0:
            continue
        last = (last_sold or {}).get(sku) or _last_sale(data, sku)
        if not last:
            continue
        days_out = (today - date.fromisoformat(last)).days
        if days_out <= 0:
            continue
        before = [r for r in data.get("sku_economics") or [] if r.get("sku") == sku and str(r["period_end"])[:10] <= last]
        f = _safe(forecast.run, {**data, "sku_economics": before, "inventory_levels": []}, horizon_days=1, default=[])
        f = next((r for r in f if r.get("item_id") == sku and r.get("status") == "ok"), None)
        if f:
            rate, lo, hi = (float(f["daily_rate_point"]), float(f["daily_rate_p10"]), float(f["daily_rate_p90"]))
            how = f"{forecast.METHOD_LABEL.get(f['method'], f['method'])} on the periods before it ran out, P10 to P90"
        else:
            rates = [float(r["units_sold"] or 0) / period_days(str(r["period_start"])[:10], str(r["period_end"])[:10])
                     for r in before]
            if not rates:
                continue
            rate = sum(float(r["units_sold"] or 0) for r in before) / sum(
                period_days(str(r["period_start"])[:10], str(r["period_end"])[:10]) for r in before)
            lo, hi = min(rates), max(rates)
            how = "too little history for a forecast: its average rate, between its slowest and fastest period"
        m = per_unit.get(sku)
        head = dict(days_out=days_out, last_sold=last, units_per_day=num(rate, 3),
                    units_missed=num(rate * days_out, 1), units_missed_low=num(lo * days_out, 1),
                    units_missed_high=num(hi * days_out, 1))
        if m is None:
            out.append(_item("stockout", sku, None, None, None,
                             f"out of stock {days_out} days; no unit cost on file, so units only. {how}", **head))
            continue
        out.append(_item("stockout", sku, -rate * days_out * m, -lo * days_out * m, -hi * days_out * m,
                         f"out of stock since its last sale {days_out} days ago (at least); demand by {how}, "
                         f"times ${m:,.2f} profit a unit", **head))
    return out


# ── slow-moving stock ────────────────────────────────────────────────────────

def slow_stock(data: dict, forecasts: list[dict], today: date, window_days: int) -> list[dict]:
    snap = latest_snapshot([r for r in data.get("inventory_levels") or [] if shopify_findings._is_shopify(r)])
    cogs = {r["sku"]: r for r in data.get("cogs_inputs") or []}
    fc = {r["item_id"]: r for r in forecasts if r.get("status") == "ok" and r.get("level") == "sku"}
    econ = data.get("sku_economics") or []
    out = []
    for sku, inv in sorted(snap.items()):
        on_hand = int(inv.get("fulfillable_quantity") or 0)
        rows = [r for r in econ if r.get("sku") == sku]
        cost = margin.landed_unit_cost(cogs.get(sku), rows[-1] if rows else {"channel": "shopify"})
        if on_hand <= 0 or not cost:
            continue
        f = fc.get(sku)
        if f:
            rate, fast, slow = float(f["daily_rate_point"]), float(f["daily_rate_p90"]), float(f["daily_rate_p10"])
        else:
            days = sum(period_days(str(r["period_start"])[:10], str(r["period_end"])[:10]) for r in rows) or window_days
            rate = fast = slow = sum(float(r["units_sold"] or 0) for r in rows) / days
        excess = lambda r, held=on_hand: max(0.0, held - r * HOLD_HORIZON_DAYS)
        if excess(rate) <= 0:
            continue
        carry = cost * ANNUAL_CAPITAL_RATE * window_days / 365.0
        cover = on_hand / rate if rate > 0 else None
        out.append(_item("slow_stock", sku, -excess(rate) * carry, -excess(fast) * carry, -excess(slow) * carry,
                         f"{on_hand} units on hand is {'no sale in sight' if cover is None else f'{cover:,.0f} days'} "
                         f"of cover; the units past {HOLD_HORIZON_DAYS} days tied up ${cost:,.2f} each at "
                         f"{ANNUAL_CAPITAL_RATE:.0%} a year for {window_days} days",
                         on_hand=on_hand, days_of_cover=num(cover, 0), excess_units=num(excess(rate), 0),
                         cash_tied_up=num(excess(rate) * cost)))
    return out


# ── the look-back ────────────────────────────────────────────────────────────

def _money(v: float) -> str:
    return f"{'−' if v < 0 else ''}${abs(v):,.0f}"


def _sentence(it: dict) -> str:
    rng = (f" (range {_money(it['usd_low'])} to {_money(it['usd_high'])})"
           if it["usd_low"] is not None else "")
    if it["kind"] == "price_change":
        verb = "earned" if (it["usd"] or 0) >= 0 else "cost"
        what = (f"Moving {it['sku']} from ${it['price_from']:,.2f} to ${it['price_to']:,.2f} on {it['since']}")
        body = (f"{what} {verb} about {_money(abs(it['usd']))} over {it['days_after']} days{rng}."
                if it["usd"] is not None else f"{what}: not priced, no unit cost on file.")
    elif it["kind"] == "stockout":
        body = (f"{it['sku']} has been out of stock at least {it['days_out']} days, about "
                f"{it['units_missed']:,.0f} sales missed"
                + (f", costing about {_money(abs(it['usd']))} in profit{rng}." if it["usd"] is not None else "."))
    else:
        body = (f"{it['sku']} holds {f"{it['days_of_cover']:,.0f}" if it['days_of_cover'] is not None else 'unlimited'} days of stock; the "
                f"{it['excess_units']:,.0f} units past {HOLD_HORIZON_DAYS} days tie up "
                f"${it['cash_tied_up']:,.0f} and cost about {_money(abs(it['usd']))} in capital over the window{rng}.")
    if it.get("margin") == UNKNOWN_MARGIN:
        body += " No unit cost on file, so unknown margin and no profit figure (add its cost in Shopify)."
    return f"Hindsight, not a sealed call: {body}"


def run(data: dict, today: date | None = None, window_days: int = DEFAULT_WINDOW_DAYS,
        last_sold: dict | None = None) -> dict:
    """The brand's look-back over [today - window_days, today]. Pure: rows in,
    a payload out; the caller saves it."""
    today = today or date.today()
    start = (today - timedelta(days=window_days)).isoformat()
    data = complete(data)
    data["sku_economics"] = [r for r in data["sku_economics"] if str(r.get("period_end"))[:10] >= start
                             and shopify_findings._is_shopify(r)]
    # A cost-sheet row without a unit cost (Shopify's unitCost blank; freight
    # alone) is no cost on file: that SKU's margin is unknown, never guessed.
    data["cogs_inputs"] = [r for r in data["cogs_inputs"] if float(r.get("unit_cost_usd") or 0) > 0]
    costed = {r.get("sku") for r in data["cogs_inputs"]}
    margins = _safe(margin.run, data, default=[])
    fits = _safe(elasticity.run, data, default=[])
    forecasts = _safe(forecast.run, data, horizon_days=7, elasticity_rows=fits, default=[])
    items = (price_changes(data, margins, fits) + stockouts(data, margins, today, last_sold)
             + slow_stock(data, forecasts, today, window_days))
    for it in items:
        if it["sku"] not in costed:
            it.update(usd=None, usd_low=None, usd_high=None, margin=UNKNOWN_MARGIN)
    priced = [i for i in items if i["usd"] is not None]
    lows = [i["usd_low"] for i in priced if i["usd_low"] is not None]
    highs = [i["usd_high"] for i in priced if i["usd_high"] is not None]
    return {
        "label": LABEL,
        "window": {"start": start, "end": today.isoformat(), "days": window_days},
        "items": items,
        "total": {"usd": num(sum(i["usd"] for i in priced)), "usd_low": num(sum(lows)) if lows else None,
                  "usd_high": num(sum(highs)) if highs else None, "n_priced": len(priced), "label": LABEL},
        "summary": [_sentence(i) for i in sorted(items, key=lambda i: -abs(i["usd"] or 0))],
        "note": ("Every figure here is hindsight from your own orders and stock, not a call we sealed before the "
                 "fact. It is not on your Profit Record and no fee is charged on it."),
    }
