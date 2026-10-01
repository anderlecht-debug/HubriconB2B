"""The founder approves every note (approval.py): the Monday note drafted from
the graded numbers on a busy week and a quiet one, Profit Brief No. 002 held
as a draft, nothing sent or published without a yes, the stale refusal, the
digest's queue, and the old behaviour on a database without the migration."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from hubricon_engine import approval, cli, value
from fakedb import FakeDB, _Q

NOW = datetime(2026, 10, 5, 11, 30, tzinfo=timezone.utc)      # a Monday, after the 11:00 sweep
LEAF = "abcdef1234567890" + "0" * 48

AGREED = {"id": "c1", "company_name": "Acme", "contact_email": "dana@acme.com", "contact_name": "Dana Reyes",
          "status": "active", "platform": "amazon", "plan": "retainer", "monthly_fee_usd": 6000, "free_months": 1,
          "retainer_started_at": "2026-08-02T00:00:00Z"}

LIVE = [
    {"id": "live1", "client_id": "c1", "channel": "amazon", "status": "done", "kind": "price_step", "module": "pricing",
     "action_text": "Raise SKU-1 from $19.99 to $21.49.", "expected_impact_usd": 2500,
     "measured_impact_usd": 2800, "attribution": "isolated", "measured_at": "2026-09-14T00:00:00Z",
     "executed_at": "2026-08-10T00:00:00Z", "created_at": "2026-08-05T11:00:00Z", "issued_at": "2026-08-05T11:00:00Z"},
    {"id": "live2", "client_id": "c1", "channel": "amazon", "status": "approved", "kind": "ad_negative", "module": "advertising",
     "action_text": "Negative-match 11 search terms on Campaign A.", "expected_impact_usd": 900,
     "measured_impact_usd": None, "executed_at": "2026-08-25T00:00:00Z", "created_at": "2026-08-20T11:00:00Z",
     "issued_at": "2026-08-20T11:00:00Z"},
    {"id": "live3", "client_id": "c1", "channel": "amazon", "status": "approved", "kind": "fee_step", "module": "margin",
     "action_text": "Move SKU-3 under the 1 lb band edge.", "expected_impact_usd": 400,
     "measured_impact_usd": None, "executed_at": "2026-09-20T00:00:00Z", "created_at": "2026-09-14T11:00:00Z",
     "issued_at": "2026-09-14T11:00:00Z"},
    {"id": "old1", "client_id": "c1", "channel": "amazon", "status": "issued", "kind": "price_step", "module": "pricing",
     "action_text": "An older notice.", "expected_impact_usd": 100, "created_at": "2026-09-21T11:00:00Z",
     "issued_at": "2026-09-21T11:05:00Z", "mandate": "explicit"},
]
NEW = [
    {"id": "new1", "client_id": "c1", "channel": "amazon", "status": "issued", "kind": "bid_cut", "mandate": "standing", "module": "advertising",
     "action_text": "Cut the bid on Campaign B by 15%.", "expected_impact_usd": 1200,
     "created_at": "2026-10-05T11:10:00Z", "issued_at": "2026-10-05T11:12:00Z"},
    {"id": "new2", "client_id": "c1", "channel": "amazon", "status": "draft", "kind": "reorder", "module": "inventory",
     "action_text": "Reorder SKU-2 by October 20.", "expected_impact_usd": 300, "created_at": "2026-10-05T11:10:00Z"},
]
MONTHS = [
    {"id": "m0", "client_id": "c1", "channel": "amazon", "month_index": 0, "month_start": "2026-08-02",
     "month_end": "2026-09-01", "free": True, "attributed_usd": 3000.0, "disputed_usd": 0.0, "fee_usd": 6000.0,
     "clears": False, "moves": [
         {"directive_id": "live1", "verdict": "measured", "usd": 3000.0, "attribution": "isolated"},
         {"directive_id": "live2", "verdict": "not_yet", "usd": None, "attribution": None}]},
]
LAST_NOTE = {"id": "n-prev", "client_id": "c1", "week_of": "2026-09-28", "status": "sent",
             "created_at": "2026-09-28T11:20:00Z", "facts": {}}
ALERTS = [
    {"id": "a-old", "client_id": "c1", "severity": "warning", "message": "Last week's news.",
     "created_at": "2026-09-28T11:15:00Z"},
    {"id": "a-new", "client_id": "c1", "severity": "critical", "message": "SKU-2: 61% stockout risk inside 14 days.",
     "created_at": "2026-10-05T11:15:00Z"},
]


class DB(FakeDB):
    """FakeDB with the delete a Brief discard uses."""

    def table(self, name):
        q = _Q(self, name)

        def delete():
            q.op = "update"
            q.patch = {"__deleted__": True}
            return q
        q.delete = delete
        return q

    def rows(self, name):
        return [r for r in self.store.get(name, []) if not r.get("__deleted__")]


def _db(busy=True, client=None, **extra):
    tables = dict(clients=[dict(client or AGREED)], directives=[dict(d) for d in LIVE + (NEW if busy else [])],
                  record_months=[dict(m) for m in MONTHS], weekly_notes=[dict(LAST_NOTE)],
                  alerts=[dict(a) for a in (ALERTS if busy else ALERTS[:1])],
                  record_seals=[{"client_id": "c1", "entry": "called", "directive_id": "new1", "leaf": LEAF, "seq": 1}],
                  recovery_claims=[], invoices=[], client_emails=[], briefings=[], bookings=[], consents=[])
    tables.update(extra)
    return DB(**tables)


@pytest.fixture
def mail(monkeypatch):
    sent = []
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(cli, "send_email",
                        lambda to, subject, text, html=None, **k: sent.append({"to": to, "subject": subject,
                                                                               "text": text, "html": html}) or True)
    return sent


# -- the Monday note ------------------------------------------------------------------------

def test_a_busy_week_drafts_found_sealed_and_watching_from_the_rows(mail):
    db = _db()
    res = approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    assert res["status"] == "drafted" and res["week_of"] == "2026-10-05"
    note = db.rows("weekly_notes")[-1]
    facts = note["facts"]
    assert note["status"] == "draft" and mail == []                # drafted, never sent
    # Found: this week's moves only (not last week's notice), expected dollars, the seal where sealed.
    assert facts["found"] == [
        "Cut the bid on Campaign B by 15%. (expected $1,200 · seal abcdef123456 · notice sent; goes live unless you say no)",
        "Reorder SKU-2 by October 20. (expected $300 · in review; it comes to you before it goes live)",
    ]
    # Sealed and holding: every live move, with what it held in the latest closed month.
    assert facts["holding"] == [
        "Raise SKU-1 from $19.99 to $21.49. (holding $3,000 in Aug 2 – Sep 1, 2026)",
        "Negative-match 11 search terms on Campaign A. (nothing measured in Aug 2 – Sep 1, 2026)",
        "Move SKU-3 under the 1 lb band edge. (live since Sep 20; first on your Record when the month ending Oct 1 closes)",
    ]
    # Watching: this week's alerts, the urgent first; last week's is not told twice.
    assert facts["watching"] == ["Urgent — SKU-2: 61% stockout risk inside 14 days."]
    assert facts["alert_ids"] == ["a-new"]
    assert facts["subject"] == "Urgent: This week on Acme: 2 moves found · 3 sealed and holding · 1 to watch"
    # The Record's one figure is the closed month, not the $2,800 the move measured alone.
    assert facts["proven"]["basis"] == "months" and facts["proven"]["usd"] == 3000.0
    assert "Your Profit Record: $3,000 proven since day one" in note["body_text"]
    assert "$2,800" not in note["body_text"]
    for line in facts["found"] + facts["holding"] + facts["watching"]:
        assert line in note["body_text"]                           # verbatim, no prose in between
    assert note["body_text"].startswith("Hi Dana,") and "Hagen" in note["body_text"]
    assert "Open Hubricon" in note["body_html"]


def test_a_quiet_week_still_drafts_the_note_and_keeps_every_sealed_leak_in_view(mail):
    db = _db(busy=False)
    assert approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)["status"] == "drafted"
    note = db.rows("weekly_notes")[-1]
    assert note["facts"]["found"] == [] and note["facts"]["watching"] == []
    assert len(note["facts"]["holding"]) == 3
    assert "Found this week: nothing new." in note["body_text"]
    assert "Watching: nothing new crossed a line this week." in note["body_text"]
    assert "holding $3,000" in note["body_text"]
    assert note["facts"]["subject"] == "This week on Acme: 0 moves found · 3 sealed and holding · nothing new to watch"


def test_a_second_pass_in_the_same_week_redrafts_the_one_note_and_supersedes_an_older_draft():
    db = _db(weekly_notes=[{"id": "n-old", "client_id": "c1", "week_of": "2026-09-28", "status": "draft",
                            "created_at": "2026-09-28T11:20:00Z", "facts": {}}])
    assert approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)["status"] == "drafted"
    assert approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)["status"] == "redrafted"
    rows = db.rows("weekly_notes")
    assert sum(1 for r in rows if r["week_of"] == "2026-10-05") == 1
    assert next(r for r in rows if r["id"] == "n-old")["status"] == "discarded"
    # A note already sent this week is never rewritten.
    this = next(r for r in rows if r["week_of"] == "2026-10-05")
    this["status"] = "sent"
    assert approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)["status"] == "sent"


def test_a_client_who_has_not_said_yes_gets_no_note():
    called = {**AGREED, "status": "pending", "retainer_started_at": None}
    db = _db(client=called, bookings=[{"client_id": "c1", "starts_at": "2026-10-01T15:00:00Z",
                                        "event_type": "Application call", "created_at": "2026-09-30T00:00:00Z"}],
             weekly_notes=[])
    res = approval.draft_weekly_note(db, called, "https://x/portal", now=NOW)
    assert res == {"status": "not_agreed", "stage": "called"}
    assert db.rows("weekly_notes") == []
    declined = {**AGREED, "status": "declined", "retainer_started_at": None}
    assert approval.draft_weekly_note(_db(client=declined), declined, "https://x/portal", now=NOW)["status"] == "not_agreed"


# -- approving the note ---------------------------------------------------------------------

def test_approve_sends_the_note_exactly_as_drafted_once(mail):
    db = _db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    note = dict(db.rows("weekly_notes")[-1])
    out = []
    res = approval.approve(db, now=NOW + timedelta(hours=2), out=out.append)
    assert res["sent"] == 1 and len(mail) == 1
    assert mail[0]["to"] == "dana@acme.com" and mail[0]["subject"] == note["facts"]["subject"]
    assert mail[0]["text"] == note["body_text"] and mail[0]["html"] == note["body_html"]
    sent = db.rows("weekly_notes")[-1]
    assert sent["status"] == "sent" and sent["approved_at"] and sent["sent_at"]
    assert next(a for a in db.rows("alerts") if a["id"] == "a-new")["emailed_at"]
    assert db.rows("client_emails")[-1]["kind"] == "weekly_note"
    # Nothing is left waiting, and nothing goes twice.
    out.clear()
    assert approval.approve(db, now=NOW + timedelta(hours=3), out=out.append)["sent"] == 0
    assert out == ["Nothing is waiting for your approval."] and len(mail) == 1


def test_a_note_older_than_ten_days_is_refused_without_stale(mail):
    db = _db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    later = NOW + timedelta(days=11)
    out = []
    res = approval.approve(db, now=later, out=out.append)
    assert res["sent"] == 0 and mail == [] and db.rows("weekly_notes")[-1]["status"] == "draft"
    assert "drafted 11 days ago, more than 10: the facts have moved since" in res["refused"][0]
    assert "--stale" in out[-1]
    assert approval.approve(db, stale=True, now=later, out=out.append)["sent"] == 1 and len(mail) == 1


def test_a_note_whose_record_figure_moved_is_refused_without_stale(mail):
    db = _db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    db.store["record_months"][0]["disputed_usd"] = 500.0          # `hubricon dispute` after the draft
    res = approval.approve(db, now=NOW + timedelta(hours=1), out=lambda *_: None)
    assert res["sent"] == 0 and mail == []
    assert "($3,000 proven since day one then, $2,500 proven since day one now)" in res["refused"][0]


def test_show_prints_in_full_and_sends_only_on_a_yes(mail):
    db = _db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    out = []
    # No terminal to answer on: a preview, nothing sent.
    res = approval.approve(db, show=True, ask=None, now=NOW, out=out.append)
    assert res["left"] == 1 and mail == []
    shown = "\n".join(out)
    assert "Subject: Urgent: This week on Acme" in shown and "Watching:" in shown
    assert approval.approve(db, show=True, ask=lambda _p: "n", now=NOW, out=out.append)["left"] == 1 and mail == []
    assert approval.approve(db, show=True, ask=lambda _p: "y", now=NOW, out=out.append)["sent"] == 1 and len(mail) == 1


def test_a_note_can_be_discarded_and_then_is_never_sent(mail):
    db = _db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    assert approval.approve(db, discard_all=True, now=NOW, out=lambda *_: None)["discarded"] == 1
    assert db.rows("weekly_notes")[-1]["status"] == "discarded"
    assert approval.approve(db, now=NOW, out=lambda *_: None)["sent"] == 0 and mail == []
    # ...and the week's sweep does not bring it back.
    assert approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)["status"] == "discarded"


# -- the Profit Brief -----------------------------------------------------------------------

@pytest.fixture
def issue_env(monkeypatch):
    """_publish_issue on the fake database: the run is stubbed, the report and
    video are absent, and no narrator is configured."""
    from hubricon_engine import video
    from hubricon_engine.report import html_report
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli, "_latest_run", lambda db, cid, run_id, channel=None, required=True:
                        {"id": "run1", "params": {"channel": "amazon"}})

    def no_report(*a, **k):
        raise RuntimeError("no report in tests")
    monkeypatch.setattr(html_report, "generate", no_report)
    monkeypatch.setattr(video, "render", lambda *a, **k: None)


def _brief_db(**extra):
    first = {"id": "b1", "client_id": "c1", "issue_number": 1, "status": "published", "memo": "Profit Brief No. 001",
             "created_at": "2026-09-01T00:00:00Z", "headline": "Profit Brief No. 001 — your first full read"}
    return _db(briefings=[first], margin_results=[], elasticity_results=[], **extra)


def test_brief_two_is_a_draft_nothing_sent_or_published_until_approved(mail, issue_env):
    db = _brief_db()
    res = cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 5))
    assert res["held"] and res["issue_number"] == 2 and not res["emailed"]
    assert mail == []                                             # --send in the job sends nothing
    draft = next(b for b in db.rows("briefings") if b["issue_number"] == 2)
    assert draft["status"] == "draft"                             # the portal's policy reads published only
    facts = draft["facts"]
    assert facts["subject"] == "Profit Brief No. 002 — $3,000 proven, $1,300 found on your Record"
    assert facts["record_line"].startswith("Your Profit Record: $3,000 proven since day one")
    assert "$3,000 proven since day one across 1 move" in draft["memo"]       # the letter: the same figure
    assert "$2,800" not in draft["memo"] and "$2,800" not in facts["subject"]
    # Run again inside the fortnight: the draft keeps waiting, nothing new is made.
    assert cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 6)) is None
    assert sum(1 for b in db.rows("briefings") if b["issue_number"] == 2) == 1

    # The founder approves: published and emailed, exactly as drafted.
    res = approval.approve(db, now=datetime.now(timezone.utc), out=lambda *_: None)
    assert res["published"] == 1 and res["emailed"] == 1
    brief = next(b for b in db.rows("briefings") if b["issue_number"] == 2)
    assert brief["status"] == "published" and brief["approved_at"]
    assert mail[-1]["subject"] == facts["subject"]
    assert facts["record_line"] in mail[-1]["text"]
    assert mail[-1]["text"].count("Your Profit Record:") == 1     # the drafted footer, not a second one


class _Bucket:
    def __init__(self, files):
        self.files = files

    def upload(self, path, data, opts=None):
        self.files[path] = data

    def download(self, path):
        return self.files[path]

    def remove(self, paths):
        for p in paths:
            self.files.pop(p, None)


def test_a_held_briefs_files_wait_outside_the_clients_folder_until_approval(mail, issue_env, monkeypatch, tmp_path):
    """The client's sign-in may read reports/{client}/ (the storage policy), so a
    draft's report and video wait in drafts/{client}/ and move on approval."""
    from hubricon_engine import video
    from hubricon_engine.report import html_report
    page, film = tmp_path / "r.html", tmp_path / "v.mp4"
    page.write_text("<p>report</p>")
    film.write_bytes(b"mp4")
    monkeypatch.setattr(html_report, "generate", lambda *a, **k: page)
    monkeypatch.setattr(video, "render", lambda *a, **k: film)
    db = _brief_db()
    files = {}
    db.storage = SimpleNamespace(from_=lambda bucket: _Bucket(files))
    cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 5))
    draft = next(b for b in db.rows("briefings") if b["issue_number"] == 2)
    assert draft["report_path"] == "drafts/c1/issue-002.html" and draft["video_path"] == "drafts/c1/issue-002.mp4"
    assert not any(p.startswith("reports/") for p in files)
    approval.approve(db, now=datetime.now(timezone.utc), out=lambda *_: None)
    brief = next(b for b in db.rows("briefings") if b["issue_number"] == 2)
    assert brief["status"] == "published"
    assert brief["report_path"] == "reports/c1/issue-002.html" and brief["video_path"] == "reports/c1/issue-002.mp4"
    assert files == {"reports/c1/issue-002.html": b"<p>report</p>", "reports/c1/issue-002.mp4": b"mp4"}


