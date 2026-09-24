"""Cross-price effects inside a variant family, and what they do to a step."""

from datetime import date

import numpy as np
import pytest

from hubricon_engine import directives, measurement
from hubricon_engine.models import cross_price
from hubricon_engine.models.pricing_engine import price_move


def _period(i: int) -> tuple[str, str]:
    year, month = 2025 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _family(seed, eps_own=-2.0, eps_cross=0.8, n_children=4, n_periods=10, price_cv=0.10, noise=0.08,
            parent="P1", prefix="S"):
    """Children of one parent whose demand follows the family model exactly."""
    rng = np.random.default_rng(seed)
    econ, traffic = [], []
    base = {f"{prefix}{c}": 300.0 * (1 + 0.3 * c) for c in range(n_children)}
    prices = {c: 20.0 * np.exp(rng.normal(0, price_cv, n_periods)) for c in base}
    for c in base:
        for t in range(n_periods):
            others = [o for o in base if o != c]
            sib = np.mean([np.log(prices[o][t] / 20.0) for o in others])
            q = base[c] * (prices[c][t] / 20.0) ** eps_own * np.exp(eps_cross * sib + rng.normal(0, noise))
            start, end = _period(t + 1)
            econ.append({"sku": c, "asin": f"B0{c}", "period_start": start, "period_end": end,
                         "units_sold": float(q), "avg_sales_price": float(prices[c][t]),
                         "sales": float(q * prices[c][t]), "referral_fees": -0.15 * q * prices[c][t],
                         "fba_fulfillment_fees": -1.5 * q, "storage_fees": 0.0, "other_fees": 0.0})
        traffic.append({"child_asin": f"B0{c}", "parent_asin": parent, "period_start": _period(1)[0],
                        "period_end": _period(1)[1], "units_ordered": 1, "ordered_product_sales": 1.0})
    return {"sku_economics": econ, "asin_traffic": traffic, "cogs_inputs": [], "ppc_spend": [],
            "ppc_search_terms": [], "inventory_levels": []}


def test_a_planted_cross_elasticity_is_recovered():
    own, cross = [], []
    for seed in range(20):
        out = cross_price.run(_family(seed))
        assert out["status"] == "ok", out
        f = out["families"][0]
        own.append(f["eps_own"])
        cross.append(f["eps_cross"])
    assert abs(float(np.median(cross)) - 0.8) < 0.2
    assert abs(float(np.median(own)) + 2.0) < 0.2
    f = cross_price.run(_family(0))["families"][0]
    assert f["ci95_cross"][0] < f["eps_cross"] < f["ci95_cross"][1]
    assert f["dof"] == 4 * 10 - 4 - 2 and f["details"]["se_estimator"] == "HC3"
    assert f["shrinkage"] == "none_pool_too_small"


def test_no_mapping_is_a_status_and_a_handle_is_a_family():
    data = _family(1)
    for r in data["asin_traffic"]:
        r["parent_asin"] = None
    assert cross_price.run(data)["status"] == "no_variant_mapping"
    # Shopify: no ASIN on the sales rows, the handle in the cost sheet's asin column
    shop = _family(1)
    shop["asin_traffic"] = []
    for r in shop["sku_economics"]:
        r["asin"] = None
    shop["cogs_inputs"] = [{"sku": f"S{c}", "asin": "blue-widget", "unit_cost_usd": 5.0} for c in range(4)]
    fams = cross_price.families(shop)
    assert fams == {"blue-widget": ["S0", "S1", "S2", "S3"]}
    assert cross_price.run(shop)["status"] == "ok"


def test_families_are_shrunk_toward_the_catalogue_when_three_or_more_fit():
    def _book(spread):
        data = _family(3)
        for k, parent in enumerate(("P2", "P3")):
            more = _family(10 + k, eps_cross=0.8 + spread * (k - 0.5), parent=parent, prefix=f"T{k}")
            data["sku_economics"] += more["sku_economics"]
            data["asin_traffic"] += more["asin_traffic"]
        return cross_price.run(data)

    # families planted far apart keep most of their own estimate
    wide = _book(1.6)
    assert wide["n_fitted"] == 3
    for f in wide["families"]:
        assert f["shrinkage"] == "empirical_bayes" and 0 < f["shrinkage_weight"] <= 1
        assert f["pooled_eps_cross"] is not None and f["tau2"] > 0
    # families no more dispersed than their own noise pool fully — τ² = 0 is an
    # answer, not a failure, and the weight says so
    close = _book(0.0)
    assert close["n_fitted"] == 3
    assert all(f["shrinkage"] == "empirical_bayes" and f["shrinkage_weight"] == 0.0 for f in close["families"])
    out = wide
    assert out["by_sku"]["S0"]["family"] == "P1" and len(out["by_sku"]["S0"]["siblings"]) == 3


def test_thin_families_refuse():
    short = _family(2, n_periods=4)
    assert cross_price.run(short)["families"][0]["status"] == "insufficient_data"
    flat = _family(2, price_cv=0.0)
    assert cross_price.run(flat)["families"][0]["status"] == "insufficient_price_variation"


MARGIN = {"sku": "BLUE", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 300,
          "revenue": 6000.0, "amazon_fees": 1350.0, "cogs": 1500.0, "net_margin": 3000.0}
