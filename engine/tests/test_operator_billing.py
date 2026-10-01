"""The hourly billing pass, on the fake database: the rolling gate decides each
invoice once, and the recovery-only plan bills only what landed."""

from datetime import date, datetime, timedelta, timezone

import pytest

from hubricon_engine import billing, cli, operator, value
from hubricon_engine import onboarding
from fakedb import FakeDB


@pytest.fixture(autouse=True)
def _stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


def _client(**kw):
    base = {"id": "c1", "company_name": "Alpha", "contact_email": "a@alpha.com", "status": "active",
            "platform": "amazon", "plan": "retainer", "monthly_fee_usd": 6000, "free_months": 1,
            "retainer_started_at": "2026-08-02T00:00:00Z", "stripe_customer_id": "cus_1",
            "stripe_subscription_id": "sub_1", "recovery_share": 0.25}
    base.update(kw)
    return base


def _inv(i, status, start, amount=6000):
    return {"id": f"i{i}", "client_id": "c1", "stripe_invoice_id": f"in_{i}", "status": status,
            "amount_due": amount, "amount_paid": amount if status == "paid" else 0,
            "period_start": start, "period_end": start, "issued_at": f"{start}T00:00:00Z",
            "stripe_customer_id": "cus_1", "currency": "usd", "gate_decision": None}


def _measured(n, usd):
    return [{"id": f"d{k}", "client_id": "c1", "status": "approved", "attribution": "isolated",
             "measured_impact_usd": usd, "expected_impact_usd": usd} for k in range(n)]


def _last_month():
    return (date.today().replace(day=1) - timedelta(days=1)).replace(day=15).isoformat()


def test_recovery_only_bills_the_share_of_what_landed_and_marks_each_claim_once(monkeypatch):
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append(path)
        if path == "invoices":
            return {"id": "in_r1"}
        if path.endswith(("/finalize", "/send")):
            return {"id": "in_r1", "hosted_invoice_url": "https://pay/in_r1"}
        return {}

    monkeypatch.setattr(billing, "_stripe", stripe)
    client = _client(plan="recovery", stripe_subscription_id=None, retainer_started_at=None)
    claims = [{"id": "k1", "client_id": "c1", "status": "paid", "paid_amount": 1500.0, "paid_at": _last_month() + "T00:00:00Z",
               "filed_at": "2026-08-01T00:00:00Z", "claim_type": "lost", "deadline": "2026-12-01"},
              {"id": "k2", "client_id": "c1", "status": "paid", "paid_amount": 500.0, "paid_at": _last_month() + "T00:00:00Z",
               "case_id": "X", "claim_type": "damaged", "deadline": "2026-12-01"},
              {"id": "k3", "client_id": "c1", "status": "paid", "paid_amount": 900.0, "paid_at": _last_month() + "T00:00:00Z",
               "claim_type": "lost", "deadline": "2026-12-01"}]          # Amazon's own: never billed
    db = FakeDB(clients=[client], recovery_claims=claims, recovery_invoices=[], directives=[], invoices=[],
                client_emails=[], funnel_events=[])
    p = operator.Pass(db, send=False, dry=False)
    p._recovery_billing(dict(db.rows("clients")[0]), cli, billing, value)
    assert "subscriptions" not in calls and "invoiceitems" in calls
    ri = db.rows("recovery_invoices")[0]
    assert ri["recovered_usd"] == 2000.0 and ri["amount_usd"] == 500.0 and ri["n_claims"] == 2 and ri["stripe_invoice_id"] == "in_r1"
    marked = {k["id"]: k.get("recovery_invoice_id") for k in db.rows("recovery_claims")}
    assert marked["k1"] == ri["id"] and marked["k2"] == ri["id"] and marked["k3"] is None
    c = db.rows("clients")[0]
    assert c["retainer_started_at"] and c["retainer_source"] == "first_invoice"
    assert any(e["kind"] == "recovery_invoiced" for e in db.rows("funnel_events"))
    # the next pass finds nothing left to bill
    n = len(calls)
    operator.Pass(db, send=False, dry=False)._recovery_billing(dict(db.rows("clients")[0]), cli, billing, value)
    assert len(calls) == n


