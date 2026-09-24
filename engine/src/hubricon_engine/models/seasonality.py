"""Seasonal demand: a multiplicative index per calendar month, pooled across the
catalog and shrunk toward flat.

Every demand simulation in this engine — the stockout model, the order sizing,
the cash cone — draws a rate that is flat over its horizon. For a catalog with
a fourth-quarter peak that understates the reorder a September wire has to
cover, misprices the storage the peak bills, and makes the cone's November
too quiet. The forecast ladder has a seasonal candidate but only with
thirteen periods of one SKU's history, which is a year most SKUs do not have.

THE ESTIMATOR. Hierarchical, because the data is thin per SKU and wide across
SKUs. For each SKU and each calendar month it was observed, the ratio of that
month's daily rate to the SKU's own mean rate over the window. The CATALOG
index for month m is the mean of every SKU's ratio in that month — forty SKUs
over one year give forty observations of December — shrunk toward 1 by the
empirical-Bayes rule of §2 (the between-month dispersion against the sampling
noise of each month's mean): a catalog whose months differ no more than their
noise explains comes back flat, and says so. Each SKU's own index is then its
own ratios shrunk toward the catalog's. Every index carries a standard error
and a Student-t interval, and the basis says whether one season or two were
seen.

Refused under twelve distinct calendar months in the history
(`insufficient_history`), which is what the brief asked for: eleven months
cannot say what the twelfth looks like.

HOW IT IS USED. `horizon_factor` is the mean index over the calendar days of a
lead-time window, applied to the rate the stockout model and the order sizing
simulate on; `daily_path` is the index per day for the cone. The index's own
uncertainty is propagated into the rate's standard deviation —
sd² = sd_rate²·I² + rate²·se_I² — so a reorder or a trough in a thin month
widens rather than pretending the index is known. The forecast ladder gains a
candidate, `seasonal_index_ses`, that deseasonalises by the index, smooths,
and reseasonalises for the target month; it is scored by the same
rolling-origin backtest as every other candidate and never chosen by
assertion.

WHAT IT CANNOT TELL YOU. A month that was never observed (the index is 1 with
no interval, and the payload lists it). A SKU whose season runs against the
catalog's, from one season of data — it carries the catalog's index until a
second season lets its own be told from its noise (the forecast ladder's
non-seasonal candidates remain for a SKU the catalogue's season does not
fit). Holidays that move between months.
"""

from datetime import date, timedelta

import numpy as np
from scipy import stats

from .common import num, period_days
from .elasticity import eb_shrink

MIN_MONTHS = 12
MIN_SKU_MONTHS = 6          # a SKU's own index needs this many observed months to be shrunk rather than pooled
MIN_RATIO_OBS = 2           # a catalog month needs this many SKU ratios to carry a standard error
CI_LEVEL = 0.95


def _monthly_rates(data: dict) -> dict[str, dict[str, list[float]]]:
    """{sku: {'YYYY-MM': [rate, ...]}} from sku_economics (Amazon and Shopify
    alike), falling back to asin_traffic for an ASIN-only catalog.

    A month flagged as a stockout or a promotion (data_quality) is left out:
    its units are the stock's or the deal's, not the season's. Corrected
    2026-09-24 — the forecast and the price fits already censored those
    months while the index read a deal month as that SKU's peak; on the
    Simons–Thorp–Griffin bench one October deal made a SKU's October index
    1.6 and its order twice the optimum."""
    from .data_quality import contaminated_periods
    out: dict[str, dict[str, list[float]]] = {}
    rows = data.get("sku_economics") or []
    key, units_key = "sku", "units_sold"
    bad = contaminated_periods(data) if rows else {}
    if not rows:
        rows, key, units_key = data.get("asin_traffic") or [], "child_asin", "units_ordered"
    for r in rows:
        units = r.get(units_key)
        if units is None or not r.get("period_start") or not r.get("period_end"):
            continue
        if str(r["period_start"])[:10] in (bad.get(r.get(key)) or {}):
            continue
        days = period_days(str(r["period_start"]), str(r["period_end"]))
        month = str(r["period_start"])[:7]
        out.setdefault(r[key], {}).setdefault(month, []).append(float(units) / days)
    return out


