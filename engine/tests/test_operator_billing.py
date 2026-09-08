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
    calls = []
    monkeypatch.setattr(billing, "_stripe", lambda path, data=None, idempotency_key=None: calls.append(path) or {})
    db = FakeDB(clients=[_client()], invoices=[_inv(1, "paid", "2026-09-01"), _inv(2, "open", "2026-10-01")],
                directives=_measured(1, 7000.0), recovery_claims=[], client_emails=[], funnel_events=[])
    p = operator.Pass(db, send=False, dry=False)
    p._rolling_gate(dict(db.rows("clients")[0]), cli, billing, value)
    by = {r["id"]: r for r in db.rows("invoices")}
    assert by["i1"]["gate_decision"] == "covered" and by["i1"]["gate_value"] == 7000.0 and by["i1"]["gate_fees"] == 6000.0
    assert by["i2"]["gate_decision"] == "waived" and by["i2"]["gate_note"] == "voided" and by["i2"]["status"] == "void"
    assert calls == ["invoices/in_2/void"]
    assert any("in_2 voided" in h or "voided" in h for h in p.human)
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
