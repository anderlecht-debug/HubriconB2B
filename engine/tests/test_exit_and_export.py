"""Leaving never means going blind (2026-10-01).

The export a client asks for is built, stored and emailed by the machine
(terms §11, within one working day); the client who leaves gets one letter,
billed or not, with the true-up, the export and what to keep watching; and the
refund owed at the exit runs on a seven-day clock the digest and `hubricon
promises` count (terms §5). All on the fake database and a fake storage bucket:
nothing here reaches Supabase, Stripe or Resend."""

import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from hubricon_engine import billing, cli, monthly, operator, storage
from fakedb import FakeDB


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


class FakeBucket:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def upload(self, path, blob, options=None):
        if self.store.fail:
            raise RuntimeError(f"Bucket not found: {self.name}")
        self.store.objects[(self.name, path)] = (bytes(blob), dict(options or {}))
        return {"Key": f"{self.name}/{path}"}

    def create_signed_url(self, path, expires_in, options=None):
        self.store.signed.append((self.name, path, expires_in, dict(options or {})))
        return {"signedURL": f"https://store.test/{self.name}/{path}?token=t&ttl={expires_in}"}

    def download(self, path):
        if (self.name, path) not in self.store.objects:
            raise RuntimeError("Object not found")
        return self.store.objects[(self.name, path)][0]

    def list(self, path=None, options=None):
        if self.store.fail:
            raise RuntimeError(f"Bucket not found: {self.name}")
        return []


class FakeStorage:
    def __init__(self, fail=False):
        self.fail = fail
        self.objects, self.signed = {}, []

    def from_(self, name):
        return FakeBucket(self, name)


NOW = datetime.now(timezone.utc)
START = date.today() - timedelta(days=100)


def _utc_today() -> date:
    """The day the operator stamps (its timestamps are UTC). date.today() is the
    machine's local day, which differs between UTC midnight and local midnight,
    and failed this test every evening in Chicago (found 2026-10-01)."""
    return datetime.now(timezone.utc).date()


def _client(**kw):
    base = {"id": "c1", "company_name": "Alpha", "contact_email": "a@alpha.com", "contact_name": "Ana Alpha",
            "status": "active", "platform": "amazon", "plan": "retainer", "monthly_fee_usd": 6000, "free_months": 1,
            "retainer_started_at": START.isoformat(), "stripe_customer_id": None, "stripe_subscription_id": None,
            "exit_trued_up_at": None, "exit_refund_usd": None}
    base.update(kw)
    return base


def _req(rid, kind, client_id="c1", hours_ago=1, due_in_days=1, **kw):
    return {"id": rid, "client_id": client_id, "kind": kind, "requester_email": "a@alpha.com",
            "opened_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
            "due_at": (NOW + timedelta(days=due_in_days)).isoformat(), "closed_at": None, **kw}


def _db(**tables):
    base = dict(clients=[_client()], data_requests=[], client_emails=[], directives=[], recovery_claims=[],
                invoices=[], record_months=[], uploads=[], briefings=[])
    base.update(tables)
    return FakeDB(**base)


def _mail(monkeypatch, ok=True):
    """Every client email, captured and logged as the real sender logs it."""
    sent = []

    def fake(db, client, kind, ref_id, subject, blocks, send):
        if not send:
            return False
        if db.table("client_emails").select("id").eq("client_id", client["id"]).eq("kind", kind) \
                .eq("ref_id", str(ref_id)).execute().data:
            return False
        if not ok:
            return False
        sent.append({"to": client["contact_email"], "kind": kind, "ref": str(ref_id), "subject": subject,
                     "blocks": blocks})
        db.table("client_emails").insert({"client_id": client["id"], "kind": kind, "ref_id": str(ref_id),
                                          "subject": subject}).execute()
        return True

    monkeypatch.setattr(cli, "_send_client_email", fake)
    monkeypatch.setattr(operator, "email_configured", lambda: True)
    return sent


def _text(blocks) -> str:
    return " ".join(b.get("p", "") + " ".join(b.get("ol", [])) + b.get("button", "") for b in blocks)


# -- the export: one zip, this client's rows and nothing else ------------------------------

