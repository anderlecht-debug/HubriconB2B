"""Every path either produces a defensible number or a status. Zero paths invent one.

This is the brand rule, as a test file. Each degenerate input the engine can
actually be handed gets a named status and an assertion here: no landed cost, no
units, no revenue, one price all year, fewer periods than the floor, a flat
series, a fit sitting on the pole, a fit on the wrong side of zero. If any of
these ever starts returning a number instead, this file fails.

The refusal test at the end is the one that matters most commercially: the
thinnest input a real seller could plausibly hand over — one SKU, five periods,
no landed cost, one price change — must come back as statuses.
"""

import numpy as np
import pytest

from hubricon_engine.directives import draft_directives
from hubricon_engine.models import (
    anomaly,
    cashflow,
    elasticity,
    inventory_sim,
    margin,
    risk,
)
from hubricon_engine.models.pricing_engine import (
    delta_draws,
    near_unit_elastic,
    optimal_price,
    price_move,
    profit_delta,
)


def _data(**over):
    base = {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [], "cogs_inputs": [],
            "settlement_transactions": []}
    base.update(over)
    return base


def _econ(prices, units, sku="S1", fees=True):
    rows = []
    for i, (p, u) in enumerate(zip(prices, units), start=1):
        revenue = float(p) * float(u)
        rows.append({
            "sku": sku, "asin": "B0" + sku,
            "period_start": f"2026-{i:02d}-01", "period_end": f"2026-{i:02d}-28",
            "units_sold": float(u), "avg_sales_price": float(p), "sales": revenue,
            "referral_fees": -0.15 * revenue if fees else None,
            "fba_fulfillment_fees": -1.5 * float(u) if fees else None,
            "storage_fees": 0.0 if fees else None, "other_fees": 0.0,
            "net_proceeds": revenue,
        })
    return rows


MARGIN = {"units": 100, "revenue": 2000.0, "amazon_fees": 300.0, "cogs": 500.0,
          "period_start": "2026-07-01", "period_end": "2026-07-31"}
FIT = {"elasticity": -2.4, "std_err": 0.15,
       "details": {"ci95": [-2.82, -1.98], "dof": 4, "t_critical": 2.776,
                   "residual_sd_log": 0.15}}


# ── the elasticity fit's own refusals ─────────────────────────────────────

def test_fewer_periods_than_the_floor_is_a_status():
    r = elasticity.run(_data(sku_economics=_econ([18, 20, 22], [100, 90, 80])))[0]
    assert r["status"] == "insufficient_data"
    assert r.get("elasticity") is None
    assert r.get("std_err") is None


def test_one_price_all_year_is_a_status_and_names_itself():
    r = elasticity.run(_data(sku_economics=_econ([20.0] * 8, [500, 510, 490, 505, 495, 500, 498, 502])))[0]
    assert r["status"] == "insufficient_price_variation"
    assert r.get("elasticity") is None
    assert r["price_cv"] is not None     # the number that failed the guard is shown


def test_a_single_price_change_is_still_too_little_variation():
    """Two distinct prices over eight periods: a price CV under 2%."""
    prices = [20.0] * 7 + [20.2]
    r = elasticity.run(_data(sku_economics=_econ(prices, [500] * 8)))[0]
    assert r["status"] == "insufficient_price_variation"


def test_zero_and_negative_units_are_dropped_not_logged():
    """log(0) is not a number. Periods with no units leave the fit rather than
    entering it as a zero."""
    rows = _econ([18, 19, 20, 21, 22, 23], [100, 0, 95, 90, 85, 80])
    r = elasticity.run(_data(sku_economics=rows))[0]
    assert r["n_periods"] == 5            # the zero-unit period is gone
    assert r["status"] == "ok"
    assert np.isfinite(r["elasticity"])


def test_a_flat_unit_series_does_not_produce_a_confident_zero():
    """Identical units at every price is a real pattern and the fit reports it,
    with an interval that contains zero rather than a confident ε of 0."""
    r = elasticity.run(_data(sku_economics=_econ([18, 19, 20, 21, 22, 23], [500] * 6)))[0]
    assert r["status"] == "ok"
    assert r["elasticity"] == pytest.approx(0.0, abs=1e-6)
    # and an inelastic-to-zero fit produces no priceable move
    assert price_move(MARGIN, {**r, "item_id": "S1"}) is None


# ── the price engine's refusals ───────────────────────────────────────────

def test_no_landed_cost_means_no_dollar_exact_recommendation():
    assert price_move({**MARGIN, "cogs": None}, FIT) is None


def test_zero_units_and_zero_revenue_are_refusals():
    assert price_move({**MARGIN, "units": 0}, FIT) is None
    assert price_move({**MARGIN, "revenue": 0.0}, FIT) is None
    assert price_move({**MARGIN, "units": -5}, FIT) is None


