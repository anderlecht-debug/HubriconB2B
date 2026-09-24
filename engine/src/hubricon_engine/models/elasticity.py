"""Per-item price elasticity from period-over-period price and volume.

Log-log OLS: log(units) ~ log(price) [+ log(sessions)], so the price
coefficient is the elasticity. Guardrails run before any fitting — too few
periods or too little price movement is reported as a status, never as a
number that looks like a finding.

Standard errors are HC3 heteroskedasticity-consistent, not classical. Log-log
demand residuals are not constant-variance across a SKU's price range — a SKU
sells in different volumes at the top and bottom of its range and the noise
scales with it — so the classical σ²(X'X)⁻¹ misstates the interval in a
direction that depends on where the price moved. HC3 (MacKinnon & White 1985)
divides each squared residual by (1 − hᵢ)², the small-sample correction, which
is the whole point at n = 5 where a single high-leverage period otherwise
dominates the fit silently. The point estimate is untouched: only the
covariance changes.

A per-SKU ε is then SHRUNK toward a pooled estimate before any optimizer sees
it. A noisy parameter fed to a nonlinear optimum is the Markowitz pathology:
the optimizer does not know the parameter is noisy, so it emits a confident
number built on sampling error. Empirical Bayes is the standard answer — each
SKU's estimate moves toward the catalog's common elasticity by exactly the
ratio of its own sampling variance to the dispersion between SKUs, so a thin
SKU borrows strength from its neighbours and a well-measured one keeps its
own answer. `epsilon_raw`, `epsilon_shrunk` and `shrinkage_weight` all ride in
`details`; the optimizer consumes the shrunk value and the report shows both.

The pool is the whole catalog within a level (ASIN-level fits pool with ASIN
fits, SKU with SKU). No category taxonomy reaches the engine today, so
`run(groups=...)` takes one if a later export carries it; absent that, the
catalog is the group, which is stated in the payload rather than implied.

The interval is a Student-t interval, not a normal one. At MIN_PERIODS = 5
with an intercept and a price term the residual degrees of freedom are 3, and
the two-sided 97.5% quantile of t(3) is 3.182 — not 1.96. Using the normal
quantile on a five-period SKU published an interval roughly 40% too narrow,
which is the one direction an honesty rule must never fail in. The critical
value and the degrees of freedom behind it ride along in `details` so the
report can show the arithmetic.
"""

import numpy as np
from scipy import stats

from .common import num, period_days

CI_LEVEL = 0.95
# HC3 divides each squared residual by (1 − hᵢ)². A period whose leverage is
# 1 is fitted exactly and carries no residual information; below this floor on
# (1 − hᵢ) the correction is a division by numerical noise, so the fit falls
# back to the classical covariance and says which it used.
MIN_LEVERAGE_SLACK = 1e-6
# Shrinkage needs something to shrink toward. Below three fitted items in a
# pool the between-item dispersion is not estimable, so nothing is shrunk and
# the payload says why.
MIN_POOL_ITEMS = 3

MIN_PERIODS = 5
MIN_PRICE_CV = 0.02
# When sessions move in lockstep with units, the traffic control absorbs the
# price effect and returns a confidently wrong near-zero elasticity — drop
# the control in that case and say so.
CONTROL_COLLINEARITY_LIMIT = 0.98


def _hc3(X: np.ndarray, residuals: np.ndarray, xtx_inv: np.ndarray,
         classical: np.ndarray) -> tuple[np.ndarray, str]:
    """HC3 sandwich covariance, or the classical one where HC3 degenerates.

    V_HC3 = (X'X)⁻¹ X' diag(eᵢ² / (1 − hᵢ)²) X (X'X)⁻¹ with hᵢ the i-th
    diagonal of the hat matrix. Returns (covariance, estimator name) so the
    payload never has to guess which one produced the interval it carries."""
    hat = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    slack = 1.0 - hat
    if not np.all(np.isfinite(slack)) or np.min(slack) <= MIN_LEVERAGE_SLACK:
        return classical, "classical_hc3_degenerate"
    omega = (residuals / slack) ** 2
    hc3 = xtx_inv @ (X.T * omega) @ X @ xtx_inv
    if not np.all(np.isfinite(hc3)) or hc3[1, 1] < 0:
        return classical, "classical_hc3_degenerate"
    return hc3, "HC3"


def _exposure_days(rows: list[dict]) -> list[int] | None:
    """Period length per row, or None if ANY row's dates will not parse.

    All-or-nothing on purpose. Normalising some rows and not others is the very
    correlation between period length and price that the normalisation exists to
    remove, so a partially parseable series is fitted unnormalised and says so in
    `details.exposure_normalised` rather than being silently half-corrected."""
    days = []
    for row in rows:
        try:
            days.append(period_days(str(row["period_start"]), str(row["period_end"])))
        except (ValueError, TypeError, KeyError):
            return None
    return days


