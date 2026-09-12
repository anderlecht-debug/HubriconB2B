import pytest

from hubricon_engine.directives import (
    branded_spend,
    draft_directives,
    resolve_brand_terms,
)

INVENTORY = [
    {"sku": "RISKY", "stockout_probability": 0.62, "reorder_qty": 740, "reorder_point": 690,
     "lead_time_days": 38, "daily_velocity_mean": 10.0, "on_hand_units": 400, "inbound_units": 0},
    {"sku": "SAFE", "stockout_probability": 0.05, "reorder_qty": 100, "reorder_point": 90,
     "lead_time_days": 30, "daily_velocity_mean": 5.0, "on_hand_units": 300, "inbound_units": 0},
]
ADS = [
    {"campaign_name": "Over", "status": "ok", "current_spend": 90.0, "breakeven_spend": 60.0,
     "bleed_terms": [{"search_term": "waste", "spend": 100.0, "clicks": 40}]},
    {"campaign_name": "Fine", "status": "ok", "current_spend": 40.0, "breakeven_spend": 60.0, "bleed_terms": []},
]
# A status-"ok" row out of elasticity.run ALWAYS carries std_err, ci95, dof and
# t_critical — the fit cannot succeed without producing them. These fixtures
# omitted them until 2026-09-12, which made them exercise a shape the engine never
# emits; since a fitted row with no stated uncertainty is now refused outright (see
# pricing_engine.near_unit_elastic), the omission became visible. Fixed here rather
# than weakening the rule: the fixture now matches the contract.
ELASTICITY = [
    {"level": "sku", "item_id": "INELASTIC", "status": "ok", "elasticity": -0.5,
     "std_err": 0.08, "details": {"ci95": [-0.75, -0.25], "dof": 5, "t_critical": 2.571,
                                  "residual_sd_log": 0.12}},
    {"level": "sku", "item_id": "RISKY", "status": "ok", "elasticity": -2.0,
     "std_err": 0.144, "details": {"ci95": [-2.4, -1.6], "dof": 5, "t_critical": 2.571,
                                   "residual_sd_log": 0.12}},
    {"level": "sku", "item_id": "FLAT", "status": "insufficient_price_variation", "elasticity": None},
]
MARGINS = [
    # latest period rows carry units + cogs so directives can be dollar-exact
    {"sku": "INELASTIC", "period_start": "2026-07-01", "units": 100, "revenue": 10000.0,
     "amazon_fees": 1500.0, "cogs": 2000.0, "net_margin": 2000.0},
    {"sku": "RISKY", "period_start": "2026-07-01", "units": 100, "revenue": 2000.0,
     "amazon_fees": 300.0, "cogs": 500.0, "net_margin": 400.0},
    {"sku": "LOSER", "period_start": "2026-07-01", "units": 30, "revenue": 3000.0,
     "amazon_fees": 900.0, "cogs": 1200.0, "net_margin": -450.0},
    {"sku": "LOSER", "period_start": "2026-06-01", "units": 32, "revenue": 3200.0,
     "amazon_fees": 940.0, "cogs": 1260.0, "net_margin": -300.0},
]
SEARCH_TERMS = [
    {"search_term": "acme widget 2 pack", "spend": 80.0, "sales_7d": 400.0,
     "period_start": "2026-07-01", "period_end": "2026-07-31"},
    {"search_term": "acme", "spend": 45.0, "sales_7d": 300.0,
     "period_start": "2026-07-01", "period_end": "2026-07-31"},
    {"search_term": "kitchen widget", "spend": 200.0, "sales_7d": 500.0,
     "period_start": "2026-07-01", "period_end": "2026-07-31"},
    {"search_term": "acme branded zero sale", "spend": 60.0, "sales_7d": 0.0,
     "period_start": "2026-07-01", "period_end": "2026-07-31"},   # bleed's territory, excluded
]


def _draft(**kw):
    return draft_directives(INVENTORY, ADS, ELASTICITY, MARGINS, **kw)


def test_inventory_directive_is_a_wire_instruction():
    d = next(x for x in _draft() if x["module"] == "inventory")
    # 740 units at $5/unit landed (cogs 500 / 100 units) = $3,700
    assert "Wire $3,700" in d["action_text"]
    assert "740 units of RISKY" in d["action_text"]
    assert " by " in d["action_text"]                 # a real calendar date
    assert d["expected_impact_usd"] is None           # avoided stockout not claimed
    assert not any("SAFE" in x["action_text"] for x in _draft())


