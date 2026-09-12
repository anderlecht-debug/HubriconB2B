"""The step size, and the property that it answers to the uncertainty.

STEP_CAP = 0.05 and INELASTIC_STEP = 0.03 were two constants doing the job of a
derived policy: a SKU fitted from five noisy periods and one fitted from thirty
clean ones got the same move. The step is now solved for. These tests are the
artifact that it is genuinely solved — that it shrinks as the engine learns
less, that the contractual rail is a rail and not the answer, and that standing
still wins when nothing else can.
"""

import numpy as np
import pytest

from hubricon_engine.models.pricing_engine import (
    RISK_BUDGET_SHARE,
    STEP_CAP,
    delta_draws,
    price_move,
    robust_step,
    trailing_monthly_net,
)


def sku(p0=20.0, units=100, unit_cost=5.0, fee_rate=0.15, fixed_fee=3.3):
    revenue = p0 * units
    return {"units": units, "revenue": revenue,
            "amazon_fees": fee_rate * revenue + fixed_fee * units,
            "cogs": unit_cost * units,
            "period_start": "2026-07-01", "period_end": "2026-07-31",
            "fee_split": {"basis": "itemized", "proportional_rate": fee_rate,
                          "fixed_per_unit": fixed_fee,
                          "proportional_fees": fee_rate * revenue,
                          "fixed_fees": fixed_fee * units}}


def fit(eps=-2.0, se=0.10, resid=0.15, dof=4):
    return {"elasticity": eps, "std_err": se,
            "details": {"ci95": [eps - 2.776 * se, eps + 2.776 * se], "dof": dof,
                        "t_critical": 2.776, "residual_sd_log": resid}}


# The regime where the statistics, not the rail, set the step: an elastic fit
# whose optimum sits a couple of percent below the current price, so the profit
# curve's own curvature is inside the cap and the variance penalty bites.
INTERIOR = dict(unit_cost=5.0)
INTERIOR_EPS = -2.0


# ── the required property ─────────────────────────────────────────────────

def test_doubling_the_standard_error_strictly_shrinks_the_step():
    """Holding everything else fixed. This is the property the whole rewrite
    exists to deliver, and it is the one a fixed cap could never have."""
    base = price_move(sku(**INTERIOR), fit(INTERIOR_EPS, se=0.10))
    doubled = price_move(sku(**INTERIOR), fit(INTERIOR_EPS, se=0.20))
    assert base is not None and doubled is not None
    assert abs(doubled["step_fraction"]) < abs(base["step_fraction"])


def test_the_step_is_monotone_in_the_standard_error_across_a_whole_sweep():
    """Not one pair — the whole curve. The step never grows as the engine
    learns less, and it ends in a refusal rather than in a small step that
    pretends to know something."""
    steps = []
    for se in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60, 0.90, 1.40):
        move = price_move(sku(**INTERIOR), fit(INTERIOR_EPS, se=se))
        steps.append(0.0 if move is None else abs(move["step_fraction"]))
    assert steps == sorted(steps, reverse=True), steps
    assert steps[0] > steps[-1] * 3          # it does not merely drift, it collapses
    assert steps[-1] == 0.0                  # wide enough, and the engine declines


def test_demand_volatility_shrinks_the_step_too():
    """Uncertainty about ε is not the only uncertainty. A SKU whose own volume
    swings 50% period to period gets a smaller step than an identical SKU whose
    volume is steady, because the promise is less knowable either way."""
    steady = price_move(sku(unit_cost=12.0), fit(-1.6, se=0.10, resid=0.05))
    swingy = price_move(sku(unit_cost=12.0), fit(-1.6, se=0.10, resid=0.60))
    assert steady is not None and swingy is not None
    assert abs(swingy["step_fraction"]) < abs(steady["step_fraction"])


def _step_curve(objective, **fit_kw):
    """The step the policy returns as the standard error on ε widens, holding
    the SKU fixed. The shape of this curve is the whole question."""
    return [
        0.0 if (m := price_move(sku(**INTERIOR),
                               fit(INTERIOR_EPS, se=se, **fit_kw),
                               objective=objective)) is None
        else round(abs(m["step_fraction"]), 4)
        for se in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60, 0.90, 1.40)
    ]