def _fit(points: list[dict]) -> dict:
    """points: [{price, units, sessions?, days?}] — one per period.

    `days` normalises units to a DAILY rate before the log is taken, and omitting
    it is a trap rather than an imprecision. The regressand is log units, so a
    period of a different length shifts it by log(days), and if that shift
    correlates with the price — which is exactly what happens when a price step is
    held for one reporting window — it loads straight onto the price coefficient.
    Closed form for a step of size s held one whole a-day window against a b-day
    baseline:

        eps_hat = eps + log(a / b) / log(1 + s)

    Measured against this function with real 15/16-day calendar fortnights and a 5%
    step: bias −1.32. At 14 against 16: −2.74. That is one to three whole units of
    elasticity, pointing at "cut the price", on a catalog of ordinary monthly
    exports the moment anybody asks for fortnightly ones — and a calendar fortnight
    inside a 31-day month forces 15/16, so it is unavoidable rather than unlucky.

    On equal-length periods the correction is worth about 1.5% on the standard error
    and nothing on the bias, which is why it reads as a nicety. It is not one: it is
    the gate on any change to export cadence."""
    usable = [p for p in points if p["price"] and p["price"] > 0 and p["units"] and p["units"] > 0]
    n = len(usable)
    base = {"n_periods": n, "details": {"points": [
        {k: num(v, 4) for k, v in p.items()} for p in usable
    ]}}
    if n < MIN_PERIODS:
        return {**base, "status": "insufficient_data"}

    prices = np.array([p["price"] for p in usable], dtype=float)
    price_cv = float(np.std(prices) / np.mean(prices))
    base["price_cv"] = num(price_cv, 4)
    if price_cv < MIN_PRICE_CV:
        return {**base, "status": "insufficient_price_variation"}

    # units per day, not units per period — see the docstring
    y = np.log([float(p["units"]) / max(1e-9, float(p.get("days") or 1)) for p in usable])
    cols = [np.ones(n), np.log(prices)]
    with_sessions = all(p.get("sessions") and p["sessions"] > 0 for p in usable)
    use_control = False
    if with_sessions:
        log_sessions = np.log([p["sessions"] for p in usable])
        spread = float(np.std(log_sessions)) > 0 and float(np.std(y)) > 0
        collinear = not spread or abs(float(np.corrcoef(log_sessions, y)[0, 1])) > CONTROL_COLLINEARITY_LIMIT
        if not collinear:
            cols.append(log_sessions)
            use_control = True
    X = np.column_stack(cols)
    if n <= X.shape[1]:
        return {**base, "status": "insufficient_data"}

    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    residuals = y - X @ beta
    dof = n - X.shape[1]
    sigma2 = float(residuals @ residuals) / dof if dof > 0 else 0.0
    xtx_inv = np.linalg.inv(X.T @ X)
    classical = sigma2 * xtx_inv
    covariance, se_estimator = _hc3(X, residuals, xtx_inv, classical)
    ss_total = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - float(residuals @ residuals) / ss_total if ss_total > 0 else 0.0

    e = float(beta[1])
    se = float(np.sqrt(covariance[1, 1]))
    base["details"]["se_estimator"] = se_estimator
    base["details"]["std_err_classical"] = num(float(np.sqrt(classical[1, 1])), 4)
    # The residual scale of log demand: how far a period's units land from the
    # fitted curve, in log points. This is the SKU's own period-to-period
    # demand variability, and it is what the profit-delta simulation draws q0
    # from — the baseline volume a promise is priced against is not known
    # exactly either.
    base["details"]["residual_sd_log"] = num(float(np.sqrt(sigma2)), 6)
    period_lengths = sorted({int(p.get("days") or 1) for p in usable})
    base["details"]["period_days"] = period_lengths
    base["details"]["exposure_normalised"] = any(p.get("days") for p in usable)
    # dof = 3 on a five-period SKU with a price term and an intercept. The
    # t quantile there is 3.18; the normal's 1.96 would understate the
    # interval by 38%.
    t_crit = float(stats.t.ppf(0.5 + CI_LEVEL / 2, dof))
    base["details"]["controls"] = ["sessions"] if use_control else []
    base["details"]["control_dropped_collinear"] = with_sessions and not use_control
    base["details"]["dof"] = int(dof)
    base["details"]["t_critical"] = num(t_crit, 4)
    # the interval is the honesty: a wide CI is reported, never hidden
    base["details"]["ci95"] = [num(e - t_crit * se, 4), num(e + t_crit * se, 4)]
    return {
        **base,
        "status": "ok",
        "elasticity": num(e, 4),
        "std_err": num(se, 4),
        "r_squared": num(r_squared, 4),
    }


def _tau_squared(estimates: np.ndarray, variances: np.ndarray) -> float:
    """Between-item dispersion of the true elasticities, DerSimonian–Laird.

    τ² = max(0, (Q − (k − 1)) / (Σw − Σw²/Σw)) with w = 1/se² and Q the
    weighted heterogeneity sum of squares. τ² = 0 is a real answer, not a
    failure: it says the spread of the fitted ε's is no wider than their own
    sampling noise already explains, and in that case the pooled estimate is
    the better description of every item in it. The payload publishes τ² and
    each item's weight so a fully pooled catalog is visible rather than
    silent."""
    w = 1.0 / variances
    w_sum = float(w.sum())
    if w_sum <= 0:
        return 0.0
    weighted_mean = float((w * estimates).sum() / w_sum)
    q = float((w * (estimates - weighted_mean) ** 2).sum())
    denom = w_sum - float((w**2).sum()) / w_sum
    if denom <= 0:
        return 0.0
    return max(0.0, (q - (len(estimates) - 1)) / denom)


TAU_GRID_POINTS = 240


