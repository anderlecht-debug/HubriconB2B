"""Model decay: parameter drift between runs, and the promises by cohort."""

from datetime import date, timedelta

import numpy as np
import pytest

from hubricon_engine import replay
from hubricon_engine.models import drift
from hubricon_engine.models.pricing_engine import price_move


def _fits(n=60, seed=1, shift=None):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        eps = -2.0 + 0.3 * rng.standard_normal()
        rows.append({"level": "sku", "item_id": f"S{i:03d}", "status": "ok", "elasticity": round(eps, 4),
                     "std_err": 0.15, "details": {"ci95": [eps - 0.4, eps + 0.4], "dof": 6, "t_critical": 2.447}})
    if shift:
        for i, delta in shift.items():
            rows[i]["elasticity"] = round(rows[i]["elasticity"] + delta, 4)
    return rows


def test_a_planted_shift_is_flagged_at_the_fdr_and_a_null_catalogue_is_quiet():
    old = _fits()
    same = [{**r, "elasticity": round(r["elasticity"] + 0.15 * np.random.default_rng(i).standard_normal(), 4)}
            for i, r in enumerate(old)]
    null = drift.compare_runs(same, old, [], [])
    assert null["status"] == "ok" and null["n_pairs"] == 60 and null["n_drifted"] <= 3
    moved = _fits(shift={3: -1.4, 17: 1.2})
    out = drift.compare_runs(moved, old, [], [])
    flagged = {d["item_id"] for d in out["drifted"]}
    assert {"S003", "S017"} <= flagged and len(flagged) <= 4
    assert all(abs(p["z"]) > 3 for p in out["pairs"] if p["item_id"] in ("S003", "S017"))
    assert drift.compare_runs(old, [], [], [])["status"] == "insufficient_data"


def test_a_drifted_fit_walks_half_as_far():
    margin = {"sku": "S003", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 300, "revenue": 6000.0,
              "amazon_fees": 1350.0, "cogs": 1500.0, "net_margin": 3000.0}
    fit = {"level": "sku", "item_id": "S003", "status": "ok", "elasticity": -2.2, "std_err": 0.35,
           "details": {"ci95": [-3.1, -1.3], "dof": 6, "t_critical": 2.447, "residual_sd_log": 0.2}}
    plain = price_move(margin, fit)
    marked = drift.apply_to_elasticity([dict(fit, details=dict(fit["details"]))],
                                       {"drifted": [{"kind": "elasticity", "level": "sku", "item_id": "S003"}]})[0]
    halved = price_move(margin, marked)
    assert plain["policy"]["drift_tolerance_scale"] == 1.0 and halved["policy"]["drift_tolerance_scale"] == 0.5
    assert halved["policy"]["risk_budget"] == pytest.approx(plain["policy"]["risk_budget"] / 2, rel=1e-6)
    assert abs(halved["step_fraction"]) <= abs(plain["step_fraction"]) + 1e-9


def _directive(i, promised, measured, measured_at):
    return {"id": f"d{i}", "kind": "price_step", "dedupe_key": f"k{i}", "expected_impact_usd": promised,
            "measured_impact_usd": measured, "measured_at": measured_at.isoformat(),
            "evidence": {"sku": f"S{i}", "p0": 20.0, "p_new": 21.0, "elasticity": -2.0, "ci95": [-2.5, -1.5],
                         "baseline_units": 100, "baseline_revenue": 2000.0, "baseline_period": "2026-01-01",
                         "delta_p5": promised * 0.2, "delta_p50": promised, "delta_p95": promised * 1.8,
                         "p_loss": 0.05, "mc_inputs": {"draws": 6000, "seed": 1}}}


def test_the_replay_scores_by_cohort_and_names_a_decay_the_pooled_ratio_hides():
    today = date(2026, 9, 1)
    ds = []
    # three older cohorts realising 0.7 of the promise, the latest realising 0.15
    for c, ratio in ((3, 0.7), (2, 0.7), (1, 0.7), (0, 0.15)):
        for i in range(6):
            ds.append(_directive(c * 10 + i, 500.0, 500.0 * ratio, today - timedelta(days=c * 90 + i * 5)))
    card = replay.score(ds)
    assert card["status"] == "ok" and card["realisation_ratio"] > replay.MIN_REALISATION
    bc = card["by_cohort"]
    assert bc["status"] == "ok" and len(bc["cohorts"]) == 4 and bc["cohorts"][0]["cohort"] == 0
    assert bc["cohorts"][0]["realisation_ratio"] == pytest.approx(0.15, abs=1e-6)
    assert bc["cohorts"][0]["ratio_p5"] <= 0.15 <= bc["cohorts"][0]["ratio_p95"] + 1e-9
    assert bc["decaying"] is True and "DECAYING" in card["note"]
    assert bc["trend"]["direction"] == "falling"
    steady = replay.score([_directive(i, 500.0, 350.0, today - timedelta(days=(i % 4) * 90)) for i in range(24)])
    assert steady["by_cohort"]["decaying"] is False and steady["by_cohort"]["trend"]["direction"] in ("flat", "rising", "falling")
    undated = replay.score([{**_directive(i, 500.0, 350.0, today), "measured_at": None} for i in range(10)])
    assert undated["by_cohort"]["status"] == "no_dates"
