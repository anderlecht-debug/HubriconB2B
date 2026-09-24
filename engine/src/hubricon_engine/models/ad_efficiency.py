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


# The ladder of response forms, simplest first. Constant ROAS is the naive
# rung: sales proportional to spend, no saturation at all. A curve is only
# chosen when it beats it out of sample, so no campaign gets a break-even by
# assertion.
FORMS = ("linear", "log", "hill")
# Fewer points than this leave no room for a rolling-origin backtest; the
# ladder then defaults to Hill as it did before 2026-09-23, and says so.
MIN_BACKTEST_ORIGINS = 2
# Origins are spread evenly over the series past MIN_POINTS and capped, so a
# long daily history costs a bounded number of refits per form.
MAX_BACKTEST_ORIGINS = 12


# The other curve form is carried as an equally weighted alternative
# (models/ad_allocation.py resamples over it) unless its out-of-sample
# errors are worse than the chosen form's by more than this many standard
# errors of the difference — the evidence the curve itself had to show
# against the straight line. Added 2026-09-24: on the bench, whose curves are
# all Hill, the backtest preferred log by 3–6% of error on campaigns where
# the difference was noise, and budget moved toward log-fitted campaigns whose
# slower saturation overstated the slope over the move (4.45 against a true 3.99).
FORM_WORSE_T = 1.0
FORM_TIE = FORM_WORSE_T   # the published name for the same rule


def _fit_form(form: str, spend: np.ndarray, sales: np.ndarray):
    """(params, cov) for one form, or None when it will not fit."""
    if form == "linear":
        # least squares through the origin, like the curves: a mean of
        # sales-to-spend ratios is dominated by the noisiest low-spend days
        ss = float(np.sum(spend * spend))
        if ss <= 0:
            return None
        roas = float(np.sum(spend * sales) / ss)
        resid = sales - roas * spend
        dof = max(1, len(spend) - 1)
        se = float(np.sqrt(np.sum(resid**2) / dof / ss))
        return np.array([roas]), np.array([[se**2]])
    try:
        if form == "hill":
            p0 = (float(sales.max()) * 1.5 or 1.0, float(np.median(spend)) or 1.0, 1.0)
            params, cov = curve_fit(_hill, spend, sales, p0=p0,
                                    bounds=([0, 1e-6, 0.5], [np.inf, np.inf, 3.0]), maxfev=20000)
        else:
            params, cov = curve_fit(_log_curve, spend, sales, p0=(float(sales.max()) or 1.0, 0.1),
                                    bounds=([0, 1e-9], [np.inf, np.inf]), maxfev=20000)
        return params, cov
    except (RuntimeError, ValueError):
        return None


def campaign_points(ppc_spend: list[dict], breaks: dict[str, dict] | None = None) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """{campaign: (spend, sales)} — the daily points each campaign's curve is
    fitted on, in date order, after its regime break when it has one: the
    same sample run() fits, for a caller that resamples it."""
    pts: dict[str, list[tuple[float, float, str]]] = {}
    breaks = breaks or {}
    for row in ppc_spend or []:
        if row.get("spend") is None:
            continue
        name = row.get("campaign_name") or row.get("campaign_id")
        brk = breaks.get(name)
        if brk and str(row.get("report_date") or "")[:10] < brk["since"]:
            continue
        if float(row["spend"]) > 0:
            pts.setdefault(name, []).append((float(row["spend"]), float(row.get("sales") or 0), str(row.get("report_date") or "")))
    out = {}
    for name, rows in pts.items():
        rows.sort(key=lambda r: r[2])
        out[name] = (np.array([r[0] for r in rows]), np.array([r[1] for r in rows]))
    return out


def _predict(form: str, params, s: np.ndarray) -> np.ndarray:
    if form == "linear":
        return params[0] * s
    return (_hill if form == "hill" else _log_curve)(s, *params)