def test_pricing_directive_is_exact_with_destination_and_range():
    texts = [x["action_text"] for x in _draft() if x["module"] == "pricing"]
    exact = next(t for t in texts if "RISKY" in t)
    assert "$20.00 → $19.00" in exact                 # -5% cap toward the $11.76 optimum
    assert "optimum $11.76" in exact
    # The range is a 90% band (P5 to P95) out of the parametric bootstrap over
    # every uncertain input, and it is named as such — "95% range" was wrong at
    # both ends: wrong level, and built from two elasticity endpoints rather
    # than from uncertainty in the elasticity, the baseline volume and the fees.
    assert "90% range" in exact
    assert "chance it goes the other way" in exact
    inelastic = next(t for t in texts if "INELASTIC" in t)
    # The step is solved for now, not set to a constant: this fixture states no
    # uncertainty at all, so the objective has nothing to be cautious about and
    # walks to the contractual rail. tests/test_pricing_engine.py pins the
    # property that matters — an uncertain fit steps less than the rail.
    assert "$100.00 → $105.00" in inelastic
    assert not any("FLAT" in t for t in texts)
    # No job watches the Buy Box daily; the measurement pass reads it while the step runs.
    for t in (exact, inelastic):
        assert "Buy Box watched while the step is live." in t and "watched daily" not in t


def test_inelastic_with_cogs_carries_computed_dollars():
    d = next(x for x in _draft() if x["module"] == "pricing" and "INELASTIC" in x["action_text"])
    assert d["expected_impact_usd"] is not None and d["expected_impact_usd"] > 0


def test_branded_spend_detector_and_directive():
    spend, n = branded_spend(SEARCH_TERMS, ["acme"])
    assert spend == 125.0 and n == 2                  # zero-sale branded term excluded
    drafts = _draft(search_terms=SEARCH_TERMS, brand_terms=["acme"])
    d = next(x for x in drafts if "your own brand" in x["action_text"])
    assert "$125" in d["action_text"] and "25–60%" in d["action_text"]
    assert d["expected_impact_usd"] == 50.0           # 0.4 midpoint
    assert d["action_text"].endswith("and the Profit Record measures the truth.")   # the name in force
    assert "Ledger" not in d["action_text"]
    # no brand terms -> no directive
    assert not any("your own brand" in x["action_text"] for x in _draft())


def test_resolve_brand_terms_prefers_explicit_then_derives():
    assert resolve_brand_terms({"brand_terms": "Acme, Acme Labs", "company_name": "X"}) == ["acme", "acme labs"]
    assert resolve_brand_terms({"brand_terms": None, "company_name": "Acme Goods LLC"}) == ["acme", "goods"]


def test_bleed_trim_and_margin_loser_survive():
    drafts = _draft()
    texts = " ".join(d["action_text"] for d in drafts)
    assert "zero attributed sales" in texts and "Over" in texts
    assert "LOSER sold at a loss" in texts
    assert drafts == sorted(drafts, key=lambda d: d["score"], reverse=True)


# ── the measurement contract (Phase 1) ───────────────────────────────────────
# A directive that carries only prose and a number can never be measured from a
# later export, which is why the ledger sat at zero. These assert the structured
# half is always present and always stable.

def test_every_draft_carries_a_measurement_subject():
    drafts = _draft(search_terms=SEARCH_TERMS, brand_terms=["acme"])
    assert drafts
    for d in drafts:
        assert d["kind"], f"no measurement family on: {d['action_text'][:60]}"
        assert d["dedupe_key"] and len(d["dedupe_key"]) == 16
        assert isinstance(d["evidence"], dict) and d["evidence"]
        assert d["mandate"] in ("standing", "explicit")


def test_dedupe_key_is_stable_across_runs_and_unique_within_one():
    a = _draft(search_terms=SEARCH_TERMS, brand_terms=["acme"])
    b = _draft(search_terms=SEARCH_TERMS, brand_terms=["acme"])
    keys = [d["dedupe_key"] for d in a]
    # Same findings, same keys: the weekly sweep re-drafting identical data must
    # not open a second directive for the same problem.
    assert keys == [d["dedupe_key"] for d in b]
    assert len(keys) == len(set(keys))


def test_price_step_inside_the_cap_is_standing_and_a_bigger_move_is_explicit():
    d = next(x for x in _draft() if x["kind"] == "price_step" and x["evidence"]["sku"] == "RISKY")
    # terms.html §6 authorises steps up to 5%; price_move already caps there.
    assert d["mandate"] == "standing"
    assert abs(d["evidence"]["p_new"] / d["evidence"]["p0"] - 1) <= 0.05 + 1e-9
    # The fit and its uncertainty travel with the directive so the later
    # counterfactual is rebuilt from the numbers that made the promise.
    assert d["evidence"]["elasticity"] == -2.0 and d["evidence"]["ci95"] == [-2.4, -1.6]
    assert d["evidence"]["baseline_units"] == 100