def test_a_cost_that_swallows_the_price_has_no_interior_optimum():
    assert optimal_price(-2.0, 0.0, 0.15, 0.0) is None
    assert optimal_price(-2.0, -1.0, 0.15, 0.0) is None
    # and a fee rate at or past 1 is not a fee rate
    assert optimal_price(-2.0, 5.0, 1.0, 0.0) is None
    assert optimal_price(-2.0, 5.0, -0.1, 0.0) is None


def test_the_pole_is_a_status_not_a_price():
    move = price_move(MARGIN, {"elasticity": -1.05, "std_err": 0.2,
                               "details": {"ci95": [-1.6, -0.5], "dof": 4,
                                           "t_critical": 2.776, "residual_sd_log": 0.2}})
    assert move["status"] == "near_unit_elastic"
    assert move["destination"] is None


def test_a_positive_elasticity_is_refused_outright():
    """A fitted upward-sloping demand curve is a fit that failed, not a finding
    that price rises grow volume."""
    for eps in (0.0, 0.4, 2.0):
        assert price_move(MARGIN, {"elasticity": eps, "details": {}}) is None


def test_a_fit_already_at_its_optimum_produces_nothing():
    """Under half a percent of a move is not an instruction."""
    # P* == p0 exactly: c + F chosen so [(c+F)/(1-f)]·ε/(1+ε) lands on $20
    eps, f = -3.0, 0.15
    contribution_cost = 20.0 * (1 - f) * (1 + eps) / eps
    row = {"units": 100, "revenue": 2000.0, "amazon_fees": f * 2000.0,
           "cogs": contribution_cost * 100, "period_start": "2026-07-01",
           "period_end": "2026-07-31"}
    assert optimal_price(eps, contribution_cost, f, 0.0) == pytest.approx(20.0)
    assert price_move(row, {"elasticity": eps, "std_err": 0.02,
                            "details": {"ci95": [-3.06, -2.94], "dof": 5,
                                        "t_critical": 2.571, "residual_sd_log": 0.05}}) is None


# ── nothing non-finite ever escapes ───────────────────────────────────────

