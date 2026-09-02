"""The Health Score — one explainable number, every point tied to dollars.

Six sub-scores, each 0–100, weighted and renormalised over whichever ones
the data can support (a missing cash input excludes the cash score rather
than faking a 50). Every sub-score carries the dollar figure behind its
deduction so the score decomposes into causes a client can act on — the
report's "dollar-weighted driver decomposition".

    margin         blended net margin vs the 15–20% benchmark for a
                   $1M+ private-label seller; loss-making SKUs' losses
    cash           ruin probability and the 5th-percentile cash low
    concentration  HHI of SKU revenue (DOJ/FTC 1,800 threshold)
    inventory      revenue-weighted stockout risk + fee bleed
    advertising    TACoS (ad spend / total revenue) and zero-sale bleed
    signal         data completeness and forecastability (FVA vs naive)

Grades: A ≥ 85, B ≥ 70, C ≥ 55, D ≥ 40, else E. The thresholds are
stated, not learned — there is no training set of "healthy" sellers to
learn from yet, and a stated rule can be argued with.
"""

from .common import num

WEIGHTS = {"margin": 0.25, "cash": 0.20, "concentration": 0.15,
           "inventory": 0.20, "advertising": 0.10, "signal": 0.10}
LABELS = {"margin": "Margin health", "cash": "Cash runway", "concentration": "Concentration risk",
          "inventory": "Inventory position", "advertising": "Advertising efficiency",
          "signal": "Data & forecastability"}
CORE_REPORTS = ("sku_economics", "cogs_inputs", "inventory_levels", "ppc_search_terms", "ppc_spend", "asin_traffic")
BLEED_REPORTS = ("inventory_ledger", "fba_reimbursements", "fba_returns", "inventory_health", "settlement_transactions")


def _interp(x: float, points: list[tuple[float, float]]) -> float:
    """Piecewise-linear map through (x, score) points sorted by x."""
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def grade(score: float) -> str:
    return "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "E"


def _latest(margin_rows):
    if not margin_rows:
        return None, []
    latest = max(m["period_start"] for m in margin_rows)
    return latest, [m for m in margin_rows if m["period_start"] == latest]


