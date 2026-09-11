"""Issuance and the veto window.

The load-bearing test here is `test_a_directive_nobody_was_told_about_never_
auto_approves`. terms.html §6 sells a veto, and a veto window opened against
someone who was never notified is worse than no window at all.
"""
from datetime import datetime, timedelta, timezone

from hubricon_engine import issue


class FakeTable:
    def __init__(self, db, name):
        self.db, self.name, self._filters, self._patch = db, name, {}, None

    def select(self, *_a, **_k):
        return self

    def update(self, patch):
        self._patch = patch
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def in_(self, col, vals):
        self._filters[("in", col)] = list(vals)
        return self

    def execute(self):
        rows = [r for r in self.db.rows(self.name) if self._matches(r)]
        if self._patch is not None:
            for r in rows:
                r.update(self._patch)
            self.db.writes.append((self.name, dict(self._patch), [r.get("id") for r in rows]))
        return type("R", (), {"data": rows})()

    def _matches(self, row):
        for k, v in self._filters.items():
            if isinstance(k, tuple):
                if row.get(k[1]) not in v:
                    return False
            elif row.get(k) != v:
                return False
        return True


class FakeDB:
    def __init__(self, directives):
        self._directives = directives
        self.writes = []

    def rows(self, name):
        return self._directives if name == "directives" else []

    def table(self, name):
        return FakeTable(self, name)


CLIENT = {"id": "c1", "contact_email": "dana@acme.test", "contact_name": "Dana Reyes"}


def _d(i, **kw):
    base = {"id": f"d{i}", "client_id": "c1", "channel": "amazon", "status": "draft",
            "module": "advertising", "mandate": "standing",
            "action_text": f"Do thing {i}", "expected_impact_usd": 100.0 * i,
            "issued_at": None, "notified_at": None, "veto_closes_at": None}
    base.update(kw)
    return base


