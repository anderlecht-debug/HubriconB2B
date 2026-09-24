"""Reallocating the ad budget across campaigns.

ad_efficiency trims each campaign toward its own break-even, one at a time.
That leaves the money that sits BETWEEN campaigns: a dollar in a campaign whose
marginal ROAS is 1.4 earns less than the same dollar moved to one at 3.1, and
the account is better off at the same total spend until every campaign's
marginal return is the same. This module finds that allocation, and it finds
money in accounts where no campaign is past break-even at all.

THE PROBLEM. With fitted response curves f_i(s) — the Hill or log fits
ad_efficiency already made — and the current daily spends s_i0 summing to B:

    maximise  Σ_i E[f_i(s_i)]   subject to   Σ_i s_i = B,   lo_i ≤ s_i ≤ hi_i

The margin is common to every campaign, so at a fixed budget it cancels: the
allocation that maximises attributed sales maximises attributed profit. The
Lagrangian reading is the one a seller hears — a multiplier λ such that every
campaign sits where f_i'(s_i) = λ, the common marginal ROAS — but the SOLVER
is not a bisection on λ. Hill with h > 1 is S-shaped, so the first-order
condition is necessary and not sufficient, s_i(λ) jumps, and a bisection can
skip the budget and leave a duality gap to apologise for. The problem is a
separable allocation on a grid, and that has an exact dynamic program:

    V_k(b) = max_{j ∈ [lo_k, hi_k], j ≤ b}  f̄_k(j) + V_{k−1}(b − j)

O(N·G²) at worst, far less with the move cap, no gap. λ* is read off the
solution afterwards as the marginal value of budget, (V(B+δ) − V(B−δ)) / 2δ.

WHICH CURVE. Not the point estimate. The objective is additively separable and
expectation is linear, so max E[Σ f_i(s_i)] = max Σ E[f_i(s_i)]: the
risk-neutral Bayes solution is the allocation on each campaign's POSTERIOR-MEAN
curve, the mean of f_i over draws of its parameters from the fit's own
covariance. Feeding the optimizer the point estimate would be the Markowitz
pathology the pricing engine already refuses — a confident number built on
sampling error — and here it is not even necessary, because the exact answer is
cheap.

HOW FAR TO MOVE. The full solution s* is the risk-neutral target. The move
actually recommended is s0 + α(s* − s0), with α chosen the way the price step
is sized: maximise the certainty equivalent E[Δ] − Var[Δ]/(2·tol) over α,
subject to the expected shortfall at 5% staying inside the risk budget. The
budget is RISK_BUDGET_SHARE of the campaign set's own monthly net — attributed
sales times margin, less spend — the same net-after-ads base the price step
uses. A set of campaigns that earns no net gets no tolerance and no move under
the standing mandate; the trims still fire on it. Two rails on top: no campaign
is pushed past EXTRAPOLATION_CAP times the spend it has ever been observed at
(the curve was fitted on the observed range), and no campaign moves more than
MOVE_CAP of its current spend in one cycle — walk, re-measure, walk.

THE INTERVAL. Parameter draws are independent across campaigns, because the
curves are fitted separately and no cross-campaign covariance exists to draw
from; draw d of every campaign is paired with draw d of every other after the
accepted counts are truncated to a common length. The published gain is the
distribution of Σ_i [f_i(s_rec) − f_i(s_0)] over those joint draws, in profit
dollars over the measurement horizon, with P(loss) and the Monte Carlo error of
each percentile. The free-budget optimum — every campaign at marginal ROAS =
1/margin — is solved too and published as information, so the report can say
whether the account as a whole is over- or under-spent even though this
directive moves no total.

WHAT IT CANNOT TELL YOU. Everything the response curves cannot: the interval is
conditional on the curve form, the attribution is the platform's own 7-day
window, and spend was chosen by the seller. A campaign whose covariance the fit
could not produce is held at its current spend and named, never guessed at.
"""

import numpy as np

from .ad_efficiency import CURVE_SEED, _marginal, curve_values, draw_params
from .common import num
from .mc import quantiles_with_se
from .pricing_engine import RISK_BUDGET_SHARE, certainty_equivalent, es5