RELATIVE_MIN_MONTHS = 6       # observed calendar months before a relative index is offered to price fits


def indices(data: dict) -> dict:
    series = _monthly_rates(data)
    months_seen = sorted({m for v in series.values() for m in v})
    calendar_months = sorted({int(m[5:7]) for m in months_seen})
    if data.get("_relative_only"):
        # the same estimate on whatever months exist, for the refusal's relative index
        calendar_months = list(range(1, 13))
    base = {"n_skus": len(series), "months_observed": len(months_seen),
            "calendar_months_covered": len(calendar_months)}
    if len(calendar_months) < MIN_MONTHS:
        refused = {**base, "status": "insufficient_history",
                   "basis": f"{len(calendar_months)} distinct calendar months in the history; {MIN_MONTHS} are needed"}
        if len(calendar_months) >= RELATIVE_MIN_MONTHS:
            # Not a seasonal model — the forecast, the stock and the cash cone
            # still see the refusal — but a price fit needs less: it compares
            # the months it observed with each other, and a catalogue ratio over
            # those months is estimable from any stretch of them. Added
            # 2026-09-24: with twelve months a catalogue's fits were
            # deseasonalised and with eleven they were not, and dropping one
            # month from the middle of a year flipped the direction of 22–26%
            # of the model-risk bench's price steps.
            full = indices({**data, "_relative_only": True})
            refused["relative_catalog"] = full.get("catalog")
            refused["relative_basis"] = (f"catalogue ratios over {len(calendar_months)} observed calendar months, "
                                         "for deseasonalising price fits only")
        return refused
    # per SKU: ratio of each month's rate to the SKU's mean over its window
    ratios: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    sku_ratios: dict[str, dict[int, list[float]]] = {}
    for sku, by_month in series.items():
        rates = {m: float(np.mean(v)) for m, v in by_month.items()}
        mean = float(np.mean(list(rates.values())))
        if mean <= 0 or len(rates) < 3:
            continue
        for m, rate in rates.items():
            cm = int(m[5:7])
            ratios[cm].append(rate / mean)
            sku_ratios.setdefault(sku, {}).setdefault(cm, []).append(rate / mean)
    estimates, ses, counts = [], [], []
    for m in range(1, 13):
        v = np.array(ratios[m], dtype=float)
        counts.append(int(v.size))
        if v.size >= MIN_RATIO_OBS:
            estimates.append(float(v.mean()))
            ses.append(float(v.std(ddof=1) / np.sqrt(v.size)) if v.size > 1 else 0.0)
        else:
            estimates.append(1.0)
            ses.append(0.0)
    est = np.array(estimates)
    se = np.array(ses)
    # shrink toward flat: the pool is the twelve months, the prior mean is 1
    observed = np.array([c >= MIN_RATIO_OBS for c in counts])
    if observed.sum() >= 3:
        eb = eb_shrink(est[observed] - 1.0, np.maximum(se[observed], 1e-6))
        shrunk = np.ones(12)
        post = np.zeros(12)
        weights = np.zeros(12)
        shrunk[observed] = 1.0 + eb["shrunk"]
        post[observed] = eb["post_se"]
        weights[observed] = eb["weights"]
        tau2, mu = eb["tau2"], 1.0 + eb["mu"]
    else:
        shrunk, post, weights, tau2, mu = np.ones(12), np.zeros(12), np.zeros(12), 0.0, 1.0
    # normalise to mean one over the observed months so the annual total is unchanged
    scale = float(np.mean(shrunk[observed])) if observed.any() else 1.0
    shrunk = np.where(observed, shrunk / scale, 1.0)
    seasons = max(counts) / max(1, len(sku_ratios)) if sku_ratios else 0
    n_seasons = 2 if len(months_seen) >= 24 else 1
    dof = max(1, int(observed.sum()) - 1)
    t_crit = float(stats.t.ppf(0.5 + CI_LEVEL / 2, dof))
    catalog = {m: {"index": num(shrunk[m - 1], 4), "se": num(post[m - 1], 4),
                   "ci95": [num(shrunk[m - 1] - t_crit * post[m - 1], 4), num(shrunk[m - 1] + t_crit * post[m - 1], 4)],
                   "n": counts[m - 1], "shrinkage_weight": num(weights[m - 1], 4), "observed": bool(observed[m - 1])}
               for m in range(1, 13)}
    # per SKU: own ratios shrunk toward the catalog index — with two seasons.
    # With one, each SKU-month is a single observation and a SKU's own
    # seasonal deviation cannot be told from its noise (both are one number
    # per month), so the SKU carries the catalogue's index, as the price fits
    # already do (deseasonalise_economics). Corrected 2026-09-24: the
    # shrinkage assumed a noise of 0.35 and let each SKU estimate its own
    # spread from twelve points, so one noisy September set a SKU's
    # September index 10% under the catalogue's, its deseasonalised rate 18%
    # high, and its order a third above the optimum.
    per_sku = {}
    for sku, by_cm in sku_ratios.items():
        if n_seasons < 2:
            per_sku[sku] = {"basis": "catalog index (one season cannot separate a SKU's own season from its noise)",
                            "index": {m: catalog[m]["index"] for m in catalog}}
            continue
        if len(by_cm) < MIN_SKU_MONTHS:
            per_sku[sku] = {"basis": "catalog index (too few months of its own)", "index": {m: catalog[m]["index"] for m in catalog}}
            continue
        own = np.array([float(np.mean(by_cm.get(m, [shrunk[m - 1]]))) for m in range(1, 13)])
        own_se = np.array([float(np.std(by_cm[m], ddof=1) / np.sqrt(len(by_cm[m]))) if m in by_cm and len(by_cm[m]) > 1
                           else (0.35 if m in by_cm else 0.0) for m in range(1, 13)])
        seen = np.array([m in by_cm for m in range(1, 13)])
        idx = shrunk.copy()
        if seen.sum() >= 3:
            eb_s = eb_shrink(own[seen] - shrunk[seen], np.maximum(own_se[seen], 1e-6))
            idx[seen] = shrunk[seen] + eb_s["shrunk"]
            w = np.zeros(12)
            w[seen] = eb_s["weights"]
        else:
            w = np.zeros(12)
        s_ = float(np.mean(idx[seen])) if seen.any() else 1.0
        idx = np.where(seen, idx / s_, shrunk)
        per_sku[sku] = {"basis": "own ratios shrunk toward the catalog index",
                        "index": {m: num(idx[m - 1], 4) for m in range(1, 13)},
                        "shrinkage_weight": {m: num(w[m - 1], 4) for m in range(1, 13)},
                        "months_seen": int(seen.sum())}
    amplitude = float(shrunk[observed].max() / shrunk[observed].min()) if observed.any() else 1.0
    return {**base, "status": "ok", "catalog": catalog, "per_sku": per_sku,
            "seasons_observed": n_seasons, "basis_label": "one_season_pooled" if n_seasons == 1 else "two_seasons",
            "tau2": num(tau2, 6), "amplitude": num(amplitude, 4), "unobserved_months": [m for m in range(1, 13) if not observed[m - 1]],
            "basis": (f"{len(sku_ratios)} SKUs over {len(months_seen)} months ({'one season' if n_seasons == 1 else 'two or more seasons'}); "
                      f"catalog index per calendar month shrunk toward flat (τ² = {tau2:.4f}), each SKU shrunk toward the catalog; "
                      f"peak-to-trough {amplitude:.2f}×")}