def eb_shrink(estimates, ses, pool_ses=None, covariates=None) -> dict:
    """Hierarchical-normal shrinkage of per-item estimates toward their pool,
    with the between-item spread τ INTEGRATED OUT rather than plugged in.

    The prior is θ_i ~ N(x_i·β, τ²): with no `covariates`, x_i = 1 and the
    pool is one mean; with them, a regression the data fits — each item is
    pulled toward what items like it show, not toward one catalogue number.
    Conditional on τ: β is its generalised-least-squares estimate with
    covariance V_β, and θ_i | y ~ N(B_i·x_iβ + (1 − B_i)·y_i,
    (1 − B_i)·s_i² + B_i²·x_iV_βx_i') with B_i = s_i²/(s_i² + τ²). τ gets a
    uniform prior on a grid from 0 to three times the spread of the
    estimates, and its posterior is the restricted marginal likelihood of the
    estimates with β integrated under a flat prior (Gelman et al., BDA §5.4,
    with covariates as in Fay and Herriot); τ² itself has a flat prior. Every
    published figure is the mixture over that posterior.

    Corrected 2026-09-24. The rule before this plugged in the
    DerSimonian–Laird point estimate of τ², which comes out at zero on an
    unlucky catalogue: every item was then pulled onto the pool mean with a
    posterior standard error of the pool mean's alone. On twenty simulated
    catalogues of 80 SKUs whose true elasticities spread over two units, two
    catalogues published 95% intervals that held the truth for 19% and 25%
    of SKUs; integrated over τ, the worst holds it for 86–89% at the same
    squared error. The DerSimonian–Laird figure is still published beside
    the posterior as `tau2_dl`.

    `pool_ses`, when given, is the standard error used to learn β and τ:
    a small-sample robust (HC3) error deliberately overstates each item's
    noise, and overstated noise makes real between-item spread look like
    noise — so the pool is learned on the classical errors and each item's
    own posterior uses its robust one. An item with no sampling error is
    never shrunk. Returns arrays aligned with the inputs plus the pool
    statistics, so the caller writes the record and nothing else."""
    est = np.asarray(estimates, dtype=float)
    ses = np.asarray(ses, dtype=float)
    k = len(est)
    positive = ses[ses > 0]
    floor = float(positive.min()) if positive.size else 1.0
    v = np.maximum(ses, floor) ** 2
    if pool_ses is not None:
        ps = np.asarray(pool_ses, dtype=float)
        ps = np.where(np.isfinite(ps) & (ps > 0), ps, np.maximum(ses, floor))
        pv = np.maximum(ps, floor * 1e-3) ** 2
    else:
        pv = v
    X = np.ones((k, 1)) if covariates is None else np.asarray(covariates, dtype=float).reshape(k, -1)
    spread = float(np.std(est)) if k > 1 else 0.0
    taus = np.linspace(0.0, max(3.0 * spread, 1e-9), TAU_GRID_POINTS)
    G = len(taus)
    loglik = np.full(G, -np.inf)
    prior_mean = np.zeros((G, k))
    prior_var = np.zeros((G, k))       # x_i V_β x_i', the prior mean's own uncertainty
    betas = np.zeros((G, X.shape[1]))
    for g, tau in enumerate(taus):
        w = 1.0 / (pv + tau**2)
        xtwx = X.T @ (X * w[:, None])
        try:
            v_beta = np.linalg.inv(xtwx)
        except np.linalg.LinAlgError:
            continue
        beta = v_beta @ (X.T @ (w * est))
        resid = est - X @ beta
        sign, logdet = np.linalg.slogdet(v_beta)
        if sign <= 0:
            continue
        loglik[g] = 0.5 * logdet + 0.5 * np.log(w).sum() - 0.5 * (w * resid**2).sum()
        prior_mean[g] = X @ beta
        prior_var[g] = np.einsum("ij,jk,ik->i", X, v_beta, X)
        betas[g] = beta
    # a flat prior on τ², so p(τ) ∝ τ on this grid. Where the pool carries
    # little information about its own spread (five noisy periods, 600 SKUs
    # whose sampling variance is ten times the spread) the posterior of τ is
    # the prior's, and flat-on-τ leaned small: extreme SKUs were shrunk past
    # the truth and their profit bands held it for 82%. Flat on τ² errs wide,
    # the safe side: 91% there, and the worst of twelve catalogues' elasticity
    # coverage 0.95 instead of 0.85 (2026-09-24).
    post = np.exp(loglik - loglik.max()) * np.maximum(taus, 1e-12)
    post /= post.sum()
    t2 = taus[:, None] ** 2
    B = v[None, :] / (v[None, :] + t2)
    theta = B * prior_mean + (1.0 - B) * est[None, :]
    var_i = (1.0 - B) * v[None, :] + B**2 * prior_var
    shrunk = (post[:, None] * theta).sum(axis=0)
    post_var = (post[:, None] * (var_i + (theta - shrunk[None, :]) ** 2)).sum(axis=0)
    weights = (post[:, None] * (1.0 - B)).sum(axis=0)
    fixed = ses <= 0
    shrunk = np.where(fixed, est, shrunk)
    post_var = np.where(fixed, v, post_var)
    weights = np.where(fixed, 1.0, weights)
    mean_prior = (post[:, None] * prior_mean).sum(axis=0)
    var_prior = (post[:, None] * (prior_var + (prior_mean - mean_prior[None, :]) ** 2)).sum(axis=0)
    beta_bar = (post[:, None] * betas).sum(axis=0)
    cdf = np.cumsum(post)
    tau_ci = [float(taus[min(G - 1, int(np.searchsorted(cdf, 0.05)))]),
              float(taus[min(G - 1, int(np.searchsorted(cdf, 0.95)))])]
    return {"mu": float(mean_prior.mean()), "var_mu": float(var_prior.mean()),
            "prior_mean": mean_prior, "prior_var": var_prior, "beta": beta_bar,
            "tau2": float((post * taus**2).sum()), "tau_ci90": tau_ci,
            "tau2_dl": _tau_squared(est, pv), "weights": weights, "shrunk": shrunk,
            "post_se": np.sqrt(np.maximum(post_var, 0.0))}


# The seller's own price as evidence about elasticity. At the price that
# maximises p^ε·(p(1 − f) − c − F), ε = −k/(k − 1) with k = p(1 − f)/(c + F):
# a SKU's current markup IMPLIES an elasticity. Whether the seller's prices
# carry that information is not assumed — the pool regresses each fitted ε
# on its markup-implied value and the data sets the slope: near zero for a
# catalogue priced at random, near one for a seller already at the optimum.
# Added 2026-09-24, after the model-risk bench's already-optimal catalogue:
# shrinking every SKU toward one catalogue mean pulled a high-markup SKU
# (true ε −1.3) toward −1.8, the implied optimum moved away from a price that
# was already right, and all 54 steps drafted there lost money against 15.7
# the engine quoted.
MARKUP_MIN_ITEMS = 20
MARKUP_K_FLOOR = 1.05          # a markup this thin implies an elasticity the fit could never resolve
MARKUP_EPS_FLOOR = -8.0


def markup_implied_elasticity(data: dict) -> dict[str, float]:
    """{sku: −k/(k − 1)} from each SKU's latest period, where the landed cost
    is on file and the markup clears MARKUP_K_FLOOR."""
    cost = {}
    for c in data.get("cogs_inputs") or []:
        if c.get("sku") and c.get("unit_cost_usd") is not None:
            cost[c["sku"]] = float(c["unit_cost_usd"]) + float(c.get("inbound_freight_per_unit_usd") or 0.0)
    latest = {}
    for r in data.get("sku_economics") or []:
        if r.get("sku") and r.get("units_sold") and float(r["units_sold"]) > 0:
            if r["sku"] not in latest or str(r["period_start"]) > str(latest[r["sku"]]["period_start"]):
                latest[r["sku"]] = r
    out = {}
    for sku, r in latest.items():
        if sku not in cost:
            continue
        units, sales = float(r["units_sold"]), float(r.get("sales") or 0)
        if sales <= 0:
            continue
        price = sales / units
        prop = -(float(r.get("referral_fees") or 0) + float(r.get("other_fees") or 0)) / sales
        fixed = -(float(r.get("fba_fulfillment_fees") or 0) + float(r.get("storage_fees") or 0)) / units
        denom = cost[sku] + max(fixed, 0.0)
        if denom <= 0:
            continue
        k = price * (1.0 - min(max(prop, 0.0), 0.9)) / denom
        if k <= MARKUP_K_FLOOR:
            continue
        out[sku] = max(-k / (k - 1.0), MARKUP_EPS_FLOOR)
    return out