def test_a_directive_nobody_was_told_about_never_auto_approves(monkeypatch):
    """The rule the design hangs on. If the notification did not go out, no
    veto window opens — silence from someone who was never told is not consent."""
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: False)
    db = FakeDB([_d(1), _d(2)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["issued"] == 2 and res["notified"] is False
    for row in db.rows("directives"):
        assert row["status"] == "issued"
        assert row["veto_closes_at"] is None      # no window, ever
        assert row["notified_at"] is None

    # ...and the closer refuses to touch them however long they sit.
    closed = issue.close_veto_windows(db, CLIENT, "amazon")
    assert closed["auto_approved"] == 0


def test_a_notified_standing_directive_opens_a_window_and_then_approves(monkeypatch):
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)
    monkeypatch.setattr("hubricon_engine.notify.send_email", lambda *a, **k: True)
    db = FakeDB([_d(1)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["notified"] is True
    row = db.rows("directives")[0]
    assert row["notified_at"] and row["veto_closes_at"]

    # Still inside the window: nothing moves.
    assert issue.close_veto_windows(db, CLIENT, "amazon")["auto_approved"] == 0
    assert row["status"] == "issued"

    # Window closed: the standing mandate is exactly what this means.
    row["veto_closes_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert issue.close_veto_windows(db, CLIENT, "amazon")["auto_approved"] == 1
    assert row["status"] == "approved" and row["auto_approved_at"]
    assert row.get("responded_by") is None        # nobody clicked, and we don't pretend


def test_an_explicit_directive_never_auto_approves_and_lapses_instead(monkeypatch):
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)
    monkeypatch.setattr("hubricon_engine.notify.send_email", lambda *a, **k: True)
    old = (datetime.now(timezone.utc) - timedelta(days=issue.EXPLICIT_LAPSE_DAYS + 1)).isoformat()
    db = FakeDB([_d(1, status="issued", mandate="explicit", issued_at=old,
                    notified_at=old, veto_closes_at=old)])
    out = issue.close_veto_windows(db, CLIENT, "amazon")
    assert out["auto_approved"] == 0 and out["lapsed"] == 1
    row = db.rows("directives")[0]
    assert row["status"] == "lapsed"
    assert "Silence is not consent" in row["measurement_notes"]


def test_no_more_than_five_decisions_land_in_one_sweep(monkeypatch):
    """The offer is that the client's effort is zero. Twelve decisions is not
    zero effort, so the rest wait for next week."""
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)
    monkeypatch.setattr("hubricon_engine.notify.send_email", lambda *a, **k: True)
    db = FakeDB([_d(i) for i in range(1, 13)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["issued"] == issue.MAX_ISSUED_PER_SWEEP == 5
    assert res["held"] == 7
    issued = [r for r in db.rows("directives") if r["status"] == "issued"]
    # The five biggest promises go first.
    assert sorted(float(r["expected_impact_usd"]) for r in issued) == [800.0, 900.0, 1000.0, 1100.0, 1200.0]


def test_the_veto_window_leaves_a_full_working_day():
    assert issue.VETO_HOURS >= 72


def test_a_module_outside_this_clients_mandate_is_downgraded_to_explicit(monkeypatch):
    """welcome.html: the mandate is where the client decides which fixes we make
    without asking. A client who narrowed it on the kickoff call must never be
    auto-approved into something they pulled back."""
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)
    monkeypatch.setattr("hubricon_engine.notify.send_email", lambda *a, **k: True)

    class NarrowDB(FakeDB):
        def rows(self, name):
            if name == "mandates":
                return [{"client_id": "c1", "module": "advertising", "standing": False,
                         "bound": None, "bound_note": "paused after the Q3 test", "veto_hours": 72}]
            return super().rows(name)

    db = NarrowDB([_d(1)])
    issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    row = db.rows("directives")[0]
    assert row["mandate"] == "explicit"
    # And so it can never auto-approve, however long it sits.
    row["veto_closes_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert issue.close_veto_windows(db, CLIENT, "amazon")["auto_approved"] == 0


def test_defaults_match_what_the_terms_page_already_says():
    """A client who has not had the kickoff call yet is governed by exactly the
    published Terms — never by something more permissive."""
    assert issue.DEFAULT_MANDATE["pricing"]["standing"] is True
    assert issue.DEFAULT_MANDATE["pricing"]["bound"] == 0.05      # terms.html §6
    assert issue.DEFAULT_MANDATE["advertising"]["standing"] is True
    for module in ("inventory", "margin", "recovery", "general"):
        assert issue.DEFAULT_MANDATE[module]["standing"] is False


def test_the_veto_email_carries_the_record_line_and_a_footer_failure_never_blocks_it(monkeypatch):
    sent = []
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)
    monkeypatch.setattr("hubricon_engine.notify.send_email", lambda to, subject, text, html=None, **k: sent.append(text) or True)
    monkeypatch.setattr("hubricon_engine.cli._fetch_claims", lambda db, cid: [])
    monkeypatch.setattr("hubricon_engine.cli._fetch_invoices", lambda db, cid: [])
    db = FakeDB([_d(1), _d(2, status="done", executed_at="2026-09-01T00:00:00Z", measured_impact_usd=None)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["notified"] is True
    # d2 is made and unmeasured ($200 expected): found, not yet banked.
    assert "Your Profit Record: $0 proven since day one · $200 found and filed, not yet banked · $0 billed to date." in sent[-1]

    def boom(db, cid):
        raise RuntimeError("invoices table missing")

    monkeypatch.setattr("hubricon_engine.cli._fetch_invoices", boom)
    db = FakeDB([_d(3)])
    res = issue.issue_drafts(db, CLIENT, "amazon", "https://x/portal", send=True)
    assert res["notified"] is True and "Your Profit Record:" not in sent[-1]


def _directives_args(db, monkeypatch, issue_flag: bool):
    """`hubricon directives <client> --issue` on the fake database: the run,
    the drafting and the client lookup are stubbed; issuance is not."""
    from types import SimpleNamespace
    from hubricon_engine import cli
    monkeypatch.setattr(cli.dbmod, "connect", lambda: db)
    monkeypatch.setattr(cli.dbmod, "resolve_client", lambda _db, _ident: CLIENT)
    monkeypatch.setattr(cli, "_latest_run", lambda _db, _cid, _run_id: {"id": "run1", "params": {"channel": "amazon"}})
    monkeypatch.setattr(cli, "_draft_for_run", lambda _db, _client, _run_id, _channel: list(db.rows("directives")))
    monkeypatch.setattr(cli, "_fetch_claims", lambda _db, _cid: [])
    monkeypatch.setattr(cli, "_fetch_invoices", lambda _db, _cid: [])
    return SimpleNamespace(client=CLIENT["contact_email"], run=None, issue=issue_flag)


def test_the_issue_flag_only_ever_issues_through_the_veto_email(monkeypatch, capsys):
    """`--issue` used to flip drafts to 'issued' with a bare update: rows in the
    portal nobody was told about, and no window. Now it goes through
    issue_drafts, so the email goes first and the window opens only for the
    moves it reached; and with no mail key nothing is issued at all."""
    from hubricon_engine import cli
    calls = []
    real = issue.issue_drafts

    def spy(db, client, channel, portal_url, send=False, **kw):
        calls.append({"statuses_before": [d["status"] for d in db.rows("directives")],
                      "client": client, "channel": channel, "portal_url": portal_url, "send": send})
        return real(db, client, channel, portal_url, send=send, **kw)

    monkeypatch.setattr(issue, "issue_drafts", spy)
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: False)
    monkeypatch.setattr(cli, "email_configured", lambda: False)

    # No mail key: the drafts stay drafts, nothing is updated, and it is said out loud.
    db = FakeDB([_d(1), _d(2)])
    cli.cmd_directives(_directives_args(db, monkeypatch, issue_flag=True))
    assert calls == [] and db.writes == []
    assert [d["status"] for d in db.rows("directives")] == ["draft", "draft"]
    assert "not notified — window not opened" in capsys.readouterr().out

    # Mail configured: issue_drafts is the only path to 'issued', with the veto window behind it.
    sent = []
    monkeypatch.setattr("hubricon_engine.notify.email_configured", lambda: True)
    monkeypatch.setattr("hubricon_engine.notify.send_email", lambda to, subject, text, html=None, **k: sent.append(subject) or True)
    monkeypatch.setattr(cli, "email_configured", lambda: True)
    db = FakeDB([_d(1), _d(2)])
    cli.cmd_directives(_directives_args(db, monkeypatch, issue_flag=True))
    assert len(calls) == 1 and calls[0]["statuses_before"] == ["draft", "draft"]
    assert calls[0]["client"] is CLIENT and calls[0]["channel"] == "amazon"
    assert calls[0]["portal_url"] == cli.PORTAL_URL and calls[0]["send"] is True
    assert all(d["status"] == "issued" and d["veto_closes_at"] and d["notified_at"] for d in db.rows("directives"))
    assert len(sent) == 1 and "go live" in sent[0]
    assert "issued and notified (veto window open)" in capsys.readouterr().out

    # Without the flag nothing is issued and nothing is sent.
    db = FakeDB([_d(1)])
    cli.cmd_directives(_directives_args(db, monkeypatch, issue_flag=False))
    assert len(calls) == 1 and db.rows("directives")[0]["status"] == "draft" and len(sent) == 1
