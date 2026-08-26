"""Dynamic profit calculus: the analytic price optimum per SKU.

With fitted constant-elasticity demand Q(P) = Q0·(P/P0)^eps and per-unit
economics from the latest margin period, profit is

    Pi(P) = Q(P) · (P·(1 − f) − c)

where f is the proportional fee rate (amazon_fees / revenue — treats fees
as price-proportional, a documented approximation that is conservative for
the fixed FBA component) and c is unit landed cost (cogs / units).

Setting dPi/dP = 0 gives the interior maximum, valid only for elastic
demand (eps < −1):

    P* = [c / (1 − f)] · eps / (1 + eps)

For inelastic SKUs (−1 < eps < 0) profit rises monotonically with price in
this model — there is no interior optimum, so the engine recommends a
bounded upward step instead. Every recommendation is capped at ±5% per
cycle: the fit is local and Buy Box suppression risk is real, so we walk
toward the optimum and re-measure, never teleport.
"""

STEP_CAP = 0.05          # max fractional price move per cycle
INELASTIC_STEP = 0.03    # bounded test step when no interior optimum exists
MIN_MOVE = 0.005         # under half a percent from optimum: leave it alone


def optimal_price(eps: float, unit_cost: float, fee_rate: float) -> float | None:
    if eps >= -1 or unit_cost <= 0 or not (0 <= fee_rate < 1):
        return None
    return (unit_cost / (1 - fee_rate)) * (eps / (1 + eps))


def profit(eps: float, p0: float, q0: float, unit_cost: float, fee_rate: float, p: float) -> float:
    q = q0 * (p / p0) ** eps
    return q * (p * (1 - fee_rate) - unit_cost)


def profit_delta(eps: float, p0: float, q0: float, unit_cost: float, fee_rate: float, p_new: float) -> float:
    args = (p0, q0, unit_cost, fee_rate)
    return profit(eps, *args, p_new) - profit(eps, *args, p0)


def price_move(margin_row: dict, elasticity_row: dict) -> dict | None:
    """One SKU's recommended move: exact new price, destination optimum
    (elastic only), expected profit delta per period, and the 95% range.
    Returns None when nothing honest can be recommended."""
    units = float(margin_row.get("units") or 0)
    revenue = float(margin_row.get("revenue") or 0)
    if units <= 0 or revenue <= 0:
        return None
    if margin_row.get("cogs") is None:
        return None  # no landed cost, no dollar-exact recommendation

    p0 = revenue / units
    fee_rate = min(0.9, max(0.0, float(margin_row.get("amazon_fees") or 0) / revenue))
    unit_cost = float(margin_row["cogs"]) / units
    eps = float(elasticity_row["elasticity"])

    destination = None
    if eps < -1:
        p_star = optimal_price(eps, unit_cost, fee_rate)
        if p_star is None or p_star <= 0:
            return None
        ratio = min(1 + STEP_CAP, max(1 - STEP_CAP, p_star / p0))
        if abs(ratio - 1) < MIN_MOVE:
            return None  # already at the optimum
        p_new = p0 * ratio
        destination = p_star
    elif -1 < eps < 0:
        p_new = p0 * (1 + INELASTIC_STEP)
    else:
        return None

    delta = profit_delta(eps, p0, units, unit_cost, fee_rate, p_new)
    ci = (elasticity_row.get("details") or {}).get("ci95")
    delta_range = None
    if ci:
        bounds = sorted(
            profit_delta(float(e), p0, units, unit_cost, fee_rate, p_new) for e in ci
        )
        delta_range = (round(bounds[0], 2), round(bounds[1], 2))

    return {
        "p0": round(p0, 2),
        "p_new": round(p_new, 2),
        "destination": round(destination, 2) if destination else None,
        "expected_delta": round(delta, 2),
        "delta_range": delta_range,
    }
