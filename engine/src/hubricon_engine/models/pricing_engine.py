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

WHAT THE PUBLISHED RANGE IS. The expected profit delta and the range around it
come out of a parametric bootstrap, not out of plugging two elasticity
endpoints into the profit function. Plugging endpoints in is a range of two
point estimates: it ignores uncertainty in the baseline volume Q0, in the fee
structure, and in everything else, and it is not a 95% interval for anything.
`delta_distribution` instead draws

    eps  from its shrunk posterior (Student-t on the fit's own dof),
    Q0   lognormally around the observed baseline at the fit's own residual
         scale — the period a promise is priced against is itself one noisy
         draw from the SKU's demand,
    f, F from the dispersion of the SKU's own fee history where two or more
         periods exist,
    c    fixed, because landed cost is a number the client states rather than
         a quantity the engine measures; cost_cv carries it when the client's
         own sheet moves,

evaluates the profit delta on every draw, and publishes P5 / P50 / P95,
P(delta < 0), and the Monte Carlo standard error of each percentile. The draws
are seeded, so the same input returns the same directive.

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

import numpy as np

from .common import num
from .mc import quantiles_with_se

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
# Draws in the profit-delta bootstrap. 6,000 puts the Monte Carlo standard
# error of the P5 at roughly a fiftieth of the P5-to-P95 width — small enough
# that re-running cannot move a recommendation, cheap enough to run on every
# SKU of a 400-SKU catalog three times a cycle. Raising it buys precision in
# the published percentiles and nothing else.
MC_DRAWS = 6000
# Fixed seed: a directive must be reproducible from its inputs alone, and the
# same draws across SKUs (common random numbers) make two SKUs' ranges
# comparable rather than differing by which stream they happened to get.
MC_SEED = 20260911
# With no fitted residual scale — a fixture, or a fit that came back perfect —
# demand still is not known to the unit. This is the counting-noise floor: a
# Poisson process with mean Q0 has log-scale sd 1/sqrt(Q0), the least
# variability any unit-count series can honestly claim.
POISSON_FLOOR = True
# The baseline volume a promise is priced against is ONE observed period, and
# the period the promise is about is ANOTHER. Two independent demand draws, so
# the uncertainty in the ratio between them is twice the per-period variance —
# sqrt(2) on the log-scale standard deviation. Dropping this would publish a
# band that is narrower than the thing it is a band for by 41%.
BASELINE_AND_FUTURE = 2.0 ** 0.5


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


def _posterior_se(elasticity_row: dict) -> tuple[float, float | None]:
    """(standard error, dof) of the elasticity estimate the optimizer is using.

    A fit from elasticity.run carries both. A fit that carries only an interval
    — an older run, or a hand-built fixture — has its SE read back off the
    interval and the critical value that drew it, so a caller is never silently
    given a zero-width posterior just because one field is missing."""
    dof = (elasticity_row.get("details") or {}).get("dof")
    se = elasticity_row.get("std_err")
    if se is not None and float(se) > 0:
        return float(se), float(dof) if dof else None
    ci = (elasticity_row.get("details") or {}).get("ci95")
    if ci and len(ci) == 2 and ci[0] is not None and ci[1] is not None:
        t_crit = (elasticity_row.get("details") or {}).get("t_critical") or 1.96
        half = abs(float(ci[1]) - float(ci[0])) / 2.0
        if half > 0 and float(t_crit) > 0:
            return half / float(t_crit), float(dof) if dof else None
    return 0.0, float(dof) if dof else None


def _fee_dispersion(fee_history: list[tuple[float, float]] | None) -> tuple[float, float]:
    """(sd of the proportional rate, sd of the fixed per-unit fee) across the
    SKU's own periods. Period-to-period dispersion, not the standard error of
    the mean: the question is what next period's fee structure will be, and
    that is the predictive spread. One period means no dispersion is
    observable, and none is invented."""
    if not fee_history or len(fee_history) < 2:
        return 0.0, 0.0
    arr = np.asarray(fee_history, dtype=float)
    arr = arr[np.isfinite(arr).all(axis=1)]
    if len(arr) < 2:
        return 0.0, 0.0
    return float(np.std(arr[:, 0], ddof=1)), float(np.std(arr[:, 1], ddof=1))


def delta_draws(*, eps: float, std_err: float, dof: float | None, p0: float, q0: float,
                unit_cost: float, fee_rate: float, fixed_fee: float,
                demand_sd_log: float | None = None,
                fee_history: list[tuple[float, float]] | None = None,
                cost_cv: float = 0.0, draws: int = MC_DRAWS,
                rng: np.random.Generator | None = None) -> dict:
    """One draw set of the uncertain inputs, reusable across candidate prices.

    Returned as arrays so a whole grid of candidate prices can be evaluated on
    the SAME draws — common random numbers, which is what makes two candidate
    steps comparable rather than differing by simulation noise."""
    rng = rng or np.random.default_rng(MC_SEED)
    n = int(draws)

    if std_err > 0:
        shock = rng.standard_t(dof, size=n) if dof and dof >= 1 else rng.standard_normal(n)
        eps_draws = eps + std_err * shock
    else:
        eps_draws = np.full(n, eps)

    sd_log = float(demand_sd_log) if demand_sd_log else 0.0
    if POISSON_FLOOR and q0 > 0:
        sd_log = max(sd_log, 1.0 / np.sqrt(q0))
    sd_log *= BASELINE_AND_FUTURE
    if sd_log > 0:
        # mean-preserving: E[Q0·exp(σZ − σ²/2)] = Q0, so the simulation does
        # not quietly raise the baseline it is measuring against
        q0_draws = q0 * np.exp(sd_log * rng.standard_normal(n) - 0.5 * sd_log**2)
    else:
        q0_draws = np.full(n, q0)

    sd_f, sd_big_f = _fee_dispersion(fee_history)
    f_draws = (np.clip(fee_rate + sd_f * rng.standard_normal(n), 0.0, 0.9)
               if sd_f > 0 else np.full(n, fee_rate))
    big_f_draws = (np.clip(fixed_fee + sd_big_f * rng.standard_normal(n), 0.0, None)
                   if sd_big_f > 0 else np.full(n, fixed_fee))

    c_draws = (np.clip(unit_cost * (1.0 + cost_cv * rng.standard_normal(n)), 0.0, None)
               if cost_cv > 0 else np.full(n, unit_cost))

    return {
        "eps": eps_draws, "q0": q0_draws, "unit_cost": c_draws,
        "fee_rate": f_draws, "fixed_fee": big_f_draws, "p0": p0, "n": n,
        "inputs": {
            "eps_se": round(float(std_err), 6),
            "eps_dof": float(dof) if dof else None,
            "demand_sd_log": round(float(sd_log), 6),
            "fee_rate_sd": round(sd_f, 6),
            "fixed_fee_sd": round(sd_big_f, 6),
            "cost_cv": round(float(cost_cv), 6),
            "draws": n,
            "seed": MC_SEED,
        },
    }


def delta_at(draw_set: dict, p_new: float) -> np.ndarray:
    """The profit-delta draw vector at one candidate price."""
    return profit_delta(draw_set["eps"], draw_set["p0"], draw_set["q0"],
                        draw_set["unit_cost"], draw_set["fee_rate"], p_new,
                        draw_set["fixed_fee"])


def summarize_delta(delta: np.ndarray) -> dict:
    """P5 / P50 / P95 of a profit-delta distribution, P(loss), and the Monte
    Carlo standard error of each published percentile."""
    q = quantiles_with_se(delta, (0.05, 0.50, 0.95))
    finite = delta[np.isfinite(delta)]
    return {
        "p5": num(q[0.05]["value"]),
        "p50": num(q[0.50]["value"]),
        "p95": num(q[0.95]["value"]),
        "mean": num(float(finite.mean())) if finite.size else None,
        "p_loss": num(float((finite < 0).mean()), 4) if finite.size else None,
        "mc_se": {"p5": num(q[0.05]["se"], 3), "p50": num(q[0.50]["se"], 3),
                  "p95": num(q[0.95]["se"], 3)},
        "draws": int(finite.size),
    }


def price_move(margin_row: dict, elasticity_row: dict,
               fee_history: list[tuple[float, float]] | None = None,
               cost_cv: float = 0.0, draws: int = MC_DRAWS,
               rng: np.random.Generator | None = None) -> dict | None:
    """One SKU's recommended move: exact new price, destination optimum
    (elastic only, and only when the fit is far enough from the pole at
    eps = −1 to have one), the expected profit delta per period and the
    5th-to-95th-percentile range around it from a seeded parametric bootstrap
    over every uncertain input. Returns None when nothing honest can be
    recommended.

    `fee_history` is [(proportional rate, fixed per unit)] across the SKU's
    own periods; its dispersion is carried into the range. `cost_cv` carries
    landed-cost dispersion where the client's own sheet shows some."""
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
    details = elasticity_row.get("details") or {}
    ci = details.get("ci95")
    std_err, dof = _posterior_se(elasticity_row)

    destination = None
    if near_unit_elastic(eps, elasticity_row.get("std_err") or std_err, ci):
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

    draw_set = delta_draws(
        eps=eps, std_err=std_err, dof=dof, p0=p0, q0=units,
        unit_cost=unit_cost, fee_rate=fee_rate, fixed_fee=fixed_fee,
        demand_sd_log=details.get("residual_sd_log"),
        fee_history=fee_history, cost_cv=cost_cv, draws=draws, rng=rng,
    )
    dist = summarize_delta(delta_at(draw_set, p_new))

    return {
        "status": status,
        "p0": round(p0, 2),
        "p_new": round(p_new, 2),
        "step_fraction": round(p_new / p0 - 1.0, 6),
        "destination": round(destination, 2) if destination else None,
        # The promise is the median of the simulated distribution, not the
        # plug-in value at epŝ. Both are reported: the plug-in is what the
        # old engine promised and the gap between them is the cost of
        # pretending a noisy parameter was exact.
        "expected_delta": dist["p50"],
        "plugin_delta": num(float(profit_delta(eps, p0, units, unit_cost, fee_rate,
                                               p_new, fixed_fee))),
        # P5 to P95 — a 90% band, named as such everywhere it is printed
        "delta_range": (dist["p5"], dist["p95"]),
        "delta_p5": dist["p5"],
        "delta_p50": dist["p50"],
        "delta_p95": dist["p95"],
        "delta_mean": dist["mean"],
        "p_loss": dist["p_loss"],
        "mc_se": dist["mc_se"],
        "mc_inputs": draw_set["inputs"],
        "fee_rate": round(fee_rate, 6),
        "fixed_fee_per_unit": round(fixed_fee, 6),
        "fee_split": fee_basis,
    }
