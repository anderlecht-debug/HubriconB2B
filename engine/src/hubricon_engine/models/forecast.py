"""Probabilistic demand forecast per item: the simplest model that wins an
honest backtest.

Demand is forecast in units/day so uneven report periods (a 28-day month
beside a 31-day one) compare cleanly. Five candidate models sit on a ladder
from dumbest to fanciest:

    naive           last period's rate carried forward
    ses             simple exponential smoothing (level only)
    holt_damped     exponential smoothing with an additive, damped trend
    croston_tsb     Teunter-Syntetos-Babai smoothing for intermittent demand
                    (the demand probability and the demand size are smoothed
                    separately). Offered instead of ses/holt when >= 30% of
                    periods are zero — the regime plain smoothing was never
                    built for.
    seasonal_naive  same period one season (12 periods) ago; only offered
                    with >= 13 periods, and it degrades to plain naive at
                    rolling origins that have not yet seen a full season so
                    every candidate is scored on the same origins.

Nothing is chosen on in-sample fit. Every candidate is re-estimated at each
rolling origin (train on periods 1..t, forecast t+1, for t = 4..n-1) and
scored by MASE: absolute one-step error scaled by the in-sample one-step
naive MAE of that training window (seasonal differences once a season fits,
first differences otherwise — Hyndman & Koehler 2006). Lowest MASE wins;
exact ties go to the simpler model. Because naive is always on the ladder
the chosen model can never be worse than "carry the last period forward",
and `fva_pct` (forecast value added) says by how much it is better — 0 when
nothing beat naive. That number is reported as computed, never flattered.

Uncertainty is empirical, not parametric: the P10-P90 band is the point
forecast plus the quantiles of the backtest's own out-of-sample one-step
errors (in-sample residuals only when fewer than 4 backtest errors exist,
and the payload says which). Periods in which an inventory snapshot shows
zero fulfillable stock are censored (observed sales <= true demand) and are
excluded from fitting when at least 4 clean periods remain; otherwise the
model fits on everything and `censoring_ignored` is set. No Tobit here.

Horizon units are the daily-rate band times the horizon — a documented
simplification that scales the one-step-rate distribution rather than
convolving day-to-day noise; the inventory simulation does the convolution.
"""

import numpy as np
from scipy.optimize import minimize, minimize_scalar

from .common import num, period_days, sku_asin_bridge

MIN_PERIODS = 4  # fewer usable periods -> insufficient_data, no model is chosen
MIN_TRAIN = 4  # the first rolling origin trains on this many periods
MIN_BACKTEST_ERRORS = 4  # fewer -> the band falls back to in-sample residuals
SEASONAL_PERIOD = 12
SEASONAL_MIN_PERIODS = SEASONAL_PERIOD + 1
INTERMITTENT_ZERO_SHARE = 0.30
CROSTON_FIT_MIN_PERIODS = 8
CROSTON_FIXED_ALPHAS = (0.1, 0.2)  # (alpha_p, alpha_z) when too short to fit them
SES_BOUNDS = (0.05, 0.95)
HOLT_BOUNDS = ((0.05, 0.95), (0.01, 0.9), (0.8, 0.98))  # alpha, beta, phi
HOLT_STARTS = ((0.3, 0.1, 0.9), (0.7, 0.3, 0.97))
CROSTON_BOUNDS = ((0.02, 0.5), (0.02, 0.5))
QUANTILE_LEVELS = (10, 25, 50, 75, 90)
DEFAULT_HORIZON_DAYS = 30
NORMAL_P10_P90_WIDTH = 2.563  # p90 - p10 of a standard normal, for the sd fallback
SCALE_EPS = 1e-9  # MASE scale below this (relative to the series level) counts as zero
SIMPLICITY_ORDER = ("naive", "ses", "holt_damped", "croston_tsb", "seasonal_naive")
METHOD_LABEL = {
    "naive": "last-period carry-forward (naive)",
    "ses": "simple exponential smoothing",
    "holt_damped": "damped-trend exponential smoothing",
    "croston_tsb": "intermittent-demand smoothing (Teunter-Syntetos-Babai)",
    "seasonal_naive": "same-period-last-year carry-forward (seasonal naive)",
}


