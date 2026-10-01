"""Cash-flow horizon: mechanics, honesty guards, JSON safety."""

import json

import numpy as np
import pytest

from hubricon_engine import channels
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
    # first 14-day transfer lands, and the transfer visibly lifts the median.
    # Corrected 2026-10-01, deliberately: the low is still day 13 (the last
    # transfer is assumed to have landed today), but $195 deeper — the $15 a
    # day of ads leaves cash the day it is spent instead of riding inside the
    # payout (13 × $115, not 13 × $100). The day-14 transfer now carries the 14
    # days of sales Amazon already held; days 1–14 land on day 28.
    out = cashflow.run(_client(balance=10_000.0, opex=3_000.0), [_inventory_row()],
                       [_margin_row()], np.random.default_rng(7), n_paths=1000)
    assert out["min_p5_day"] == 13
    assert out["min_median"] == pytest.approx(10_000 - 13 * (100 + 15), rel=0.001)
    p50 = out["details"]["p50"]
    assert p50[13] > p50[12]  # payday
    # nothing lands between the transfers: day 14 to day 27 falls $115 a day
    assert p50[26] == pytest.approx(p50[13] - 13 * 115, abs=0.01)
    assert out["details"]["payout_days"][:2] == [14, 28]
    assert out["details"]["settlement_days"][:2] == [10, 24]


def test_a_sale_reaches_the_bank_only_after_the_reserve_and_the_transfer():
    """One $100 sale on day 1. Amazon (payable 10 days on, settled every 14
    days, 4 days to the bank) pays it on day 28, not day 14: the day-24
    settlement is the first that can carry it. Shopify pays it on day 5."""
    sales = np.zeros((1, 40))
    sales[0, 0] = 100.0
    amazon = cashflow.landed(sales, np.zeros(14), list(range(13, 40, 14)), 10, 4)
    assert amazon[0, 26] == 0.0 and amazon[0, 27] == 100.0       # day 27, day 28
    shopify = cashflow.landed(sales, np.zeros(4), list(range(0, 40)), 4, 0)
    assert shopify[0, 3] == 0.0 and shopify[0, 4] == 100.0       # day 4, day 5
    # the balance held on day one is paid first: $50 a day for the 14 days before today
    held = cashflow.landed(np.zeros((1, 40)), np.full(14, 50.0), list(range(13, 40, 14)), 10, 4)
    assert held[0, 12] == 0.0 and held[0, 13] == 700.0 and held[0, 39] == 700.0


def test_amazons_dd7_example_sets_which_settlement_carries_a_sale():
    """Amazon's own example: sold January 1 (day 1), delivered January 6,
    available January 14. A settlement on January 13 cannot carry it; one on
    January 14 does, and with the 4-day transfer it is in the bank January 18."""
    from datetime import date, timedelta

    from hubricon_engine import channels
    reserve = channels.payout_reserve_days("amazon", delivery_days=5)
    sales = np.zeros((1, 30))
    sales[0, 0] = 100.0                                            # day 1 = January 1
    on_13 = cashflow.landed(sales, np.zeros(0), [12], reserve, 0)   # settled and landed January 13
    on_14 = cashflow.landed(sales, np.zeros(0), [13], reserve, 0)   # January 14
    assert on_13[0, -1] == 0.0 and on_14[0, -1] == 100.0
    banked = cashflow.landed(sales, np.zeros(0), [17], reserve, channels.payout_transit_days("amazon"))
    assert banked[0, 16] == 0.0 and banked[0, 17] == 100.0
    assert date(2025, 12, 31) + timedelta(days=18) == date(2026, 1, 18)


def test_ad_spend_is_charged_the_day_it_is_spent():
    """Ads leave cash daily, before any payout: the same draws with and without
    $15 a day of ads differ by exactly $15 × the day, from day one."""
    with_ads = cashflow.sku_cash_params([_inventory_row()], [_margin_row()])
    no_ads = [{**p, "ad_daily": 0.0} for p in with_ads]
    a = cashflow.simulate(with_ads, [], 10_000.0, 3_000.0, np.random.default_rng(3), horizon_days=40, n_paths=300)
    b = cashflow.simulate(no_ads, [], 10_000.0, 3_000.0, np.random.default_rng(3), horizon_days=40, n_paths=300)
    gap = np.array(b["details"]["p50"]) - np.array(a["details"]["p50"])
    assert gap == pytest.approx(15.0 * np.arange(1, 41), abs=0.02)
    assert any("Ad spend leaves your cash the day it is spent" in s for s in a["details"]["assumptions"])


def test_the_balance_amazon_already_holds_is_paid_and_said():
    """A going concern does not start at zero with Amazon: the last 14 days of
    sales are held, and the first transfer pays them. At $210 a day net of
    fees that is about $2,940, the same in expectation as the old cone's first
    payout — the timing of everything after it is what moved."""
    out = cashflow.run(_client(balance=10_000.0), [_inventory_row()], [_margin_row()],
                       np.random.default_rng(7), n_paths=2000)
    d = out["details"]
    assert d["held_at_start_p50"] == pytest.approx(14 * 210, rel=0.05)
    assert d["p50"][13] - d["p50"][12] == pytest.approx(14 * 210 - 115, rel=0.05)
    # on day 90 Amazon still holds days 71–90: the day-84 transfer carried sales to day 70
    assert d["held_at_end_p50"] == pytest.approx(20 * 210, rel=0.08)
    assert any("already holds your last 14 days of sales" in s for s in d["assumptions"])


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
    assert (out["details"]["payout_reserve_days"], out["details"]["payout_transit_days"]) == (10, 4)
    assert "14 days" in out["details"]["assumptions"][0]
    assert "DD+7" in out["details"]["assumptions"][0]


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
    assert shopify["details"]["assumptions"][0] == channels.payout_note("shopify")
    assert "4 days later" in shopify["details"]["assumptions"][0]
    assert (shopify["details"]["payout_reserve_days"], shopify["details"]["payout_transit_days"]) == (4, 0)
    # four days of sales are held at the start, and each day's sales land four days on
    assert shopify["details"]["held_at_start_p50"] == pytest.approx(4 * 210, rel=0.1)


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
