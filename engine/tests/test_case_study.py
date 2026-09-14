"""The case study refuses before it publishes. Every test here is a reason
index.html §3b stays empty, and one is the day it does not."""

from datetime import date

from fakedb import FakeDB
from hubricon_engine import case_study

TODAY = date(2026, 11, 1)
CLIENT = {"id": "c1", "company_name": "Riverbend Kitchen", "contact_email": "ada@riverbend.com",
          "industry": "kitchen", "platform": "amazon", "retainer_started_at": "2026-09-01T00:00:00Z",
          "monthly_fee_usd": 6000}
DIRECTIVES = [
    {"id": "d1", "status": "done", "executed_at": "2026-09-05T00:00:00Z",
     "action_text": "Negative-matched 11 search terms on RB-GARLIC-02", "expected_impact_usd": 6200,
     "measured_impact_usd": 6200, "measurement_notes": "Measured $6,840 on the exact lines, booked at $6,200",
     "evidence": {"sku": "RB-GARLIC-02"}},
    {"id": "d2", "status": "done", "executed_at": "2026-09-09T00:00:00Z",
     "action_text": "Price step +4% on B0C1234XYZ", "expected_impact_usd": 3400, "measured_impact_usd": 2150,
     "measurement_notes": "Measured against the stated baseline", "evidence": {"asin": "B0C1234XYZ"}},
    {"id": "d3", "status": "issued", "action_text": "Not made yet", "expected_impact_usd": 9999},
]
CLAIMS = [{"id": "k1", "claim_type": "lost_inventory", "units": 3, "sku": "RB-GARLIC-02", "status": "paid",
           "filed_at": "2026-09-12T00:00:00Z", "case_id": "123", "expected_value": 900, "paid_amount": 840,
           "eligible_from": "2026-08-01", "deadline": "2026-12-01"}]
CONSENTS = [{"kind": "testimonial", "granted": True, "testimonial": "I stopped guessing on reorders.",
             "before_text": "Sunday nights were five reports and a spreadsheet nobody trusted."},
            {"kind": "named_results", "granted": True},
            {"kind": "anonymised_results", "granted": True}]


def _draft(consents=CONSENTS, directives=DIRECTIVES, claims=CLAIMS, today=TODAY, **kw):
    return case_study.draft(CLIENT, directives, claims, consents, [], today, **kw)


def test_a_closed_consented_record_with_a_miss_is_publishable_and_masks_every_identifier():
    row, problems = _draft()
    assert problems == []
    assert row["brand_name"] == "Riverbend Kitchen"
    text = " ".join(r["move"] + " " + r["how"] for r in row["record"])
    assert "RB-GARLIC-02" not in text and "B0C1234XYZ" not in text
    assert "RB••" in text and "B0••" in text
    assert any(r["miss"] and r["expected"] == 3400 and r["measured"] == 2150 for r in row["record"])
    assert "Not made yet" not in text                                    # issued is not made: not on the Record
    assert [n["label"] for n in row["numbers"]] == ["Found", "Proven", "Measured against"]
    assert row["numbers"][0]["amount_usd"] == 6200 + 3400 + 900
    assert row["numbers"][1]["amount_usd"] == 6200 + 2150 + 840            # measured, plus what Amazon paid
    assert row["quote"] == CONSENTS[0]["testimonial"] and row["before_text"] == CONSENTS[0]["before_text"]
    assert row["proving_month_closed_on"] == "2026-10-01"


def test_the_proving_month_has_to_have_closed():
    _, problems = _draft(today=date(2026, 9, 20))
    assert any("closes on 2026-10-01" in p for p in problems)


def test_the_quote_and_the_before_state_are_the_clients_own_or_nothing():
    long_quote = " ".join(["word"] * 31)
    _, problems = _draft(consents=[{**CONSENTS[0], "testimonial": long_quote, "before_text": ""}, *CONSENTS[1:]])
    assert any("31 words" in p for p in problems) and any("before-state" in p for p in problems)
    _, problems = _draft(consents=[{**CONSENTS[0], "granted": False}, *CONSENTS[1:]])
    assert any("testimonial consent" in p for p in problems)


def test_anonymised_consent_publishes_without_the_brand_and_no_consent_publishes_nothing():
    row, problems = _draft(consents=[CONSENTS[0], {"kind": "anonymised_results", "granted": True}])
    assert problems == [] and row["brand_name"] is None
    _, problems = _draft(consents=[CONSENTS[0]])
    assert any("publication not granted" in p for p in problems)


def test_a_record_with_no_miss_is_refused_unless_that_really_is_the_whole_record():
    clean = [DIRECTIVES[0]]
    claims = [{**CLAIMS[0], "paid_amount": 900}]
    _, problems = _draft(directives=clean, claims=claims)
    assert any("no recorded miss" in p for p in problems)
    _, problems = _draft(directives=clean, claims=claims, allow_no_miss=True)
    assert problems == []


def test_publish_writes_nothing_while_a_rule_fails_and_one_row_when_none_do():
    owned = lambda rows: [{**r, "client_id": "c1"} for r in rows]  # noqa: E731 — load() reads by client
    db = FakeDB(clients=[CLIENT], directives=owned(DIRECTIVES), recovery_claims=owned(CLAIMS),
                consents=owned(CONSENTS[:1]), invoices=[], case_studies=[], funnel_events=[])
    _, problems = case_study.publish(db, "c1", today=TODAY)
    assert problems == ["publication not granted: neither named_results nor anonymised_results"]
    assert db.rows("case_studies") == []
    db.store["consents"] = owned(CONSENTS)
    _, problems = case_study.publish(db, "c1", today=TODAY)
    assert problems == [] and len(db.rows("case_studies")) == 1
    assert db.rows("case_studies")[0]["published"] is True
    assert db.rows("funnel_events")[-1]["kind"] == "case_study_published"
    case_study.unpublish(db, "c1")
    assert db.rows("case_studies")[0]["published"] is False
