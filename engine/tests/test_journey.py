"""The journey's stages in the machine (lifecycle.py), end to end on the fake
database: nudges counted from the call and sent only where the stage allows,
a no that silences everything, the yes confirmed with the billing gate's own
dates, a first read that waits for the core files (or a day), and first moves
that go out with the first read, to a client who said yes and to nobody else."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from fakedb import FakeDB
from hubricon_engine import cli, issue, monthly, notify, onboarding, operator


def _ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _client(cid="c1", **kw):
    return {"id": cid, "contact_email": f"{cid}@brand.com", "contact_name": "Ana Alpha", "company_name": "Alpha",
            "status": "pending", "platform": "amazon", "created_at": _ago(30), **kw}


def _call(cid="c1", days_ago=4.0, **kw):
    return {"id": f"b-{cid}", "client_id": cid, "invitee_email": f"{cid}@brand.com", "event_type": "Margin audit",
            "starts_at": _ago(days_ago), "created_at": _ago(days_ago + 2), "provisioned_at": _ago(days_ago + 2),
            "welcome_sent_at": _ago(days_ago + 2), "is_test": False, **kw}


def _touch(cid, kind, days_ago=6.0):
    return {"client_id": cid, "kind": kind, "sent_at": _ago(days_ago)}


def _nudged(monkeypatch, db) -> list:
    sent = []
    monkeypatch.setattr(operator.Pass, "_reonboard", lambda self, c, kind, stage=None: sent.append((c["id"], kind, stage)))
    operator.Pass(db, send=True, dry=False).nudges()
    return sent


def _mail(monkeypatch, db, ok=True) -> list:
    """Resend replaced at the bottom, so every gate above it is the real one."""
    sent = []
    monkeypatch.setattr(notify, "email_configured", lambda: True)
    monkeypatch.setattr(operator, "email_configured", lambda: True)
    monkeypatch.setattr(notify, "send_email", lambda to, subject, text, html=None, **k:
                        sent.append({"to": to, "subject": subject, "text": text}) or ok)
    db.rpcs.setdefault("revoke_intake_tokens", lambda **_k: [])
    db.rpcs.setdefault("create_intake_token", lambda **_k: [])
    return sent


# -- nudges: from the call, by stage ---------------------------------------------------

def test_nudges_count_from_the_call_not_the_booking(monkeypatch):
    db = FakeDB(clients=[_client("a"), _client("b"), _client("c")], uploads=[],
                bookings=[_call("a", 4), _call("b", 8), _call("c", -2, created_at=_ago(20))],
                client_touches=[_touch("a", "call_prep", 9), _touch("b", "call_prep", 12), _touch("b", "nudge", 5),
                                _touch("c", "call_prep", 20)])
    sent = _nudged(monkeypatch, db)
    assert ("a", "nudge", "called") in sent           # three days after the call
    assert ("b", "files", "called") in sent           # seven days after it
    assert not [s for s in sent if s[0] == "c"]       # booked twenty days ago, call still ahead: nothing


def test_a_nudge_is_never_anyones_first_email(monkeypatch):
    db = FakeDB(clients=[_client("a")], uploads=[], bookings=[_call("a", 9, welcome_sent_at=None)],
                client_touches=[])
    assert _nudged(monkeypatch, db) == []
    # a call prep recorded only on the booking (before client_touches could hold the kind) counts
    db = FakeDB(clients=[_client("a")], uploads=[], bookings=[_call("a", 9)], client_touches=[])
    assert _nudged(monkeypatch, db) == [("a", "files", "called")]


def test_a_client_who_said_yes_gets_the_upload_link_again_but_never_the_downsell(monkeypatch):
    yes_today = _client("y", retainer_started_at=_ago(1))
    yes_long = _client("z", retainer_started_at=_ago(16))
    db = FakeDB(clients=[yes_today, yes_long], uploads=[], bookings=[_call("y", 20), _call("z", 20)],
                client_touches=[_touch("y", "agreed", 1), _touch("z", "agreed", 16), _touch("z", "nudge", 10)])
    sent = _nudged(monkeypatch, db)
    assert [s for s in sent if s[0] == "y"] == []     # counted from the yes, not the call twenty days ago
    assert ("z", "files", "agreed") in sent and not [s for s in sent if s[1] == "downsell"]


def test_a_no_or_an_exit_gets_nothing(monkeypatch):
    db = FakeDB(clients=[_client("d", status="declined"), _client("x", status="churned")], uploads=[],
                bookings=[_call("d", 15), _call("x", 15)],
                client_touches=[_touch("d", "call_prep", 20), _touch("x", "call_prep", 20)])
    assert _nudged(monkeypatch, db) == []


def test_the_stage_gate_holds_even_when_reonboard_is_called_directly(monkeypatch):
    """_touch asks lifecycle.may_send itself: a downsell to a client who said
    yes, or anything to a declined one, does not go."""
    db = FakeDB(clients=[_client("y")], client_touches=[])
    sent = _mail(monkeypatch, db)
    p = operator.Pass(db, send=True, dry=False)
    assert p._touch(_client("y"), "downsell", "l", stage="agreed") is False
    assert p._touch(_client("y"), "nudge", "l", stage="declined") is False
    assert p._touch(_client("y"), "nudge", "l", stage="called") is True
    assert len(sent) == 1


# -- the no ---------------------------------------------------------------------------

def _cli(monkeypatch, db, client):
    monkeypatch.setattr(cli.dbmod, "connect", lambda: db)
    # resolve_client's fixed column list has no retainer_started_at; the commands re-read the row
    monkeypatch.setattr(cli.dbmod, "resolve_client", lambda _db, _ident: {
        k: client.get(k) for k in ("id", "company_name", "contact_email", "status", "contact_name", "free_months",
                                   "created_at", "platform")})


def test_declined_records_the_no_revokes_the_links_and_sends_nothing(monkeypatch, capsys):
    db = FakeDB(clients=[_client("d")], funnel_events=[])
    revoked = []
    db.rpcs["revoke_intake_tokens"] = lambda **k: revoked.append(k) or []
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: pytest.fail("a no is answered by a person"))
    _cli(monkeypatch, db, _client("d"))
    cli.cmd_declined(SimpleNamespace(client="d@brand.com", note="price"))
    row = db.rows("clients")[0]
    assert row["status"] == "declined" and row["declined_at"]
    assert revoked == [{"p_client_id": "d"}]
    ev = db.rows("funnel_events")[-1]
    assert ev["kind"] == "client_declined" and ev["note"] == "price"
    assert "Nothing was sent" in capsys.readouterr().out


def test_after_a_no_the_machine_sends_nothing_at_all(monkeypatch):
    """Nudges, the downsell, the first read, the agreed letter, move notices:
    none of them reach a client recorded as declined."""
    d = _client("d", status="declined")
    db = FakeDB(clients=[d], uploads=[{"client_id": "d", "report_type": "business_report", "status": "parsed",
                                       "uploaded_at": _ago(3)}],
                sku_economics=[{"id": 1, "client_id": "d"}], briefings=[],
                bookings=[_call("d", 15)], client_touches=[_touch("d", "call_prep", 20)],
                directives=[{"id": "m1", "client_id": "d", "channel": "amazon", "status": "draft", "module": "pricing",
                             "mandate": "standing", "expected_impact_usd": 500.0}], funnel_events=[])
    sent = _mail(monkeypatch, db)
    monkeypatch.setattr(operator.Pass, "_publish_first_issue", lambda *a, **k: pytest.fail("no read for a no"))
    p = operator.Pass(db, send=True, dry=False)
    p.bookings()
    p.nudges()
    p.teardowns()
    assert issue.issue_drafts(db, d, "amazon", "https://x/portal", send=True)["issued"] == 0
    assert sent == [] and db.rows("directives")[0]["status"] == "draft"


def test_declined_before_the_migration_says_exactly_what_to_apply(monkeypatch, capsys):
    class Unmigrated(FakeDB):
        def table(self, name):
            q = super().table(name)
            real = q.select

            def select(*cols, **k):
                if "declined_at" in cols:
                    raise RuntimeError("column clients.declined_at does not exist")
                return real(*cols, **k)
            q.select = select
            return q

    db = Unmigrated(clients=[_client("d")], funnel_events=[])
    _cli(monkeypatch, db, _client("d"))
    with pytest.raises(SystemExit) as out:
        cli.cmd_declined(SimpleNamespace(client="d@brand.com", note=None))
    assert "20261001000003_journey_lifecycle.sql" in str(out.value)
    assert "declined_at does not exist" in str(out.value)
    assert db.rows("clients")[0]["status"] == "pending"


def test_a_no_after_a_yes_is_a_cancel_not_a_decline(monkeypatch):
    db = FakeDB(clients=[_client("y", retainer_started_at=_ago(3))], funnel_events=[], bookings=[])
    _cli(monkeypatch, db, db.rows("clients")[0])
    with pytest.raises(SystemExit) as out:
        cli.cmd_declined(SimpleNamespace(client="y@brand.com", note=None))
    assert "hubricon cancel" in str(out.value) and db.rows("clients")[0]["status"] == "pending"


# -- the yes ----------------------------------------------------------------------------

def test_retainer_records_the_yes_and_sends_the_agreed_letter_with_the_gates_dates(monkeypatch, capsys):
    db = FakeDB(clients=[_client("y", free_months=1)], client_touches=[], funnel_events=[], briefings=[],
                uploads=[], directives=[], bookings=[_call("y", 0.5)])
    sent = _mail(monkeypatch, db)
    _cli(monkeypatch, db, db.rows("clients")[0])
    started = date.today()
    cli.cmd_retainer(SimpleNamespace(client="y@brand.com", started=None, source="client_yes", show=False))
    row = db.rows("clients")[0]
    month0 = monthly.billing_months(row, started)[0]
    out = capsys.readouterr().out
    assert f"Proving Month: {month0['start'].isoformat()} to {month0['end'].isoformat()}" in out
    assert len(sent) == 1
    letter = sent[0]
    assert letter["subject"] == (f"Confirmed: your Proving Month runs {onboarding.fmt_date(month0['start'], year=False)}"
                                 f" to {onboarding.fmt_date(month0['end'])}")
    assert "This confirms your yes." in letter["text"] and "/intake?t=" in letter["text"]
    assert [t["kind"] for t in db.rows("client_touches")] == ["agreed"]
    assert {e["kind"] for e in db.rows("funnel_events")} >= {"client_agreed", "agreed_letter_sent"}
    # run again (a corrected date): the letter is not sent twice
    cli.cmd_retainer(SimpleNamespace(client="y@brand.com", started=None, source="client_yes", show=False))
    assert len(sent) == 1 and "already sent" in capsys.readouterr().out


def test_without_a_mail_key_here_the_operator_sends_the_agreed_letter(monkeypatch, capsys):
    db = FakeDB(clients=[_client("y")], client_touches=[], funnel_events=[], briefings=[], uploads=[],
                directives=[], bookings=[])
    _cli(monkeypatch, db, db.rows("clients")[0])
    monkeypatch.setattr(notify, "email_configured", lambda: False)
    cli.cmd_retainer(SimpleNamespace(client="y@brand.com", started=None, source="client_yes", show=False))
    assert "the operator's next pass sends it" in capsys.readouterr().out
    sent = _mail(monkeypatch, db)
    operator.Pass(db, send=True, dry=False)._agreed_letters()
    assert len(sent) == 1 and sent[0]["subject"].startswith("Confirmed: your Proving Month runs")
    operator.Pass(db, send=True, dry=False)._agreed_letters()
    assert len(sent) == 1


def test_no_agreed_letter_before_the_migration_or_weeks_late(monkeypatch):
    class Unmigrated(FakeDB):
        def table(self, name):
            q = super().table(name)
            real = q.select
            q.select = lambda *cols, **k: (_ for _ in ()).throw(RuntimeError("no declined_at")) \
                if "declined_at" in cols else real(*cols, **k)
            return q

    db = Unmigrated(clients=[_client("y", retainer_started_at=_ago(1))], client_touches=[], funnel_events=[])
    sent = _mail(monkeypatch, db)
    ok, why = onboarding.deliver_agreed(db, db.rows("clients")[0])
    assert not ok and "20261001000003" in why and sent == []
    db = FakeDB(clients=[_client("y", retainer_started_at=_ago(20))], client_touches=[], funnel_events=[])
    ok, why = onboarding.deliver_agreed(db, db.rows("clients")[0])
    assert not ok and "days old" in why and sent == []


def test_a_yes_after_a_no_replaces_it(monkeypatch, capsys):
    db = FakeDB(clients=[_client("d", status="declined", declined_at=_ago(5))], client_touches=[],
                funnel_events=[], briefings=[], uploads=[], directives=[], bookings=[])
    _mail(monkeypatch, db)
    _cli(monkeypatch, db, db.rows("clients")[0])
    cli.cmd_retainer(SimpleNamespace(client="d@brand.com", started=None, source="client_yes", show=False))
    row = db.rows("clients")[0]
    assert row["status"] == "pending" and row["declined_at"] is None and row["retainer_started_at"]
    assert "this yes replaces it" in capsys.readouterr().out


# -- the first read --------------------------------------------------------------------

def _reader(monkeypatch, db):
    published = []
    monkeypatch.setattr(operator.Pass, "_publish_first_issue",
                        lambda self, c, cli_, missing=None: published.append((c["id"], list(missing or []))))
    monkeypatch.setattr(cli, "_ingest_client", lambda *_a, **_k: pytest.fail("nothing is waiting to be parsed"))
    p = operator.Pass(db, send=True, dry=False)
    p.teardowns()
    return p, published


def _up(cid, kind, hours_ago):
    return {"client_id": cid, "report_type": kind, "status": "parsed",
            "uploaded_at": (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()}


def test_issue_001_waits_for_the_core_files(monkeypatch):
    db = FakeDB(clients=[_client("a")], briefings=[], sku_economics=[], asin_traffic=[{"id": 1, "client_id": "a"}],
                uploads=[_up("a", "business_report", 2)], funnel_events=[])
    p, published = _reader(monkeypatch, db)
    assert published == [] and any("first read waits for SKU Economics" in n for n in p.notes)
    db.store["uploads"].append(_up("a", "sku_economics", 1))
    _, published = _reader(monkeypatch, db)
    assert published == [("a", [])]


def test_issue_001_goes_a_day_after_the_last_file_and_names_what_is_missing(monkeypatch):
    db = FakeDB(clients=[_client("a")], briefings=[], sku_economics=[{"id": 1, "client_id": "a"}], asin_traffic=[],
                uploads=[_up("a", "sku_economics", 25)], funnel_events=[])
    _, published = _reader(monkeypatch, db)
    assert published == [("a", ["business_report"])]


def test_the_first_letter_says_where_the_client_stands_and_what_the_read_could_not_see():
    memo = "Profit Brief No. 001\n\nDear Ana,\n\nX.\n\nNothing needs your decision this period — the watch " \
           "continues either way.\n\nRecord.\n\n— Hubricon"
    prospect = operator.Pass._first_read_letter(memo, ["sku_economics"], "booked")
    assert "the watch continues" not in prospect
    assert "Nothing in this read changes anything in your account." in prospect
    assert prospect.index("One file was not in") < prospect.index("— Hubricon")
    assert prospect.endswith("— Hubricon")
    agreed = operator.Pass._first_read_letter(memo, [], "agreed")
    assert "listed in their own notice" in agreed and "One file" not in agreed
    narrated = operator.Pass._first_read_letter("Dear Ana,\n\nA letter in other words.", [], "called")
    assert narrated.endswith("before it goes live.")


# -- first moves with the first read ---------------------------------------------------------

class Stored(FakeDB):
    """The fake database plus a storage bucket that keeps what it is given."""

    def __init__(self, **tables):
        super().__init__(**tables)
        self.files = {}
        bucket = SimpleNamespace(upload=lambda path, data, opts=None: self.files.__setitem__(path, data))
        self.storage = SimpleNamespace(from_=lambda _name: bucket)


def _publish(monkeypatch, client, tmp_path):
    db = Stored(clients=[client], briefings=[], funnel_events=[], prospects=[], client_touches=[], bookings=[],
                margin_results=[], elasticity_results=[], mandates=[],
                directives=[{"id": "m1", "client_id": client["id"], "channel": "amazon", "status": "draft",
                             "module": "advertising", "mandate": "standing", "kind": "ad_bleed_terms",
                             "action_text": "Negative-match 4 terms", "expected_impact_usd": 420.0}])
    sent = _mail(monkeypatch, db)
    page = tmp_path / "r.html"
    page.write_text("<p>read</p>")
    monkeypatch.setattr(cli, "_run_models", lambda *a, **k: "run1")
    monkeypatch.setattr(cli, "_draft_for_run", lambda *a, **k: [])
    monkeypatch.setattr(cli, "draft_plan_for_run", lambda *a, **k: None)
    monkeypatch.setattr("hubricon_engine.narrate.available", lambda: False)
    monkeypatch.setattr("hubricon_engine.report.html_report.generate", lambda *a, **k: page)
    monkeypatch.setattr("hubricon_engine.video.render", lambda *a, **k: None)
    monkeypatch.setattr("hubricon_engine.seal.seal_called", lambda *a, **k: {"status": "sealed", "short": {}})
    monkeypatch.setattr("hubricon_engine.cli._fetch_claims", lambda *a: [])
    monkeypatch.setattr("hubricon_engine.cli._fetch_invoices", lambda *a: [])
    p = operator.Pass(db, send=True, dry=False)
    p._publish_first_issue(client, cli, missing=[])
    return db, sent, p


def test_a_client_who_said_yes_gets_the_first_moves_with_the_first_read(monkeypatch, tmp_path):
    db, sent, _ = _publish(monkeypatch, _client("y", retainer_started_at=_ago(2)), tmp_path)
    assert [s["subject"] for s in sent][0] == "Your first full read is ready"
    assert len(sent) == 2 and "go live" in sent[1]["subject"]          # the notice, in the same pass
    m = db.rows("directives")[0]
    assert m["status"] == "issued" and m["notified_at"] and m["veto_closes_at"]
    assert "listed in their own notice" in db.rows("briefings")[0]["memo"]
    assert [e["kind"] for e in db.rows("funnel_events")][-1] == "first_moves_issued"


def test_a_prospect_gets_the_first_read_and_no_moves(monkeypatch, tmp_path):
    db, sent, _ = _publish(monkeypatch, _client("p"), tmp_path)
    assert [s["subject"] for s in sent] == ["Your first full read is ready"]
    assert db.rows("directives")[0]["status"] == "draft"
    memo = db.rows("briefings")[0]["memo"]
    assert "Nothing in this read changes anything in your account." in memo and "the watch continues" not in memo


def test_a_yes_after_the_first_read_issues_the_moves_on_the_next_pass_once(monkeypatch):
    y = _client("y", retainer_started_at=_ago(0.1))
    db = FakeDB(clients=[y], briefings=[{"id": "i1", "client_id": "y", "issue_number": 1}], mandates=[],
                funnel_events=[], directives=[{"id": "m1", "client_id": "y", "channel": "amazon", "status": "draft",
                                               "module": "pricing", "mandate": "standing", "kind": "price_step",
                                               "action_text": "Step SKU-1 to $24.99", "expected_impact_usd": 300.0}])
    sent = _mail(monkeypatch, db)
    monkeypatch.setattr("hubricon_engine.seal.seal_called", lambda *a, **k: {"status": "sealed", "short": {}})
    monkeypatch.setattr("hubricon_engine.cli._fetch_claims", lambda *a: [])
    monkeypatch.setattr("hubricon_engine.cli._fetch_invoices", lambda *a: [])
    operator.Pass(db, send=True, dry=False).teardowns()
    assert db.rows("directives")[0]["status"] == "issued" and len(sent) == 1
    db.store["directives"].append({**db.rows("directives")[0], "id": "m2", "status": "draft", "issued_at": None})
    operator.Pass(db, send=True, dry=False).teardowns()
    assert len(sent) == 1                    # after the first moves, Monday's sweep takes over
    # and a prospect with a first read and drafts is never sent one
    p = _client("p")
    db = FakeDB(clients=[p], briefings=[{"id": "i1", "client_id": "p", "issue_number": 1}], mandates=[],
                funnel_events=[], directives=[{"id": "m1", "client_id": "p", "channel": "amazon", "status": "draft",
                                               "module": "pricing", "mandate": "standing"}])
    sent = _mail(monkeypatch, db)
    operator.Pass(db, send=True, dry=False).teardowns()
    assert sent == [] and db.rows("directives")[0]["status"] == "draft"
