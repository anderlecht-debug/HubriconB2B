"""Fee creep, margin erosion, ad-spend spikes and traffic drops — change
detection on the short, noisy series a seller actually has.

Four detectors, each a pure function over a numeric series, each answering
``{"status": "insufficient_data"}`` instead of raising when the series is
too short to say anything:

    robust_z    — is the LATEST point an outlier against the rest? Median
                  and MAD (scaled by 1.4826 so it estimates σ under
                  normality) of every point but the last, then the z of the
                  last. The short-series cousin of S-H-ESD: no distribution
                  fit, no seasonal model, a robust location and scale. When
                  MAD is zero the mean absolute deviation (×1.2533) stands
                  in; when even that is zero every baseline point is
                  identical and any departure is flagged with no finite z.
    cusum       — did the LEVEL shift, and when? Page's two-sided CUSUM on
                  standardised values, baseline mean/sd from the first
                  max(4, n//2) points, sd floored at 1e-9 so a perfectly
                  flat baseline followed by a different value still trips.
                  Allowance k=0.5σ and decision interval h=4σ are the
                  textbook tuning for catching a 1σ shift (Montgomery).
                  Reports where the accumulating run began and the shift
                  in ORIGINAL units (mean since the run started minus the
                  baseline mean).
    changepoint — single change in mean: a Gaussian likelihood-ratio scan
                  over every split with ≥ min_segment points on each side.
                  Flagged when 2·LLR exceeds a BIC penalty of 2·log(n).
                  The split model spends two extra degrees of freedom — a
                  second mean AND the split location — so the plain
                  one-parameter log(n) penalty is too easy to beat on a
                  ten-point series; 2·log(n) is the conservative choice.
                  Softmax weights over the candidate splits, exp(LLR_i −
                  max), say how sure we are about WHERE, so the Desk can say
                  "most likely since <period>".
    weekly_decompose + spikes — for daily series (ad spend). trend is a
                  centred 7-day running median, seasonal the per-weekday
                  median of the detrended series re-centred to zero, and
                  ``spikes`` is robust z on the remainder for every point.
                  Two things keep that honest on a 3–13 week series. The
                  window is clamped to the series at the edges rather than
                  padded, so every window holds each weekday exactly once
                  (replicating the last day three times bends the trend by
                  that day's weekday effect — exactly where "spikes in the
                  last 14 days" looks). And the remainder is PREDICTIVE:
                  day i is judged against a trend and weekday effect fitted
                  without day i. A median absorbs the point it picks, so an
                  in-sample remainder has a mass of exact zeros that shrinks
                  the MAD by a third and turns 2.5σ noise into "spikes"; the
                  leave-one-out remainder has no such mass (validated in
                  simulation: false-spike rate per series ~5–10% instead of
                  50–100%, MAD/sd ≈ 1.0).

``run`` scans SKU fees, ASIN traffic, campaign spend and settlement fee
buckets and emits one row per (series, detector), flagged or not — an
unflagged row still carries the baseline so the Desk can say "fee per unit
stable at $3.42".

Honesty discipline: nothing is a finding unless a detector crossed its
threshold; ``dollar_impact`` exists only for the adverse direction (fees
up, conversion or sessions down, spend up) and ``details["basis"]`` spells
out the arithmetic in words. A small shift on a very quiet series will
cross a standardised threshold — ``delta_pct`` is there so the caller can
apply materiality on top.
"""

import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

from .common import num

MAD_SCALE = 1.4826        # median absolute deviation -> sigma under normality
MEAN_AD_SCALE = 1.2533    # mean absolute deviation -> sigma; fallback when MAD is 0
Z_THRESHOLD = 3.5
MIN_N = 6
CUSUM_K = 0.5             # allowance, in sigmas — tuned for a 1-sigma shift
CUSUM_H = 4.0             # decision interval, in sigmas
# Daily spend gets a wider interval: at h=4 the two-sided run length between
# false alarms is ~170 points, i.e. a 90-day series false-alarms ~40% of the
# time; h=5 (~900 points) brings that to ~10% and still catches a 1σ shift
# within ~10 days. Monthly series keep h=4 — there are only 6–12 points.
DAILY_CUSUM_H = 5.0
MR_D2 = 1.128             # mean moving range -> sigma (control-chart d2 for n=2)
SD_FLOOR = 1e-9           # absolute, and relative to the level
FLAT_TOL = 1e-9           # a series whose whole range is below this (relative) is flat
MIN_SEGMENT = 3
WEEK = 7
WEEKLY_MIN_N = 3 * WEEK
SERIES_TAIL = 60
SPIKE_RECENT_DAYS = 14
SPEND_SHIFT_DAYS = 30     # a daily spend level shift is valued over this many days
DESCRIPTION_BUCKETS = ("FBA Inventory Fee", "Service Fee")
POSTERIOR_TOP = 5