def test_issue_one_is_not_held(mail, issue_env):
    db = _db(briefings=[], margin_results=[], elasticity_results=[])
    res = cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 5))
    assert res["issue_number"] == 1 and not res.get("held")
    assert db.rows("briefings")[-1].get("status", "published") == "published"
    assert len(mail) == 1


def test_a_stale_brief_draft_is_redrafted_in_place_under_its_own_number(mail, issue_env):
    stale = {"id": "b2", "client_id": "c1", "issue_number": 2, "status": "draft", "memo": "old",
             "created_at": "2026-09-20T00:00:00Z",
             "facts": {"channel": "amazon", "proven": {"usd": 1.0, "basis": "measured"}}}
    db = _brief_db()
    db.store["briefings"].append(stale)
    out = []
    assert approval.approve(db, now=NOW, out=out.append)["published"] == 0     # refused: eleven days old
    assert "re-draft it with `hubricon issue --client dana@acme.com --force`" in out[-1].lower()
    res = cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 5))
    assert res["held"] and res["issue_number"] == 2
    rows = [b for b in db.rows("briefings") if b["issue_number"] == 2]
    assert len(rows) == 1 and rows[0]["id"] == "b2" and rows[0]["memo"] != "old" and mail == []


def test_a_client_who_has_not_said_yes_gets_no_second_brief(mail, issue_env):
    called = {**AGREED, "status": "pending", "retainer_started_at": None}
    db = _brief_db(bookings=[{"client_id": "c1", "starts_at": "2026-09-01T15:00:00Z",
                              "event_type": "Application call", "created_at": "2026-08-30T00:00:00Z"}])
    db.store["clients"] = [called]
    assert cli._publish_issue(db, called, "amazon", send=True, today=date(2026, 10, 5)) is None
    assert [b["issue_number"] for b in db.rows("briefings")] == [1] and mail == []