def backtest_forms(spend: np.ndarray, sales: np.ndarray) -> dict:
    """Rolling-origin one-step errors per form, in the points' own order:
    train on the first t, predict point t, t from MIN_POINTS to n − 1; each
    error scaled by the training window's naive (constant-ROAS) in-sample
    MAE, the same discipline as forecast.py. Lowest wins; ties go up the
    ladder to the simpler form."""
    n = len(spend)
    origins = list(range(MIN_POINTS, n))
    if len(origins) > MAX_BACKTEST_ORIGINS:
        origins = [int(round(x)) for x in np.linspace(MIN_POINTS, n - 1, MAX_BACKTEST_ORIGINS)]
    if len(origins) < MIN_BACKTEST_ORIGINS:
        return {"status": "insufficient_origins", "chosen": "hill", "origins": len(origins),
                "candidates": {}, "basis": f"{n} points leave {len(origins)} backtest origin(s); Hill by default"}
    scaled = {f: [] for f in FORMS}
    level = max(1.0, float(np.mean(np.abs(sales))))
    for t in origins:
        tr_s, tr_v = spend[:t], sales[:t]
        naive_mae = float(np.mean(np.abs(tr_v - float(np.mean(tr_v / np.maximum(tr_s, 1e-9))) * tr_s)))
        # an exactly proportional history has no naive error to scale by;
        # the floor keeps every origin and lets the tie go to the line
        naive_mae = max(naive_mae, 1e-6 * level)
        for f in FORMS:
            fit = _fit_form(f, tr_s, tr_v)
            if fit is None:
                scaled[f].append(np.nan)
                continue
            pred = float(_predict(f, fit[0], np.array([spend[t]]))[0])
            scaled[f].append(abs(sales[t] - pred) / naive_mae)
    errors, per_origin = {}, {}
    for f in FORMS:
        v = np.array(scaled[f], dtype=float)
        per_origin[f] = v
        v = v[np.isfinite(v)]
        errors[f] = float(v.mean()) if v.size else None
    if errors.get("linear") is None:
        return {"status": "insufficient_origins", "chosen": "hill", "origins": len(origins), "candidates": errors}
    # A curve nests the line (Hill with a huge k, log with a tiny b), so it
    # can edge the line out by noise. It wins only when its per-origin
    # improvement over the line is more than one standard error of that
    # improvement — evidence of saturation, not a coin flip.
    best, best_err, best_t = "linear", errors["linear"], 0.0
    lin = per_origin["linear"]
    for f in ("log", "hill"):
        if errors[f] is None or errors[f] >= best_err:
            continue
        both = np.isfinite(lin) & np.isfinite(per_origin[f])
        diff = lin[both] - per_origin[f][both]
        se = float(diff.std(ddof=1) / np.sqrt(diff.size)) if diff.size > 1 else float("inf")
        t_stat = float(diff.mean() / se) if se > 0 else 0.0
        if t_stat > 1.0:
            best, best_err, best_t = f, errors[f], t_stat
    naive = errors["linear"]
    fva = ((naive - best_err) / naive * 100) if naive > 0 and best != "linear" else 0.0
    # how much worse, in its own standard errors, the other curve form is
    # than the chosen one, origin by origin: the same evidence standard the
    # curve had to meet against the line
    worse_by = {}
    for other in (("log", "hill") if best == "linear" else ("hill" if best == "log" else "log",)):
        if errors.get(other) is None:
            continue
        both = np.isfinite(per_origin[best]) & np.isfinite(per_origin[other])
        diff = per_origin[other][both] - per_origin[best][both]
        if diff.size > 1:
            se = float(diff.std(ddof=1) / np.sqrt(diff.size))
            worse_by[other] = num(float(diff.mean() / se) if se > 0 else 0.0, 3)
    return {"status": "ok", "chosen": best, "origins": len(origins), "candidates": {f: num(e, 4) for f, e in errors.items()},
            "fva_pct": num(fva, 1), "t_vs_linear": num(best_t, 3), "other_form_worse_t": worse_by,
            "basis": (f"{len(origins)} rolling-origin backtests, one-step error scaled by the training window's "
                      f"constant-ROAS MAE; " + (f"{best} beats the straight line by {best_t:.1f} standard errors"
                                                if best != "linear" else "no saturation beats a straight line here"))}


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
    keep = sample[:, 0] > 0                            # a is a ceiling, or a ROAS
    if model != "linear":
        keep &= sample[:, 1] > 0                          # k a scale, b a rate
    if model == "hill":
        keep &= (sample[:, 2] >= 0.5) & (sample[:, 2] <= 3.0)
    accepted = sample[keep]
    return accepted if len(accepted) else None


