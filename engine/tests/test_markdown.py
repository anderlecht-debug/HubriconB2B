"""Excess stock three ways — hold, liquidate, mark down — and the stretch."""

from datetime import date

import numpy as np
import pytest

from hubricon_engine import directives, measurement, replay
from hubricon_engine.models import inventory_econ as econ
from hubricon_engine.models import markdown as md
from hubricon_engine.models.markdown import choose, position_value, stretch, value_options

TODAY = date(2026, 9, 1)
FIT = {"level": "sku", "item_id": "X", "status": "ok", "elasticity": -2.0, "std_err": 0.2,
       "details": {"ci95": [-2.5, -1.5], "dof": 6, "t_critical": 2.447, "residual_sd_log": 0.15}}


def _draws(n=2000, rate=3.0):
    return (np.full(n, rate), np.full(n, -2.0), np.full(n, 0.15), np.full(n, 1.5))


def test_hold_value_excludes_sunk_landed_cost_and_matches_a_hand_computed_sum():
    """No cliffs, 60 units at one a day: two months of 30 units at $15.50
    contribution, discounted at 1%/month — nothing else, and landed cost is
    nowhere in it."""
    rate, eps, f, F = _draws(n=1, rate=1.0)
    npv, months = position_value(60.0, rate, eps, f, F, 20.0, None, False, 0.05, 60, TODAY, cliffs=False)
    contrib = 20.0 * 0.85 - 1.5
    i = 1 + econ.ANNUAL_CAPITAL_RATE / 12
    assert float(npv[0]) == pytest.approx(30 * contrib / i + 30 * contrib / i**2, rel=1e-9)
    assert float(months[0]) == 1.0   # position was under the cover after month 1... target = 90 units


def test_every_option_values_the_same_position_and_degenerate_options_coincide():
    rate, eps, f, F = _draws()
    common = dict(vol=0.05, age0=60, today=TODAY)
    hold, _ = position_value(500, rate, eps, f, F, 20.0, None, False, **common)
    zero_depth, _ = position_value(500, rate, eps, f, F, 20.0, 0.0, False, **common)
    assert np.allclose(hold, zero_depth)
    # a position inside the target cover has no excess: liquidate == hold
    no_excess_hold, _ = position_value(100, rate, eps, f, F, 20.0, None, False, **common)
    no_excess_liq, _ = position_value(100, rate, eps, f, F, 20.0, None, True, **common)
    assert np.allclose(no_excess_hold, no_excess_liq)


def test_the_excess_sells_last_and_the_carry_falls_on_it():
    """Same excess, twice the cover in front of it: the excess is reached later,
    carries longer, and is worth less held."""
    rate, eps, f, F = _draws(n=1, rate=2.0)
    small, m_small = position_value(180 + 200, rate, eps, f, F, 20.0, None, False, 0.3, 150, TODAY)
    # the same 200 excess behind a 3× slower sell-down of the cover: age it more first
    slow_rate = np.full(1, 2.0 / 3)
    big, m_big = position_value(60 + 200, slow_rate, eps, f, F, 20.0, None, False, 0.3, 150, TODAY)
    assert m_big[0] > m_small[0]
    assert big[0] < small[0]


def test_markdown_wins_with_steep_carry_and_elastic_demand_and_liquidation_when_demand_is_dead():
    live = value_options(800, 20.0, 3.0, 0.4, 0.15, 1.5, 0.4, 200, TODAY, elasticity_row=FIT, draws=2000)
    pick = choose(live, tol=2000.0)
    assert pick["decision"] == "markdown" and pick["depth"] in md.DEPTH_GRID
    assert live["markdown"][pick["depth"]]["npv"].mean() > live["hold"]["npv"].mean()
    dead = value_options(800, 20.0, 0.2, 0.05, 0.15, 1.5, 0.4, 300, TODAY, elasticity_row=FIT, draws=2000)
    assert choose(dead, tol=2000.0)["decision"] == "liquidate"
    healthy = value_options(300, 20.0, 3.0, 0.4, 0.15, 1.5, 0.05, 60, TODAY, elasticity_row=FIT, draws=2000)
    assert choose(healthy, tol=2000.0)["decision"] == "hold"