# The curve is fitted on the observed spend range; this is how far past the
# largest observed spend a campaign may be pushed. Raising it trusts the fitted
# saturation further out; 1.0 would forbid any campaign from growing past its
# own history.
EXTRAPOLATION_CAP = 1.5
# The largest fraction of a campaign's current spend one cycle may move, in
# either direction. The fit is local and the next cycle re-measures.
MOVE_CAP = 0.30
# Spend grid resolution: the budget in this many steps. The DP is exact on the
# grid; finer costs time quadratically and changes recommendations by cents.
GRID = 1000
# Joint parameter draws behind the published gain. 400 matches CURVE_DRAWS.
ALLOC_DRAWS = 400
ALLOC_SEED = 20260911
# Below this many accepted joint draws no percentile is worth printing.
MIN_DRAWS = 50
MIN_CAMPAIGNS = 2
# A reallocation whose median 30-day gain is under this, or whose chance of
# any gain is under ALLOC_MIN_P_GAIN, is not drafted: the marginals are already
# equal within the noise.
ALLOC_MIN_GAIN = 50.0
ALLOC_MIN_P_GAIN = 0.6
HORIZON_DAYS = 30
ALPHAS = np.round(np.arange(0.05, 1.0001, 0.05), 2)


def params_vector(row: dict) -> np.ndarray | None:
    """(a, k, h) for a Hill row, (a, b) for a log row, from `curve_params`."""
    cp = row.get("curve_params") or {}
    keys = ("a", "k", "h") if row.get("curve_model") == "hill" else ("a", "b")
    try:
        return np.array([float(cp[k]) for k in keys], dtype=float)
    except (KeyError, TypeError, ValueError):
        return None


def _usable(row: dict) -> str | None:
    """None when the row can enter the optimisation, else the reason it is held."""
    if row.get("status") != "ok":
        return f"status:{row.get('status')}"
    if row.get("curve_model") not in ("hill", "log") or params_vector(row) is None:
        return "no_curve"
    details = row.get("details") or {}
    if details.get("curve_cov") is None:
        return "no_covariance"
    if not (float(row.get("current_spend") or 0) > 0) or not (float(details.get("max_spend") or 0) > 0):
        return "no_spend"
    return None


def campaign_monthly_net(rows: list[dict], avg_margin: float) -> float:
    """Thirty days of attributed sales times margin, less spend, over the
    campaigns in scope, floored at zero — the base the risk budget is a share
    of. The campaign-set analogue of pricing_engine.trailing_monthly_net."""
    daily = sum(avg_margin * float(r.get("current_sales") or 0) - float(r.get("current_spend") or 0)
                for r in rows)
    return float(HORIZON_DAYS * max(0.0, daily))


def allocate_dp(mean_curves: np.ndarray, bounds: list[tuple[int, int]], budget_steps: int) -> tuple[np.ndarray, np.ndarray]:
    """Exact allocation on the grid.

    `mean_curves[i, j]` is campaign i's expected sales at spend j·δ; `bounds[i]`
    the inclusive grid range campaign i may sit in. Returns the chosen grid
    index per campaign at exactly `budget_steps`, and the value function V(b)
    for b = 0..budget_steps + 1 (the +1 is what the marginal value of budget is
    read off). Equality, not ≤: with increasing curves the two coincide, and the
    equality form is what makes the answer budget-neutral by construction."""
    n, width = mean_curves.shape
    top = budget_steps + 1
    neg = -np.inf
    v_prev = np.full(top + 1, neg)
    v_prev[0] = 0.0
    choice = np.zeros((n, top + 1), dtype=int)
    for i in range(n):
        lo, hi = bounds[i]
        hi = min(hi, width - 1, top)
        v_new = np.full(top + 1, neg)
        for j in range(lo, hi + 1):
            cand = np.full(top + 1, neg)
            cand[j:] = mean_curves[i, j] + v_prev[: top + 1 - j]
            better = cand > v_new
            v_new = np.where(better, cand, v_new)
            choice[i][better] = j
        v_prev = v_new
    # backtrack from the exact budget
    picks = np.zeros(n, dtype=int)
    b = budget_steps
    for i in range(n - 1, -1, -1):
        picks[i] = choice[i, b]
        b -= picks[i]
    return picks, v_prev


def _free_budget(mean_curves: np.ndarray, delta: float, caps: list[int], avg_margin: float) -> list[int]:
    """Each campaign at the grid point maximising m·f̄(s) − s inside its
    extrapolation cap: the joint optimum with the total free. Information, not
    the directive."""
    out = []
    for i, cap in enumerate(caps):
        j = np.arange(0, cap + 1)
        profit = avg_margin * mean_curves[i, : cap + 1] - j * delta
        out.append(int(np.argmax(profit)))
    return out