def test_recovery_only_never_enters_the_day_30_machinery(monkeypatch):
    monkeypatch.setattr(billing, "_stripe", lambda *a, **k: pytest.fail("no Stripe call expected"))
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    client = _client(plan="recovery", stripe_subscription_id=None, retainer_started_at="2026-01-01T00:00:00Z")
    db = FakeDB(clients=[client], recovery_claims=[], recovery_invoices=[], directives=[], invoices=[],
                client_emails=[], funnel_events=[], consents=[])
    p = operator.Pass(db, send=False, dry=False)
    p.billing()
    assert db.rows("clients")[0].get("stripe_subscription_id") is None
    assert db.rows("clients")[0].get("billing_decision") is None


def test_the_downsell_email_goes_once_at_day_14_to_an_amazon_seller_only(monkeypatch):
    sent = []
    monkeypatch.setattr(operator.Pass, "_reonboard", lambda self, c, kind: sent.append((c["id"], kind)))
    old = (date.today() - timedelta(days=15)).isoformat() + "T00:00:00Z"
    db = FakeDB(
        clients=[{"id": "a", "contact_email": "a@x.com", "status": "pending", "platform": "amazon", "created_at": old},
                 {"id": "s", "contact_email": "s@y.com", "status": "pending", "platform": "shopify", "created_at": old},
                 {"id": "r", "contact_email": "r@z.com", "status": "pending", "platform": "amazon", "plan": "recovery",
                  "created_at": old}],
        uploads=[],
        client_touches=[{"client_id": "a", "kind": "welcome", "sent_at": old},
                        {"client_id": "a", "kind": "nudge", "sent_at": old},
                        {"client_id": "a", "kind": "files", "sent_at": old},
                        {"client_id": "s", "kind": "welcome", "sent_at": old},
                        {"client_id": "s", "kind": "nudge", "sent_at": old},
                        {"client_id": "r", "kind": "welcome", "sent_at": old},
                        {"client_id": "r", "kind": "nudge", "sent_at": old}],
    )
    operator.Pass(db, send=False, dry=False).nudges()
    assert ("a", "downsell") in sent
    assert ("s", "files") in sent and ("s", "downsell") not in sent        # Shopify has no smaller door
    assert ("r", "files") in sent and ("r", "downsell") not in sent        # already on it


def test_the_downsell_email_names_the_share_and_asks_for_the_word():
    spec = onboarding.email_spec("downsell", "Dana", "https://x/intake?t=tok", "https://x/portal")
    text = " ".join(b.get("p", "") for b in spec["blocks"])
    assert f"{billing.RECOVERY_SHARE * 100:.0f}% of what actually lands" in text
    assert "Reply RECOVERY" in text and "nothing up front" in text
    assert "smaller door" in spec["subject"].lower()


def test_a_founder_who_chose_recovery_on_the_site_gets_none_of_the_teardown_nudges(monkeypatch):
    sent = []
    monkeypatch.setattr(operator.Pass, "_reonboard", lambda self, c, kind: sent.append((c["id"], kind)))
    old = (date.today() - timedelta(days=15)).isoformat() + "T00:00:00Z"
    db = FakeDB(
        clients=[{"id": "g", "contact_email": "g@x.com", "status": "pending", "platform": "amazon", "created_at": old}],
        uploads=[],
        client_touches=[{"client_id": "g", "kind": "recovery_welcome", "sent_at": old}],
    )
    operator.Pass(db, send=False, dry=False).nudges()
    assert sent == []


def test_the_recovery_welcome_names_the_share_and_asks_for_a_confirming_reply():
    spec = onboarding.email_spec("recovery_welcome", "Dana", "https://x/intake?t=tok", "https://x/portal")
    text = " ".join(b.get("p", "") for b in spec["blocks"])
    assert f"{billing.RECOVERY_SHARE * 100:.0f}% of what actually lands" in text
    assert "Reply to this email to confirm" in text and "nothing up front" in text
    assert "https://x/intake?t=tok" in [b.get("url") for b in spec["blocks"]]