def test_bleed_evidence_names_the_terms_and_their_campaign():
    d = next(x for x in _draft() if x["kind"] == "ad_bleed_terms")
    assert d["evidence"]["terms"] == [
        {"campaign_name": "Over", "search_term": "waste", "spend": 100.0, "clicks": 40}
    ]
    # The campaign is what proves the saving came from the negative match
    # rather than the whole campaign being switched off.
    assert d["evidence"]["baseline_spend"] == 100.0


def test_campaign_trim_promises_the_net_saving_not_the_gross():
    d = next(x for x in _draft() if x["kind"] == "campaign_trim")
    gross = (90.0 - 60.0) * 30
    # Those dollars were buying something; without a marginal ROAS on file the
    # net equals the gross, but the arithmetic that discounts it is recorded.
    assert d["evidence"]["avg_margin"] > 0
    assert d["expected_impact_usd"] is not None and d["expected_impact_usd"] <= gross


def test_loss_making_sku_carries_all_three_exit_routes_baselines():
    d = next(x for x in _draft() if x["kind"] == "negative_margin_sku")
    ev = d["evidence"]
    # reprice / cut ads / exit are three different measurements, and each needs
    # a different baseline read from this same row.
    assert ev["sku"] == "LOSER" and ev["baseline_net"] == -450.0
    assert ev["baseline_units"] == 30 and ev["baseline_revenue"] == 3000.0
    assert "baseline_ad_spend" in ev


def test_a_step_the_engine_capped_at_five_percent_stays_inside_the_mandate():
    """price_move caps the ratio at STEP_CAP and then rounds to cents, so a move
    held at exactly 5% can read as 5.002%. Sending that back to the client for a
    signature asks them to re-authorise something they already did."""
    from hubricon_engine.directives import _pricing_directive
    fit = {"level": "sku", "item_id": "CAPPED", "status": "ok", "elasticity": -3.0,
           "details": {"ci95": [-3.2, -2.8]}}
    # p* is far below p0, so the engine clamps the move to the full 5% down.
    margin = {"sku": "CAPPED", "period_start": "2026-07-01", "units": 100,
              "revenue": 2399.0, "amazon_fees": 300.0, "cogs": 500.0, "net_margin": 400.0}
    d = _pricing_directive(fit, margin)
    assert d["evidence"]["p0"] == 23.99 and d["evidence"]["p_new"] == 22.79
    assert abs(d["evidence"]["p_new"] / d["evidence"]["p0"] - 1) > 0.05    # 5.002% after rounding
    assert d["mandate"] == "standing"


def test_a_genuinely_larger_step_still_needs_an_explicit_yes():
    from hubricon_engine.directives import _draft
    big = _draft("pricing", "price_step", "X", 1, 100.0, "t",
                 {"p0": 10.0, "p_new": 11.0}, mandate="explicit")
    assert big["mandate"] == "explicit"


# ── the downside guard ────────────────────────────────────────────────────

def _guard_fixture(monthly_net, delta_p5):
    """A drafted price step with a known 5th-percentile outcome and a SKU with a
    known monthly net, so the guard can be exercised directly."""
    from hubricon_engine.directives import _draft

    units, price = 100.0, 20.0
    revenue = units * price
    margin_row = {"sku": "G1", "units": units, "revenue": revenue,
                  "amazon_fees": 0.0, "cogs": revenue - monthly_net,
                  "net_margin": monthly_net,
                  "period_start": "2026-07-01", "period_end": "2026-07-30"}
    draft = _draft("pricing", "price_step", "G1", 20.0, 50.0, "move it",
                   {"sku": "G1", "delta_p5": delta_p5})
    return draft, margin_row


def test_downside_guard_leaves_a_small_risk_inside_the_standing_mandate():
    from hubricon_engine.directives import downside_guard

    draft, row = _guard_fixture(monthly_net=2000.0, delta_p5=-100.0)
    out = downside_guard(draft, row)
    assert out["mandate"] == "standing"
    guard = out["evidence"]["downside_guard"]
    assert guard["within_budget"] is True
    assert guard["budget_usd"] == pytest.approx(300.0)     # 15% of $2,000
    assert guard["downside_usd"] == pytest.approx(100.0)


