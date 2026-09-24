"""What the elasticity estimate is, and what it is not.

Imbens and Chernozhukov would ask one question about this engine and it is the
right one: the price in your regression was chosen by the seller, and sellers
choose prices in response to demand. Your ε is a correlation. What is the bias,
which way does it run, and does the report say so?

This file answers the first three. The fourth is answered in the report template
and in MATH_METHODS.md, in the plain sentence a seller reads.

The simulation is the realistic shape of the problem, not a strawman:

    the demand shock is persistent (AR(1), ρ), so last month's demand tells the
    seller something about this month's;
    the seller raises price by φ·(last month's shock) — reacting to what they
    saw, not to what is about to happen, because nobody has next month's data.

Endogeneity bites only when BOTH hold. With an independent shock, reacting to
last month carries no information about this month and the bias is small. With a
persistent shock, the reaction loads positive demand onto high prices and the
fitted demand curve looks FLATTER than it is.

WHAT IT FOUND (median ε̂ − ε_true over 96 seeds × 60 SKUs per cell, 9 periods):

    ρ = 0.6   φ = 0.0   +0.02     persistence alone: nothing
    ρ = 0.6   φ = 0.4   +0.51     reaction on persistent demand — the whole bias
    ρ = 0.0   φ = 0.6   −0.16     reaction with nothing to react to: the OTHER way

This docstring used to describe a "+0.14 small-sample attenuation baseline" with
the endogeneity as an increment on top. That baseline was an artifact of eight
seeds (see test_there_is_no_attenuation_baseline_worth_naming, and MATH_METHODS.md
§2, corrected 2026-09-12): there is no baseline, and the whole +0.5 is endogeneity.
It runs toward zero — toward "raise the price, demand barely cares" — which is
the dangerous direction, because it is the direction that makes the engine
recommend increases. A SKU whose true elasticity is −2.0 can read −1.6, and at
−1.6 the model puts the optimum 33% higher than at −2.0 — exactly 4/3,
independent of cost and fees.

An observational fit does not correct this and cannot: correcting it needs an
instrument, something that moves price without moving demand. What stands
between the bias and a client on such a fit, each tested elsewhere in this suite:

  1. The pole guard refuses a destination whenever ε̂ cannot be separated from
     −1, and a +0.5 bias pushes estimates toward exactly that band — so the
     most-biased SKUs are the ones the engine most often declines to price.
  2. The step is sized by the certainty equivalent, so an uncertain fit produces
     a small move that a later export can correct.
  3. The engine's ordinary price steps are NOT the instrument (this docstring
     claimed they were until 2026-09-23; the claim was withdrawn on 2026-09-12
     because a step chosen by the fit is not exogenous and a fortnight-long step
     blends away below the monthly estimator's floor). The instrument is the
     randomised six-block test in models/price_experiment.py, measured on this
     same generator in tests/test_price_experiment.py, and it corrects the bias
     one SKU at a time once that SKU's test has run.
"""

import numpy as np
import pytest

from hubricon_engine.models import elasticity

FEE_RATE, FIXED_FEE, BASE_PRICE = 0.15, 1.50, 20.0


def _period(i: int, length: int = 28) -> tuple[str, str]:
    """(start, end) for the i-th period, 1-indexed, rolling into the next year.

    Fixtures used to write f"2026-{i:02d}-01" directly, which produces month 13
    past a year of history. Nothing caught it until elasticity._fit began reading
    period_end to normalise units by period length (2026-09-12) — a real export
    never has a thirteenth month."""
    year, month = 2026 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{length:02d}"


def _reactive_catalog(seed, phi, rho, n_skus=60, n_periods=9, demand_sd=0.22):
    """Exports from a seller who reprices in response to last month's demand."""
    rng = np.random.default_rng(seed)
    econ, truth = [], []
    for i in range(n_skus):
        sku = f"S{i:03d}"
        eps = float(rng.uniform(-3.4, -1.2))
        shock = np.zeros(n_periods)
        shock[0] = rng.normal(0, demand_sd)
        for t in range(1, n_periods):
            shock[t] = rho * shock[t - 1] + rng.normal(0, demand_sd * np.sqrt(1 - rho**2))
        noise = rng.normal(0, 0.05, size=n_periods)
        prices = np.array([BASE_PRICE * np.exp(noise[t] + (phi * shock[t - 1] if t else 0.0))
                           for t in range(n_periods)])
        units = 400.0 * (prices / BASE_PRICE) ** eps * np.exp(shock)
        for j, (p, u) in enumerate(zip(prices, units), start=1):
            revenue = float(p) * float(u)
            econ.append({
                "sku": sku, "asin": "B0" + sku,
                "period_start": _period(j)[0], "period_end": _period(j)[1],
                "units_sold": float(u), "avg_sales_price": float(p), "sales": revenue,
                "referral_fees": -FEE_RATE * revenue,
                "fba_fulfillment_fees": -FIXED_FEE * float(u),
                "storage_fees": 0.0, "other_fees": 0.0, "net_proceeds": revenue,
            })
        truth.append((sku, eps))
    data = {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [], "cogs_inputs": []}
    return data, dict(truth)