# ── series construction ───────────────────────────────────────────────────

def to_rates(rows: list[dict], units_key: str) -> list[tuple[str, float]]:
    """(period_start, units/day) per period, sorted by period_start. Rows
    with no units are skipped; duplicate rows for one period are summed."""
    units_by_period: dict[tuple[str, str], float] = {}
    for row in rows:
        units = row.get(units_key)
        if units is None:
            continue
        key = (row["period_start"], row["period_end"])
        units_by_period[key] = units_by_period.get(key, 0.0) + float(units)
    return sorted(
        (start, units / period_days(start, end)) for (start, end), units in units_by_period.items()
    )


def censored_periods(rows: list[dict], snapshots: list[dict]) -> set[str]:
    """period_start of every period containing an inventory snapshot with
    zero fulfillable stock — observed sales there are a floor on demand."""
    zero_dates = sorted({
        s["snapshot_date"] for s in snapshots
        if s.get("fulfillable_quantity") is not None and float(s["fulfillable_quantity"]) <= 0
    })
    return {
        row["period_start"] for row in rows
        if any(row["period_start"] <= d <= row["period_end"] for d in zero_dates)
    }


def is_intermittent(y) -> bool:
    y = np.asarray(y, dtype=float)
    return y.size > 0 and float(np.mean(y == 0)) >= INTERMITTENT_ZERO_SHARE


# ── models: y -> {"point", "fitted", "params"} ────────────────────────────
# `fitted[t]` is the one-step-ahead forecast of y[t] from y[:t] (NaN where
# the model has nothing to say yet); `point` is the forecast for period n.

def naive(y) -> dict:
    """Last observed rate carried forward: fitted[t] = y[t-1]."""
    y = np.asarray(y, dtype=float)
    fitted = np.full(len(y), np.nan)
    fitted[1:] = y[:-1]
    return {"point": float(y[-1]), "fitted": fitted, "params": {}}


