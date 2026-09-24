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

HOW FAR TO WALK. The step used to be a constant: STEP_CAP = 0.05, or
INELASTIC_STEP = 0.03, two numbers doing the job of a derived policy. A SKU
fitted from five noisy periods and one fitted from thirty clean ones got the
same 5%.

The step now falls out of the uncertainty, in the Almgren–Chriss shape: the
DIRECTION comes from the model (toward P*, or up where there is no interior
optimum), and the SIZE comes from the statistics, subject to a risk budget.
Concretely, over a grid of candidate prices inside the hard cap:

  feasible   — the candidate's expected shortfall at 5% (the mean of the worst
               twentieth of outcomes, not merely the percentile at its edge) is
               no worse than RISK_BUDGET_SHARE of the SKU's own trailing monthly
               net. A coherent risk measure, so the constraint behaves when
               directives aggregates across SKUs.
  chosen     — among the feasible candidates, the one that maximises a
               certainty equivalent: E[delta] − Var[delta] / (2·risk tolerance),
               with the SKU's risk tolerance the same dollar budget. Never the
               plug-in expected profit at epŝ, which is what hands a seller a
               confident number built on sampling error.

WHY NOT A PURE QUANTILE OBJECTIVE. The obvious robust objective is "maximise
the 25th percentile of the profit delta", and it does not work — not because it
is wrong but because it cannot size a step. For small moves the delta is
proportional to the step, and every quantile of a positively scaled random
variable scales with it: Q25[s·X] = s·Q25[X]. So the objective is positively
homogeneous in s, its maximum against a box constraint is always a corner, and
the policy collapses to "the full cap, or nothing". Measured, before the
objective was changed: across a sweep of elasticities, margins, demand noise
and standard errors, every single recommendation landed on the cap or on zero.

The fix is the term Almgren and Chriss use for the same reason — a cost
quadratic in the size of the move, which makes the objective strictly concave
and the solution interior. Theirs is market impact. Here it is the variance the
move carries, priced at the SKU's own risk tolerance, which gives exactly the
shape the problem wants: s* = tolerance · (expected gain per unit step) /
(variance per unit step), a rate set by the signal-to-uncertainty ratio. Double
the standard error on epŝ and the step shrinks. At the interior optimum the
variance penalty consumes exactly half the expected gain, whatever the SKU —
that identity is what makes one dimensionless constant enough.

The pure tail objectives are kept and selectable (`objective="quantile"`,
`"cvar"`), because the horse race has to be able to run them and because a
reader expects to see them. tests/test_horse_race.py reports what each earns.

Doing nothing is always a candidate and its delta is exactly zero, so a SKU
whose objective cannot beat zero gets no step at all — the refusal is a
property of the objective, not a threshold bolted on.

The hard cap stays as an outer safety rail, because it is what the client
actually authorised (terms.html §6: price steps of up to five percent per SKU
per cycle) and because the fit is local. Each move reports whether the cap or
the statistics bound it, so a cap that is binding on most of a catalog is
visible rather than assumed.

WHAT IS NOT MODELLED HERE. Almgren–Chriss penalises execution risk with a
convex cost. The execution risk in this problem is Buy Box suppression, and
nothing in the engine's data prices the suppression hazard as a function of
step size — no competitor price series reaches it. A quadratic hazard curve
would make the policy prettier and would be invented, which is the one
substitution this engine does not make. So execution risk is carried by the two
mechanisms that are real: the hard cap, and Buy Box share watched while the
step is live, with the step reversed if it drops. Said plainly in
MATH_METHODS.md as a named limitation.

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

from .common import num, period_days
from .mc import quantiles_with_se

import math

