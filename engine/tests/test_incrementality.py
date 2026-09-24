"""Is the ad break-even too generous or too strict? Two estimators of the
incrementality ratio ι, one honest about monthly data and one that identifies."""

from datetime import date, timedelta

import numpy as np
import pytest

from hubricon_engine import directives, measurement
from hubricon_engine.models import ad_efficiency, incrementality
from hubricon_engine.models.incrementality import (
    analyze_switchback, design_switchback, observational, switchback_seed,
)


def _period(i: int) -> tuple[str, str]:
    year, month = 2025 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _history(n_periods=12, iota=0.4, spend_cv=0.3, seed=3, noise=40.0):
    """Monthly exports where attributed sales respond 3:1 to spend and only a
    fraction ι of that response shows in total sales."""
    rng = np.random.default_rng(seed)
    traffic, ppc = [], []
    for i in range(1, n_periods + 1):
        start, end = _period(i)
        spend = 100.0 * (1 + spend_cv * rng.standard_normal())
        spend = max(20.0, spend)
        attributed = 3.0 * spend
        total = 5000.0 + iota * attributed + rng.normal(0, noise)
        traffic.append({"child_asin": "B0X", "period_start": start, "period_end": end,
                        "ordered_product_sales": total * 28, "units_ordered": 100, "sessions": 1000})
        for d in range(28):
            day = (date.fromisoformat(start) + timedelta(days=d)).isoformat()
            ppc.append({"campaign_name": "Main", "report_date": day, "spend": spend, "sales": attributed})
    return {"asin_traffic": traffic, "sku_economics": [], "ppc_spend": ppc, "ppc_search_terms": []}


# ── observational ────────────────────────────────────────────────────────────

def test_the_observational_ratio_recovers_a_planted_iota_on_a_long_clean_history():
    hits, inside = [], []
    for seed in range(20):
        r = observational(_history(n_periods=14, iota=0.4, seed=seed, noise=20.0))
        assert r["status"] == "ok", r
        hits.append(r["incrementality"])
        inside.append(r["ci95"][0] <= 0.4 <= r["ci95"][1])
    assert abs(float(np.median(hits)) - 0.4) < 0.15
    assert float(np.mean(inside)) >= 0.8
    assert r["details"]["se_estimator"] == "HC3" and r["details"]["dof"] == 14 - 1 - 2


def test_it_refuses_short_histories_and_flat_spend():
    short = observational(_history(n_periods=6))
    assert short["status"] == "insufficient_data" and "incrementality" not in short
    flat = observational(_history(n_periods=12, spend_cv=0.0))
    assert flat["status"] == "insufficient_spend_variation"


def test_the_reading_names_the_direction_only_when_the_interval_excludes_one():
    generous = observational(_history(n_periods=16, iota=0.3, seed=11, noise=10.0))
    assert generous["status"] == "ok" and "too generous" in generous["reading"]
    halo = observational(_history(n_periods=16, iota=1.8, seed=11, noise=10.0))
    assert "too strict" in halo["reading"]
    noisy = observational(_history(n_periods=9, iota=1.0, seed=5, noise=300.0))
    assert noisy["status"] == "ok" and "includes 1" in noisy["reading"]


# ── switchback ───────────────────────────────────────────────────────────────

def _simulate(schedule, iota=0.4, organic=2000.0, attributed_on=300.0, carryover=0.0,
              attribution_carryover=0.0, seed=1, paused=True, noise=40.0):
    """`carryover`: the share of the ON-day real effect that still arrives on an
    OFF day after an ON day. `attribution_carryover`: the share of ON-day
    attributed sales the platform still credits on that OFF day."""
    rng = np.random.default_rng(seed)
    totals, ppc = [], []
    prev_on = False
    for b in schedule["blocks"]:
        d = date.fromisoformat(b["start"])
        while d <= date.fromisoformat(b["end"]):
            on = b["arm"] == "on"
            if on:
                attributed, spend = attributed_on, 100.0
            elif not paused:
                attributed, spend = attributed_on * 0.6, 100.0
            else:
                attributed, spend = (attribution_carryover * attributed_on if prev_on else 0.0), 0.0
            effect = iota * attributed_on if on else (carryover * iota * attributed_on if prev_on else 0.0)
            totals.append({"date": d.isoformat(), "units": 10, "revenue": organic + effect + rng.normal(0, noise),
                           "orders": 10})
            ppc.append({"campaign_name": schedule["campaign"], "report_date": d.isoformat(),
                        "spend": spend, "sales": attributed})
            prev_on = on
            d += timedelta(days=1)
    return totals, ppc


