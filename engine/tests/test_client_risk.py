"""The client's own risk tolerance and cash buffer, stated rather than assumed."""

import numpy as np
import pytest

from hubricon_engine import directives
from hubricon_engine.models import cash_orders, cashflow
from hubricon_engine.models.pricing_engine import RISK_BUDGET_SHARE, price_move

MARGIN = {"sku": "X", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 300, "revenue": 6000.0,
          "amazon_fees": 1350.0, "cogs": 1500.0, "net_margin": 3000.0}
FIT = {"level": "sku", "item_id": "X", "status": "ok", "elasticity": -2.2, "std_err": 0.35,
       "details": {"ci95": [-3.1, -1.3], "dof": 6, "t_critical": 2.447, "residual_sd_log": 0.2}}
INVENTORY = [{"sku": "X", "daily_velocity_mean": 10.0, "daily_velocity_std": 3.0, "lead_time_days": 30,
              "on_hand_units": 200, "inbound_units": 0, "reorder_qty": 300, "reorder_point": 320}]
CASH_MARGIN = [{**MARGIN, "ad_spend_allocated": 200.0}]


def test_a_stated_buffer_raises_the_ruin_probability_monotonically_and_the_default_is_zero():
    base = {"cash_on_hand": 3000.0, "monthly_fixed_costs": 2500.0}
    p = []
    for buffer in (0.0, 1000.0, 2500.0):
        out = cashflow.run({**base, "min_cash_buffer_usd": buffer}, INVENTORY, CASH_MARGIN,
                           np.random.default_rng(7), n_paths=1500)
        p.append(float(out["p_ruin"]))
        assert out["details"]["ruin_floor"] == buffer
    assert p[0] <= p[1] <= p[2] and p[2] > p[0]
    plain = cashflow.run(base, INVENTORY, CASH_MARGIN, np.random.default_rng(7), n_paths=1500)
    assert plain["p_ruin"] == p[0] and plain["details"]["ruin_floor"] == 0.0
    assert plain["details"]["ruin_floor_basis"].startswith("zero")
    # the order budget reads the same floor: a buffer shrinks what the cash supports
    cone = {**plain, "trough_p5": 600.0, "trough_expected_shortfall": 400.0}
    k0 = cash_orders.cash_budget(cone, [{"day": 2, "sku": "X", "amount": 1000.0}])
    k1 = cash_orders.cash_budget({**cone, "details": {**plain["details"], "ruin_floor": 1000.0}},
                                 [{"day": 2, "sku": "X", "amount": 1000.0}])
    assert k0["budget_p5"] == pytest.approx(1000.0) and k1["budget_p5"] == pytest.approx(600.0)


def test_a_lower_share_walks_a_shorter_step_and_the_default_reproduces_todays_numbers():
    default = price_move(MARGIN, FIT)
    same = price_move(MARGIN, FIT, risk_share=None)
    assert same == default and default["policy"]["risk_budget_share"] == RISK_BUDGET_SHARE
    assert default["policy"]["risk_budget_share_basis"] == "default"
    cautious = price_move(MARGIN, FIT, risk_share=0.05)
    bold = price_move(MARGIN, FIT, risk_share=0.30)
    assert cautious["policy"]["risk_budget_share_basis"] == "client"
    steps = [abs(m["step_fraction"]) if m else 0.0 for m in (cautious, default, bold)]
    assert steps[0] <= steps[1] <= steps[2]


def test_a_lower_share_demotes_more_drafts_to_an_explicit_yes():
    fit = {**FIT, "std_err": 0.6, "details": {**FIT["details"], "ci95": [-3.7, -0.7]}}
    loose = directives.draft_directives([], [], [fit], [MARGIN], risk_share=0.30)
    tight = directives.draft_directives([], [], [fit], [MARGIN], risk_share=0.05)
    steps_loose = [d for d in loose if d["kind"] == "price_step"]
    steps_tight = [d for d in tight if d["kind"] == "price_step"]
    if steps_loose and steps_tight:
        assert steps_tight[0]["evidence"]["downside_guard"]["share"] == 0.05
        assert steps_loose[0]["evidence"]["downside_guard"]["budget_usd"] > steps_tight[0]["evidence"]["downside_guard"]["budget_usd"]
        assert (steps_tight[0]["mandate"] == "explicit") >= (steps_loose[0]["mandate"] == "explicit")
    plain = directives.draft_directives([], [], [fit], [MARGIN])
    assert all(d["evidence"].get("downside_guard", {}).get("share", 0.15) == 0.15 for d in plain if d["kind"] == "price_step")
