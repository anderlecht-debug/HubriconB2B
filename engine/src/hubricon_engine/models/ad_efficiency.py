"""Diminishing-returns curve per campaign.

Fits sales as a saturating function of spend — Hill first, log fallback —
then reads off the marginal ROAS at current spend and the spend level where
marginal ROAS crosses break-even. Break-even defaults to marginal ROAS = 1
(pure revenue); when the margin model produced an average contribution
margin, the threshold becomes 1/margin so ads break even on profit.

BOTH OF THOSE NUMBERS CARRY AN INTERVAL. A break-even spend fitted from eight
daily points is an estimate, and a campaign trim sized against it is a promise
built on that estimate — so `curve_fit`'s parameter covariance is propagated
rather than discarded. Parameters are drawn from their asymptotic normal
posterior, the marginal ROAS and the break-even are recomputed on every draw,
and the 5th/50th/95th percentiles are published beside the point estimate. A fit
whose covariance is not finite — too few points, a flat response, a boundary
solution — reports the point estimate with `interval_basis: "unavailable"`
rather than a range it cannot support.

The intervals are conditional on the curve FORM being right, which is the
assumption no amount of bootstrap resampling can test. Named in MATH_METHODS.md.
"""

import numpy as np
from scipy.optimize import curve_fit

from .common import num
from .mc import quantiles_with_se

MIN_POINTS = 5
BLEED_SPEND_THRESHOLD = 10.0
# A campaign whose spend never moved cannot have a response curve fitted to it,
# the same way a SKU with one price cannot have an elasticity. curve_fit will
# still converge — onto an arbitrary point of a flat likelihood ridge, with a
# zero covariance that reads as certainty — so the guard runs before the fit and
# the answer is a status. Mirrors elasticity.MIN_PRICE_CV.
MIN_SPEND_CV = 0.02
# Parameter draws behind the published interval on marginal ROAS and break-even
# spend. Each draw re-solves the break-even by the same grid search the point
# estimate uses, so 400 is the trade: enough for a 5th/95th percentile, cheap
# enough to run on every campaign of a real account.
CURVE_DRAWS = 400
CURVE_SEED = 20260911


def _hill(s, a, k, h):
    return a * s**h / (k**h + s**h)


def _log_curve(s, a, b):
    return a * np.log1p(b * s)


def _fit_curve(spend: np.ndarray, sales: np.ndarray, with_cov: bool = False):
    """(model, params) or (model, params, covariance) when `with_cov`.

    The covariance is curve_fit's asymptotic one and may be non-finite at a
    boundary solution or with too few points; callers check rather than assume."""
    try:
        p0 = (float(sales.max()) * 1.5 or 1.0, float(np.median(spend)) or 1.0, 1.0)
        params, cov = curve_fit(
            _hill, spend, sales, p0=p0,
            bounds=([0, 1e-6, 0.5], [np.inf, np.inf, 3.0]), maxfev=20000,
        )
        return ("hill", params, cov) if with_cov else ("hill", params)
    except (RuntimeError, ValueError):
        pass
    try:
        params, cov = curve_fit(
            _log_curve, spend, sales, p0=(float(sales.max()) or 1.0, 0.1),
            bounds=([0, 1e-9], [np.inf, np.inf]), maxfev=20000,
        )
        return ("log", params, cov) if with_cov else ("log", params)
    except (RuntimeError, ValueError):
        return (None, None, None) if with_cov else (None, None)


def draw_params(model: str, params, cov, draws: int = CURVE_DRAWS,
                rng: np.random.Generator | None = None) -> np.ndarray | None:
    """Parameter draws from the fit's asymptotic normal posterior, in draw order,
    with every draw outside the fit's own bounds rejected — which is how the
    boundary constraints carry through to anything computed on the draws.

    None when the covariance cannot support a draw: not finite, a zero diagonal
    (an exactly-fitted response whose covariance is zero because the likelihood
    is flat, not because the parameters are known), or no draw inside the
    bounds. Shared by the per-campaign interval, the budget allocation and the
    measurement pass, so every one of them draws the same posterior."""
    if cov is None or not np.all(np.isfinite(cov)):
        return None
    cov = np.asarray(cov, dtype=float)
    if np.any(np.diag(cov) <= 0):
        return None
    rng = rng or np.random.default_rng(CURVE_SEED)
    try:
        sample = rng.multivariate_normal(np.asarray(params, dtype=float), cov, size=int(draws))
    except (ValueError, np.linalg.LinAlgError):
        return None
    keep = (sample[:, 0] > 0) & (sample[:, 1] > 0)   # a is a ceiling, k a scale
    if model == "hill":
        keep &= (sample[:, 2] >= 0.5) & (sample[:, 2] <= 3.0)
    accepted = sample[keep]
    return accepted if len(accepted) else None


def curve_values(model: str, theta, spend) -> np.ndarray:
    """Sales at every spend level for every parameter draw: shape (draws, spends).
    `theta` may be one parameter vector or a (draws, p) array."""
    theta = np.atleast_2d(np.asarray(theta, dtype=float))
    s = np.asarray(spend, dtype=float).reshape(1, -1)
    if model == "hill":
        a, k, h = theta[:, 0:1], theta[:, 1:2], theta[:, 2:3]
        return a * s**h / (k**h + s**h)
    a, b = theta[:, 0:1], theta[:, 1:2]
    return a * np.log1p(b * s)


def curve_marginals(model: str, theta, spend) -> np.ndarray:
    """Marginal ROAS (dSales/dSpend) at every spend level for every draw, by the
    same central difference `_marginal` uses. Shape (draws, spends)."""
    s = np.asarray(spend, dtype=float)
    eps = np.maximum(s, 1.0) * 1e-4
    lo = np.maximum(s - eps, 0.0)
    hi = s + eps
    return (curve_values(model, theta, hi) - curve_values(model, theta, lo)) / (hi - lo).reshape(1, -1)


