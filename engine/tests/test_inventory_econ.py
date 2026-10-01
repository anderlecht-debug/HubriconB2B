from datetime import date

import numpy as np
import pytest

from hubricon_engine.models import fee_schedule as fees
from hubricon_engine.models import inventory_econ as econ

TODAY = date(2026, 9, 1)


def test_fee_schedule_steps():
    assert fees.aged_surcharge_rate(100) == 0.0
    assert fees.aged_surcharge_rate(181) == 0.50
    assert fees.aged_surcharge_rate(280) == 5.45
    assert fees.aged_surcharge_rate(400) == 6.90
    assert fees.storage_rate(11) == 2.40 and fees.storage_rate(3) == 0.78
    assert fees.low_inventory_fee(35) == 0.0
    assert fees.low_inventory_fee(10) == 0.89 and fees.low_inventory_fee(25) == 0.32
    assert fees.months_until_peak(date(2026, 7, 1)) == 3 and fees.months_until_peak(date(2026, 11, 1)) == 0


def test_critical_fractile_rises_with_margin_and_is_bounded():
    thin = econ.critical_fractile(unit_margin=0.5, unit_cost=8.0, item_volume=0.1, cycle_days=52, month=9)
    fat = econ.critical_fractile(unit_margin=15.0, unit_cost=8.0, item_volume=0.1, cycle_days=52, month=9)
    assert thin["q"] < fat["q"] <= econ.FRACTILE_CEIL
    assert fat["c_u"] == pytest.approx(15.0 + 0.89)
    assert set(thin["c_o_parts"]) == {"storage", "capital", "obsolescence"}
    peak = econ.critical_fractile(15.0, 8.0, 0.1, 52, month=11)
    assert peak["c_o"] > fat["c_o"]  # Oct–Dec storage is dearer, so hold less


def test_demand_over_cycle_matches_rate_times_horizon_and_is_lognormal():
    rng = np.random.default_rng(1)
    d = econ.demand_over_cycle(mean_rate=4.0, std_rate=0.4, lead_days=30, rng=rng, simulations=40000)
    assert d.mean() == pytest.approx(4.0 * (30 + econ.REVIEW_PERIOD_DAYS), rel=0.05)
    # a volatile rate: the clipped normal it used to draw had no skew and a
    # mean above the one it was given; the lognormal keeps the mean and skews
    wide = econ.demand_over_cycle(mean_rate=2.0, std_rate=2.0, lead_days=30, rng=rng, simulations=40000)
    assert wide.mean() == pytest.approx(2.0 * 37, rel=0.05)
    assert float(((wide - wide.mean()) ** 3).mean()) > 0


def test_hold_vs_liquidate_flips_with_carry_and_velocity_on_cash_contribution():
    """Landed cost is sunk for units on hand, so the rule compares cash
    contribution against liquidation recovery (corrected 2026-09-23)."""
    slow = econ.hold_vs_liquidate(excess_units=500, mean_rate=0.5, contribution=15.5, price=20.0,
                                  item_volume=0.4, start_age_days=200, today=TODAY)
    assert slow["decision"] == "liquidate"
    assert slow["liquidate_value"] == pytest.approx(500 * 20 * 0.10, rel=0.02)
    fast = econ.hold_vs_liquidate(excess_units=500, mean_rate=10.0, contribution=15.5, price=20.0,
                                  item_volume=0.05, start_age_days=60, today=TODAY)
    assert fast["decision"] == "hold" and fast["hold_npv"] > fast["liquidate_value"]
    # the regression: a thin-margin SKU the old rule sent to liquidation. At
    # $20 with $16 landed, the old hold value was $1/unit against $2 recovered;
    # the cash the seller actually keeps by selling is $15.50 a unit.
    thin = econ.hold_vs_liquidate(excess_units=300, mean_rate=5.0, contribution=15.5, price=20.0,
                                  item_volume=0.05, start_age_days=60, today=TODAY)
    assert thin["decision"] == "hold" and thin["hold_npv"] > 4 * thin["liquidate_value"]
    assert "landed cost sunk" in thin["basis"]


def _inventory(sku, on_hand, inbound=0, rate=3.0, sd=0.5, lead=30, reorder_qty=180):
    return {"sku": sku, "daily_velocity_mean": rate, "daily_velocity_std": sd, "lead_time_days": lead,
            "on_hand_units": on_hand, "inbound_units": inbound, "reorder_qty": reorder_qty}