# -- the digest ----------------------------------------------------------------------------

def test_the_founders_digest_names_what_waits_with_its_first_lines(mail, issue_env):
    db = _brief_db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 5))
    lines = approval.digest_lines(db, now=NOW)
    assert lines[0] == "Waiting for your approval: 1 note, 1 brief — `hubricon approve all --show`"
    text = "\n".join(lines)
    assert "Acme · weekly note, week of 2026-10-05: Urgent: This week on Acme" in text
    assert "Found: Cut the bid on Campaign B by 15%." in text
    assert "Acme · Profit Brief No. 002: Profit Brief No. 002 — $3,000 proven" in text
    from hubricon_engine import operator
    digest = operator.Pass(db, send=False, dry=True).digest_text()
    assert "Waiting for your approval: 1 note, 1 brief" in digest


# -- without the migration -----------------------------------------------------------------

class _OldQ(_Q):
    def eq(self, col, val):
        if self.name == "briefings" and col == "status":
            raise RuntimeError("column briefings.status does not exist (42703)")
        return super().eq(col, val)

    def insert(self, rows):
        for r in rows if isinstance(rows, list) else [rows]:
            if self.name == "briefings" and ("status" in r or "facts" in r):
                raise RuntimeError("Could not find the 'facts' column of 'briefings' in the schema cache (PGRST204)")
        return super().insert(rows)


