"""What would break you: five stresses on the cone's own paths, no new draws."""

import numpy as np
import pytest

from hubricon_engine.models import cashflow, stress

INVENTORY = [
    {"sku": "BIG", "daily_velocity_mean": 12.0, "daily_velocity_std": 3.0, "lead_time_days": 30, "on_hand_units": 400,
     "inbound_units": 0, "reorder_qty": 300, "reorder_point": 320, "days_of_cover": 33.0},
    {"sku": "SMALL", "daily_velocity_mean": 4.0, "daily_velocity_std": 1.0, "lead_time_days": 30, "on_hand_units": 400,
     "inbound_units": 0, "reorder_qty": 100, "reorder_point": 120, "days_of_cover": 100.0},
]
MARGINS = [
    {"sku": "BIG", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 336, "revenue": 6720.0,
     "amazon_fees": 1500.0, "cogs": 1680.0, "net_margin": 3000.0, "ad_spend_allocated": 300.0},
    {"sku": "SMALL", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 112, "revenue": 2240.0,
     "amazon_fees": 500.0, "cogs": 560.0, "net_margin": 1000.0, "ad_spend_allocated": 100.0},
]
CLIENT = {"cash_on_hand": 3000.0, "monthly_fixed_costs": 3500.0}


def _cone(cash=3000.0, seed=3, n_paths=2000):
    out = cashflow.run({**CLIENT, "cash_on_hand": cash}, INVENTORY, MARGINS, np.random.default_rng(seed),
                       n_paths=n_paths, keep_paths=True)
    paths = out.pop("_paths")
    return out, paths


def test_the_base_scenario_reproduces_the_cone_and_no_paths_means_no_stress():
    cone, paths = _cone()
    assert "_paths" not in cone
    plain = cashflow.run(CLIENT, INVENTORY, MARGINS, np.random.default_rng(3), n_paths=2000)
    assert "_paths" not in plain
    st = stress.run(paths, cone)
    assert st["status"] == "ok" and st["reproduces_cone"]
    assert st["base"]["p_ruin"] == cone["p_ruin"]
    assert st["base"]["trough_p5"] == pytest.approx(cone["trough_p5"], abs=0.01)
    assert stress.run(None, cone)["status"] == "no_cash_inputs"
    names = [r["name"] for r in st["scenarios"]]
    assert names[0] == "base" and {"fee_rise", "cpc_rise", "payout_hold", "top_sku_suppressed", "supplier_delay"} <= set(names)


def test_each_stress_moves_the_right_number_the_right_way():
    cone, paths = _cone()
    st = stress.run(paths, cone)
    by = {r["name"]: r for r in st["scenarios"]}
    # a fee rise costs that share of revenue paid through the last payout day
    revenue_paid = float(np.median(paths["revenue"][:, : paths["payout_days"][-1] + 1].sum(axis=1)))
    assert by["fee_rise"]["end_cash_delta_p50"] == pytest.approx(-stress.FEE_SHOCK_PP * revenue_paid, rel=0.15)
    # dearer clicks: ad spend up by the shock over the horizon
    ads_paid = paths["ad_daily_total"] * (paths["payout_days"][-1] + 1)
    assert by["cpc_rise"]["end_cash_delta_p50"] == pytest.approx(-stress.CPC_SHOCK * ads_paid, rel=0.05)
    # the biggest SKU silenced for a month: more ruin, deeper trough
    assert by["top_sku_suppressed"]["sku"] == "BIG"
    assert by["top_sku_suppressed"]["p_ruin"] >= by["base"]["p_ruin"]
    assert by["top_sku_suppressed"]["trough_p5"] < by["base"]["trough_p5"]
    # a late supplier hits the SKU whose cover runs out inside the horizon
    assert "BIG" in by["supplier_delay"]["skus"]
    assert by["supplier_delay"]["trough_p5"] <= by["base"]["trough_p5"]
    # a held payout: the same money later, so the trough is deeper
    assert by["payout_hold"]["trough_p5"] < by["base"]["trough_p5"]
    # the table is ranked by what raises ruin most
    deltas = [r["p_ruin_delta"] for r in st["scenarios"][1:]]
    assert deltas == sorted(deltas, reverse=True)
    assert st["worst"] == st["scenarios"][1]["name"]
