"""The engine corrections of the Simons–Thorp–Griffin bench, round three
(MATH_SCORECARD.md, iteration 38), each pinned where it can be pinned without
the bench itself.

  exact lead-time demand     a SKU's stockout probability and reorder point
                             owe nothing to a seed (a SKU at the alert line
                             was drafted a reorder under one and not another)
  per-SKU streams            a SKU's order does not move with the caller's
                             seed or with the SKUs drawn before it
  orders at planned prices   the sweep's own price steps size its orders
  the seasonal index         flagged months stay out of it; one season pools
                             every SKU to the catalogue's
  price-restated forecasts   a cheap month is not read as demand
  the sibling index          equal weights unless revenue weights earn it
  the reaction correction    each SKU read off the catalogue's own line
  the trim                   never below the spend the campaign has run
  κ                          reads the family's prediction too
"""

from datetime import date

import numpy as np
import pytest

from hubricon_engine import directives, measurement
from hubricon_engine.models import (cross_price, elasticity, forecast, inventory_econ, inventory_sim,
                                    seasonality)
from hubricon_engine.models.dependence import correlated_rates

from test_cross_price import FIT, MARGIN, _family
from test_endogeneity import _reactive_catalog
from test_inventory_econ import _inventory, _margin
from test_models import _inventory_data
from test_seasonality import _catalog

TODAY = date(2026, 9, 1)


# ── exact lead-time demand ────────────────────────────────────────────────

def test_the_stockout_probability_is_exact_and_owes_nothing_to_the_seed():
    data = _inventory_data(40)
    a = inventory_sim.run(data, np.random.default_rng(1), simulations=8000)[0]
    b = inventory_sim.run(data, np.random.default_rng(99), simulations=10)[0]
    assert a["stockout_probability"] == b["stockout_probability"]
    assert a["reorder_point"] == b["reorder_point"]
    assert a["details"]["method"].startswith("exact")
    assert a["details"]["stockout_probability_mc_se"] == 0.0
    # against two million draws of the same lognormal–Poisson model
    rng = np.random.default_rng(7)
    n, lead = 2_000_000, 40
    rate, sd = float(a["daily_velocity_mean"]), float(a["daily_velocity_std"])
    d = rng.poisson(correlated_rates(rng, [rate], [sd], (n,), 0.0)[0] * rng.lognormal(np.log(lead), 0.2, n))
    p_mc = float(np.mean(d > a["on_hand_units"] + a["inbound_units"]))
    se = np.sqrt(p_mc * (1 - p_mc) / n)
    assert abs(a["stockout_probability"] - p_mc) < 4 * se + 1e-4
    assert abs(a["reorder_point"] - int(np.quantile(d, 0.95, method="inverted_cdf"))) <= 1


# ── per-SKU streams ───────────────────────────────────────────────────────

def test_a_skus_order_does_not_move_with_the_seed_or_with_its_neighbours():
    inv = [_inventory("A", on_hand=40)]
    margins = [_margin("A")]
    one = inventory_econ.run({}, inv, margin_rows=margins, rng=np.random.default_rng(3), simulations=4000, today=TODAY)
    other_seed = inventory_econ.run({}, inv, margin_rows=margins, rng=np.random.default_rng(4), simulations=4000,
                                    today=TODAY)
    with_neighbour = inventory_econ.run({}, [_inventory("0", on_hand=10)] + inv, margin_rows=[_margin("0")] + margins,
                                        rng=np.random.default_rng(3), simulations=4000, today=TODAY)
    row = lambda out: next(r for r in out["rows"] if r["sku"] == "A")
    assert row(one)["order_up_to"] == row(other_seed)["order_up_to"] == row(with_neighbour)["order_up_to"]
    assert row(one)["details"]["demand_ladder"] == row(with_neighbour)["details"]["demand_ladder"]


# ── the order at the sweep's own prices ───────────────────────────────────

def test_the_price_plan_reads_the_steps_own_demand_effect():
    rise_fit = {**FIT, "item_id": "BLUE", "elasticity": -1.3, "details": {**FIT["details"], "ci95": [-1.7, -0.9]}}
    plan = directives.plan_prices([rise_fit], [MARGIN])
    ev = plan["drafts"]["BLUE"]["evidence"]
    assert ev["p_new"] > ev["p0"]                       # a rise
    m = plan["multipliers"]["BLUE"]
    expected = (ev["p_new"] / ev["p0"]) ** -1.3
    assert m["own"] == pytest.approx(expected, rel=0.01) and m["multiplier"] < 1.0 and m["sd"] > 0
    # and the drafter issues the very same step from the very same plan
    drafts = directives.draft_directives([], [], [rise_fit], [MARGIN], price_plan=plan)
    step = next(d for d in drafts if d["kind"] == "price_step")
    assert step["evidence"]["p_new"] == ev["p_new"] and step["expected_impact_usd"] == plan["drafts"]["BLUE"]["expected_impact_usd"]


