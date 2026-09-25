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


def test_a_covered_invoice_is_marked_and_an_uncovered_one_is_voided_once(monkeypatch):
    calls, letters = [], []
    monkeypatch.setattr(billing, "_stripe", lambda path, data=None, idempotency_key=None: calls.append(path) or {})
    monkeypatch.setattr(cli, "_send_client_email", lambda db, c, kind, ref, subject, blocks, send: letters.append((kind, subject)) or False)
    db = FakeDB(clients=[_client()], invoices=[_inv(1, "paid", "2026-09-01"), _inv(2, "open", "2026-10-01")],
                directives=_measured(1, 7000.0), recovery_claims=[], client_emails=[], funnel_events=[])
    p = operator.Pass(db, send=False, dry=False)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    by = {r["id"]: r for r in db.rows("invoices")}
    assert by["i1"]["gate_decision"] == "covered" and by["i1"]["gate_value"] == 7000.0 and by["i1"]["gate_fees"] == 6000.0
    assert by["i2"]["gate_decision"] == "waived" and by["i2"]["gate_note"] == "voided" and by["i2"]["status"] == "void"
    assert calls == ["invoices/in_2/void"]
    assert any("in_2 voided" in h or "voided" in h for h in p.human)
    # The subject is the verdict itself: the Record against the bills.
    assert letters == [("month_waived", "Invoice this month void — $7,000 on the Record against $12,000 billed")]
    # a second pass judges nothing again
    p2 = operator.Pass(db, send=False, dry=False)
    p2._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    assert calls == ["invoices/in_2/void"] and not p2.notes


def test_a_dry_run_names_the_verdict_and_writes_nothing(monkeypatch):
    monkeypatch.setattr(billing, "_stripe", lambda *a, **k: pytest.fail("dry run must not call Stripe"))
    db = FakeDB(clients=[_client()], invoices=[_inv(1, "open", "2026-09-01")], directives=[], recovery_claims=[])
    p = operator.Pass(db, send=False, dry=True)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    assert any("would be WAIVED" in n for n in p.notes)
    assert db.rows("invoices")[0]["gate_decision"] is None


