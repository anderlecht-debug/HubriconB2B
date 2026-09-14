"""Proof: the ledger's verified events become cards, and the cards become one
guarded sentence. The tests that matter are the ones that refuse: nothing from
the gate's bar, nothing without consent, no number the ledger did not supply."""

from hubricon_engine import narrate, proof
from fakedb import FakeDB

CLIENT = {"id": "c1", "platform": "amazon", "industry": "kitchen", "revenue_band": "$1M–$5M",
          "billing_decision": None, "retainer_started_at": "2026-08-01"}


def _ledger(total, multiple=None, identified=0.0):
    return {"value_total": total, "roi_multiple": multiple, "identified_unbanked": identified, "as_of": "2026-09-08"}


def test_the_gate_answer_reads_the_booking_string_in_both_shapes():
    assert proof.revenue_band_from_answers({"utm": "rev:$1M–$5M|model:Private label|fit:core"}) == "$1M–$5M"
    assert proof.revenue_band_from_answers({"rev": "Under $1M"}) == "under $1M"
    # the chips since the floor moved to $3M, and the retired ones still read
    assert proof.revenue_band_from_answers({"utm": "rev:$3M–$5M|model:Private label|fit:core"}) == "$3M–$5M"
    assert proof.revenue_band_from_answers({"rev": "Under $3M"}) == "under $3M"
    assert proof.revenue_band_from_answers({"utm": "rev:$5M–$20M|fit:core"}) == "$5M–$20M"
    assert proof.revenue_band_from_answers({"utm": "model:x"}) is None
    assert proof.revenue_band_from_answers(None) is None


def test_only_a_claim_we_filed_is_a_first_recovered_result():
    claims = [
        {"id": "k1", "status": "paid", "paid_amount": 400.0, "paid_at": "2026-09-01", "claim_type": "lost"},          # Amazon's own
        {"id": "k2", "status": "paid", "paid_amount": 250.0, "paid_at": "2026-09-03", "filed_at": "2026-08-20",
         "claim_type": "damaged"},
        {"id": "k3", "status": "paid", "paid_amount": 900.0, "paid_at": "2026-09-05", "case_id": "X", "claim_type": "lost"},
    ]
    rows = proof.detect(CLIENT, _ledger(1150.0), [], claims)
    first = [r for r in rows if r["kind"] == "first_recovered"]
    assert len(first) == 1 and first[0]["source_ref"] == "k2" and first[0]["amount_usd"] == 250.0
    assert first[0]["how_we_know"] == "recovered" and first[0]["industry"] == "kitchen"


def test_direct_measurements_are_one_card_each_and_other_tiers_are_not():
    directives = [
        {"id": "d1", "attribution": "direct", "measured_impact_usd": 320.0, "module": "pricing"},
        {"id": "d2", "attribution": "isolated", "measured_impact_usd": 500.0, "module": "pricing"},
        {"id": "d3", "attribution": "direct", "measured_impact_usd": 0.0, "module": "ads"},
    ]
    rows = proof.detect(CLIENT, _ledger(820.0), directives, [])
    direct = [r for r in rows if r["kind"] == "direct_measured"]
    assert [r["source_ref"] for r in direct] == ["d1"] and direct[0]["mechanism"] == "pricing"


def test_the_gate_bar_is_not_the_proof_bar():
    """billing.verdict counts identified-but-unbanked value; a card must not."""
    cleared = {**CLIENT, "billing_decision": "cleared"}
    assert proof.detect(cleared, _ledger(0.0, identified=9000.0), [], []) == []
    rows = proof.detect(cleared, _ledger(7000.0, multiple=1.2), [], [])
    assert [r["kind"] for r in rows] == ["gate_cleared"] and rows[0]["source_ref"] == "2026-08-01"


