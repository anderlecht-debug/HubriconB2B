"""The loop as rates, and the two attributions that join a reply or a booking
to the teardown that earned it."""

from hubricon_engine import loop
from fakedb import FakeDB


def test_rates_are_zero_safe_and_chain_from_the_prior_stage():
    s = {"contacted": 200, "replied": 10, "interested": 4, "bookings": 2, "teardowns_delivered": 2, "paid": 1}
    r = dict((stage, (n, pct)) for stage, n, pct in loop.rates(s))
    assert r["contacted"] == (200, None)
    assert r["replied"] == (10, 0.05)
    assert r["paid"] == (1, 0.5)
    assert r["renewed"] == (0, 0.0)
    assert r["asks_sent"] == (0, 0.0)
    assert r["consent_granted"] == (0, None)          # nothing asked yet: no denominator
    assert loop.rates({}) and all(n == 0 for _, n, _ in loop.rates({}))


def test_the_table_and_the_digest_read():
    s = {"contacted": 200, "replied": 10, "asks_sent": 3, "consent_granted": 2, "testimonials": 1,
         "results_published": 2, "referral_links": 2, "referral_booked": 1, "referral_paid": 0,
         "partner_booked": 0, "teardowns_sent": 40, "teardowns_replied": 3, "teardowns_booked": 1,
         "median_hours_to_first_issue": 7.5}
    text = loop.table(s)
    assert "replied" in text and "5.0% of prior" in text and "exports → Issue 001: 7.5" in text
    lines = loop.digest_lines(s)
    assert lines[0] == "The loop past paid" and "consented 2" in lines[1] and "teardowns sent 40" in lines[3]
    assert loop.digest_lines({}) == []


def _db():
    return FakeDB(
        outreach_sends=[{"id": "s1", "teardown_id": "t1", "recipient_email": "dana@brand.com", "sent_at": "2026-09-01"}],
        harvest_sellers=[{"seller_id": "A1", "website": "https://www.otherbrand.com", "email": "hello@otherbrand.com"}],
        teardowns=[{"id": "t2", "prospect_key": "A1", "status": "sent", "created_at": "2026-09-02"}],
        teardown_events=[],
        prospects=[{"id": "p1", "email": "dana@brand.com", "source": "instantly_list"}],
    )


def test_a_reply_from_a_teardown_recipient_is_recorded_once():
    db = _db()
    assert loop.attribute_reply(db, "Dana@Brand.com", "interested") == "t1"
    assert loop.attribute_reply(db, "dana@brand.com", "question") is None
    events = db.rows("teardown_events")
    assert len(events) == 1 and events[0]["kind"] == "reply" and events[0]["detail"]["category"] == "interested"
    assert loop.attribute_reply(db, "nobody@else.com") is None


def test_a_booking_matches_by_address_first_and_by_domain_second():
    db = _db()
    assert loop.attribute_booking(db, "dana@brand.com", "b1") == "t1"
    assert db.rows("prospects")[0]["source"] == "teardown"
    assert loop.attribute_booking(db, "owner@otherbrand.com", "b2") == "t2"
    kinds = [(e["teardown_id"], e["kind"]) for e in db.rows("teardown_events")]
    assert kinds == [("t1", "booked"), ("t2", "booked")]
    assert loop.attribute_booking(db, "owner@otherbrand.com", "b3") is None     # once