STEP_CAP = 0.05          # hard outer rail on a cycle's move — what the client authorised
INELASTIC_STEP = 0.03    # legacy bounded step; retained for callers that quote it
MIN_MOVE = 0.005         # under half a percent of a move: leave it alone
# The risk-aversion quantile. The engine maximises the 25th percentile of the
# profit-delta distribution rather than its mean. Lowering it (toward 0.05)
# buys protection against the bad tail at the price of leaving money on the
# table on well-measured SKUs; raising it (toward 0.5) walks faster and eats
# more of the variance. 0.25 is the setting under which the robust policy beats
# both the plug-in optimum and a naive fixed step in the out-of-sample horse
# race — see tests/test_horse_race.py.
ROBUST_QUANTILE = 0.25
# How much of a SKU's own trailing monthly net its 5th-percentile outcome may
# put at risk. This is the budget the step size is solved against, and it is
# the same number directives.py enforces before a move can travel under the
# standing mandate. Raising it permits larger steps on thin fits; lowering it
# makes the engine recommend less, more often.
RISK_BUDGET_SHARE = 0.15
# Candidate price resolution inside the cap: 0.25% of price, which on a $20
# item is five cents — finer than the cent the recommendation rounds to.
STEP_GRID = 0.0025
# The step search ranks twenty-one candidates and only has to get the ranking
# right; the published distribution is then computed on the full draw set. A
# deterministic every-third-draw subsample is enough for the ranking and cuts
# the search cost to a third. Raising it does not change a recommendation, only
# how long a 400-SKU sweep takes.
SEARCH_DRAWS = 2000
# Which robust objective sizes the step. "certainty_equivalent" is the default
# and the one the horse race picks; "quantile" and "cvar" are the pure tail
# objectives, kept because they are what a reader expects and because the horse
# race has to be able to run them.
OBJECTIVE = "certainty_equivalent"
# An optional loss gate: when set to a probability, a step is only issued when
# that quantile of its own profit-delta distribution is non-negative (0.25:
# at most a one-in-four chance of losing on the step recommended). Off by
# default. Added 2026-09-24 so the model-risk harness could price the gate:
# on three synthetic worlds it is measured against the certainty-equivalent
# default (MATH_SCORECARD.md, "Model risk, measured on three worlds"); the
# horse race in tests/test_horse_race.py is the standing reason the default
# stays off — the pure-quantile rule earns more per move by declining 40% of
# the catalogue, and puts less money in the payout.
MAX_P_LOSS: float | None = None
# A step is issued only when more of the posterior's draws than not agree that
# a small move in its direction raises profit (own plus family) — the Bayes
# rule for a sign. Set 2026-09-24 after the model-risk bench priced it: at one
# half it removed every step drafted on a catalogue already at its optimum
# (110 over two seeds, all losing) and cost nothing elsewhere ($19,712 of true
# profit against $19,759 without it, four worlds, two seeds). None switches it off.
MIN_DIRECTION_CONFIDENCE: float | None = 0.5
DIRECTION_NUDGE = 0.005
OPTIMAL_MIX_SEED = 20260926
# How close to the pole at eps = −1 is too close to name a destination. Two
# standard errors is the same line the 95% interval draws, so the guard and
# the published interval cannot disagree: if a two-sigma band around epŝ
# touches −1, the distance to the optimum is unbounded and only the direction
# is knowable. Raising this refuses more destinations; lowering it publishes
# cents the data cannot support.
POLE_GUARD_SIGMAS = 2.0
POLE_OPTIMUM_LOG_SD = 0.5     # no destination when one standard error moves the optimum by more than half
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


def near_unit_elastic(eps: float, std_err: float | None, ci: list | tuple | None,
                      fitted: bool = True) -> bool:
    """Is this fit too close to the pole at eps = −1 to name a destination?

    True when the 95% interval straddles −1, when epŝ is within
    POLE_GUARD_SIGMAS standard errors of it, and ALSO when a fitted row carries no
    usable uncertainty at all.

    That last clause closes a hole this guard had until 2026-09-12. The original
    took a missing standard error as a claim of certainty, reasoning that a
    hand-built fixture states no uncertainty and should be taken at its word. But
    `common.num` maps ±inf and NaN to None, so a fit whose standard error came back
    UNBOUNDED arrives here looking exactly like a fixture claiming to be exact —
    and the guard let it through. Measured: a SKU at epŝ = −1.05 whose SE was
    non-finite produced a destination of $123.53 on a $20 item, a full 5% step, a
    dollar promise, and p_loss = 0.0, which the directive prose renders as "under a
    1% chance it goes the other way". Maximum confidence exactly where there is no
    information — the precise failure this guard exists to prevent.

    A FITTED row with no interval and no positive finite standard error is now
    refused. `fitted=False` restores take-it-at-its-word for a caller that
    genuinely is asserting an exact elasticity: a test fixture, or a counterfactual
    evaluated at a named value."""
    if ci and len(ci) == 2 and ci[0] is not None and ci[1] is not None:
        lo, hi = sorted(float(c) for c in ci)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            return True
        if lo <= -1.0 <= hi:
            return True
    if std_err is not None and float(std_err) > 0:
        if not math.isfinite(float(std_err)):
            return True
        if abs(1.0 + eps) < POLE_GUARD_SIGMAS * float(std_err):
            return True
        # the optimum's own relative uncertainty: d log P*/dε = 1/(ε(1+ε)).
        # Added 2026-09-24: a catalogue pooled to a precise ε = −1.05 has an
        # interval that excludes −1, and an optimum of 21× cost that its own
        # interval moves between 13× and 51× — a price no one should be told
        return float(std_err) / abs(eps * (1.0 + eps)) > POLE_OPTIMUM_LOG_SD if eps < -1 else False
    # no usable uncertainty on a fitted row: unbounded, not exact
    return bool(fitted)


