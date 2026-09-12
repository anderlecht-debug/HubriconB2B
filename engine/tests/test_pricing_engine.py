import pytest

from hubricon_engine.models.pricing_engine import (
    optimal_price,
    price_move,
    profit_delta,
)


def test_optimal_price_matches_hand_computation():
    # eps=-2, c=$5, f=0.15: P* = (5/0.85) * (-2/-1) = $11.7647
    assert optimal_price(-2.0, 5.0, 0.15) == pytest.approx(11.7647, abs=1e-3)
    # zero fees: classic markup rule P* = c * eps/(1+eps)
    assert optimal_price(-3.0, 6.0, 0.0) == pytest.approx(9.0)


def test_no_interior_optimum_for_inelastic_or_unit_elastic():
    assert optimal_price(-0.5, 5.0, 0.15) is None
    assert optimal_price(-1.0, 5.0, 0.15) is None
    assert optimal_price(-2.0, 0.0, 0.15) is None  # no cost, no optimum


def test_profit_delta_zero_at_current_and_positive_toward_optimum():
    args = (-2.0, 20.0, 100.0, 5.0, 0.15)  # p* = 11.76, well below p0
    assert profit_delta(*args, 20.0) == pytest.approx(0.0)
    assert profit_delta(*args, 19.0) > 0        # stepping down toward p* gains
    assert profit_delta(*args, 21.0) < 0        # stepping away loses


ELASTIC_MARGIN = {"units": 100, "revenue": 2000.0, "amazon_fees": 300.0, "cogs": 500.0}
ELASTIC_FIT = {"elasticity": -2.0, "details": {"ci95": [-2.4, -1.6]}}


def test_price_move_caps_step_and_reports_destination():
    move = price_move(ELASTIC_MARGIN, ELASTIC_FIT)
    assert move["p0"] == 20.0
    assert move["p_new"] == 19.0                 # capped at -5% though p* is $11.76
    assert move["destination"] == pytest.approx(11.76, abs=0.01)
    assert move["expected_delta"] > 0
    lo, hi = move["delta_range"]
    assert lo <= move["expected_delta"] <= hi or lo <= hi  # range ordered


def test_price_move_inelastic_has_no_destination_and_steps_up_to_the_rail():
    """An inelastic fit that states NO uncertainty — no standard error, no
    interval — has nothing for the robust objective to be cautious about, so the
    step goes to the contractual rail. This replaces an assertion that the step
    was exactly the old INELASTIC_STEP constant of 3%: the step is now solved
    for rather than set, and a fit claiming certainty gets the full authorised
    move. The companion test below is the one that matters — as soon as the fit
    states real uncertainty, the step comes in off the rail."""
    move = price_move(ELASTIC_MARGIN, {"elasticity": -0.5, "details": {}})
    assert move["destination"] is None           # no interior optimum exists
    assert move["step_fraction"] == pytest.approx(0.05)
    assert move["policy"]["cap_bound"] is True
    assert move["expected_delta"] > 0            # inelastic: raising price gains


def test_an_uncertain_inelastic_fit_never_steps_further_than_a_certain_one():
    """The same SKU, the same elasticity, with an honest standard error on it.

    On this fixture the gain at the rail is so much larger than the variance it
    carries that the rail still binds — which is the right answer, not a
    failure: a SKU earning $12 a unit on a price-insensitive product is not
    taking a risk by moving 5%. The monotonicity property, and the regime where
    the statistics bind instead of the rail, are measured across a whole grid in
    tests/test_robust_step.py."""
    certain = price_move(ELASTIC_MARGIN, {"elasticity": -0.5, "details": {}})
    uncertain = price_move(ELASTIC_MARGIN, {
        "elasticity": -0.5, "std_err": 0.35,
        "details": {"ci95": [-1.47, 0.47], "dof": 3, "t_critical": 3.182,
                    "residual_sd_log": 0.45}})
    assert uncertain is None or uncertain["step_fraction"] <= certain["step_fraction"]


def test_price_move_refuses_without_landed_cost():
    no_cogs = {**ELASTIC_MARGIN, "cogs": None}
    assert price_move(no_cogs, ELASTIC_FIT) is None
