"""The ruin cost of one decision: what a wire does to the cone, read off the
paths it already simulated."""

import numpy as np
import pytest

from hubricon_engine import directives
from hubricon_engine.models import cashflow
from hubricon_engine.models.cashflow import ruin_delta, ruin_ladder

INVENTORY = [{"sku": "X", "daily_velocity_mean": 10.0, "daily_velocity_std": 3.0, "lead_time_days": 30,
              "on_hand_units": 200, "inbound_units": 0, "reorder_qty": 300, "reorder_point": 320}]
MARGINS = [{"sku": "X", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 300, "revenue": 6000.0,
            "amazon_fees": 1350.0, "cogs": 1500.0, "net_margin": 3000.0, "ad_spend_allocated": 200.0}]
CLIENT = {"cash_on_hand": 4000.0, "monthly_fixed_costs": 2500.0}


def test_the_ladder_prices_a_wire_the_way_a_second_simulation_would():
    cone = cashflow.run(CLIENT, INVENTORY, MARGINS, np.random.default_rng(3), n_paths=3000)
    # the same cone with an extra $2,000 wire on day 20, simulated outright
    wires = cone["details"]["wires"] + [{"day": 20, "sku": "X", "amount": 2000.0}]
    params = cashflow.sku_cash_params(INVENTORY, MARGINS)
    rerun = cashflow.simulate(params, wires, 4000.0, 2500.0, np.random.default_rng(3), n_paths=3000,
                              correlation=cone["details"]["demand_correlation"])
    rd = ruin_delta(cone, 20, 2000.0)
    assert rd["p_ruin_before"] == pytest.approx(cone["p_ruin"], abs=1e-6)
    assert rd["p_ruin_after"] == pytest.approx(rerun["p_ruin"], abs=3 * max(rd["mc_se"], 0.01) + 0.01)
    assert rd["p_ruin_after"] >= rd["p_ruin_before"]
    assert ruin_delta(cone, 20, 0.0)["p_ruin_after"] == pytest.approx(cone["p_ruin"], abs=1e-6)
    assert ruin_delta(cone, 5, 1e7)["p_ruin_after"] == pytest.approx(1.0, abs=1e-6)
    inflow = ruin_delta(cone, 10, -3000.0)
    assert inflow["p_ruin_after"] <= inflow["p_ruin_before"]
    assert ruin_delta(None, 1, 100.0) is None and ruin_delta({"details": {}}, 1, 100.0) is None


def test_the_ladder_is_exact_on_a_hand_built_matrix():
    # four path shapes, each repeated so the quantile grid has something to hold
    shapes = np.array([[100.0, 50.0, 80.0], [30.0, 60.0, 90.0], [200.0, 150.0, -10.0], [10.0, 20.0, 30.0]])
    cash = np.repeat(shapes, 250, axis=0)
    ladder = ruin_ladder(cash, floor=0.0)
    payload = {"details": {"ruin_ladder": ladder}}
    # before: one path in four (the third shape) dips under zero
    assert ruin_delta(payload, 0, 0.0)["p_ruin_before"] == pytest.approx(0.25, abs=0.02)
    # a $40 wire on day 1: minima from day 1 on are 50, 60, −10, 20 → under 40: the third and fourth
    assert ruin_delta(payload, 1, 40.0)["p_ruin_after"] == pytest.approx(0.5, abs=0.02)
    # a $95 wire on day 2: from day 2 on 80, 90, −10, 30 → all four under 95
    assert ruin_delta(payload, 2, 95.0)["p_ruin_after"] == pytest.approx(1.0, abs=0.02)


def test_a_wire_that_pushes_ruin_past_the_line_is_routed_to_an_explicit_yes():
    cone = cashflow.run({**CLIENT, "cash_on_hand": 9000.0}, INVENTORY, MARGINS, np.random.default_rng(3), n_paths=2000)
    assert cone["p_ruin"] < directives.RUIN_WARNING
    inv = [{**INVENTORY[0], "stockout_probability": 0.6}]
    margins = [{**MARGINS[0], "cogs": 1500.0}]
    drafts = directives.draft_directives(inv, [], [], margins, cash=cone)
    reorder = next(d for d in drafts if d["kind"] == "inventory_reorder")
    rd = reorder["evidence"]["ruin_delta"]
    assert rd["p_ruin_before"] == pytest.approx(cone["p_ruin"], abs=1e-6) and rd["amount"] == reorder["evidence"]["wire_usd"]
    # the same reorder, priced at ten times the landed cost: the wire alone sinks the account
    big = directives.draft_directives(inv, [], [], [{**MARGINS[0], "cogs": 60000.0}], cash=cone)
    r2 = next(d for d in big if d["kind"] == "inventory_reorder")
    assert r2["evidence"]["ruin_delta"]["p_ruin_after"] > directives.RUIN_WARNING
    assert r2["mandate"] == "explicit" and "past the 5% line" in r2["mandate_reason"]
    # no cone: nothing attached, nothing invented
    plain = directives.draft_directives(inv, [], [], margins)
    assert "ruin_delta" not in next(d for d in plain if d["kind"] == "inventory_reorder")["evidence"]
