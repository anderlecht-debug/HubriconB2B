"""A bad month is bad across the catalog.

Three simulations in this engine draw each SKU's demand independently: the
inventory sim, the cash-flow cone, and the monthly value-at-risk. Independence
is the most expensive assumption in any of them. If forty SKUs each have a 10%
chance of a bad month and those chances are independent, the chance that half of
them go bad together is effectively zero; if their demand shares a common factor
— a slow season, a category-wide shift, a seller's own traffic dropping — it is
not small at all. The 5th percentile of the aggregate is then far more
optimistic than the truth, and a runway decision is made on it.

This is the dependence-modelling failure that broke correlated-default models in
2008: marginals fitted carefully, the joint assumed away.

THE MODEL. One common factor, Gaussian copula, lognormal marginals:

    r_i = mu_i · exp(sigma_i · (rho·Z_common + sqrt(1 − rho²)·Z_i) − sigma_i²/2)

Z_common is shared by every SKU in a period; Z_i is that SKU's own. The
−sigma_i²/2 is not decoration: without it the lognormal's mean is
mu_i·exp(sigma_i²/2) and the simulation would quietly raise every SKU's demand
above the level it was calibrated to, by 6% at a 35% coefficient of variation.
sigma_i comes from the observed mean and standard deviation by matching moments,
sigma_i = sqrt(ln(1 + (sd/mean)²)), so the marginal mean and variance are the
ones the data showed.

Lognormal rather than the truncated normal these simulations used before: a
normal rate clipped at zero has a mean above the one it was given and no skew,
and demand is multiplicative and right-skewed. The clip mattered most for
exactly the thin, volatile SKUs where the stockout question is live.

ESTIMATING RHO. corr(log r_i, log r_j) = rho² under this model, so the average
pairwise correlation of the panel's log-demand residuals identifies rho. It is
estimated from the cross-sectional mean rather than from N² pairs —
Var_t(mean_i x_it) = (1 + (N−1)·rho_bar)/N for standardised residuals, which
inverts to a stable estimator — and then shrunk toward a conservative default,
because a four-period panel cannot measure a correlation and the cost of
underestimating it is all on the client's side.
"""

import numpy as np

# Average pairwise correlation of log demand assumed when history is too thin to
# measure one. A quarter of a SKU's log-demand variance shared with the catalog,
# i.e. rho = 0.5. Retail panels commonly sit between 0.2 and 0.5 pairwise; this
# is the middle of that, and it is the conservative direction to be wrong in
# because a higher shared factor makes the aggregate tail worse, never better.
DEFAULT_PAIRWISE_CORR = 0.25
# Shrinkage strength, in periods. With PRIOR_PERIODS = 4, a four-period panel
# gets half its own estimate and half the default; a twelve-period panel keeps
# three quarters of its own.
PRIOR_PERIODS = 4
MIN_PANEL_SKUS = 3
MIN_PANEL_PERIODS = 3
MAX_PAIRWISE_CORR = 0.9


def log_sigma(mean_rate: float, sd_rate: float) -> float:
    """Moment-matched lognormal shape: sigma = sqrt(ln(1 + (sd/mean)²))."""
    if mean_rate <= 0 or sd_rate <= 0:
        return 0.0
    cv2 = (sd_rate / mean_rate) ** 2
    return float(np.sqrt(np.log1p(cv2)))


def estimate_pairwise_corr(panel: dict[str, list[float]]) -> dict:
    """Average pairwise correlation of log demand across the catalog.

    `panel` is {sku: [rate per period]} over a COMMON set of periods in the same
    order. Returns the raw estimate, the shrunk one actually used, the weight,
    and the basis — so a number that came mostly from the default says so.
    """
    usable = {k: v for k, v in panel.items() if v and all(r and r > 0 for r in v)}
    lengths = {len(v) for v in usable.values()}
    basis = "estimated"
    raw = None
    n_skus = len(usable)
    periods = min(lengths) if lengths else 0

    if n_skus >= MIN_PANEL_SKUS and periods >= MIN_PANEL_PERIODS:
        x = np.array([np.log(v[:periods]) for v in usable.values()], dtype=float)
        x -= x.mean(axis=1, keepdims=True)
        sd = x.std(axis=1, ddof=1)
        keep = sd > 0
        x, sd = x[keep], sd[keep]
        n_skus = len(x)
        if n_skus >= MIN_PANEL_SKUS:
            x = x / sd[:, None]
            cross = x.mean(axis=0)
            # Var_t(cross-sectional mean) = (1 + (N-1)·rho_bar) / N
            var_cross = float(np.var(cross, ddof=1))
            raw = (n_skus * var_cross - 1.0) / (n_skus - 1)
        else:
            basis = "default_thin_panel"
    else:
        basis = "default_thin_panel"

    if raw is None:
        shrunk, weight = DEFAULT_PAIRWISE_CORR, 0.0
    else:
        weight = periods / (periods + PRIOR_PERIODS)
        shrunk = weight * raw + (1 - weight) * DEFAULT_PAIRWISE_CORR
    shrunk = float(min(MAX_PAIRWISE_CORR, max(0.0, shrunk)))
    return {
        "pairwise_corr": round(shrunk, 4),
        "pairwise_corr_raw": round(float(raw), 4) if raw is not None else None,
        "rho": round(float(np.sqrt(shrunk)), 4),
        "shrinkage_weight": round(float(weight), 4),
        "panel_skus": int(n_skus),
        "panel_periods": int(periods),
        "basis": basis,
        "default_pairwise_corr": DEFAULT_PAIRWISE_CORR,
    }


