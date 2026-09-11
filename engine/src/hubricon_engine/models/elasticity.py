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

from .common import num

CI_LEVEL = 0.95
# HC3 divides each squared residual by (1 − hᵢ)². A period whose leverage is
# 1 is fitted exactly and carries no residual information; below this floor on
# (1 − hᵢ) the correction is a division by numerical noise, so the fit falls
# back to the classical covariance and says which it used.
MIN_LEVERAGE_SLACK = 1e-6

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


def _fit(points: list[dict]) -> dict:
    """points: [{price, units, sessions?}] — one per period."""
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

    y = np.log([p["units"] for p in usable])
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


def run(data: dict, rng=None, simulations=None) -> list[dict]:
    results = []

    by_asin: dict[str, list[dict]] = {}
    for row in data["asin_traffic"]:
        by_asin.setdefault(row["child_asin"], []).append(row)
    for asin, rows in sorted(by_asin.items()):
        points = [
            {
                "price": (row["ordered_product_sales"] or 0) / row["units_ordered"] if row["units_ordered"] else None,
                "units": row["units_ordered"],
                "sessions": row["sessions"],
            }
            for row in sorted(rows, key=lambda r: r["period_start"])
        ]
        results.append({"level": "asin", "item_id": asin, **_fit(points)})

    by_sku: dict[str, list[dict]] = {}
    for row in data["sku_economics"]:
        by_sku.setdefault(row["sku"], []).append(row)
    for sku, rows in sorted(by_sku.items()):
        points = [
            {
                "price": row["avg_sales_price"]
                or ((row["sales"] or 0) / row["units_sold"] if row["units_sold"] else None),
                "units": row["units_sold"],
            }
            for row in sorted(rows, key=lambda r: r["period_start"])
        ]
        results.append({"level": "sku", "item_id": sku, **_fit(points)})

    return results