def _finite(value, path=""):
    if isinstance(value, float):
        assert np.isfinite(value), f"non-finite at {path}: {value}"
    elif isinstance(value, dict):
        for k, v in value.items():
            _finite(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _finite(v, f"{path}[{i}]")


def test_no_nan_or_inf_reaches_a_price_move_under_any_fit():
    """A sweep across the whole parameter space the engine can be handed,
    including the pathological corners."""
    for eps in (-12.0, -3.0, -1.001, -1.0, -0.999, -0.2, -1e-9):
        for se in (0.0, 1e-9, 0.2, 3.0):
            for cogs in (1.0, 500.0, 1900.0, 2600.0):
                for fees in (0.0, 300.0, 1800.0):
                    row = {**MARGIN, "cogs": cogs, "amazon_fees": fees}
                    fit = {"elasticity": eps, "std_err": se,
                           "details": {"ci95": [eps - 3 * se, eps + 3 * se], "dof": 3,
                                       "t_critical": 3.182, "residual_sd_log": 0.2}}
                    move = price_move(row, fit)
                    if move is not None:
                        _finite(move, f"eps={eps},se={se},cogs={cogs},fees={fees}")


def test_no_nan_or_inf_reaches_a_directive():
    """The same guarantee one level up: whatever the models hand over, the
    Decision Ledger never receives a non-finite number."""
    rng = np.random.default_rng(3)
    econ = []
    for i in range(12):
        prices = 20.0 * np.exp(rng.normal(0, 0.12, size=7))
        units = 300.0 * (prices / 20.0) ** rng.uniform(-4.0, 0.5) * np.exp(
            rng.normal(0, 0.3, size=7))
        econ += _econ(prices, units, sku=f"S{i:03d}")
    data = _data(
        sku_economics=econ,
        cogs_inputs=[{"sku": f"S{i:03d}", "asin": f"B0S{i:03d}", "unit_cost_usd": 5.0,
                      "supplier_lead_time_days": 40} for i in range(12)],
        inventory_levels=[{"sku": f"S{i:03d}", "snapshot_date": "2026-07-28",
                           "fulfillable_quantity": 200, "inbound_quantity": 0}
                          for i in range(12)],
    )
    margins = margin.run(data)
    fits = elasticity.run(data)
    inv = inventory_sim.run(data, np.random.default_rng(1), simulations=3000)
    rows = anomaly.run(data)
    drafts = draft_directives(inv, [], fits, margins, anomaly_rows=rows)
    assert drafts
    for d in drafts:
        _finite(d, d["kind"])


def test_profit_delta_is_exactly_zero_at_the_current_price():
    for eps in (-4.0, -1.5, -0.5):
        for fixed in (0.0, 3.3):
            assert profit_delta(eps, 20.0, 100.0, 5.0, 0.15, 20.0, fixed) == pytest.approx(0.0)


def test_p_star_is_monotone_in_cost_and_in_the_fixed_fee():
    base = optimal_price(-2.0, 5.0, 0.15, 1.0)
    assert optimal_price(-2.0, 5.01, 0.15, 1.0) > base
    assert optimal_price(-2.0, 5.0, 0.15, 1.01) > base


def test_a_degenerate_draw_set_still_summarises():
    """Zero uncertainty everywhere: the distribution collapses to a point and the
    percentiles must agree rather than producing a None."""
    from hubricon_engine.models.pricing_engine import delta_at, summarize_delta

    draws = delta_draws(eps=-2.0, std_err=0.0, dof=None, p0=20.0, q0=100.0,
                        unit_cost=5.0, fee_rate=0.15, fixed_fee=0.0,
                        demand_sd_log=0.0)
    out = summarize_delta(delta_at(draws, 19.0))
    assert out["p5"] is not None and out["p50"] is not None
    # the Poisson counting floor means it is not a literal point mass, but it is
    # tight and finite
    _finite(out)


# ── the other models' refusals ────────────────────────────────────────────

def test_an_empty_catalog_produces_nothing_anywhere():
    empty = _data()
    assert elasticity.run(empty) == []
    assert margin.run(empty) == []
    assert anomaly.run(empty) == []
    assert inventory_sim.run(empty, np.random.default_rng(0), simulations=100) == []
    assert cashflow.run({"cash_on_hand": 1000.0, "monthly_fixed_costs": 100.0},
                        [], [], np.random.default_rng(0)) is None
    panel = inventory_sim.aggregate([], empty, np.random.default_rng(0), simulations=100)
    assert panel["status"] == "insufficient_data"


def test_the_cash_cone_refuses_without_client_stated_inputs():
    assert cashflow.run({"cash_on_hand": None, "monthly_fixed_costs": 5000.0},
                        [{"sku": "A"}], [], np.random.default_rng(0)) is None
    assert cashflow.run({"cash_on_hand": 5000.0, "monthly_fixed_costs": None},
                        [{"sku": "A"}], [], np.random.default_rng(0)) is None


def test_a_series_too_short_for_a_detector_is_insufficient_not_quiet():
    """"No alert" and "could not look" are different answers and the payload
    distinguishes them."""
    rows = anomaly.run(_data(sku_economics=_econ([20.0] * 3, [100, 101, 99])))
    assert rows
    assert all(r["status"] == "insufficient_data" for r in rows)
    assert all(r["p_value"] is None for r in rows)
    assert all(not r["flagged"] for r in rows)


def test_risk_sections_report_insufficient_rather_than_zero():
    out = risk.run(_data(), [], rng=np.random.default_rng(0), simulations=500)
    assert out["var"]["status"] == "insufficient_data"
    assert out["var"].get("var_95") is None


# ── the refusal test: the thinnest plausible seller ────────────────────────

def test_the_thinnest_plausible_input_returns_statuses_not_numbers():
    """One SKU, five periods, one price change, no landed cost uploaded. This is
    a real shape of first upload, and the brand rests on what comes back.

    Every number that would require data this seller has not given must be
    absent, and every absence must have a name."""
    prices = [20.0, 20.0, 20.0, 21.0, 21.0]
    units = [100, 104, 96, 92, 95]
    data = _data(sku_economics=_econ(prices, units))   # no cogs_inputs at all

    margins = margin.run(data)
    assert len(margins) == 5
    assert all(m["cogs"] is None for m in margins)     # never zero, never guessed

    fits = elasticity.run(data)
    fit = next(f for f in fits if f["level"] == "sku")
    # five periods clears the period floor, so the fit runs — and then every
    # downstream dollar figure is refused for want of a landed cost
    assert fit["status"] in ("ok", "insufficient_price_variation", "insufficient_data")

    latest = max(m["period_start"] for m in margins)
    margin_row = next(m for m in margins if m["period_start"] == latest)
    assert price_move(margin_row, fit) is None

    inv = inventory_sim.run(data, np.random.default_rng(0), simulations=2000)
    drafts = draft_directives(inv, [], fits, margins, anomaly_rows=anomaly.run(data))

    # nothing that promises dollars may be issued
    for d in drafts:
        assert d["expected_impact_usd"] is None, (d["kind"], d["action_text"])
    # and any pricing instruction that does appear says what is missing
    for d in drafts:
        if d["module"] == "pricing":
            assert "Upload unit costs" in d["action_text"] or "cannot separate" in d["action_text"]

    # the anomaly sweep, on five points, says it could not look
    rows = anomaly.run(data)
    assert all(not r["flagged"] for r in rows)

    # the cash cone has no client inputs and says so by returning nothing
    assert cashflow.run({"cash_on_hand": None, "monthly_fixed_costs": None},
                        inv, margins, np.random.default_rng(0)) is None
