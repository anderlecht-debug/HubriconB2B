"""The error bars on the error bars.

A published percentile is an estimate. These tests check that the standard
error we attach to it is the right size — measured against the spread of
repeated independent simulations, which is the only thing "standard error of
the P5" can honestly mean.
"""

import numpy as np
import pytest
from scipy import stats

from hubricon_engine.models.mc import expected_shortfall, quantile_se, quantiles_with_se


def test_quantile_se_matches_the_spread_of_repeated_simulations():
    """The claim: quantile_se(draws, q) predicts how much the q-quantile would
    move if you ran the simulation again. Check it against 400 reruns."""
    rng = np.random.default_rng(0)
    n = 8000
    for q in (0.05, 0.25, 0.5, 0.95):
        estimates, reported = [], []
        for _ in range(400):
            x = rng.normal(100.0, 20.0, size=n)
            estimates.append(float(np.quantile(x, q)))
            reported.append(quantile_se(x, q))
        empirical = float(np.std(estimates, ddof=1))
        predicted = float(np.mean(reported))
        assert predicted == pytest.approx(empirical, rel=0.20), f"q={q}"


def test_quantile_se_matches_the_analytic_formula_for_a_normal():
    """sqrt(q(1−q)/n) / φ(z_q) σ⁻¹ — the textbook asymptotic, independent of
    the implementation's density estimator."""
    rng = np.random.default_rng(1)
    n, sigma, q = 20000, 20.0, 0.05
    x = rng.normal(0.0, sigma, size=n)
    z = stats.norm.ppf(q)
    analytic = np.sqrt(q * (1 - q) / n) / (stats.norm.pdf(z) / sigma)
    assert quantile_se(x, q) == pytest.approx(analytic, rel=0.15)


def test_quantile_se_refuses_rather_than_claiming_zero_error():
    assert quantile_se([1.0] * 500, 0.05) is None      # flat: no finite density
    assert quantile_se([1.0, 2.0, 3.0], 0.05) is None  # too few draws
    assert quantile_se(np.random.default_rng(2).normal(size=500), 1.5) is None


def test_expected_shortfall_is_worse_than_the_percentile_it_sits_behind():
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 1.0, size=20000)
    es = expected_shortfall(x, 0.05, "lower")
    assert es["shortfall"] < es["threshold"]
    # normal lower 5% tail mean is −φ(z)/0.05 = −2.063
    assert es["shortfall"] == pytest.approx(-2.063, abs=0.06)
    assert es["se"] is not None and es["se"] < 0.02
    assert es["tail_n"] == pytest.approx(1000, rel=0.05)


def test_expected_shortfall_separates_two_distributions_a_percentile_cannot():
    """Why VaR is not a risk measure. Two samples with the same 5th percentile
    and very different tails: the percentile calls them identical, the
    shortfall does not."""
    rng = np.random.default_rng(4)
    body = np.abs(rng.normal(0, 1, 19000))               # everything good stays above zero
    mild = np.concatenate([body, np.linspace(-2.0, -2.2, 1000)])
    wild = np.concatenate([body, np.linspace(-2.0, -50.0, 1000)])
    mild_es, wild_es = expected_shortfall(mild, 0.05), expected_shortfall(wild, 0.05)
    # identical 5th percentile by construction: the threshold cannot tell them apart
    assert mild_es["threshold"] == pytest.approx(wild_es["threshold"], abs=0.05)
    # the tail mean can, by a factor of twelve
    assert wild_es["shortfall"] < mild_es["shortfall"] - 20


def test_upper_tail_shortfall_for_losses():
    rng = np.random.default_rng(5)
    losses = rng.exponential(100.0, size=20000)
    es = expected_shortfall(losses, 0.05, "upper")
    assert es["shortfall"] > es["threshold"]
    # exponential: CVaR_95 = VaR_95 + mean
    assert es["shortfall"] == pytest.approx(es["threshold"] + 100.0, rel=0.10)


def test_quantiles_with_se_reports_every_requested_level():
    rng = np.random.default_rng(6)
    out = quantiles_with_se(rng.normal(size=5000), (0.05, 0.5, 0.95))
    assert out["n"] == 5000
    assert all(out[q]["value"] is not None and out[q]["se"] is not None
               for q in (0.05, 0.5, 0.95))