def test_the_band_widens_with_the_elasticitys_uncertainty_and_deeper_still_at_deeper_depths():
    tight = value_options(800, 20.0, 3.0, 0.4, 0.15, 1.5, 0.4, 200, TODAY, elasticity_row=FIT, draws=3000)
    loose = value_options(800, 20.0, 3.0, 0.4, 0.15, 1.5, 0.4, 200, TODAY, draws=3000,
                          elasticity_row={**FIT, "std_err": 0.6, "details": {**FIT["details"], "ci95": [-3.5, -0.5]}})

    def width(opts, d):
        g = opts["markdown"][d]["npv"] - opts["hold"]["npv"]
        return float(np.quantile(g, 0.95) - np.quantile(g, 0.05))

    assert width(loose, 0.10) > width(tight, 0.10)
    assert width(loose, 0.30) > width(loose, 0.10)


def test_the_floor_and_the_range_flag():
    opts = value_options(800, 20.0, 3.0, 0.4, 0.15, 1.5, 0.4, 200, TODAY, elasticity_row=FIT,
                         min_observed_price=19.0, draws=500)
    # 5% off: $19.00, inside the observed range; 15% off: $17.00 < 0.9 × $19
    assert opts["markdown"][0.05]["beyond_observed_range"] is False
    assert opts["markdown"][0.15]["beyond_observed_range"] is True
    # a $2.50 item: a 40% markdown nets 1.50·0.85 − 1.5 < 0.25 recovered — below the floor
    cheap = value_options(800, 2.5, 3.0, 0.4, 0.15, 1.5, 0.05, 60, TODAY, elasticity_row=FIT, draws=200)
    assert cheap["markdown"][0.40]["status"] == "below_floor"


def test_the_stretch_pays_on_an_inelastic_sku_and_refuses_on_an_elastic_one():
    """80 units on hand, 40 days of lead at 2.1/day: expected demand 84 and a
    stockout more likely than not. On an inelastic SKU a rise sells nearly the
    same units at a higher price and trims the risk; on an elastic one the
    rise that would stop the stockout throws away more sales than it recovers,
    and the first draft's stockout target recommended exactly that."""
    inelastic = {**FIT, "elasticity": -0.5, "std_err": 0.1, "details": {**FIT["details"], "ci95": [-0.75, -0.25]}}
    st = stretch(80, 40.0, 2.1, 0.2, inelastic, 20.0, 0.15, 1.5, draws=4000, tol=300.0)
    assert st["status"] == "ok" and 0 < st["step_fraction"] <= md.STEP_CAP
    assert st["p_stockout_after"] < st["p_stockout_before"]
    assert st["gain"]["p50"] > 0 and st["gain"]["p5"] <= st["gain"]["p50"] <= st["gain"]["p95"]
    assert st["mc_inputs"]["thinning"].startswith("binomial") and st["objective_value"] > 0
    elastic = {**FIT, "elasticity": -8.0, "details": {**FIT["details"], "ci95": [-8.5, -7.5]}}
    lose = stretch(80, 40.0, 2.1, 0.2, elastic, 20.0, 0.15, 1.5, draws=4000, tol=300.0)
    assert lose["status"] == "no_stretch_pays"
    # the ladder says why: the deeper the rise, the more the window loses
    assert lose["ladder"][-1]["gain_p50"] < lose["ladder"][0]["gain_p50"] and lose["ladder"][-1]["gain_p50"] < 0
    assert stretch(80, None, 2.1, 0.2, FIT, 20.0, 0.15, 1.5)["status"] == "insufficient_data"


def test_thinned_draws_have_less_variance_than_independent_poissons():
    rng = np.random.default_rng(0)
    lam = rng.uniform(80, 120, 20000)
    d0 = rng.poisson(lam)
    thinned = rng.binomial(d0, 0.9)
    independent = rng.poisson(lam * 0.9)
    assert np.var(d0 - thinned) < np.var(d0 - independent)


def _econ_row(sku="X", excess=500, rate=3.0, price=20.0, min_price=19.0, aged=120.0, storage=40.0, stockout=0.05):
    return {"sku": sku, "status": "ok", "price": price, "fee_rate": 0.15, "fixed_fee": 1.5, "rate_mean": rate,
            "rate_sd": 0.4, "excess_units": excess, "item_volume_cuft": 0.4, "weighted_age": 200.0,
            "size_tier": "standard", "min_observed_price": min_price, "aged_surcharge_month": aged,
            "storage_next_month": storage, "stockout_probability": stockout, "position": excess + rate * 90}