def _margin(sku, units=90, revenue=2700.0, fees_=810.0, cogs=450.0):
    return {"sku": sku, "period_start": "2026-08-01", "period_end": "2026-08-31", "units": units,
            "revenue": revenue, "amazon_fees": fees_, "cogs": cogs, "ad_spend_allocated": 100.0, "net_margin": 1340.0}


def test_run_prices_fee_cliffs_and_sizes_the_economic_order():
    health = [{"snapshot_date": "2026-08-30", "sku": "A", "available": 40, "item_volume": 0.1,
               "inv_age_181_to_270": 20, "inv_age_271_to_365": 0, "inv_age_365_plus": 0,
               "estimated_excess_quantity": 0}]
    data = {"inventory_health": health}
    out = econ.run(data, [_inventory("A", on_hand=40), _inventory("B", on_hand=900, inbound=0)],
                   margin_rows=[_margin("A"), _margin("B")], rng=np.random.default_rng(3),
                   simulations=20000, today=TODAY)
    assert out["status"] == "ok"
    a = next(r for r in out["rows"] if r["sku"] == "A")
    b = next(r for r in out["rows"] if r["sku"] == "B")
    # A: 40 on hand at 3/day = 13 days → low-inventory fee applies at the <14-day rate
    assert a["low_inventory_fee_risk"] is True
    assert a["low_inventory_fee_month"] == pytest.approx(0.89 * 3 * 30, rel=1e-3)
    # aged surcharge from the 181–270 bucket at the schedule rate
    assert a["aged_units_181_plus"] == 20
    assert a["aged_surcharge_month"] == pytest.approx(20 * 0.1 * fees.aged_surcharge_rate(225), rel=1e-3)  # 225-day midpoint → $1.00 tier
    assert "schedule" in a["aged_surcharge_basis"]
    # economic order: high-margin SKU → high fractile, order-up-to covers the cycle
    assert a["critical_fractile"] > 0.9
    assert a["order_up_to"] > a["position"] and a["order_qty_econ"] == a["order_up_to"] - a["position"]
    assert a["wire_econ"] == pytest.approx(a["order_qty_econ"] * 5.0, rel=1e-3)
    # B: deep stock → no low-inventory fee, excess flagged, decision present, no order
    assert b["low_inventory_fee_risk"] is False and b["order_qty_econ"] == 0
    assert b["excess_units"] > 0 and b["decision"] in ("hold", "liquidate")
    assert b["volume_assumed"] is True
    s = out["summary"]
    assert s["bleed"]["total_month"] == pytest.approx(
        s["bleed"]["low_inventory_fee_month"] + s["bleed"]["aged_surcharge_month"] + s["bleed"]["peak_storage_premium_month"])
    assert s["econ_orders"][0]["sku"] == "A"


def test_amazon_estimates_override_the_schedule():
    health = [{"snapshot_date": "2026-08-30", "sku": "A", "available": 40, "item_volume": 0.1,
               "inv_age_181_to_270": 20, "estimated_aged_surcharge": 7.25,
               "estimated_storage_cost_next_month": 3.10, "low_inventory_level_fee_applied": True}]
    out = econ.run({"inventory_health": health}, [_inventory("A", on_hand=40)], margin_rows=[_margin("A")],
                   rng=np.random.default_rng(0), simulations=5000, today=TODAY)
    a = out["rows"][0]
    assert a["aged_surcharge_month"] == 7.25 and "Amazon" in a["aged_surcharge_basis"]
    assert a["storage_next_month"] == 3.10 and a["low_inventory_fee_applied_per_amazon"] is True


def test_no_unit_economics_still_prices_fees_but_skips_the_newsvendor():
    out = econ.run({}, [_inventory("A", on_hand=10)], margin_rows=[], rng=np.random.default_rng(0),
                   simulations=2000, today=TODAY)
    a = out["rows"][0]
    assert a["status"] == "no_unit_economics" and "order_qty_econ" not in a
    assert a["low_inventory_fee_risk"] is True


def test_forecast_rate_takes_precedence_over_observed():
    fc = [{"item_id": "A", "status": "ok", "method": "ses", "daily_rate_point": 6.0, "details": {"error_sd": 0.7}}]
    out = econ.run({}, [_inventory("A", on_hand=100)], margin_rows=[_margin("A")], forecast_rows=fc,
                   rng=np.random.default_rng(0), simulations=2000, today=TODAY)
    assert out["rows"][0]["rate_mean"] == 6.0 and out["rows"][0]["rate_source"].startswith("forecast")