# ── pure detectors ────────────────────────────────────────────────────────

def _finite(y) -> np.ndarray:
    """Float array of the finite points. None/NaN are dropped — callers
    hand over already-clean series, so indices refer to what survives."""
    arr = np.array([np.nan if v is None else float(v) for v in y], dtype=float)
    return arr[np.isfinite(arr)]


def _robust_scale(values: np.ndarray, center: float) -> float:
    deviations = np.abs(values - center)
    mad = float(np.median(deviations)) * MAD_SCALE
    if mad > 0:
        return mad
    return float(np.mean(deviations)) * MEAN_AD_SCALE


def _direction(delta: float) -> str | None:
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return None


def robust_z(y, min_n: int = MIN_N) -> dict:
    """z of the last point against the median/MAD of everything before it."""
    y = _finite(y)
    n = len(y)
    if n < min_n:
        return {"status": "insufficient_data", "n": n}
    base, last = y[:-1], float(y[-1])
    median = float(np.median(base))
    mad = float(np.median(np.abs(base - median)))
    scale = _robust_scale(base, median)
    delta = last - median
    if scale > 0:
        z = delta / scale
        flagged = abs(z) >= Z_THRESHOLD
    else:
        # every baseline point is identical: a departure is unmistakable,
        # but no finite z describes it
        z = None
        flagged = not math.isclose(last, median, rel_tol=1e-9, abs_tol=1e-12)
    return {
        "status": "ok",
        "n": n,
        "z": num(z, 3),
        "flagged": bool(flagged),
        "direction": _direction(delta) if flagged else None,
        "median": num(median, 6),
        "mad": num(mad, 6),
        "scale": num(scale, 6),
        "last": num(last, 6),
        "threshold": Z_THRESHOLD,
    }


