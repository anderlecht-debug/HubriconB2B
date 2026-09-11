"""What a simulated percentile is actually worth.

Every number this engine publishes out of a Monte Carlo is an estimate of a
number, and it has its own error bar. Ten thousand crude paths give a P5 whose
standard error can be several percent of the figure itself, and a client
reading "$4,120" off a cash cone deserves to know whether the next run would
have said $4,100 or $3,400. So every published percentile comes with its Monte
Carlo standard error, and the tests assert that error is small relative to the
interval the percentile is describing.

Two estimators live here:

  quantile_se — the asymptotic standard error of a sample quantile,
                sqrt(q(1−q)/n) / f(x_q), with the density at the quantile
                estimated from the spacing of the order statistics (Siddiqui's
                estimator, bandwidth from Bloch & Gastwirth). A quantile in a
                flat stretch of the distribution is badly determined and this
                says so; one in a steep stretch is sharp and this says that too.

  expected_shortfall — the mean of the tail beyond a quantile, and the only
                coherent answer to "how bad is it once I'm there" (Artzner et
                al. 1999; Rockafellar & Uryasev 2000). A 5th percentile is a
                threshold, not a risk measure: it says nothing about whether
                the 1% case is a little worse or catastrophically worse. Its
                standard error is the tail's own sd over the root of the tail
                count, which ignores the second-order term from estimating the
                threshold itself — stated here rather than hidden.
"""

import numpy as np

# Siddiqui bandwidth. The window is symmetric in quantile space and must not
# run off the end of the distribution — a window around the 5th percentile that
# reached from 0 to the 22nd would measure the slope of the body, not the tail,
# and inflate the reported error by half. So the half-width is capped at half
# the distance to the nearer end, and floored at however much is needed to put
# MIN_WINDOW_DRAWS order statistics inside it.
BANDWIDTH_EXPONENT = -0.2        # h ~ n^(-1/5), the usual density-estimation rate
MIN_WINDOW_DRAWS = 20


def quantile_se(draws, q: float) -> float | None:
    """Monte Carlo standard error of the q-quantile of `draws`.

    None when the sample is too small, or when the distribution is flat enough
    at the quantile that no finite density estimate exists (every draw
    identical, for instance) — a None that the caller reports rather than
    replaces with a zero that would claim false precision."""
    x = np.sort(np.asarray(draws, dtype=float).ravel())
    x = x[np.isfinite(x)]
    n = x.size
    if n < 50 or not 0 < q < 1:
        return None
    ceiling = 0.5 * min(q, 1.0 - q)
    floor = MIN_WINDOW_DRAWS / (2.0 * n)
    if floor > ceiling:
        return None   # not enough draws out here to estimate a slope at all
    h = min(max(n ** BANDWIDTH_EXPONENT, floor), ceiling)
    lo_q, hi_q = q - h, q + h
    lo = float(np.quantile(x, lo_q))
    hi = float(np.quantile(x, hi_q))
    spread = hi - lo
    if spread <= 0:
        return None
    density = (hi_q - lo_q) / spread
    if density <= 0:
        return None
    return float(np.sqrt(q * (1 - q) / n) / density)


def quantiles_with_se(draws, qs) -> dict:
    """{q: {"value", "se"}} for each requested quantile, plus the sample size."""
    x = np.asarray(draws, dtype=float).ravel()
    x = x[np.isfinite(x)]
    out = {"n": int(x.size)}
    for q in qs:
        if x.size == 0:
            out[q] = {"value": None, "se": None}
            continue
        out[q] = {"value": float(np.quantile(x, q)), "se": quantile_se(x, q)}
    return out


def expected_shortfall(draws, alpha: float = 0.05, tail: str = "lower") -> dict:
    """Mean of the worst `alpha` of the sample, with its standard error.

    tail="lower" for a quantity where small is bad (a cash trough, a profit
    delta); tail="upper" where large is bad (a loss). Returns the threshold
    quantile beside the shortfall so the pair can be published together — the
    familiar percentile and the tail mean behind it."""
    x = np.asarray(draws, dtype=float).ravel()
    x = x[np.isfinite(x)]
    n = x.size
    if n == 0 or not 0 < alpha < 1:
        return {"threshold": None, "shortfall": None, "se": None, "tail_n": 0, "alpha": alpha}
    if tail == "lower":
        threshold = float(np.quantile(x, alpha))
        worst = x[x <= threshold]
    else:
        threshold = float(np.quantile(x, 1 - alpha))
        worst = x[x >= threshold]
    if worst.size == 0:
        worst = np.array([threshold])
    shortfall = float(worst.mean())
    se = float(np.std(worst, ddof=1) / np.sqrt(worst.size)) if worst.size >= 2 else None
    return {"threshold": threshold, "shortfall": shortfall, "se": se,
            "tail_n": int(worst.size), "alpha": alpha}