def gain_draws(models: list[str], thetas: list[np.ndarray], s_from: np.ndarray, s_to: np.ndarray) -> np.ndarray:
    """Σ_i [f_i(s_to) − f_i(s_from)] on every joint draw: shape (draws,)."""
    total = None
    for model, theta, a, b in zip(models, thetas, s_from, s_to):
        vals = curve_values(model, theta, [a, b])
        diff = vals[:, 1] - vals[:, 0]
        total = diff if total is None else total + diff
    return total


def shrink_move(models, thetas, s0: np.ndarray, s_star: np.ndarray, tol: float, avg_margin: float) -> dict:
    """α on a grid maximising the certainty equivalent of the 30-day profit
    gain, subject to its 5% expected shortfall staying inside `tol`. Standing
    still (α = 0) is always a candidate with a gain of exactly zero."""
    best = {"alpha": 0.0, "objective_value": 0.0, "feasible_alphas": 1, "candidates": len(ALPHAS) + 1}
    for alpha in ALPHAS:
        s_a = s0 + alpha * (s_star - s0)
        profit = HORIZON_DAYS * avg_margin * gain_draws(models, thetas, s0, s_a)
        if es5(profit) < -tol:
            continue
        best["feasible_alphas"] += 1
        score = certainty_equivalent(profit, tol)
        if score > best["objective_value"]:
            best = {**best, "alpha": float(alpha), "objective_value": float(score)}
    best["objective"] = "certainty_equivalent"
    best["risk_budget"] = round(float(tol), 2)
    return best