def test_without_a_stripe_key_an_uncovered_invoice_is_a_warning_never_a_silent_bill(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY")
    db = FakeDB(clients=[_client()], invoices=[_inv(1, "open", "2026-09-01")], directives=[], recovery_claims=[])
    p = operator.Pass(db, send=False, dry=False)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    assert any("cannot be waived" in w for w in p.warnings)
    assert db.rows("invoices")[0]["gate_decision"] is None


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


def test_the_day_30_subjects_are_the_verdict_short_and_cleared(monkeypatch):
    """Becker's build item: the subject line IS the arithmetic — the Record
    against the fee, and whether an invoice stands."""
    letters = []
    monkeypatch.setattr(cli, "_send_client_email",
                        lambda db, c, kind, ref, subject, blocks, send: letters.append((kind, subject)) or False)
    monkeypatch.setattr(billing, "_stripe", lambda *a, **k: pytest.fail("no Stripe call expected"))
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")

    # Short: nothing proven, nothing found -> no invoice, and the subject says so.
    db = FakeDB(clients=[_day_31_client()], directives=[], recovery_claims=[], invoices=[],
                client_emails=[], funnel_events=[], consents=[])
    operator.Pass(db, send=False, dry=False).billing()
    assert letters == [("guarantee_short", "Proving Month — $0 on your Profit Record against $6,000: no invoice")]
    assert db.rows("clients")[0]["billing_decision"] == "short"

    # Cleared: $7,000 proven -> billing starts, and the subject says the invoice stands.
    letters.clear()
    monkeypatch.setattr(billing, "start_billing", lambda c, price_id: {"id": "sub_new", "customer": "cus_1"})
    db = FakeDB(clients=[_day_31_client()], directives=_measured(1, 7000.0), recovery_claims=[], invoices=[],
                client_emails=[], funnel_events=[], consents=[], referrals=[])
    operator.Pass(db, send=False, dry=False).billing()
    assert letters[0] == ("guarantee_cleared",
                          "Proving Month cleared — $7,000 on your Profit Record against $6,000: your first invoice stands")
    assert db.rows("clients")[0]["stripe_subscription_id"] == "sub_new"


# -- the Profit Record footer on every other client email --------------------------------

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

    for kind in ("guarantee_cleared", "guarantee_short", "month_waived", "exit_true_up", "late_teardown"):
        assert cli._send_client_email(db, client, kind, f"ref-{kind}", "verdict", [{"p": "The arithmetic."}], True)
        assert "Your Profit Record:" not in sent[-1][1]
    assert cli.RECORD_FOOTER_EXEMPT == {"guarantee_cleared", "guarantee_short", "month_waived", "exit_true_up",
                                        "late_teardown"}

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


def test_a_held_draft_the_record_covers_is_sent_and_one_it_does_not_is_voided_unsent(monkeypatch):
    calls = _stripe_log(monkeypatch, {"invoices/in_2/send": {"id": "in_2", "status": "open", "number": "HUB-0002",
                                                             "hosted_invoice_url": "https://pay/in_2"}})
    letters = []
    monkeypatch.setattr(cli, "_send_client_email", lambda db, c, kind, ref, subject, blocks, send: letters.append(kind) or False)
    db = FakeDB(clients=[_client()], directives=_measured(1, 13000.0), recovery_claims=[], client_emails=[],
                invoices=[_inv(1, "paid", "2026-09-01"), _inv(2, "draft", "2026-10-01"), _inv(3, "draft", "2026-11-01")])
    p = operator.Pass(db, send=False, dry=False)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    by = {r["id"]: r for r in db.rows("invoices")}
    # $13,000 covers $12,000 billed through the October draft, so it goes out, once;
    assert by["i2"]["gate_decision"] == "covered" and by["i2"]["status"] == "open"
    assert by["i2"]["hosted_invoice_url"] == "https://pay/in_2" and by["i2"]["number"] == "HUB-0002"
    # it does not cover $18,000 through November, so that draft dies before anyone sees it.
    assert by["i3"]["gate_decision"] == "waived" and by["i3"]["status"] == "void" and by["i3"]["gate_note"] == "voided"
    assert calls == ["invoices/in_2/finalize", "invoices/in_2/send", "invoices/in_3/finalize", "invoices/in_3/void"]
    assert letters == []                      # nothing was sent for November, so there is nothing to explain
    assert any("voided unsent" in h for h in p.human)


def test_one_voided_draft_is_not_counted_against_the_next_in_the_same_pass(monkeypatch):
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_client()], directives=_measured(1, 9000.0), recovery_claims=[], client_emails=[],
                invoices=[_inv(1, "paid", "2026-09-01"), _inv(2, "draft", "2026-10-01"), _inv(3, "draft", "2026-11-01")])
    # Measured $9,000 + nothing found: October ($12,000 through it) fails. With October void,
    # November's bar is $6,000 + $6,000 = $12,000 — still short — and it is judged on that, not $18,000.
    p = operator.Pass(db, send=False, dry=False)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    by = {r["id"]: r for r in db.rows("invoices")}
    assert by["i2"]["gate_fees"] == 12000 and by["i3"]["gate_fees"] == 12000
    assert calls.count("invoices/in_2/void") == 1 and calls.count("invoices/in_3/void") == 1


def test_a_paid_month_the_record_no_longer_covers_is_refunded_and_leaves_the_bills(monkeypatch):
    calls = _stripe_log(monkeypatch)
    letters = []
    monkeypatch.setattr(cli, "_send_client_email", lambda db, c, kind, ref, subject, blocks, send: letters.append(subject) or False)
    db = FakeDB(clients=[_client()], directives=_measured(1, 5000.0), recovery_claims=[], client_emails=[],
                invoices=[_inv(1, "paid", "2026-09-01")])
    p = operator.Pass(db, send=False, dry=False)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    row = db.rows("invoices")[0]
    assert calls == ["credit_notes"] and row["gate_note"] == "refunded" and row["refunded_usd"] == 6000
    assert letters == ["Invoice this month refunded — $5,000 on the Record against $6,000 billed"]
    ledger = value.compute(db.rows("clients")[0], db.rows("directives"), [], db.rows("invoices"))
    assert ledger["fees_billed"] == 0 and ledger["fees_paid"] == 0


def test_a_client_whose_ach_payment_failed_is_still_gated(monkeypatch):
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_client(status="past_due")], directives=[], recovery_claims=[], client_emails=[],
                invoices=[_inv(1, "open", "2026-09-01")], funnel_events=[])
    operator.Pass(db, send=False, dry=False).billing()
    assert calls == ["invoices/in_1/void"] and db.rows("invoices")[0]["status"] == "void"