def _bias(phi, rho, seeds=range(700, 708)):
    """Median ε̂ − ε_true across a population. Median, not mean: a handful of
    wild fits on nine periods would otherwise dominate."""
    errors = []
    for seed in seeds:
        data, truth = _reactive_catalog(seed, phi, rho)
        for f in elasticity.run(data):
            if f["level"] != "sku" or f["status"] != "ok":
                continue
            errors.append(float(f["details"]["epsilon_raw"]) - truth[f["item_id"]])
    return float(np.median(errors)), len(errors)


BASELINE_PHI = 0.0
# Eight seeds is not a measurement. The between-8-seed-block sd of the median bias
# is 0.079, so a cell measured on one block carries a ±0.16 two-sigma band — wide
# enough to invent a +0.15 "baseline" that does not exist. Every cell here is
# measured over this many seeds, and the tolerances come from that dispersion.
WIDE_SEEDS = range(700, 796)


def test_there_is_no_attenuation_baseline_worth_naming():
    """The correction that matters most, pinned.

    This test used to assert 0.05 < bias < 0.25 at φ = 0 and call the result
    small-sample attenuation. Over 96 seeds the figure is +0.022 and the old
    assertion passes 5 of 12 independent 8-seed blocks. There is no baseline; the
    whole measured bias at φ > 0 is endogeneity, and the problem is therefore
    bigger than the first write-up said, not smaller."""
    bias, n = _bias(phi=BASELINE_PHI, rho=0.6, seeds=WIDE_SEEDS)
    assert n > 5000
    assert abs(bias) < 0.06, bias
    # persistence on its own still changes nothing, and now that is a real claim
    independent, _ = _bias(phi=BASELINE_PHI, rho=0.0, seeds=WIDE_SEEDS)
    assert independent == pytest.approx(bias, abs=0.06)


def test_an_eight_seed_block_cannot_measure_this_cell():
    """The methodological finding, kept as a test so the mistake cannot recur.

    Twelve independent 8-seed blocks of the φ = 0 cell span −0.117 to +0.145. Any
    claim about this cell from one block is noise, and this engine published one
    for a day."""
    blocks = [_bias(phi=BASELINE_PHI, rho=0.6, seeds=range(s, s + 8))[0]
              for s in range(700, 796, 8)]
    spread = max(blocks) - min(blocks)
    assert spread > 0.2, blocks
    assert np.std(blocks, ddof=1) > 0.05
    # and the pooled estimate is far tighter than any single block
    pooled, _ = _bias(phi=BASELINE_PHI, rho=0.6, seeds=WIDE_SEEDS)
    assert abs(pooled) < min(abs(b) for b in blocks if abs(b) > 0.1)


def test_reacting_to_an_independent_shock_does_not_bias_toward_zero():
    """Reacting to last month tells you nothing about this month when demand has
    no memory, so the price is effectively still exogenous. Note the sign: with no
    persistence the reaction biases ε̂ the OTHER way, which is why a correction
    triggered on reaction strength alone would do harm on a non-persistent
    catalog."""
    baseline, _ = _bias(phi=BASELINE_PHI, rho=0.0, seeds=WIDE_SEEDS)
    reactive, _ = _bias(phi=0.6, rho=0.0, seeds=WIDE_SEEDS)
    assert reactive < baseline - 0.1


def test_reactive_pricing_on_persistent_demand_biases_epsilon_toward_zero():
    """The finding, over 96 seeds. Demand reads measurably LESS elastic than it
    is, which is the direction that makes the engine recommend price increases —
    and with no attenuation baseline to net off, the whole half-unit is
    endogeneity."""
    baseline, _ = _bias(phi=BASELINE_PHI, rho=0.6, seeds=WIDE_SEEDS)
    reactive, _ = _bias(phi=0.4, rho=0.6, seeds=WIDE_SEEDS)
    assert reactive > 0.40, reactive
    assert reactive - baseline > 0.35, f"{reactive:.3f} vs baseline {baseline:.3f}"
    assert reactive - baseline < 1.0


def test_the_bias_direction_is_stable_across_reaction_strengths():
    """Not an artifact of one φ: every reaction strength on persistent demand
    biases the same way, above the no-reaction baseline."""
    baseline, _ = _bias(phi=BASELINE_PHI, rho=0.6, seeds=range(700, 748))
    for phi in (0.4, 0.6, 1.2):
        bias, _ = _bias(phi=phi, rho=0.6, seeds=range(700, 748))
        assert bias > baseline + 0.1, f"phi={phi}: {bias:.3f} vs {baseline:.3f}"