def prices_optimal_probability(estimates, pool_var, implied) -> dict | None:
    """Posterior probability that the catalogue's prices are ALREADY at their
    optimum: model M0, ε_i equal to the markup-implied elasticity (no free
    parameter), against M1, the pooled regression ε_i ~ N(a + b·implied_i, τ²)
    (three), each SKU's fitted ε carrying its own sampling variance. Equal
    prior odds; the Bayes factor by BIC. None below MARKUP_MIN_ITEMS.

    Added 2026-09-24. On a catalogue priced exactly at its optimum every
    SKU's elasticity error is the one shared error of the pool, a first-order
    edge appears on paper wherever that error points, and the true loss is
    second-order — the model-risk bench's already-optimal world drafted 78
    small steps that all lost against 34% quoted. What tells that world apart
    is not any one SKU but the whole catalogue lying on the line its own
    markups imply; this is the test for it."""
    y = np.asarray(estimates, dtype=float)
    v = np.asarray(pool_var, dtype=float)
    x = np.asarray(implied, dtype=float)
    n = len(y)
    if n < MARKUP_MIN_ITEMS:
        return None
    ll0 = float(-0.5 * np.sum(np.log(2 * np.pi * v) + (y - x) ** 2 / v))
    X = np.column_stack([np.ones(n), x])
    spread = float(np.std(y))
    best = -np.inf
    for tau in np.linspace(0.0, max(3.0 * spread, 1e-9), 160):
        w = 1.0 / (v + tau**2)
        try:
            beta = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * y))
        except np.linalg.LinAlgError:
            continue
        r = y - X @ beta
        best = max(best, float(-0.5 * np.sum(np.log(2 * np.pi / w) + w * r**2)))
    delta_bic = (-2.0 * ll0) - (-2.0 * best + 3.0 * np.log(n))
    w0 = float(1.0 / (1.0 + np.exp(np.clip(delta_bic / 2.0, -50, 50))))
    return {"p_prices_optimal": w0, "delta_bic": float(delta_bic), "n": n}


MODERATE_MIN_ITEMS = 10


def _trigamma_inverse(y: float) -> float:
    """x with ψ'(x) = y, by Newton on the reciprocal (Smyth 2004, appendix)."""
    from scipy.special import polygamma
    if y > 1e7:
        return 1.0 / np.sqrt(y)
    if y < 1e-6:
        return 1.0 / y
    x = 0.5 + 1.0 / y
    for _ in range(50):
        tri = float(polygamma(1, x))
        dif = tri * (1.0 - tri / y) / float(polygamma(2, x))
        x += dif
        if -dif / x < 1e-8:
            break
    return x


def moderate_variances(s2, dof) -> dict | None:
    """Empirical-Bayes moderation of per-item residual variances (Smyth 2004,
    the "moderated t" of limma): each s_i² on d_i degrees of freedom is
    pulled toward a pooled s0² carried by d0 prior degrees of freedom,
    s̃_i² = (d0·s0² + d_i·s_i²)/(d0 + d_i), with (d0, s0²) fitted to the
    spread of log s_i² beyond what sampling alone gives it. Returns the
    moderated variances and d0, or None with too few items.

    Added 2026-09-24. On seven monthly points a SKU's own residual variance
    is a noisy number, and a SKU whose variance came out small by luck was
    treated as precisely fitted: the model-risk bench's thin world published
    elasticities of −10.9 and −5.8 with standard errors near one against
    truths of −3.1 and −2.7, and drafted full steps on them."""
    from scipy.special import digamma, polygamma
    s2 = np.asarray(s2, dtype=float)
    d = np.asarray(dof, dtype=float)
    ok = np.isfinite(s2) & (s2 > 0) & (d > 0)
    if ok.sum() < MODERATE_MIN_ITEMS:
        return None
    z = np.log(s2[ok])
    e = z - digamma(d[ok] / 2.0) + np.log(d[ok] / 2.0)
    e_bar = float(e.mean())
    n = int(ok.sum())
    excess = float(((e - e_bar) ** 2).sum() / (n - 1) - np.mean(polygamma(1, d[ok] / 2.0)))
    if excess > 0:
        d0 = 2.0 * _trigamma_inverse(excess)
        s0 = float(np.exp(e_bar + digamma(d0 / 2.0) - np.log(d0 / 2.0)))
    else:
        d0 = np.inf
        s0 = float(np.exp(e_bar))
    moderated = np.where(ok, s0 if not np.isfinite(d0) else (d0 * s0 + d * s2) / (d0 + d), s2)
    return {"moderated": moderated, "d0": d0, "s0": s0}