def multiplier_stream(rng: np.random.Generator, sigmas, shape, rho: float):
    """One SKU's mean-one lognormal multipliers at a time, sharing one factor.

    Materialising (n_skus, n_paths, days) is what a 400-SKU cash cone over 10,000
    paths and 90 days would do, and that is 2.9 GB. The common factor is drawn
    once and held; each SKU's own shock is drawn, used and discarded, so the
    memory is the shape of one SKU's draw however wide the catalog is.

    The draw ORDER is identical to `correlated_multipliers`, so streaming and
    materialising give bit-identical numbers from the same generator — which is
    what lets the tests check one and the engine use the other."""
    sigmas = np.asarray(sigmas, dtype=float)
    rho = float(min(1.0, max(0.0, rho)))
    common = rng.standard_normal(shape)
    # the shared part is the same for every SKU, so it is scaled once rather than
    # once per SKU — on a 400-SKU cone that is 400 fewer passes over 900k floats
    shared = rho * common
    idiosyncratic = np.sqrt(1.0 - rho**2)
    for sigma in sigmas:
        if sigma <= 0:
            yield np.ones_like(common)
            continue
        z = shared + idiosyncratic * rng.standard_normal(shape)
        yield np.exp(sigma * z - 0.5 * sigma**2)


def rate_stream(rng: np.random.Generator, mean_rates, sd_rates, shape, rho: float):
    """(index, rate array) per SKU, one at a time. The streaming form of
    `correlated_rates`, and the one every production caller uses."""
    mean_rates = np.asarray(mean_rates, dtype=float)
    sigmas = [log_sigma(m, s)
              for m, s in zip(mean_rates, np.asarray(sd_rates, dtype=float))]
    for i, multiplier in enumerate(multiplier_stream(rng, sigmas, shape, rho)):
        yield i, mean_rates[i] * multiplier


def correlated_multipliers(rng: np.random.Generator, sigmas, shape, rho: float) -> np.ndarray:
    """Mean-one lognormal multipliers with a shared factor.

    Returns an array of shape (len(sigmas), *shape). Every SKU sees the SAME
    Z_common at the same position of `shape`, so a bad day is bad across the
    catalog; the independent part is drawn per SKU. A rho of 0 reproduces
    independent draws exactly, which is what makes the before/after comparison in
    the tests a fair one."""
    sigmas = np.asarray(sigmas, dtype=float)
    rho = float(min(1.0, max(0.0, rho)))
    common = rng.standard_normal(shape)
    out = np.empty((len(sigmas), *np.shape(common)))
    for i, sigma in enumerate(sigmas):
        if sigma <= 0:
            out[i] = 1.0
            continue
        own = rng.standard_normal(shape)
        z = rho * common + np.sqrt(1.0 - rho**2) * own
        out[i] = np.exp(sigma * z - 0.5 * sigma**2)
    return out


def correlated_rates(rng: np.random.Generator, mean_rates, sd_rates, shape,
                     rho: float) -> np.ndarray:
    """Demand rates with lognormal marginals matched to (mean, sd) and a shared
    factor. Shape (n_skus, *shape)."""
    mean_rates = np.asarray(mean_rates, dtype=float)
    sigmas = [log_sigma(m, s)
              for m, s in zip(mean_rates, np.asarray(sd_rates, dtype=float))]
    multipliers = correlated_multipliers(rng, sigmas, shape, rho)
    broadcast = mean_rates.reshape((-1,) + (1,) * (multipliers.ndim - 1))
    return broadcast * multipliers