def _day_31_client(**kw):
    started = (date.today() - timedelta(days=31)).isoformat() + "T00:00:00Z"
    return _client(status="pending", stripe_subscription_id=None, retainer_started_at=started, **kw)


def test_every_client_email_closes_on_the_record_line_except_the_billing_letters(monkeypatch):
    sent = []
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(cli, "send_email", lambda to, subject, text, html=None, **k: sent.append((subject, text, html)) or True)
    made = {"id": "d1", "client_id": "c1", "status": "approved", "executed_at": "2026-09-01T00:00:00Z",
            "measured_impact_usd": None, "expected_impact_usd": 2400.0}
    db = FakeDB(clients=[_client()], directives=_measured(1, 5415.0) + [made], recovery_claims=[],
                invoices=[_inv(1, "paid", "2026-09-01")], client_emails=[])
    client = dict(db.rows("clients")[0])
    line = ("Your Profit Record: $5,415 proven since day one · $2,400 found and filed, not yet banked · "
            "$6,000 billed to date · 0.9× proven ÷ billed.")

    assert cli._send_client_email(db, client, "issue_ready", "b1", "Profit Brief No. 002", [{"p": "It is ready."}], True)
    subject, text, html = sent[-1]
    assert line in text and line in html and text.index("It is ready.") < text.index(line)

    for kind in ("guarantee_cleared", "guarantee_short", "month_waived", "exit_true_up"):
        assert cli._send_client_email(db, client, kind, f"ref-{kind}", "verdict", [{"p": "The arithmetic."}], True)
        assert "Your Profit Record:" not in sent[-1][1]
    assert cli.RECORD_FOOTER_EXEMPT == {"guarantee_cleared", "guarantee_short", "month_waived", "exit_true_up"}

    # A footer failure never blocks the letter.
    monkeypatch.setattr(cli, "_fetch_claims", lambda db, cid: (_ for _ in ()).throw(RuntimeError("claims table missing")))
    assert cli._send_client_email(db, client, "issue_ready", "b2", "Profit Brief No. 003", [{"p": "Still ready."}], True)
    assert "Still ready." in sent[-1][1] and "Your Profit Record:" not in sent[-1][1]


def test_the_issue_email_leads_with_the_record_not_the_periods_net_profit():
    """The briefings row keeps the net-profit headline for the portal; the
    inbox gets the numbers the invoice is judged on. 'Net profit down $300'
    is a period proxy — the Record is proven and found since day one."""
    headline = "Profit Brief No. 007 — net profit down $300"
    subject = cli._issue_subject(7, headline, 13870, 2400)
    assert subject == "Profit Brief No. 007 — $13,870 proven, $2,400 found on your Record"
    assert "proven" in subject and "net profit" not in subject
    # Found alone is enough to lead with the Record; an empty Record falls back as before.
    assert cli._issue_subject(7, headline, 0, 2400) == "Profit Brief No. 007 — $0 proven, $2,400 found on your Record"
    assert cli._issue_subject(7, headline, 0, 0) == "Profit Brief No. 007 — net profit down $300"
    assert cli._issue_subject(7, "Profit Brief No. 007", 0, 0) == "Profit Brief No. 007 is in Hubricon"

    blocks = cli._issue_email_blocks(7, 13870, 2400, has_video=True)
    assert blocks[0] == {"p": "Your Profit Brief is ready — $13,870 proven on your Record since day one, "
                              "$2,400 found and filed."}
    body = " ".join(b.get("p", "") for b in blocks)
    assert "net profit" not in body and "short video" in body
    assert "Before it goes live" in body                     # the veto section is named as the portal names it
    assert cli._issue_email_blocks(7, 0, 0, has_video=False)[0]["p"] == \
        "Your Profit Brief is ready — $0 proven on your Record since day one, $0 found and filed."


# -- the legal clocks in the digest ----------------------------------------------------