def index_for(seasonal: dict | None, sku: str | None, month: int) -> tuple[float, float]:
    """(index, se) for a SKU (or the catalog) in a calendar month; (1, 0) when
    there is no seasonal estimate."""
    if not seasonal or seasonal.get("status") != "ok":
        return 1.0, 0.0
    cat = seasonal["catalog"][month] if month in seasonal["catalog"] else seasonal["catalog"].get(str(month))
    if cat is None:
        return 1.0, 0.0
    se = float(cat.get("se") or 0.0)
    if sku and sku in (seasonal.get("per_sku") or {}):
        idx = seasonal["per_sku"][sku]["index"]
        val = idx.get(month, idx.get(str(month)))
        if val is not None:
            return float(val), se
    return float(cat["index"] or 1.0), se


def deseasonalise_economics(data: dict, seasonal: dict | None) -> tuple[dict, dict]:
    """SKU Economics with the CATALOGUE index divided out of every period's
    units and sales, for a fit that should not read the season as a response
    to price. The per-SKU index is deliberately not used: with one season on
    file a SKU's own monthly ratio is its own residual, and dividing by it
    would fit the noise away. The catalogue index pools every SKU, so no
    single SKU's noise moves it. Returns (data, note); data is the input,
    untouched, when the index is not on file."""
    if not seasonal or (seasonal.get("status") != "ok" and not seasonal.get("relative_catalog")):
        return data, {"deseasonalised": False, "basis": "no catalogue seasonal index on file"}
    catalog = seasonal.get("catalog") if seasonal.get("status") == "ok" else seasonal.get("relative_catalog")
    idx = {}
    for k, v in (catalog or {}).items():
        try:
            m = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, dict) and v.get("observed", True) and v.get("index"):
            idx[m] = float(v["index"])
    if not idx:
        return data, {"deseasonalised": False, "basis": "catalogue seasonal index carries no observed month"}
    rows = []
    for r in data.get("sku_economics") or []:
        try:
            f = idx.get(int(str(r["period_start"])[5:7]), 1.0)
        except (TypeError, ValueError):
            f = 1.0
        if f <= 0 or f == 1.0:
            rows.append(r)
            continue
        rr = dict(r)
        if rr.get("units_sold") is not None:
            rr["units_sold"] = float(rr["units_sold"]) / f
        if rr.get("sales") is not None:
            rr["sales"] = float(rr["sales"]) / f
        rows.append(rr)
    return {**data, "sku_economics": rows}, {"deseasonalised": True,
                                            "basis": seasonal.get("basis_label") or seasonal.get("relative_basis"),
                                            "amplitude": seasonal.get("amplitude")}


