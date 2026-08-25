"""Per-item price elasticity from period-over-period price and volume.

Log-log OLS: log(units) ~ log(price) [+ log(sessions)], so the price
coefficient is the elasticity. Guardrails run before any fitting — too few
periods or too little price movement is reported as a status, never as a
number that looks like a finding.
"""

import numpy as np

from .common import num

MIN_PERIODS = 5
MIN_PRICE_CV = 0.02
# When sessions move in lockstep with units, the traffic control absorbs the
# price effect and returns a confidently wrong near-zero elasticity — drop
# the control in that case and say so.
CONTROL_COLLINEARITY_LIMIT = 0.98


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
    covariance = sigma2 * np.linalg.inv(X.T @ X)
    ss_total = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - float(residuals @ residuals) / ss_total if ss_total > 0 else 0.0

    e = float(beta[1])
    se = float(np.sqrt(covariance[1, 1]))
    base["details"]["controls"] = ["sessions"] if use_control else []
    base["details"]["control_dropped_collinear"] = with_sessions and not use_control
    # the interval is the honesty: a wide CI is reported, never hidden
    base["details"]["ci95"] = [num(e - 1.96 * se, 4), num(e + 1.96 * se, 4)]
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
