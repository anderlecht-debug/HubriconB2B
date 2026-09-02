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

from datetime import date

import numpy as np

from .console import _select_price_curves
from .directives import BRANDED_SPEND_MIN, INCREMENTALITY_MID, branded_spend
from .models.anomaly import summarize as summarize_anomalies
from .models.common import num
from .models.pricing_engine import profit

MAX_FANS = 3
MAX_CLAIMS = 8
MAX_SHARES = 8
SERIES_TAIL = 12
EXPIRING_WITHIN_DAYS = 14
ANOMALY_MIN_DOLLARS = 50.0    # per period, to appear on the Desk
ANOMALY_MIN_PCT = 0.02

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


def value_section(value: dict | None) -> dict | None:
    if not value:
        return None
    keys = ("value_total", "measured", "measured_count", "recovered", "recovered_count", "fees_paid",
            "billed_months", "monthly_fee", "roi_multiple", "identified_unbanked", "status", "engagement_start")
    return {k: value.get(k) for k in keys}


def health_section(health: dict | None) -> dict | None:
    if not health or health.get("status") != "ok":
        return None
    return {
        "status": "ok",
        "score": health["score"], "grade": health["grade"], "period": health.get("period"),
        "sub_scores": [{k: s.get(k) for k in ("key", "label", "score", "weight", "dollars_at_stake", "points_lost", "note")}
                       for s in health.get("sub_scores", [])],
        "top_drivers": health.get("top_drivers", []),
        "excluded": health.get("excluded", []),
    }


def claim_window_state(claim: dict, today: date) -> str:
    """Where a stored claim sits today: the DB holds the lifecycle
    (detected → filed → paid/denied); the window state is a function of
    the calendar."""
    status = claim.get("status") or "detected"
    if status != "detected":
        return status
    deadline = date.fromisoformat(str(claim["deadline"])[:10]) if claim.get("deadline") else None
    eligible = date.fromisoformat(str(claim["eligible_from"])[:10]) if claim.get("eligible_from") else today
    if deadline and today > deadline:
        return "expired"
    if today < eligible:
        return "not_yet_eligible"
    if deadline and (deadline - today).days <= EXPIRING_WITHIN_DAYS:
        return "expiring"
    return "open"


def money_found(claims: list[dict] | None, recovery: dict | None, today: date | None = None) -> dict | None:
    today = today or date.today()
    claims = claims or []
    if not claims and not (recovery and recovery.get("status") == "ok"):
        return None
    order = {"expiring": 0, "open": 1, "filed": 2, "not_yet_eligible": 3}
    staged = []
    for c in claims:
        state = claim_window_state(c, today)
        if state in order:
            deadline = date.fromisoformat(str(c["deadline"])[:10]) if c.get("deadline") else None
            staged.append({**c, "state": state, "days_left": (deadline - today).days if deadline else None})
    staged.sort(key=lambda c: (order[c["state"]], -float(c.get("value") or 0)))
    paid = [c for c in claims if c.get("status") == "paid"]
    summary = (recovery or {}).get("summary") or {}
    return {
        "n_claims": sum(1 for c in claims if c.get("status") != "dismissed"),
        "n_live": len(staged),
        "live_value": num(sum(float(c.get("value") or 0) for c in staged)),
        "live_ev": num(sum(float(c.get("expected_value") or 0) for c in staged)),
        "n_expiring": sum(1 for c in staged if c["state"] == "expiring"),
        "expiring_value": num(sum(float(c.get("value") or 0) for c in staged if c["state"] == "expiring")),
        "paid_total": num(sum(float(c.get("paid_amount") or 0) for c in paid)),
        "paid_count": len(paid),
        "reimbursed_90d": summary.get("reimbursed_90d"),
        "by_type": summary.get("by_type"),
        "claims": [{
            "claim_type": c["claim_type"], "sku": c.get("sku"), "order_id": c.get("order_id"),
            "units": c.get("units"), "value": num(float(c["value"])) if c.get("value") is not None else None,
            "status": c["state"], "days_left": c["days_left"],
            "deadline": str(c["deadline"])[:10] if c.get("deadline") else None,
            "eligible_from": str(c["eligible_from"])[:10] if c.get("eligible_from") else None,
        } for c in staged[:MAX_CLAIMS]],
    }


def forecast_fans(forecast_rows: list[dict] | None, margins: list[dict], max_skus: int = MAX_FANS) -> list[dict]:
    if not forecast_rows:
        return []
    _, latest = _latest_rows(margins)
    revenue = {m["sku"]: float(m.get("revenue") or 0) for m in latest}
    ok = [f for f in forecast_rows if f.get("status") == "ok" and f.get("level") == "sku"
          and (f.get("details") or {}).get("series")]
    ok.sort(key=lambda f: revenue.get(f["item_id"], 0), reverse=True)
    out = []
    for f in ok[:max_skus]:
        series = [{"t": p["period_start"], "rate": num(float(p["rate"]), 3)}
                  for p in f["details"]["series"][-SERIES_TAIL:] if p.get("rate") is not None]
        if len(series) < 3:
            continue
        out.append({
            "sku": f["item_id"], "method": f.get("method"),
            "fva_pct": f.get("fva_pct"), "mase": f.get("mase"), "naive_mase": f.get("naive_mase"),
            "series": series,
            "point": f.get("daily_rate_point"),
            "p10": f.get("daily_rate_p10"), "p25": f.get("daily_rate_p25"),
            "p75": f.get("daily_rate_p75"), "p90": f.get("daily_rate_p90"),
            "horizon_days": f.get("horizon_days"),
            "horizon_units_point": f.get("horizon_units_point"),
            "horizon_units_p10": f.get("horizon_units_p10"),
            "horizon_units_p90": f.get("horizon_units_p90"),
        })
    return out