def test_an_order_is_sized_on_demand_at_the_planned_price():
    inv = [_inventory("A", on_hand=40)]
    margins = [_margin("A")]
    base = inventory_econ.run({}, inv, margin_rows=margins, simulations=4000, today=TODAY)
    plan = {"multipliers": {"A": {"multiplier": 0.85, "sd": 0.02, "own": 0.85, "cross": 1.0, "p0": 30.0, "p_new": 31.5}}}
    planned = inventory_econ.run({}, inv, margin_rows=margins, simulations=4000, today=TODAY, price_plan=plan)
    a0 = next(r for r in base["rows"] if r["sku"] == "A")
    a1 = next(r for r in planned["rows"] if r["sku"] == "A")
    assert a1["order_up_to"] < a0["order_up_to"]
    assert a1["price_plan"]["demand_multiplier"] == 0.85
    # what is valued at today's price keeps today's rate
    assert a1["rate_mean"] == a0["rate_mean"] and a1["low_inventory_fee_month"] == a0["low_inventory_fee_month"]


# ── the seasonal index ────────────────────────────────────────────────────

def _with_deal(data, sku="S03", month="2025-10"):
    """One October deal: units tripled, and a settlement file whose rebates say so."""
    econ, txns = [], []
    for r in data["sku_economics"]:
        if r["sku"] == sku and r["period_start"].startswith(month):
            r = {**r, "units_sold": r["units_sold"] * 3.0, "sales": r["sales"] * 3.0}
        econ.append(r)
    for r in econ:
        if r["sku"] == sku:
            rebate = 0.2 * r["sales"] if r["period_start"].startswith(month) else 0.0
            txns.append({"txn_type": "Order", "sku": sku, "txn_date": r["period_start"][:8] + "15",
                         "product_sales": r["sales"], "promotional_rebates": -rebate})
    return {**data, "sku_economics": econ, "settlement_transactions": txns}


def test_a_flagged_month_stays_out_of_the_index_and_one_season_pools_every_sku():
    clean = seasonality.indices(_catalog(months=12, start_month=9))
    dealt = seasonality.indices(_with_deal(_catalog(months=12, start_month=9)))
    # the deal month is out: the catalogue's October is what it was without it
    assert dealt["catalog"][10]["index"] == pytest.approx(clean["catalog"][10]["index"], abs=0.02)
    # one season: every SKU carries the catalogue's index, the dealt one included
    s03 = dealt["per_sku"]["S03"]
    assert s03["basis"].startswith("catalog index (one season")
    assert s03["index"][10] == dealt["catalog"][10]["index"]


# ── price-restated forecasts ──────────────────────────────────────────────

def test_a_cheap_month_is_restated_at_todays_price_before_it_is_smoothed():
    econ = []
    for k in range(10):
        start = f"2026-{k + 1:02d}-01"
        price = 16.0 if k == 8 else 20.0                  # the second-to-last month 20% cheaper
        units = 10.0 * 28 * (price / 20.0) ** -2.0        # ε = −2, flat demand otherwise
        econ.append({"sku": "A", "asin": "BA", "period_start": start, "period_end": start[:8] + "28",
                     "units_sold": units, "sales": units * price, "avg_sales_price": price})
    data = {"sku_economics": econ, "asin_traffic": [], "inventory_levels": [], "cogs_inputs": []}
    fit = [{"level": "sku", "item_id": "A", "status": "ok", "elasticity": -2.0, "details": {}}]
    plain = next(f for f in forecast.run(data) if f["item_id"] == "A")
    restated = next(f for f in forecast.run(data, elasticity_rows=fit) if f["item_id"] == "A")
    assert restated["details"]["price_normalised"]["reference_price"] == pytest.approx(20.0)
    assert restated["details"]["price_normalised"]["periods_adjusted"] == 10
    # every restated period is the flat 10 a day, so the forecast is too
    assert float(restated["daily_rate_point"]) == pytest.approx(10.0, rel=1e-6)
    assert all(float(x["rate"]) == pytest.approx(10.0, rel=1e-6) for x in restated["details"]["series"])
    assert float(plain["daily_rate_point"]) != pytest.approx(10.0, rel=1e-3)


# ── the sibling index ─────────────────────────────────────────────────────

def test_the_sibling_index_is_equal_weighted_unless_revenue_weights_earn_it():
    out = cross_price.run(_family(4))
    assert out["index_weighting"] == "equal"
    choice = out["index_choice"]
    assert choice["threshold"] == cross_price.VUONG_Z and choice["vuong_z"] <= cross_price.VUONG_Z


# ── the reaction correction ───────────────────────────────────────────────

