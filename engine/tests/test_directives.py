from hubricon_engine.directives import draft_directives

INVENTORY = [
    {"sku": "RISKY", "stockout_probability": 0.62, "reorder_qty": 740, "reorder_point": 690, "lead_time_days": 38},
    {"sku": "SAFE", "stockout_probability": 0.05, "reorder_qty": 100, "reorder_point": 90, "lead_time_days": 30},
]
ADS = [
    {"campaign_name": "Over", "status": "ok", "current_spend": 90.0, "breakeven_spend": 60.0,
     "bleed_terms": [{"search_term": "waste", "spend": 100.0, "clicks": 40}]},
    {"campaign_name": "Fine", "status": "ok", "current_spend": 40.0, "breakeven_spend": 60.0, "bleed_terms": []},
]
ELASTICITY = [
    {"level": "sku", "item_id": "INELASTIC", "status": "ok", "elasticity": -0.5},
    {"level": "sku", "item_id": "ELASTIC", "status": "ok", "elasticity": -1.9},
    {"level": "sku", "item_id": "FLAT", "status": "insufficient_price_variation", "elasticity": None},
]
MARGINS = [
    {"sku": "INELASTIC", "period_start": "2026-07-01", "revenue": 10000.0, "net_margin": 2000.0},
    {"sku": "LOSER", "period_start": "2026-07-01", "revenue": 3000.0, "net_margin": -450.0},
    {"sku": "LOSER", "period_start": "2026-06-01", "revenue": 3200.0, "net_margin": -300.0},  # older period ignored
]


def test_drafts_cover_all_modules_and_thresholds():
    drafts = draft_directives(INVENTORY, ADS, ELASTICITY, MARGINS)
    by_module = {}
    for d in drafts:
        by_module.setdefault(d["module"], []).append(d)

    assert [d for d in by_module["inventory"] if "RISKY" in d["action_text"]]
    assert not any("SAFE" in d["action_text"] for d in drafts)  # below alert threshold

    ad_texts = " ".join(d["action_text"] for d in by_module["advertising"])
    assert "bleed" in ad_texts and "Over" in ad_texts
    assert "Fine" not in ad_texts  # under break-even, no trim directive

    pricing = by_module["pricing"]
    assert len(pricing) == 1 and "INELASTIC" in pricing[0]["action_text"]  # elastic + flat excluded

    assert [d for d in by_module["margin"] if "LOSER" in d["action_text"]]


def test_expected_impacts_are_computed_honestly():
    drafts = draft_directives(INVENTORY, ADS, ELASTICITY, MARGINS)
    bleed = next(d for d in drafts if "bleed" in d["action_text"])
    assert bleed["expected_impact_usd"] == 100.0
    trim = next(d for d in drafts if "Trim" in d["action_text"])
    assert trim["expected_impact_usd"] == 30.0 * 30  # excess/day over the 30-day horizon
    price = next(d for d in drafts if d["module"] == "pricing")
    assert price["expected_impact_usd"] == 300.0  # 3% of $10k latest revenue
    stockout = next(d for d in drafts if d["module"] == "inventory")
    assert stockout["expected_impact_usd"] is None  # not honestly computable -> stays empty


def test_ranked_most_severe_first():
    drafts = draft_directives(INVENTORY, ADS, ELASTICITY, MARGINS)
    assert drafts == sorted(drafts, key=lambda d: d["score"], reverse=True)