def test_the_bias_is_large_enough_to_move_a_recommendation():
    """Why it matters in dollars: a 0.4 bias toward zero moves the quoted optimum
    by a THIRD, not by a sixth. That is not a rounding difference, it is the
    difference between a cut and a rise.

    The ratio is [ε₁/(1+ε₁)] / [ε₂/(1+ε₂)] = (1.6/0.6)/(2.0/1.0) = 4/3 exactly,
    and the cost and fee terms cancel — so this is pinned tightly at several
    economics rather than loosely at one. The previous version of this test
    asserted only `> 1.15`, which is why the docs said 17% for a day."""
    from hubricon_engine.models.pricing_engine import optimal_price

    for cost, fee, fixed in ((5.0, FEE_RATE, FIXED_FEE), (5.0, 0.0, 0.0),
                             (8.0, 0.08, 3.3), (1.0, 0.30, 0.5)):
        ratio = (optimal_price(-1.6, cost, fee, fixed)
                 / optimal_price(-2.0, cost, fee, fixed))
        assert ratio == pytest.approx(4 / 3, rel=1e-9), (cost, fee, fixed, ratio)


def test_the_pole_guard_catches_the_most_biased_skus():
    """The mitigation that is actually load-bearing: a bias toward zero pushes
    estimates into the band where the pole guard refuses to name a destination,
    so the SKUs the bias hurts most are disproportionately the ones the engine
    declines to price to the cent."""
    from hubricon_engine.models.pricing_engine import near_unit_elastic

    data, truth = _reactive_catalog(701, phi=0.6, rho=0.6)
    fits = [f for f in elasticity.run(data)
            if f["level"] == "sku" and f["status"] == "ok"]
    guarded, unguarded = [], []
    for f in fits:
        err = abs(float(f["details"]["epsilon_raw"]) - truth[f["item_id"]])
        bucket = guarded if near_unit_elastic(
            float(f["elasticity"]), f["std_err"],
            (f.get("details") or {}).get("ci95")) else unguarded
        bucket.append(err)
    assert guarded and unguarded
    # the guarded group carries more estimation error than the group the engine
    # is willing to quote a destination for
    assert np.median(guarded) > np.median(unguarded)


def test_a_seller_facing_sentence_exists_for_this():
    """The fourth question — does the report say so — is answered by a string
    that has to be there. If this fails, the documentation drifted away from the
    mathematics and the claim on the page is no longer true."""
    from pathlib import Path

    methods = Path(__file__).resolve().parents[1] / "MATH_METHODS.md"
    assert methods.exists(), "MATH_METHODS.md is part of the deliverable"
    text = methods.read_text()
    lower = " ".join(text.split()).lower()
    # the explicit limits section, and the endogeneity named in plain words
    assert "cannot tell you" in lower
    assert "what this engine cannot tell you" in lower
    assert "in response to how demand was running" in lower
    assert "the single most dangerous assumption" in lower
    # the withdrawal is on the record in the methods document too, with both
    # reasons, rather than the claim being quietly deleted
    assert "corrected 2026-09-12" in lower
    assert "not an instrument" in lower
    # the measured size of the bias, so the doc and the simulation cannot drift.
    # Was "+0.59 or +0.44" until 2026-09-12; both were 8-seed figures and the
    # second was an increment over a baseline that turned out not to exist.
    assert "+0.51" in text
    assert "+0.022" in text          # the φ=0 cell over 96 seeds
    # the withdrawn "+0.15 attenuation baseline" may still appear — but only inside
    # the paragraph that withdraws it, never as a live figure. Checking for its
    # absence would push the correction history out of the document, which is the
    # opposite of what this engine wants; so check the withdrawal is attached to it.
    if "+0.15" in text:
        window = text[max(0, text.index("+0.15") - 900):text.index("+0.15") + 900]
        assert "Corrected 2026-09-12" in window or "artifact" in window

    # and the seller-facing version of the same sentence, on the report itself.
    # Whitespace is normalised: the template wraps its prose, and a line break is
    # not a change in what the client reads.
    report = " ".join((Path(__file__).resolve().parents[1] / "src" / "hubricon_engine"
                       / "report" / "templates" / "report.html.j2").read_text().split())
    assert "What this number is, and what it is not" in report
    assert "in response to how demand was running" in report
    assert "It is not corrected." in report
    # the measured consequence, in the client's units
    assert "a third too high" in report
    # and the per-SKU bound claim must NOT be there. It was shipped for 25
    # minutes on 2026-09-12 on the strength of an asymptotic argument, then
    # measured: on the SKUs the engine actually quotes, using the shrunk estimate
    # it actually uses, "quoted >= true optimum" holds 0.797 at (phi=0.4,
    # rho=0.6) and 0.373 at (phi=0.4, rho=0) — and rho=0 is inside the claim's
    # own stated domain. A bound that is wrong for a quarter to two-thirds of the
    # SKUs it is printed on is not a bound.
    assert "ceiling on the best price rather than a target" not in report
    # what replaced it is a catalogue-level statement with its own limits named
    assert "statement about the catalogue and not about" in report

    # AND the false claim stays gone. Until 2026-09-12 this report told every
    # client "correcting it needs a price change made for a reason unrelated to
    # demand. Every step on this report is exactly that." The second sentence was
    # false: the steps are chosen by the same fit, so they are not exogenous to
    # demand, and a 14-day step blends below MIN_PRICE_CV so the estimator cannot
    # even see them. A test that pinned the claim is what let it ship, so this
    # one pins its absence.
    for withdrawn in ("Every step on this report is exactly that",
                      "become the clean history the next fit is built on"):
        assert withdrawn not in report, withdrawn
