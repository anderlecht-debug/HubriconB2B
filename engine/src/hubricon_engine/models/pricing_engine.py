"""Dynamic profit calculus: the analytic price optimum per SKU.

With fitted constant-elasticity demand Q(P) = Q0·(P/P0)^eps and per-unit
economics from the latest margin period, profit is

    Pi(P) = Q(P) · (P·(1 − f) − c − F)

where

    f — the PROPORTIONAL fee rate: the fee that is a percentage of the sale
        (Amazon's referral fee), so it scales with the price.
    F — the FIXED per-unit fee: FBA fulfilment, charged by size and weight,
        plus monthly storage allocated across the period's units. Neither
        moves when the price moves.
    c — landed unit cost (cogs / units).

margin.fee_split does the splitting and names its basis; a channel whose
export reports one blended fee line falls back to treating the whole fee as
proportional (basis "assumed_proportional"), which is what this module did
before the split existed. That fallback biases the optimum DOWN and so
understates the gain from an increase — the conservative direction, and the
report says which basis was used.

Setting dPi/dP = 0 gives the interior maximum, valid only for elastic
demand (eps < −1):

    P* = [(c + F) / (1 − f)] · eps / (1 + eps)

The fixed per-unit fee therefore behaves exactly like extra unit cost, and
the proportional fee grosses the whole thing up — which is why collapsing
the two into one rate moved the optimum the wrong way.

For inelastic SKUs (−1 < eps < 0) profit rises monotonically with price in
this model — there is no interior optimum, so the engine recommends a
bounded upward step instead. Every recommendation is capped at ±5% per
cycle: the fit is local and Buy Box suppression risk is real, so we walk
toward the optimum and re-measure, never teleport.

THE POLE AT eps = −1. The factor eps/(1 + eps) diverges as eps → −1. At
eps = −1.05 it is 21; at eps = −1.02 it is 51. So an estimate of −1.12 with a
standard error of 0.18 does not name a destination at all — it names a price
between "a little above here" and "several times here", and printing the cent
would be a lie with a decimal point on it. The house rule that a thin SKU gets
a status rather than a number applies here, and `price_move` enforces it: when
the confidence interval on eps straddles −1, or epŝ sits within
POLE_GUARD_SIGMAS standard errors of it, no `destination` is emitted and the
recommendation comes back with status "near_unit_elastic".

The DIRECTION survives the pole even though the distance does not. P* > P0
whenever eps/(1 + eps) exceeds P0(1 − f)/(c + F), and that ratio is above 1 for
any SKU with a positive contribution margin while eps/(1 + eps) runs to
infinity as eps → −1 from below and to 1 as eps → −∞. Near the pole the
inequality therefore always holds, from either side: the move is up. A
near-unit-elastic SKU gets a bounded exploratory increase and an honest
sentence about why there is no destination beside it.
"""

STEP_CAP = 0.05          # max fractional price move per cycle
INELASTIC_STEP = 0.03    # bounded test step when no interior optimum exists
MIN_MOVE = 0.005         # under half a percent from optimum: leave it alone
# How close to the pole at eps = −1 is too close to name a destination. Two
# standard errors is the same line the 95% interval draws, so the guard and
# the published interval cannot disagree: if a two-sigma band around epŝ
# touches −1, the distance to the optimum is unbounded and only the direction
# is knowable. Raising this refuses more destinations; lowering it publishes
# cents the data cannot support.
POLE_GUARD_SIGMAS = 2.0


def fee_terms(margin_row: dict) -> tuple[float, float, str]:
    """(proportional rate f, fixed per-unit fee F, basis) for one margin row.

    Reads margin.fee_split when the row carries it; a row from an older run
    (or a caller's hand-built fixture) has only the blended `amazon_fees`
    total, which is the assumed-proportional fallback."""
    revenue = float(margin_row.get("revenue") or 0)
    units = float(margin_row.get("units") or 0)
    split = margin_row.get("fee_split")
    if split and split.get("basis") == "itemized" and revenue > 0 and units > 0:
        f = float(split.get("proportional_rate") or 0)
        big_f = float(split.get("fixed_per_unit") or 0)
        return min(0.9, max(0.0, f)), max(0.0, big_f), "itemized"
    blended = float(margin_row.get("amazon_fees") or 0) / revenue if revenue > 0 else 0.0
    return min(0.9, max(0.0, blended)), 0.0, "assumed_proportional"


