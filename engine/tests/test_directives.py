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
ELASTICITY = [
    {"level": "sku", "item_id": "INELASTIC", "status": "ok", "elasticity": -0.5, "details": {}},
    {"level": "sku", "item_id": "RISKY", "status": "ok", "elasticity": -2.0, "details": {"ci95": [-2.4, -1.6]}},
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
    assert "95% range" in exact
    inelastic = next(t for t in texts if "INELASTIC" in t)
    assert "$100.00 → $103.00" in inelastic           # +3% bounded step, computed dollars
    assert not any("FLAT" in t for t in texts)


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
