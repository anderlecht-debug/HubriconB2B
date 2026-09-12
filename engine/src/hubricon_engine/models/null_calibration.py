"""How often would this detector fire on nothing at all?

A detector threshold is only meaningful next to the rate at which it fires on
noise. `anomaly.py` runs four detectors over every SKU's fees, every ASIN's
traffic and every campaign's spend: a 400-SKU catalog is thousands of tests a
sweep, and a threshold that fires once in fifty on pure noise produces dozens of
confident alerts every cycle about nothing. False alerts are the fastest way to
lose a seller's trust, and they cost more than missed ones because the seller
stops reading.

Controlling that needs a p-value per test, and three of the four statistics have
no closed form at n = 6 to n = 120: Page's CUSUM maximum, a likelihood-ratio
scan maximised over split points, and a maximum of robust z scores. So the null
distribution of each is simulated once per series length and cached. Every
statistic here is invariant to the location and scale of the series under an
i.i.d. Gaussian null, so the null depends only on the length and the detector's
own tuning — which is what makes caching by length correct rather than
convenient.

THE TAIL. A Monte Carlo p-value cannot be smaller than 1/(R+1), and
Benjamini–Hochberg on a 3,000-test sweep needs resolution down to 1.7e-5 at the
first rank. With R = 4,000 replicates the floor is 2.5e-4, so the strongest
finding on a large catalog would be unable to clear the first BH threshold and
the procedure would reject nothing, ever. Above the 99th percentile of the null
the p-value is therefore extrapolated from an exponential fit to the excesses —
the standard peaks-over-threshold device with the shape parameter held at zero,
which is the conservative choice for a statistic whose tail we have no reason to
believe is heavier than exponential. Rows carry `p_basis` saying which of the
two produced their number, so an extrapolated p-value is never mistaken for a
counted one.

WHAT THE NULL ASSUMES. Independent Gaussian noise with no trend and no
seasonality. A fee series with a slow drift, or a traffic series with a seasonal
shape the weekly decomposition did not remove, will produce p-values that are
too small — the detector is reacting to real structure that is not the step
change it was looking for. That is a limitation of the null, not of the
arithmetic, and it is named in MATH_METHODS.md.
"""

from functools import lru_cache

import numpy as np

# Replicates per cached null distribution. At 4,000 the standard error of a
# p-value near 0.05 is 0.0034, which is small against the Benjamini–Hochberg
# thresholds it feeds; the extrapolated tail handles everything below 0.01.
# Raising it costs a one-off sweep and buys resolution in the counted body only.
NULL_REPLICATES = 4000
# Fixed seed: the same catalog must produce the same alerts on two runs, and a
# simulated null is part of the input to that.
NULL_SEED = 20260911
# Above this quantile of the null, p-values are extrapolated rather than counted.
TAIL_QUANTILE = 0.99
# Control-chart constant: mean moving range -> sigma for n = 2. Mirrors
# anomaly.MR_D2 so the simulated null uses the detector's own scale estimator.
MR_D2 = 1.128


def _normal_panel(n: int, replicates: int) -> np.ndarray:
    """(replicates, n) of standard normal noise. Seeded by length so each
    series length has its own reproducible null."""
    return np.random.default_rng(NULL_SEED + n).standard_normal((replicates, n))


# ── the four statistics, vectorised over replicates ───────────────────────

def _robust_z_stat(y: np.ndarray) -> np.ndarray:
    """|z| of the last point against the median and MAD of everything before."""
    base = y[:, :-1]
    last = y[:, -1]
    median = np.median(base, axis=1)
    deviations = np.abs(base - median[:, None])
    mad = np.median(deviations, axis=1) * 1.4826
    mean_ad = deviations.mean(axis=1) * 1.2533
    scale = np.where(mad > 0, mad, mean_ad)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.abs(last - median) / scale
    return np.where(np.isfinite(z), z, 0.0)