def test_empty_inventory_is_insufficient():
    assert econ.run({}, [], today=TODAY)["status"] == "insufficient_data"


# --- a store with no marketplace warehouse ------------------------------------

def test_critical_fractile_without_fee_cliffs_is_margin_vs_capital_and_obsolescence():
    """No marketplace storage in C_o, no low-inventory fee in C_u — the plain
    newsvendor, which is the one a self-fulfilled store actually faces."""
    cliffless = econ.critical_fractile(unit_margin=16.0, unit_cost=5.0, item_volume=0.1,
                                       cycle_days=37, month=11, fee_cliffs=False)
    assert cliffless["c_u"] == pytest.approx(16.0)
    assert cliffless["c_u_parts"]["low_inventory_fee"] == 0.0
    assert cliffless["c_o_parts"]["storage"] == 0.0
    assert cliffless["c_o"] == pytest.approx(5.0 * 0.12 * 37 / 365 + 5.0 * 0.02)
    # peak season is Amazon's, so November costs a Shopify store nothing extra
    off_peak = econ.critical_fractile(16.0, 5.0, 0.1, 37, month=3, fee_cliffs=False)
    assert off_peak["c_o"] == pytest.approx(cliffless["c_o"])


def test_hold_value_without_fee_cliffs_carries_nothing():
    """Charging Amazon's storage and aged surcharge to a self-fulfilled brand
    would push it to dump stock it should keep."""
    kw = dict(excess_units=500, mean_rate=1.0, contribution=9.0, price=20.0,
              item_volume=0.4, start_age_days=200, today=TODAY)
    amazon = econ.hold_vs_liquidate(**kw)
    shopify = econ.hold_vs_liquidate(**kw, fee_cliffs=False)
    assert shopify["hold_npv"] > amazon["hold_npv"]
    assert shopify["liquidate_value"] == amazon["liquidate_value"]   # 10% of ASP either way


def test_shopify_run_zeroes_the_cliffs_and_still_prices_the_order():
    inv = [_inventory("A", on_hand=40)]
    out = econ.run({"inventory_health": []}, inv, [_margin("A")], None,
                   np.random.default_rng(3), 4000, TODAY, channel="shopify")
    assert out["status"] == "ok" and out["summary"]["channel"] == "shopify"
    row = out["rows"][0]

    # the three Amazon step functions are zero, and say why rather than estimating
    assert row["low_inventory_fee_risk"] is False
    assert row["low_inventory_fee_month"] == 0.0
    assert row["aged_surcharge_month"] == 0.0 and row["aged_units_181_plus"] == 0
    assert row["storage_next_month"] == 0.0
    assert row["peak_storage_premium_month"] == 0.0
    assert row["aged_surcharge_basis"] == econ.NO_CLIFF_BASIS
    assert row["storage_basis"] == econ.NO_CLIFF_BASIS
    assert out["summary"]["bleed"]["total_month"] == 0.0
    assert out["summary"]["fee_schedule_effective"] is None

    # the newsvendor still runs: $30 price, 30% fees, $5 landed -> $16 unit margin
    assert row["c_u"] == 16.0
    assert row["c_u_parts"] == {"margin": 16.0, "low_inventory_fee": 0.0}
    assert row["c_o_parts"] == {"storage": 0.0, "capital": 0.06, "obsolescence": 0.1}
    assert row["order_up_to"] > 0 and row["critical_fractile"] > 0.5
    assert row["details"]["basis"].startswith("Shopify:")
    assert econ.NO_CLIFF_BASIS in row["details"]["basis"]


def test_amazon_run_is_unchanged_by_the_channel_default():
    health = [{"snapshot_date": "2026-08-30", "sku": "A", "available": 40, "item_volume": 0.1,
               "inv_age_181_to_270": 20, "inv_age_271_to_365": 0, "inv_age_365_plus": 0}]
    inv = [_inventory("A", on_hand=40)]
    default = econ.run({"inventory_health": health}, inv, [_margin("A")], None,
                       np.random.default_rng(3), 4000, TODAY)
    named = econ.run({"inventory_health": health}, inv, [_margin("A")], None,
                     np.random.default_rng(3), 4000, TODAY, channel="amazon")
    assert default["rows"][0]["c_u"] == named["rows"][0]["c_u"]
    assert default["summary"]["bleed"] == named["summary"]["bleed"]
    assert default["rows"][0]["low_inventory_fee_month"] > 0   # 40 units at 3/day is thin cover
    assert named["rows"][0]["details"]["basis"].startswith("Amazon:")


