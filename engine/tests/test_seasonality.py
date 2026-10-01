"""A seasonal index per calendar month, pooled across the catalog, shrunk
toward flat, and carried into every demand simulation."""

from datetime import date

import numpy as np
import pytest

from hubricon_engine.models import cashflow, forecast, inventory_econ, inventory_sim, seasonality
from hubricon_engine.models.seasonality import horizon_factor, indices, seasonal_rate

TODAY = date(2026, 9, 1)


def _catalog(n_skus=30, months=12, peak=1.8, noise=0.12, seed=1, start_year=2025, start_month=1):
    """SKUs whose rate follows a Q4 peak of `peak`× on a flat base, with noise."""
    rng = np.random.default_rng(seed)
    econ = []
    for i in range(n_skus):
        base = rng.uniform(2.0, 12.0)
        for k in range(months):
            y, m = start_year + (start_month - 1 + k) // 12, (start_month - 1 + k) % 12 + 1
            idx = peak if m in (10, 11, 12) else 1.0
            idx /= (3 * peak + 9) / 12          # mean one over the year
            rate = base * idx * np.exp(rng.normal(0, noise))
            days = 28
            econ.append({"sku": f"S{i:02d}", "asin": f"B{i:02d}", "period_start": f"{y}-{m:02d}-01",
                         "period_end": f"{y}-{m:02d}-{days}", "units_sold": rate * days, "sales": rate * days * 20.0,
                         "avg_sales_price": 20.0})
    return {"sku_economics": econ, "asin_traffic": [], "inventory_levels": [], "cogs_inputs": []}


def test_the_catalog_index_recovers_a_planted_peak_and_sharpens_with_a_second_season():
    one = indices(_catalog(months=12))
    assert one["status"] == "ok" and one["basis_label"] == "one_season_pooled"
    dec, jun = one["catalog"][12]["index"], one["catalog"][6]["index"]
    true_dec = 1.8 / ((3 * 1.8 + 9) / 12)
    true_jun = 1.0 / ((3 * 1.8 + 9) / 12)
    assert abs(dec - true_dec) < 0.15 and abs(jun - true_jun) < 0.15
    assert one["catalog"][12]["ci95"][0] < dec < one["catalog"][12]["ci95"][1]
    two = indices(_catalog(months=24))
    assert two["basis_label"] == "two_seasons"
    assert abs(two["catalog"][12]["index"] - true_dec) < 0.08
    assert two["catalog"][12]["se"] < one["catalog"][12]["se"]
    assert abs(np.mean([two["catalog"][m]["index"] for m in range(1, 13)]) - 1.0) < 1e-6


def test_a_flat_catalog_shrinks_to_one_and_eleven_months_refuse():
    flat = indices(_catalog(peak=1.0, noise=0.10))
    assert flat["status"] == "ok"
    assert max(abs(flat["catalog"][m]["index"] - 1.0) for m in range(1, 13)) < 0.08
    assert flat["amplitude"] < 1.15
    short = indices(_catalog(months=11))
    assert short["status"] == "insufficient_history" and "catalog" not in short


def test_a_skus_own_index_is_shrunk_toward_the_catalog():
    data = _catalog(months=24)
    # one SKU that peaks in summer against the catalog's winter
    econ = [r for r in data["sku_economics"] if r["sku"] != "S00"]
    for r in data["sku_economics"]:
        if r["sku"] == "S00":
            m = int(r["period_start"][5:7])
            summer = 2.0 if m in (6, 7, 8) else 1.0
            econ.append({**r, "units_sold": 5.0 * 28 * summer / ((3 * 2.0 + 9) / 12)})
    out = indices({**data, "sku_economics": econ})
    own = out["per_sku"]["S00"]["index"]
    assert own[7] > out["catalog"][7]["index"]          # pulled toward its own summer
    assert own[7] < 2.0 / ((3 * 2.0 + 9) / 12) + 0.05   # but not all the way, one season of evidence
    assert out["per_sku"]["S00"]["basis"].startswith("own ratios")


