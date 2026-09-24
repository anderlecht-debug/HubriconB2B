"""BG/NBD and Gamma–Gamma on a store that knows its customers, and what they
do to the allowable cost of acquiring one."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from hubricon_engine.ingest import shopify_orders
from hubricon_engine.models import ad_efficiency, clv
from hubricon_engine.models.clv import bgnbd_fit, customer_table, expected_repeats, gamma_gamma_fit


def _customers(n=2000, r=0.6, alpha=8.0, a=0.8, b=3.0, weeks=78, seed=1, p=6.0, q=4.0, gamma=40.0):
    """Orders simulated from the BG/NBD + Gamma–Gamma story: a Poisson buying
    rate per customer, a dropout coin after each purchase, Gamma order values."""
    rng = np.random.default_rng(seed)
    end = date(2026, 9, 1)
    orders = []
    for i in range(n):
        lam = rng.gamma(r, 1 / alpha)
        drop = rng.beta(a, b)
        nu = rng.gamma(q, 1 / gamma)
        first = end - timedelta(weeks=float(rng.uniform(4, weeks)))
        t = first
        k = 0
        alive = True
        while alive:
            value = rng.gamma(p, 1 / nu)
            orders.append({"customer_key": f"c{i}", "order_name": f"#{i}-{k}", "order_date": t.isoformat(),
                           "revenue": round(float(value), 2), "units": 1})
            k += 1
            if rng.random() < drop:
                alive = False
                break
            gap = min(float(rng.exponential(7.0 / max(lam, 1e-6))), 3650.0)
            t = t + timedelta(days=gap)
            if t > end:
                break
    return orders


def test_the_customer_table_counts_repeats_recency_and_age_in_weeks():
    orders = [{"customer_key": "a", "order_name": "1", "order_date": "2026-01-01", "revenue": 30.0},
              {"customer_key": "a", "order_name": "2", "order_date": "2026-01-15", "revenue": 50.0},
              {"customer_key": "b", "order_name": "3", "order_date": "2026-02-01", "revenue": 20.0}]
    x, t_x, T, mv, fv, end = customer_table(orders, end=date(2026, 3, 1))
    assert list(x) == [1.0, 0.0] and t_x[0] == pytest.approx(2.0) and T[0] == pytest.approx(59 / 7)
    assert mv[0] == 50.0 and fv[0] == 30.0 and mv[1] == 0.0


def test_maximum_likelihood_recovers_the_planted_parameters():
    orders = _customers()
    x, t_x, T, mv, fv, _ = customer_table(orders)
    fit = bgnbd_fit(x, t_x, T)
    assert fit["converged"]
    # the shape of repeat behaviour: expected repeats per customer over a year
    # matches what the same parameters would predict, not the raw parameters
    # (r, α, a, b are only weakly identified on 78 weeks; the prediction is not)
    truth = {"r": 0.6, "alpha": 8.0, "a": 0.8, "b": 3.0}
    pred_fit = expected_repeats(fit, 52, x, t_x, T).mean()
    pred_true = expected_repeats(truth, 52, x, t_x, T).mean()
    assert pred_fit == pytest.approx(pred_true, rel=0.25)
    gg = gamma_gamma_fit(x, mv)
    assert gg["status"] == "ok"
    # population mean order value γ·p/(q−1) = 40·6/3 = 80
    assert gg["population_mean_value"] == pytest.approx(80.0, rel=0.15)


def test_the_holdout_calibration_passes_on_its_own_generator_and_the_multiplier_carries_a_band():
    out = clv.run(_customers(), today=date(2026, 9, 1))
    assert out["status"] == "ok", out.get("calibration")
    cal = out["calibration"]
    assert 0.7 <= cal["actual_over_predicted"] <= 1.3 and cal["calibrated"]
    assert out["clv_multiplier"] > 1.0
    band = out["clv_multiplier_band"]
    assert band and band["p5"] <= band["p50"] <= band["p95"] and band["seed"] == clv.CLV_SEED
    assert out["gamma_gamma"]["frequency_value_correlation"] is not None
    assert "moves the ad break-even" in out["basis"]


def test_refusals():
    few = clv.run(_customers(n=80), today=date(2026, 9, 1))
    assert few["status"] == "insufficient_data" and "80 customers" in few["basis"]
    short = clv.run(_customers(n=300, weeks=20), today=date(2026, 9, 1))
    assert short["status"] == "insufficient_data" and "weeks" in short["basis"]
    assert clv.run(_customers(), channel="amazon")["status"] == "not_applicable"


def test_the_parser_writes_hashed_keys_and_never_the_email():
    df = pd.DataFrame([
        {"Name": "#1001", "Email": "Ann@Example.com", "Financial Status": "paid", "Created at": "2026-08-02 10:00",
         "Lineitem quantity": 2, "Lineitem name": "Widget", "Lineitem price": 20.0, "Lineitem sku": "W1",
         "Refunded Amount": 0.0},
        {"Name": "#1001", "Email": "", "Financial Status": "", "Created at": "", "Lineitem quantity": 1,
         "Lineitem name": "Gadget", "Lineitem price": 10.0, "Lineitem sku": "G1"},
        {"Name": "#1002", "Email": "ann@example.com ", "Financial Status": "paid", "Created at": "2026-08-20 10:00",
         "Lineitem quantity": 1, "Lineitem name": "Widget", "Lineitem price": 20.0, "Lineitem sku": "W1"},
        {"Name": "#1003", "Email": "", "Financial Status": "paid", "Created at": "2026-08-21 10:00",
         "Lineitem quantity": 1, "Lineitem name": "Widget", "Lineitem price": 20.0, "Lineitem sku": "W1"},
    ])
    upload = {"client_id": "client-1", "id": "u1", "period_start": "2026-08-01", "period_end": "2026-08-31"}
    out = shopify_orders.parse(df, upload)
    tables = {t: rows for t, rows, _ in out}
    assert set(tables) == {"sku_economics", "customer_orders"}
    cust = tables["customer_orders"]
    assert [c["order_name"] for c in cust] == ["#1001", "#1002"]          # the email-less order is absent
    assert cust[0]["customer_key"] == cust[1]["customer_key"]              # case and whitespace do not split a customer
    assert len(cust[0]["customer_key"]) == 64
    assert "ann@" not in str(cust).lower() and "example.com" not in str(cust).lower()
    assert cust[0]["revenue"] == 50.0 and cust[0]["units"] == 3
    other = shopify_orders.parse(df, {**upload, "client_id": "client-2"})
    assert other[1][1][0]["customer_key"] != cust[0]["customer_key"]      # salted per client
    assert len(tables["sku_economics"]) == 2


def test_a_calibrated_multiplier_moves_the_break_even_and_an_uncalibrated_one_does_not():
    rng = np.random.default_rng(2)
    spend = np.linspace(10, 300, 12)
    sales = 1000 * spend / (50 + spend) + rng.normal(0, 8, 12)
    ppc = [{"campaign_name": "C", "campaign_id": "C", "spend": float(s), "sales": float(v),
            "report_date": f"2026-08-{i + 1:02d}"} for i, (s, v) in enumerate(zip(spend, sales))]
    data = {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [], "ppc_spend": ppc,
            "inventory_levels": [], "cogs_inputs": []}
    plain = ad_efficiency.run(data, avg_margin=0.35)[0]
    with_clv = ad_efficiency.run(data, avg_margin=0.35, clv_multiplier=2.0, clv_basis="calibrated")[0]
    # a customer worth two orders halves the marginal return an ad needs: the
    # break-even spend rises
    assert with_clv["breakeven_spend"] > plain["breakeven_spend"]
    assert with_clv["breakeven_spend_attributed"] == plain["breakeven_spend"]
    assert with_clv["details"]["clv_multiplier"] == 2.0
    unc = ad_efficiency.run(data, avg_margin=0.35, clv_multiplier=2.0, clv_basis=None)[0]
    assert unc["breakeven_spend"] == plain["breakeven_spend"]