def test_five_times_supersedes_three_times_and_the_month_is_the_key():
    rows = proof.detect(CLIENT, _ledger(30000.0, multiple=5.0), [], [])
    assert [r["kind"] for r in rows] == ["roi_5x"] and rows[0]["source_ref"] == "2026-09"
    rows = proof.detect(CLIENT, _ledger(18000.0, multiple=3.0), [], [])
    assert [r["kind"] for r in rows] == ["roi_3x"]
    assert proof.detect(CLIENT, _ledger(6000.0, multiple=1.0), [], []) == []


def test_record_writes_each_event_once_and_never_touches_an_existing_row():
    db = FakeDB(results=[{"id": "r0", "client_id": "c1", "kind": "roi_3x", "source_ref": "2026-09",
                          "published": True}])
    rows = proof.detect(CLIENT, _ledger(18000.0, multiple=3.0), [], [
        {"id": "k2", "status": "paid", "paid_amount": 250.0, "filed_at": "2026-08-20", "claim_type": "damaged"}])
    assert proof.record(db, rows) == 1                      # roi_3x already there; first_recovered is new
    assert proof.record(db, rows) == 0
    assert db.rows("results")[0]["published"] is True       # untouched


def test_publish_flips_only_consented_clients():
    db = FakeDB(
        results=[{"id": "r1", "client_id": "c1", "published": False},
                 {"id": "r2", "client_id": "c2", "published": False}],
        consents=[{"client_id": "c1", "kind": "anonymised_results", "granted": True},
                  {"client_id": "c2", "kind": "anonymised_results", "granted": False}],
    )
    assert proof.publish(db) == 1
    by = {r["id"]: r for r in db.rows("results")}
    assert by["r1"]["published"] is True and by["r1"]["published_at"]
    assert by["r2"]["published"] is False
    assert proof.publish(db) == 0


def test_the_proof_line_is_none_until_there_is_something_to_prove():
    assert proof.line_from([]) is None
    db = FakeDB()
    db.rpcs["public_results"] = lambda: []
    assert proof.line(db) is None


def test_one_result_names_the_brand_by_category_and_band_and_never_by_name():
    line = proof.line_from([{"industry": "kitchen", "revenue_band": "$1M–$5M", "amount_usd": 12300}])
    assert "kitchen brand" in line and "$1M–$5M" in line and "$12,300" in line
    assert "hubricon.com/results" in line
    assert "Test" not in line


def test_many_results_are_counted_and_summed():
    rows = [{"industry": "kitchen", "revenue_band": "$1M–$5M", "amount_usd": 12300},
            {"industry": "pet", "revenue_band": "$5M–$20M", "amount_usd": 4100}]
    line = proof.line_from(rows)
    assert line.startswith("2 brands") and "$16,400" in line


def test_the_templates_carry_no_number_the_guard_would_reject():
    facts = proof.facts([{"industry": "pet", "revenue_band": "$5M–$20M", "amount_usd": 100}])
    for template in (proof.ONE_RESULT, proof.MANY_RESULTS):
        assert narrate.validate(template, facts) == []


def test_a_template_edit_that_smuggles_a_number_in_is_refused(monkeypatch):
    monkeypatch.setattr(proof, "ONE_RESULT", "Three brands found $10k. {{proof_url}}")
    try:
        proof.line_from([{"industry": "pet", "revenue_band": "x", "amount_usd": 100}])
    except ValueError as err:
        assert "number guard" in str(err)
    else:
        raise AssertionError("a digit outside a placeholder must not render")


def test_set_profile_accepts_only_the_fixed_vocabulary_and_backfills_cards():
    db = FakeDB(clients=[{"id": "c1"}], results=[{"id": "r1", "client_id": "c1", "industry": None}])
    try:
        proof.set_profile(db, "c1", industry="widgets")
    except ValueError as err:
        assert "industry must be one of" in str(err)
    else:
        raise AssertionError("unknown industry accepted")
    patch = proof.set_profile(db, "c1", industry="Kitchen", revenue_band="$1m-$5m")
    assert patch == {"industry": "kitchen", "revenue_band": "$1M–$5M"}
    assert db.rows("results")[0]["industry"] == "kitchen"