def test_the_export_holds_what_invoices_are_judged_against_and_how_to_check_it():
    other = {"client_id": "c2", "month_index": 1, "attributed_usd": 1.0, "disputed_usd": 0}
    db = _db(record_months=[{"client_id": "c1", "channel": "amazon", "month_index": 1, "month_start": "2026-08-02",
                             "month_end": "2026-09-01", "attributed_usd": 7200.0, "disputed_usd": 200.0,
                             "moves": [{"directive_id": "d1", "verdict": "measured", "usd": 7200.0}]}, other],
             results=[{"client_id": "c1", "kind": "gate_cleared", "amount_usd": 7000}],
             customer_orders=[{"client_id": "c1", "order_name": "#1001", "revenue": 42.0}],
             recovery_invoices=[{"client_id": "c1", "amount_usd": 25.0}],
             client_emails=[{"client_id": "c1", "kind": "agreed", "ref_id": "c1", "subject": "Your yes"}],
             uploads=[{"id": "up-000001", "client_id": "c1", "storage_path": "c1/a.csv", "original_filename": "a.csv"}])
    db.storage = FakeStorage()
    db.storage.objects[("intake", "c1/a.csv")] = (b"sku,units\nA,1\n", {})
    z = zipfile.ZipFile(io.BytesIO(cli.build_export(db, "c1")))
    names = set(z.namelist())
    for table in ("record_months", "results", "customer_orders", "recovery_invoices", "client_emails"):
        assert f"tables/{table}.csv" in names, table
    assert "c2" not in z.read("tables/record_months.csv").decode()        # one client's rows, never another's
    assert {"profit-record.json", "record-seal.json", "verify-record.mjs", "HOW-TO-VERIFY.txt", "MANIFEST.txt",
            "raw/up-00000-a.csv"} <= names
    assert "ledger.json" not in names                                      # a retired word, as a file name too
    assert z.read("raw/up-00000-a.csv") == b"sku,units\nA,1\n"
    manifest = z.read("MANIFEST.txt").decode()
    assert "$7,000 proven on your Profit Record since day one" in manifest  # the one number, after the dispute
    assert "record_seals: empty" in manifest and "raw/ — 1 uploaded file(s)" in manifest
    how = z.read("HOW-TO-VERIFY.txt").decode()
    assert "node verify-record.mjs record-seal.json" in how and "--seal" in how
    assert "could rewrite the whole" in how                                # what it does not prove, said plainly
    assert set(cli.EXPORT_TABLES) >= {"record_months", "results", "customer_orders", "recovery_invoices",
                                      "client_emails", "record_seals"}


def test_hubricon_export_writes_the_same_zip(monkeypatch, tmp_path, capsys):
    db = _db()
    monkeypatch.setattr(cli.dbmod, "connect", lambda: db)
    out = tmp_path / "alpha.zip"
    cli.cmd_export(SimpleNamespace(client="a@alpha.com", out=str(out), no_files=True))
    assert "HOW-TO-VERIFY.txt" in zipfile.ZipFile(out).namelist()
    assert "It is theirs, free, any time." in capsys.readouterr().out


# -- the export request, fulfilled by the machine --------------------------------------------

def test_an_export_request_is_built_stored_and_emailed_to_the_client_and_closed(monkeypatch):
    sent = _mail(monkeypatch)
    db = _db(data_requests=[_req("req-export-1", "access", requester_email="someone@else.test")])
    db.storage = FakeStorage()
    p = operator.Pass(db, send=True, dry=False)
    p.data_requests()
    [(bucket, path)] = list(db.storage.objects)
    assert (bucket, path) == ("exports", "c1/req-export-1.zip")
    blob, options = db.storage.objects[(bucket, path)]
    assert options["content-type"] == "application/zip" and "HOW-TO-VERIFY.txt" in zipfile.ZipFile(io.BytesIO(blob)).namelist()
    [(_, _, ttl, sign_opts)] = db.storage.signed
    assert ttl == 7 * 86400 and sign_opts["download"].startswith("alpha-hubricon-export-")
    [mail] = sent
    assert mail["to"] == "a@alpha.com" and mail["kind"] == "export_ready"   # the contact email, never the requester's
    assert {"button": "Download your export", "url": f"https://store.test/exports/{path}?token=t&ttl=604800"} in mail["blocks"]
    assert "works for seven days" in _text(mail["blocks"]) and "forward it with care" in _text(mail["blocks"])
    req = db.rows("data_requests")[0]
    assert req["closed_at"] and "seven" not in req["outcome"] and "7-day download link to a@alpha.com" in req["outcome"]
    assert p.human == [] and p.warnings == []
    # Closed: the next pass does nothing.
    operator.Pass(db, send=True, dry=False).data_requests()
    assert len(sent) == 1 and len(db.storage.objects) == 1