def _has_stated_uncertainty(elasticity_row: dict) -> bool:
    """Does this row state ANY usable uncertainty? A row that does not cannot be
    given a zero-width posterior — see near_unit_elastic's docstring."""
    se = elasticity_row.get("std_err")
    if se is not None and float(se) > 0 and math.isfinite(float(se)):
        return True
    ci = (elasticity_row.get("details") or {}).get("ci95")
    return bool(ci and len(ci) == 2 and ci[0] is not None and ci[1] is not None
                and math.isfinite(float(ci[0])) and math.isfinite(float(ci[1]))
                and float(ci[1]) != float(ci[0]))


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
                rng: np.random.Generator | None = None,
                cross: dict | None = None, optimal_mix: tuple[float, float] | None = None) -> dict:
    """One draw set of the uncertain inputs, reusable across candidate prices.

    `optimal_mix` is (w, ε0): with posterior probability w the catalogue already
    prices at its optimum and this SKU's elasticity is ε0, the one its markup
    implies (models/elasticity.prices_optimal_probability). That share of the
    draws is set to ε0, on a stream of its own so every other draw is
    unchanged.

    Returned as arrays so a whole grid of candidate prices can be evaluated on
    the SAME draws — common random numbers, which is what makes two candidate
    steps comparable rather than differing by simulation noise.

    `cross` is the variant family's cross-price effect (models/cross_price.py):
    {eps, std_err, dof, siblings: [{sku, q0, contribution, weight}]}. Its ε is
    drawn last, so a SKU with no family reproduces every draw it made before the
    term existed."""
    rng = rng or np.random.default_rng(MC_SEED)
    n = int(draws)

    if std_err > 0:
        shock = rng.standard_t(dof, size=n) if dof and dof >= 1 else rng.standard_normal(n)
        eps_draws = eps + std_err * shock
    else:
        eps_draws = np.full(n, eps)
    at_optimum = None
    if optimal_mix is not None and optimal_mix[0] is not None and float(optimal_mix[0]) > 0:
        # the already-optimal model's share of the posterior, on its own stream:
        # its own elasticity is the one its markup implies, and — the catalogue
        # being at its optimum — no sibling term survives either (below)
        at_optimum = np.random.default_rng(OPTIMAL_MIX_SEED).random(n) < float(optimal_mix[0])
        eps_draws = np.where(at_optimum, float(optimal_mix[1]), eps_draws)

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

    cross_set = None
    if cross and cross.get("siblings"):
        se_c = float(cross.get("std_err") or 0.0)
        dof_c = cross.get("dof")
        if se_c > 0:
            shock_c = rng.standard_t(dof_c, size=n) if dof_c and dof_c >= 1 else rng.standard_normal(n)
            eps_c = float(cross["eps"]) + se_c * shock_c
        else:
            eps_c = np.full(n, float(cross["eps"]))
        if at_optimum is not None:
            eps_c = np.where(at_optimum, 0.0, eps_c)
        cross_set = {"eps": eps_c,
                     "siblings": [(float(j["q0"]), float(j["contribution"]), float(j["weight"]))
                                  for j in cross["siblings"]]}

    return {
        "eps": eps_draws, "q0": q0_draws, "unit_cost": c_draws,
        "fee_rate": f_draws, "fixed_fee": big_f_draws, "p0": p0, "n": n,
        "cross": cross_set,
        "inputs": {
            "eps_se": round(float(std_err), 6),
            "eps_dof": float(dof) if dof else None,
            "demand_sd_log": round(float(sd_log), 6),
            "fee_rate_sd": round(sd_f, 6),
            "fixed_fee_sd": round(sd_big_f, 6),
            "cost_cv": round(float(cost_cv), 6),
            "draws": n,
            "seed": MC_SEED,
            "cross_eps_se": round(float(cross.get("std_err") or 0.0), 6) if cross_set else None,
            "n_siblings": len(cross_set["siblings"]) if cross_set else 0,
        },
    }


