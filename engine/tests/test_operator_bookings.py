"""The hourly bookings pass, on the fake database.

Since 2026-10-01 a booking is answered with the call prep, never "You're in":
what the call is, the one thing to do before it, and the upload link as an
option. An address that is already a client (a kickoff, a reschedule, a second
booking) is linked and sent nothing. A call prep that did not go out is tried
again while the call is still ahead, and `welcome_sent_at` says, honestly,
whether it went."""

from datetime import datetime, timedelta, timezone

from hubricon_engine import onboarding, operator
from fakedb import FakeDB


def _at(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _client(**kw):
    return {"id": "c1", "contact_email": "ana@alpha.com", "contact_name": "Ana", "company_name": "Alpha",
            "status": "pending", "platform": "amazon", **kw}


def _booking(event_type, email="ana@alpha.com", bid="b1", starts=2.0, **kw):
    return {"id": bid, "invitee_email": email, "invitee_name": "Ana Alpha", "event_type": event_type,
            "starts_at": _at(starts), "answers": {}, "qualified": True, "is_test": False,
            "provisioned_at": None, "client_id": None, "welcome_sent_at": None, "created_at": _at(-1), **kw}


def _pass(monkeypatch, db):
    """A pass whose provisioning and email are recorded, not performed."""
    provisioned, touched = [], []

    def fake_provision(_db, email, name=None, company=None, platform=None):
        provisioned.append(email)
        rows = [c for c in db.rows("clients") if c["contact_email"] == email]
        if rows:
            return rows[0], "https://x/intake?t=1", False
        row = {"id": "new", "contact_email": email, "status": "pending", "platform": platform or "amazon"}
        db.store.setdefault("clients", []).append(row)
        return row, "https://x/intake?t=1", True

    def fake_touch(self, client, kind, link, force=False, stage=None, **ctx):
        touched.append((kind, stage))
        return True

    monkeypatch.setattr(onboarding, "provision", fake_provision)
    monkeypatch.setattr(operator.Pass, "_touch", fake_touch)
    monkeypatch.setattr(operator.Pass, "_attribute_booking", lambda self, client, b, email: None)
    p = operator.Pass(db, send=True, dry=False)
    return p, provisioned, touched


def _mail(monkeypatch, db, ok=True):
    """The real _touch, with Resend replaced: what was sent, to whom, with what."""
    sent = []

    def fake_send(kind, to, first_name, link, portal_url=None, platform="amazon", **ctx):
        sent.append({"kind": kind, "to": to, "link": link, **ctx})
        return ok

    monkeypatch.setattr(onboarding, "send", fake_send)
    monkeypatch.setattr(operator, "email_configured", lambda: True)
    db.rpcs["revoke_intake_tokens"] = lambda **_k: []
    db.rpcs["create_intake_token"] = lambda **_k: []
    monkeypatch.setattr(operator.Pass, "_attribute_booking", lambda self, client, b, email: None)
    return sent


def test_a_kickoff_from_an_existing_client_is_linked_and_nothing_is_sent(monkeypatch):
    prospect = {"id": "p1", "email": "ana@alpha.com", "status": "engaged", "client_id": "c1"}
    db = FakeDB(clients=[_client()], bookings=[_booking("Hubricon Kickoff — 45 min")], prospects=[prospect],
                funnel_events=[])
    p, provisioned, touched = _pass(monkeypatch, db)
    p.bookings()
    b = db.rows("bookings")[0]
    assert b["client_id"] == "c1" and b["provisioned_at"]
    assert provisioned == [] and touched == []          # no new upload link, no second email
    assert db.rows("prospects")[0]["status"] == "engaged"  # the funnel row is left where it was
    assert [e["kind"] for e in db.rows("funnel_events")] == ["kickoff_booked"]
    assert any(h.startswith("Kickoff booked: Ana Alpha") and "nothing was sent" in h for h in p.human)


def test_a_kickoff_from_an_address_we_do_not_know_gets_the_call_prep(monkeypatch):
    db = FakeDB(clients=[], bookings=[_booking("Kick-off call", email="new@beta.com")], prospects=[],
                funnel_events=[])
    p, provisioned, touched = _pass(monkeypatch, db)
    p.bookings()
    assert provisioned == ["new@beta.com"] and touched == [("call_prep", "booked")]


def test_a_new_booking_is_sent_the_call_prep_and_never_youre_in(monkeypatch):
    db = FakeDB(clients=[], bookings=[_booking("Margin audit", email="new@beta.com")], prospects=[],
                funnel_events=[], client_touches=[])
    sent = _mail(monkeypatch, db)
    p = operator.Pass(db, send=True, dry=False)
    monkeypatch.setattr(onboarding, "provision", lambda _db, email, *a, **k: (
        db.store["clients"].append({"id": "n1", "contact_email": email, "status": "pending", "platform": "amazon"})
        or (db.rows("clients")[-1], "https://x/intake?t=new", True)))
    p.bookings()
    assert [s["kind"] for s in sent] == ["call_prep"]
    assert sent[0]["link"] == "https://x/intake?t=new" and sent[0]["call_at"] is not None
    assert sent[0]["stage"] == "booked"
    b = db.rows("bookings")[0]
    assert b["client_id"] == "n1" and b["provisioned_at"] and b["welcome_sent_at"]
    assert [t["kind"] for t in db.rows("client_touches")] == ["call_prep"]
    assert any("Call prep email sent" in h for h in p.human)


def test_a_reschedule_from_an_existing_client_is_linked_and_nothing_is_resent(monkeypatch):
    """The second non-kickoff booking used to re-provision: the first upload link
    revoked, a new one minted, the first email sent again."""
    first = _booking("Margin audit", bid="b0", starts=1.0, provisioned_at=_at(-1), client_id="c1",
                     welcome_sent_at=_at(-1))
    db = FakeDB(clients=[_client()], bookings=[first, _booking("Margin audit", bid="b1", starts=4.0)],
                prospects=[], funnel_events=[], client_touches=[{"client_id": "c1", "kind": "call_prep",
                                                                 "sent_at": _at(-1)}])
    sent = _mail(monkeypatch, db)
    monkeypatch.setattr(onboarding, "provision", lambda *a, **k: (_ for _ in ()).throw(AssertionError("provisioned")))
    p = operator.Pass(db, send=True, dry=False)
    p.bookings()
    b1 = next(b for b in db.rows("bookings") if b["id"] == "b1")
    assert b1["client_id"] == "c1" and b1["provisioned_at"] and b1["welcome_sent_at"] is None
    assert sent == []
    assert [e["kind"] for e in db.rows("funnel_events")] == ["booking_linked"]
    assert any("booked again" in h and "Nothing was sent" in h for h in p.human)


def test_a_call_prep_that_did_not_go_is_retried_until_it_does_then_never_again(monkeypatch):
    db = FakeDB(clients=[], bookings=[_booking("Margin audit", email="new@beta.com")], prospects=[],
                funnel_events=[], client_touches=[])
    sent = _mail(monkeypatch, db, ok=False)
    monkeypatch.setattr(onboarding, "provision", lambda _db, email, *a, **k: (
        db.store["clients"].append({"id": "n1", "contact_email": email, "status": "pending", "platform": "amazon"})
        or (db.rows("clients")[-1], "https://x/intake?t=new", True)))
    p = operator.Pass(db, send=True, dry=False)
    p.bookings()
    assert len(sent) == 1                                     # tried once this pass, not twice
    assert db.rows("bookings")[0]["welcome_sent_at"] is None  # and recorded honestly as not sent
    assert any("NOT sent" in h for h in p.human)

    sent2 = _mail(monkeypatch, db, ok=True)
    operator.Pass(db, send=True, dry=False).bookings()
    assert [s["kind"] for s in sent2] == ["call_prep"]
    assert db.rows("bookings")[0]["welcome_sent_at"]

    sent3 = _mail(monkeypatch, db, ok=True)
    operator.Pass(db, send=True, dry=False).bookings()
    assert sent3 == []


def test_no_call_prep_is_sent_once_the_call_has_happened(monkeypatch):
    late = _booking("Margin audit", starts=-1.0, provisioned_at=_at(-3), client_id="c1")
    db = FakeDB(clients=[_client()], bookings=[late], prospects=[], funnel_events=[], client_touches=[])
    sent = _mail(monkeypatch, db)
    operator.Pass(db, send=True, dry=False).bookings()
    assert sent == []


def test_a_call_prep_the_database_cannot_record_is_still_never_sent_twice(monkeypatch):
    """Before migration 20261001000003, client_touches refuses the kind
    'call_prep'. The mail has gone; the booking remembers it."""
    class NoNewKinds(FakeDB):
        def table(self, name):
            q = super().table(name)
            if name == "client_touches":
                def refuse(rows, **k):
                    raise RuntimeError('violates check constraint "client_touches_kind_check"')
                q.upsert = refuse
            return q

    db = NoNewKinds(clients=[], bookings=[_booking("Margin audit", email="new@beta.com")], prospects=[],
                    funnel_events=[], client_touches=[])
    sent = _mail(monkeypatch, db)
    monkeypatch.setattr(onboarding, "provision", lambda _db, email, *a, **k: (
        db.store["clients"].append({"id": "n1", "contact_email": email, "status": "pending", "platform": "amazon"})
        or (db.rows("clients")[-1], "https://x/intake?t=new", True)))
    p = operator.Pass(db, send=True, dry=False)
    p.bookings()
    assert len(sent) == 1 and db.rows("bookings")[0]["welcome_sent_at"]
    assert any("20261001000003" in w for w in p.warnings)
    operator.Pass(db, send=True, dry=False).bookings()
    assert len(sent) == 1


def test_without_a_mail_key_nothing_is_minted_and_the_founder_is_told(monkeypatch):
    waiting = _booking("Margin audit", provisioned_at=_at(-1), client_id="c1")
    db = FakeDB(clients=[_client()], bookings=[waiting], prospects=[], funnel_events=[], client_touches=[])
    minted = []
    monkeypatch.setattr(onboarding, "mint_token", lambda *a, **k: minted.append(a) or "t")
    monkeypatch.setattr(operator, "email_configured", lambda: False)
    p = operator.Pass(db, send=True, dry=False)
    p.bookings()
    assert minted == []
    assert any("call prep email(s) waiting" in w and "RESEND_API_KEY" in w for w in p.warnings)


def test_the_kickoff_pattern_is_the_one_the_unit_economics_count():
    from hubricon_engine import economics
    assert economics.KICKOFF is onboarding.KICKOFF_EVENT
    assert all(onboarding.KICKOFF_EVENT.search(s) for s in ("Kickoff", "kick-off call", "Hubricon KICK OFF"))
    assert not onboarding.KICKOFF_EVENT.search("Profit Teardown call")
