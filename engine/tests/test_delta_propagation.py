"""The range on a promise, and where it comes from.

The engine used to build its "95% range" by plugging the two endpoints of the
elasticity interval into the profit function and sorting. That is a range of
two point estimates: it ignores the baseline volume, the fee structure, and
every other uncertain input, and it is not a 95% interval for anything.

These tests are the artifact that the published range is now a real
propagation — that every uncertain input moves it, that it is seeded and
reproducible, and that the Monte Carlo error in the percentiles is small
enough that re-running cannot change a recommendation.
"""

import numpy as np
import pytest

from hubricon_engine.models.pricing_engine import (
    MC_DRAWS,
    delta_at,
    delta_draws,
    price_move,
    profit_delta,
    summarize_delta,
)

MARGIN = {"units": 200, "revenue": 4000.0, "amazon_fees": 900.0, "cogs": 1000.0,
          "period_start": "2026-07-01", "period_end": "2026-07-31",
          "fee_split": {"basis": "itemized", "proportional_rate": 0.15,
                        "fixed_per_unit": 1.5, "proportional_fees": 600.0,
                        "fixed_fees": 300.0}}


def _fit(eps=-2.4, se=0.20, dof=4, resid=0.18):
    return {"elasticity": eps, "std_err": se,
            "details": {"ci95": [eps - 2.776 * se, eps + 2.776 * se],
                        "dof": dof, "t_critical": 2.776, "residual_sd_log": resid}}


# ── it is a propagation, not two point estimates ──────────────────────────

def test_every_uncertain_input_widens_the_published_range():
    """Turn each source of uncertainty on in turn; each must widen the band.
    The old range could only respond to one of them."""
    base_kwargs = dict(eps=-2.4, std_err=0.0, dof=4, p0=20.0, q0=200.0,
                       unit_cost=5.0, fee_rate=0.15, fixed_fee=1.5,
                       demand_sd_log=0.0, fee_history=None, cost_cv=0.0)

    def width(**over):
        kwargs = {**base_kwargs, **over}
        d = summarize_delta(delta_at(delta_draws(**kwargs), 19.0))
        return d["p95"] - d["p5"]

    # the counting-noise floor on q0 means the baseline is never exact, so the
    # floor width is already positive — every added source must exceed it
    floor = width()
    assert floor > 0
    assert width(std_err=0.20) > floor * 1.5                     # elasticity
    assert width(demand_sd_log=0.30) > floor * 1.5               # demand volatility
    assert width(fee_history=[(0.12, 1.0), (0.18, 2.0), (0.15, 1.6)]) > floor * 1.2  # fees
    assert width(cost_cv=0.15) > floor * 1.2                     # landed cost


def test_the_old_range_was_not_an_interval_for_anything():
    """What was actually wrong with the old construction.

    It is tempting to say the old two-endpoint range was "too narrow". At this
    fit it is not — mapping a 95% interval on ε through the profit function
    happens to give a wider band than a 90% interval on the delta. The defect
    was never the width. It was that the construction is not a probability
    statement: it maps one input's interval through a nonlinear function and
    calls the result a confidence interval, while ignoring the baseline volume
    and the fee structure entirely, so its coverage of the realized delta is
    whatever it happens to be.

    The width comparison that IS meaningful holds the method and the level
    fixed and varies only the inputs — see
    test_every_uncertain_input_widens_the_published_range above. The coverage
    comparison is in tests/test_calibration_math.py, which measures both
    constructions against realized deltas on simulated ground truth."""
    fit = _fit()
    p0, q0, c, f, big_f = 20.0, 200.0, 5.0, 0.15, 1.5
    endpoints = sorted(float(profit_delta(e, p0, q0, c, f, 19.0, big_f))
                       for e in fit["details"]["ci95"])

    # the old range is a deterministic function of ε alone: double the demand
    # volatility and it does not move a cent
    noisy = price_move(MARGIN, _fit(resid=0.40))
    calm = price_move(MARGIN, _fit(resid=0.05))
    assert noisy["delta_p95"] - noisy["delta_p5"] > (calm["delta_p95"] - calm["delta_p5"]) * 1.5
    assert endpoints == sorted(float(profit_delta(e, p0, q0, c, f, 19.0, big_f))
                               for e in _fit(resid=0.40)["details"]["ci95"])


