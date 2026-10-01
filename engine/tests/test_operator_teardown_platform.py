"""What is left of the TEARDOWN door, now the Teardown is retired.

A prospect who still replies TEARDOWN to an old email is answered by triage
with the call and the free course; the operator moves them to 'interested' and
provisions nothing: no client row, no upload link, no email before a booking.
The Recovery Only door (api/gate) still provisions, on its own email."""
from __future__ import annotations

from fakedb import FakeDB
from hubricon_engine import onboarding, operator


def test_a_teardown_reply_provisions_nothing_and_becomes_interest_in_the_call(monkeypatch):
    db = FakeDB(
        prospects=[{"id": "p1", "email": "owner@brand.com", "first_name": "Ada", "status": "wants_teardown", "client_id": None}],
        harvest_sellers=[], tool_runs=[], funnel_events=[], client_touches=[],
    )
    called = []
    monkeypatch.setattr(onboarding, "provision", lambda *a, **k: called.append("provision"))
    monkeypatch.setattr(operator.Pass, "_touch", lambda *a, **k: called.append("touch") or True)
    p = operator.Pass(db, send=True, dry=False)
    p.teardown_requests()
    assert called == []
    row = db.rows("prospects")[0]
    assert row["status"] == "interested" and row["client_id"] is None
    assert [e["kind"] for e in db.rows("funnel_events")] == ["teardown_retired"]
    assert any("TEARDOWN" in h and "nothing was provisioned" in h for h in p.human)


def test_a_recovery_request_from_the_site_gets_the_recovery_email_not_the_teardown_one(monkeypatch):
    """api/gate.js writes the note; the gate's channel answer beats a stale harvest row."""
    db = FakeDB(
        prospects=[{"id": "p1", "email": "owner@brand.com", "status": "wants_teardown", "client_id": None,
                    "fit_notes": "recovery-only (site gate) · channel:Both · rev:Under $3M · model:Private label"}],
        harvest_sellers=[{"email": "owner@brand.com", "platform": "shopify"}], tool_runs=[], funnel_events=[],
        client_touches=[],
    )
    seen = {}
    monkeypatch.setattr(onboarding, "provision", lambda _db, email, name, company, platform: (
        seen.__setitem__("platform", platform) or ({"id": "c1", "contact_email": email}, "https://x/upload", True)))
    monkeypatch.setattr(operator.Pass, "_touch", lambda self, client, kind, link, force=False: seen.__setitem__("kind", kind) or True)
    operator.Pass(db, send=False, dry=False).teardown_requests()
    assert seen == {"platform": "both", "kind": "recovery_welcome"}
    assert db.rows("funnel_events")[-1]["kind"] == "recovery_provisioned"
