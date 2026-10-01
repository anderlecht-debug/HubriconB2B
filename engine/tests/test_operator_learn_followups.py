"""A week after a playbook download (api/learn.js writes learn_capture), the
operator asks once what came back and whether it may be published. One ask
per address, keyed on the learn_result_ask row it logs; nothing before the
week is up, nothing for an address already asked, nothing to an internal
address, and a failed send leaves no row so the next pass tries again."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fakedb import FakeDB
from hubricon_engine import operator

ADDRESS = "owner@brand.com"


def _capture(days_ago: int, email: str = ADDRESS, **extra) -> dict:
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {"id": f"cap-{email}", "kind": "learn_capture", "occurred_at": when,
            "payload": {"email": email, "first_name": "Ada", "course": "reimbursement-playbook", "route": "core", **extra}}


def _run(monkeypatch, events: list[dict], *, send: bool = True, dry: bool = False, deliver: bool = True):
    db = FakeDB(funnel_events=events)
    sent = []
    monkeypatch.setattr(operator, "email_configured", lambda: True)
    monkeypatch.setattr(operator, "send_email", lambda to, subject, text, html=None, sender=None, reply_to=None: (
        sent.append({"to": to, "subject": subject, "text": text, "html": html, "sender": sender, "reply_to": reply_to}) or deliver))
    monkeypatch.setenv("FOUNDER_EMAIL", "hagen@hubricon.com")
    p = operator.Pass(db, send=send, dry=dry)
    p.learn_followups()
    return p, db, sent


def _asks(db: FakeDB) -> list[dict]:
    return [r for r in db.rows("funnel_events") if r["kind"] == "learn_result_ask"]


def test_a_week_after_the_download_one_email_asks_what_came_back_and_logs_the_ask(monkeypatch):
    p, db, sent = _run(monkeypatch, [_capture(8)])
    assert len(sent) == 1
    m = sent[0]
    assert m["to"] == ADDRESS and m["reply_to"] == "hagen@hubricon.com" and m["sender"] == operator.onboarding.FROM
    assert m["subject"] == "The Reimbursement Playbook, a week on"
    assert "how much has come back" in m["text"] and "publish the amount and the brand name" in m["text"]
    assert m["text"].startswith("Hi Ada,")
    assert "!" not in m["text"]
    asks = _asks(db)
    assert len(asks) == 1
    assert asks[0]["payload"] == {"email": ADDRESS, "course": "reimbursement-playbook", "capture_id": f"cap-{ADDRESS}", "route": "core"}
    assert p.notes and "Asked owner@brand.com" in p.notes[0]


def test_nothing_before_the_week_is_up(monkeypatch):
    _, db, sent = _run(monkeypatch, [_capture(6)])
    assert sent == [] and _asks(db) == []


def test_an_address_already_asked_is_not_asked_again(monkeypatch):
    prior = {"kind": "learn_result_ask", "payload": {"email": ADDRESS, "course": "reimbursement-playbook"}}
    _, db, sent = _run(monkeypatch, [_capture(9), prior])
    assert sent == [] and len(_asks(db)) == 1


def test_a_second_pass_is_idempotent(monkeypatch):
    p, db, sent = _run(monkeypatch, [_capture(8)])
    p.learn_followups()
    assert len(sent) == 1 and len(_asks(db)) == 1


def test_internal_addresses_and_captures_without_a_timestamp_are_skipped(monkeypatch):
    internal = _capture(10, email="hagen.simmons@hubricon.com")
    undated = {"id": "cap-x", "kind": "learn_capture", "payload": {"email": "someone@brand.com"}}
    _, db, sent = _run(monkeypatch, [internal, undated])
    assert sent == [] and _asks(db) == []


def test_without_send_the_ask_is_a_warning_and_a_dry_pass_only_says_so(monkeypatch):
    p, db, sent = _run(monkeypatch, [_capture(8)], send=False)
    assert sent == [] and _asks(db) == []
    assert any("learn follow-up to owner@brand.com not sent: --send not given" in w for w in p.warnings)
    p, db, sent = _run(monkeypatch, [_capture(8)], dry=True)
    assert sent == [] and _asks(db) == []
    assert p.notes == ["[dry] would ask owner@brand.com what The Reimbursement Playbook got back"]


def test_a_failed_send_leaves_no_row_so_the_next_pass_tries_again(monkeypatch):
    p, db, sent = _run(monkeypatch, [_capture(8)], deliver=False)
    assert len(sent) == 1 and _asks(db) == []
    assert any("failed to send" in w for w in p.warnings)


def test_the_follow_up_carries_no_figure():
    subject, text, html = operator.learn_followup_email("Ada", "reimbursement-playbook")
    for s in (subject, text):
        assert not any(ch.isdigit() for ch in s), s
        assert "!" not in s
    assert "Best,\nHagen" in text
