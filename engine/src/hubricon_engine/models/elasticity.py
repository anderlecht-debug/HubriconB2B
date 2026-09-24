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


def eb_shrink(estimates, ses) -> dict:
    """Empirical-Bayes shrinkage of per-item estimates toward their pool.

    ε_shrunk = w·ε̂ + (1 − w)·μ with w = τ² / (τ² + se²), τ² by DerSimonian–Laird,
    μ the precision-weighted pool mean. The posterior SE carries both terms,
    w·se² + (1 − w)²·var(μ). A zero SE floors at the smallest positive SE in
    the pool so the weighting stays finite; an item with no sampling error is
    never shrunk. Returns arrays aligned with the inputs plus the pool
    statistics, so the caller writes the record and nothing else."""
    est = np.asarray(estimates, dtype=float)
    ses = np.asarray(ses, dtype=float)
    positive = ses[ses > 0]
    floor = float(positive.min()) if positive.size else 1.0
    variances = np.maximum(ses, floor) ** 2
    tau2 = _tau_squared(est, variances)
    precision = 1.0 / (variances + tau2)
    mu = float((precision * est).sum() / precision.sum())
    var_mu = float(1.0 / precision.sum())
    weights = np.empty(len(est))
    for i, (own_se, var) in enumerate(zip(ses, variances)):
        if own_se <= 0 or tau2 + var <= 0:
            weights[i] = 1.0
        else:
            weights[i] = tau2 / (tau2 + var)
    shrunk = weights * est + (1.0 - weights) * mu
    post_se = np.sqrt(np.maximum(weights * variances + (1.0 - weights) ** 2 * var_mu, 0.0))
    return {"mu": mu, "var_mu": var_mu, "tau2": tau2, "weights": weights,
            "shrunk": shrunk, "post_se": post_se}


def _shrink(rows: list[dict], group_of) -> None:
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

        eb = eb_shrink(estimates, ses)
        tau2, mu = eb["tau2"], eb["mu"]

        for r, est, weight, shrunk, post_se in zip(members, estimates, eb["weights"],
                                                   eb["shrunk"], eb["post_se"]):
            weight, shrunk, post_se = float(weight), float(shrunk), float(post_se)
            t_crit = float(r["details"].get("t_critical") or 0.0)
            r["details"].update({
                **detail,
                "epsilon_raw": num(est, 4),
                "epsilon_shrunk": num(shrunk, 4),
                "shrinkage_weight": num(weight, 4),
                "pooled_epsilon": num(mu, 4),
                "tau2": num(tau2, 6),
                "std_err_raw": r["std_err"],
                "ci95_raw": r["details"]["ci95"],
                "shrinkage": "empirical_bayes",
            })
            # the optimizer consumes the shrunk value; the raw one stays on
            # the record beside it
            r["elasticity"] = num(shrunk, 4)
            r["std_err"] = num(post_se, 4)
            r["details"]["ci95"] = [num(shrunk - t_crit * post_se, 4),
                                    num(shrunk + t_crit * post_se, 4)]


def run(data: dict, rng=None, simulations=None, groups: dict[str, str] | None = None) -> list[dict]:
    """`groups` maps item_id -> pool name (a category, when a later export
    carries one). Absent, every item of a level pools with the rest of the
    catalog."""
    results = []

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

    groups = groups or {}

    def pool_key(row: dict):
        return (row["level"], groups.get(row["item_id"], "catalog"))

    _shrink(results, pool_key)
    return results