def cross_delta(cross_set: dict | None, log_ratio, stride: int = 1):
    """Sibling profit change for a move of log(p_new/p0) = `log_ratio`:
    Σ_j q0_j·c_j·[(p_new/p0)^(ε_cross·w_ij) − 1]. `log_ratio` may be a scalar
    (one candidate) or a column (a grid of candidates); the result broadcasts
    against the draw axis. Zero when there is no family."""
    if not cross_set:
        return 0.0
    eps = cross_set["eps"][::stride]
    total = 0.0
    for q0_j, c_j, w in cross_set["siblings"]:
        total = total + q0_j * c_j * (np.exp(log_ratio * eps * w) - 1.0)
    return total


def delta_at(draw_set: dict, p_new: float, own_only: bool = False) -> np.ndarray:
    """The profit-delta draw vector at one candidate price: own profit plus,
    when the SKU sits in a variant family, the siblings' change."""
    own = profit_delta(draw_set["eps"], draw_set["p0"], draw_set["q0"],
                       draw_set["unit_cost"], draw_set["fee_rate"], p_new,
                       draw_set["fixed_fee"])
    if own_only or not draw_set.get("cross"):
        return own
    return own + cross_delta(draw_set["cross"], float(np.log(p_new / draw_set["p0"])))


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


def certainty_equivalent(delta, tol: float) -> float:
    """E[delta] − Var[delta] / (2·tol): the certainty equivalent under quadratic
    utility, with `tol` the dollar risk tolerance. The objective `robust_step`
    sizes a price step by, exposed so every other module that chooses among
    uncertain moves (budget reallocation, markdown depth) uses the same rule
    rather than a copy of it. −inf on an empty or non-finite sample."""
    d = np.asarray(delta, dtype=float).ravel()
    d = d[np.isfinite(d)]
    if d.size == 0:
        return float("-inf")
    tol = max(abs(float(tol)), 1e-9)
    return float(d.mean() - d.var() / (2.0 * tol))


def es5(delta, alpha: float = 0.05) -> float:
    """Expected shortfall at `alpha`: the mean of the worst `alpha` of outcomes.
    The feasibility constraint a move must clear against the risk budget."""
    d = np.sort(np.asarray(delta, dtype=float).ravel())
    d = d[np.isfinite(d)]
    if d.size == 0:
        return float("-inf")
    return float(d[:max(1, int(alpha * d.size))].mean())


def trailing_monthly_net(margin_row: dict) -> float:
    """The SKU's own net for a 30-day month, from the period the promise is
    priced off. The denominator of the risk budget: what a step is allowed to
    put at risk is a share of what this SKU actually earns, not a share of the
    catalog."""
    net = margin_row.get("net_margin")
    if net is None:
        revenue = float(margin_row.get("revenue") or 0)
        fees = float(margin_row.get("amazon_fees") or 0)
        cogs = float(margin_row.get("cogs") or 0)
        net = revenue - fees - cogs
    start, end = margin_row.get("period_start"), margin_row.get("period_end")
    days = period_days(str(start), str(end)) if start and end else 30
    return float(net) * 30.0 / max(1, days)


