"""Which response form, chosen out of sample: a curve only when it beats a
straight line."""

import numpy as np

from hubricon_engine import directives
from hubricon_engine.models import ad_allocation, ad_efficiency
from hubricon_engine.models.ad_efficiency import backtest_forms


def _campaign(kind, n=24, noise=6.0, seed=2, name="C"):
    rng = np.random.default_rng(seed)
    spend = np.linspace(10, 300, n)
    rng.shuffle(spend)
    if kind == "hill":
        sales = 1000 * spend**1.2 / (50**1.2 + spend**1.2)
    elif kind == "linear":
        sales = 3.2 * spend
    else:
        sales = 400 * np.log1p(0.05 * spend)
    sales = sales + rng.normal(0, noise, size=n)
    ppc = [{"campaign_name": name, "campaign_id": name, "spend": float(s), "sales": float(max(0.0, v)),
            "report_date": f"2026-08-{i + 1:02d}" if i < 30 else f"2026-09-{i - 29:02d}"}
           for i, (s, v) in enumerate(zip(spend, sales))]
    return {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [], "ppc_spend": ppc,
            "inventory_levels": [], "cogs_inputs": []}


def test_a_saturating_campaign_picks_a_curve_and_a_linear_one_picks_the_straight_line():
    hill = ad_efficiency.run(_campaign("hill"), avg_margin=0.35)[0]
    assert hill["status"] == "ok" and hill["curve_model"] in ("hill", "log")
    sel = hill["details"]["form_selection"]
    assert sel["status"] == "ok" and sel["chosen"] == hill["curve_model"] and sel["fva_pct"] > 0
    assert set(sel["candidates"]) == {"linear", "log", "hill"}
    linear = ad_efficiency.run(_campaign("linear"), avg_margin=0.35)[0]
    assert linear["status"] == "no_diminishing_returns" and linear["curve_model"] == "linear"
    assert linear["breakeven_spend"] is None and abs(linear["marginal_roas"] - 3.2) < 0.2
    assert linear["details"]["form_selection"]["fva_pct"] == 0.0
    assert linear["details"]["uncertainty"]["marginal_roas_p5"] < 3.2 < linear["details"]["uncertainty"]["marginal_roas_p95"]


def test_a_short_series_defaults_to_hill_and_says_so():
    short = ad_efficiency.run(_campaign("hill", n=6), avg_margin=0.35)[0]
    assert short["details"]["form_selection"]["status"] == "insufficient_origins"
    assert short["status"] == "ok" and short["curve_model"] == "hill"


def test_a_linear_campaign_is_not_trimmed_but_can_still_take_or_give_budget():
    rows = [ad_efficiency.run(_campaign("linear", name="L"), avg_margin=0.35)[0],
            ad_efficiency.run(_campaign("hill", name="H"), avg_margin=0.35)[0]]
    rows[0]["current_spend"], rows[1]["current_spend"] = 40.0, 160.0
    assert "L" not in directives.trim_candidates(rows, 0.35)
    out = ad_allocation.run(rows, 0.35)
    assert out["status"] in ("ok", "no_reallocation")
    by = {c["campaign_name"]: c for c in out["campaigns"]}
    assert by["L"]["status"] == "ok" and by["L"]["curve_model"] == "linear"
    # the straight line's marginal return is its ROAS everywhere
    assert abs(by["L"]["marginal_roas_now"] - by["L"]["marginal_roas_at_rec"]) < 1e-9


def test_the_backtest_is_honest_about_ties_and_scale():
    spend = np.linspace(10, 300, 12)
    sales = 3.0 * spend
    sel = backtest_forms(spend, sales)
    assert sel["chosen"] == "linear"