def test_the_horizon_factor_and_the_widened_sd():
    sea = indices(_catalog(months=24))
    f_sep, se_sep = horizon_factor(sea, None, date(2026, 9, 1), 30)
    f_nov, _ = horizon_factor(sea, None, date(2026, 11, 1), 30)
    assert f_nov > f_sep
    mean, sd, note = seasonal_rate(10.0, 2.0, sea, None, date(2026, 11, 1), 30)
    assert mean == pytest.approx(10.0 * f_nov, rel=1e-6)
    assert sd > 2.0 * f_nov and note["seasonal_basis"] == "two_seasons"
    assert seasonal_rate(10.0, 2.0, None, None, TODAY, 30)[:2] == (10.0, 2.0)
    assert horizon_factor({"status": "insufficient_history"}, None, TODAY, 30) == (1.0, 0.0)


def test_the_forecast_ladder_gains_the_candidate_and_only_keeps_it_when_it_wins():
    data = _catalog(n_skus=20, months=15, noise=0.05, seed=3)
    sea = indices(data)
    rows = forecast.run(data, seasonal=sea)
    methods = {r["method"] for r in rows if r["status"] == "ok"}
    assert "seasonal_index_ses" in methods
    win = [r for r in rows if r["method"] == "seasonal_index_ses"]
    assert all(r["mase"] <= r["naive_mase"] for r in win if r["mase"] is not None)
    assert all("seasonal_index_ses" in r["details"]["candidates"] for r in rows if r["status"] == "ok")
    flat = _catalog(n_skus=20, months=15, peak=1.0, noise=0.05, seed=3)
    flat_rows = forecast.run(flat, seasonal=indices(flat))
    assert sum(r["method"] == "seasonal_index_ses" for r in flat_rows) < len(flat_rows) / 2


def test_september_orders_more_than_march_for_the_peaked_sku_and_the_cone_sees_the_peak():
    data = _catalog(months=24, seed=5)
    sea = indices(data)
    data["cogs_inputs"] = [{"sku": "S01", "unit_cost_usd": 5.0, "supplier_lead_time_days": 60}]
    data["inventory_levels"] = [{"snapshot_date": "2026-08-30", "sku": "S01", "fulfillable_quantity": 300, "inbound_quantity": 0}]
    sep = [r for r in inventory_sim.run(data, np.random.default_rng(1), 5000, seasonal=sea, today=date(2026, 9, 1)) if r["sku"] == "S01"][0]
    mar = [r for r in inventory_sim.run(data, np.random.default_rng(1), 5000, seasonal=sea, today=date(2026, 3, 1)) if r["sku"] == "S01"][0]
    assert sep["reorder_qty"] > mar["reorder_qty"] and sep["details"]["seasonal_factor"] > mar["details"]["seasonal_factor"]
    margins = [{"sku": "S01", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 200, "revenue": 4000.0,
                "amazon_fees": 600.0, "cogs": 1000.0, "ad_spend_allocated": 0.0, "net_margin": 2400.0}]
    client = {"cash_on_hand": 5000.0, "monthly_fixed_costs": 1000.0}
    quiet = cashflow.run(client, sep and [sep], margins, np.random.default_rng(2), n_paths=800, horizon_days=90,
                         seasonal=sea, today=date(2026, 2, 1))
    peak = cashflow.run(client, [sep], margins, np.random.default_rng(2), n_paths=800, horizon_days=90,
                        seasonal=sea, today=date(2026, 10, 1))
    assert peak["details"]["p50"][-1] > quiet["details"]["p50"][-1]
    assert peak["details"]["seasonal"] == "index applied per calendar day"
    econ_sep = inventory_econ.run(data, [sep], margins, None, np.random.default_rng(1), 4000, date(2026, 9, 1), seasonal=sea)
    assert econ_sep["rows"][0]["seasonal_factor"] > 1.0