def robust_step(draw_set: dict, *, direction: int, hard_cap: float = STEP_CAP,
                risk_budget: float = 0.0, quantile: float = ROBUST_QUANTILE,
                objective: str = OBJECTIVE) -> dict:
    """Solve for the step size, given the draws and a risk budget.

    `direction` is +1 or −1 and comes from the model, never from the
    simulation: moving away from the optimum cannot help under this demand
    curve, and letting Monte Carlo noise pick a sign would be the one place
    where the simulation could invent a recommendation.

    `objective` selects what is maximised — "quantile" for the ROBUST_QUANTILE
    of the profit-delta distribution, "cvar" for the mean of its worst decile.
    Both are robust; the horse race measures which pays, and the quantile wins
    on both mean and 5th-percentile realised profit."""
    p0 = draw_set["p0"]
    n_steps = int(round(hard_cap / STEP_GRID))
    fractions = np.array([direction * STEP_GRID * k for k in range(1, n_steps + 1)])

    # every candidate price against the SAME draws, in one pass. Common random
    # numbers: two candidate steps differ by their economics, never by which
    # simulation stream they happened to get.
    stride = max(1, draw_set["n"] // SEARCH_DRAWS)
    eps = draw_set["eps"][::stride]
    q0 = draw_set["q0"][::stride]
    f = draw_set["fee_rate"][::stride]
    big_f = draw_set["fixed_fee"][::stride]
    c = draw_set["unit_cost"][::stride]

    prices = (p0 * (1.0 + fractions))[:, None]
    q = q0 * np.exp(np.log(prices / p0) * eps)
    base_contribution = p0 * (1 - f) - c - big_f
    delta = q * (prices * (1 - f) - c - big_f) - q0 * base_contribution
    if draw_set.get("cross"):
        # the family's side of every candidate, on the same draws
        delta = delta + cross_delta(draw_set["cross"], np.log(prices / p0), stride)
    if not np.isfinite(delta).all():
        delta = np.where(np.isfinite(delta), delta, -np.inf)

    # one sort serves every statistic the search needs; order statistics are
    # a perfectly good quantile definition and three times faster than
    # interpolated ones on a matrix this shape
    srt = np.sort(delta, axis=1)
    m = srt.shape[1]
    p5 = srt[:, min(m - 1, int(0.05 * m))]
    es5 = srt[:, :max(1, int(0.05 * m))].mean(axis=1)
    # the optional gate: that quantile of the step's own distribution must not be a loss
    p_gate = srt[:, min(m - 1, int(MAX_P_LOSS * m))] if MAX_P_LOSS is not None else np.zeros(len(fractions))
    if objective == "cvar":
        # mean of the worst decile: coherent, and noisier than a quantile
        scores = srt[:, :max(1, int(0.10 * m))].mean(axis=1)
    elif objective == "quantile":
        scores = srt[:, min(m - 1, int(quantile * m))]
    else:
        # certainty equivalent under quadratic utility: expected delta less the
        # variance it carries, priced at this SKU's own risk tolerance. See the
        # module docstring for why a pure quantile objective cannot size a step.
        tol = max(abs(float(risk_budget)), 1e-9)
        scores = delta.mean(axis=1) - delta.var(axis=1) / (2.0 * tol)

    budget = abs(float(risk_budget))
    feasible = np.isfinite(es5) & np.isfinite(scores) & (es5 >= -budget) & (p_gate >= 0.0)
    gate_bound = bool((np.isfinite(es5) & np.isfinite(scores) & (es5 >= -budget)).any() and not feasible.any())
    # standing still is always a candidate, and its delta is exactly zero
    chosen, best_score = 0.0, 0.0
    if feasible.any():
        candidates = np.where(feasible)[0]
        winner = candidates[int(np.argmax(scores[candidates]))]
        if scores[winner] > 0.0:
            chosen, best_score = float(fractions[winner]), float(scores[winner])

    cap_bound = chosen != 0.0 and abs(abs(chosen) - hard_cap) < STEP_GRID / 2
    # the budget bound bit: a feasible region that stopped short of the cap
    budget_bound = bool(chosen != 0.0 and not cap_bound and not feasible[-1])
    return {
        "step_fraction": chosen,
        "objective_value": num(best_score),
        "objective": objective,
        "quantile": quantile,
        "cap_bound": cap_bound,
        "budget_bound": budget_bound,
        # the loss gate refused every candidate the budget would have allowed
        "gain_gate_bound": gate_bound,
        "max_p_loss": MAX_P_LOSS,
        "risk_budget": round(budget, 2),
        "hard_cap": hard_cap,
        "candidates": int(len(fractions)) + 1,
        "feasible_candidates": int(feasible.sum()) + 1,
    }


def price_move(margin_row: dict, elasticity_row: dict,
               fee_history: list[tuple[float, float]] | None = None,
               cost_cv: float = 0.0, draws: int = MC_DRAWS,
               rng: np.random.Generator | None = None,
               hard_cap: float = STEP_CAP, quantile: float = ROBUST_QUANTILE,
               objective: str = OBJECTIVE, cross: dict | None = None,
               risk_share: float | None = None) -> dict | None:
    """One SKU's recommended move: exact new price, destination optimum
    (elastic only, and only when the fit is far enough from the pole at
    eps = −1 to have one), the expected profit delta per period and the
    5th-to-95th-percentile range around it from a seeded parametric bootstrap
    over every uncertain input. The step size is solved for, not capped: see
    robust_step and the module docstring. Returns None when nothing honest can
    be recommended — including when the robust objective cannot beat standing
    still.

    `fee_history` is [(proportional rate, fixed per unit)] across the SKU's
    own periods; its dispersion is carried into the range. `cost_cv` carries
    landed-cost dispersion where the client's own sheet shows some.

    `cross` is the SKU's variant-family effect (see delta_draws). Every candidate
    is then valued on own PLUS sibling profit, and the step is sized on the
    total. When the own-only objective would have moved and the total will
    not, the answer is a dict with status "cannibalisation" naming the sibling
    — a finding — rather than the silence None means."""
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
    # a fitted row with no stated uncertainty is unbounded, not exact
    if not _has_stated_uncertainty(elasticity_row) and elasticity_row.get("status") == "ok":
        return None
    if near_unit_elastic(eps, elasticity_row.get("std_err") or std_err, ci,
                         fitted=elasticity_row.get("status") == "ok"):
        # No destination: the distance is unbounded this close to the pole. The
        # direction is NOT asserted either. The pole proof in the docstring pins
        # it upward for an epŝ genuinely near −1, but the guard also fires on a
        # clearly elastic epŝ whose interval is merely wide, and forcing that
        # SKU upward would be asserting the one thing the wide interval says we
        # do not know. Both directions are searched and the objective — which
        # integrates over the whole posterior, both sides of −1 included —
        # decides.
        status, direction = "near_unit_elastic", 0
    elif eps < -1:
        status = "optimum"
        p_star = optimal_price(eps, unit_cost, fee_rate, fixed_fee)
        if p_star is None or p_star <= 0:
            return None
        destination = p_star
        direction = +1 if p_star > p0 else -1
    elif -1 < eps < 0:
        # no interior optimum: profit rises with price in this model
        status, direction = "inelastic_step", +1
    else:
        return None

    mix = None
    if details.get("p_prices_optimal") is not None and details.get("markup_implied_epsilon") is not None:
        mix = (float(details["p_prices_optimal"]), float(details["markup_implied_epsilon"]))
    draw_set = delta_draws(
        eps=eps, std_err=std_err, dof=dof, p0=p0, q0=units,
        unit_cost=unit_cost, fee_rate=fee_rate, fixed_fee=fixed_fee,
        demand_sd_log=details.get("residual_sd_log"),
        fee_history=fee_history, cost_cv=cost_cv, draws=draws, rng=rng, cross=cross,
        optimal_mix=mix,
    )
    monthly_net = trailing_monthly_net(margin_row)
    # the client's stated tolerance, or the house default
    share = float(risk_share) if risk_share is not None else RISK_BUDGET_SHARE
    budget = share * max(monthly_net, 0.0)
    # a fit that just moved (models/drift.py) walks half as far this cycle
    drift_scale = float((details.get("drift") or {}).get("tolerance_scale") or 1.0)
    budget *= drift_scale

    def _solve(ds):
        if direction == 0:
            options = [robust_step(ds, direction=d, hard_cap=hard_cap, risk_budget=budget,
                                   quantile=quantile, objective=objective) for d in (-1, +1)]
            return max(options, key=lambda o: o["objective_value"] or 0.0)
        return robust_step(ds, direction=direction, hard_cap=hard_cap,
                           risk_budget=budget, quantile=quantile, objective=objective)

    policy = _solve(draw_set)
    fraction = policy["step_fraction"]
    if abs(fraction) < MIN_MOVE:
        if draw_set.get("cross"):
            # would the SKU on its own have moved? Then the family is what
            # stopped it, and that is a finding with a name.
            own_policy = _solve({**draw_set, "cross": None})
            if abs(own_policy["step_fraction"]) >= MIN_MOVE:
                p_own = p0 * (1.0 + own_policy["step_fraction"])
                own_d = summarize_delta(delta_at(draw_set, p_own, own_only=True))
                total_d = summarize_delta(delta_at(draw_set, p_own))
                sibs = sorted(cross["siblings"], key=lambda j: -float(j["weight"]) * float(j["q0"]) * abs(float(j["contribution"])))
                return {"status": "cannibalisation", "p0": round(p0, 2), "p_own": round(p_own, 2),
                        "own_step_fraction": round(own_policy["step_fraction"], 6),
                        "own_delta_p50": own_d["p50"], "total_delta_p50": total_d["p50"],
                        "sibling_delta_p50": num((total_d["p50"] or 0) - (own_d["p50"] or 0)),
                        "sibling": sibs[0]["sku"] if sibs else None,
                        "family": cross.get("family"), "eps_cross": cross.get("eps"),
                        "cross_std_err": cross.get("std_err"), "n_siblings": len(cross["siblings"]),
                        "trailing_monthly_net": num(monthly_net)}
        # the robust objective cannot beat doing nothing, or the move it wants
        # is smaller than half a percent. Either way there is no instruction
        # here, and the refusal is the objective's own answer.
        return None
    p_new = p0 * (1.0 + fraction)

    # past the optimum is never the answer: walk to P* and stop there
    if destination is not None:
        p_new = max(p_new, destination) if direction < 0 else min(p_new, destination)
        fraction = p_new / p0 - 1.0
        if abs(fraction) < MIN_MOVE:
            return None

    # Direction confidence: on what share of the posterior's draws does a
    # half-percent move this way raise the profit of the SKU and its family?
    # At a price already near its optimum a small error in ε makes a
    # first-order edge on paper and a second-order loss in fact; this is the
    # gate that tells the two apart.
    nudge = delta_at(draw_set, p0 * (1.0 + DIRECTION_NUDGE * float(np.sign(fraction))))
    direction_confidence = float(np.mean(nudge[np.isfinite(nudge)] > 0)) if np.isfinite(nudge).any() else 0.0
    if MIN_DIRECTION_CONFIDENCE is not None and direction_confidence < MIN_DIRECTION_CONFIDENCE:
        return None

    dist = summarize_delta(delta_at(draw_set, p_new))
    cross_effect = None
    if draw_set.get("cross"):
        own_d = summarize_delta(delta_at(draw_set, p_new, own_only=True))
        sib = summarize_delta(cross_delta(draw_set["cross"], float(np.log(p_new / p0))) + np.zeros(draw_set["n"]))
        cross_effect = {"family": cross.get("family"), "eps_cross": cross.get("eps"),
                        "std_err": cross.get("std_err"), "dof": cross.get("dof"),
                        "siblings": cross["siblings"],
                        "delta_own_p50": own_d["p50"],
                        "delta_sibling_p5": sib["p5"], "delta_sibling_p50": sib["p50"], "delta_sibling_p95": sib["p95"]}

    return {
        "status": status,
        "cross_effect": cross_effect,
        "p0": round(p0, 2),
        "p_new": round(p_new, 2),
        "step_fraction": round(fraction, 6),
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
        "direction_confidence": round(direction_confidence, 4),
        "p_prices_optimal": mix[0] if mix else None,
        "mc_se": dist["mc_se"],
        "mc_inputs": draw_set["inputs"],
        "policy": {**policy, "risk_budget_share": share,
                   "risk_budget_share_basis": "client" if risk_share is not None else "default",
                   "drift_tolerance_scale": drift_scale},
        "trailing_monthly_net": num(monthly_net),
        "fee_rate": round(fee_rate, 6),
        "fixed_fee_per_unit": round(fixed_fee, 6),
        "fee_split": fee_basis,
    }