def inventory_econ_section(inv_econ: dict | None) -> dict | None:
    if not inv_econ or inv_econ.get("status") != "ok":
        return None
    s = inv_econ["summary"]
    priced = [r for r in inv_econ["rows"] if r.get("critical_fractile") is not None]
    priced.sort(key=lambda r: float(r.get("unit_margin") or 0), reverse=True)
    return {
        "bleed": s.get("bleed"),
        "n_low_inventory_fee_risk": s.get("n_low_inventory_fee_risk"),
        "aged_units_181_plus": s.get("aged_units_181_plus"),
        "liquidation_candidates": s.get("liquidation_candidates"),
        "liquidation_value": s.get("liquidation_value"),
        "econ_orders": s.get("econ_orders"),
        "econ_wires_total": s.get("econ_wires_total"),
        "fee_schedule_effective": s.get("fee_schedule_effective"),
        "inventory_age_on_file": s.get("inventory_age_on_file"),
        "service_levels": [{"sku": r["sku"], "critical_fractile": r["critical_fractile"],
                            "service_level_current_policy": r.get("service_level_current_policy"),
                            "unit_margin": r.get("unit_margin")} for r in priced[:6]],
        "n_skus": s.get("n_skus"),
    }


def risk_section(risk: dict | None, margins: list[dict]) -> dict | None:
    if not risk:
        return None
    out = {}
    var = risk.get("var") or {}
    if var.get("status") == "ok":
        out["var"] = {k: var.get(k) for k in ("status", "expected_net", "var_95", "cvar_95", "var_99", "cvar_99",
                                              "worst_5pct_net", "p5_net", "p50_net", "n_paths", "skus_modeled")}
    conc = ((risk.get("concentration") or {}).get("sku_revenue")) or {}
    if conc.get("hhi") is not None:
        _, latest = _latest_rows(margins)
        total = sum(float(m.get("revenue") or 0) for m in latest)
        shares = sorted(((m["sku"], float(m.get("revenue") or 0) / total) for m in latest if total > 0),
                        key=lambda x: x[1], reverse=True)[:MAX_SHARES]
        out["concentration"] = {
            **{k: conc.get(k) for k in ("hhi", "effective_n", "top_item", "top_share", "level",
                                        "dollar_at_risk_top_item", "n")},
            "shares": [{"item": s, "share": num(v, 4)} for s, v in shares],
        }
    rr = risk.get("returns_reserve") or {}
    if rr.get("status") == "ok":
        out["returns_reserve"] = {k: rr.get(k) for k in ("expected", "p95", "return_rate_pct", "returned_units")}
    return out or None


def anomalies_section(anomaly_rows: list[dict] | None) -> dict | None:
    if not anomaly_rows:
        return None
    s = summarize_anomalies(anomaly_rows)
    if not s["flagged"]:
        return None
    seen, top = set(), []
    flagged = sorted((r for r in anomaly_rows if r.get("flagged")),
                     key=lambda r: (r.get("dollar_impact") or 0, r.get("detector") == "changepoint"), reverse=True)
    for r in flagged:
        key = (r.get("scope"), r.get("item_id"), r.get("metric"))
        if key in seen:
            continue
        # materiality: a statistically real 1% shift on a quiet series is not
        # a story worth a client's attention; Buy Box moves always are
        material = (r.get("dollar_impact") or 0) >= ANOMALY_MIN_DOLLARS or r.get("metric") == "buy_box_pct"
        if not material or (r.get("delta_pct") is not None and abs(float(r["delta_pct"])) < ANOMALY_MIN_PCT
                            and r.get("metric") != "buy_box_pct"):
            continue
        seen.add(key)
        top.append({
            **{k: r.get(k) for k in ("scope", "item_id", "metric", "detector", "direction", "since",
                                     "baseline", "current", "delta", "delta_pct", "dollar_impact")},
            "series": ((r.get("details") or {}).get("series") or [])[-SERIES_TAIL:],
        })
        if len(top) == 6:
            break
    return {"flagged": s["flagged"], "dollar_impact_total": s["dollar_impact_total"], "top": top}


def build_pack(margins, fits, inventory_rows, ads_rows, search_terms, brand_terms, *,
               value=None, health=None, claims=None, recovery=None, forecast_rows=None,
               inv_econ=None, risk=None, anomaly_rows=None, today=None) -> dict:
    sections = {
        "value": value_section(value),
        "health": health_section(health),
        "waterfall": waterfall(margins),
        "sku_stacks": sku_stacks(margins),
        "money_found": money_found(claims, recovery, today),
        "elasticity": elasticity_curves(fits),
        "profit_curves": profit_curves(margins, fits),
        "forecast_fans": forecast_fans(forecast_rows, margins),
        "ad_curves": ad_curves(ads_rows),
        "bleed": bleed(ads_rows),
        "brand": brand_range(search_terms, brand_terms),
        "inventory_econ": inventory_econ_section(inv_econ),
        "risk": risk_section(risk, margins),
        "anomalies": anomalies_section(anomaly_rows),
        "risk_map": risk_map(inventory_rows),
    }
    return {k: v for k, v in sections.items() if v}