def test_a_data_request_is_named_the_day_it_opens_not_only_when_its_clock_is_short():
    """privacy.html gives each request a deadline. The founder hears about a
    request the day it is opened (with the export to run), and again in the
    last two days; a request three days old with weeks to run is quiet."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    fresh = {"id": "req-fresh-1", "kind": "access", "requester_email": "dana@acme.test",
             "opened_at": (now - timedelta(hours=1)).isoformat(),
             "due_at": (now + timedelta(days=7)).isoformat(), "closed_at": None}
    settled = {"id": "req-settled", "kind": "deletion", "requester_email": "sam@beta.test",
               "opened_at": (now - timedelta(days=3)).isoformat(),
               "due_at": (now + timedelta(days=27)).isoformat(), "closed_at": None}
    closing = {"id": "req-closing", "kind": "correction", "requester_email": "kim@gamma.test",
               "opened_at": (now - timedelta(days=5)).isoformat(),
               "due_at": (now + timedelta(days=1)).isoformat(), "closed_at": None}
    done = {"id": "req-done", "kind": "access", "requester_email": "old@delta.test",
            "opened_at": (now - timedelta(hours=2)).isoformat(),
            "due_at": (now + timedelta(days=7)).isoformat(), "closed_at": now.isoformat()}
    p = operator.Pass(FakeDB(data_requests=[fresh, settled, closing, done]), send=False, dry=False)
    p.data_requests()
    assert p.human == [
        "correction request from kim@gamma.test is due in 0d (req-clos).",
        "New access request from dana@acme.test — due in 6d (req-fres). Run: hubricon export <client>",
    ]
    assert p.warnings == []
    assert not any("sam@beta.test" in h or "old@delta.test" in h for h in p.human)


# -- the guarantee stack, 2026-09-25 -------------------------------------------------------

def _stripe_log(monkeypatch, replies=None):
    calls = []

    def fake(path, data=None, idempotency_key=None, method=None):
        calls.append(path)
        return (replies or {}).get(path, {})

    monkeypatch.setattr(billing, "_stripe", fake)
    return calls


def test_a_client_whose_ach_payment_failed_is_still_gated(monkeypatch):
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_client(status="past_due")], directives=[], recovery_claims=[], client_emails=[],
                invoices=[_inv(1, "open", "2026-09-01")], funnel_events=[])
    operator.Pass(db, send=False, dry=False).billing()
    assert calls == ["invoices/in_1/void"] and db.rows("invoices")[0]["status"] == "void"


def test_a_slow_first_issue_no_longer_adds_a_free_month(monkeypatch):
    """The Teardown and its late-month promise were retired on 2026-09-30
    (HUBRICON_SPEC.md: "The Teardown is killed"), so a slow first read of a
    client's files writes nothing and sends nothing."""
    letters = []
    monkeypatch.setattr(cli, "_send_client_email", lambda db, c, kind, ref, subject, blocks, send: letters.append(kind) or False)
    landed = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    db = FakeDB(clients=[
        _client(id="slow", status="pending", stripe_subscription_id=None, retainer_started_at=None,
                exports_landed_at=landed, first_issue_at=None),
    ], directives=[], recovery_claims=[], invoices=[], client_emails=[], funnel_events=[])
    for _ in range(2):
        operator.Pass(db, send=False, dry=False).billing()
    slow = db.rows("clients")[0]
    assert slow["free_months"] == 1 and not slow.get("late_teardown_month_at")
    assert letters == []
    # A free month granted by hand is still honoured: nothing starts until the free months are over.
    assert billing.due_to_start({**slow, "free_months": 2, "retainer_started_at": "2026-08-01"}, date(2026, 9, 15))[0] is False


def test_the_teardown_clock_starts_when_the_first_readable_file_was_uploaded():
    """A late Teardown costs a month, so the clock cannot start when the
    hourly pass happens to notice the files; it starts when they arrived."""
    db = FakeDB(uploads=[
        {"id": "u1", "client_id": "c1", "status": "failed", "uploaded_at": "2026-09-01T08:00:00+00:00"},
        {"id": "u2", "client_id": "c1", "status": "parsed", "uploaded_at": "2026-09-01T09:15:00+00:00"},
        {"id": "u3", "client_id": "c1", "status": "parsed", "uploaded_at": "2026-09-01T11:00:00+00:00"},
        {"id": "u4", "client_id": "c1", "status": "parsed", "uploaded_at": None},
    ])
    p = operator.Pass(db, send=False, dry=False)
    assert p._first_file_at({"id": "c1"}) == datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc)
    assert p._first_file_at({"id": "c2"}) is None          # seat-pulled exports: the pass starts it