def optimal_price(eps: float, unit_cost: float, fee_rate: float,
                  fixed_fee: float = 0.0) -> float | None:
    """P* = [(c + F) / (1 − f)] · eps/(1 + eps). None where no interior
    maximum exists (inelastic or unit-elastic demand, or no landed cost)."""
    if eps >= -1 or not (0 <= fee_rate < 1):
        return None
    contribution_cost = unit_cost + fixed_fee
    if contribution_cost <= 0:
        return None
    return (contribution_cost / (1 - fee_rate)) * (eps / (1 + eps))


def profit(eps: float, p0: float, q0: float, unit_cost: float, fee_rate: float, p: float,
           fixed_fee: float = 0.0):
    """Period profit at price p. Array-safe in `eps`, `q0` and `p` so the
    Monte Carlo can evaluate a whole draw set at once."""
    q = q0 * (p / p0) ** eps
    return q * (p * (1 - fee_rate) - unit_cost - fixed_fee)


def profit_delta(eps: float, p0: float, q0: float, unit_cost: float, fee_rate: float, p_new: float,
                 fixed_fee: float = 0.0):
    args = (p0, q0, unit_cost, fee_rate)
    return profit(eps, *args, p_new, fixed_fee) - profit(eps, *args, p0, fixed_fee)


def near_unit_elastic(eps: float, std_err: float | None, ci: list | tuple | None) -> bool:
    """Is this fit too close to the pole at eps = −1 to name a destination?

    True when the 95% interval straddles −1, or when epŝ is within
    POLE_GUARD_SIGMAS standard errors of it. A fit carrying neither an
    interval nor a standard error states no uncertainty at all — a hand-built
    fixture, or a fit from before this guard existed — and is taken at its
    word rather than refused on a guess about how uncertain it might be."""
    if ci and len(ci) == 2 and ci[0] is not None and ci[1] is not None:
        lo, hi = sorted(float(c) for c in ci)
        if lo <= -1.0 <= hi:
            return True
    if std_err is not None and float(std_err) > 0:
        return abs(1.0 + eps) < POLE_GUARD_SIGMAS * float(std_err)
    return False


def price_move(margin_row: dict, elasticity_row: dict) -> dict | None:
    """One SKU's recommended move: exact new price, destination optimum
    (elastic only, and only when the fit is far enough from the pole at
    eps = −1 to have one), expected profit delta per period, and the 95%
    range. Returns None when nothing honest can be recommended."""
    units = float(margin_row.get("units") or 0)
    revenue = float(margin_row.get("revenue") or 0)
    if units <= 0 or revenue <= 0:
        return None
    if margin_row.get("cogs") is None:
        return None  # no landed cost, no dollar-exact recommendation

    p0 = revenue / units
    fee_rate, fixed_fee, fee_basis = fee_terms(margin_row)
    unit_cost = float(margin_row["cogs"]) / units
    eps = float(elasticity_row["elasticity"])
    ci = (elasticity_row.get("details") or {}).get("ci95")
    std_err = elasticity_row.get("std_err")

    destination = None
    if near_unit_elastic(eps, std_err, ci):
        # the distance is unbounded, the direction is not: a bounded
        # exploratory increase, no destination, and a status that says why
        status = "near_unit_elastic"
        p_new = p0 * (1 + INELASTIC_STEP)
    elif eps < -1:
        status = "optimum"
        p_star = optimal_price(eps, unit_cost, fee_rate, fixed_fee)
        if p_star is None or p_star <= 0:
            return None
        ratio = min(1 + STEP_CAP, max(1 - STEP_CAP, p_star / p0))
        if abs(ratio - 1) < MIN_MOVE:
            return None  # already at the optimum
        p_new = p0 * ratio
        destination = p_star
    elif -1 < eps < 0:
        status = "inelastic_step"
        p_new = p0 * (1 + INELASTIC_STEP)
    else:
        return None

    delta = profit_delta(eps, p0, units, unit_cost, fee_rate, p_new, fixed_fee)
    delta_range = None
    if ci:
        bounds = sorted(
            float(profit_delta(float(e), p0, units, unit_cost, fee_rate, p_new, fixed_fee)) for e in ci
        )
        delta_range = (round(bounds[0], 2), round(bounds[1], 2))

    return {
        "status": status,
        "p0": round(p0, 2),
        "p_new": round(p_new, 2),
        "step_fraction": round(p_new / p0 - 1.0, 6),
        "destination": round(destination, 2) if destination else None,
        "expected_delta": round(delta, 2),
        "delta_range": delta_range,
        "fee_rate": round(fee_rate, 6),
        "fixed_fee_per_unit": round(fixed_fee, 6),
        "fee_split": fee_basis,
    }