def test_without_the_bucket_the_request_stays_open_and_the_founder_is_told(monkeypatch):
    sent = _mail(monkeypatch)
    db = _db(data_requests=[_req("req-export-2", "access")])
    db.storage = FakeStorage(fail=True)
    p = operator.Pass(db, send=True, dry=False)
    p.data_requests()
    assert sent == [] and db.rows("data_requests")[0]["closed_at"] is None
    assert any("could not be stored" in w and "hubricon export" in w for w in p.warnings)
    assert p.human == ["New access request from a@alpha.com — due in 0d (req-expo). Run: hubricon export <client>"]


def test_a_pass_that_cannot_send_email_builds_nothing_and_a_dry_run_only_says(monkeypatch):
    _mail(monkeypatch)
    monkeypatch.setattr(operator, "email_configured", lambda: False)
    db = _db(data_requests=[_req("req-export-3", "access")])
    db.storage = FakeStorage()
    p = operator.Pass(db, send=True, dry=False)
    p.data_requests()
    assert db.storage.objects == {} and any("Run: hubricon export" in h for h in p.human)
    p = operator.Pass(db, send=True, dry=True)
    p.data_requests()
    assert db.storage.objects == {} and db.rows("data_requests")[0]["closed_at"] is None
    assert any("would build the export" in n for n in p.notes)


# -- the exit letter, always ----------------------------------------------------------------

def test_a_client_who_leaves_in_the_proving_month_gets_the_letter_once(monkeypatch):
    sent = _mail(monkeypatch)
    db = _db(clients=[_client(status="churned")], data_requests=[_req("exit-1", "exit", due_in_days=7)])
    db.storage = FakeStorage()
    p = operator.Pass(db, send=True, dry=False)
    p.billing()              # the billing pass never sees a client with no Stripe customer
    assert sent == []
    p.data_requests()
    [mail] = sent
    assert mail["kind"] == "exit_true_up" and mail["subject"] == "You've left Managed Profit: nothing more is invoiced"
    text = _text(mail["blocks"])
    assert "Nothing was ever charged, so there is nothing to true up and nothing is owed." in text
    assert "Download your full Profit Record" in text and ("exports", f"c1/exit-{_utc_today().isoformat()}.zip") in db.storage.objects
    assert db.rows("clients")[0]["exit_trued_up_at"] and db.rows("data_requests")[0]["closed_at"]
    for _ in range(2):
        operator.Pass(db, send=True, dry=False).billing()
        operator.Pass(db, send=True, dry=False).data_requests()
    assert len(sent) == 1                                                   # never twice


def _m(k, client):
    return monthly.billing_months(client, date.today())[k]


def _bill(i, status, k, client):
    start = (_m(k, client)["end"] + timedelta(days=1)).isoformat()
    return {"id": f"i{i}", "client_id": "c1", "stripe_invoice_id": f"in_{i}", "status": status,
            "amount_due": 6000, "amount_paid": 6000 if status == "paid" else 0, "period_start": start,
            "issued_at": f"{start}T00:00:00Z", "stripe_customer_id": "cus_1", "gate_decision": "covered"}


def _month_row(k, usd, client, moves=(), disputed=0.0):
    m = _m(k, client)
    return {"client_id": "c1", "channel": "amazon", "month_index": k, "month_start": m["start"].isoformat(),
            "month_end": m["end"].isoformat(), "attributed_usd": usd, "disputed_usd": disputed, "fee_usd": 6000,
            "moves": list(moves)}


