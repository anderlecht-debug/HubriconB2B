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
    # One Profit Record figure: the ledger's own total is not offered beside it.
    assert "value_total" not in facts and "ledger_measured" not in facts
    assert facts["proven"]["value"] == "$2,977" and facts["proven_basis"]["value"] == "measured so far"
    # ledger_count is what it counts: moves measured, not moves issued.
    assert facts["ledger_count"] == {"value": "6", "label": "number of moves measured on the Profit Record to date"}
    assert facts["identified_unbanked"]["label"] == "found and filed, not yet measured or paid"
    labels = " ".join(f["label"] for f in facts.values())
    assert "directive" not in labels and "ledger" not in labels.lower().replace("profit record", "")


def test_the_letter_names_the_records_one_figure_on_either_basis():
    """The narrated letter takes the same figure as the subject, the footer and
    the portal: the closed months once there are any, and the multiple is that
    figure over what was billed, never the ledger's own total."""
    ledger = {"value_total": 9000, "fees_paid": 6000, "fees_billed": 6000, "roi_multiple": 1.5,
              "identified_unbanked": 400, "value_interval_basis": {"banded_share_of_measured": 1.0},
              "value_p5": 8000, "value_p95": 9500}
    months = {"usd": 7200.0, "basis": "months", "label": "Proven on your Profit Record since day one",
              "moves": 3, "by_attribution": {"direct": 1200.0, "isolated": 6000.0}}
    facts = narrate.build_facts("Acme", "Ann", None, [], [], 1.0, 1, 4, value=ledger, proven=months)
    assert facts["proven"]["value"] == "$7,200" and facts["proven_basis"]["value"] == "proven since day one"
    assert facts["ledger_count"]["value"] == "3"
    assert facts["roi_multiple"]["value"] == "1.2×" and facts["fees_billed"]["value"] == "$6,000"
    assert "value_range" not in facts                     # the band belongs to the measured figure only
    assert facts["measured_direct"]["value"] == "$1,200" and facts["measured_isolated"]["value"] == "$6,000"
    # A dispute took dollars off a month: the per-move split no longer adds up, so none is offered.
    disputed = {**months, "usd": 6700.0, "by_attribution": None}
    facts = narrate.build_facts("Acme", "Ann", None, [], [], 1.0, 1, 4, value=ledger, proven=disputed)
    assert facts["proven"]["value"] == "$6,700" and not any(k.startswith("measured_") for k in facts)
    early = {"usd": 900.0, "basis": "measured", "label": "Measured so far · your first month closes November 1",
             "moves": 1, "by_attribution": None}
    facts = narrate.build_facts("Acme", "Ann", None, [], [], 1.0, 1, 2, proven=early)
    assert facts["proven_basis"]["value"] == "measured so far; your first month closes November 1"
    assert "{{proven}} {{proven_basis}}" in narrate.LETTER_STRUCTURE
