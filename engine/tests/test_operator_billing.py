"""The hourly billing pass, on the fake database: the rolling gate decides each
invoice once, and the recovery-only plan bills only what landed."""

from datetime import date, timedelta

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

def test_every_client_email_closes_on_the_record_line_except_the_three_billing_letters(monkeypatch):
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

    for kind in ("guarantee_cleared", "guarantee_short", "month_waived"):
        assert cli._send_client_email(db, client, kind, f"ref-{kind}", "verdict", [{"p": "The arithmetic."}], True)
        assert "Your Profit Record:" not in sent[-1][1]
    assert cli.RECORD_FOOTER_EXEMPT == {"guarantee_cleared", "guarantee_short", "month_waived"}

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