FIT = {"level": "sku", "item_id": "BLUE", "status": "ok", "elasticity": -3.0, "std_err": 0.2,
       "details": {"ci95": [-3.5, -2.5], "dof": 6, "t_critical": 2.447, "residual_sd_log": 0.1}}


def _cross(weight=1.0, q0=900.0, contribution=12.0, eps=1.5):
    return {"eps": eps, "std_err": 0.2, "dof": 30, "family": "P1",
            "siblings": [{"sku": "RED", "q0": q0, "contribution": contribution, "weight": weight,
                          "baseline_units": q0, "baseline_profit": q0 * contribution}]}


def test_a_cut_that_steals_from_a_large_sibling_is_refused_as_cannibalisation():
    alone = price_move(MARGIN, FIT)
    assert alone and alone["p_new"] < alone["p0"]          # ε = −3: a cut, on its own
    together = price_move(MARGIN, FIT, cross=_cross())
    assert together["status"] == "cannibalisation"
    assert together["sibling"] == "RED" and together["own_delta_p50"] > 0
    assert together["total_delta_p50"] < together["own_delta_p50"]
    d = directives._cannibalisation_directive(together, FIT, MARGIN, "BLUE")
    assert d["kind"] == "cannibalisation_watch" and d["mandate"] == "explicit" and d["expected_impact_usd"] is None
    assert "No step on BLUE" in d["action_text"] and "from RED" in d["action_text"]
    assert "price the family together" in d["action_text"]


def test_a_move_the_family_welcomes_carries_the_sibling_gain_in_its_range():
    rise_fit = {**FIT, "item_id": "BLUE", "elasticity": -1.3, "details": {**FIT["details"], "ci95": [-1.7, -0.9]}}
    alone = price_move(MARGIN, rise_fit)
    assert alone and alone["p_new"] > alone["p0"]          # a rise
    together = price_move(MARGIN, rise_fit, cross=_cross(weight=0.5, q0=400.0, contribution=10.0, eps=0.8))
    assert together["status"] == alone["status"]
    ce = together["cross_effect"]
    assert ce["delta_sibling_p50"] > 0 and ce["delta_own_p50"] is not None
    assert together["delta_p50"] > alone["delta_p50"]
    assert together["mc_inputs"]["n_siblings"] == 1 and together["mc_inputs"]["cross_eps_se"] == 0.2
    # no family: byte-identical to before the term existed
    assert price_move(MARGIN, rise_fit, cross=None) == alone


def test_the_measurement_charges_the_sibling_and_caps_at_the_familys_change():
    rise_fit = {**FIT, "elasticity": -1.3, "details": {**FIT["details"], "ci95": [-1.7, -0.9]}}
    move = price_move(MARGIN, rise_fit, cross=_cross(weight=0.5, q0=400.0, contribution=10.0, eps=0.8))
    ev = {"sku": "BLUE", **move, "elasticity": -1.3, "std_err": 0.2, "ci95": [-1.7, -0.9],
          "baseline_units": 300.0, "baseline_revenue": 6000.0, "baseline_cogs": 1500.0, "baseline_fees": 1350.0,
          "baseline_period": "2026-07-01"}
    d = {"id": "p1", "kind": "price_step", "status": "approved", "expected_impact_usd": move["expected_delta"],
         "evidence": ev, "issued_at": "2026-08-01T00:00:00+00:00"}
    p1 = move["p_new"]
    after = [
        {"sku": "BLUE", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 285,
         "revenue": 285 * p1, "amazon_fees": 0.225 * 285 * p1, "cogs": 1425.0, "net_margin": 0.0,
         "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 1.5}},
        # RED sold more after BLUE went up, at $10 contribution a unit
        {"sku": "RED", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 420,
         "revenue": 420 * 25.0, "amazon_fees": 420 * 25.0 * 0.15, "cogs": 420 * (25.0 * 0.85 - 10.0),
         "net_margin": 4200.0},
    ]
    v = measurement.measure_price_step(d, after, [], date(2026, 7, 31), date(2026, 9, 1))
    assert v["verdict"] == "measured"
    assert v["evidence_after"]["siblings"] == [{"sku": "RED", "units_after": 420.0}]
    assert v["evidence_after"]["sibling_delta_p50"] is not None
    assert "family's own profit" in v["measurement_notes"] or v["measured_impact_usd"] <= move["expected_delta"] + 0.01


def test_the_drafter_builds_the_family_from_the_siblings_margin_rows():
    margins = [MARGIN,
               {"sku": "RED", "period_start": "2026-07-01", "period_end": "2026-07-28", "units": 900,
                "revenue": 22500.0, "amazon_fees": 3375.0, "cogs": 4500.0, "net_margin": 14000.0}]
    cross = {"status": "ok", "by_sku": {
        "BLUE": {"family": "P1", "eps_cross": 1.5, "se_cross": 0.2, "dof": 30,
                 "siblings": [{"sku": "RED", "weight": 1.0}]}}}
    drafts = directives.draft_directives([], [], [FIT], margins, cross_price=cross)
    kinds = {x["kind"] for x in drafts}
    assert "cannibalisation_watch" in kinds and "price_step" not in {x["kind"] for x in drafts if x["evidence"].get("sku") == "BLUE"}
    # a sibling without landed cost drops out and the SKU is priced alone
    margins[1]["cogs"] = None
    drafts = directives.draft_directives([], [], [FIT], margins, cross_price=cross)
    assert any(x["kind"] == "price_step" and x["evidence"]["sku"] == "BLUE" for x in drafts)