# ── the low-inventory-level fee by size tier, on Amazon's 30/90-day rule (2026-10-01) ──

def test_the_schedule_has_five_tiers_and_the_two_storage_classes_map_to_rows():
    assert fees.LOW_INVENTORY_FEE_PER_UNIT["large_standard_3lb"] == {"lt14": 0.97, "14to21": 0.70, "21to28": 0.36}
    assert fees.LOW_INVENTORY_FEE_PER_UNIT["large_standard_20lb"] == {"lt14": 1.11, "14to21": 0.87, "21to28": 0.47}
    assert fees.LOW_INVENTORY_FEE_PER_UNIT["small_bulky"] == {"lt14": 1.85, "14to21": 1.02, "21to28": 0.51}
    assert fees.LOW_INVENTORY_FEE_PER_UNIT["large_bulky"] == {"lt14": 2.09, "14to21": 1.15, "21to28": 0.57}
    # "standard" with no finer tier is the lowest standard row, so never overstated
    assert fees.low_inventory_fee(10, "standard") == fees.low_inventory_fee(10, "small_standard") == 0.89
    # "oversize" with no finer tier is the lowest bulky row, for the same reason
    assert fees.low_inventory_fee(15, "oversize") == fees.low_inventory_fee(15, "small_bulky") == 1.02
    assert fees.low_inventory_fee(10, None) == 0.0, "a tier with no row is not priced"
    assert fees.low_inventory_band_days(12.0, 30.0) == 30.0 and fees.low_inventory_band_days(None, 9.0) == 9.0
    assert fees.low_inventory_band_days(None, None) is None and fees.low_inventory_fee(None) == 0.0


@pytest.mark.parametrize("label, weight, tier, says", [
    ("Small standard", None, "small_standard", "from your export"),
    ("Large standard", 0.82, "large_standard_3lb", "from your export"),
    ("Large standard", 3.0, "large_standard_3lb", "from your export"),
    ("Large standard", 7.5, "large_standard_20lb", "from your export"),
    ("Large standard", None, "large_standard_3lb", "weight not on file"),
    ("Small Bulky", None, "small_bulky", "least certain"),
    ("Large bulky", None, "large_bulky", "least certain"),
    ("Standard-Size", None, "small_standard", "size tier assumed (small standard)"),
    (None, None, "small_standard", "size tier assumed (small standard)"),
    ("Oversize", None, "small_bulky", "assumed"),   # the lowest bulky row: an assumed tier never overstates
    ("Extra-large 50+ to 70 lb", None, None, "not priced"),
])
def test_a_size_tier_as_an_export_names_it_finds_its_row(label, weight, tier, says):
    got, basis = fees.low_inventory_tier(label, weight)
    assert got == tier and says in basis


def _health(sku="L", available=60, t7=40, t30=150, t90=450, **extra):
    return {"snapshot_date": "2026-08-30", "sku": sku, "available": available, "item_volume": 0.1,
            "units_shipped_t7": t7, "units_shipped_t30": t30, "units_shipped_t90": t90, **extra}


def _lilf_row(health, on_hand=60, rate=5.0):
    out = econ.run({"inventory_health": [health]}, [_inventory(health["sku"], on_hand=on_hand, rate=rate)],
                   margin_rows=[_margin(health["sku"])], rng=np.random.default_rng(0), simulations=2000, today=TODAY)
    return out["rows"][0]


