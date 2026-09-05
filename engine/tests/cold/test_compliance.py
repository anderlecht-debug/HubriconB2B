"""The Phase 0 gate: prove a send is impossible when it should be.

Every test here is an attempt to get an email out that should not go, and the
last one is the important one — it checks that a caller who forgets the guard
entirely gets an exception rather than a delivered message.
"""

from datetime import datetime, timedelta, timezone

import pytest

from hubricon_engine.cold import compliance, settings
from builders import snapshot


class FakeTable:
    def __init__(self, rows):
        self.rows, self._filters, self.inserted = rows, [], []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters.append((col, "eq", val))
        return self

    def gte(self, col, val):
        self._filters.append((col, "gte", val))
        return self

    def order(self, *_a, **_k):
        return self

    def insert(self, row):
        self.inserted.append(row)
        return self

    def execute(self):
        rows = self.rows
        for col, op, val in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(col) == val]
            else:
                rows = [r for r in rows if str(r.get(col, "")) >= str(val)]
        self._filters = []
        return type("R", (), {"data": rows})()


class FakeDB:
    def __init__(self, **tables):
        self.tables = {name: FakeTable(rows) for name, rows in tables.items()}

    def table(self, name):
        return self.tables.setdefault(name, FakeTable([]))


@pytest.fixture(autouse=True)
def _sendable(monkeypatch):
    """The baseline: everything set up so a send is allowed, so each test can
    break exactly one thing."""
    monkeypatch.setenv("COLD_DRY_RUN", "false")
    monkeypatch.setenv("POSTAL_ADDRESS", "1 Example Way, Austin TX 78701")


def db(**kw):
    kw.setdefault("suppressions", [])
    kw.setdefault("outreach_sends", [])
    return FakeDB(**kw)


def test_the_baseline_prospect_clears():
    c = compliance.authorise(db(), snapshot())
    assert c.ok and c.send is not None
    assert "legitimate interest" in c.send.basis


def test_dry_run_stops_everything(monkeypatch):
    monkeypatch.setenv("COLD_DRY_RUN", "true")
    c = compliance.authorise(db(), snapshot())
    assert not c.ok and "COLD_DRY_RUN" in c.reason and c.send is None


def test_dry_run_still_allows_the_founder_lane_to_draft(monkeypatch):
    monkeypatch.setenv("COLD_DRY_RUN", "true")
    assert compliance.authorise(db(), snapshot(), allow_dry_run=True).ok


def test_a_suppressed_address_is_refused():
    d = db(suppressions=[{"email": "dana@testbrand.com", "reason": "asked us to stop"}])
    c = compliance.authorise(d, snapshot())
    assert not c.ok and "asked us to stop" in c.reason


def test_a_suppressed_domain_takes_every_address_on_it_with_it():
    d = db(suppressions=[{"domain": "testbrand.com", "reason": "company-wide objection"}])
    assert not compliance.authorise(d, snapshot(email="someone@testbrand.com")).ok


def test_the_suppression_check_runs_even_for_a_draft(monkeypatch):
    monkeypatch.setenv("COLD_DRY_RUN", "true")
    d = db(suppressions=[{"email": "dana@testbrand.com", "reason": "unsubscribed"}])
    assert not compliance.authorise(d, snapshot(), allow_dry_run=True).ok


def test_eu_and_uk_prospects_are_suppressed_not_risked():
    for country in ("GB", "DE", "IE"):
        c = compliance.authorise(db(), snapshot(country=country))
        assert not c.ok and "GDPR" in c.reason


def test_can_spam_needs_a_postal_address(monkeypatch):
    monkeypatch.delenv("POSTAL_ADDRESS", raising=False)
    c = compliance.authorise(db(), snapshot())
    assert not c.ok and "CAN-SPAM" in c.reason


def test_no_address_no_send():
    assert not compliance.authorise(db(), snapshot(email=None)).ok


def test_we_never_email_ourselves():
    assert not compliance.authorise(db(), snapshot(email="hagen.simmons@hubricon.com")).ok


def test_three_touches_is_the_lifetime_cap():
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    d = db(outreach_sends=[{"prospect_key": "A1TESTSELLER", "sent_at": old}] * 3)
    c = compliance.authorise(d, snapshot())
    assert not c.ok and "cap is 3" in c.reason


def test_ninety_days_between_touches():
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    d = db(outreach_sends=[{"prospect_key": "A1TESTSELLER", "sent_at": recent}])
    c = compliance.authorise(d, snapshot())
    assert not c.ok and "90 days" in c.reason


def test_a_touch_older_than_ninety_days_is_allowed_again():
    old = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    d = db(outreach_sends=[{"prospect_key": "A1TESTSELLER", "sent_at": old}])
    assert compliance.authorise(d, snapshot()).ok


def test_the_domain_daily_cap_is_enforced_in_code(monkeypatch):
    monkeypatch.setenv("COLD_DOMAIN_DAILY_CAP", "2")
    fresh = datetime.now(timezone.utc).isoformat()
    d = db(outreach_sends=[{"sending_domain": "mail1.example", "sent_at": fresh}] * 2)
    c = compliance.authorise(d, snapshot(), sending_domain="mail1.example")
    assert not c.ok and "cap is 2" in c.reason


def test_the_cap_is_per_domain_not_global(monkeypatch):
    monkeypatch.setenv("COLD_DOMAIN_DAILY_CAP", "2")
    fresh = datetime.now(timezone.utc).isoformat()
    d = db(outreach_sends=[{"sending_domain": "mail1.example", "sent_at": fresh}] * 2)
    assert compliance.authorise(d, snapshot(), sending_domain="mail2.example").ok


# -- the guard that cannot be walked around ---------------------------------------

def test_a_send_cannot_be_constructed_without_a_clearance():
    with pytest.raises(compliance.NotAuthorised):
        compliance.SendTicket(
            grant=object(), prospect_key="A1TESTSELLER", email="dana@testbrand.com",
            sending_domain=None, jurisdiction="US", basis="made up", checked=(),
            issued_at=datetime.now(timezone.utc))


def test_a_denied_clearance_carries_no_ticket_to_borrow():
    c = compliance.authorise(db(), snapshot(country="FR"))
    assert c.send is None


def test_every_clearance_records_what_it_checked_for_the_gdpr_file():
    c = compliance.authorise(db(), snapshot())
    assert "global suppression list" in c.checked
    assert "jurisdiction" in c.checked
    assert "contact frequency" in c.checked


def test_recording_a_send_writes_the_basis_it_was_made_under():
    d = db()
    ticket = compliance.authorise(d, snapshot()).send
    compliance.record_send(d, ticket, template_id="teardown-v1", subject="A subject")
    row = d.table("outreach_sends").inserted[0]
    assert row["prospect_key"] == "A1TESTSELLER"
    assert row["recipient_email"] == "dana@testbrand.com"
    assert "legitimate interest" in row["basis"]


def test_an_objection_is_honoured_immediately():
    d = db()
    compliance.suppress(d, email="Dana@TestBrand.com", reason="replied: remove me")
    d.tables["suppressions"].rows = d.table("suppressions").inserted
    assert not compliance.authorise(d, snapshot()).ok
