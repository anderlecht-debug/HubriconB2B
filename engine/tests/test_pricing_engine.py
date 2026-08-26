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


def test_price_move_inelastic_bounded_step_with_computed_dollars():
    move = price_move(ELASTIC_MARGIN, {"elasticity": -0.5, "details": {}})
    assert move["p_new"] == pytest.approx(20.60, abs=0.01)  # +3% bounded step
    assert move["destination"] is None
    assert move["expected_delta"] > 0            # inelastic: raising price gains


def test_price_move_refuses_without_landed_cost():
    no_cogs = {**ELASTIC_MARGIN, "cogs": None}
    assert price_move(no_cogs, ELASTIC_FIT) is None