def test_the_range_is_a_quantile_of_the_simulated_distribution():
    """Not asserted — recomputed from the draws independently."""
    fit = _fit()
    draw_set = delta_draws(eps=-2.4, std_err=0.20, dof=4, p0=20.0, q0=200.0,
                           unit_cost=5.0, fee_rate=0.15, fixed_fee=1.5,
                           demand_sd_log=0.18)
    delta = delta_at(draw_set, 19.0)
    summary = summarize_delta(delta)
    assert summary["p5"] == pytest.approx(float(np.quantile(delta, 0.05)), abs=0.02)
    assert summary["p50"] == pytest.approx(float(np.quantile(delta, 0.50)), abs=0.02)
    assert summary["p95"] == pytest.approx(float(np.quantile(delta, 0.95)), abs=0.02)
    assert summary["p_loss"] == pytest.approx(float((delta < 0).mean()), abs=1e-4)
    assert summary["draws"] == MC_DRAWS
    assert fit["elasticity"] == -2.4   # the fit itself is not mutated


# ── the Monte Carlo error is small enough to act on ───────────────────────

def test_monte_carlo_error_is_small_relative_to_the_interval_width():
    """The Glasserman question. If the standard error of the P5 were a
    meaningful fraction of the P5-to-P95 width, the published range would
    move between runs and a recommendation could flip on the seed."""
    move = price_move(MARGIN, _fit())
    width = move["delta_p95"] - move["delta_p5"]
    assert width > 0
    for level in ("p5", "p50", "p95"):
        se = move["mc_se"][level]
        assert se is not None
        assert se / width < 0.02, f"{level}: MC se is {se / width:.1%} of the width"


def test_reruns_agree_to_inside_the_reported_monte_carlo_error():
    """The standard error is a claim about rerunning. Check it by rerunning
    with different streams and comparing the spread of the P5 against the
    reported error."""
    fit = _fit()
    p5s = []
    for seed in range(40):
        move = price_move(MARGIN, fit, rng=np.random.default_rng(1000 + seed))
        p5s.append(move["delta_p5"])
    empirical = float(np.std(p5s, ddof=1))
    reported = price_move(MARGIN, fit)["mc_se"]["p5"]
    assert reported == pytest.approx(empirical, rel=0.40)


# ── seeded and reproducible ───────────────────────────────────────────────

def test_same_input_same_directive():
    """A seeded simulation means the promise is a function of the data alone.
    Two calls, byte-identical payloads."""
    fit = _fit()
    assert price_move(MARGIN, fit) == price_move(MARGIN, fit)


def test_the_promise_is_the_median_and_the_plug_in_is_kept_beside_it():
    move = price_move(MARGIN, _fit())
    assert move["expected_delta"] == move["delta_p50"]
    assert move["plugin_delta"] is not None
    # both are on the record so the gap between them is inspectable
    assert abs(move["plugin_delta"] - move["expected_delta"]) < abs(move["delta_p95"])


def test_p_loss_rises_as_the_fit_gets_noisier():
    """The number a seller actually wants: how often does this move lose
    money. It must respond to how little we know."""
    losses = [price_move(MARGIN, _fit(se=se))["p_loss"] for se in (0.05, 0.20, 0.35)]
    assert losses == sorted(losses)
    assert losses[-1] > losses[0]


def test_no_nan_or_inf_ever_reaches_the_payload():
    for se in (0.0, 0.05, 0.6):
        for eps in (-4.0, -2.0, -1.6, -0.6, -0.2):
            move = price_move(MARGIN, _fit(eps=eps, se=se))
            if move is None:
                continue
            for key, value in move.items():
                if isinstance(value, float):
                    assert np.isfinite(value), f"{key} = {value}"