MARGIN = {"sku": "X", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 84, "revenue": 1680.0,
          "amazon_fees": 378.0, "cogs": 420.0, "net_margin": 800.0,
          "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 1.5}}


def test_run_decides_three_ways_and_two_ways_without_an_elasticity():
    inv = {"rows": [_econ_row(), _econ_row(sku="Y", excess=0)]}
    out = md.run({}, inv, [FIT], [MARGIN, {**MARGIN, "sku": "Y"}], [], TODAY, "amazon", draws=1500)
    assert out["status"] == "ok" and out["seed"] == md.MD_SEED
    x = next(r for r in out["rows"] if r["sku"] == "X")
    assert x["status"] == "ok" and x["decision"] in ("hold", "liquidate", "markdown")
    assert "markdown_10" in x["npv"] and x["npv"]["hold"]["p5"] <= x["npv"]["hold"]["p50"]
    y = next(r for r in out["rows"] if r["sku"] == "Y")
    assert y["status"] == "no_excess"
    two_way = md.run({}, inv, [], [MARGIN], [], TODAY, "amazon", draws=1500)
    x2 = next(r for r in two_way["rows"] if r["sku"] == "X")
    assert x2["status"] == "no_elasticity" and x2["decision"] in ("hold", "liquidate") and x2["npv"].keys() == {"hold", "liquidate"}
    assert two_way["summary"]["n_no_elasticity"] == 1


def _md_row(depth=0.10, gain=(150.0, 600.0, 1100.0), beyond=False):
    return {"sku": "X", "status": "ok", "decision": "markdown", "depth": depth, "p0": 20.0, "p_new": round(20 * (1 - depth), 2),
            "excess_units": 500, "months_to_clear": {"hold": 8.0, "markdown": 3.0},
            "npv": {"hold": {"p50": 5000.0}, "liquidate": {"p50": 1000.0}, f"markdown_{int(depth * 100)}": {"p50": 5600.0}},
            "delta_vs_hold": {"p5": gain[0], "p50": gain[1], "p95": gain[2], "mc_se": {}},
            "delta_vs_liquidate": {"p50": 4600.0}, "delta_p5": gain[0], "delta_p50": gain[1], "delta_p95": gain[2],
            "p_loss": 0.03, "mc_se": {}, "mc_inputs": {"draws": 4000, "seed": 1}, "carry_saving_p50": 800.0,
            "carry_month_now": 160.0, "beyond_observed_range": beyond, "elasticity": -2.0, "std_err": 0.2,
            "ci95": [-2.5, -1.5], "fee_rate": 0.15, "fixed_fee_per_unit": 1.5}


def test_the_directive_is_standing_inside_the_cap_and_explicit_beyond_it():
    d = directives._markdown_directive(_md_row(depth=0.05), MARGIN, FIT)
    assert d["kind"] == "markdown" and d["mandate"] == "standing" and d["expected_impact_usd"] == 600.0
    assert "Mark X down 5% to $19.00" in d["action_text"] and "about 3 months" in d["action_text"]
    assert "+$600 against holding" in d["action_text"] and "+$4,600 against liquidating" in d["action_text"]
    deep = directives._markdown_directive(_md_row(depth=0.25, beyond=True), MARGIN, FIT)
    assert deep["mandate"] == "explicit" and "extrapolation" in deep["action_text"]
    assert replay.completeness(d)["complete"] and replay.completeness(d)["distribution_complete"]
    # the downside guard: a bad case of −$900 against 15% of a $857 monthly net
    guarded = directives._markdown_directive(_md_row(gain=(-900.0, 600.0, 1100.0)), MARGIN, FIT)
    assert guarded["mandate"] == "explicit" and "worst realistic case" in guarded["mandate_reason"]


def test_the_markdown_replaces_the_price_step_and_the_aged_surcharge_draft_for_its_sku():
    inv_econ = {"rows": [{**_econ_row(), "decision": "hold", "hold_npv": 5000.0, "liquidate_value": 1000.0,
                          "low_inventory_fee_risk": False, "low_inventory_fee_month": 0.0,
                          "aged_units_181_plus": 300, "peak_storage_premium_month": 0.0}]}
    markdown = {"status": "ok", "rows": [_md_row(depth=0.10)]}
    drafts = directives.draft_directives([], [], [FIT], [MARGIN], inv_econ=inv_econ, markdown=markdown)
    kinds = [(x["kind"], x["evidence"].get("sku")) for x in drafts]
    assert ("markdown", "X") in kinds
    assert ("price_step", "X") not in kinds
    assert not any(k == "aged_surcharge" for k, _ in kinds)
    assert not any(k == "liquidation" for k, _ in kinds)
    # a liquidation decision from the three-way rows carries its band
    liq = {"status": "ok", "rows": [{**_md_row(), "decision": "liquidate", "depth": None,
                                     "delta_p5": 100.0, "delta_p50": 400.0, "delta_p95": 700.0}]}
    drafts = directives.draft_directives([], [], [FIT], [MARGIN], inv_econ=inv_econ, markdown=liq)
    liq_d = next(x for x in drafts if x["kind"] == "liquidation")
    assert liq_d["evidence"]["delta_p50"] == 400.0 and "No markdown depth nets more" in liq_d["action_text"]


def test_the_stretch_lands_as_an_ordinary_price_step():
    row = {**_md_row(), "decision": None, "stretch": {
        "status": "ok", "step_fraction": 0.03, "p_new": 20.6, "p0": 20.0, "p_stockout_before": 0.45,
        "p_stockout_after": 0.2, "gain": {"p5": 20.0, "p50": 90.0, "p95": 160.0, "mc_se": {}}, "p_loss": 0.02,
        "mc_inputs": {"draws": 4000, "seed": 1, "lead_days": 40}}}
    d = directives._stretch_directive(row, MARGIN, FIT)
    assert d["kind"] == "price_step" and d["mandate"] == "standing" and d["evidence"]["reason"] == "stretch"
    assert "stockout risk falls from 45% to 20%" in d["action_text"] and "+$90 over the window" in d["action_text"]
    assert replay.completeness(d)["complete"] and replay.completeness(d)["distribution_complete"]
    drafts = directives.draft_directives([], [], [FIT], [MARGIN], markdown={"status": "ok", "rows": [row]})
    steps = [x for x in drafts if x["kind"] == "price_step" and x["evidence"]["sku"] == "X"]
    assert len(steps) == 1 and steps[0]["evidence"]["reason"] == "stretch"


def test_the_markdown_is_measured_before_landed_cost_and_adds_the_carry_saving():
    d = {**directives._markdown_directive(_md_row(depth=0.10), MARGIN, FIT), "id": "m1", "status": "approved",
         "issued_at": "2026-08-31T00:00:00+00:00"}
    # the markdown was made: 160 units at $18 in the after period (up from 84 at $20)
    after = [{"sku": "X", "period_start": "2026-09-01", "period_end": "2026-09-28", "units": 160, "revenue": 2880.0,
              "amazon_fees": 2880.0 * 0.15 + 160 * 1.5, "cogs": 800.0, "net_margin": 0.0,
              "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 1.5}}]
    inv_now = {"rows": [{"sku": "X", "aged_surcharge_month": 20.0, "storage_next_month": 10.0}]}
    v = measurement.measure_markdown(d, after, inv_now, date(2026, 8, 31), date(2026, 10, 1))
    assert v["verdict"] == "measured" and v["attribution"] == "attributable"
    assert v["evidence_after"]["carry_saving"] == pytest.approx(130.0)   # 160 − 30, one period, under the promised 800
    assert v["evidence_after"]["factual_before_cogs"] == pytest.approx(2880.0 - 432.0 - 240.0)
    assert "before landed cost" in v["measurement_notes"]
    assert v["measured_impact_usd"] <= 600.0 + 0.01
    # never made: stalled
    same_price = [{**after[0], "units": 84, "revenue": 1680.0, "amazon_fees": 378.0}]
    assert measurement.measure_markdown(d, same_price, inv_now, date(2026, 8, 31), date(2026, 10, 1))["verdict"] == "not_yet"
    via = measurement.measure([d], {}, after, [], [], today=date(2026, 10, 1), inv_econ=inv_now)
    assert via[0]["verdict"] == "measured"
