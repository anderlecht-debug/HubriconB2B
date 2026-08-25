import numpy as np
import pytest

from hubricon_engine.models import ad_efficiency, elasticity, inventory_sim, margin


def _month(i: int) -> tuple[str, str]:
    return f"2026-{i:02d}-01", f"2026-{i:02d}-28"


def _econ_rows(prices, units, sku="S1"):
    rows = []
    for i, (p, u) in enumerate(zip(prices, units), start=1):
        start, end = _month(i)
        rows.append({
            "sku": sku, "asin": "B0TEST", "period_start": start, "period_end": end,
            "units_sold": u, "avg_sales_price": p, "sales": p * u,
            "referral_fees": 0, "fba_fulfillment_fees": 0, "storage_fees": 0,
            "other_fees": 0, "net_proceeds": p * u,
        })
    return rows


def _data(**overrides):
    base = {
        "asin_traffic": [], "sku_economics": [], "ppc_search_terms": [],
        "ppc_spend": [], "inventory_levels": [], "cogs_inputs": [],
    }
    base.update(overrides)
    return base


# ── elasticity ────────────────────────────────────────────────────────────

def test_elasticity_recovers_known_exponent():
    e_true = -1.8
    prices = [18.0, 19.0, 20.0, 21.0, 22.0, 23.0]
    units = [1e6 * p**e_true for p in prices]  # noise-free log-linear demand
    results = elasticity.run(_data(sku_economics=_econ_rows(prices, units)))
    r = next(x for x in results if x["level"] == "sku")
    assert r["status"] == "ok"
    assert r["elasticity"] == pytest.approx(e_true, abs=1e-3)
    assert r["r_squared"] == pytest.approx(1.0, abs=1e-6)


def test_flat_prices_are_a_status_not_a_number():
    prices = [20.0] * 6
    units = [500, 510, 490, 505, 495, 500]
    results = elasticity.run(_data(sku_economics=_econ_rows(prices, units)))
    r = results[0]
    assert r["status"] == "insufficient_price_variation"
    assert r.get("elasticity") is None


def test_too_few_periods():
    results = elasticity.run(_data(sku_economics=_econ_rows([18.0, 20.0, 22.0], [100, 90, 80])))
    assert results[0]["status"] == "insufficient_data"


def _traffic_rows(prices, units, sessions):
    rows = []
    for i, (p, u, s) in enumerate(zip(prices, units, sessions), start=1):
        start, end = _month(i)
        rows.append({
            "child_asin": "B0TEST", "parent_asin": None, "period_start": start, "period_end": end,
            "units_ordered": u, "ordered_product_sales": p * u, "sessions": s,
        })
    return rows


def test_collinear_sessions_control_is_dropped():
    e_true = -1.8
    prices = [18.0, 19.0, 20.0, 21.0, 22.0, 23.0]
    units = [1e6 * p**e_true for p in prices]
    sessions = [u * 4 + 60 for u in units]  # sessions a pure function of units
    results = elasticity.run(_data(asin_traffic=_traffic_rows(prices, units, sessions)))
    r = results[0]
    assert r["status"] == "ok"
    assert r["details"]["control_dropped_collinear"] is True
    assert r["details"]["controls"] == []
    assert r["elasticity"] == pytest.approx(e_true, abs=1e-3)


def test_independent_sessions_control_is_used():
    rng = np.random.default_rng(3)
    e_true = -1.5
    prices = np.array([18.0, 21.0, 19.0, 23.0, 20.0, 22.0, 18.5, 21.5])
    sessions = rng.uniform(800, 2000, size=len(prices))  # traffic swings on its own
    units = 50.0 * prices**e_true * (sessions / 1000.0)
    results = elasticity.run(_data(asin_traffic=_traffic_rows(prices, units, sessions)))
    r = results[0]
    assert r["status"] == "ok"
    assert r["details"]["controls"] == ["sessions"]
    assert r["elasticity"] == pytest.approx(e_true, abs=1e-3)


# ── ad efficiency ─────────────────────────────────────────────────────────

def test_hill_fit_recovers_parameters():
    a, k, h = 1000.0, 50.0, 1.2
    spend = np.array([10, 25, 40, 60, 90, 130, 170, 200], dtype=float)
    sales = a * spend**h / (k**h + spend**h)
    model, params = ad_efficiency._fit_curve(spend, sales)
    assert model == "hill"
    assert params[0] == pytest.approx(a, rel=0.05)
    assert params[1] == pytest.approx(k, rel=0.10)


def test_marginal_roas_decreases_and_breakeven_found():
    params = (1000.0, 50.0, 1.2)
    m_low = ad_efficiency._marginal("hill", params, 20.0)
    m_high = ad_efficiency._marginal("hill", params, 150.0)
    assert m_low > m_high  # diminishing returns
    breakeven = ad_efficiency._breakeven("hill", params, 200.0, threshold=1.0)
    assert breakeven is not None
    assert ad_efficiency._marginal("hill", params, breakeven) == pytest.approx(1.0, abs=0.15)