def test_a_billed_client_is_trued_up_and_told_the_refund_was_issued_inside_the_clock(monkeypatch):
    calls = []
    monkeypatch.setattr(billing, "_stripe", lambda path, data=None, idempotency_key=None, method=None:
                        calls.append(path) or {})
    sent = _mail(monkeypatch)
    c = _client(status="churned", stripe_customer_id="cus_1")
    fee = {"id": "fee1", "client_id": "c1", "kind": "fee_anomaly",
           "evidence": {"item_id": "MUG-12OZ", "metric": "fba_fee_per_unit", "baseline": 3.86, "current": 4.12}}
    db = _db(clients=[c], directives=[fee],
             invoices=[_bill(1, "paid", 1, c), _bill(2, "paid", 2, c)],
             record_months=[_month_row(1, 9000.0, c),
                            _month_row(2, 7000.0, c, disputed=1500.0,
                                       moves=[{"directive_id": "fee1", "verdict": "measured", "usd": 640.0}])],
             data_requests=[_req("exit-2", "exit", hours_ago=2, due_in_days=7)])
    db.storage = FakeStorage()
    p = operator.Pass(db, send=True, dry=False)
    p.billing()
    assert "credit_notes" in calls                                          # month 2 no longer clears: refunded
    [mail] = sent
    assert mail["subject"] == "You've left Managed Profit: $6,000.00 refunded"
    text = _text(mail["blocks"])
    assert f"We issued it on {_utc_today():%B %-d}, within the seven days the terms promise from your email." in text
    assert "It cleared, so it stands." in text and "It did not clear, so it is refunded in full." in text
    assert "If the FBA fee on MUG-12OZ goes back up to $4.12 a unit, the $0.26 a unit step returns." in text
    assert db.rows("data_requests")[0]["closed_at"]                         # the clock closed with the letter
    assert db.rows("clients")[0]["exit_refund_usd"] == 6000.0


def test_a_letter_that_could_not_go_with_the_money_goes_on_the_next_pass_and_says_the_same(monkeypatch):
    calls = []
    monkeypatch.setattr(billing, "_stripe", lambda path, data=None, idempotency_key=None, method=None:
                        calls.append(path) or {})
    sent = _mail(monkeypatch)
    c = _client(status="churned", stripe_customer_id="cus_1")
    db = _db(clients=[c], invoices=[_bill(1, "open", 1, c)], record_months=[_month_row(1, 2000.0, c)],
             data_requests=[_req("exit-3", "exit", due_in_days=7)])
    db.storage = FakeStorage()
    p = operator.Pass(db, send=False, dry=False)         # no email this pass: the money still moves
    p.billing()
    p.data_requests()
    assert calls == ["invoices/in_1/void"] and sent == []
    assert db.rows("invoices")[0]["gate_note"] == billing.EXIT_VOID_NOTE
    assert db.rows("data_requests")[0]["closed_at"] is None
    assert any("the exit letter waits for a pass that can send email" in n for n in p.notes)
    assert any("Alpha left" in n and "the exit letter has not gone yet" in n for n in p.notes)
    promise = {r[0]: r for r in cli.promise_rows(db)}["A refund owed at the exit is issued within seven days of the email"]
    assert promise[2] is True and "Alpha: trued up; the exit letter still to go" in promise[3]
    p = operator.Pass(db, send=True, dry=False)
    p.billing()
    p.data_requests()
    [mail] = sent
    assert mail["subject"] == "You've left Managed Profit: $6,000 voided"
    assert "The unpaid invoice worth $6,000 is void" in _text(mail["blocks"])
    assert calls == ["invoices/in_1/void"]                                   # the money moved once
    assert db.rows("data_requests")[0]["closed_at"]


def test_a_refund_owed_without_a_stripe_key_is_due_then_overdue_in_the_digest_and_in_promises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    sent = _mail(monkeypatch)
    c = _client(status="churned", stripe_customer_id="cus_1")
    rows = dict(clients=[c], invoices=[_bill(1, "paid", 1, c)], record_months=[_month_row(1, 2000.0, c)])
    db = _db(**rows, data_requests=[_req("exit-4", "exit", due_in_days=5)])
    p = operator.Pass(db, send=True, dry=False)
    p.billing()
    p.data_requests()
    assert sent == [] and any("STRIPE_SECRET_KEY missing. The exit letter waits for it." in w for w in p.warnings)
    assert any("Alpha left" in n and "$6,000.00 to refund due by" in n for n in p.notes)
    promise = {r[0]: r for r in cli.promise_rows(db)}["A refund owed at the exit is issued within seven days of the email"]
    assert promise[2] is True and "Alpha: $6,000.00 to refund due" in promise[3]

    late = _db(**rows, data_requests=[_req("exit-5", "exit", hours_ago=24 * 9, due_in_days=-2)])
    p = operator.Pass(late, send=True, dry=False)
    p.data_requests()
    assert any(w.startswith("OVERDUE by 2d: Alpha left") and "$6,000.00 to refund was due by" in w for w in p.warnings)
    promise = {r[0]: r for r in cli.promise_rows(late)}["A refund owed at the exit is issued within seven days of the email"]
    assert promise[2] is False and "(PAST)" in promise[3]