class PreMigration(FakeDB):
    def table(self, name):
        if name == "weekly_notes":
            raise RuntimeError('relation "public.weekly_notes" does not exist (42P01)')
        return _OldQ(self, name)


def _old_db(client=None):
    tables = dict(clients=[dict(client or AGREED)], directives=[dict(d) for d in LIVE + NEW],
                  record_months=[dict(m) for m in MONTHS], alerts=[], recovery_claims=[], invoices=[],
                  client_emails=[], bookings=[], consents=[], margin_results=[], elasticity_results=[],
                  briefings=[{"id": "b1", "client_id": "c1", "issue_number": 1, "memo": "x",
                              "created_at": "2026-09-01T00:00:00Z"}])
    return PreMigration(**tables)


def test_without_the_migration_the_brief_publishes_and_sends_as_before_and_the_digest_says_so(mail, issue_env):
    db = _old_db()
    res = cli._publish_issue(db, dict(AGREED), "amazon", send=True, today=date(2026, 10, 5))
    assert res["issue_number"] == 2 and res["emailed"] and not res.get("held")
    assert "status" not in db.rows("briefings")[-1] and len(mail) == 1
    assert mail[0]["subject"] == "Profit Brief No. 002 — $3,000 proven, $1,300 found on your Record"
    lines = approval.digest_lines(db)
    assert lines[0].startswith("APPROVAL GATE OFF: apply supabase/migrations/20261001000004_notes_approved.sql")
    out = []
    assert approval.approve(db, out=out.append)["gate"] is False
    assert approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)["status"] == "unavailable"