def horizon_factor(seasonal: dict | None, sku: str | None, start: date, days: float) -> tuple[float, float]:
    """Mean index over the calendar days of a window from `start`, and its se."""
    if not seasonal or seasonal.get("status") != "ok" or days <= 0:
        return 1.0, 0.0
    n = int(np.ceil(days))
    vals, ses = [], []
    for k in range(n):
        d = start + timedelta(days=k)
        v, s_ = index_for(seasonal, sku, d.month)
        vals.append(v)
        ses.append(s_)
    return float(np.mean(vals)), float(np.mean(ses))


def daily_path(seasonal: dict | None, sku: str | None, start: date, days: int) -> np.ndarray:
    if not seasonal or seasonal.get("status") != "ok":
        return np.ones(int(days))
    return np.array([index_for(seasonal, sku, (start + timedelta(days=k)).month)[0] for k in range(int(days))])


def seasonal_rate(mean_rate: float, sd_rate: float, seasonal: dict | None, sku: str | None,
                  start: date, days: float) -> tuple[float, float, dict]:
    """The rate and sd a simulation should draw over a window: the index applied
    to the mean, its own uncertainty added to the sd in quadrature."""
    factor, se = horizon_factor(seasonal, sku, start, days)
    mean = mean_rate * factor
    sd = float(np.sqrt((sd_rate * factor) ** 2 + (mean_rate * se) ** 2))
    return mean, sd, {"seasonal_factor": num(factor, 4), "seasonal_factor_se": num(se, 4),
                      "seasonal_basis": (seasonal or {}).get("basis_label") if seasonal and seasonal.get("status") == "ok" else "flat"}