def test_the_schedule_is_balanced_reproducible_and_blind_to_the_data():
    a = design_switchback("client-1", "Main", "2026-09-01")
    b = design_switchback("client-1", "Main", "2026-09-01")
    assert a == b and a["seed"] == switchback_seed("client-1", "Main", "2026-09-01")
    arms = [x["arm"] for x in a["blocks"]]
    assert arms.count("on") == arms.count("off") == 7
    assert arms != ["on"] * 7 + ["off"] * 7
    other = design_switchback("client-1", "Main", "2026-09-02")
    assert other["seed"] != a["seed"]
    assert a["end_date"] == "2026-09-28"


def test_the_switchback_recovers_iota_where_the_month_could_not():
    schedule = design_switchback("c", "Main", "2026-09-01")
    estimates = []
    for seed in range(24):
        totals, ppc = _simulate(schedule, iota=0.4, seed=seed)
        r = analyze_switchback(schedule, totals, ppc)
        assert r["status"] == "ok", r
        estimates.append(r["incrementality"])
    assert abs(float(np.median(estimates)) - 0.4) < 0.1
    assert r["ci90"][0] < r["incrementality"] < r["ci90"][1]
    assert r["p_permutation"] < 0.05
    assert r["compliance"] == 1.0


def test_carryover_moves_iota_both_ways_and_the_payload_says_so():
    """Real effect arriving on OFF days shrinks the total lift (ι reads low);
    attribution following the click into OFF days shrinks the attributed lift
    (ι reads high). The first draft claimed one direction; this pins both."""
    schedule = design_switchback("c", "Main", "2026-09-01")
    plain, effect, attributed = [], [], []
    for seed in range(24):
        plain.append(analyze_switchback(schedule, *_simulate(schedule, seed=seed))["incrementality"])
        effect.append(analyze_switchback(schedule, *_simulate(schedule, seed=seed, carryover=0.5))["incrementality"])
        attributed.append(analyze_switchback(
            schedule, *_simulate(schedule, seed=seed, attribution_carryover=0.5))["incrementality"])
    assert float(np.median(effect)) < float(np.median(plain)) < float(np.median(attributed))
    r = analyze_switchback(schedule, *_simulate(schedule, carryover=0.5))
    assert "carryover is not corrected" in r["details"]["basis"]


def test_a_campaign_that_kept_spending_on_off_days_identifies_nothing():
    schedule = design_switchback("c", "Main", "2026-09-01")
    r = analyze_switchback(schedule, *_simulate(schedule, paused=False))
    assert r["status"] == "not_executed" and r["compliance"] == 0.0
    few = analyze_switchback(schedule, _simulate(schedule)[0][:6], _simulate(schedule)[1])
    assert few["status"] == "insufficient_data"


# ── use ──────────────────────────────────────────────────────────────────────

def test_only_an_executed_switchback_moves_the_break_even():
    data = _history(n_periods=6)
    schedule = design_switchback("c", "Main", "2026-09-01")
    result = analyze_switchback(schedule, *_simulate(schedule, iota=0.4, noise=5.0))
    out = incrementality.run(data, [{**schedule, "result": result}])
    assert out["incrementality_for_breakeven"] == result["incrementality"]
    assert incrementality.run(data, [])["incrementality_for_breakeven"] is None

    rng = np.random.default_rng(2)
    spend = np.linspace(10, 300, 12)
    sales = 1000 * spend / (50 + spend) + rng.normal(0, 8, 12)
    ppc = [{"campaign_name": "C", "campaign_id": "C", "spend": float(s), "sales": float(v),
            "report_date": f"2026-08-{i + 1:02d}"} for i, (s, v) in enumerate(zip(spend, sales))]
    curve_data = {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [], "ppc_spend": ppc,
                  "inventory_levels": [], "cogs_inputs": []}
    plain = ad_efficiency.run(curve_data, avg_margin=0.35)[0]
    adjusted = ad_efficiency.run(curve_data, avg_margin=0.35, incrementality=0.4,
                                 incrementality_basis="switchback")[0]
    info = ad_efficiency.run(curve_data, avg_margin=0.35, incrementality=0.4,
                             incrementality_basis="observational")[0]
    # only 40% of attributed sales are real: the marginal attributed dollar must
    # return 1/(0.35·0.4) = 7.1, so the break-even spend falls
    assert adjusted["breakeven_spend"] < plain["breakeven_spend"]
    assert adjusted["breakeven_spend_attributed"] == plain["breakeven_spend"]
    assert adjusted["details"]["breakeven_marginal_roas_incremental"] == pytest.approx(1 / (0.35 * 0.4), abs=0.01)
    assert info["breakeven_spend"] == plain["breakeven_spend"]
    assert info["breakeven_spend_incremental"] == adjusted["breakeven_spend"]


