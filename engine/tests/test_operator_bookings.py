"""The hourly bookings pass, on the fake database: a client's own kickoff is
their follow-up call, not an application, so it is linked and nothing is sent;
every other booking is provisioned exactly as before."""

from hubricon_engine import onboarding, operator
from fakedb import FakeDB


def _client():
    return {"id": "c1", "contact_email": "ana@alpha.com", "contact_name": "Ana", "company_name": "Alpha",
            "status": "pending", "platform": "amazon"}


def _booking(event_type, email="ana@alpha.com", bid="b1"):
    return {"id": bid, "invitee_email": email, "invitee_name": "Ana Alpha", "event_type": event_type,
            "starts_at": "2026-10-02T15:00:00Z", "answers": {}, "qualified": True, "is_test": False,
            "provisioned_at": None, "client_id": None, "created_at": "2026-09-30T12:00:00Z"}


def _pass(monkeypatch, db):
    provisioned, touched = [], []

    def fake_provision(_db, email, name=None, company=None, platform=None):
        provisioned.append(email)
        rows = [c for c in db.rows("clients") if c["contact_email"] == email]
        return (rows[0] if rows else {"id": "new", "contact_email": email}), "https://x/intake?t=1", not rows

    monkeypatch.setattr(onboarding, "provision", fake_provision)
    monkeypatch.setattr(operator.Pass, "_touch", lambda self, client, kind, link, force=False: touched.append((kind, force)) or True)
    monkeypatch.setattr(operator.Pass, "_attribute_booking", lambda self, client, b, email: None)
    p = operator.Pass(db, send=True, dry=False)
    return p, provisioned, touched


def test_a_kickoff_from_an_existing_client_is_linked_and_nothing_is_sent(monkeypatch):
    prospect = {"id": "p1", "email": "ana@alpha.com", "status": "engaged", "client_id": "c1"}
    db = FakeDB(clients=[_client()], bookings=[_booking("Hubricon Kickoff — 45 min")], prospects=[prospect],
                funnel_events=[])
    p, provisioned, touched = _pass(monkeypatch, db)
    p.bookings()
    b = db.rows("bookings")[0]
    assert b["client_id"] == "c1" and b["provisioned_at"]
    assert provisioned == [] and touched == []          # no new upload link, no second welcome
    assert db.rows("prospects")[0]["status"] == "engaged"  # the funnel row is left where it was
    assert [e["kind"] for e in db.rows("funnel_events")] == ["kickoff_booked"]
    assert any(h.startswith("Kickoff booked: Ana Alpha") and "no welcome" in h for h in p.human)


def test_a_kickoff_from_an_address_we_do_not_know_is_still_onboarded(monkeypatch):
    db = FakeDB(clients=[], bookings=[_booking("Kick-off call", email="new@beta.com")], prospects=[], funnel_events=[])
    p, provisioned, touched = _pass(monkeypatch, db)
    p.bookings()
    assert provisioned == ["new@beta.com"] and touched == [("welcome", True)]


def test_any_other_booking_from_an_existing_client_is_provisioned_as_before(monkeypatch):
    db = FakeDB(clients=[_client()], bookings=[_booking("Profit Teardown call")], prospects=[], funnel_events=[])
    p, provisioned, touched = _pass(monkeypatch, db)
    p.bookings()
    assert provisioned == ["ana@alpha.com"] and touched == [("welcome", True)]
    assert db.rows("bookings")[0]["client_id"] == "c1"


def test_the_kickoff_pattern_is_the_one_the_unit_economics_count():
    from hubricon_engine import economics
    assert economics.KICKOFF is onboarding.KICKOFF_EVENT
    assert all(onboarding.KICKOFF_EVENT.search(s) for s in ("Kickoff", "kick-off call", "Hubricon KICK OFF"))
    assert not onboarding.KICKOFF_EVENT.search("Profit Teardown call")
