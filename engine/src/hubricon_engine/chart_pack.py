"""The chart pack — model output re-cut as chart-shaped deliverables.

The Desk never touches raw model tables (engine lockdown). What it draws
comes from here: per run, the engine publishes one JSON payload holding
exactly the series the Chart Book specifies — the margin waterfall, the
per-SKU stacks, fitted demand curves with their 95% bands, the profit
parabolas with the capped step and P*, ad saturation curves, the bleed
Pareto, the branded-spend range, and the inventory risk map. All curve
math happens here in Python, on the same functions the directives use,
so a chart can never disagree with the instruction beside it.
"""

import numpy as np

from .console import _select_price_curves
from .directives import BRANDED_SPEND_MIN, INCREMENTALITY_MID, branded_spend
from .models.common import num
from .models.pricing_engine import profit

TOP_SKUS = 6
CURVE_POINTS = 48
MAX_SKU_CURVES = 2
MAX_AD_CURVES = 2
TOP_BLEED_TERMS = 6
INCREMENTALITY_LO, INCREMENTALITY_HI = 0.25, 0.60


def _latest_rows(margins: list[dict]) -> tuple[str | None, list[dict]]:
    if not margins:
        return None, []
    latest = max(m["period_start"] for m in margins)
    return latest, [m for m in margins if m["period_start"] == latest]


def waterfall(margins: list[dict]) -> dict | None:
    latest, rows = _latest_rows(margins)
    if not rows:
        return None
    tot = lambda k: sum(float(r[k] or 0) for r in rows)
    return {
        "period": latest,
        "revenue": num(tot("revenue")),
        "fees": num(tot("amazon_fees")),
        "cogs": num(tot("cogs")),
        "ads": num(tot("ad_spend_allocated")),
        "net": num(tot("net_margin")),
    }


def sku_stacks(margins: list[dict]) -> list[dict]:
    _, rows = _latest_rows(margins)
    rows = sorted((r for r in rows if float(r["revenue"] or 0) > 0),
                  key=lambda r: float(r["revenue"]), reverse=True)[:TOP_SKUS]
    return [{
        "sku": r["sku"],
        "revenue": num(float(r["revenue"])),
        "fees": num(float(r["amazon_fees"] or 0)),
        "cogs": num(float(r["cogs"] or 0)),
        "ads": num(float(r["ad_spend_allocated"] or 0)),
        "net": num(float(r["net_margin"] or 0)),
    } for r in rows]


def elasticity_curves(fits: list[dict], max_skus: int = 4) -> list[dict]:
    """Fitted demand curves with 95% bands, pivoted on the observed
    centroid — the band pinches where the data actually is."""
    out = []
    ok = [f for f in fits
          if f.get("status") == "ok" and f.get("level") == "sku"
          and (f.get("details") or {}).get("points")]
    ok.sort(key=lambda f: float(f.get("r_squared") or 0), reverse=True)
    for f in ok[:max_skus]:
        pts = f["details"]["points"]
        prices = np.array([float(p["price"]) for p in pts])
        units = np.array([float(p["units"]) for p in pts])
        if len(prices) < 3 or (units <= 0).any() or (prices <= 0).any():
            continue
        e = float(f["elasticity"])
        mean_lp, mean_lu = float(np.mean(np.log(prices))), float(np.mean(np.log(units)))
        grid = np.linspace(prices.min() * 0.95, prices.max() * 1.05, CURVE_POINTS)

        def u_at(eps):
            return np.exp(mean_lu - eps * mean_lp) * grid ** eps

        mid = u_at(e)
        ci = (f.get("details") or {}).get("ci95")
        band = None
        if ci:
            lo_u, hi_u = u_at(float(ci[0])), u_at(float(ci[1]))
            band = [{"p": num(float(p)), "lo": num(float(min(a, b)), 1), "hi": num(float(max(a, b)), 1)}
                    for p, a, b in zip(grid, lo_u, hi_u)]
        out.append({
            "sku": f["item_id"],
            "eps": num(e, 3),
            "ci95": [num(float(c), 3) for c in ci] if ci else None,
            "r2": num(float(f.get("r_squared") or 0), 3),
            "points": [{"p": num(float(p)), "u": num(float(u), 1)} for p, u in zip(prices, units)],
            "curve": [{"p": num(float(p)), "u": num(float(u), 1)} for p, u in zip(grid, mid)],
            "band": band,
        })
    return out


