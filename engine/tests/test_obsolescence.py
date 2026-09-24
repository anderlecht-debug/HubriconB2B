"""Obsolescence in the order decision from the catalogue's own survival curve,
not a flat two percent."""

from datetime import date

import numpy as np
import pytest

from hubricon_engine.models import inventory_econ as econ, risk

TODAY = date(2026, 9, 1)


def _period(i):
    year, month = 2025 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _margins(sku, units, start=1, cogs_per_unit=5.0):
    rows = []
    for k, u in enumerate(units):
        s, e = _period(start + k)
        rows.append({"sku": sku, "period_start": s, "period_end": e, "units": u, "revenue": 20.0 * u,
                     "amazon_fees": 3.0 * u, "cogs": cogs_per_unit * u, "ad_spend_allocated": 0.0,
                     "net_margin": 12.0 * u})
    return rows


def _catalogue(dying=True):
    margins = []
    for i in range(10):
        margins += _margins(f"OK{i}", [90] * 8)
    if dying:
        for i in range(8):                       # eight SKUs that died after two or three periods
            rows = _margins(f"DEAD{i}", [90, 60, 0, 0, 0, 0, 0, 0] if i % 2 else [90, 80, 40, 0, 0, 0, 0, 0])
            margins += rows
    margins += _margins("YOUNG", [90, 90], start=7)
    return margins


def test_a_young_sku_on_a_catalogue_that_dies_young_earns_a_lower_service_level():
    margins = _catalogue()
    risk_out = risk.run({"sku_economics": [], "fba_returns": []}, margins, None, [], None, np.random.default_rng(1), 200)
    assert risk_out["survival"]["status"] == "ok" and risk_out["survival"]["events"] >= 8
    charge = econ.obsolescence_charge(risk_out, sku_age_periods=2, cycle_days=52, unit_cost=5.0, price=20.0)
    assert charge and 0 < charge["p_death_before_sellthrough"] < 1 and charge["per_unit"] > 0
    assert charge["per_unit"] == pytest.approx(charge["p_death_before_sellthrough"] * (5.0 - 2.0), rel=1e-6)
    old = econ.obsolescence_charge(risk_out, sku_age_periods=8, cycle_days=52, unit_cost=5.0, price=20.0)
    # the curve has no information beyond the longest life it saw: an old SKU carries no charge
    assert old["p_death_before_sellthrough"] == 0.0
    young = econ.critical_fractile(12.0, 5.0, 0.1, 52, 9, obsolescence_per_unit=charge["per_unit"], obsolescence_basis=charge["basis"])
    flat = econ.critical_fractile(12.0, 5.0, 0.1, 52, 9)
    assert young["q"] < flat["q"] and young["obsolescence_basis"].startswith("Kaplan")
    assert flat["obsolescence_basis"].startswith("flat rate")
    assert econ.obsolescence_charge(None, 2, 52, 5.0, 20.0) is None


def test_run_prices_it_and_publishes_the_band_and_falls_back_flat():
    margins = _catalogue()
    risk_out = risk.run({"sku_economics": [], "fba_returns": []}, margins, None, [], None, np.random.default_rng(1), 200)
    inv = [{"sku": "YOUNG", "daily_velocity_mean": 3.0, "daily_velocity_std": 0.5, "lead_time_days": 30,
            "on_hand_units": 100, "inbound_units": 0, "reorder_qty": 180, "reorder_point": 120}]
    with_curve = econ.run({}, inv, margins, None, np.random.default_rng(1), 4000, TODAY, risk_out=risk_out)
    flat = econ.run({}, inv, margins, None, np.random.default_rng(1), 4000, TODAY)
    a, b = with_curve["rows"][0], flat["rows"][0]
    assert a["obsolescence_basis"].startswith("Kaplan") and a["p_death_before_sellthrough"] > 0
    assert a["critical_fractile"] < b["critical_fractile"]
    band = a["critical_fractile_band"]
    assert band and band[0] <= a["critical_fractile"] <= band[1]
    assert b["obsolescence_basis"].startswith("flat rate") and b["critical_fractile_band"] is None
    assert "survival curve" in with_curve["assumptions"][1]