def test_the_export_promise_is_judged_on_the_requests_actually_waiting(monkeypatch):
    db = _db(data_requests=[_req("r-ok", "access", due_in_days=1)])
    row = {r[0]: r for r in cli.promise_rows(db)}["Your export within one working day"]
    assert row[2] is True and "1 open, none late" in row[3] and "by hand" in row[3]   # the fake has no bucket
    db.storage = FakeStorage()
    row = {r[0]: r for r in cli.promise_rows(db)}["Your export within one working day"]
    assert "emails the client a seven-day link" in row[3]
    db = _db(data_requests=[_req("r-late", "access", hours_ago=60, due_in_days=-1)])
    row = {r[0]: r for r in cli.promise_rows(db)}["Your export within one working day"]
    assert row[2] is False and "PAST the one working day" in row[3]


# -- hubricon cancel starts the clock -----------------------------------------------------------

def _cancel(monkeypatch, db, **args):
    monkeypatch.setattr(cli.dbmod, "connect", lambda: db)
    # resolve_client reads a dozen columns, never the Stripe ids: cancel must read the rest itself.
    monkeypatch.setattr(cli.dbmod, "resolve_client", lambda _db, ident: {
        k: v for k, v in db.rows("clients")[0].items() if k in ("id", "company_name", "contact_email", "status")})
    cli.cmd_cancel(SimpleNamespace(client="a@alpha.com", **args))