def profit_curves(margins: list[dict], fits: list[dict]) -> list[dict]:
    out = []
    for c in _select_price_curves(margins, fits, limit=MAX_SKU_CURVES):
        lo_p, hi_p = c["p0"] * 0.85, c["p0"] * 1.15
        grid = np.linspace(lo_p, hi_p, CURVE_POINTS)
        curve = [{"p": num(float(p)), "profit": num(profit(c["eps"], c["p0"], c["q0"],
                                                          c["unit_cost"], c["fee_rate"], float(p)))}
                 for p in grid]
        move = c["move"]
        out.append({
            "sku": c["sku"],
            "eps": num(c["eps"], 3),
            "p0": num(c["p0"]),
            "p_new": num(move["p_new"]),
            "p_star": num(move["destination"]) if move.get("destination") else None,
            "expected_delta": num(move["expected_delta"]),
            "delta_range": [num(v) for v in move["delta_range"]] if move.get("delta_range") else None,
            "curve": curve,
        })
    return out


def ad_curves(ads_rows: list[dict]) -> list[dict]:
    ok = [r for r in ads_rows if r.get("status") == "ok" and r.get("curve_params")]
    ok.sort(key=lambda r: float(r.get("current_spend") or 0), reverse=True)
    out = []
    for r in ok[:MAX_AD_CURVES]:
        p = r["curve_params"]
        top = max(float(r.get("current_spend") or 1), float(r.get("breakeven_spend") or 1)) * 1.6
        grid = np.linspace(0.01, top, CURVE_POINTS)
        if r["curve_model"] == "hill":
            y = p["a"] * grid ** p["h"] / (p["k"] ** p["h"] + grid ** p["h"])
        else:
            y = p["a"] * np.log1p(p["k"] * grid) if "k" in p else p["a"] * np.log1p(grid)
        out.append({
            "name": r["campaign_name"],
            "curve": [{"s": num(float(s)), "y": num(float(v))} for s, v in zip(grid, y)],
            "current": num(float(r["current_spend"])) if r.get("current_spend") else None,
            "breakeven": num(float(r["breakeven_spend"])) if r.get("breakeven_spend") else None,
            "marginal_roas": num(float(r["marginal_roas"]), 3) if r.get("marginal_roas") is not None else None,
        })
    return out


def bleed(ads_rows: list[dict]) -> dict | None:
    terms = [t for r in ads_rows for t in (r.get("bleed_terms") or []) if (t.get("spend") or 0) > 0]
    if not terms:
        return None
    terms.sort(key=lambda t: float(t["spend"]), reverse=True)
    top = terms[:TOP_BLEED_TERMS]
    total = sum(float(t["spend"]) for t in terms)
    other = total - sum(float(t["spend"]) for t in top)
    return {
        "total": num(total),
        "terms": [{"term": t["search_term"] if "search_term" in t else t.get("term", "—"),
                   "spend": num(float(t["spend"]))} for t in top],
        "other": num(other),
        "n_terms": len(terms),
    }


def brand_range(search_terms: list[dict], brand_terms: list[str]) -> dict | None:
    spend, n = branded_spend(search_terms or [], brand_terms or [])
    if spend < BRANDED_SPEND_MIN:
        return None
    return {
        "spend": num(spend),
        "n_terms": n,
        "lo": num(spend * INCREMENTALITY_LO),
        "hi": num(spend * INCREMENTALITY_HI),
        "expected": num(spend * INCREMENTALITY_MID),
    }


def risk_map(inventory_rows: list[dict]) -> list[dict]:
    return [{
        "sku": r["sku"],
        "p": num(float(r["stockout_probability"]), 4),
        "cover": num(min(90.0, float(r["days_of_cover"])), 1),
    } for r in inventory_rows
        if r.get("stockout_probability") is not None and r.get("days_of_cover") is not None]


def build_pack(margins, fits, inventory_rows, ads_rows, search_terms, brand_terms) -> dict:
    sections = {
        "waterfall": waterfall(margins),
        "sku_stacks": sku_stacks(margins),
        "elasticity": elasticity_curves(fits),
        "profit_curves": profit_curves(margins, fits),
        "ad_curves": ad_curves(ads_rows),
        "bleed": bleed(ads_rows),
        "brand": brand_range(search_terms, brand_terms),
        "risk_map": risk_map(inventory_rows),
    }
    return {k: v for k, v in sections.items() if v}