def curve_uncertainty(model: str, params, cov, current_spend: float, max_spend: float,
                      threshold: float, draws: int = CURVE_DRAWS) -> dict:
    """Intervals on marginal ROAS and break-even spend, from the fit's own
    parameter covariance.

    Draws parameters from the asymptotic normal posterior (rejecting draws outside
    the parameter bounds, which is how the boundary constraints carry through),
    recomputes both quantities on each, and publishes percentiles. Returns
    `basis: "unavailable"` — and no interval — when the covariance is not finite
    or no draw lands inside the bounds."""
    out = {"basis": "unavailable", "draws": 0}
    sample = draw_params(model, params, cov, draws)
    if sample is None:
        return out

    marginals, breakevens = [], []
    for draw in sample:
        marginal = _marginal(model, tuple(draw), current_spend)
        if not np.isfinite(marginal):
            continue
        marginals.append(marginal)
        be = _breakeven(model, tuple(draw), max_spend, threshold)
        if be is not None and np.isfinite(be):
            breakevens.append(be)
    if not marginals:
        return out

    roas_q = quantiles_with_se(marginals, (0.05, 0.50, 0.95))
    out = {"basis": "parameter_covariance", "draws": len(marginals),
           "seed": CURVE_SEED,
           "marginal_roas_p5": num(roas_q[0.05]["value"], 4),
           "marginal_roas_p50": num(roas_q[0.50]["value"], 4),
           "marginal_roas_p95": num(roas_q[0.95]["value"], 4),
           "marginal_roas_mc_se": num(roas_q[0.50]["se"], 5),
           # how often the marginal dollar is already below break-even: the
           # number a trim decision actually rests on
           "p_below_breakeven": num(float(np.mean(np.asarray(marginals) < threshold)), 4),
           "breakeven_draws": len(breakevens)}
    if breakevens:
        be_q = quantiles_with_se(breakevens, (0.05, 0.50, 0.95))
        out.update({"breakeven_p5": num(be_q[0.05]["value"]),
                    "breakeven_p50": num(be_q[0.50]["value"]),
                    "breakeven_p95": num(be_q[0.95]["value"]),
                    "breakeven_mc_se": num(be_q[0.50]["se"], 3)})
    return out


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


def run(data: dict, rng=None, simulations=None, avg_margin: float | None = None,
        incrementality: float | None = None, incrementality_basis: str | None = None) -> list[dict]:
    """`incrementality` is ι from models/incrementality.py: the ratio of the
    total-sales response to the attributed-sales response. When its basis is an
    executed switchback the break-even is computed on ι-adjusted attribution
    (marginal attributed ROAS must reach 1/(m·ι)) and the attributed figure is
    kept beside it; an observational ι is published as information only."""
    threshold = 1.0 / avg_margin if avg_margin and avg_margin > 0 else 1.0
    adjusted = None
    if incrementality is not None and float(incrementality) > 0:
        adjusted = threshold / float(incrementality)
    use_adjusted = adjusted is not None and incrementality_basis == "switchback"

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
        if adjusted is not None:
            base["details"].update({"incrementality": num(incrementality, 4),
                                    "incrementality_basis": incrementality_basis,
                                    "breakeven_marginal_roas_incremental": num(adjusted, 4)})
        if len(points) < MIN_POINTS:
            results.append({**base, "status": "insufficient_data"})
            continue
        spend_cv = float(np.std(spend) / np.mean(spend)) if spend.mean() > 0 else 0.0
        base["details"] = {**base["details"], "spend_cv": num(spend_cv, 4)}
        if spend_cv < MIN_SPEND_CV:
            # the spend never moved: no response curve, and saying so is a
            # finding of its own
            results.append({**base, "status": "insufficient_spend_variation"})
            continue
        model, params, cov = _fit_curve(spend, sales, with_cov=True)
        if model is None:
            results.append({**base, "status": "insufficient_data"})
            continue
        breakeven_attributed = _breakeven(model, params, float(spend.max()), threshold)
        breakeven_incremental = (_breakeven(model, params, float(spend.max()), adjusted)
                                 if adjusted is not None else None)
        # an executed switchback moves the break-even itself; the attributed
        # figure stays on the record beside it
        breakeven = breakeven_incremental if use_adjusted else breakeven_attributed
        uncertainty = curve_uncertainty(model, params, cov, current_spend,
                                        float(spend.max()), adjusted if use_adjusted else threshold)
        # The covariance itself rides along so a later module — the budget
        # allocation, the measurement pass — can redraw the SAME posterior
        # instead of trusting the point estimate. None when it is not finite.
        cov_list = ([[num(v, 8) for v in row] for row in np.asarray(cov, dtype=float)]
                    if cov is not None and np.all(np.isfinite(cov)) else None)
        base["details"] = {**base["details"], "uncertainty": uncertainty,
                           "curve_cov": cov_list, "max_spend": num(float(spend.max())),
                           "mean_sales": num(float(sales.mean()))}
        results.append(
            {
                **base,
                "status": "ok",
                "curve_model": model,
                "curve_params": {k: num(v, 6) for k, v in zip(("a", "k", "h")[: len(params)], params)},
                "marginal_roas": num(_marginal(model, params, current_spend), 4),
                "breakeven_spend": num(breakeven),
                "breakeven_spend_attributed": num(breakeven_attributed),
                "breakeven_spend_incremental": num(breakeven_incremental),
                "recommended_spend": num(breakeven),
            }
        )
    return results