def curve_values(model: str, theta, spend) -> np.ndarray:
    """Sales at every spend level for every parameter draw: shape (draws, spends).
    `theta` may be one parameter vector or a (draws, p) array."""
    theta = np.atleast_2d(np.asarray(theta, dtype=float))
    s = np.asarray(spend, dtype=float).reshape(1, -1)
    if model == "linear":
        return theta[:, 0:1] * s
    if model == "hill":
        a, k, h = theta[:, 0:1], theta[:, 1:2], theta[:, 2:3]
        return a * s**h / (k**h + s**h)
    a, b = theta[:, 0:1], theta[:, 1:2]
    return a * np.log1p(b * s)


def form_mixture_values(form_fits: list[dict], spend, draws: int, seed: int) -> np.ndarray | None:
    """Sales at every spend level on draws pooled equally across the curve
    forms the backtest could not tell apart (details.form_fits): each form
    contributes the same number of draws from its own posterior. Shape
    (draws, spends); None when no form supports a draw."""
    rng = np.random.default_rng(seed)
    usable = [f for f in form_fits or [] if f.get("model") in ("hill", "log") and f.get("cov") is not None]
    if not usable:
        return None
    per = max(1, int(draws) // len(usable))
    blocks = []
    for f in usable:
        theta = draw_params(f["model"], np.asarray(f["params"], dtype=float), np.asarray(f["cov"], dtype=float),
                            per, rng)
        if theta is not None and len(theta):
            blocks.append(curve_values(f["model"], theta, spend))
    if not blocks:
        return None
    n = min(len(b) for b in blocks)
    return np.vstack([b[:n] for b in blocks])


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

    # every draw at once: the marginal at today's spend, and the break-even
    # as the largest grid spend whose marginal still returns the threshold —
    # _breakeven's own grid and rule, vectorised (2026-09-24: the per-draw
    # loop was 1.3 million Python calls a catalogue)
    with np.errstate(all="ignore"):
        m_now = curve_marginals(model, sample, [current_spend])[:, 0]
        finite = np.isfinite(m_now)
        grid = np.linspace(max_spend * 3, max_spend * 0.01, 400)
        m_grid = curve_marginals(model, sample[finite], grid)
    marginals = list(m_now[finite])
    hit = m_grid >= threshold
    found = hit.any(axis=1)
    breakevens = [float(grid[j]) for j in np.argmax(hit, axis=1)[found]]
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
    if model == "linear":
        return float(params[0])
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


def regime_breaks(anomaly_rows: list[dict] | None) -> dict[str, dict]:
    """{campaign: {since, metric}} for every campaign whose cost per click or
    sales per click shifted (flagged after the sweep's false-discovery control).
    A response curve fitted across such a break is two curves averaged."""
    out: dict[str, dict] = {}
    for r in anomaly_rows or []:
        if r.get("scope") != "campaign" or r.get("metric") not in ("cpc", "sales_per_click") or not r.get("flagged"):
            continue
        since = str(r.get("since") or "")[:10]
        if not since:
            continue
        cur = out.get(r["item_id"])
        if cur is None or since > cur["since"]:
            out[r["item_id"]] = {"since": since, "metric": r["metric"], "detector": r.get("detector")}
    return out


def run(data: dict, rng=None, simulations=None, avg_margin: float | None = None,
        incrementality: float | None = None, incrementality_basis: str | None = None,
        clv_multiplier: float | None = None, clv_basis: str | None = None,
        breaks: dict[str, dict] | None = None, clv_extra: dict | None = None) -> list[dict]:
    """`incrementality` is ι from models/incrementality.py: the ratio of the
    total-sales response to the attributed-sales response. When its basis is an
    executed switchback the break-even is computed on ι-adjusted attribution
    (marginal attributed ROAS must reach 1/(m·ι)) and the attributed figure is
    kept beside it; an observational ι is published as information only."""
    threshold = 1.0 / avg_margin if avg_margin and avg_margin > 0 else 1.0
    adjusted = None
    # ι scales what an attributed dollar is worth; a calibrated lifetime-value
    # multiplier scales what a first order is worth. Both divide the threshold.
    factor = 1.0
    if incrementality is not None and float(incrementality) > 0 and incrementality_basis == "switchback":
        factor *= float(incrementality)
    if clv_multiplier is not None and float(clv_multiplier) > 0 and clv_basis == "calibrated":
        factor *= float(clv_multiplier)
    if incrementality is not None and float(incrementality) > 0:
        adjusted = threshold / float(incrementality)
    use_adjusted = adjusted is not None and incrementality_basis == "switchback"
    threshold_used = threshold / factor if factor != 1.0 else threshold
    if factor != 1.0:
        adjusted, use_adjusted = threshold_used, True

    terms_by_campaign: dict[str, list[dict]] = {}
    for row in data["ppc_search_terms"]:
        terms_by_campaign.setdefault(row["campaign_name"], []).append(row)

    # Daily points from ppc_spend when present, else one aggregate point per
    # (campaign, period) from the search-term uploads.
    points_by_campaign: dict[str, list[tuple[float, float]]] = {}
    breaks = breaks or {}
    dropped_before_break: dict[str, int] = {}
    for row in data["ppc_spend"]:
        if row["spend"] is not None:
            name = row["campaign_name"] or row["campaign_id"]
            brk = breaks.get(name)
            if brk and str(row.get("report_date") or "")[:10] < brk["since"]:
                # a point from before the regime break describes a curve
                # that no longer applies; fit on the new regime only
                dropped_before_break[name] = dropped_before_break.get(name, 0) + 1
                continue
            points_by_campaign.setdefault(name, []).append(
                (float(row["spend"]), float(row["sales"] or 0), str(row.get("report_date") or ""))
            )
    if not points_by_campaign:
        per_period: dict[tuple, list[float]] = {}
        for row in data["ppc_search_terms"]:
            key = (row["campaign_name"], row["period_start"], row["period_end"])
            bucket = per_period.setdefault(key, [0.0, 0.0])
            bucket[0] += row["spend"] or 0
            bucket[1] += row["sales_7d"] or 0
        for (campaign, start, _), (spend, sales) in per_period.items():
            points_by_campaign.setdefault(campaign, []).append((spend, sales, str(start or "")))

    results = []
    for campaign in sorted(set(points_by_campaign) | set(terms_by_campaign)):
        # in date order: the form is chosen by a rolling-origin backtest, and
        # an origin is only an origin in time
        points = sorted(((s, v, d) for s, v, d in points_by_campaign.get(campaign, []) if s > 0), key=lambda p: p[2])
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
        if campaign in breaks:
            base["details"]["regime_break"] = {**breaks[campaign],
                                               "points_before_break_dropped": dropped_before_break.get(campaign, 0)}
        if adjusted is not None:
            base["details"].update({"incrementality": num(incrementality, 4),
                                    "incrementality_basis": incrementality_basis,
                                    "breakeven_marginal_roas_incremental": num(adjusted, 4),
                                    "clv_multiplier": num(clv_multiplier, 4), "clv_basis": clv_basis,
                                    **(clv_extra or {})})
        if len(points) < MIN_POINTS:
            # too few points since the break: the old curve is not trusted and
            # the new one is not fitted yet — a status, not a stale number
            results.append({**base, "status": "regime_break" if campaign in breaks else "insufficient_data"})
            continue
        spend_cv = float(np.std(spend) / np.mean(spend)) if spend.mean() > 0 else 0.0
        base["details"] = {**base["details"], "spend_cv": num(spend_cv, 4)}
        if spend_cv < MIN_SPEND_CV:
            # the spend never moved: no response curve, and saying so is a
            # finding of its own
            results.append({**base, "status": "insufficient_spend_variation"})
            continue
        selection = backtest_forms(spend, sales)
        base["details"] = {**base["details"], "form_selection": selection}
        if selection["chosen"] == "linear":
            # no saturation beats a straight line out of sample: the marginal
            # dollar returns what the average dollar returns, so there is no
            # break-even to trim toward and no curve to reallocate along —
            # the reallocation treats the campaign as linear at its ROAS
            params, cov = _fit_form("linear", spend, sales)
            roas, se = float(params[0]), float(np.sqrt(cov[0, 0]))
            # a line whose whole return interval sits under break-even loses on
            # every dollar: its break-even spend is zero and the trim fires;
            # otherwise there is no break-even to name
            underwater = roas + 1.645 * se < threshold
            # "could not show saturation" is not "shown not to saturate": the
            # curve forms not significantly worse than the line ride along
            alts = ["linear"] + [f for f, t in (selection.get("other_form_worse_t") or {}).items()
                                 if t is not None and float(t) <= FORM_WORSE_T]
            base["details"]["form_alternatives"] = {"forms": alts, "weights": [1.0 / len(alts)] * len(alts),
                                                    "tie": FORM_WORSE_T}
            results.append({
                **base, "status": "no_diminishing_returns", "curve_model": "linear",
                "curve_params": {"roas": num(roas, 6)},
                "marginal_roas": num(roas, 4),
                "breakeven_spend": 0.0 if underwater else None, "recommended_spend": 0.0 if underwater else None,
                "details": {**base["details"], "curve_cov": [[num(cov[0, 0], 10)]], "max_spend": num(float(spend.max())),
                            "mean_sales": num(float(sales.mean())),
                            "uncertainty": {"basis": "roas_standard_error", "marginal_roas_p5": num(roas - 1.645 * se, 4),
                                            "marginal_roas_p50": num(roas, 4), "marginal_roas_p95": num(roas + 1.645 * se, 4),
                                            "p_below_breakeven": num(float(roas < threshold), 4)}},
            })
            continue
        fitted = _fit_form(selection["chosen"], spend, sales)
        if fitted is None:
            model, params, cov = _fit_curve(spend, sales, with_cov=True)
        else:
            model, (params, cov) = selection["chosen"], fitted
        # the curve forms the out-of-sample backtest cannot tell apart from the
        # chosen one ride along, equally weighted: a model that reallocates
        # along one curve should know the other fitted it as well
        worse = selection.get("other_form_worse_t") or {}
        alternatives = [model]
        for f, t in worse.items():
            if f != model and t is not None and float(t) <= FORM_WORSE_T:
                alternatives.append(f)
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
        # every form the backtest could not separate from the chosen one,
        # fitted on the same days with its own break-even interval: a trim
        # is sized at the cautious end across them and promised on draws
        # pooled over them (added 2026-09-24 — a log curve chosen by a hair
        # set a trim to $102 a day where the truth's break-even was $133,
        # below any day the campaign had run, and the trim delivered 43% of
        # its promise)
        form_fits = [{"model": model, "params": [num(v, 8) for v in params], "cov": cov_list,
                      "breakeven": num(breakeven), "breakeven_p95": uncertainty.get("breakeven_p95")}]
        for f in alternatives[1:]:
            if f not in ("hill", "log"):
                continue
            fit_f = _fit_form(f, spend, sales)
            if fit_f is None or not np.all(np.isfinite(fit_f[1])):
                continue
            unc_f = curve_uncertainty(f, fit_f[0], fit_f[1], current_spend, float(spend.max()),
                                      adjusted if use_adjusted else threshold)
            be_f = _breakeven(f, fit_f[0], float(spend.max()), adjusted if use_adjusted else threshold)
            form_fits.append({"model": f, "params": [num(v, 8) for v in fit_f[0]],
                              "cov": [[num(v, 8) for v in row] for row in np.asarray(fit_f[1], dtype=float)],
                              "breakeven": num(be_f), "breakeven_p95": unc_f.get("breakeven_p95")})
        base["details"] = {**base["details"], "uncertainty": uncertainty,
                           "curve_cov": cov_list, "max_spend": num(float(spend.max())),
                           "spend_p10": num(float(np.quantile(spend, 0.10))),
                           "form_fits": form_fits,
                           "mean_sales": num(float(sales.mean())),
                           "form_alternatives": {"forms": alternatives, "weights": [1.0 / len(alternatives)] * len(alternatives),
                                                 "tie": FORM_TIE}}
        results.append(
            {
                **base,
                "status": "ok",
                "curve_model": model,
                # named by form: Hill (a, k, h), log (a, b). The log fit carried
                # Hill's names until 2026-09-23, which nothing downstream read
                # by name until the reallocation did.
                "curve_params": {k: num(v, 6) for k, v in zip(("a", "k", "h") if model == "hill" else ("a", "b"), params)},
                "marginal_roas": num(_marginal(model, params, current_spend), 4),
                "breakeven_spend": num(breakeven),
                "breakeven_spend_attributed": num(breakeven_attributed),
                "breakeven_spend_incremental": num(breakeven_incremental),
                "recommended_spend": num(breakeven),
            }
        )
    return results
