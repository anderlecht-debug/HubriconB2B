"""Cash-flow horizon: mechanics, honesty guards, JSON safety."""

import json

import numpy as np
import pytest

from hubricon_engine.models import cashflow


def _inventory_row(sku="SKU-A", rate=10.0, std=2.0, position=9000, rop=0, qty=600, lead=30):
    return {"sku": sku, "daily_velocity_mean": rate, "daily_velocity_std": std,
            "on_hand_units": position, "inbound_units": 0, "reorder_point": rop,
            "reorder_qty": qty, "lead_time_days": lead}


def _margin_row(sku="SKU-A", units=300, revenue=9000.0, fees=2700.0, cogs=1800.0, ads=450.0):
    # p0 = $30, fee rate 0.30, unit cost $6, ad spend $15/day over a 30-day period
    return {"sku": sku, "period_start": "2026-07-01", "period_end": "2026-07-30",
            "units": units, "revenue": revenue, "amazon_fees": fees, "cogs": cogs,
            "ad_spend_allocated": ads}


def _client(balance=50_000.0, opex=3_000.0):
    return {"cash_on_hand": balance, "monthly_fixed_costs": opex}


def test_healthy_book_never_ruins():
    rng = np.random.default_rng(7)
    out = cashflow.run(_client(), [_inventory_row()], [_margin_row()], rng, n_paths=2000)
    assert out["p_ruin"] == 0.0
    assert out["horizon_days"] == 90 and len(out["details"]["p50"]) == 90
    for lo, mid, hi in zip(out["details"]["p5"], out["details"]["p50"], out["details"]["p95"]):
        assert lo <= mid <= hi


def test_wire_bigger_than_cash_is_certain_breach():
    # $3,600 wire leaves on day 0 against $2,000 in the bank — every path breaches
    inv = _inventory_row(position=300, rop=300, qty=600, rate=5.0)
    out = cashflow.run(_client(balance=2_000.0, opex=6_000.0), [inv], [_margin_row()],
                       np.random.default_rng(7), n_paths=500)
    assert out["p_ruin"] == 1.0
    assert out["min_p5"] < 0


def test_payout_lag_creates_the_day13_trough():
    # No wires, healthy margins: the deterministic low is the day before the
    # first 14-day payout lands, and the payout visibly lifts the median.
    out = cashflow.run(_client(balance=10_000.0, opex=3_000.0), [_inventory_row()],
                       [_margin_row()], np.random.default_rng(7), n_paths=1000)
    assert out["min_p5_day"] == 13
    assert out["min_median"] == pytest.approx(10_000 - 13 * 100, rel=0.01)
    p50 = out["details"]["p50"]
    assert p50[13] > p50[12]  # payday


def test_wire_schedule_cycles_and_requires_landed_cost():
    inv = [_inventory_row(position=900, rop=300, qty=600, rate=10.0),
           _inventory_row(sku="SKU-NOCOGS", position=100, rop=300, qty=400)]
    margins = [_margin_row(), _margin_row(sku="SKU-NOCOGS", cogs=None)]
    wires = cashflow.wire_schedule(inv, margins, horizon_days=90)
    # SKU-A: first wire at (900-300)/10 = day 60, cycle 60d -> exactly one in horizon
    assert wires == [{"day": 60, "sku": "SKU-A", "amount": 3600.0}]


def test_missing_inputs_or_data_returns_none():
    rng = np.random.default_rng(7)
    assert cashflow.run({"cash_on_hand": None, "monthly_fixed_costs": 3000},
                        [_inventory_row()], [_margin_row()], rng) is None
    assert cashflow.run(_client(), [], [], rng) is None


def test_payload_is_json_safe():
    out = cashflow.run(_client(), [_inventory_row()], [_margin_row()],
                       np.random.default_rng(7), n_paths=200)
    json.dumps(out)  # numpy types or NaN would raise


# --- the payout cycle is the platform's, not the model's ----------------------

def _shopify(balance=10_000.0, opex=3_000.0):
    return {"cash_on_hand": balance, "monthly_fixed_costs": opex, "platform": "shopify"}


def test_amazon_stays_the_default_and_states_its_assumption():
    out = cashflow.run(_client(balance=10_000.0), [_inventory_row()], [_margin_row()],
                       np.random.default_rng(7), n_paths=500)
    assert out["details"]["payout_cycle_days"] == 14
    assert out["details"]["payout_days"][:3] == [14, 28, 42]
    assert "14 days" in out["details"]["assumptions"][0]


def test_shopify_pays_out_daily_so_there_is_no_fortnightly_trough():
    """Shopify Payments settles every day: cash never waits thirteen days for
    its first disbursement, so the deterministic trough is gone."""
    amazon = cashflow.run(_client(balance=10_000.0), [_inventory_row()], [_margin_row()],
                          np.random.default_rng(7), n_paths=500)
    shopify = cashflow.run(_shopify(), [_inventory_row()], [_margin_row()],
                           np.random.default_rng(7), n_paths=500)
    assert shopify["details"]["payout_cycle_days"] == 1
    assert shopify["details"]["payout_days"][:3] == [1, 2, 3]
    assert shopify["min_p5_day"] == 1                      # day one is the low, not day 13
    assert shopify["min_median"] > amazon["min_median"]     # no cash held back
    assert shopify["details"]["assumptions"][0] == (
        "Shopify Payments pays out daily; the ~2 business-day lag is ignored at this horizon")


def test_an_explicit_channel_beats_the_clients_platform():
    """A client selling on both is run once per channel, so the caller states
    which one rather than letting the client record decide."""
    both = {"cash_on_hand": 10_000.0, "monthly_fixed_costs": 3_000.0, "platform": "both"}
    out = cashflow.run(both, [_inventory_row()], [_margin_row()], np.random.default_rng(7),
                       n_paths=200, channel="shopify")
    assert out["details"]["payout_cycle_days"] == 1
    # unstated, a two-platform client falls back to the Amazon default
    assert cashflow.run(both, [_inventory_row()], [_margin_row()], np.random.default_rng(7),
                        n_paths=200)["details"]["payout_cycle_days"] == 14


def test_simulate_takes_the_cycle_as_a_number():
    """The simulation itself stays channel-blind: it is handed a cadence and a
    sentence, never a platform."""
    params = cashflow.sku_cash_params([_inventory_row()], [_margin_row()])
    out = cashflow.simulate(params, [], 10_000.0, 3_000.0, np.random.default_rng(7),
                            horizon_days=30, n_paths=200, payout_cycle_days=7,
                            payout_note="weekly, per the contract")
    assert out["details"]["payout_days"] == [7, 14, 21, 28]
    assert out["details"]["assumptions"][0] == "weekly, per the contract"
