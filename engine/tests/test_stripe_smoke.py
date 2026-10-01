"""The smoke harness, run end to end against a stateful fake Stripe. The real
run needs a test-mode key; this proves the harness itself walks every step,
cleans up, and fails loudly when Stripe answers wrong."""

import itertools

from hubricon_engine import billing, stripe_smoke


class FakeStripe:
    def __init__(self, credit_note_refunds=True):
        self.invoices, self.subs, self.calls = {}, {}, []
        self.ids = itertools.count(1)
        self.credit_note_refunds = credit_note_refunds

    def _new_invoice(self, **kw):
        inv = {"id": f"in_{next(self.ids)}", "status": "draft", "amount_due": 0, "amount_paid": 0, "total": 0,
               "auto_advance": True, "metadata": {}, **kw}
        self.invoices[inv["id"]] = inv
        return inv

    def __call__(self, path, data=None, idempotency_key=None, method=None):
        self.calls.append((method or ("POST" if data is not None else "GET"), path))
        data = data or {}
        if path.startswith("subscriptions?"):
            return {"data": list(self.subs.values())}
        if path.startswith("invoices?"):
            return {"data": [dict(i) for i in self.invoices.values()]}
        if path.startswith("customers?"):
            return {"data": []}
        if path == "customers":
            return {"id": "cus_t"}
        if path == "prices":
            return {"id": "price_t", "product": "prod_t"}
        if path == "subscriptions":
            first = self._new_invoice(amount_due=600000, total=600000)
            sub = {"id": "sub_t", "status": "active", "latest_invoice": first["id"],
                   "metadata": {"hubricon_client_id": data["metadata[hubricon_client_id]"]}}
            self.subs[sub["id"]] = sub
            return sub
        if path == "subscriptions/sub_t" and method == "DELETE":
            self.subs["sub_t"]["status"] = "canceled"
            return self.subs["sub_t"]
        if path == "invoices":
            return self._new_invoice(metadata={k[9:-1]: v for k, v in data.items() if k.startswith("metadata[")})
        if path == "invoiceitems":
            inv = self.invoices[data["invoice"]]
            inv["amount_due"] = inv["total"] = inv["amount_due"] + data["amount"]
            return {"id": "ii_t"}
        if path.startswith("invoices/"):
            parts = path.split("/")
            inv = self.invoices[parts[1]]
            action = parts[2] if len(parts) > 2 else None
            if action == "finalize":
                inv.update(status="open", auto_advance=data.get("auto_advance") != "false")
            elif action == "send":
                inv["hosted_invoice_url"] = f"https://pay/{inv['id']}"
            elif action == "void":
                inv["status"] = "void"
            elif action == "pay":
                inv.update(status="paid", amount_paid=inv["amount_due"])
            elif data.get("auto_advance") == "false":
                inv["auto_advance"] = False
            return dict(inv)
        if path == "payment_methods/pm_card_visa/attach":
            return {"id": "pm_t"}
        if path == "credit_notes":
            return {"amount": data["amount"], "refunds": [{"amount": data.get("refund_amount")}]}
        if path.startswith("credit_notes?"):
            return {"data": [{"refunds": [{}] if self.credit_note_refunds else []}]}
        return {}


def test_the_smoke_run_walks_every_step_and_cleans_up(monkeypatch, capsys):
    fake = FakeStripe()
    monkeypatch.setattr(billing, "_stripe", fake)
    assert stripe_smoke.run("sk_test_x") == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out and "Every Stripe call the billing path makes worked." in out
    assert ("DELETE", "customers/cus_t") in fake.calls and ("DELETE", "subscriptions/sub_t") in fake.calls
    assert ("POST", "invoices/in_1/send") in fake.calls          # the held first invoice was released
    assert fake.calls.count(("POST", "subscriptions")) == 1        # asked twice, created once


def test_a_wrong_answer_from_stripe_is_a_named_failure(monkeypatch, capsys):
    monkeypatch.setattr(billing, "_stripe", FakeStripe(credit_note_refunds=False))
    assert stripe_smoke.run("rk_test_x") == 1
    out = capsys.readouterr().out
    assert "FAIL  waive_invoice on a paid invoice" in out and "the credit note carries no refund" in out


def test_a_live_key_is_refused_before_any_call(monkeypatch):
    monkeypatch.setattr(billing, "_stripe", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called Stripe")))
    assert stripe_smoke.run("sk_live_x") == 2 and stripe_smoke.run("") == 2