def test_a_pure_quantile_objective_cannot_size_a_step():
    """The finding that forced the objective's shape, kept as a test so it
    cannot be quietly forgotten.

    Every quantile of a positively scaled random variable scales with it —
    Q25[s·X] = s·Q25[X] — so a quantile objective against a box constraint is
    maximised at a corner and there is nothing in between for it to find. On a
    SKU sitting a couple of percent above its optimum, the whole curve of steps
    across a 28-fold range of standard error takes at most two distinct values,
    and the tail objectives spend almost all of it refusing outright."""
    for objective in ("quantile", "cvar"):
        curve = _step_curve(objective)
        assert len(set(curve)) <= 2, f"{objective}: {curve}"
        assert curve.count(0.0) >= 8, f"{objective}: {curve}"


def test_the_certainty_equivalent_objective_does_size_one():
    """The same SKU, the same sweep, the default objective. The variance term
    makes the objective strictly concave, so the step is a solution rather than
    a corner: a graded curve that falls with the standard error and ends in a
    refusal."""
    curve = _step_curve("certainty_equivalent")
    assert len(set(curve)) >= 5, curve
    assert curve == sorted(curve, reverse=True), curve
    assert curve[0] > 0.015 and curve[-1] == 0.0


# ── the rails behave like rails ───────────────────────────────────────────

def test_the_hard_cap_is_never_exceeded_whatever_the_objective_wants():
    """A safety rail has to hold even where the statistics would happily go
    further — it is what the client actually authorised."""
    for cap in (0.01, 0.05, 0.10):
        for eps in (-1.4, -2.5, -0.5):
            move = price_move(sku(unit_cost=12.0), fit(eps, se=0.05), hard_cap=cap)
            if move is None:
                continue
            assert abs(move["step_fraction"]) <= cap + 1e-9
            assert move["policy"]["hard_cap"] == cap


def test_the_walk_stops_at_the_optimum_and_never_overshoots_it():
    """A SKU whose optimum is 2% away does not take a 5% step past it."""
    move = price_move(sku(unit_cost=5.0), fit(-2.05, se=0.02))
    assert move is not None and move["destination"] is not None
    assert move["p_new"] >= move["destination"] - 0.01
    assert abs(move["step_fraction"]) < STEP_CAP


def test_standing_still_is_always_a_candidate_and_sometimes_wins():
    """The refusal is a property of the objective, not a threshold bolted on:
    doing nothing scores exactly zero and a SKU whose best move cannot beat
    zero gets no instruction."""
    draws = delta_draws(eps=-2.0, std_err=1.2, dof=3, p0=20.0, q0=100.0,
                        unit_cost=5.0, fee_rate=0.15, fixed_fee=3.3,
                        demand_sd_log=0.6)
    policy = robust_step(draws, direction=-1, risk_budget=50.0)
    assert policy["step_fraction"] == 0.0
    assert policy["objective_value"] == 0.0


def test_the_risk_budget_is_a_share_of_this_skus_own_monthly_net():
    """Not a share of the catalog: a $200-a-month SKU and a $20,000-a-month SKU
    do not get the same dollar budget."""
    small, large = sku(units=10), sku(units=1000)
    assert trailing_monthly_net(large) == pytest.approx(trailing_monthly_net(small) * 100)
    move = price_move(large, fit(-2.0, se=0.10))
    assert move["policy"]["risk_budget"] == pytest.approx(
        RISK_BUDGET_SHARE * trailing_monthly_net(large), abs=0.01)


def test_a_period_that_is_not_a_month_is_annualised_to_one():
    """A weekly export and a monthly one must not produce different budgets for
    the same underlying SKU."""
    weekly = {**sku(units=25), "period_start": "2026-07-01", "period_end": "2026-07-07"}
    monthly = {**sku(units=25 * 30 / 7), "period_start": "2026-06-01", "period_end": "2026-06-30"}
    assert trailing_monthly_net(weekly) == pytest.approx(trailing_monthly_net(monthly), rel=1e-6)


def test_the_policy_says_which_constraint_bound_it():
    """So a cap that is binding across a whole catalog is visible rather than
    assumed."""
    railed = price_move(sku(unit_cost=12.0), fit(-3.0, se=0.05))
    assert railed["policy"]["cap_bound"] is True
    interior = price_move(sku(**INTERIOR), fit(INTERIOR_EPS, se=0.20))
    assert interior["policy"]["cap_bound"] is False


def test_every_objective_is_reproducible():
    for objective in ("certainty_equivalent", "quantile", "cvar"):
        a = price_move(sku(unit_cost=12.0), fit(-2.0, se=0.2), objective=objective)
        b = price_move(sku(unit_cost=12.0), fit(-2.0, se=0.2), objective=objective)
        assert a == b
        assert a["policy"]["objective"] == objective