def test_the_exit_true_up_voids_the_unpaid_refunds_the_rest_and_runs_once(monkeypatch):
    calls = _stripe_log(monkeypatch)
    letters = []
    monkeypatch.setattr(cli, "_send_client_email", lambda db, c, kind, ref, subject, blocks, send: letters.append((kind, subject)) or False)
    db = FakeDB(clients=[_client(status="churned", exit_trued_up_at=None)], recovery_claims=[], client_emails=[],
                directives=_measured(1, 9500.0), funnel_events=[],
                invoices=[{**_inv(1, "paid", "2026-09-01"), "gate_decision": "covered"},
                          {**_inv(2, "paid", "2026-10-01"), "gate_decision": "covered"},
                          {**_inv(3, "open", "2026-11-01"), "gate_decision": "covered"},
                          _inv(4, "draft", "2026-12-01")])
    operator.Pass(db, send=False, dry=False).billing()
    by = {r["id"]: r for r in db.rows("invoices")}
    # Billed $18,000 against a $9,500 Record: the unsent December draft and the unpaid
    # November invoice are voided, and the $2,500 left is refunded on October.
    assert by["i4"]["status"] == "void" and by["i3"]["status"] == "void"
    assert by["i2"]["refunded_usd"] == 2500 and not by["i1"].get("refunded_usd")
    assert calls == ["invoices/in_4/finalize", "invoices/in_4/void", "invoices/in_3/void", "credit_notes"]
    client = db.rows("clients")[0]
    assert client["exit_trued_up_at"] and client["exit_refund_usd"] == 2500
    assert letters == [("exit_true_up", "Trued up: $6,000 voided, $2,500.00 refunded to your bank")]
    operator.Pass(db, send=False, dry=False).billing()
    assert len(calls) == 4                    # once per client, for all time


def test_a_late_teardown_adds_a_free_month_once_and_never_to_a_client_already_billing(monkeypatch):
    letters = []
    monkeypatch.setattr(cli, "_send_client_email", lambda db, c, kind, ref, subject, blocks, send: letters.append(kind) or False)
    landed = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    on_time = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    db = FakeDB(clients=[
        _client(id="late", status="pending", stripe_subscription_id=None, retainer_started_at=None,
                exports_landed_at=landed, first_issue_at=None),
        _client(id="fast", status="pending", stripe_subscription_id=None, retainer_started_at=None,
                exports_landed_at=landed, first_issue_at=on_time),
        _client(id="paying", status="active", exports_landed_at=landed, first_issue_at=None),
        _client(id="recov", status="pending", plan="recovery", stripe_subscription_id=None,
                exports_landed_at=landed, first_issue_at=None),
    ], directives=[], recovery_claims=[], invoices=[], client_emails=[], funnel_events=[])
    for _ in range(2):
        operator.Pass(db, send=False, dry=False).billing()
    by = {r["id"]: r for r in db.rows("clients")}
    assert by["late"]["free_months"] == 2 and by["late"]["late_teardown_month_at"]
    assert by["fast"]["free_months"] == 1 and not by["fast"].get("late_teardown_month_at")   # 20h: on time
    assert by["paying"]["free_months"] == 1 and by["recov"]["free_months"] == 1
    assert letters == ["late_teardown"]
    # The extra month is honoured by the day-30 clock: day 45 of a two-month Proving Month is not due.
    assert billing.due_for_decision({**by["late"], "retainer_started_at": "2026-08-01"}, date(2026, 9, 15))[0] is False


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


def test_one_clients_failure_does_not_stop_the_gate_for_the_next(monkeypatch):
    calls = _stripe_log(monkeypatch)
    db = FakeDB(clients=[_client(id="c0", company_name="Broken", stripe_subscription_id="sub_0"), _client()],
                invoices=[_inv(1, "open", "2026-09-01")], directives=[], recovery_claims=[], client_emails=[])
    original = operator.Pass._rolling_gate

    def gate(self, c, *a):
        if c["id"] == "c0":
            raise RuntimeError("boom")
        return original(self, c, *a)

    monkeypatch.setattr(operator.Pass, "_rolling_gate", gate)
    p = operator.Pass(db, send=False, dry=False)
    p.billing()
    assert any("Broken: the rolling gate failed: boom" in w for w in p.warnings)
    assert calls == ["invoices/in_1/void"]


def test_the_promise_check_names_the_missing_migration_and_the_guarantees_it_blocks(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_x")
    db = FakeDB(clients=[], data_requests=[], invoices=[])
    rows = {r[0]: r for r in cli.promise_rows(db)}
    assert rows["A late Teardown makes the first paid month free"][2] is True
    assert "The billing pass can run" not in rows
    for name in ("No bill reaches you before the Record covers it", "Trued up the day you leave",
                 "A paid month the Record stops covering is refunded, not credited"):
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
    assert rows["A late Teardown makes the first paid month free"][2] is False
