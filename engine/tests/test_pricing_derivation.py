"""The closed forms, proved twice: once symbolically, once by brute force.

A derivation in a docstring is a claim. These tests are the artifact behind
the claim — sympy re-derives the first-order condition from the profit
function itself, and a grid search over prices confirms the analytic optimum
really is the maximum of the function the engine believes it is maximising.

sympy is a test-only dependency; the engine itself stays on numpy and scipy.
"""

import numpy as np
import pytest

from hubricon_engine.models.pricing_engine import optimal_price, profit

sympy = pytest.importorskip("sympy")


def test_first_order_condition_derives_p_star_symbolically():
    """P* = [(c + F)/(1 − f)] · ε/(1 + ε), derived, not asserted.

    Π(P) = Q0·(P/P0)^ε · (P(1 − f) − c − F). Solve dΠ/dP = 0 for P and the
    only root is the engine's formula."""
    P, P0, Q0, c, F, f, eps = sympy.symbols("P P0 Q0 c F f eps", positive=True)
    # eps enters as a negative exponent; keep it a free symbol so no sign
    # assumption sneaks into the algebra
    e = sympy.Symbol("e", real=True)
    pi = Q0 * (P / P0) ** e * (P * (1 - f) - c - F)
    roots = sympy.solve(sympy.diff(pi, P), P)
    assert len(roots) == 1
    expected = ((c + F) / (1 - f)) * e / (1 + e)
    assert sympy.simplify(roots[0] - expected) == 0


def test_fixed_fee_enters_exactly_like_unit_cost():
    """The symbolic form says c and F are interchangeable in P*. The
    implementation must agree, because that equivalence is the whole reason
    the split matters."""
    assert optimal_price(-2.5, 4.0, 0.15, 3.0) == pytest.approx(
        optimal_price(-2.5, 7.0, 0.15, 0.0)
    )


def test_collapsing_a_fixed_fee_into_the_rate_biases_the_optimum_down():
    """The defect this fix closes, measured.

    A SKU at $20 with a $3.00 referral fee (15%) and a $3.30 fixed FBA fee.
    The old code set f = 6.30/20 = 31.5% and F = 0; the correct split is
    f = 15%, F = $3.30. The old treatment quotes a lower optimum — so the
    engine was walking toward a price below the one that maximises profit."""
    eps, c = -2.0, 5.0
    correct = optimal_price(eps, c, 0.15, 3.30)
    collapsed = optimal_price(eps, c, 0.315, 0.0)
    assert collapsed < correct
    # and the gap is material, not a rounding artifact
    assert (correct - collapsed) / correct > 0.05


@pytest.mark.parametrize("eps", [-1.4, -2.0, -3.5, -6.0])
@pytest.mark.parametrize("fee_rate,fixed_fee", [(0.0, 0.0), (0.15, 0.0), (0.15, 3.3), (0.08, 1.2)])
def test_analytic_optimum_matches_brute_force_grid(eps, fee_rate, fixed_fee):
    """Numerical proof: a dense grid search over prices finds the same
    maximum the closed form names."""
    p0, q0, c = 20.0, 100.0, 5.0
    p_star = optimal_price(eps, c, fee_rate, fixed_fee)
    assert p_star is not None and p_star > 0
    grid = np.linspace(p_star * 0.5, p_star * 1.5, 200_001)
    profits = profit(eps, p0, q0, c, fee_rate, grid, fixed_fee)
    best = float(grid[int(np.argmax(profits))])
    assert best == pytest.approx(p_star, rel=1e-4)


def test_p_star_is_monotone_in_cost_and_in_the_fixed_fee():
    base = optimal_price(-2.0, 5.0, 0.15, 1.0)
    assert optimal_price(-2.0, 6.0, 0.15, 1.0) > base
    assert optimal_price(-2.0, 5.0, 0.15, 2.0) > base
    assert optimal_price(-2.0, 5.0, 0.25, 1.0) > base   # a higher rate needs a higher price


def test_no_interior_optimum_without_a_positive_contribution_cost():
    assert optimal_price(-2.0, 0.0, 0.15, 0.0) is None
    assert optimal_price(-0.5, 5.0, 0.15, 1.0) is None
    assert optimal_price(-1.0, 5.0, 0.15, 1.0) is None
