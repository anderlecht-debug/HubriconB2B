from hubricon_engine import narrate

FACTS = {
    "first_name": {"value": "Dana", "label": "client first name"},
    "net_latest": {"value": "$4,842", "label": "net profit"},
    "moves_before_they_go_live": {"value": "2", "label": "moves"},
}


def test_validate_catches_every_way_a_number_sneaks_in():
    assert narrate.validate("Dear {{first_name}}, profit was {{net_latest}}.", FACTS) == []
    assert "digits" in " ".join(narrate.validate("You earned $4,842 last month.", FACTS))
    assert "number words" in " ".join(narrate.validate("Roughly half of it came from two SKUs.", FACTS))
    assert "unknown placeholder" in " ".join(narrate.validate("See {{made_up_key}}.", FACTS))
    assert "currency" in " ".join(narrate.validate("Margins moved by a few %.", FACTS))
    assert "empty" in " ".join(narrate.validate("   ", FACTS))


def test_render_substitutes_only_known_placeholders():
    assert narrate.render("Dear {{first_name}}, {{net_latest}} on {{ moves_before_they_go_live }} decisions.", FACTS) == \
        "Dear Dana, $4,842 on 2 decisions."


def test_narrate_retries_once_then_renders():
    drafts = iter(["Dear Dana, you made $4,842.", "Dear {{first_name}}, you made {{net_latest}}."])
    calls = []

    def fake(system, prompt, model):
        calls.append(prompt)
        return next(drafts)

    out = narrate.narrate(FACTS, call=fake, model="test-model")
    assert out["attempts"] == 2 and out["reason"] is None
    assert out["text"] == "Dear Dana, you made $4,842."
    assert "rejected by the number guard" in calls[1]


def test_narrate_falls_back_when_the_guard_keeps_failing_or_the_call_errors():
    out = narrate.narrate(FACTS, call=lambda s, p, m: "It was 12 units.", model="t")
    assert out["text"] is None and "number guard" in out["reason"] and out["attempts"] == 2

    def boom(s, p, m):
        raise RuntimeError("no network")

    out = narrate.narrate(FACTS, call=boom, model="t")
    assert out["text"] is None and "no network" in out["reason"] and out["attempts"] == 1


def test_build_facts_only_emits_formatted_strings():
    deltas = {"period": "2026-08-01", "latest": {"net": 4842.4, "revenue": 30210.0, "pct": 0.1603},
              "prior": {"net": 4000, "revenue": 29000, "pct": 0.138}, "net_delta": 842.4, "revenue_delta": 1210.0}
    facts = narrate.build_facts("Dry Run Co", "Dana", deltas,
                                [{"status": "issued", "action_text": "Move X", "expected_impact_usd": 120.6}],
                                [{"severity": "critical", "message": "Cash pinch"}], 2977.0, 6, 3,
                                health={"status": "ok", "score": 71.4, "grade": "B",
                                        "top_drivers": [{"label": "Margin health", "dollars_at_stake": 300}]},
                                value={"value_total": 2977, "fees_paid": 0, "roi_multiple": None, "identified_unbanked": 900})
    assert all(isinstance(v["value"], str) for v in facts.values())
    assert facts["net_latest"]["value"] == "$4,842" and facts["margin_pct_latest"]["value"] == "16.0%"
    assert facts["health_score"]["value"] == "71" and facts["decision_1_expected"]["value"] == "$121 per period"
    assert facts["net_direction"]["value"] == "up"
    assert facts["moves_before_they_go_live"]["value"] == "1" and "decisions_on_desk" not in facts
    assert facts["value_total"]["label"] == "proven to date on the Profit Record (moves + recovered)"
    assert facts["identified_unbanked"]["label"] == "found and filed, not yet measured or paid"
    labels = " ".join(f["label"] for f in facts.values())
    assert "directive" not in labels and "ledger" not in labels.lower().replace("profit record", "")