def run(ads_rows: list[dict], avg_margin: float | None, draws: int = ALLOC_DRAWS,
        rng: np.random.Generator | None = None, exclude: set[str] | None = None) -> dict:
    """The reallocation over the campaigns that can enter it.

    `exclude` names campaigns another directive already moves this cycle (a
    trim); they are held at current spend so no campaign carries two promises."""
    exclude = exclude or set()
    rows = sorted((r for r in ads_rows if r.get("campaign_name")), key=lambda r: r["campaign_name"])
    out = {"status": "ok", "horizon_days": HORIZON_DAYS, "avg_margin": num(avg_margin, 4),
           "seed": ALLOC_SEED, "draws": 0, "campaigns": []}
    if not avg_margin or avg_margin <= 0:
        return {**out, "status": "insufficient_margin",
                "campaigns": [{"campaign_name": r["campaign_name"], "status": "held", "reason": "no_margin"} for r in rows]}

    active, held = [], []
    for r in rows:
        reason = "trimmed_this_run" if r["campaign_name"] in exclude else _usable(r)
        if reason:
            held.append({"campaign_name": r["campaign_name"], "status": "held", "reason": reason,
                         "current": num(r.get("current_spend"))})
        else:
            active.append(r)
    if len(active) < MIN_CAMPAIGNS:
        return {**out, "status": "insufficient_campaigns", "campaigns": held,
                "n_usable": len(active)}

    # — the joint posterior: draw d of every campaign paired with draw d of every other —
    rng = rng or np.random.default_rng(ALLOC_SEED)
    models, thetas = [], []
    for r in active:
        theta = draw_params(r["curve_model"], params_vector(r), np.asarray(r["details"]["curve_cov"], dtype=float),
                            draws, rng)
        models.append(r["curve_model"])
        thetas.append(theta)
    m = min((len(t) for t in thetas if t is not None), default=0)
    if any(t is None for t in thetas) or m < MIN_DRAWS:
        return {**out, "status": "insufficient_draws", "draws": int(m), "campaigns": held
                + [{"campaign_name": r["campaign_name"], "status": "held", "reason": "posterior_unsupported"}
                   for r in active]}
    thetas = [t[:m] for t in thetas]

    # — the grid, the bounds, the posterior-mean curves —
    s0 = np.array([float(r["current_spend"]) for r in active])
    budget = float(s0.sum())
    delta = budget / GRID
    grid = np.arange(0, GRID + 2) * delta
    mean_curves = np.vstack([curve_values(mdl, th, grid).mean(axis=0) for mdl, th in zip(models, thetas)])
    caps = [min(GRID + 1, int(np.floor(EXTRAPOLATION_CAP * float(r["details"]["max_spend"]) / delta)))
            for r in active]
    bounds = []
    for s, cap in zip(s0, caps):
        lo = int(np.floor(s * (1 - MOVE_CAP) / delta))
        hi = int(np.ceil(s * (1 + MOVE_CAP) / delta))
        hi = max(lo, min(hi, cap, GRID + 1))
        bounds.append((lo, hi))
    picks, v = allocate_dp(mean_curves, bounds, GRID)
    s_star = picks * delta
    lam = float((v[GRID + 1] - v[GRID - 1]) / (2 * delta)) if np.isfinite(v[GRID + 1]) and np.isfinite(v[GRID - 1]) else None
    free = _free_budget(mean_curves, delta, caps, avg_margin)

    # — how far to move, and what the move is worth —
    tol = RISK_BUDGET_SHARE * campaign_monthly_net(active, avg_margin)
    policy = shrink_move(models, thetas, s0, s_star, tol, avg_margin)
    alpha = policy["alpha"]
    s_rec = s0 + alpha * (s_star - s0)
    sales_gain = gain_draws(models, thetas, s0, s_rec)
    profit_gain = HORIZON_DAYS * avg_margin * sales_gain
    q = quantiles_with_se(profit_gain, (0.05, 0.50, 0.95))
    p_loss = float(np.mean(profit_gain < 0)) if alpha > 0 else None

    campaigns = []
    for r, mdl, s, st, sr, cap, (lo, hi), fr in zip(active, models, s0, s_star, s_rec, caps, bounds, free):
        params = tuple(params_vector(r))
        campaigns.append({
            "campaign_name": r["campaign_name"], "status": "ok",
            "current": num(s), "recommended": num(sr), "s_star": num(st),
            "move": num(sr - s),
            "marginal_roas_now": num(_marginal(mdl, params, float(s)), 4),
            "marginal_roas_at_rec": num(_marginal(mdl, params, float(sr)), 4),
            "curve_model": mdl, "curve_params": r.get("curve_params"),
            "curve_cov": r["details"]["curve_cov"], "max_spend": r["details"]["max_spend"],
            "current_sales": num(r.get("current_sales")),
            "extrapolation_cap": num(cap * delta),
            "extrapolation_bound": bool(picks[list(active).index(r)] == cap and cap < hi + 1 and st > s),
            "move_cap_bound": bool(abs(st - s) >= (MOVE_CAP * s - delta)),
            "free_budget_spend": num(fr * delta),
        })
    out.update({
        "campaigns": campaigns + held,
        "total_spend": num(budget),
        "total_moved_daily": num(float(np.abs(s_rec - s0).sum()) / 2.0),
        "lambda": num(lam, 4),
        "breakeven_marginal_roas": num(1.0 / avg_margin, 4),
        "alpha": alpha,
        "policy": policy,
        "draws": int(m),
        "delta_p5": num(q[0.05]["value"]), "delta_p50": num(q[0.50]["value"]), "delta_p95": num(q[0.95]["value"]),
        "delta_mean": num(float(profit_gain.mean())),
        "p_loss": num(p_loss, 4) if p_loss is not None else None,
        "mc_se": {"p5": num(q[0.05]["se"], 3), "p50": num(q[0.50]["se"], 3), "p95": num(q[0.95]["se"], 3)},
        "mc_inputs": {"draws": int(m), "seed": ALLOC_SEED, "grid": GRID, "grid_step": num(delta, 4)},
        "sales_gain_daily_p50": num(float(np.quantile(sales_gain, 0.5))),
        "free_budget": {"total": num(sum(free) * delta),
                        "per_campaign": {r["campaign_name"]: num(f * delta) for r, f in zip(active, free)}},
        "duality_gap": 0.0,
    })
    median = out["delta_p50"] or 0.0
    if alpha == 0.0 or median < ALLOC_MIN_GAIN or (p_loss is not None and 1 - p_loss < ALLOC_MIN_P_GAIN):
        out["status"] = "no_reallocation"
        out["reason"] = ("the risk budget admits no move" if alpha == 0.0 else
                         f"median 30-day gain ${median:,.0f} under ${ALLOC_MIN_GAIN:,.0f}" if median < ALLOC_MIN_GAIN
                         else f"only {1 - p_loss:.0%} of draws gain")
    out["basis"] = (
        f"{len(active)} campaign(s) reallocated at the same ${budget:,.0f}/day; exact grid allocation on each "
        f"campaign's posterior-mean response curve ({m} joint parameter draws); marginal ROAS equalises at "
        f"{lam if lam is None else round(lam, 2)} against a break-even of {1 / avg_margin:.2f}; move sized by "
        f"the certainty equivalent (α = {alpha}) inside a risk budget of ${tol:,.0f}; "
        f"{len(held)} campaign(s) held."
    )
    return out