def _sweep_stubs(monkeypatch, fresh):
    from hubricon_engine import issue
    monkeypatch.setattr(issue, "close_veto_windows", lambda db, c, ch: {"auto_approved": 0, "lapsed": 0})
    monkeypatch.setattr(issue, "overdue_executions", lambda db, c, ch: [])
    monkeypatch.setattr(cli, "_run_models", lambda *a, **k: "run1")
    monkeypatch.setattr(cli, "_draft_for_run", lambda *a, **k: [])
    monkeypatch.setattr(cli, "_measure_for_run", lambda *a, **k: [])
    monkeypatch.setattr(cli, "_close_months", lambda *a, **k: [])
    monkeypatch.setattr(cli, "compute_alerts", lambda *a, **k: [dict(x) for x in fresh])


SKU_ROW = {"client_id": "c1", "channel": "amazon", "id": "s1"}
FRESH = [{"severity": "critical", "message": "SKU-9: 70% stockout risk inside 10 days.", "kind": "stockout"}]


def test_the_sweep_drafts_the_note_and_sends_no_watch_email(mail, monkeypatch):
    _sweep_stubs(monkeypatch, FRESH)
    db = _db(sku_economics=[SKU_ROW], weekly_notes=[])
    out = cli._sweep_channel(db, dict(AGREED), "amazon", "Acme", send_alerts=True)
    assert out["note"] == "drafted" and out["alerts"] == 1 and not out["emailed"] and mail == []
    alert = next(a for a in db.rows("alerts") if a.get("message", "").startswith("SKU-9"))
    assert alert["emailed_at"] is None                            # in the portal; in the inbox once approved
    note = db.rows("weekly_notes")[-1]
    assert "Urgent — SKU-9: 70% stockout risk inside 10 days." in note["facts"]["watching"]
    # A quiet Monday drafts the note too (it used to send nothing at all).
    _sweep_stubs(monkeypatch, [])
    quiet = _db(busy=False, sku_economics=[SKU_ROW], weekly_notes=[], alerts=[])
    assert cli._sweep_channel(quiet, dict(AGREED), "amazon", "Acme", send_alerts=True)["note"] == "drafted"
    assert "nothing new crossed a line this week" in quiet.rows("weekly_notes")[-1]["body_text"]