def _shrink(rows: list[dict], group_of, markup: dict[str, float] | None = None) -> None:
    """Empirical-Bayes shrinkage of each fitted ε toward its pool, in place.

    ε_shrunk = w·ε̂ + (1 − w)·μ with w = τ² / (τ² + se²) — the ratio of
    between-item dispersion to this item's own sampling variance, which is
    exactly James–Stein with a per-item variance. The posterior standard error
    carries both terms: w·se² from the item's own fit plus (1 − w)²·var(μ)
    from the pooled mean it borrowed, so borrowing strength is not free.

    An item fitted exactly (se = 0) is never shrunk: there is no sampling
    error to pull on."""
    pools: dict[object, list[dict]] = {}
    for r in rows:
        if r.get("status") == "ok" and r.get("elasticity") is not None:
            pools.setdefault(group_of(r), []).append(r)

    for key, members in pools.items():
        # the residual variances moderated across the pool first: every
        # standard error and critical value below rides on the moderated one
        mod = moderate_variances([float((r["details"].get("residual_sd_log") or 0.0)) ** 2 for r in members],
                                 [float(r["details"].get("dof") or 0) for r in members])
        if mod is not None:
            for r, s2m in zip(members, mod["moderated"]):
                det = r["details"]
                s2 = float(det.get("residual_sd_log") or 0.0) ** 2
                # a reaction-corrected fit's error is not its static residual's:
                # the biased slope absorbed part of every shock, so moderating
                # that residual re-weights the pool on the wrong number
                if s2 <= 0 or det.get("source") == "experiment" or "epsilon_uncorrected" in det:
                    continue
                ratio = float(np.sqrt(s2m / s2))
                dof_m = float(det.get("dof") or 0) + (mod["d0"] if np.isfinite(mod["d0"]) else 1e6)
                # the critical value stays on the item's OWN degrees of freedom:
                # the moderated variance fixes a lucky-small residual, but the
                # interval must also carry what no variance model sees (a
                # reacting seller's SKU-by-SKU bias), and the moderated dof
                # took reacting catalogues' coverage from 0.93 to 0.84
                t_crit = float(det.get("t_critical") or stats.t.ppf(0.5 + CI_LEVEL / 2, max(dof_m, 1)))
                det["std_err_unmoderated"] = r["std_err"]
                # the demand noise a promise draws is this residual too: a
                # lucky-small one made a thin SKU's profit band too narrow
                det["residual_sd_log_raw"] = det.get("residual_sd_log")
                det["residual_sd_log"] = num(float(np.sqrt(s2m)), 6)
                det["variance_moderation"] = {"ratio": num(ratio, 4), "prior_dof": num(mod["d0"], 3)
                                              if np.isfinite(mod["d0"]) else "inf", "pooled_sd_log": num(np.sqrt(mod["s0"]), 6)}
                r["std_err"] = num(float(r["std_err"] or 0.0) * ratio, 4)
                if det.get("std_err_classical") is not None:
                    det["std_err_classical_raw"] = det["std_err_classical"]
                    det["std_err_classical"] = num(float(det["std_err_classical"]) * ratio, 4)
                if det.get("std_err_uncorrected") is not None:
                    det["std_err_uncorrected"] = num(float(det["std_err_uncorrected"]) * ratio, 4)
                det["t_critical"] = num(t_crit, 4)
                det["dof_moderated"] = num(dof_m, 3)
                e = float(r["elasticity"])
                det["ci95"] = [num(e - t_crit * float(r["std_err"]), 4), num(e + t_crit * float(r["std_err"]), 4)]
        estimates = np.array([float(r["elasticity"]) for r in members], dtype=float)
        ses = np.array([float(r["std_err"] or 0.0) for r in members], dtype=float)
        detail = {"pool": key[-1], "pool_n": len(members)}

        if len(members) < MIN_POOL_ITEMS:
            for r in members:
                r["details"].update({**detail, "epsilon_raw": r["elasticity"],
                                     "epsilon_shrunk": r["elasticity"],
                                     "shrinkage_weight": 1.0,
                                     "pooled_epsilon": None, "tau2": None,
                                     "shrinkage": "none_pool_too_small"})
            continue

        classical = np.array([float(r["details"].get("std_err_classical") or r["std_err"] or 0.0)
                              for r in members], dtype=float)
        covariates = None
        has = np.array([bool(markup) and r.get("level") == "sku" and r["item_id"] in markup for r in members])
        if markup and has.sum() >= MARKUP_MIN_ITEMS:
            xm = np.array([markup.get(r["item_id"], 0.0) if h else 0.0 for r, h in zip(members, has)])
            cols = [np.ones(len(members)), xm]
            if not has.all():
                cols.insert(1, has.astype(float))
            covariates = np.column_stack(cols)
        eb = eb_shrink(estimates, ses, pool_ses=classical, covariates=covariates)
        tau2, mu = eb["tau2"], eb["mu"]
        markup_slope = float(eb["beta"][-1]) if covariates is not None else None
        optimal = None
        if covariates is not None:
            optimal = prices_optimal_probability(estimates[has], np.maximum(classical[has], 1e-6) ** 2,
                                                 [markup[r["item_id"]] for r, h in zip(members, has) if h])

        for r, est, weight, shrunk, post_se, pm, pvar in zip(members, estimates, eb["weights"], eb["shrunk"],
                                                            eb["post_se"], eb["prior_mean"], eb["prior_var"]):
            weight, shrunk, post_se = float(weight), float(shrunk), float(post_se)
            if r["details"].get("source") == "experiment":
                # An experimental estimate is unbiased; the pool mean is the
                # observational one and carries the reactive-pricing bias, so
                # shrinking toward it would pull the bias back in. It still
                # informs μ and τ² for the observational rows around it.
                weight, shrunk, post_se = 1.0, est, float(r["std_err"] or 0.0)
                r["details"]["shrinkage"] = "none_experimental"
            t_crit = float(r["details"].get("t_critical") or 0.0)
            corrected = "epsilon_uncorrected" in r["details"]
            r["details"].update({
                **detail,
                # raw is the fit as fitted; a reaction-corrected estimate is
                # what entered the pool, published beside it
                "epsilon_raw": r["details"]["epsilon_uncorrected"] if corrected else num(est, 4),
                "epsilon_corrected": num(est, 4) if corrected else None,
                "epsilon_shrunk": num(shrunk, 4),
                "shrinkage_weight": num(weight, 4),
                "pooled_epsilon": num(mu, 4),
                "pooled_epsilon_se": num(float(np.sqrt(eb["var_mu"])), 4),
                "prior_epsilon": num(float(pm), 4),
                "prior_epsilon_se": num(float(np.sqrt(max(pvar, 0.0))), 4),
                "markup_slope": num(markup_slope, 4) if markup_slope is not None else None,
                "p_prices_optimal": (num(optimal["p_prices_optimal"], 4)
                                     if optimal and markup and r["item_id"] in markup else None),
                "markup_implied_epsilon": num(markup.get(r["item_id"]), 4) if markup and r["item_id"] in markup else None,
                "tau2": num(tau2, 6),
                "tau_ci90": [num(x, 4) for x in eb["tau_ci90"]],
                "tau2_dl": num(eb["tau2_dl"], 6),
                "std_err_raw": r["details"].get("std_err_uncorrected", r["std_err"]),
                "ci95_raw": r["details"].get("ci95_uncorrected", r["details"]["ci95"]),
                "shrinkage": r["details"].get("shrinkage") if r["details"].get("shrinkage") == "none_experimental"
                else "empirical_bayes",
            })
            # the optimizer consumes the shrunk value; the raw one stays on
            # the record beside it
            # the part of this item's posterior error it shares with every
            # other item in the pool: the pool mean's, in the share it borrowed
            rb = float(r["details"].get("reaction_bias_se") or 0.0)
            r["details"]["common_se"] = num(float(np.sqrt(((1.0 - weight) * np.sqrt(max(pvar, 0.0))) ** 2 + rb**2)), 4)
            hetero = float(r["details"].get("reaction_bias_heterogeneity") or 0.0)
            if hetero > 0:
                post_se = float(np.sqrt(post_se**2 + hetero**2))
            r["elasticity"] = num(shrunk, 4)
            r["std_err"] = num(post_se, 4)
            r["details"]["ci95"] = [num(shrunk - t_crit * post_se, 4),
                                    num(shrunk + t_crit * post_se, 4)]