def _cusum_stat(y: np.ndarray, k: float) -> np.ndarray:
    """max over the path of max(S+, S−), on the detector's own standardisation.

    The recursion S+_i = max(0, S+_{i−1} + z_i − k) has the closed form
    S+_i = D_i − min_{m ≤ i} D_m with D the cumulative sum of (z − k) and
    D_{−1} = 0, which vectorises."""
    n = y.shape[1]
    m = max(4, n // 2)
    mu = y[:, :m].mean(axis=1)
    base_sd = y[:, :m].std(axis=1, ddof=1)
    mr_sd = np.abs(np.diff(y, axis=1)).mean(axis=1) / MR_D2
    sd = np.maximum(np.maximum(base_sd, mr_sd), 1e-9)
    z = (y - mu[:, None]) / sd[:, None]

    out = np.empty(len(y))
    for sign in (1.0, -1.0):
        d = np.cumsum(sign * z - k, axis=1)
        prefix_min = np.minimum.accumulate(np.concatenate(
            [np.zeros((len(y), 1)), d[:, :-1]], axis=1), axis=1)
        running = d - np.minimum(prefix_min, 0.0)
        best = running.max(axis=1)
        out = best if sign == 1.0 else np.maximum(out, best)
    return out


def _changepoint_stat(y: np.ndarray, min_segment: int) -> np.ndarray:
    """max over split points of 2·n·½·log(SS_total / SS_split)."""
    n = y.shape[1]
    cs = np.concatenate([np.zeros((len(y), 1)), np.cumsum(y, axis=1)], axis=1)
    cs2 = np.concatenate([np.zeros((len(y), 1)), np.cumsum(y**2, axis=1)], axis=1)
    total = cs2[:, n] - cs[:, n] ** 2 / n
    best = np.zeros(len(y))
    for i in range(min_segment, n - min_segment + 1):
        left = cs2[:, i] - cs[:, i] ** 2 / i
        right = (cs2[:, n] - cs2[:, i]) - (cs[:, n] - cs[:, i]) ** 2 / (n - i)
        split = np.maximum(left + right, total * 1e-12)
        with np.errstate(divide="ignore", invalid="ignore"):
            llr = 0.5 * n * np.log(np.maximum(total, 1e-300) / split)
        best = np.maximum(best, np.where(np.isfinite(llr), llr, 0.0))
    return 2.0 * best


def _spikes_stat(y: np.ndarray) -> np.ndarray:
    """max |z| over every point, against the median and MAD of all of them."""
    median = np.median(y, axis=1)
    deviations = np.abs(y - median[:, None])
    mad = np.median(deviations, axis=1) * 1.4826
    mean_ad = deviations.mean(axis=1) * 1.2533
    scale = np.where(mad > 0, mad, mean_ad)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = deviations / scale[:, None]
    return np.where(np.isfinite(z), z, 0.0).max(axis=1)


_STATISTICS = {
    "robust_z": lambda y, **kw: _robust_z_stat(y),
    "cusum": lambda y, k=0.5, **kw: _cusum_stat(y, k),
    "changepoint": lambda y, min_segment=3, **kw: _changepoint_stat(y, min_segment),
    "spikes": lambda y, **kw: _spikes_stat(y),
}

MIN_N = {"robust_z": 3, "cusum": 2, "changepoint": 4, "spikes": 3}


@lru_cache(maxsize=512)
def null_distribution(statistic: str, n: int, k: float = 0.5,
                      min_segment: int = 3) -> tuple:
    """Sorted null draws of `statistic` at series length `n`, plus the
    exponential tail fit above TAIL_QUANTILE. Cached: a 400-SKU catalog has a
    handful of distinct series lengths, not four hundred."""
    if n < MIN_N.get(statistic, 3):
        return ((), 0.0, 0.0)
    y = _normal_panel(n, NULL_REPLICATES)
    stat = _STATISTICS[statistic](y, k=k, min_segment=min_segment)
    stat = np.sort(stat[np.isfinite(stat)])
    if stat.size == 0:
        return ((), 0.0, 0.0)
    threshold = float(np.quantile(stat, TAIL_QUANTILE))
    excess = stat[stat > threshold] - threshold
    # mean excess is the exponential scale; a degenerate tail falls back to a
    # scale that makes the extrapolation flat rather than explosive
    scale = float(excess.mean()) if excess.size >= 2 else 0.0
    return (tuple(stat.tolist()), threshold, scale)


def p_value(statistic: str, n: int, observed: float, k: float = 0.5,
            min_segment: int = 3) -> tuple[float | None, str]:
    """(p, basis) for an observed statistic at series length n.

    basis is "mc" where the p-value was counted against the simulated null and
    "mc_tail" where it was extrapolated past the counting floor. None where the
    series is too short for a null to exist at all — which the caller reports as
    insufficient data rather than as a non-finding."""
    draws, threshold, scale = null_distribution(statistic, n, k, min_segment)
    if not draws or observed is None or not np.isfinite(observed):
        return None, "unavailable"
    arr = np.asarray(draws)
    if observed <= threshold or scale <= 0:
        # counted, with the conservative (1 + exceedances) / (R + 1) form so a
        # p-value is never exactly zero
        exceed = int(np.count_nonzero(arr >= observed))
        return float((1 + exceed) / (arr.size + 1)), "mc"
    tail_p = (1.0 - TAIL_QUANTILE) * float(np.exp(-(observed - threshold) / scale))
    # never claim less than double precision can carry, and never more than the
    # counted value at the threshold
    return float(max(tail_p, 1e-12)), "mc_tail"


def benjamini_hochberg(p_values: list[float], q: float) -> tuple[list[bool], list[float], float]:
    """(rejected, q_values, the largest p-value that cleared) for one test family.

    Step-up procedure: sort, find the largest rank i with p_i ≤ i·q/m, reject
    everything up to it. The q-values returned are the monotone-adjusted ones, so
    a row can carry its own q rather than only a yes or no.

    BH controls the false discovery rate under independence and under positive
    regression dependence. Two detectors on the SAME series are strongly
    positively dependent, which is the benign case; an adversarial dependence
    structure would need Benjamini–Yekutieli and a log(m) penalty. Named in
    MATH_METHODS.md rather than assumed away."""
    m = len(p_values)
    if m == 0:
        return [], [], 0.0
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, p_values[i] * m / rank)
        adjusted[i] = running
    cutoff = 0.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        if p_values[i] <= rank * q / m:
            cutoff = rank * q / m
            break
    rejected = [adjusted[i] <= q for i in range(m)]
    return rejected, adjusted, cutoff