def compute(margin_rows: list[dict], cash: dict | None = None, risk: dict | None = None,
            inventory_rows: list[dict] | None = None, inv_econ: dict | None = None,
            ads_rows: list[dict] | None = None, forecast_rows: list[dict] | None = None,
            recovery: dict | None = None, data_present: dict | None = None) -> dict:
    subs: list[dict] = []
    excluded: list[str] = []
    latest, rows = _latest(margin_rows)
    revenue = sum(float(m.get("revenue") or 0) for m in rows)
    net = sum(float(m.get("net_margin") or 0) for m in rows)
    ads = sum(float(m.get("ad_spend_allocated") or 0) for m in rows)

    # — margin —
    if revenue > 0:
        pct = net / revenue
        losses = sum(abs(float(m["net_margin"])) for m in rows if m.get("net_margin") is not None and float(m["net_margin"]) < 0)
        loss_share = sum(float(m.get("revenue") or 0) for m in rows
                         if m.get("net_margin") is not None and float(m["net_margin"]) < 0) / revenue
        score = _interp(pct, [(0.0, 0), (0.05, 25), (0.10, 50), (0.15, 75), (0.20, 100)]) * (1 - 0.5 * loss_share)
        subs.append({"key": "margin", "score": score, "dollars_at_stake": losses,
                     "note": f"{pct:.1%} blended net margin; loss-making SKUs cost ${losses:,.0f} last period"})
    else:
        excluded.append("margin")

    # — cash —
    if cash:
        p_ruin = float(cash.get("p_ruin") or 0)
        min_p5 = float(cash.get("min_p5") or 0)
        score = 100 * (1 - min(1.0, p_ruin / 0.15))
        if min_p5 < 0:
            score = min(score, 40.0)
        subs.append({"key": "cash", "score": score, "dollars_at_stake": max(0.0, -min_p5),
                     "note": (f"{p_ruin:.0%} of simulated 90-day paths touch $0; "
                              f"bad-quarter low {'$' + format(min_p5, ',.0f')}")})
    else:
        excluded.append("cash")

    # — concentration —
    conc = ((risk or {}).get("concentration") or {}).get("sku_revenue")
    if conc and conc.get("status", "ok") == "ok" and conc.get("hhi") is not None:
        hhi = float(conc["hhi"])
        score = _interp(hhi, [(1000, 100), (1800, 60), (2500, 45), (5000, 15), (10000, 5)])
        subs.append({"key": "concentration", "score": score,
                     "dollars_at_stake": float(conc.get("dollar_at_risk_top_item") or 0),
                     "note": (f"HHI {hhi:,.0f} — {conc.get('top_share', 0) * 100:.0f}% of revenue on "
                              f"{conc.get('top_item')}; one suppressed listing costs "
                              f"${float(conc.get('dollar_at_risk_top_item') or 0):,.0f}/period")})
    else:
        excluded.append("concentration")

    # — inventory —
    if inventory_rows and revenue > 0:
        rev_by_sku = {m["sku"]: float(m.get("revenue") or 0) for m in rows}
        weighted = sum(rev_by_sku.get(r["sku"], 0) * float(r.get("stockout_probability") or 0) for r in inventory_rows)
        covered = sum(rev_by_sku.get(r["sku"], 0) for r in inventory_rows) or revenue
        w_p = weighted / covered
        bleed = float((((inv_econ or {}).get("summary") or {}).get("bleed") or {}).get("total_month") or 0)
        stock_score = 100 * (1 - min(1.0, w_p / 0.5))
        bleed_score = 100 * (1 - min(1.0, (bleed / revenue) / 0.05))
        subs.append({"key": "inventory", "score": 0.6 * stock_score + 0.4 * bleed_score, "dollars_at_stake": bleed,
                     "note": (f"revenue-weighted stockout risk {w_p:.0%}; "
                              f"fee bleed (aged, low-inventory, peak storage) ${bleed:,.0f}/month")})
    else:
        excluded.append("inventory")

    # — advertising —
    if revenue > 0 and ads > 0:
        tacos = ads / revenue
        bleed = sum(float(t.get("spend") or 0) for r in (ads_rows or []) for t in (r.get("bleed_terms") or []))
        excess = sum(max(0.0, float(r.get("current_spend") or 0) - float(r.get("breakeven_spend") or 0))
                     for r in (ads_rows or []) if r.get("status") == "ok" and r.get("breakeven_spend"))
        score = _interp(tacos, [(0.10, 100), (0.15, 80), (0.25, 50), (0.40, 10)]) * (1 - min(0.5, bleed / ads))
        subs.append({"key": "advertising", "score": score, "dollars_at_stake": bleed + excess * 30,
                     "note": f"TACoS {tacos:.1%}; ${bleed:,.0f} zero-sale spend, ${excess * 30:,.0f}/month past break-even"})
    elif revenue > 0:
        subs.append({"key": "advertising", "score": 100.0, "dollars_at_stake": 0.0, "note": "no ad spend allocated"})
    else:
        excluded.append("advertising")

    # — signal —
    present = data_present or {}
    core = sum(1 for k in CORE_REPORTS if present.get(k)) / len(CORE_REPORTS)
    bleed_cov = sum(1 for k in BLEED_REPORTS if present.get(k)) / len(BLEED_REPORTS)
    ok_fc = [f for f in (forecast_rows or []) if f.get("status") == "ok" and f.get("mase") is not None]
    mase = sum(float(f["mase"]) for f in ok_fc) / len(ok_fc) if ok_fc else None
    score = 60 * core + 40 * bleed_cov
    if mase is not None and mase > 1:
        score -= 20
    open_ev = float(((recovery or {}).get("summary") or {}).get("live_ev") or 0)
    subs.append({"key": "signal", "score": max(0.0, score), "dollars_at_stake": open_ev,
                 "note": (f"{core:.0%} of core exports and {bleed_cov:.0%} of recovery exports on file"
                          + (f"; forecast MASE {mase:.2f} vs naive 1.00" if mase is not None else "")
                          + (f"; ${open_ev:,.0f} of expected reimbursements unclaimed" if open_ev else ""))})

    total_w = sum(WEIGHTS[s["key"]] for s in subs)
    if total_w == 0 or all(s["key"] == "signal" for s in subs):
        return {"status": "insufficient_data", "score": None, "grade": None, "sub_scores": [], "excluded": excluded}
    score = sum(WEIGHTS[s["key"]] / total_w * s["score"] for s in subs)
    for s in subs:
        s["label"] = LABELS[s["key"]]
        s["weight"] = num(WEIGHTS[s["key"]] / total_w, 4)
        s["score"] = num(s["score"], 1)
        s["dollars_at_stake"] = num(s["dollars_at_stake"])
        s["points_lost"] = num((100 - s["score"]) * WEIGHTS[s["key"]] / total_w, 1)
    drivers = sorted(subs, key=lambda s: (s["dollars_at_stake"] or 0), reverse=True)[:3]
    return {
        "status": "ok",
        "score": num(score, 1),
        "grade": grade(score),
        "period": latest,
        "sub_scores": subs,
        "top_drivers": [{"key": s["key"], "label": s["label"], "dollars_at_stake": s["dollars_at_stake"],
                         "points_lost": s["points_lost"], "note": s["note"]} for s in drivers],
        "excluded": excluded,
        "basis": ("Weighted average of the sub-scores shown, weights renormalised over the ones the data supports; "
                  "each sub-score states the dollars behind its deduction."),
    }