def test_sparse_campaign_reported_not_fitted():
    ppc = [{"campaign_name": "Tiny", "campaign_id": "Tiny", "spend": 10.0, "sales": 30.0,
            "report_date": "2026-08-01"}]
    results = ad_efficiency.run(_data(ppc_spend=ppc))
    assert results[0]["status"] == "insufficient_data"


def test_bleed_terms_flagged():
    terms = [
        {"campaign_name": "C", "period_start": "2026-07-01", "period_end": "2026-07-31",
         "search_term": "wasted term", "spend": 80.0, "sales_7d": 0.0, "clicks": 40},
        {"campaign_name": "C", "period_start": "2026-07-01", "period_end": "2026-07-31",
         "search_term": "good term", "spend": 90.0, "sales_7d": 400.0, "clicks": 50},
    ]
    results = ad_efficiency.run(_data(ppc_search_terms=terms))
    bleed = results[0]["bleed_terms"]
    assert [b["search_term"] for b in bleed] == ["wasted term"]


# ── inventory ─────────────────────────────────────────────────────────────

def _inventory_data(lead_days: int):
    return _data(
        sku_economics=_econ_rows([20.0] * 3, [300, 300, 300]),
        inventory_levels=[{
            "sku": "S1", "snapshot_date": "2026-08-01",
            "fulfillable_quantity": 400, "inbound_quantity": 0,
        }],
        cogs_inputs=[{
            "sku": "S1", "asin": "B0TEST", "unit_cost_usd": 5.0,
            "supplier_lead_time_days": lead_days,
        }],
    )


def test_stockout_probability_rises_with_lead_time():
    short = inventory_sim.run(_inventory_data(20), np.random.default_rng(1), simulations=8000)[0]
    long = inventory_sim.run(_inventory_data(90), np.random.default_rng(1), simulations=8000)[0]
    assert 0.0 <= short["stockout_probability"] <= 1.0
    assert long["stockout_probability"] > short["stockout_probability"]
    # ~10.7 units/day against 400 on hand: 20-day lead is comfortable, 90 is not
    assert short["stockout_probability"] < 0.10
    assert long["stockout_probability"] > 0.90


def test_simulation_is_reproducible():
    a = inventory_sim.run(_inventory_data(40), np.random.default_rng(7), simulations=4000)[0]
    b = inventory_sim.run(_inventory_data(40), np.random.default_rng(7), simulations=4000)[0]
    assert a == b


# ── margin ────────────────────────────────────────────────────────────────

def test_margin_reconciles_by_hand():
    econ = [
        {"sku": "A", "asin": "B0A", "period_start": "2026-07-01", "period_end": "2026-07-31",
         "units_sold": 100, "avg_sales_price": 20.0, "sales": 2000.0,
         "referral_fees": -300.0, "fba_fulfillment_fees": -330.0, "storage_fees": -20.0,
         "other_fees": None, "net_proceeds": 1350.0},
        {"sku": "B", "asin": "B0B", "period_start": "2026-07-01", "period_end": "2026-07-31",
         "units_sold": 50, "avg_sales_price": 40.0, "sales": 2000.0,
         "referral_fees": -300.0, "fba_fulfillment_fees": -180.0, "storage_fees": -20.0,
         "other_fees": None, "net_proceeds": 1500.0},
    ]
    cogs = [
        {"sku": "A", "asin": "B0A", "unit_cost_usd": 4.0, "inbound_freight_per_unit_usd": 0.5,
         "packaging_per_unit_usd": 0.5, "other_cost_per_unit_usd": None, "supplier_lead_time_days": 30},
    ]
    ppc = [{"campaign_name": "C", "campaign_id": "C", "report_date": "2026-07-15",
            "spend": 400.0, "sales": 900.0}]
    results = margin.run(_data(sku_economics=econ, cogs_inputs=cogs, ppc_spend=ppc))

    a = next(r for r in results if r["sku"] == "A")
    # fees 650, cogs 100*(4+.5+.5)=500, ads 400*0.5=200 -> net 2000-650-500-200=650
    assert a["amazon_fees"] == 650.0
    assert a["cogs"] == 500.0
    assert a["ad_spend_allocated"] == 200.0
    assert a["net_margin"] == 650.0
    assert a["net_margin_pct"] == pytest.approx(0.325)

    b = next(r for r in results if r["sku"] == "B")
    assert b["cogs"] is None  # no COGS row supplied -> reported as unknown, not zero
    assert b["net_margin"] == 2000.0 - 500.0 - 200.0  # fees + ads only

    avg = margin.average_margin(results)
    assert avg == pytest.approx((650 + 200 + 1300 + 200) / 4000)