def test_a_large_standard_sku_is_priced_on_its_own_row_and_says_so():
    """60 on hand, 150 shipped in 30 days and 450 in 90 (5 a day): 12 days of
    supply on both, under 14. A large-standard item of 0.82 lb pays $0.97 a
    unit, not the small-standard $0.89: $145.50 a month at 5 a day."""
    raw = {"product-size-tier": "Large standard", "item-package-weight": "0.82", "unit-of-weight": "pounds"}
    row = _lilf_row(_health(raw=raw))
    assert row["fee_size_tier"] == "large_standard_3lb"
    assert row["low_inventory_fee_rate"] == 0.97
    assert row["low_inventory_fee_month"] == pytest.approx(0.97 * 5 * 30)
    assert row["low_inventory_days_of_supply"]["t30"] == 12.0 and row["low_inventory_days_of_supply"]["t90"] == 12.0
    assert "large standard, up to 3 lb" in row["low_inventory_fee_basis"]
    # the newsvendor's C_u carries the same tier at its under-14-days rate
    assert row["c_u_parts"]["low_inventory_fee"] == 0.97
    # the same SKU with no tier on file: the lowest standard row, labelled as assumed
    plain = _lilf_row(_health())
    assert plain["low_inventory_fee_month"] == pytest.approx(0.89 * 5 * 30)
    assert plain["fee_size_tier_basis"] == "size tier assumed (small standard)"
    assert "size tier assumed (small standard)" in plain["low_inventory_fee_basis"]
    # in ounces, 56 oz is 3.5 lb: the 3-20 lb row
    heavy = _lilf_row(_health(raw={**raw, "item-package-weight": "56", "unit-of-weight": "ounces"}))
    assert heavy["fee_size_tier"] == "large_standard_20lb" and heavy["low_inventory_fee_rate"] == 1.11


def test_the_fee_needs_both_the_30_and_90_day_supply_under_28_and_the_higher_sets_the_band():
    # a fortnight's dip: 30-day supply 12 days, but the 90-day supply 40 days -> no fee
    dip = _lilf_row(_health(t30=150, t90=135))
    assert dip["low_inventory_days_of_supply"]["t30"] == 12.0 and dip["low_inventory_days_of_supply"]["t90"] == 40.0
    assert dip["low_inventory_fee_risk"] is False and dip["low_inventory_fee_month"] == 0.0
    # both under 28: 30-day 12 days, 90-day 18 days -> the 14-21 band, not under-14
    both = _lilf_row(_health(t30=150, t90=300))
    assert both["low_inventory_days_of_supply"]["band"] == 18.0
    assert both["low_inventory_fee_rate"] == 0.63


def test_amazons_own_historical_days_of_supply_win_when_the_export_has_them():
    raw = {"short-term-historical-days-of-supply": "20", "long-term-historical-days-of-supply": "25"}
    row = _lilf_row(_health(raw=raw))           # the shipping pace alone would say 12 days
    assert row["low_inventory_days_of_supply"] == {"t30": 20.0, "t90": 25.0, "band": 25.0,
                                                   "source": "Amazon's own 30- and 90-day historical days of supply"}
    assert row["low_inventory_fee_rate"] == 0.32


def test_the_exemptions_an_export_shows_are_applied_and_the_rest_are_named():
    slow_week = _lilf_row(_health(t7=12))
    assert slow_week["low_inventory_fee_month"] == 0.0 and slow_week["low_inventory_fee_risk"] is False
    assert "12 units shipped in the past 7 days, under 20" in slow_week["low_inventory_fee_exempt"]
    flagged = _lilf_row(_health(raw={"exempted-from-low-inventory-level-fee": "Yes"}))
    assert flagged["low_inventory_fee_month"] == 0.0 and "marks this SKU exempt" in flagged["low_inventory_fee_exempt"]
    grocery = _lilf_row(_health(raw={"product-group": "Grocery"}))
    assert grocery["low_inventory_fee_month"] == 0.0 and grocery["low_inventory_fee_exempt"] == "exempt: Grocery"
    # no 7-day count on file: the fee stands, and the row says the exemption went unchecked
    unchecked = _lilf_row(_health(t7=None))
    assert unchecked["low_inventory_fee_month"] > 0 and unchecked["low_inventory_fee_exempt"] is None
    assert "exemption is unchecked (no units-shipped-t7 on file)" in unchecked["low_inventory_fee_basis"]
    # the exemptions no export shows are named on every row
    for r in (slow_week, unchecked):
        assert "New Selection" in r["low_inventory_fee_basis"] and "AWD" in r["low_inventory_fee_basis"]


def test_without_shipping_history_the_modelled_rate_stands_in_and_says_so():
    """No Inventory Age row at all: on hand over the modelled rate, as before, labelled."""
    out = econ.run({}, [_inventory("A", on_hand=40)], margin_rows=[_margin("A")], rng=np.random.default_rng(0),
                   simulations=2000, today=TODAY)
    a = out["rows"][0]
    assert a["low_inventory_days_of_supply"]["band"] == pytest.approx(40 / 3, abs=0.05)
    assert "modelled rate" in a["low_inventory_days_of_supply"]["source"]
    assert a["low_inventory_fee_month"] == pytest.approx(0.89 * 3 * 30, rel=1e-3)
