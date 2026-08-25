"""Diminishing-returns curve per campaign.

Fits sales as a saturating function of spend — Hill first, log fallback —
then reads off the marginal ROAS at current spend and the spend level where
marginal ROAS crosses break-even. Break-even defaults to marginal ROAS = 1
(pure revenue); when the margin model produced an average contribution
margin, the threshold becomes 1/margin so ads break even on profit.
"""

import numpy as np
from scipy.optimize import curve_fit

from .common import num

MIN_POINTS = 5
BLEED_SPEND_THRESHOLD = 10.0


def _hill(s, a, k, h):
    return a * s**h / (k**h + s**h)


def _log_curve(s, a, b):
    return a * np.log1p(b * s)


def _fit_curve(spend: np.ndarray, sales: np.ndarray):
    try:
        p0 = (float(sales.max()) * 1.5 or 1.0, float(np.median(spend)) or 1.0, 1.0)
        params, _ = curve_fit(
            _hill, spend, sales, p0=p0,
            bounds=([0, 1e-6, 0.5], [np.inf, np.inf, 3.0]), maxfev=20000,
        )
        return "hill", params
    except (RuntimeError, ValueError):
        pass
    try:
        params, _ = curve_fit(
            _log_curve, spend, sales, p0=(float(sales.max()) or 1.0, 0.1),
            bounds=([0, 1e-9], [np.inf, np.inf]), maxfev=20000,
        )
        return "log", params
    except (RuntimeError, ValueError):
        return None, None


def _marginal(model: str, params, s: float) -> float:
    eps = max(s, 1.0) * 1e-4
    f = _hill if model == "hill" else _log_curve
    return float((f(s + eps, *params) - f(max(s - eps, 0.0), *params)) / (s + eps - max(s - eps, 0.0)))


def _breakeven(model: str, params, max_spend: float, threshold: float) -> float | None:
    """Largest spend where the marginal dollar still returns `threshold`."""
    grid = np.linspace(max_spend * 3, max_spend * 0.01, 400)
    for s in grid:
        if _marginal(model, params, float(s)) >= threshold:
            return float(s)
    return None


def _bleed_terms(rows: list[dict]) -> list[dict]:
    bleeding = [
        r for r in rows
        if (r["spend"] or 0) > BLEED_SPEND_THRESHOLD and not (r["sales_7d"] or 0)
    ]
    bleeding.sort(key=lambda r: r["spend"], reverse=True)
    return [
        {"search_term": r["search_term"], "spend": num(r["spend"]), "clicks": r["clicks"]}
        for r in bleeding[:25]
    ]


def run(data: dict, rng=None, simulations=None, avg_margin: float | None = None) -> list[dict]:
    threshold = 1.0 / avg_margin if avg_margin and avg_margin > 0 else 1.0

    terms_by_campaign: dict[str, list[dict]] = {}
    for row in data["ppc_search_terms"]:
        terms_by_campaign.setdefault(row["campaign_name"], []).append(row)

    # Daily points from ppc_spend when present, else one aggregate point per
    # (campaign, period) from the search-term uploads.
    points_by_campaign: dict[str, list[tuple[float, float]]] = {}
    for row in data["ppc_spend"]:
        if row["spend"] is not None:
            points_by_campaign.setdefault(row["campaign_name"] or row["campaign_id"], []).append(
                (float(row["spend"]), float(row["sales"] or 0))
            )
    if not points_by_campaign:
        per_period: dict[tuple, list[float]] = {}
        for row in data["ppc_search_terms"]:
            key = (row["campaign_name"], row["period_start"], row["period_end"])
            bucket = per_period.setdefault(key, [0.0, 0.0])
            bucket[0] += row["spend"] or 0
            bucket[1] += row["sales_7d"] or 0
        for (campaign, _, _), (spend, sales) in per_period.items():
            points_by_campaign.setdefault(campaign, []).append((spend, sales))

    results = []
    for campaign in sorted(set(points_by_campaign) | set(terms_by_campaign)):
        points = [(s, v) for s, v in points_by_campaign.get(campaign, []) if s > 0]
        bleed = _bleed_terms(terms_by_campaign.get(campaign, []))
        spend = np.array([p[0] for p in points])
        sales = np.array([p[1] for p in points])
        current_spend = float(spend.mean()) if len(points) else None
        base = {
            "campaign_name": campaign,
            "current_spend": num(current_spend),
            "current_sales": num(float(sales.mean())) if len(points) else None,
            "bleed_terms": bleed,
            "details": {"n_points": len(points), "breakeven_marginal_roas": num(threshold, 4)},
        }
        if len(points) < MIN_POINTS:
            results.append({**base, "status": "insufficient_data"})
            continue
        model, params = _fit_curve(spend, sales)
        if model is None:
            results.append({**base, "status": "insufficient_data"})
            continue
        breakeven = _breakeven(model, params, float(spend.max()), threshold)
        results.append(
            {
                **base,
                "status": "ok",
                "curve_model": model,
                "curve_params": {k: num(v, 6) for k, v in zip(("a", "k", "h")[: len(params)], params)},
                "marginal_roas": num(_marginal(model, params, current_spend), 4),
                "breakeven_spend": num(breakeven),
                "recommended_spend": num(breakeven),
            }
        )
    return results