def cusum(y, k: float = CUSUM_K, h: float = CUSUM_H, min_n: int = MIN_N) -> dict:
    """Page's two-sided CUSUM on standardised values. Baseline from the
    first max(4, n//2) points; the first run to cross h is reported."""
    y = _finite(y)
    n = len(y)
    if n < min_n:
        return {"status": "insufficient_data", "n": n}
    m = max(4, n // 2)
    base = y[:m]
    mu = float(base.mean())
    # Scale: the baseline sd from 4–8 points is a noisy estimate, and a
    # lucky-quiet baseline inflates every later z. The control-chart
    # moving-range estimator (mean |Δy| / d2) uses the whole series yet a
    # single level shift touches only one difference, so it stays honest
    # under the very shift we are hunting. Take the larger of the two.
    mr_sd = float(np.mean(np.abs(np.diff(y))) / MR_D2) if n > 1 else 0.0
    sd = max(float(base.std(ddof=1)), mr_sd, SD_FLOOR, SD_FLOOR * abs(mu))
    z = (y - mu) / sd

    s_pos = s_neg = 0.0
    start_pos = start_neg = 0
    crossed = None  # (index crossed, direction, index the run began)
    for i in range(n):
        if s_pos == 0.0:
            start_pos = i
        if s_neg == 0.0:
            start_neg = i
        s_pos = max(0.0, s_pos + z[i] - k)
        s_neg = max(0.0, s_neg - z[i] - k)
        if crossed is None:
            if s_pos >= h:
                crossed = (i, "up", start_pos)
            elif s_neg >= h:
                crossed = (i, "down", start_neg)

    if crossed is None:
        crossed_index, direction, start = None, None, None
        shift = None
    else:
        crossed_index, direction, start = crossed
        shift = float(y[start:].mean()) - mu
    return {
        "status": "ok",
        "n": n,
        "flagged": crossed is not None,
        "direction": direction,
        "start_index": start,
        "crossed_index": crossed_index,
        "s_pos": num(s_pos, 4),
        "s_neg": num(s_neg, 4),
        "shift_estimate": num(shift, 6),
        "baseline_mean": num(mu, 6),
        "baseline_sd": num(sd, 6),
        "baseline_n": m,
        "k": k,
        "h": h,
    }


def changepoint(y, min_segment: int = MIN_SEGMENT, penalty="bic") -> dict:
    """Single mean shift by likelihood-ratio scan. ``penalty`` is "bic"
    (threshold 2·log(n) on 2·LLR, two extra parameters) or an explicit
    float threshold on 2·LLR. ``index`` is the first point of the new
    regime."""
    y = _finite(y)
    n = len(y)
    if n < 2 * min_segment:
        return {"status": "insufficient_data", "n": n}
    ss_total = float(((y - y.mean()) ** 2).sum())
    # a flat series (to rounding) has nothing to explain — without this the
    # ratio of two rounding-noise sums of squares can look like a shift
    flat = float(np.ptp(y)) <= FLAT_TOL * max(1.0, abs(float(y.mean())))
    candidates = list(range(min_segment, n - min_segment + 1))
    llrs = []
    for i in candidates:
        left, right = y[:i], y[i:]
        ss_split = float(((left - left.mean()) ** 2).sum() + ((right - right.mean()) ** 2).sum())
        if flat or ss_total <= 0:
            llrs.append(0.0)
        else:
            # a perfect two-level step has ss_split == 0; cap the ratio so
            # the statistic stays finite and JSON-safe
            llrs.append(0.5 * n * math.log(ss_total / max(ss_split, ss_total * 1e-12)))
    llr_arr = np.array(llrs)
    best = int(np.argmax(llr_arr))
    index = candidates[best]
    llr = float(llr_arr[best])
    threshold = 2.0 * math.log(n) if penalty == "bic" else float(penalty)
    bic_gain = 2.0 * llr - threshold
    flagged = bic_gain > 0

    before = float(y[:index].mean())
    after = float(y[index:].mean())
    delta = after - before
    weights = np.exp(llr_arr - llr_arr.max())
    weights /= weights.sum()
    return {
        "status": "ok",
        "n": n,
        "flagged": bool(flagged),
        "index": index,
        "before_mean": num(before, 6),
        "after_mean": num(after, 6),
        "delta": num(delta, 6),
        "delta_pct": num(delta / abs(before), 4) if before != 0 else None,
        "llr": num(llr, 4),
        "bic_gain": num(bic_gain, 4),
        "penalty": num(threshold, 4),
        "min_segment": min_segment,
        "posterior": [
            {"index": i, "weight": num(float(w), 4)} for i, w in zip(candidates, weights)
        ],
    }


def _window(j: int, n: int) -> tuple[int, int]:
    """A full 7-day window containing j, clamped inside the series so every
    window holds each weekday exactly once (no edge padding)."""
    start = min(max(j - WEEK // 2, 0), n - WEEK)
    return start, start + WEEK


def _running_median(y: np.ndarray) -> np.ndarray:
    n = len(y)
    return np.array([float(np.median(y[slice(*_window(j, n))])) for j in range(n)])


def weekly_decompose(y) -> dict:
    """Daily series -> trend, seasonal, remainder. Weekday = position mod 7,
    so the series must be contiguous. Needs three full weeks.

    trend/seasonal are the display decomposition: two passes, so the
    running median is taken on the deseasonalised series and the zero-mean
    re-centring of the weekday effect is self-consistent (one pass leaves a
    constant offset in the remainder whenever the pattern's median weekday
    is not its mean).

    remainder is predictive — remainder[i] = y[i] minus a baseline (window
    median plus weekday effect) fitted with day i left out — which is the
    right thing to feed ``spikes``; see the module docstring for why. It
    therefore does not sum with trend and seasonal back to y exactly;
    ``y - remainder`` is the leave-one-out expectation for each day."""
    y = _finite(y)
    n = len(y)
    if n < WEEKLY_MIN_N:
        return {"status": "insufficient_data", "n": n}
    weekday = np.arange(n) % WEEK
    positions = np.arange(n)

    seasonal = np.zeros(n)
    for _ in range(2):
        trend = _running_median(y - seasonal)
        detrended = y - trend
        effect = np.array([float(np.median(detrended[weekday == d])) for d in range(WEEK)])
        effect -= effect.mean()
        seasonal = effect[weekday]

    # leave-one-out: each day detrended by the median of the OTHER six days
    # of its window, then compared with the same-weekday days of other weeks
    loo = np.empty(n)
    for j in range(n):
        s, e = _window(j, n)
        loo[j] = y[j] - float(np.median(np.concatenate([y[s:j], y[j + 1:e]])))
    remainder = np.empty(n)
    for i in range(n):
        peers = loo[(weekday == weekday[i]) & (positions != i)]
        remainder[i] = loo[i] - float(np.median(peers))
    return {
        "status": "ok",
        "n": n,
        "trend": trend.tolist(),
        "seasonal": seasonal.tolist(),
        "remainder": remainder.tolist(),
        "weekday_effect": effect.tolist(),
    }


def spikes(remainder, threshold: float = Z_THRESHOLD, min_n: int = MIN_N) -> dict:
    """Robust z of every point of a (remainder) series; indices, values and
    z of the points at or beyond ``threshold``."""
    r = _finite(remainder)
    n = len(r)
    if n < min_n:
        return {"status": "insufficient_data", "n": n}
    median = float(np.median(r))
    scale = _robust_scale(r, median)
    base = {"status": "ok", "n": n, "median": num(median, 6), "scale": num(scale, 6),
            "threshold": threshold}
    if scale <= 0:
        return {**base, "flagged": False, "indices": [], "values": [], "z": []}
    z = (r - median) / scale
    hits = np.where(np.abs(z) >= threshold)[0]
    return {
        **base,
        "flagged": bool(len(hits)),
        "indices": hits.tolist(),
        "values": [num(float(r[i]), 6) for i in hits],
        "z": [num(float(z[i]), 3) for i in hits],
    }


# ── row plumbing ──────────────────────────────────────────────────────────

def _money(v: float) -> str:
    return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"


def _rate(v: float) -> str:
    return f"{v:.2%}"


def _points(v: float) -> str:
    return f"{v:.1f}%"


def _count(v: float) -> str:
    return f"{v:,.0f}"


def _ratio(delta: float | None, base: float | None) -> float | None:
    if delta is None or not base:
        return None
    return delta / abs(base)


def _spec(scope: str, item_id: str, metric: str, points: list[tuple[str, float]], *,
          label: str, fmt, impact, digits: int = 2, extra: dict | None = None) -> dict:
    """One series to scan: ``points`` are (t, value) already clean and
    sorted; ``impact(direction, before, after) -> (dollars | None, clause)``
    values a flagged shift and explains the arithmetic.

    ``extra`` rides along into every row's ``details`` — the volume the impact
    was valued at, so a later measurement pass can rebuild the same arithmetic
    instead of guessing which denominator produced the dollars."""
    return {
        "scope": scope, "item_id": item_id, "metric": metric,
        "ts": [t for t, _ in points], "ys": [float(v) for _, v in points],
        "label": label, "fmt": fmt, "impact": impact, "digits": digits,
        "extra": extra or {},
    }


def _row(spec: dict, detector: str, *, status: str = "ok", flagged: bool = False,
         direction: str | None = None, since: str | None = None,
         baseline: float | None = None, current: float | None = None,
         delta: float | None = None, delta_pct: float | None = None,
         dollar_impact: float | None = None, params: dict | None = None,
         basis: str | None = None, extra: dict | None = None) -> dict:
    digits = spec["digits"]
    series = [
        {"t": t, "v": num(v, digits)}
        for t, v in zip(spec["ts"][-SERIES_TAIL:], spec["ys"][-SERIES_TAIL:])
    ]
    details = {"series": series, "params": params or {}, "basis": basis, **spec.get("extra", {})}
    if extra:
        details.update(extra)
    return {
        "scope": spec["scope"],
        "item_id": spec["item_id"],
        "metric": spec["metric"],
        "detector": detector,
        "status": status,
        "flagged": bool(flagged),
        "direction": direction if flagged else None,
        "since": since if flagged else None,
        "baseline": num(baseline, digits),
        "current": num(current, digits),
        "delta": num(delta, digits) if flagged else None,
        "delta_pct": num(delta_pct, 4) if flagged else None,
        "dollar_impact": num(dollar_impact) if flagged else None,
        "n": len(spec["ys"]),
        "details": details,
    }


def _shift_basis(spec: dict, direction: str, before: float, after: float, since: str) -> tuple:
    impact, clause = spec["impact"](direction, before, after)
    verb = "rose" if direction == "up" else "fell"
    text = f"{spec['label']} {verb} from {spec['fmt'](before)} to {spec['fmt'](after)} since {since}"
    if clause:
        text += f"; {clause}"
    return impact, text


def _stable_basis(spec: dict, baseline: float, current: float) -> str:
    return (f"{spec['label']} shows no level shift: baseline {spec['fmt'](baseline)}, "
            f"latest {spec['fmt'](current)}")


def _cusum_row(spec: dict, ys: list[float] | None = None, params: dict | None = None,
               h: float = CUSUM_H) -> dict:
    """``ys`` overrides the scanned values (e.g. a deseasonalised copy);
    reported series/points stay the raw ones."""
    values = spec["ys"] if ys is None else ys
    res = cusum(values, h=h)
    if res["status"] != "ok":
        return _row(spec, "cusum", status="insufficient_data", params={"min_n": MIN_N, **(params or {})})
    keep = ("k", "h", "baseline_n", "baseline_mean", "baseline_sd", "s_pos", "s_neg",
            "start_index", "crossed_index", "shift_estimate")
    p = {**{k: res[k] for k in keep}, **(params or {})}
    if not res["flagged"]:
        return _row(spec, "cusum", baseline=res["baseline_mean"], current=spec["ys"][-1],
                    params=p, basis=_stable_basis(spec, res["baseline_mean"], spec["ys"][-1]))
    before = res["baseline_mean"]
    after = before + res["shift_estimate"]
    since = spec["ts"][res["start_index"]]
    impact, basis = _shift_basis(spec, res["direction"], before, after, since)
    return _row(spec, "cusum", flagged=True, direction=res["direction"], since=since,
                baseline=before, current=after, delta=after - before,
                delta_pct=_ratio(after - before, before), dollar_impact=impact,
                params=p, basis=basis)


def _changepoint_row(spec: dict) -> dict:
    res = changepoint(spec["ys"])
    if res["status"] != "ok":
        return _row(spec, "changepoint", status="insufficient_data",
                    params={"min_segment": MIN_SEGMENT})
    p = {k: res[k] for k in ("index", "llr", "bic_gain", "penalty", "min_segment")}
    top = sorted(res["posterior"], key=lambda c: c["weight"], reverse=True)[:POSTERIOR_TOP]
    extra = {"posterior": [{"t": spec["ts"][c["index"]], "weight": c["weight"]} for c in top]}
    if not res["flagged"]:
        overall = float(np.mean(spec["ys"]))
        return _row(spec, "changepoint", baseline=overall, current=spec["ys"][-1], params=p,
                    basis=_stable_basis(spec, overall, spec["ys"][-1]), extra=extra)
    before, after = res["before_mean"], res["after_mean"]
    direction = _direction(after - before)
    since = spec["ts"][res["index"]]
    impact, basis = _shift_basis(spec, direction, before, after, since)
    return _row(spec, "changepoint", flagged=True, direction=direction, since=since,
                baseline=before, current=after, delta=after - before,
                delta_pct=_ratio(after - before, before), dollar_impact=impact,
                params=p, basis=basis, extra=extra)


def _robust_z_row(spec: dict) -> dict:
    res = robust_z(spec["ys"])
    if res["status"] != "ok":
        return _row(spec, "robust_z", status="insufficient_data", params={"min_n": MIN_N})
    p = {k: res[k] for k in ("z", "median", "mad", "scale", "threshold")}
    median, last = res["median"], spec["ys"][-1]
    if not res["flagged"]:
        return _row(spec, "robust_z", baseline=median, current=last, params=p,
                    basis=(f"{spec['label']} latest {spec['fmt'](last)} is in line with a "
                           f"typical {spec['fmt'](median)}"))
    impact, clause = spec["impact"](res["direction"], median, last)
    z_text = f"robust z {res['z']:+.1f}" if res["z"] is not None else "baseline had no spread"
    basis = (f"{spec['label']} latest {spec['fmt'](last)} against a typical "
             f"{spec['fmt'](median)} ({z_text})")
    if clause:
        basis += f"; {clause}"
    return _row(spec, "robust_z", flagged=True, direction=res["direction"], since=spec["ts"][-1],
                baseline=median, current=last, delta=last - median,
                delta_pct=_ratio(last - median, median), dollar_impact=impact,
                params=p, basis=basis)


def _spikes_row(spec: dict, decomposition: dict) -> dict:
    ts, ys = spec["ts"], spec["ys"]
    if decomposition["status"] != "ok":
        return _row(spec, "spikes", status="insufficient_data", params={"min_n": WEEKLY_MIN_N})
    res = spikes(decomposition["remainder"])
    if res["status"] != "ok":
        return _row(spec, "spikes", status="insufficient_data", params={"min_n": MIN_N})
    # the leave-one-out expectation for each day, the baseline the z is against
    expected = np.array(ys) - np.array(decomposition["remainder"])
    cutoff = len(ys) - SPIKE_RECENT_DAYS
    recent = [(i, z) for i, z in zip(res["indices"], res["z"]) if i >= cutoff]
    p = {
        "z_threshold": Z_THRESHOLD,
        "recent_days": SPIKE_RECENT_DAYS,
        "spikes_total": len(res["indices"]),
        "spikes_recent": len(recent),
        "remainder_scale": res["scale"],
        "weekday_effect": [num(v) for v in decomposition["weekday_effect"]],
    }
    extra = {"spikes": [
        {"t": ts[i], "v": num(ys[i]), "expected": num(float(expected[i])), "z": z}
        for i, z in recent
    ]}
    typical = float(np.median(ys))
    if not recent:
        earlier = f" ({len(res['indices'])} earlier in the series)" if res["indices"] else ""
        return _row(spec, "spikes", baseline=typical, current=ys[-1], params=p, extra=extra,
                    basis=(f"daily spend stayed within its weekday pattern over the last "
                           f"{SPIKE_RECENT_DAYS} days{earlier}"))
    biggest, z_big = max(recent, key=lambda iz: abs(iz[1]))
    exp_big = float(expected[biggest])
    delta = ys[biggest] - exp_big
    excess = sum(ys[i] - float(expected[i]) for i, _ in recent if ys[i] > float(expected[i]))
    basis = (f"{len(recent)} spend spike(s) in the last {SPIKE_RECENT_DAYS} days; largest on "
             f"{ts[biggest]}: {_money(ys[biggest])} against an expected {_money(exp_big)} for that "
             f"weekday (robust z {z_big:+.1f})")
    if excess > 0:
        basis += f"; spend above expectation on those days totals {_money(excess)}"
    return _row(spec, "spikes", flagged=True, direction=_direction(delta), since=ts[min(i for i, _ in recent)],
                baseline=typical, current=ys[biggest], delta=delta,
                delta_pct=_ratio(delta, exp_big), dollar_impact=excess if excess > 0 else None,
                params=p, basis=basis, extra=extra)


# ── impact closures (adverse direction only) ──────────────────────────────

def _no_impact(direction, before, after):
    return None, ""


def _per_unit_impact(units: float | None):
    def impact(direction, before, after):
        if direction != "up" or not units:
            return None, ""
        dollars = (after - before) * units
        return dollars, f"at last period's {_count(units)} units that is {_money(dollars)} per period"
    return impact


def _rate_on_sales_impact(sales: float | None):
    def impact(direction, before, after):
        if direction != "up" or not sales:
            return None, ""
        dollars = (after - before) * sales
        return dollars, f"on last period's {_money(sales)} of sales that is {_money(dollars)} per period"
    return impact


def _per_period_impact(period: str):
    def impact(direction, before, after):
        if direction != "up":
            return None, ""
        dollars = after - before
        return dollars, f"that is {_money(dollars)} more per {period}"
    return impact


def _sessions_impact(conversion_pct: float | None, price: float | None):
    def impact(direction, before, after):
        if direction != "down":
            return None, ""
        if conversion_pct is None or price is None:
            return None, "no conversion rate or unit price on file to value it"
        dollars = (before - after) * conversion_pct / 100.0 * price
        return dollars, (f"at {conversion_pct:.1f}% conversion and a {_money(price)} average "
                         f"price that is {_money(dollars)} of sales per period")
    return impact


def _conversion_impact(sessions: float | None, price: float | None):
    def impact(direction, before, after):
        if direction != "down":
            return None, ""
        if sessions is None or price is None:
            return None, "no session count or unit price on file to value it"
        dollars = (before - after) / 100.0 * sessions * price
        return dollars, (f"on last period's {_count(sessions)} sessions at a {_money(price)} "
                         f"average price that is {_money(dollars)} of sales per period")
    return impact


def _spend_shift_impact(direction, before, after):
    if direction != "up":
        return None, ""
    dollars = (after - before) * SPEND_SHIFT_DAYS
    return dollars, f"over {SPEND_SHIFT_DAYS} days that is {_money(dollars)} more ad spend"


# ── scans ─────────────────────────────────────────────────────────────────

def _abs_or_none(v) -> float | None:
    return None if v is None else abs(float(v))


def _sku_rows(econ: list[dict]) -> list[dict]:
    by_sku: dict[str, list[dict]] = defaultdict(list)
    for r in econ:
        by_sku[r["sku"]].append(r)
    rows = []
    for sku, periods in sorted(by_sku.items()):
        periods.sort(key=lambda r: r["period_start"])
        fee_per_unit, referral_rate, fba_per_unit, storage = [], [], [], []
        latest_units = latest_sales = None
        for r in periods:
            t = r["period_start"]
            units = float(r.get("units_sold") or 0)
            sales = float(r.get("sales") or 0)
            fees = {
                f: _abs_or_none(r.get(f))
                for f in ("referral_fees", "fba_fulfillment_fees", "storage_fees", "other_fees")
            }
            known = [v for v in fees.values() if v is not None]
            if units > 0:
                latest_units = units
                if known:
                    fee_per_unit.append((t, sum(known) / units))
                if fees["fba_fulfillment_fees"] is not None:
                    fba_per_unit.append((t, fees["fba_fulfillment_fees"] / units))
            if sales > 0:
                latest_sales = sales
                if fees["referral_fees"] is not None:
                    referral_rate.append((t, fees["referral_fees"] / sales))
            if fees["storage_fees"] is not None:
                storage.append((t, fees["storage_fees"]))
        basis = {"units_basis": latest_units, "sales_basis": latest_sales}
        specs = [
            _spec("sku", sku, "fee_per_unit", fee_per_unit, label="fee per unit", fmt=_money,
                  impact=_per_unit_impact(latest_units), extra=basis),
            _spec("sku", sku, "referral_rate", referral_rate, label="referral rate", fmt=_rate,
                  impact=_rate_on_sales_impact(latest_sales), digits=4, extra=basis),
            _spec("sku", sku, "fba_fee_per_unit", fba_per_unit, label="FBA fee per unit", fmt=_money,
                  impact=_per_unit_impact(latest_units), extra=basis),
            _spec("sku", sku, "storage_fee", storage, label="storage fee per period", fmt=_money,
                  impact=_per_period_impact("period"), extra=basis),
        ]
        for spec in specs:
            if spec["ys"]:
                rows += [_cusum_row(spec), _changepoint_row(spec)]
    return rows


def _asin_rows(traffic: list[dict]) -> list[dict]:
    by_asin: dict[str, list[dict]] = defaultdict(list)
    for r in traffic:
        by_asin[r["child_asin"]].append(r)
    rows = []
    for asin, periods in sorted(by_asin.items()):
        periods.sort(key=lambda r: r["period_start"])
        series = {"sessions": [], "unit_session_pct": [], "buy_box_pct": []}
        price = None
        for r in periods:
            for metric in series:
                v = r.get(metric)
                if v is not None and math.isfinite(float(v)):
                    series[metric].append((r["period_start"], float(v)))
            units = r.get("units_ordered")
            if units and r.get("ordered_product_sales"):
                price = float(r["ordered_product_sales"]) / float(units)
        latest_sessions = series["sessions"][-1][1] if series["sessions"] else None
        latest_conversion = series["unit_session_pct"][-1][1] if series["unit_session_pct"] else None
        specs = [
            _spec("asin", asin, "sessions", series["sessions"], label="sessions", fmt=_count,
                  impact=_sessions_impact(latest_conversion, price)),
            _spec("asin", asin, "unit_session_pct", series["unit_session_pct"],
                  label="conversion (unit session %)", fmt=_points,
                  impact=_conversion_impact(latest_sessions, price), digits=4),
            _spec("asin", asin, "buy_box_pct", series["buy_box_pct"], label="Buy Box share",
                  fmt=_points, impact=_no_impact, digits=4),
        ]
        for spec in specs:
            if spec["ys"]:
                rows += [_robust_z_row(spec), _changepoint_row(spec)]
    return rows


def _campaign_rows(ppc: list[dict]) -> list[dict]:
    by_campaign: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in ppc:
        if r.get("spend") is None or not r.get("report_date"):
            continue
        key = r.get("campaign_name") or r.get("campaign_id")
        by_campaign[key][r["report_date"][:10]] += float(r["spend"])
    rows = []
    for campaign, daily in sorted(by_campaign.items()):
        try:
            first, last = date.fromisoformat(min(daily)), date.fromisoformat(max(daily))
        except ValueError:
            continue
        # a day with no row is a day with no spend; the weekday grouping
        # needs a contiguous calendar
        days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
        points = [(d, daily.get(d, 0.0)) for d in days]
        spec = _spec("campaign", campaign, "spend", points, label="daily spend", fmt=_money,
                     impact=_spend_shift_impact)
        decomposition = weekly_decompose(spec["ys"])
        deseasonalised = decomposition["status"] == "ok"
        spike_days = 0
        scan = None
        if deseasonalised:
            # the level shift is scanned on spend minus the weekday pattern,
            # with spike days (reported by the spikes row) replaced by their
            # expectation — one blowout day must not read as a new level
            found = spikes(decomposition["remainder"])
            spiked = set(found.get("indices") or [])
            spike_days = len(spiked)
            scan = [
                v - s - (r if i in spiked else 0.0)
                for i, (v, s, r) in enumerate(zip(
                    spec["ys"], decomposition["seasonal"], decomposition["remainder"]))
            ]
        rows.append(_spikes_row(spec, decomposition))
        rows.append(_cusum_row(spec, ys=scan, h=DAILY_CUSUM_H, params={
            "deseasonalised": deseasonalised,
            "spike_days_replaced": spike_days,
            "days_filled_with_zero": len(days) - len(daily),
        }))
    return rows


def _month_range(first: str, last: str) -> list[str]:
    y, m = int(first[:4]), int(first[5:7])
    months = []
    while f"{y:04d}-{m:02d}" <= last:
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def _settlement_rows(txns: list[dict]) -> list[dict]:
    dated = []
    for r in txns:
        dt, total = r.get("txn_datetime"), r.get("total")
        if not dt or total is None:
            continue
        try:
            day = date.fromisoformat(str(dt)[:10])
        except ValueError:
            continue
        dated.append((day, float(total), r))
    if not dated:
        return []
    # a settlement export rarely starts on the 1st or ends on the 31st: a
    # partial month would read as a fee drop, so edge months that look
    # partial are left out and named in the params
    lo = min(d for d, _, _ in dated)
    hi = max(d for d, _, _ in dated)
    dropped = set()
    if lo.day != 1:
        dropped.add(lo.strftime("%Y-%m"))
    if (hi + timedelta(days=1)).month == hi.month:
        dropped.add(hi.strftime("%Y-%m"))
    months = [m for m in _month_range(lo.strftime("%Y-%m"), hi.strftime("%Y-%m")) if m not in dropped]
    if not months:
        return []

    buckets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for day, total, r in dated:
        month = day.strftime("%Y-%m")
        if month in dropped:
            continue
        txn_type = r.get("txn_type") or "Unknown"
        buckets[txn_type][month] += total
        if txn_type in DESCRIPTION_BUCKETS and r.get("description"):
            buckets[f"{txn_type} / {r['description']}"][month] += total
    rows = []
    for item_id, monthly in sorted(buckets.items()):
        signed = [monthly.get(m, 0.0) for m in months]
        # sign convention: a bucket that is net money-out is a cost, and its
        # series is the cost magnitude so "up" means more paid
        cost_like = sum(signed) < 0
        values = [-v for v in signed] if cost_like else signed
        points = list(zip([m + "-01" for m in months], values))
        spec = _spec("fee_type", item_id, "monthly_total", points,
                     label=f"{item_id} per month", fmt=_money,
                     impact=_per_period_impact("month") if cost_like else _no_impact)
        params = {"cost_like": cost_like, "partial_months_dropped": sorted(dropped)}
        cusum_row = _cusum_row(spec, params=params)
        change_row = _changepoint_row(spec)
        change_row["details"]["params"].update(params)
        rows += [change_row, cusum_row]
    return rows


def run(data: dict, rng=None, simulations=None) -> list[dict]:
    """One row per (series, detector) — see the module docstring for the
    row shape. Tables that are missing or empty are skipped, never faked."""
    rows: list[dict] = []
    rows += _sku_rows(data.get("sku_economics") or [])
    rows += _asin_rows(data.get("asin_traffic") or [])
    rows += _campaign_rows(data.get("ppc_spend") or [])
    rows += _settlement_rows(data.get("settlement_transactions") or [])
    return rows


def summarize(rows: list[dict]) -> dict:
    """Headline for the Desk: how many series moved, the money at stake in
    the adverse direction, and the five biggest."""
    flagged = [r for r in rows if r.get("flagged")]
    at_stake = sum(r["dollar_impact"] for r in flagged if (r.get("dollar_impact") or 0) > 0)
    top = sorted(
        flagged,
        key=lambda r: (r.get("dollar_impact") is not None, r.get("dollar_impact") or 0),
        reverse=True,
    )[:5]
    return {
        "scanned": len(rows),
        "insufficient": sum(1 for r in rows if r.get("status") == "insufficient_data"),
        "flagged": len(flagged),
        "dollar_impact_total": num(at_stake),
        "top": top,
    }