def test_the_directive_designs_the_test_when_nothing_identifies_iota():
    ads = [{"campaign_name": "Main", "status": "ok", "current_spend": 120.0, "current_sales": 400.0,
            "breakeven_spend": 200.0, "bleed_terms": [], "curve_model": "hill",
            "curve_params": {"a": 1000, "k": 60, "h": 1.0},
            "details": {"uncertainty": {"basis": "parameter_covariance"},
                        "curve_cov": [[100.0, 0, 0], [0, 4.0, 0], [0, 0, 0.01]]}}]
    incr = incrementality.run(_history(n_periods=6), [])
    today = date(2026, 9, 1)
    d = directives._switchback_directive(incr, ads, 0.35, "client-1", today)
    assert d is not None and d["kind"] == "ad_switchback" and d["mandate"] == "explicit"
    assert d["expected_impact_usd"] is None
    assert "14 randomised 2-day blocks from 2026-09-02" in d["action_text"]
    assert "14 days paused" in d["action_text"]
    # cost: 14 OFF days × (0.35·400 − 120) × prior 1.0 = $280
    assert d["evidence"]["expected_cost"] == pytest.approx(280.0)
    assert d["evidence"]["expected_cost_p5"] is not None
    assert d["evidence"]["schedule"]["seed"] == switchback_seed("client-1", "Main", "2026-09-02")
    # once a switchback has run, or the history already says which way, no test
    schedule = design_switchback("c", "Main", "2026-09-01")
    done = incrementality.run(_history(n_periods=6),
                              [{**schedule, "result": analyze_switchback(schedule, *_simulate(schedule, noise=5.0))}])
    assert directives._switchback_directive(done, ads, 0.35, "client-1", today) is None
    clear = incrementality.run(_history(n_periods=16, iota=0.3, seed=11, noise=10.0), [])
    assert directives._switchback_directive(clear, ads, 0.35, "client-1", today) is None
    drafts = directives.draft_directives([], ads, [], [], incrementality=incr, client_id="client-1")
    assert any(x["kind"] == "ad_switchback" for x in drafts)


def test_the_test_is_measured_as_information_never_dollars():
    schedule = design_switchback("c", "Main", "2026-09-01")
    d = {"id": "t1", "kind": "ad_switchback", "status": "approved", "expected_impact_usd": None,
         "issued_at": "2026-08-31T00:00:00+00:00",
         "evidence": {"campaign_name": "Main", "schedule": schedule}}
    running = measurement.measure_ad_switchback(d, [schedule], date(2026, 8, 31), date(2026, 9, 10))
    assert running["verdict"] == "not_yet"
    result = analyze_switchback(schedule, *_simulate(schedule, noise=5.0))
    done = measurement.measure_ad_switchback(d, [{**schedule, "result": result}], date(2026, 8, 31), date(2026, 10, 1))
    assert done["verdict"] == "closed" and done["measured_impact_usd"] is None
    assert done["evidence_after"]["incrementality"] == result["incrementality"]
    assert "Measured:" in done["measurement_notes"]
    not_run = measurement.measure_ad_switchback(
        d, [{**schedule, "result": analyze_switchback(schedule, *_simulate(schedule, paused=False))}],
        date(2026, 8, 31), date(2026, 10, 1))
    assert not_run["verdict"] == "closed" and "kept spending" in not_run["measurement_notes"]
    via_dispatch = measurement.measure([d], {}, [], [], [], today=date(2026, 9, 10), switchbacks=[schedule])
    assert via_dispatch[0]["verdict"] == "not_yet"