# ── the seller's own repricing habit, and the bias it induces ────────────────
# MATH_METHODS.md §2 names the reactive-pricing bias and, until 2026-09-24,
# only disclosed it. The correction built here is the classical one: the
# seller reacts to LAST period's demand, and last period's demand is in the
# export, so a fit that controls for it is unbiased — at the price of two
# more coefficients on a short series. The catalogue then pays for the
# correction once: the seller's habit is the seller's, not the SKU's, so the
# difference between the static and the controlled fit, taken as a median
# over the catalogue, is the bias, estimated with the catalogue's precision
# and subtracted from every SKU's efficient static fit. tests/test_reaction.py
# and the model-risk harness measure it on the generator that produces the
# bias; a simulation-based variant that needed the shock's persistence was
# tried first and dropped, because that persistence cannot be read off the
# residuals of the very regression the reaction biases.
REACTION_T = 2.0            # φ̂ must clear this many standard errors before anything is corrected
REACTION_MIN_PAIRS = 40     # (price, prior residual) pairs across the catalogue
DYNAMIC_MIN_PERIODS = 8     # the controlled fit spends three coefficients on n − 1 points
BIAS_MIN_SKUS = 20          # SKUs with both fits before the catalogue difference is trusted
BIAS_BOOTSTRAP = 200
BIAS_SEED = 20260924


