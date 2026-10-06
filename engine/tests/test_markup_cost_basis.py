"""The "are these prices already optimal?" model prices each SKU at the elasticity
its markup implies. That markup must cost the unit the way the margin and the price
step cost it, or the already-optimal world still points every price up (2026-10-06:
on the demo catalogue, unit cost and freight alone put all 22 optima 2.6–4.6% above
today's price, and the steps read 99% sure of their direction)."""

import pytest

from hubricon_engine.models import elasticity, pricing_engine
from hubricon_engine.models.margin import landed_unit_cost


def _data(**cost):
    row = {"sku": "A", "period_start": "2026-08-01", "units_sold": 100, "sales": 2500.0,
           "referral_fees": -375.0, "other_fees": 0.0, "fba_fulfillment_fees": -500.0, "storage_fees": -20.0}
    return {"cogs_inputs": [{"sku": "A", **cost}], "sku_economics": [row]}, row


def test_packaging_and_other_costs_enter_the_markup():
    lean, _ = _data(unit_cost_usd=6.0, inbound_freight_per_unit_usd=0.5)
    full, row = _data(unit_cost_usd=6.0, inbound_freight_per_unit_usd=0.5, packaging_per_unit_usd=0.9,
                      other_cost_per_unit_usd=0.2)
    eps_lean = elasticity.markup_implied_elasticity(lean)["A"]
    eps_full = elasticity.markup_implied_elasticity(full)["A"]
    assert eps_full < eps_lean   # a thinner markup implies a more elastic optimum


def test_at_the_implied_elasticity_todays_price_is_the_steps_own_optimum():
    data, row = _data(unit_cost_usd=6.0, inbound_freight_per_unit_usd=0.5, packaging_per_unit_usd=0.9,
                      other_cost_per_unit_usd=0.2)
    eps = elasticity.markup_implied_elasticity(data)["A"]
    price, units = row["sales"] / row["units_sold"], row["units_sold"]
    fee_rate = -row["referral_fees"] / row["sales"]
    fixed_fee = -(row["fba_fulfillment_fees"] + row["storage_fees"]) / units
    unit_cost = landed_unit_cost(data["cogs_inputs"][0], row)
    best = pricing_engine.optimal_price(eps, unit_cost, fee_rate, fixed_fee)
    assert best == pytest.approx(price, rel=1e-6)