def seasonal_naive(y, m: int = SEASONAL_PERIOD) -> dict:
    """Same period one season ago: fitted[t] = y[t-m]. Until a full season
    is available it is plain naive, so it can be scored on the same rolling
    origins as every other candidate."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    fitted = np.full(n, np.nan)
    fitted[1:] = y[:-1]
    if n > m:
        fitted[m:] = y[:-m]
    point = float(y[-m]) if n >= m else float(y[-1])
    return {"point": point, "fitted": fitted, "params": {"m": m}}


def _ses_path(y: np.ndarray, alpha: float) -> tuple[np.ndarray, float]:
    level = y[0]
    fitted = np.full(len(y), np.nan)
    for t in range(1, len(y)):
        fitted[t] = level
        level += alpha * (y[t] - level)
    return fitted, float(level)


def ses(y) -> dict:
    """Simple exponential smoothing with the level seeded at y[0]; alpha
    minimises the in-sample one-step SSE on a bounded search."""
    y = np.asarray(y, dtype=float)

    def sse(alpha):
        fitted, _ = _ses_path(y, alpha)
        return float(np.nansum((y - fitted) ** 2))

    alpha = float(minimize_scalar(sse, bounds=SES_BOUNDS, method="bounded").x)
    fitted, level = _ses_path(y, alpha)
    return {"point": level, "fitted": fitted, "params": {"alpha": alpha}}


def _holt_path(y: np.ndarray, alpha: float, beta: float, phi: float) -> tuple[np.ndarray, float]:
    level, trend = y[0], y[1] - y[0]
    fitted = np.full(len(y), np.nan)
    for t in range(1, len(y)):
        forecast = level + phi * trend
        if t >= 2:  # t = 1 would be scored against the value that seeded the trend
            fitted[t] = forecast
        new_level = alpha * y[t] + (1 - alpha) * forecast
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return fitted, float(level + phi * trend)


def holt_damped(y) -> dict:
    """Additive damped-trend smoothing (Gardner-McKenzie):
        l_t = a*y_t + (1-a)(l_{t-1} + phi*b_{t-1})
        b_t = beta*(l_t - l_{t-1}) + (1-beta)*phi*b_{t-1}
        y^_{t+1} = l_t + phi*b_t
    seeded with l_0 = y_0, b_0 = y_1 - y_0. alpha/beta/phi minimise the
    in-sample one-step SSE under bounds; phi in [0.8, 0.98] so a fitted
    trend always fades rather than extrapolating forever."""
    y = np.asarray(y, dtype=float)

    def sse(x):
        fitted, _ = _holt_path(y, *x)
        return float(np.nansum((y - fitted) ** 2))

    best = None
    for x0 in HOLT_STARTS:
        res = minimize(sse, x0=np.array(x0), bounds=HOLT_BOUNDS, method="L-BFGS-B")
        if best is None or res.fun < best.fun:
            best = res
    alpha, beta, phi = (float(v) for v in best.x)
    fitted, point = _holt_path(y, alpha, beta, phi)
    return {"point": point, "fitted": fitted, "params": {"alpha": alpha, "beta": beta, "phi": phi}}


def _tsb_path(y: np.ndarray, alpha_p: float, alpha_z: float) -> tuple[np.ndarray, float]:
    nonzero = y > 0
    p = float(np.mean(nonzero))
    z = float(np.mean(y[nonzero])) if nonzero.any() else 0.0
    fitted = np.full(len(y), np.nan)
    for t in range(len(y)):
        if t >= 1:
            fitted[t] = p * z
        if y[t] > 0:
            p += alpha_p * (1.0 - p)
            z += alpha_z * (y[t] - z)
        else:
            p += alpha_p * (0.0 - p)
    return fitted, float(p * z)


def croston_tsb(y) -> dict:
    """Teunter-Syntetos-Babai: the demand probability p is smoothed every
    period (towards 1 on a sale, towards 0 on a blank), the demand size z
    only on periods with a sale; forecast = p*z. Unlike classic Croston the
    forecast decays through a run of zeros, so a product going obsolete is
    not forecast at its old rate. Smoothing constants are fitted by SSE
    when n >= 8, otherwise fixed at (0.1, 0.2) and flagged as such."""
    y = np.asarray(y, dtype=float)
    fit_alphas = len(y) >= CROSTON_FIT_MIN_PERIODS
    if fit_alphas:
        def sse(x):
            fitted, _ = _tsb_path(y, *x)
            return float(np.nansum((y - fitted) ** 2))

        res = minimize(sse, x0=np.array(CROSTON_FIXED_ALPHAS), bounds=CROSTON_BOUNDS, method="L-BFGS-B")
        alpha_p, alpha_z = (float(v) for v in res.x)
    else:
        alpha_p, alpha_z = CROSTON_FIXED_ALPHAS
    fitted, point = _tsb_path(y, alpha_p, alpha_z)
    return {
        "point": point,
        "fitted": fitted,
        "params": {"alpha_p": alpha_p, "alpha_z": alpha_z, "alphas_fitted": fit_alphas},
    }


MODELS = {
    "naive": naive,
    "ses": ses,
    "holt_damped": holt_damped,
    "croston_tsb": croston_tsb,
    "seasonal_naive": seasonal_naive,
}


def candidate_models(y) -> dict:
    """The ladder that applies to this series. Smoothing models are swapped
    for TSB on intermittent series; seasonal naive needs >= 13 periods."""
    y = np.asarray(y, dtype=float)
    candidates = {"naive": naive}
    if is_intermittent(y):
        candidates["croston_tsb"] = croston_tsb
    else:
        candidates["ses"] = ses
        candidates["holt_damped"] = holt_damped
    if len(y) >= SEASONAL_MIN_PERIODS:
        candidates["seasonal_naive"] = seasonal_naive
    return candidates


# ── backtest and selection ────────────────────────────────────────────────

def _degenerate(scale: float, train: np.ndarray) -> bool:
    return scale <= SCALE_EPS * max(1.0, float(np.mean(np.abs(train))))


def _mase_scale(train: np.ndarray, m: int | None) -> float:
    """In-sample one-step naive MAE of the training window — the classic
    MASE denominator. Seasonal differences once a full season plus one
    period fits in the window (falling back to first differences if the
    seasonal ones are all zero), first differences otherwise. A zero
    result means the scale is undefined at this origin."""
    if m and len(train) > m:
        seasonal = float(np.mean(np.abs(train[m:] - train[:-m])))
        if not _degenerate(seasonal, train):
            return seasonal
    diffs = np.abs(train[1:] - train[:-1])
    return float(np.mean(diffs)) if diffs.size else 0.0


def _pinball(actual: float, forecast: float, q: float) -> float:
    diff = actual - forecast
    return float(max(q * diff, (q - 1) * diff))


def _in_sample_residuals(y: np.ndarray, fitted: np.ndarray) -> np.ndarray:
    resid = np.asarray(y, dtype=float) - fitted
    return resid[~np.isnan(resid)]


def rolling_origin_backtest(y, model_fn, min_train: int = MIN_TRAIN, m: int | None = None) -> dict:
    """One-step-ahead errors from origins min_train..n-1, the model refitted
    at every origin on y[:t] only. Returns mase (mean |error|/scale, origins
    with a zero scale are left out and never floored), wape (sum|error| /
    sum|actual|), pinball losses at 0.1/0.9 for the model's own quantile
    forecasts (point + quantiles of the training window's in-sample
    residuals, clipped at 0) and the raw error list (actual - forecast).
    `m` is the seasonal period used for the MASE scale when a season fits."""
    y = np.asarray(y, dtype=float)
    errors, scaled, actuals, pin10, pin90 = [], [], [], [], []
    for t in range(min_train, len(y)):
        train = y[:t]
        fit = model_fn(train)
        point = max(0.0, float(fit["point"]))
        error = float(y[t] - point)
        errors.append(error)
        actuals.append(float(y[t]))
        scale = _mase_scale(train, m)
        if not _degenerate(scale, train):
            scaled.append(abs(error) / scale)  # an undefined scale is left out, never floored
        resid = _in_sample_residuals(train, fit["fitted"])
        lo = point + (float(np.quantile(resid, 0.1)) if resid.size else 0.0)
        hi = point + (float(np.quantile(resid, 0.9)) if resid.size else 0.0)
        pin10.append(_pinball(float(y[t]), max(0.0, lo), 0.1))
        pin90.append(_pinball(float(y[t]), max(0.0, hi), 0.9))
    total_actual = float(np.sum(np.abs(actuals))) if actuals else 0.0
    return {
        "origins": len(errors),
        "mase": float(np.mean(scaled)) if scaled else None,
        "wape": float(np.sum(np.abs(errors)) / total_actual) if total_actual > 0 else None,
        "pinball_p10": float(np.mean(pin10)) if pin10 else None,
        "pinball_p90": float(np.mean(pin90)) if pin90 else None,
        "errors": errors,
    }


def select_model(y) -> tuple[str | None, dict]:
    """(name, backtest) of the candidate with the lowest rolling-origin MASE;
    exact ties go to the simpler model. The returned backtest dict also
    carries `candidates` = {name: mase} for every model that was tried.
    Fewer than MIN_PERIODS points -> (None, {"status": "insufficient_data"})."""
    y = np.asarray(y, dtype=float)
    if len(y) < MIN_PERIODS:
        return None, {"status": "insufficient_data", "candidates": {}}
    m = SEASONAL_PERIOD if len(y) >= SEASONAL_MIN_PERIODS else None
    backtests = {
        name: rolling_origin_backtest(y, fn, MIN_TRAIN, m) for name, fn in candidate_models(y).items()
    }

    def rank(name):
        mase = backtests[name]["mase"]
        return (mase if mase is not None else float("inf"), SIMPLICITY_ORDER.index(name))

    chosen = min(backtests, key=rank)
    return chosen, {**backtests[chosen], "candidates": {n: bt["mase"] for n, bt in backtests.items()}}


def quantiles_from_errors(point: float, errors) -> dict[str, float]:
    """Empirical P10..P90 of point + error, clipped at 0 (no negative demand)."""
    errors = np.asarray(errors, dtype=float)
    out = {}
    for level in QUANTILE_LEVELS:
        shift = float(np.quantile(errors, level / 100)) if errors.size else 0.0
        out[f"p{level}"] = max(0.0, float(point) + shift)
    return out


def rate_moments(row: dict) -> tuple[float | None, float | None]:
    """(mean_rate, std_rate) for the inventory simulation: the point forecast
    and the sd of the forecast errors, falling back to the normal-equivalent
    width of the P10-P90 band. (None, None) for a row with no forecast."""
    if row.get("status") != "ok":
        return None, None
    sd = row["details"].get("error_sd")
    if sd is None:
        sd = (row["daily_rate_p90"] - row["daily_rate_p10"]) / NORMAL_P10_P90_WIDTH
    return float(row["daily_rate_point"]), float(sd)


# ── per-item row ──────────────────────────────────────────────────────────

def _fva_pct(name: str, mase: float | None, naive_mase: float | None) -> float | None:
    if name == "naive":
        return 0.0
    if mase is None or naive_mase is None or naive_mase <= 0:
        return None
    return (naive_mase - mase) / naive_mase * 100


def _json_params(params: dict) -> dict:
    return {k: (v if isinstance(v, bool) else num(v, 4)) for k, v in params.items()}


def _basis(name: str, n_used: int, backtest: dict, quantile_basis: str, horizon_days: int) -> str:
    label = METHOD_LABEL[name]
    others = [METHOD_LABEL[c] for c in backtest["candidates"] if c != name]
    if backtest["origins"] == 0:
        how = f"{label} is carried forward because {n_used} periods leave no room for a rolling-origin backtest"
    elif backtest["mase"] is None:
        how = (f"{label} is used because the history was flat enough that no scaled error could be "
               f"computed at any of the {backtest['origins']} rolling-origin test periods")
    else:
        how = (f"{label} had the lowest scaled one-step error (MASE {backtest['mase']:.3f}) across "
               f"{backtest['origins']} rolling-origin backtests")
        if others:
            how += f", beating {', '.join(others)}"
    spread = (
        "the spread of those out-of-sample backtest errors"
        if quantile_basis == "backtest_errors"
        else "the spread of in-sample residuals (too few backtest errors to use)"
    )
    return (f"{how}; the P10-P90 band adds {spread} to the point rate, and the {horizon_days}-day unit "
            f"figures scale that daily band by {horizon_days} days rather than convolving day-to-day noise.")


def _forecast_item(level: str, item_id: str, rows: list[dict], units_key: str,
                   snapshots: list[dict], horizon_days: int) -> dict:
    censored = censored_periods(rows, snapshots)
    series = [
        {"period_start": start, "rate": rate, "censored": start in censored}
        for start, rate in to_rates(rows, units_key)
    ]
    clean = [s["rate"] for s in series if not s["censored"]]
    use_all = not censored or len(clean) < MIN_PERIODS
    y = np.array([s["rate"] for s in series] if use_all else clean, dtype=float)
    n_used = int(len(y))

    row = {
        "level": level,
        "item_id": item_id,
        "status": "ok",
        "method": None,
        "n_periods": len(series),
        "n_used": n_used,
        "horizon_days": horizon_days,
        "intermittent": is_intermittent(y),
    }
    details = {
        "series": [
            {"period_start": s["period_start"], "rate": num(s["rate"], 4), "censored": s["censored"]}
            for s in series
        ],
        "censored_periods": len(censored),
        "censoring_ignored": bool(censored) and use_all,
    }
    if n_used < MIN_PERIODS:
        details["basis"] = (f"Only {n_used} usable period(s) of demand history; at least {MIN_PERIODS} "
                            "are needed before any forecast is attempted.")
        return {**row, "status": "insufficient_data", "details": details}

    name, backtest = select_model(y)
    fit = MODELS[name](y)
    point = max(0.0, float(fit["point"]))
    if len(backtest["errors"]) >= MIN_BACKTEST_ERRORS:
        errors, quantile_basis = np.array(backtest["errors"]), "backtest_errors"
    else:
        errors, quantile_basis = _in_sample_residuals(y, fit["fitted"]), "in_sample_residuals"
    q = quantiles_from_errors(point, errors)
    error_sd = float(np.std(errors, ddof=1)) if len(errors) >= 2 else None

    mase, naive_mase = backtest["mase"], backtest["candidates"]["naive"]
    if mase is not None and naive_mase is not None:
        assert mase <= naive_mase, "selection must never pick a model that loses to naive"

    row["method"] = name
    row.update({
        "daily_rate_point": num(point, 4),
        **{f"daily_rate_{k}": num(v, 4) for k, v in q.items()},
        "horizon_units_point": num(point * horizon_days, 1),
        "horizon_units_p10": num(q["p10"] * horizon_days, 1),
        "horizon_units_p90": num(q["p90"] * horizon_days, 1),
        "mase": num(mase, 4),
        "wape": num(backtest["wape"], 4),
        "pinball_p10": num(backtest["pinball_p10"], 4),
        "pinball_p90": num(backtest["pinball_p90"], 4),
        "naive_mase": num(naive_mase, 4),
        "fva_pct": num(_fva_pct(name, mase, naive_mase), 1),
    })
    details.update({
        "params": _json_params(fit["params"]),
        "backtest_origins": backtest["origins"],
        "candidates": {n: num(v, 4) for n, v in backtest["candidates"].items()},
        "error_sd": num(error_sd, 4),
        "quantile_basis": quantile_basis,
        "basis": _basis(name, n_used, backtest, quantile_basis, horizon_days),
    })
    return {**row, "details": details}


def run(data: dict, rng=None, simulations=None, horizon_days: int = DEFAULT_HORIZON_DAYS) -> list[dict]:
    """One row per SKU in sku_economics (units_sold). ASINs in asin_traffic
    that no SKU row covers (via the SKU->ASIN bridge) get their own row at
    level 'asin' from units_ordered — the whole catalog when it is ASIN-only.
    `rng`/`simulations` are accepted for interface parity and unused: the
    forecast is deterministic."""
    econ = data.get("sku_economics") or []
    traffic = data.get("asin_traffic") or []
    inventory = data.get("inventory_levels") or []
    bridge = sku_asin_bridge(econ, data.get("cogs_inputs") or [])

    econ_by_sku: dict[str, list[dict]] = {}
    for row in econ:
        econ_by_sku.setdefault(row["sku"], []).append(row)
    traffic_by_asin: dict[str, list[dict]] = {}
    for row in traffic:
        traffic_by_asin.setdefault(row["child_asin"], []).append(row)
    snaps_by_sku: dict[str, list[dict]] = {}
    snaps_by_asin: dict[str, list[dict]] = {}
    for snap in inventory:
        if snap.get("sku"):
            snaps_by_sku.setdefault(snap["sku"], []).append(snap)
        if snap.get("asin"):
            snaps_by_asin.setdefault(snap["asin"], []).append(snap)

    results = []
    for sku, rows in sorted(econ_by_sku.items()):
        results.append(_forecast_item("sku", sku, rows, "units_sold", snaps_by_sku.get(sku, []), horizon_days))
    covered = {bridge[sku] for sku in econ_by_sku if sku in bridge}
    for asin, rows in sorted(traffic_by_asin.items()):
        if asin in covered:
            continue
        results.append(
            _forecast_item("asin", asin, rows, "units_ordered", snaps_by_asin.get(asin, []), horizon_days)
        )
    return results
