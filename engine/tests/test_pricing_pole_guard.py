"""The pole at ε = −1, and the engine refusing to report through it.

P* carries the factor ε/(1+ε), which is 21 at ε = −1.05 and 51 at ε = −1.02.
A fit of −1.12 with a standard error of 0.18 therefore names no destination at
all. These tests are the artifact that the refusal is real and that the one
thing which does survive the pole — the direction — is still handed over.
"""

import numpy as np
import pytest

from hubricon_engine.models.pricing_engine import (
    near_unit_elastic,
    optimal_price,
    price_move,
)

MARGIN = {"units": 100, "revenue": 2000.0, "amazon_fees": 300.0, "cogs": 500.0,
          "fee_split": {"basis": "itemized", "proportional_rate": 0.10,
                        "fixed_per_unit": 1.0, "proportional_fees": 200.0,
                        "fixed_fees": 100.0}}


def _fit(eps, se, ci=None):
    if ci is None and se is not None:
        ci = [eps - 3.18 * se, eps + 3.18 * se]
    return {"elasticity": eps, "std_err": se, "details": {"ci95": ci}}


# ── the pole is real ──────────────────────────────────────────────────────

def test_the_optimum_diverges_near_minus_one():
    """Why the guard has to exist, in numbers."""
    far = optimal_price(-2.0, 5.0, 0.10, 1.0)
    close = optimal_price(-1.05, 5.0, 0.10, 1.0)
    closer = optimal_price(-1.02, 5.0, 0.10, 1.0)
    assert close / far > 10
    assert closer / close > 2
    # and the two "close" estimates are three hundredths of an ε apart
    assert abs(-1.05 - -1.02) < 0.04


# ── the guard ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("eps,se", [(-1.12, 0.18), (-0.95, 0.20), (-1.0, 0.05), (-1.3, 0.30)])
def test_guard_fires_when_two_sigma_touches_minus_one(eps, se):
    assert near_unit_elastic(eps, se, None) is True


@pytest.mark.parametrize("eps,se", [(-2.0, 0.20), (-1.6, 0.10), (-0.4, 0.05), (-3.5, 0.80)])
def test_guard_stays_quiet_when_the_fit_is_clear_of_the_pole(eps, se):
    assert near_unit_elastic(eps, se, None) is False


def test_a_straddling_interval_fires_the_guard_even_on_a_confident_point():
    """ε̂ = −1.45 looks comfortably elastic, but if its own published interval
    runs from −2.6 to −0.3 then −1 is inside it and the destination is not
    knowable. The guard and the interval cannot disagree."""
    assert near_unit_elastic(-1.45, 0.01, [-2.6, -0.3]) is True


def test_a_fit_that_states_no_uncertainty_is_taken_at_its_word():
    """A hand-built fixture, or a fit from before the guard existed, carries
    neither interval nor standard error. The guard does not invent an
    uncertainty in order to refuse."""
    assert near_unit_elastic(-1.05, None, None) is False


# ── what the engine returns at the pole ───────────────────────────────────

def test_no_destination_is_emitted_at_the_pole():
    move = price_move(MARGIN, _fit(-1.12, 0.18))
    assert move["status"] == "near_unit_elastic"
    assert move["destination"] is None


def test_the_direction_survives_the_pole_and_the_step_is_bounded():
    """P* > P0 for every ε near −1 on a SKU with a positive contribution
    margin, from either side of the pole — so the move is up, and that is the
    one thing worth saying."""
    for eps in (-1.12, -1.04, -1.0, -0.96, -0.88):
        move = price_move(MARGIN, _fit(eps, 0.18))
        assert move["status"] == "near_unit_elastic"
        assert move["p_new"] > move["p0"]
        assert 0 < move["step_fraction"] <= 0.05


def test_the_direction_claim_holds_against_the_profit_function_itself():
    """Not taken on faith: evaluate the modelled profit at P0 and just above
    it for a dense sweep of ε through the pole. Raising the price must pay at
    every one of them."""
    from hubricon_engine.models.pricing_engine import profit_delta

    p0, q0, c, f, big_f = 20.0, 100.0, 5.0, 0.10, 1.0
    for eps in np.linspace(-1.40, -0.70, 71):
        d = profit_delta(float(eps), p0, q0, c, f, p0 * 1.01, big_f)
        assert d > 0, f"raising the price loses money at eps={eps:.3f}"


def test_a_clear_fit_still_gets_its_destination():
    """The guard must not swallow the cases it was not built for."""
    move = price_move(MARGIN, _fit(-2.4, 0.15))
    assert move["status"] == "optimum"
    assert move["destination"] is not None


def test_the_pole_directive_promises_no_dollars():
    """A status, never a number that looks like a finding — at the one place
    in the engine where the number would have been most tempting."""
    from hubricon_engine.directives import _pricing_directive

    d = _pricing_directive({**_fit(-1.10, 0.20), "item_id": "S1"},
                           {**MARGIN, "period_start": "2026-07-01"})
    assert d["expected_impact_usd"] is None
    assert "direction but not the distance" in d["action_text"]
    assert "optimum" not in d["action_text"].replace("no optimum to quote", "")
    assert d["evidence"]["destination"] is None