def test_downside_guard_routes_a_large_risk_to_an_explicit_yes():
    """Regardless of step size: the guard is about the size of the bad case, not
    the size of the move."""
    from hubricon_engine.directives import downside_guard

    draft, row = _guard_fixture(monthly_net=2000.0, delta_p5=-700.0)
    out = downside_guard(draft, row)
    assert out["mandate"] == "explicit"
    assert out["evidence"]["downside_guard"]["within_budget"] is False
    assert "worst realistic case" in out["mandate_reason"]
    assert "$300" in out["mandate_reason"]                 # the budget, in words


def test_downside_guard_treats_a_positive_fifth_percentile_as_no_risk():
    from hubricon_engine.directives import downside_guard

    draft, row = _guard_fixture(monthly_net=2000.0, delta_p5=25.0)
    out = downside_guard(draft, row)
    assert out["mandate"] == "standing"
    assert out["evidence"]["downside_guard"]["downside_usd"] == 0.0


def test_downside_guard_gives_a_loss_making_sku_no_budget_at_all():
    """A SKU already losing money has no monthly net to risk, so any quantified
    downside needs a signature."""
    from hubricon_engine.directives import downside_guard

    draft, row = _guard_fixture(monthly_net=-400.0, delta_p5=-10.0)
    out = downside_guard(draft, row)
    assert out["evidence"]["downside_guard"]["budget_usd"] == 0.0
    assert out["mandate"] == "explicit"


def test_downside_guard_does_not_invent_a_downside_it_was_not_given():
    """A draft with no simulated distribution is left alone. Gating on a number
    the engine would have had to make up is the thing it does not do."""
    from hubricon_engine.directives import _draft, downside_guard

    draft = _draft("advertising", "campaign_trim", "C", 10.0, 500.0, "trim it",
                   {"campaign_name": "C"})
    out = downside_guard(draft, {"units": 1, "revenue": 1.0, "net_margin": 1000.0,
                                 "period_start": "2026-07-01", "period_end": "2026-07-30"})
    assert out["mandate"] == "standing"
    assert "downside_guard" not in out["evidence"]


def test_every_drafted_price_step_carries_the_guard_and_the_solver_makes_it_slack():
    """End to end, and the finding is the relationship between the two rules.

    The step size is already solved against the same risk budget, so by the time
    a price step is drafted its 5th-percentile outcome is normally a GAIN — on
    this eight-SKU catalog every one of them is. The guard is therefore slack in
    normal operation, which is the designed outcome: it is a backstop against a
    directive arriving from anywhere else, not the thing that sizes the move.
    What matters is that every step carries its own downside on the record so the
    claim is checkable rather than asserted."""
    import numpy as np

    from hubricon_engine.models import elasticity, margin
    from hubricon_engine.models.pricing_engine import RISK_BUDGET_SHARE
    from hubricon_engine.directives import DOWNSIDE_GUARD_SHARE

    # one constant, two enforcement points: how far to walk, and whether we may
    # walk without asking
    assert DOWNSIDE_GUARD_SHARE == RISK_BUDGET_SHARE

    rng = np.random.default_rng(4)
    econ = []
    for i in range(8):
        prices = 20.0 * np.exp(rng.normal(0, 0.12, size=8))
        units = 300.0 * (prices / 20.0) ** -2.6 * np.exp(rng.normal(0, 0.2, size=8))
        for j, (p, u) in enumerate(zip(prices, units), start=1):
            revenue = float(p) * float(u)
            econ.append({"sku": f"D{i}", "asin": f"B0D{i}",
                         "period_start": f"2026-{j:02d}-01", "period_end": f"2026-{j:02d}-28",
                         "units_sold": float(u), "avg_sales_price": float(p),
                         "sales": revenue, "referral_fees": -0.15 * revenue,
                         "fba_fulfillment_fees": -1.5 * float(u), "storage_fees": 0.0,
                         "other_fees": 0.0, "net_proceeds": revenue})
    data = {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [],
            "cogs_inputs": [{"sku": f"D{i}", "asin": f"B0D{i}", "unit_cost_usd": 5.0}
                            for i in range(8)]}
    margins = margin.run(data)
    fits = elasticity.run(data)
    steps = [d for d in draft_directives([], [], fits, margins) if d["kind"] == "price_step"]
    assert len(steps) >= 5

    for d in steps:
        guard = d["evidence"]["downside_guard"]
        assert guard["trailing_monthly_net"] > 0
        assert guard["delta_p5"] is not None
        assert guard["share"] == DOWNSIDE_GUARD_SHARE
        # the solver already refused anything whose bad case was a material loss
        assert guard["within_budget"] is True
        assert guard["downside_usd"] == 0.0