def test_without_the_migration_the_whole_billing_pass_waits_and_says_why(monkeypatch):
    """A refund made and not recorded could be made again once Stripe's key
    expired, so a missing column pauses everything, loudly."""
    monkeypatch.setattr(billing, "_stripe", lambda *a, **k: pytest.fail("no Stripe call without the schema"))
    db = FakeDB(clients=[_client(status="past_due")], invoices=[_inv(1, "open", "2026-09-01")], directives=[],
                recovery_claims=[])
    real = db.table

    def table(name):
        q = real(name)
        if name == "invoices":
            q.select = lambda *cols, **k: (_ for _ in ()).throw(RuntimeError("column invoices.refunded_usd does not exist")) \
                if cols and "refunded_usd" in cols[0] else q
        return q

    monkeypatch.setattr(db, "table", table)
    p = operator.Pass(db, send=False, dry=False)
    p.billing()
    assert any("Billing paused: apply supabase/migrations/20260925000001_guarantee_stack.sql" in w for w in p.warnings)
    assert db.rows("invoices")[0]["gate_decision"] is None


def test_the_promise_check_names_the_missing_migration_and_the_guarantees_it_blocks(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    db = FakeDB(clients=[], data_requests=[], invoices=[])
    rows = {r[0]: r for r in cli.promise_rows(db)}
    assert "A late Teardown makes the first paid month free" not in rows   # retired with the Teardown, 2026-09-30
    assert "The billing pass can run" not in rows
    for name in ("A month is billed only if it clears the fee", "Trued up the day you leave",
                 "A month a dispute takes under the fee is refunded, not credited"):
        assert name in rows and rows[name][2] is True
    real = db.table

    def table(name):
        q = real(name)
        if name == "invoices":
            q.select = lambda *cols, **k: (_ for _ in ()).throw(RuntimeError("42703")) if "refunded_usd" in cols[0] else q
        return q

    monkeypatch.setattr(db, "table", table)
    rows = {r[0]: r for r in cli.promise_rows(db)}
    assert rows["The billing pass can run"][2] is False and "20260925000001" in rows["The billing pass can run"][3]


# -- the guarantee, month by month (HUBRICON_SPEC.md, "The mechanics") ----------------

from hubricon_engine import monthly  # noqa: E402

_START = date.today() - timedelta(days=100)


def _monthly_client(**kw):
    return _client(retainer_started_at=_START.isoformat(), **kw)


def _m(k):
    return monthly.billing_months(_monthly_client(), date.today())[k]


def _month_row(k, usd, disputed=0.0):
    m = _m(k)
    return {"client_id": "c1", "channel": "amazon", "month_index": k, "month_start": m["start"].isoformat(),
            "month_end": m["end"].isoformat(), "attributed_usd": usd, "disputed_usd": disputed, "fee_usd": 6000}


def _bill(i, status, k):
    """Stripe raises the invoice for month k the day after it ends."""
    return _inv(i, status, (_m(k)["end"] + timedelta(days=1)).isoformat())


def _letters(monkeypatch):
    out = []
    monkeypatch.setattr(cli, "_send_client_email",
                        lambda db, c, kind, ref, subject, blocks, send: out.append((kind, subject)) or False)
    return out


def test_each_held_invoice_is_judged_against_its_own_month(monkeypatch):
    calls = _stripe_log(monkeypatch, {"invoices/in_1/send": {"id": "in_1", "status": "open", "number": "HUB-0001"}})
    letters = _letters(monkeypatch)
    db = FakeDB(clients=[_monthly_client()], invoices=[_bill(1, "draft", 1), _bill(2, "draft", 2)],
                record_months=[_month_row(1, 7000.0), _month_row(2, 3000.0)], consents=[],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[], referrals=[])
    p = operator.Pass(db, send=False, dry=False)
    p._month_gate(dict(db.rows("clients")[0]), cli, billing)
    by = {r["id"]: r for r in db.rows("invoices")}
    assert by["i1"]["gate_decision"] == "covered" and by["i1"]["status"] == "open" and by["i1"]["gate_month_index"] == 1
    assert by["i2"]["gate_decision"] == "waived" and by["i2"]["status"] == "void" and by["i2"]["gate_month_index"] == 2
    # A cleared month is finalized without Stripe's auto-send and sent once; a short one is voided unsent.
    assert calls == ["invoices/in_1/finalize", "invoices/in_1/send", "invoices/in_2/finalize", "invoices/in_2/void"]
    assert [k for k, _ in letters] == ["month_cleared", "month_unbilled"]
    assert "$3,000 on your Record, under the $6,000 fee. No invoice" in letters[1][1]
    # A month above the fee does not lend its surplus to the next one.
    assert by["i2"]["gate_value"] == 3000.0


def test_an_invoice_waits_while_its_month_is_unmeasured(monkeypatch):
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_monthly_client()], invoices=[_bill(2, "draft", 2)], record_months=[_month_row(1, 9000.0)],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    operator.Pass(db, send=False, dry=False)._month_gate(dict(db.rows("clients")[0]), cli, billing)
    assert calls == [] and db.rows("invoices")[0]["gate_decision"] is None