def test_each_sku_is_corrected_on_the_catalogues_own_line_when_it_can_draw_one():
    data, _ = _reactive_catalog(3, 0.4, 0.6, n_skus=80, n_periods=12)
    ok = [r for r in elasticity.run(data) if r["level"] == "sku" and r["status"] == "ok"]
    en = ok[0]["details"]["endogeneity"]
    assert en["applied"] is True
    line = en["bias_by_price_variance"]
    assert line is not None and line["slope_se"] > 0
    for r in ok:
        d = r["details"]
        assert d["epsilon_uncorrected"] - d["epsilon_corrected"] == pytest.approx(d["reaction_bias_sku"], abs=2e-4)
        # the reading off the line, through the constant at the centre
        expect = en["bias_hat"] + line["slope_used"] * (d["price_log_var"] - line["v_centre"])
        assert d["reaction_bias_sku"] == pytest.approx(expect, abs=2e-4)
        assert d["reaction_bias_se"] >= en["bias_se"] - 1e-9
    assert len({r["details"]["reaction_bias_sku"] for r in ok}) > 1


def test_a_small_catalogue_gets_the_one_constant():
    data, _ = _reactive_catalog(3, 0.4, 0.6, n_skus=30, n_periods=12)
    ok = [r for r in elasticity.run(data) if r["level"] == "sku" and r["status"] == "ok"]
    en = ok[0]["details"]["endogeneity"]
    assert en["applied"] is True and en.get("bias_by_price_variance") is None
    assert all(r["details"]["reaction_bias_sku"] == pytest.approx(en["bias_hat"], abs=1e-4) for r in ok)


def test_the_bootstrap_over_skus_is_a_weighted_sum_of_their_moments():
    data, _ = _reactive_catalog(5, 0.4, 0.6, n_skus=40, n_periods=12)
    ok = [r for r in elasticity.run(data) if r["level"] == "sku" and r["status"] == "ok"]
    series = []
    for r in ok:
        lp, lq = elasticity._series_of(r["details"]["points"])
        if len(lp) >= elasticity.DYNAMIC_MIN_PERIODS:
            series.append(elasticity._sku_moments(lp, lq))
    pick = np.random.default_rng(11).integers(0, len(series), len(series))
    counts = np.bincount(pick, minlength=len(series))[None, :]
    assert elasticity.reaction_bias_weighted(series, counts)[0] == pytest.approx(
        elasticity.reaction_bias([series[j] for j in pick]), abs=1e-9)


# ── the trim ──────────────────────────────────────────────────────────────

def test_a_trim_stops_at_the_spend_the_campaign_has_run():
    row = {"campaign_name": "C", "status": "ok", "current_spend": 200.0, "breakeven_spend": 80.0,
           "details": {"uncertainty": {"breakeven_p95": 95.0}, "spend_p10": 130.0,
                       "form_fits": [{"model": "log", "breakeven_p95": 95.0},
                                     {"model": "hill", "breakeven_p95": 110.0}]}}
    t = directives.trim_candidates([row], 0.4)["C"]
    assert t["breakeven"] == 130.0 and t["bound_by"] == "observed_floor"
    row["details"]["spend_p10"] = 60.0
    t = directives.trim_candidates([row], 0.4)["C"]
    assert t["breakeven"] == 110.0 and t["bound_by"] == "form_disagreement"
    row["details"]["form_fits"] = row["details"]["form_fits"][:1]
    t = directives.trim_candidates([row], 0.4)["C"]
    assert t["breakeven"] == 95.0 and t["bound_by"] == "breakeven"


# ── κ reads the family's prediction ───────────────────────────────────────

def _kappa_case(with_cross_term: bool):
    """Eight SKUs in two families of four, every one raised 5%, whose after
    volume moved exactly as own + family said: ε = −2, ε_cross = +1."""
    eps, eps_c, r = -2.0, 1.0, 1.05
    margins, drafts = [], []
    skus = [f"K{i}" for i in range(8)]
    for i, s in enumerate(skus):
        fam = [x for x in skus if x != s and int(x[1:]) // 4 == i // 4]
        q0 = 100.0 + 10 * i
        q1 = q0 * r ** eps * np.exp(eps_c * np.log(r))       # all three siblings also rose 5%
        margins += [{"sku": s, "period_start": "2026-08-01", "period_end": "2026-08-28", "units": q0,
                     "revenue": q0 * 20.0},
                    {"sku": s, "period_start": "2026-09-02", "period_end": "2026-09-29", "units": q1,
                     "revenue": q1 * 21.0}]
        ev = {"sku": s, "p0": 20.0, "p_new": 21.0, "elasticity": eps, "baseline_units": q0,
              "baseline_period": "2026-08-01", "mc_inputs": {"demand_sd_log": 0.1}}
        if with_cross_term:
            ev["cross_effect"] = {"eps_cross": eps_c, "siblings": [{"sku": j, "weight": 1 / 3} for j in fam]}
        drafts.append({"kind": "price_step", "evidence": ev})
    return measurement.volume_realisation(drafts, margins, lambda d: date(2026, 9, 1))


def test_kappa_reads_the_familys_prediction_and_needs_three_errors_to_override():
    with_family = _kappa_case(True)
    own_only = _kappa_case(False)
    assert with_family["kappa"] == pytest.approx(1.0, abs=0.02) and with_family["applied"] is False
    # without the family term the same batch reads as half a response
    assert own_only["kappa"] < 0.6
    assert measurement.REALISATION_T == 3.0
