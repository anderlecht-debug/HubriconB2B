"""Cold outreach is paused by default (HUBRICON_SPEC.md, channel decision): the hourly
operator enrolls, pushes, dispatches and activates nothing, holds every Hubricon
campaign paused, and still carries the conversations already started."""

from hubricon_engine import operator, outbound
from hubricon_engine.instantly import CAMPAIGN_ACTIVE, CAMPAIGN_PAUSED
from fakedb import FakeDB


class FakeInstantly:
    def __init__(self, campaigns):
        self._campaigns = campaigns
        self.calls = []

    def campaigns(self):
        return [dict(c) for c in self._campaigns]

    def pause_campaign(self, cid):
        self.calls.append(("pause", cid))
        for c in self._campaigns:
            if c["id"] == cid:
                c["status"] = CAMPAIGN_PAUSED
        return {}

    def activate_campaign(self, cid):
        self.calls.append(("activate", cid))
        raise AssertionError("a paused channel never activates a campaign")


def _campaigns():
    return [
        {"id": "k1", "name": "Hubricon — Profit Teardown (PL FBA $3M–$20M)", "status": CAMPAIGN_ACTIVE},
        {"id": "k2", "name": "Hubricon — Profit Teardown (per-prospect)", "status": CAMPAIGN_PAUSED},
        {"id": "k3", "name": "Someone else's campaign", "status": CAMPAIGN_ACTIVE},
    ]


def test_paused_is_the_default_and_only_on_resumes(monkeypatch):
    monkeypatch.delenv(outbound.COLD_ENV, raising=False)
    assert outbound.cold_paused()
    for v in ("", "off", "true", "1", "yes"):
        monkeypatch.setenv(outbound.COLD_ENV, v)
        assert outbound.cold_paused()
    monkeypatch.setenv(outbound.COLD_ENV, " ON ")
    assert not outbound.cold_paused()


def test_only_an_active_hubricon_campaign_is_paused_and_the_pause_is_read_back():
    db = FakeDB(funnel_events=[])
    api = FakeInstantly(_campaigns())
    notes = outbound.hold_campaigns(db, api, dry=False)
    assert api.calls == [("pause", "k1")]
    assert len(notes) == 1 and "Paused" in notes[0]
    assert [e["kind"] for e in db.rows("funnel_events")] == ["campaign_paused"]


def test_a_dry_pass_pauses_nothing():
    db = FakeDB(funnel_events=[])
    api = FakeInstantly(_campaigns())
    notes = outbound.hold_campaigns(db, api, dry=True)
    assert api.calls == [] and notes and notes[0].startswith("[dry] would pause")


def test_the_operator_holds_cold_but_keeps_the_conversations(monkeypatch):
    monkeypatch.delenv(outbound.COLD_ENV, raising=False)
    monkeypatch.setenv("INSTANTLY_API_KEY", "test")
    api = FakeInstantly(_campaigns())
    monkeypatch.setattr(operator.instantly, "Instantly", lambda: api)
    did = []
    for name in ("ensure_campaign", "enroll_from_lists", "enroll_from_supersearch", "repair_enrollment"):
        monkeypatch.setattr(outbound, name, lambda *a, _n=name, **k: (_ for _ in ()).throw(AssertionError(f"{_n} ran while paused")))
    monkeypatch.setattr(outbound, "sync_campaign_leads", lambda db, api, cid: did.append(("leads", cid)) or [])
    monkeypatch.setattr(outbound, "sync_replies", lambda db, api, cid, dry: did.append(("replies", cid)) or (0, []))
    monkeypatch.setattr(outbound, "send_approved", lambda db, api, dry: did.append(("approved",)) or (0, []))
    monkeypatch.setattr(outbound, "campaign_summary", lambda api, cid: {"leads_count": 1})
    db = FakeDB(funnel_events=[], operator_state=[{"key": "instantly.campaign", "value": {"id": "k1"}}])
    p = operator.Pass(db, send=False, dry=False)
    p.outbound()
    assert ("pause", "k1") in api.calls and not any(c[0] == "activate" for c in api.calls)
    assert did == [("leads", "k1"), ("replies", "k1"), ("approved",)]
    assert any("Cold outreach is paused" in n for n in p.notes)
    assert not p.warnings