def test_a_dry_run_names_the_month_and_writes_nothing(monkeypatch):
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_monthly_client()], invoices=[_bill(1, "draft", 1)], record_months=[_month_row(1, 2000.0)],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    p = operator.Pass(db, send=False, dry=True)
    p._month_gate(dict(db.rows("clients")[0]), cli, billing)
    assert calls == [] and db.rows("invoices")[0]["gate_decision"] is None
    assert any("would void it, the month is free" in n for n in p.notes)


def test_without_a_stripe_key_a_short_month_is_a_warning_never_a_silent_bill(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_monthly_client()], invoices=[_bill(1, "open", 1)], record_months=[_month_row(1, 2000.0)],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    p = operator.Pass(db, send=False, dry=False)
    p._month_gate(dict(db.rows("clients")[0]), cli, billing)
    assert calls == [] and any("cannot be voided: STRIPE_SECRET_KEY missing" in w for w in p.warnings)


def test_billing_starts_in_arrears_when_the_free_months_end(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    sent = {}
    def fake(path, data=None, idempotency_key=None, method=None):
        if path.startswith("customers?") or path.startswith("subscriptions?"):
            return {"data": []}
        if path == "customers":
            return {"id": "cus_9"}
        sent[path] = data
        return {"id": "sub_9", "customer": "cus_9"}
    monkeypatch.setattr(billing, "_stripe", fake)
    letters = _letters(monkeypatch)
    start = date.today() - timedelta(days=40)
    c = _client(id="c9", stripe_subscription_id=None, stripe_customer_id=None, status="pending",
                retainer_started_at=start.isoformat())
    db = FakeDB(clients=[c], invoices=[], record_months=[], directives=[], recovery_claims=[], client_emails=[],
                funnel_events=[])
    operator.Pass(db, send=False, dry=False).billing()
    row = db.rows("clients")[0]
    assert row["stripe_subscription_id"] == "sub_9" and row["billing_decision"] == "started"
    first = monthly.billing_months(c, date.today())[1]
    from datetime import datetime as dt
    assert dt.fromtimestamp(int(sent["subscriptions"]["trial_end"]), timezone.utc).date() == first["end"] + timedelta(days=1)
    assert letters and letters[0][0] == "billing_started"


def test_the_first_cleared_month_credits_the_referrer_and_asks_for_the_consents(monkeypatch):
    _stripe_log(monkeypatch, {"invoices/in_1/send": {"id": "in_1", "status": "open"}})
    _letters(monkeypatch)
    credited = []
    monkeypatch.setattr(operator.Pass, "_credit_referrer", lambda self, c: credited.append(c["id"]))
    db = FakeDB(clients=[_monthly_client()], invoices=[_bill(1, "draft", 1)], record_months=[_month_row(1, 9000.0)],
                consents=[], directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    operator.Pass(db, send=False, dry=False)._month_gate(dict(db.rows("clients")[0]), cli, billing)
    assert credited == ["c1"]
    assert sorted(r["kind"] for r in db.rows("consents")) == ["anonymised_results", "testimonial"]


def test_the_exit_true_up_checks_every_billed_month_and_runs_once(monkeypatch):
    calls = _stripe_log(monkeypatch)
    letters = _letters(monkeypatch)
    paid_short = _bill(2, "paid", 2)
    db = FakeDB(clients=[_monthly_client(status="churned", exit_trued_up_at=None)],
                invoices=[{**_bill(1, "paid", 1), "gate_decision": "covered"}, {**paid_short, "gate_decision": "covered"},
                          _bill(3, "draft", 3)],
                record_months=[_month_row(1, 9000.0), _month_row(2, 7000.0, disputed=1500.0)],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    monkeypatch.setattr(operator, "email_configured", lambda: True)
    operator.Pass(db, send=True, dry=False).billing()
    assert "invoices/in_3/void" in calls and "credit_notes" in calls
    assert db.rows("clients")[0]["exit_trued_up_at"]
    assert [k for k, _ in letters] == ["exit_true_up"]
    # The held draft was for the month in progress: voided, and marked as never sent.
    assert {r["id"]: r.get("gate_note") for r in db.rows("invoices")}["i3"] == billing.EXIT_UNSENT_NOTE
    n = len(calls)
    operator.Pass(db, send=True, dry=False).billing()
    assert len(calls) == n


def test_one_clients_failure_does_not_stop_the_gate_for_the_next(monkeypatch):
    calls = _stripe_log(monkeypatch)
    _letters(monkeypatch)
    db = FakeDB(clients=[_monthly_client(id="c0", company_name="Broken", stripe_subscription_id="sub_0"), _monthly_client()],
                invoices=[_bill(1, "open", 1)], record_months=[_month_row(1, 1000.0)],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    original = operator.Pass._month_gate

    def gate(self, c, *a):
        if c["id"] == "c0":
            raise RuntimeError("boom")
        return original(self, c, *a)

    monkeypatch.setattr(operator.Pass, "_month_gate", gate)
    p = operator.Pass(db, send=False, dry=False)
    p.billing()
    assert any("Broken: the month gate failed: boom" in w for w in p.warnings)
    assert calls == ["invoices/in_1/void"]


def test_a_billed_month_a_dispute_takes_under_the_fee_is_refunded_and_one_still_above_it_stands(monkeypatch):
    calls = _stripe_log(monkeypatch)
    letters = _letters(monkeypatch)
    paid1 = {**_bill(1, "paid", 1), "gate_decision": "covered", "gate_month_index": 1}
    paid2 = {**_bill(2, "paid", 2), "gate_decision": "covered", "gate_month_index": 2}
    db = FakeDB(clients=[_monthly_client()], invoices=[paid1, paid2],
                record_months=[_month_row(1, 7000.0, disputed=1500.0), _month_row(2, 9000.0, disputed=1000.0)],
                directives=[], recovery_claims=[], client_emails=[], funnel_events=[])
    operator.Pass(db, send=False, dry=False)._month_gate(dict(db.rows("clients")[0]), cli, billing)
    by = {r["id"]: r for r in db.rows("invoices")}
    assert by["i1"]["gate_decision"] == "waived" and by["i1"]["refunded_usd"] == 6000.0
    assert by["i2"]["gate_decision"] == "covered"
    assert calls == ["credit_notes"] and [k for k, _ in letters] == ["month_unbilled"]
    # Judged once: the next pass does nothing more.
    operator.Pass(db, send=False, dry=False)._month_gate(dict(db.rows("clients")[0]), cli, billing)
    assert calls == ["credit_notes"]