def test_without_the_migration_the_sweep_sends_the_watch_email_as_before_to_an_agreed_client_only(mail, monkeypatch):
    _sweep_stubs(monkeypatch, FRESH)
    db = _old_db()
    db.store["sku_economics"] = [SKU_ROW]
    out = cli._sweep_channel(db, dict(AGREED), "amazon", "Acme", send_alerts=True)
    assert out["note"] == "unavailable" and out["emailed"] and len(mail) == 1
    assert mail[0]["subject"] == "1 urgent item on Acme"
    assert "$3,000 proven since day one" in mail[0]["text"]        # the footer reads the one figure
    assert db.rows("alerts")[-1]["emailed_at"]
    called = {**AGREED, "status": "pending", "retainer_started_at": None}
    db = _old_db(client=called)
    db.store["sku_economics"] = [SKU_ROW]
    assert not cli._sweep_channel(db, called, "amazon", "Acme", send_alerts=True)["emailed"] and len(mail) == 1


# -- the command ---------------------------------------------------------------------------

def test_the_command_keeps_the_directive_meaning_and_sends_drafts_otherwise(mail, monkeypatch):
    db = _db()
    approval.draft_weekly_note(db, AGREED, "https://x/portal", now=NOW)
    monkeypatch.setattr(cli.dbmod, "connect", lambda: db)
    monkeypatch.setattr(cli.dbmod, "resolve_client", lambda _db, ident: AGREED)
    cli.cmd_approve(SimpleNamespace(client="dana@acme.com", show=False, stale=False, discard=False,
                                    directive=None, decline=False))
    assert len(mail) == 1 and db.rows("weekly_notes")[-1]["status"] == "sent"
    cli.cmd_approve(SimpleNamespace(client="dana@acme.com", show=False, stale=False, discard=False,
                                    directive="new1", decline=True))
    assert next(d for d in db.rows("directives") if d["id"] == "new1")["status"] == "declined"
    with pytest.raises(SystemExit):
        cli.cmd_approve(SimpleNamespace(client="all", show=False, stale=False, discard=False,
                                        directive="new1", decline=False))
