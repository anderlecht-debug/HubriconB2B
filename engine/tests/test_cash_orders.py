"""The order set the cash supports: the newsvendor with a budget constraint."""

from datetime import date

import numpy as np
import pytest

from hubricon_engine import directives
from hubricon_engine.models import cash_orders, inventory_econ as econ
from hubricon_engine.models.cash_orders import cash_budget, funded_orders, funded_set

TODAY = date(2026, 9, 1)


def _row(sku, c_u, c_o, unit_cost, position, mean=100.0, sd=20.0, seed=0):
    rng = np.random.default_rng(seed)
    demand = rng.normal(mean, sd, 20000).clip(0)
    ladder_q = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.975, 0.99, 0.995]
    q = min(econ.FRACTILE_CEIL, max(econ.FRACTILE_FLOOR, c_u / (c_u + c_o)))
    return {"sku": sku, "status": "ok", "c_u": c_u, "c_o": c_o, "unit_cost": unit_cost, "position": position,
            "critical_fractile": q, "order_up_to": int(np.ceil(np.quantile(demand, q))),
            "order_qty_econ": max(0, int(np.ceil(np.quantile(demand, q))) - position),
            "details": {"demand_ladder": [[x, float(np.quantile(demand, x))] for x in ladder_q]}}


def test_a_zero_shadow_price_reproduces_the_newsvendor():
    rows = [_row("A", 15.0, 1.0, 5.0, 40), _row("B", 4.0, 1.5, 8.0, 30, seed=1)]
    free = funded_orders(rows, 0.0)
    for o, r in zip(free, rows):
        assert o["fractile"] == pytest.approx(r["critical_fractile"], abs=1e-9)
        assert abs(o["order_qty"] - r["order_qty_econ"]) <= 2      # the ladder interpolates between its rungs
        assert o["p_stockout_cycle"] == pytest.approx(1 - r["critical_fractile"], abs=1e-4)


def test_capital_goes_first_to_contribution_at_risk_per_dollar_and_the_total_wire_is_monotone():
    high = _row("HIGH", 15.0, 1.0, 5.0, 40)      # $3.00 of contribution at risk per dollar
    low = _row("LOW", 4.0, 1.5, 8.0, 30, seed=1)  # $0.50
    rows = [high, low]
    free_total = sum(o["wire"] for o in funded_orders(rows, 0.0))
    fs = funded_set(rows, 0.6 * free_total)
    assert fs["status"] == "constrained" and fs["lambda"] > 0
    assert float(fs["wire_total"]) <= 0.6 * free_total + 1e-6
    by = {o["sku"]: o for o in fs["orders"]}
    # the high-return SKU keeps more of its service level than the low one
    assert (by["HIGH"]["fractile"] / high["critical_fractile"]) > (by["LOW"]["fractile"] / low["critical_fractile"])
    assert fs["orders"][0]["sku"] == "HIGH"
    totals = [sum(o["wire"] for o in funded_orders(rows, lam)) for lam in (0.0, 0.2, 0.5, 1.0, 2.0)]
    assert all(a >= b for a, b in zip(totals, totals[1:]))


def test_refusals_and_the_budget_read_off_the_cone():
    rows = [_row("A", 15.0, 1.0, 5.0, 40)]
    assert cash_orders.run({"rows": rows}, None)["status"] == "no_cash_inputs"
    planned = funded_orders(rows, 0.0)[0]["wire"]
    cone = {"trough_p5": 500.0, "trough_expected_shortfall": 200.0, "p_ruin": 0.01,
            "details": {"wires": [{"day": 3, "sku": "A", "amount": planned}]}}
    k = cash_budget(cone, None)
    assert k["budget_p5"] == pytest.approx(planned) and k["budget_expected_shortfall"] == pytest.approx(planned)
    assert cash_orders.run({"rows": rows}, cone)["status"] == "fully_funded"
    short = {**cone, "trough_p5": -0.4 * planned, "trough_expected_shortfall": -0.6 * planned}
    out = cash_orders.run({"rows": rows}, short)
    assert out["status"] == "constrained"
    assert float(out["wire_total"]) <= 0.6 * planned + 1e-6
    assert out["bridge_capital"] == pytest.approx(0.4 * planned, abs=0.01)
    assert "contribution at risk per inventory dollar" in out["basis"]


def test_the_directive_replaces_the_individual_reorders_for_the_funded_skus():
    rows = [_row("A", 15.0, 1.0, 5.0, 40), _row("B", 4.0, 1.5, 8.0, 30, seed=1)]
    free_total = sum(o["wire"] for o in funded_orders(rows, 0.0))
    cone = {"trough_p5": -0.5 * free_total, "trough_expected_shortfall": -0.6 * free_total, "p_ruin": 0.1,
            "details": {"wires": [{"day": 3, "sku": o["sku"], "amount": o["wire"]} for o in funded_orders(rows, 0.0)]}}
    co = cash_orders.run({"rows": rows}, cone)
    inv = [{"sku": s, "stockout_probability": 0.6, "reorder_qty": 100, "reorder_point": 90, "lead_time_days": 30,
            "daily_velocity_mean": 3.0, "on_hand_units": 40, "inbound_units": 0} for s in ("A", "B")]
    margins = [{"sku": s, "period_start": "2026-08-01", "units": 90, "revenue": 2700.0, "amazon_fees": 810.0,
                "cogs": 450.0, "net_margin": 1340.0} for s in ("A", "B")]
    drafts = directives.draft_directives(inv, [], [], margins, inv_econ={"rows": rows}, cash_orders=co)
    kinds = [d["kind"] for d in drafts]
    assert kinds.count("budget_order_set") == 1 and "inventory_reorder" not in kinds
    d = next(x for x in drafts if x["kind"] == "budget_order_set")
    assert d["mandate"] == "explicit" and d["expected_impact_usd"] is None
    assert "Your cash supports" in d["action_text"] and "Bridge capital of" in d["action_text"]
    assert "Fund these first" in d["action_text"] and d["evidence"]["lambda"] > 0
    from hubricon_engine.measurement import UNBANKABLE_KINDS
    assert "budget_order_set" in UNBANKABLE_KINDS
    # fully funded: the individual reorders stand
    drafts = directives.draft_directives(inv, [], [], margins, inv_econ={"rows": rows},
                                         cash_orders={"status": "fully_funded"})
    assert [d["kind"] for d in drafts].count("inventory_reorder") == 2