def test_cancel_ends_the_subscription_and_starts_a_seven_day_exit_clock(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(billing, "_stripe", lambda path, data=None, idempotency_key=None, method=None:
                        calls.append((path, method)) or {})
    db = _db(clients=[_client(stripe_customer_id="cus_1", stripe_subscription_id="sub_1")])
    _cancel(monkeypatch, db, emailed="2026-10-01")
    assert ("subscriptions/sub_1", "DELETE") in calls                       # ended, though resolve_client hid it
    assert db.rows("clients")[0]["status"] == "churned"
    [clock] = db.rows("data_requests")
    assert clock["kind"] == "exit" and clock["opened_at"].startswith("2026-10-01")
    assert clock["due_at"].startswith("2026-10-08")
    out = capsys.readouterr().out
    assert "Exit clock started" in out and "the exit letter would go to a@alpha.com" in out
    _cancel(monkeypatch, db)                                                # twice is one exit
    assert len(db.rows("data_requests")) == 1 and "already running" in capsys.readouterr().out


def test_cancel_without_the_migration_says_the_clock_did_not_start(monkeypatch, capsys):
    db = _db()
    real = db.table

    def table(name):
        q = real(name)
        if name == "data_requests":
            q.insert = lambda rows: (_ for _ in ()).throw(RuntimeError('violates check constraint "data_requests_kind_check"'))
        return q

    monkeypatch.setattr(db, "table", table)
    _cancel(monkeypatch, db)
    out = capsys.readouterr().out
    assert "Exit clock NOT started" in out and "20261001000005_exit_and_export.sql" in out
    assert "exit letter waits for the migration" in out


def test_cancel_for_someone_who_never_said_yes_sends_no_exit_letter(monkeypatch, capsys):
    db = _db(clients=[_client(status="pending", retainer_started_at=None)])
    _cancel(monkeypatch, db)
    assert db.rows("data_requests") == [] and "never said yes" in capsys.readouterr().out


# -- what the export holds of the founder's drafts, and the clocks beside the exit ---------------

def test_the_export_holds_published_briefs_and_sent_notes_never_a_draft():
    """A Brief held for approval and a weekly note never sent are the founder's
    working papers: the client was told neither, so neither is in their zip,
    and a held Brief's report is not either. A Brief from before the approval
    gate has no status and was published."""
    db = _db(briefings=[
                 {"id": "b1", "client_id": "c1", "issue_number": 1, "report_path": "reports/c1/issue-001.html"},
                 {"id": "b2", "client_id": "c1", "issue_number": 2, "status": "published",
                  "report_path": "reports/c1/issue-002.html"},
                 {"id": "b3", "client_id": "c1", "issue_number": 3, "status": "draft", "memo": "HELD DRAFT",
                  "report_path": "drafts/c1/issue-003.html"}],
             weekly_notes=[
                 {"id": "n1", "client_id": "c1", "week_of": "2026-09-28", "status": "sent", "body_text": "SENT NOTE"},
                 {"id": "n2", "client_id": "c1", "week_of": "2026-10-05", "status": "draft", "body_text": "DRAFT NOTE"},
                 {"id": "n3", "client_id": "c1", "week_of": "2026-09-21", "status": "discarded",
                  "body_text": "DISCARDED NOTE"}])
    db.storage = FakeStorage()
    for path in ("reports/c1/issue-001.html", "reports/c1/issue-002.html", "drafts/c1/issue-003.html"):
        db.storage.objects[(storage.BUCKET, path)] = (b"<html></html>", {})
    z = zipfile.ZipFile(io.BytesIO(cli.build_export(db, "c1")))
    names = set(z.namelist())
    assert {"reports/issue-001.html", "reports/issue-002.html"} <= names
    assert "reports/issue-003.html" not in names
    briefs = z.read("tables/briefings.csv").decode()
    assert "b1" in briefs and "b2" in briefs and "HELD DRAFT" not in briefs
    notes = z.read("tables/weekly_notes.csv").decode()
    assert "SENT NOTE" in notes and "DRAFT NOTE" not in notes and "DISCARDED NOTE" not in notes
    manifest = z.read("MANIFEST.txt").decode()
    assert "tables/briefings.csv — 2 row(s)" in manifest and "tables/weekly_notes.csv — 1 row(s)" in manifest


def test_the_export_works_without_the_notes_migration():
    """Before 20261001000004 there is no weekly_notes table and no briefings
    status: the export is built as before, with no database error in it."""
    db = _db(briefings=[{"id": "b1", "client_id": "c1", "issue_number": 1}])
    real = db.table

    def table(name):
        if name == "weekly_notes":
            raise RuntimeError('relation "public.weekly_notes" does not exist (42P01)')
        return real(name)

    db.table = table
    z = zipfile.ZipFile(io.BytesIO(cli.build_export(db, "c1", files=False)))
    manifest = z.read("MANIFEST.txt").decode()
    assert "weekly_notes" not in manifest and "42P01" not in manifest
    assert "tables/briefings.csv — 1 row(s)" in manifest


def test_cancel_takes_the_day_the_email_arrived(monkeypatch):
    """`hubricon cancel <client> --emailed YYYY-MM-DD`: the refund clock runs
    seven days from the client's email, not from when the founder got to it."""
    import sys
    seen, real = [], cli.cmd_cancel
    monkeypatch.setattr(cli, "cmd_cancel", lambda args: seen.append(args))
    monkeypatch.setattr(sys, "argv", ["hubricon", "cancel", "a@alpha.com", "--emailed", "2026-09-30"])
    cli.main()
    assert seen[0].client == "a@alpha.com" and seen[0].emailed == "2026-09-30"
    monkeypatch.setattr(sys, "argv", ["hubricon", "cancel", "a@alpha.com"])
    cli.main()
    assert seen[1].emailed is None
    monkeypatch.setattr(sys, "argv", ["hubricon", "cancel", "a@alpha.com", "--emailed", "last tuesday"])
    with pytest.raises(SystemExit):
        cli.main()

    monkeypatch.setattr(cli, "cmd_cancel", real)
    db = _db(clients=[_client()])
    _cancel(monkeypatch, db, emailed=seen[0].emailed)
    [clock] = db.rows("data_requests")
    assert clock["opened_at"].startswith("2026-09-30") and clock["due_at"].startswith("2026-10-07")


def test_a_late_exit_is_counted_on_its_own_row_not_as_a_late_privacy_request():
    """The exit's refund clock (terms §5) has its own promise row; counted in the
    privacy clocks too, one late refund read as a late privacy request."""
    late = _db(data_requests=[_req("exit-9", "exit", hours_ago=24 * 9, due_in_days=-2)])
    rows = {r[0]: r for r in cli.promise_rows(late)}
    assert rows["A refund owed at the exit is issued within seven days of the email"][2] is False
    clocks = rows["Deletion in 30d · DSAR in 7d · breach in 72h"]
    assert clocks[2] is True and "no open request is past its deadline" in clocks[3]
    both = _db(data_requests=[_req("exit-9", "exit", hours_ago=24 * 9, due_in_days=-2),
                              _req("del-1", "deletion", hours_ago=24 * 40, due_in_days=-10)])
    clocks = {r[0]: r for r in cli.promise_rows(both)}["Deletion in 30d · DSAR in 7d · breach in 72h"]
    assert clocks[2] is False and "1 request(s) PAST" in clocks[3]
