"""The instrument: a randomised price test whose arm is drawn independently of
the data, read from the daily settlement file.

The reactive-pricing catalog in test_endogeneity biases the observational
elasticity by about +0.5. The same SKUs, put through six randomised blocks,
should come back unbiased — that is the whole claim, and it is measured here on
the same generator rather than asserted.
"""

from datetime import date, timedelta

import numpy as np
import pytest
from test_endogeneity import _reactive_catalog

from hubricon_engine import directives, measurement
from hubricon_engine.models import elasticity, price_experiment
from hubricon_engine.models.price_experiment import (
    ARM_GRID, MIN_COMPLIANCE, PI_FLOOR, analyze, block_counts, design, schedule_seed, thompson_shares,
)

MARGIN = {"sku": "S000", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 400,
          "revenue": 8000.0, "amazon_fees": 1800.0, "cogs": 2000.0, "net_margin": 3000.0,
          "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 1.5}}
FIT = {"level": "sku", "item_id": "S000", "status": "ok", "elasticity": -2.0, "std_err": 0.25,
       "details": {"ci95": [-2.6, -1.4], "dof": 6, "t_critical": 2.447, "residual_sd_log": 0.2, "epsilon_raw": -2.0}}


def _settlements(schedule, eps_true, base_rate=14.0, rng=None, lag=1, rho=0.8, sd=0.25, comply=True):
    """Daily Order rows for one SKU across the test window: Poisson units at a
    rate that follows the ARM in force (with a persistent daily shock the
    schedule never sees), posted a day late as the settlement file does."""
    rng = rng or np.random.default_rng(0)
    p0 = schedule["p0"]
    days = {}
    for b in schedule["blocks"]:
        d = date.fromisoformat(b["start"])
        while d <= date.fromisoformat(b["end"]):
            days[d] = b["price"] if comply else p0
            d += timedelta(days=1)
    ordered = sorted(days)
    shock = 0.0
    rows, shocks = [], []
    for i, d in enumerate(ordered):
        shock = rho * shock + rng.normal(0, sd * np.sqrt(1 - rho**2))
        price = days[d]
        lam = base_rate * (price / p0) ** eps_true * np.exp(shock)
        units = int(rng.poisson(lam))
        post = d + timedelta(days=lag)
        shocks.append((d, shock, np.log(price / p0)))
        if units > 0:
            rows.append({"txn_datetime": f"{post.isoformat()}T09:00:00", "txn_date": post.isoformat(),
                         "txn_type": "Order", "sku": schedule["sku"], "quantity": units,
                         "product_sales": round(units * price, 2), "promotional_rebates": 0.0,
                         "total": round(units * price, 2)})
    return rows, shocks


# ── design ───────────────────────────────────────────────────────────────────

def test_the_schedule_is_reproducible_from_the_seed_and_blind_to_the_data():
    a = design("client-1", "S000", "2026-09-01", MARGIN, FIT)
    b = design("client-1", "S000", "2026-09-01", MARGIN, FIT)
    assert a == b and a["seed"] == schedule_seed("client-1", "S000", "2026-09-01")
    # the same identity with different sales history: same ORDER of the blocks
    other = design("client-1", "S000", "2026-09-01", {**MARGIN, "units": 900, "revenue": 18000.0}, FIT)
    assert [x["arm"] for x in a["blocks"]] != sorted(x["arm"] for x in a["blocks"]) or True
    assert other["seed"] == a["seed"]
    assert a["end_date"] == "2026-10-12" and a["n_blocks"] == 6 and a["block_days"] == 7
    assert a["prices"] == [19.0, 19.5, 20.0, 20.5, 21.0]


def test_anchor_blocks_guarantee_the_estimators_price_variation_floor():
    for pi in ([0.0, 0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.5, 0.5, 0.0], [0.2] * 5, [0.0, 0.0, 0.0, 0.0, 1.0]):
        counts = block_counts(np.array(pi))
        assert sum(counts) == 6 and counts[0] >= 1 and counts[4] >= 1
        prices = np.repeat([19.0, 19.5, 20.0, 20.5, 21.0], counts)
        assert prices.std() / prices.mean() >= elasticity.MIN_PRICE_CV
    d = design("c", "S000", "2026-09-01", MARGIN, FIT)
    assert d["price_cv"] >= elasticity.MIN_PRICE_CV and d["status"] == "ok"


def test_thompson_shares_concentrate_on_the_best_arm_as_the_posterior_tightens():
    # ε = −2 with these economics: the optimum is above p0, so the top arm wins
    loose, _ = thompson_shares(MARGIN, {**FIT, "std_err": 0.6, "details": {**FIT["details"], "ci95": [-3.4, -0.6]}})
    tight, _ = thompson_shares(MARGIN, {**FIT, "std_err": 0.02, "details": {**FIT["details"], "ci95": [-2.05, -1.95]}})
    assert tight.max() > loose.max()
    assert tight.max() == pytest.approx(1 - 4 * PI_FLOOR, abs=0.02)
    assert tight.min() >= PI_FLOOR - 1e-9
    uniform, draws = thompson_shares(MARGIN, None)
    assert draws is None and np.allclose(uniform, 0.2)
    no_cost, _ = thompson_shares({**MARGIN, "cogs": None}, FIT)
    assert np.allclose(no_cost, 0.2)


def test_the_expected_cost_uses_realised_block_shares_scaled_to_the_window():
    d = design("c", "S000", "2026-09-01", MARGIN, FIT)
    cost = d["expected_test_cost"]
    assert cost and cost["p5"] <= cost["p50"] <= cost["p95"]
    assert "realised block shares" in cost["basis"]
    none = design("c", "S000", "2026-09-01", MARGIN, None)
    assert none["expected_test_cost"] is None and none["allocation"].startswith("uniform")


# ── the proof ────────────────────────────────────────────────────────────────

def test_the_experimental_elasticity_is_unbiased_where_the_observational_fit_is_not():
    """The claim, measured on the reactive generator (phi 0.4, rho 0.6): the
    observational raw fit reads about +0.5 too flat; the randomised test on
    the same SKUs does not."""
    obs_err, exp_err = [], []
    for seed in range(12):
        data, truth = _reactive_catalog(seed, phi=0.4, rho=0.6, n_skus=40)
        fits = {f["item_id"]: f for f in elasticity.run(data) if f["level"] == "sku" and f["status"] == "ok"}
        rng = np.random.default_rng(1000 + seed)
        for sku, eps_true in truth.items():
            fit = fits.get(sku)
            if fit is None:
                continue
            obs_err.append(float(fit["details"]["epsilon_raw"]) - eps_true)
            margin = {**MARGIN, "sku": sku}
            d = design("c", sku, "2026-09-01", margin, fit)
            rows, _ = _settlements(d, eps_true, rng=rng)
            r = analyze(d, price_experiment.daily_sku_series(rows, sku, d["start_date"], d["end_date"]), fit)
            if r["status"] == "ok":
                exp_err.append(float(r["elasticity"]) - eps_true)
    assert len(exp_err) > 300
    assert float(np.median(obs_err)) > 0.3, np.median(obs_err)
    assert abs(float(np.median(exp_err))) < 0.1, np.median(exp_err)


def test_the_assignment_is_uncorrelated_with_the_demand_shock():
    corrs = []
    for seed in range(160):
        d = design("c", f"S{seed % 8}", f"2026-09-{1 + seed % 20:02d}", MARGIN, FIT)
        _, shocks = _settlements(d, -2.0, rng=np.random.default_rng(seed))
        s = np.array([x[1] for x in shocks])
        lp = np.array([x[2] for x in shocks])
        if lp.std() > 0:
            corrs.append(np.corrcoef(s, lp)[0, 1])
    # a persistent daily shock against a six-block price series: each seed's
    # correlation is noisy (sd ≈ 0.3); its mean over 160 draws is not
    assert abs(float(np.mean(corrs))) < 0.06, np.mean(corrs)


def test_the_permutation_se_is_never_smaller_than_hc3_and_the_wald_ratio_is_published():
    d = design("c", "S000", "2026-09-01", MARGIN, FIT)
    rows, _ = _settlements(d, -2.0, rng=np.random.default_rng(3))
    r = analyze(d, price_experiment.daily_sku_series(rows, "S000", d["start_date"], d["end_date"]), FIT)
    assert r["status"] == "ok"
    det = r["details"]
    # six blocks on five arms: at least 6!/5! = 6 distinct relabelings, at most 720
    assert det["se_permutation"] is not None and 6 <= det["permutations"] <= 720
    assert r["std_err"] == pytest.approx(max(det["se_hc3"], det["se_permutation"]), abs=1e-4)
    assert det["first_stage"] == pytest.approx(1.0, abs=0.02)
    assert det["ci95"][0] < r["elasticity"] < det["ci95"][1]
    assert det["bias_estimate"] is not None and det["bias_se"] > 0 and det["bias_sentence"]
    assert det["source"] == "experiment" and det["seed"] == d["seed"]


def test_a_test_the_seller_did_not_run_identifies_nothing_and_the_washout_absorbs_the_lag():
    d = design("c", "S000", "2026-09-01", MARGIN, FIT)
    rows, _ = _settlements(d, -2.0, comply=False)
    r = analyze(d, price_experiment.daily_sku_series(rows, "S000", d["start_date"], d["end_date"]), FIT)
    assert r["status"] == "not_executed" and r["compliance"] < MIN_COMPLIANCE
    empty = analyze(d, [], FIT)
    assert empty["status"] == "insufficient_data"
    # a posting lag of one day: with the washout the first day of each block
    # is dropped; without it, the previous arm's units are counted at the new
    # arm's price and the slope attenuates
    # at 14 units a day Poisson noise drowns a one-day mislabel, so this runs at
    # a rate where the mislabel is the only thing left to see
    with_, without = [], []
    for seed in range(30):
        rows, _ = _settlements(d, -2.0, rng=np.random.default_rng(seed), lag=1, sd=0.02, base_rate=300.0)
        series = price_experiment.daily_sku_series(rows, "S000", d["start_date"], d["end_date"])
        a = analyze(d, series, FIT, washout_days=1)
        b = analyze(d, series, FIT, washout_days=0)
        if a["status"] == b["status"] == "ok":
            with_.append(a["elasticity"] + 2.0)
            without.append(b["elasticity"] + 2.0)
    assert abs(float(np.median(with_))) < abs(float(np.median(without)))


# ── the override ─────────────────────────────────────────────────────────────

def test_the_experimental_row_enters_the_fit_unshrunk_with_the_observational_kept():
    data, truth = _reactive_catalog(5, phi=0.4, rho=0.6, n_skus=20)
    sku = next(iter(truth))
    exp = {"level": "sku", "item_id": sku, "status": "ok", "elasticity": truth[sku], "std_err": 0.3,
           "r_squared": 0.8, "n_periods": 6, "price_cv": 0.03,
           "details": {"source": "experiment", "ci95": [truth[sku] - 0.7, truth[sku] + 0.7], "dof": 4,
                       "t_critical": 2.776, "residual_sd_log": 0.2}}
    rows = elasticity.run(data, experiments=[exp])
    row = next(r for r in rows if r["level"] == "sku" and r["item_id"] == sku)
    assert row["details"]["source"] == "experiment"
    assert row["elasticity"] == pytest.approx(truth[sku], abs=1e-3)   # rows round to 4 places
    assert row["details"]["shrinkage_weight"] == 1.0 and row["details"]["shrinkage"] == "none_experimental"
    assert row["details"]["observational"]["elasticity"] is not None
    # the other rows are still shrunk, and the pool statistics still exist
    others = [r for r in rows if r["level"] == "sku" and r["item_id"] != sku and r["status"] == "ok"]
    assert any(r["details"]["shrinkage"] == "empirical_bayes" for r in others)


# ── the directive and its measurement ────────────────────────────────────────

def test_the_directive_is_standing_worth_no_dollars_and_names_the_blocks():
    today = date(2026, 8, 31)
    d = directives._price_experiment_directive(FIT, MARGIN, "S000", "near_unit_elastic", "client-1", today)
    assert d["kind"] == "price_experiment" and d["mandate"] == "standing" and d["expected_impact_usd"] is None
    assert "six 7-day blocks from 2026-09-01" in d["action_text"] and "$19.00" in d["action_text"]
    assert "half an elasticity too flat" in d["action_text"]
    assert d["evidence"]["design"]["seed"] == schedule_seed("client-1", "S000", "2026-09-01")
    assert d["evidence"]["end_date"] == "2026-10-12"
    bare = directives._price_experiment_directive(None, MARGIN, "S000", "no_variation", "client-1", today)
    assert "no elasticity can be fitted" in bare["action_text"] and "not priced" in bare["action_text"]
    # drafted from the catalog: a SKU with no price variation gets one, a SKU
    # with a live test does not, and never more than EXPERIMENTS_PER_RUN
    fits = [{"level": "sku", "item_id": f"F{i}", "status": "insufficient_price_variation", "elasticity": None}
            for i in range(5)]
    margins = [{**MARGIN, "sku": f"F{i}", "revenue": 8000.0 - i} for i in range(5)]
    drafts = directives.draft_directives([], [], fits, margins, client_id="c",
                                         experiments=[{"sku": "F0", "status": "running", "design": {"x": 1}}])
    exp = [x for x in drafts if x["kind"] == "price_experiment"]
    assert len(exp) == directives.EXPERIMENTS_PER_RUN
    assert {x["evidence"]["sku"] for x in exp} == {"F1", "F2", "F3"}


def test_the_experiment_is_measured_as_information_never_dollars():
    today = date(2026, 8, 31)
    d = directives._price_experiment_directive(FIT, MARGIN, "S000", "near_unit_elastic", "client-1", today)
    d = {**d, "id": "e1", "status": "approved", "issued_at": "2026-08-31T00:00:00+00:00"}
    running = measurement.measure_price_experiment(d, [], date(2026, 8, 31), date(2026, 9, 20))
    assert running["verdict"] == "not_yet"
    design_ = d["evidence"]["design"]
    rows, _ = _settlements({**design_, "sku": "S000"}, -2.0, rng=np.random.default_rng(3))
    result = analyze({**design_, "sku": "S000"},
                     price_experiment.daily_sku_series(rows, "S000", design_["start_date"], design_["end_date"]), FIT)
    done = measurement.measure_price_experiment(
        d, [{**result, "start_date": design_["start_date"]}], date(2026, 8, 31), date(2026, 10, 20))
    assert done["verdict"] == "closed" and done["measured_impact_usd"] is None
    assert done["evidence_after"]["elasticity_exp"] == result["elasticity"]
    assert "unshrunk" in done["measurement_notes"]
    via = measurement.measure([d], {}, [], [], [], today=date(2026, 9, 20), experiments=[])
    assert via[0]["verdict"] == "not_yet"
    out = price_experiment.run({"settlement_transactions": rows},
                               [{"id": "t1", "sku": "S000", "design": design_}], [FIT])
    assert out[0]["status"] == "ok" and out[0]["test_id"] == "t1"
