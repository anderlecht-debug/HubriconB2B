"""The ask and the month. What matters: the ask fires at the moment of value
and only once; the credit is paid at the referred client's gate and only
once; a code that matches nobody is reported, never guessed."""

from hubricon_engine import referral
from fakedb import FakeDB


def test_the_ref_code_is_read_from_either_shape_the_routine_stores():
    assert referral.code_from_answers({"utm": "rev:$1M–$5M|fit:core|ref:Ab12cd34"}) == "Ab12cd34"
    assert referral.code_from_answers({"ref": "Ab12cd34"}) == "Ab12cd34"
    assert referral.code_from_answers({"utm": "rev:$1M–$5M"}) is None
    assert referral.code_from_answers({"ref": "<script>"}) is None


def test_ask_due_at_three_times_or_a_recovered_dollar_and_never_twice():
    paid = [{"status": "paid", "paid_amount": 300.0, "filed_at": "2026-08-20"}]
    assert referral.ask_due({"value_total": 18000, "roi_multiple": 3.0}, [], []) is True
    assert referral.ask_due({"value_total": 300, "roi_multiple": None}, paid, []) is True
    assert referral.ask_due({"value_total": 6000, "roi_multiple": 1.0}, [], []) is False
    assert referral.ask_due({"value_total": 0, "roi_multiple": None},
                            [{"status": "paid", "paid_amount": 300.0}], []) is False     # Amazon's own
    answered = [{"kind": "testimonial", "answered_at": "2026-09-01"}]
    assert referral.ask_due({"value_total": 18000, "roi_multiple": 3.0}, [], answered) is False


def _db(**extra):
    db = FakeDB(clients=[{"id": "c1", "company_name": "Alpha", "contact_email": "a@alpha.com"}],
                consents=[], client_touches=[], funnel_events=[], **extra)
    db.rpcs["create_intake_token"] = lambda **kw: []
    db.rpcs["revoke_intake_tokens"] = lambda **kw: []
    return db


def test_a_rehearsal_names_the_ask_and_mints_nothing():
    db = _db()
    client = dict(db.rows("clients")[0])
    blocks = referral.ask_if_due(db, client, {"value_total": 18000, "roi_multiple": 3.0}, [], send=False)
    assert blocks and "would ride" in blocks[0]["p"]
    assert client.get("referral_code") is None


def test_the_ask_carries_the_say_page_and_the_referral_link_once():
    db = _db()
    client = dict(db.rows("clients")[0])
    blocks = referral.ask_if_due(db, client, {"value_total": 18000, "roi_multiple": 3.0}, [], send=True)
    text = " ".join(b.get("p", "") + b.get("url", "") for b in blocks)
    assert "/say/" in text and f"?ref={client['referral_code']}" in text
    assert "testimonial" in text and "next month is on us" in text
    referral.mark_asked(db, client)
    assert {k["kind"] for k in db.rows("consents")} == set(referral.CONSENT_KINDS)
    assert db.rows("client_touches")[0]["kind"] == "consent_ask"
    # asked: nothing rides the next issue
    assert referral.ask_if_due(db, client, {"value_total": 30000, "roi_multiple": 5.0}, [], send=True) == []


def test_a_booking_on_a_clients_link_is_attributed_to_them():
    db = FakeDB(clients=[{"id": "c1", "referral_code": "Ab12cd34", "company_name": "Alpha"},
                         {"id": "c2", "contact_email": "new@brand.com"}],
                partners=[], bookings=[{"id": "b1", "invitee_email": "new@brand.com",
                                        "answers": {"utm": "rev:x|ref:Ab12cd34"}}],
                prospects=[], funnel_events=[])
    hit = referral.attribute(db, dict(db.rows("clients")[1]), db.rows("bookings")[0])
    assert hit["matched"] == "referral" and hit["who"]["company_name"] == "Alpha"
    assert db.rows("clients")[1]["referred_by_client_id"] == "c1"
    assert db.rows("bookings")[0]["ref_code"] == "Ab12cd34"
    p = db.rows("prospects")[0]
    assert p["source"] == "referral" and p["referrer_client_id"] == "c1" and p["status"] == "booked"
    assert db.rows("funnel_events")[0]["kind"] == "referral_booked"


def test_a_partner_code_and_an_unknown_code():
    db = FakeDB(clients=[{"id": "c2", "contact_email": "new@brand.com"}],
                partners=[{"id": "pt1", "code": "books", "name": "A2X Bookkeeping"}],
                bookings=[{"id": "b1", "invitee_email": "new@brand.com", "answers": {"ref": "books"}},
                          {"id": "b2", "invitee_email": "new@brand.com", "answers": {"ref": "nobody99"}}],
                prospects=[], funnel_events=[])
    hit = referral.attribute(db, dict(db.rows("clients")[0]), db.rows("bookings")[0])
    assert hit["matched"] == "partner" and db.rows("clients")[0]["referred_by_partner_id"] == "pt1"
    assert db.rows("prospects")[0]["source"] == "partner"
    assert referral.attribute(db, dict(db.rows("clients")[0]), db.rows("bookings")[1]) == {"code": "nobody99", "matched": None}
    assert referral.attribute(db, {"id": "c2"}, {"id": "b3", "answers": {}}) is None


def test_a_billing_referrer_gets_a_balance_credit_with_an_idempotency_key():
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data, idempotency_key))
        return {"id": "cbtxn_1"}

    db = FakeDB(clients=[
        {"id": "c1", "company_name": "Alpha", "stripe_subscription_id": "sub_1", "stripe_customer_id": "cus_1",
         "monthly_fee_usd": 6000},
        {"id": "c2", "company_name": "Beta", "referred_by_client_id": "c1"},
    ], funnel_events=[])
    credit = referral.credit_referrer(db, dict(db.rows("clients")[1]), stripe=stripe)
    assert credit["how"].startswith("credited") and credit["fee"] == 6000.0
    path, data, key = calls[0]
    assert path == "customers/cus_1/balance_transactions" and data["amount"] == -600000 and key == "referral-c2"
    assert db.rows("clients")[1]["referral_credit_applied_at"]
    assert "Beta" in credit["blocks"][0]["p"]
    # once
    assert referral.credit_referrer(db, dict(db.rows("clients")[1]), stripe=stripe) is None
    assert len(calls) == 1


def test_an_unbilled_referrer_gets_a_further_free_month_instead():
    db = FakeDB(clients=[{"id": "c1", "free_months": 1},
                         {"id": "c2", "referred_by_client_id": "c1"}], funnel_events=[])
    credit = referral.credit_referrer(db, dict(db.rows("clients")[1]), stripe=lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Stripe")))
    assert credit["how"].startswith("added") and db.rows("clients")[0]["free_months"] == 2


def test_a_partner_referral_is_flagged_for_a_human_and_never_auto_paid():
    db = FakeDB(clients=[{"id": "c2", "referred_by_partner_id": "pt1"}], funnel_events=[])
    credit = referral.credit_referrer(db, dict(db.rows("clients")[0]))
    assert credit["partner_id"] == "pt1" and "by hand" in credit["how"]
    assert db.rows("funnel_events")[0]["kind"] == "partner_referral_paid"
    assert referral.credit_referrer(db, {"id": "c9"}) is None