def reaction_diagnostic(data: dict) -> dict:
    """How the seller sets price in response to last period's demand.

    Per SKU, the residual e_t of log units on log price is last period's
    demand surprise; the price the seller then set, log p_{t+1} demeaned
    within the SKU, is regressed on e_t across the catalogue with HC3
    standard errors. φ̂ > 0 and significant is a seller who raises price
    after a good month. ρ̂, the lag-one autocorrelation of the residuals, is
    published for the record and used for nothing: the same reaction that
    biases the slope attenuates it."""
    by_sku: dict[str, list[dict]] = {}
    for r in data.get("sku_economics") or []:
        by_sku.setdefault(r["sku"], []).append(r)
    x_all, y_all, e_pairs = [], [], []
    n_skus = 0
    for sku, rows in by_sku.items():
        rows = sorted(rows, key=lambda r: r["period_start"])
        pts = [(float(r["avg_sales_price"] or ((r.get("sales") or 0) / r["units_sold"])), float(r["units_sold"]),
                period_days(str(r["period_start"]), str(r["period_end"])))
               for r in rows if r.get("units_sold") and float(r["units_sold"]) > 0
               and (r.get("avg_sales_price") or r.get("sales"))]
        if len(pts) < MIN_PERIODS:
            continue
        logp = np.log([p for p, _, _ in pts])
        logq = np.log([u / d for _, u, d in pts])
        if float(np.std(logp)) <= 0:
            continue
        X = np.column_stack([np.ones(len(pts)), logp])
        beta = np.linalg.lstsq(X, logq, rcond=None)[0]
        e = logq - X @ beta
        lp = logp - logp.mean()
        for t in range(len(pts) - 1):
            x_all.append(e[t])
            y_all.append(lp[t + 1])
            e_pairs.append((e[t], e[t + 1]))
        n_skus += 1
    n = len(x_all)
    out = {"n_pairs": n, "n_skus": n_skus}
    if n < REACTION_MIN_PAIRS:
        return {**out, "status": "insufficient_data", "phi": None, "rho": None, "reactive": False}
    x, y = np.array(x_all), np.array(y_all)
    X = np.column_stack([np.ones(n), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    xtx_inv = np.linalg.inv(X.T @ X)
    hat = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    omega = (resid / np.maximum(1 - hat, MIN_LEVERAGE_SLACK)) ** 2
    cov = xtx_inv @ (X.T * omega) @ X @ xtx_inv
    phi, se_phi = float(beta[1]), float(np.sqrt(max(cov[1, 1], 0)))
    e0 = np.array([a for a, _ in e_pairs])
    e1 = np.array([b for _, b in e_pairs])
    rho = float((e0 * e1).sum() / (e0 * e0).sum()) if (e0 * e0).sum() > 0 else 0.0
    return {**out, "status": "ok", "phi": num(phi, 4), "se_phi": num(se_phi, 4),
            "t_phi": num(phi / se_phi, 3) if se_phi > 0 else None, "rho": num(rho, 4),
            "reactive": bool(se_phi > 0 and phi / se_phi >= REACTION_T)}


def _fit_controlled(points: list[dict]) -> dict:
    """log q_t = a + ε log p_t + b log p_{t−1} + γ log q_{t−1} + η_t.

    Under a persistent demand shock and a seller who prices off last period's
    demand, p_t is correlated with the shock only through last period's
    demand, which the two lags carry; η_t is independent of p_t and the
    coefficient on log p_t is ε. HC3 on n − 1 points and four coefficients."""
    usable = [p for p in points if p["price"] and p["price"] > 0 and p["units"] and p["units"] > 0]
    n = len(usable)
    if n < DYNAMIC_MIN_PERIODS:
        return {"status": "insufficient_data", "n_periods": n}
    days = np.array([p.get("days") or 1.0 for p in usable], dtype=float)
    lp = np.log(np.array([p["price"] for p in usable], dtype=float))
    lq = np.log(np.array([p["units"] for p in usable], dtype=float) / days)
    X = np.column_stack([np.ones(n - 1), lp[1:], lp[:-1], lq[:-1]])
    y = lq[1:]
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        xtx_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return {"status": "singular", "n_periods": n}
    resid = y - X @ beta
    hat = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    slack = 1 - hat
    if not np.all(np.isfinite(slack)) or np.min(slack) <= MIN_LEVERAGE_SLACK:
        return {"status": "singular", "n_periods": n}
    omega = (resid / slack) ** 2
    cov = xtx_inv @ (X.T * omega) @ X @ xtx_inv
    se = float(np.sqrt(max(cov[1, 1], 0)))
    if not np.isfinite(se) or se <= 0:
        return {"status": "singular", "n_periods": n}
    return {"status": "ok", "elasticity": float(beta[1]), "std_err": se, "dof": n - 1 - 4,
            "lag_price": float(beta[2]), "lag_demand": float(beta[3]), "n_periods": n}


def _series_of(points: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    usable = [p for p in points if p["price"] and p["price"] > 0 and p["units"] and p["units"] > 0]
    days = np.array([p.get("days") or 1.0 for p in usable], dtype=float)
    return (np.log(np.array([p["price"] for p in usable], dtype=float)),
            np.log(np.array([p["units"] for p in usable], dtype=float) / days))


def _moments(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """(X'X, X'y) of one block after demeaning it — its fixed effect — or None
    for a block too short to carry one."""
    if len(y) < 3:
        return None
    Xd, yd = X - X.mean(axis=0), y - y.mean()
    return Xd.T @ Xd, Xd.T @ yd


def _sku_moments(lp: np.ndarray, lq: np.ndarray) -> dict:
    """One SKU's contribution to the four pooled regressions the reaction
    correction needs: static on the full series, controlled on the full
    series and on each half."""
    def ctl(lo, hi):
        p, q = lp[lo:hi], lq[lo:hi]
        if len(p) < 4:
            return None
        return _moments(np.column_stack([p[1:], p[:-1], q[:-1]]), q[1:])
    h = len(lp) // 2
    return {"static": _moments(lp[:, None], lq), "full": ctl(0, None), "first": ctl(0, h), "second": ctl(h, None)}


def _slope_from(moments: list, key: str) -> float | None:
    parts = [m[key] for m in moments if m[key] is not None]
    if not parts:
        return None
    xtx = sum(a for a, _ in parts)
    xty = sum(b for _, b in parts)
    if np.linalg.matrix_rank(xtx) < xtx.shape[0]:
        return None
    return float(np.linalg.solve(xtx, xty)[0])


def reaction_bias(moments: list[dict]) -> float | None:
    """The catalogue's reaction bias: the pooled static slope less the
    half-panel-jackknifed pooled controlled slope, from each SKU's stored
    regression moments (so a bootstrap over SKUs is a sum, not a refit).

    Both are pooled over every SKU with a fixed effect each, so both estimate
    the same price-variance-weighted average elasticity. The static one
    carries the reaction bias in full. The controlled one — log units on log
    price, last period's log price and last period's log units — removes it
    to first order, but in a panel this short it is itself biased by terms of
    order 1/T: the coefficient on last period's demand is pulled toward zero
    (Nickell), and a price set in reaction to demand is correlated with the
    SKU's own future shocks once its series is demeaned. The half-panel
    jackknife, 2·β(full) − ½·(β(first half) + β(second half)) (Dhaene and
    Jochmans 2015), removes the 1/T terms without modelling them."""
    static = _slope_from(moments, "static")
    full, first, second = (_slope_from(moments, k) for k in ("full", "first", "second"))
    if static is None or full is None or first is None or second is None:
        return None
    return static - (2.0 * full - 0.5 * (first + second))


def correct_endogeneity(rows: list[dict], data: dict, points_by_sku: dict[str, list[dict]] | None = None) -> dict:
    """Estimate the reaction bias once for the catalogue and subtract it from
    every fitted, non-experimental SKU row's RAW estimate, in place, before
    the pool learns from them — each row's standard error widened by the bias
    estimate's own, which is shared by every row and published as such.
    Returns the diagnostic, which every row also carries under
    details.endogeneity.

    Corrected 2026-09-24 (twice in a day). The first version subtracted a
    trimmed mean of per-SKU (static − controlled) differences; the controlled
    fit's own short-panel bias rode into that difference, and on the
    model-risk bench's reacting catalogues the corrected median error stayed
    at +0.10 to +0.24. The jackknifed pooled correction took the same sixteen
    catalogues (six reactive, six drifting, four of the endogeneity grid) to a
    mean absolute median error of 0.055, the worst +0.166; it also corrects
    the case where the bias runs the other way (no persistence, a reacting
    seller: −0.20 estimated, the corrected error +0.02)."""
    diag = reaction_diagnostic(data)
    applied, reason = False, None
    fitted = [r for r in rows if r.get("level") == "sku" and r.get("status") == "ok"
              and (r.get("details") or {}).get("source") != "experiment" and r.get("elasticity") is not None]
    series, price_var = [], {}
    for r in fitted:
        pts = (points_by_sku or {}).get(r["item_id"]) or (r.get("details") or {}).get("points") or []
        lp, lq = _series_of(pts)
        if len(lp) >= 3:
            price_var[r["item_id"]] = float(np.var(lp - lp.mean()))
        if len(lp) >= DYNAMIC_MIN_PERIODS:
            series.append(_sku_moments(lp, lq))
    price_var_mean = float(np.mean(list(price_var.values()))) if price_var else 0.0
    if diag.get("status") != "ok":
        reason = "too few (price, prior residual) pairs to estimate the habit"
    elif not diag["reactive"]:
        reason = f"no significant reaction to last period's demand (t = {diag['t_phi']})"
    elif len(series) < BIAS_MIN_SKUS:
        reason = f"only {len(series)} SKUs have the {DYNAMIC_MIN_PERIODS} periods the controlled fit needs (need {BIAS_MIN_SKUS})"
    else:
        bias = reaction_bias(series)
        rng = np.random.default_rng(BIAS_SEED)
        boots = []
        for _ in range(BIAS_BOOTSTRAP):
            pick = rng.integers(0, len(series), len(series))
            b = reaction_bias([series[j] for j in pick])
            if b is not None and np.isfinite(b):
                boots.append(b)
        if bias is None or len(boots) < BIAS_BOOTSTRAP // 2:
            reason = "the pooled fits could not be computed on this catalogue"
        else:
            se_bias = float(np.std(boots, ddof=1))
            diag.update({"bias_hat": num(bias, 4), "bias_se": num(se_bias, 4), "n_skus_both_fits": len(series),
                         "t_bias": num(bias / se_bias, 3) if se_bias > 0 else None,
                         "method": "pooled static less half-panel-jackknifed pooled controlled, bootstrap over SKUs"})
            # Applied whenever the habit itself is established: the estimate is
            # then the best guess at a bias theory says exists, and its error
            # rides in every interval. A significance gate on the estimate
            # (there was one, BIAS_T = 2, until 2026-09-24) left a known bias of
            # −0.2 in place on reacting catalogues whose demand had no memory,
            # because an eighty-SKU estimate of it carried a 0.15 error.
            applied = se_bias > 0
    diag["applied"], diag["reason"] = applied, reason
    for r in rows:
        det = r.setdefault("details", {})
        det["endogeneity"] = {k: diag.get(k) for k in ("status", "phi", "t_phi", "rho", "bias_hat", "bias_se",
                                                      "applied", "reason", "method")}
        if not applied or r not in fitted:
            continue
        bias, sd_b = float(diag["bias_hat"]), float(diag["bias_se"])
        t_crit = float(det.get("t_critical") or 1.96)
        det["epsilon_uncorrected"] = r["elasticity"]
        det["std_err_uncorrected"] = r["std_err"]
        det["ci95_uncorrected"] = det.get("ci95")
        det["reaction_bias_se"] = num(sd_b, 4)
        # the catalogue's one correction is right for a SKU of average price
        # variation; a SKU's own static bias scales roughly with the inverse
        # of its own price variance, so the part of its bias the constant
        # misses is carried as uncertainty (not as a correction: the SKU's
        # own variance is too noisy on twelve points to correct by)
        v_i = price_var.get(r["item_id"])
        hetero = bias * (price_var_mean / v_i - 1.0) if v_i and price_var_mean else 0.0
        det["reaction_bias_heterogeneity"] = num(abs(hetero), 4)
        # the shared error enters before the pool; the SKU's own heterogeneity
        # is added to its published interval after it (_shrink), so it widens
        # what the SKU is told without re-weighting what the pool learns
        extra = sd_b**2
        r["elasticity"] = num(float(r["elasticity"]) - bias, 4)
        r["std_err"] = num(float(np.sqrt(float(r["std_err"] or 0.0) ** 2 + extra)), 4)
        if det.get("std_err_classical") is not None:
            det["std_err_classical"] = num(float(np.sqrt(float(det["std_err_classical"]) ** 2 + extra)), 4)
        det["ci95"] = [num(float(r["elasticity"]) - t_crit * float(r["std_err"]), 4),
                       num(float(r["elasticity"]) + t_crit * float(r["std_err"]), 4)]
    return diag


def run(data: dict, rng=None, simulations=None, groups: dict[str, str] | None = None,
        experiments: list[dict] | None = None, correct_reaction: bool = True,
        seasonal: dict | None = None) -> list[dict]:
    """`groups` maps item_id -> pool name (a category, when a later export
    carries one). Absent, every item of a level pools with the rest of the
    catalog.

    `seasonal` is models/seasonality.py's payload. With a catalogue index on
    file the SKU fits run on deseasonalised units (the index divided out;
    see seasonality.deseasonalise_economics): on a catalogue with a 1.6×
    fourth quarter the standard error fell by a third and the cross-price
    fit went from unidentified to identified. Absent, nothing changes.

    `experiments` are models/price_experiment.py analyses. One with status ok
    REPLACES the SKU's observational row before shrinkage — the randomised
    estimate is the one the optimizer should see — and the observational fit
    rides in details.observational beside the bias the experiment measured."""
    results = []
    from .data_quality import clean_for_fitting
    from .seasonality import deseasonalise_economics
    exported = data           # the markup is read off the export as sent, fees and all
    data, cleaning = clean_for_fitting(data)
    data, season_note = deseasonalise_economics(data, seasonal)

    by_asin: dict[str, list[dict]] = {}
    for row in data["asin_traffic"]:
        by_asin.setdefault(row["child_asin"], []).append(row)
    for asin, rows in sorted(by_asin.items()):
        ordered = sorted(rows, key=lambda r: r["period_start"])
        exposure = _exposure_days(ordered)
        points = [
            {
                "price": (row["ordered_product_sales"] or 0) / row["units_ordered"] if row["units_ordered"] else None,
                "units": row["units_ordered"],
                "sessions": row["sessions"],
                "days": exposure[i] if exposure else None,
            }
            for i, row in enumerate(ordered)
        ]
        results.append({"level": "asin", "item_id": asin, **_fit(points)})

    by_sku: dict[str, list[dict]] = {}
    for row in data["sku_economics"]:
        by_sku.setdefault(row["sku"], []).append(row)
    points_by_sku: dict[str, list[dict]] = {}
    for sku, rows in sorted(by_sku.items()):
        ordered = sorted(rows, key=lambda r: r["period_start"])
        exposure = _exposure_days(ordered)
        points = [
            {
                "price": row["avg_sales_price"]
                or ((row["sales"] or 0) / row["units_sold"] if row["units_sold"] else None),
                "units": row["units_sold"],
                "days": exposure[i] if exposure else None,
            }
            for i, row in enumerate(ordered)
        ]
        results.append({"level": "sku", "item_id": sku, **_fit(points)})
        points_by_sku[sku] = points

    for exp in experiments or []:
        if exp.get("status") != "ok" or exp.get("level") != "sku":
            continue
        replaced = None
        for i, r in enumerate(results):
            if r["level"] == "sku" and r["item_id"] == exp["item_id"]:
                replaced = i
                break
        row = {"level": "sku", "item_id": exp["item_id"], "status": "ok",
               "elasticity": exp["elasticity"], "std_err": exp["std_err"], "r_squared": exp.get("r_squared"),
               "n_periods": exp.get("n_periods"), "price_cv": exp.get("price_cv"),
               "details": {**(exp.get("details") or {}), "source": "experiment"}}
        if replaced is None:
            results.append(row)
        else:
            row["details"].setdefault("observational", {
                k: results[replaced].get(k) for k in ("status", "elasticity", "std_err")})
            results[replaced] = row

    groups = groups or {}

    def pool_key(row: dict):
        return (row["level"], groups.get(row["item_id"], "catalog"))

    if correct_reaction:
        # before shrinkage, so the pool learns on corrected estimates
        correct_endogeneity(results, data, points_by_sku)
    _shrink(results, pool_key, markup_implied_elasticity(exported))
    for r in results:
        r.setdefault("details", {})["seasonal_adjustment"] = season_note
        excluded = (cleaning.get("excluded") or {}).get(r.get("item_id"))
        if excluded and r.get("level") == "sku":
            r["details"]["excluded_periods"] = excluded
    return results
