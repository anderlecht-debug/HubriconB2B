"""`hubricon stripe-smoke`: every Stripe call the billing path makes, run once
against a TEST-mode account, then cleaned up.

The billing tests run against fakes, which prove the logic and nothing about
Stripe. This runs the real functions — billing.start_billing, release_invoice,
waive_invoice, refund_invoice, invoice_recovery_share, cancel_subscription —
against Stripe itself with a throwaway customer, and says PASS or FAIL for
each. It refuses a live key.

Two stand-ins, both named in the output: the refunded invoice is paid with a
test card, because a test ACH payment needs a bank-verification flow no
script can finish (a credit note refunds either the same way); and the hold
the webhook places is applied here by the same API call, because a local run
receives no webhooks.
"""

from __future__ import annotations

import time
import urllib.parse

from . import billing


def _inv(obj: dict) -> dict:
    """A Stripe invoice in the shape the mirror stores."""
    return {"stripe_invoice_id": obj["id"], "status": obj.get("status"), "number": obj.get("number"),
            "amount_due": (obj.get("amount_due") or 0) / 100, "amount_paid": (obj.get("amount_paid") or 0) / 100,
            "stripe_customer_id": obj.get("customer"), "currency": obj.get("currency"), "raw": obj}


def run(key: str) -> int:
    if not key.startswith(("sk_test_", "rk_test_")):
        print("Refused: stripe-smoke runs only on a TEST-mode key (sk_test_… or rk_test_…). "
              "It creates and deletes customers, invoices and refunds.")
        return 2
    call = billing._stripe
    stamp = int(time.time())
    failures = 0
    made: dict = {}

    def step(name: str, fn):
        nonlocal failures
        try:
            out = fn()
            print(f"  PASS  {name}")
            return out
        except Exception as err:  # every step reports; one failure does not hide the rest
            failures += 1
            print(f"  FAIL  {name}: {str(err)[:300]}")
            return None

    def one_off(amount_cents: int, ach_only: bool = True) -> dict:
        inv = call("invoices", {"customer": made["customer"], "collection_method": "send_invoice",
                                "days_until_due": billing.NET_DAYS, "auto_advance": "false",
                                "pending_invoice_items_behavior": "exclude",
                                **({"payment_settings[payment_method_types][0]": "us_bank_account"} if ach_only else {})})
        call("invoiceitems", {"customer": made["customer"], "invoice": inv["id"], "amount": amount_cents,
                              "currency": "usd", "description": "Hubricon smoke test"})
        return call(f"invoices/{inv['id']}")

    def expect(cond: bool, what: str):
        if not cond:
            raise AssertionError(what)

    client = {"id": f"smoke-{stamp}", "contact_email": f"smoke+{stamp}@example.com",
              "company_name": "Hubricon smoke test", "retainer_started_at": "2026-01-01"}
    print(f"Stripe smoke test at API {billing.STRIPE_VERSION}, test mode.\n")

    made["customer"] = step("a customer, created once and found again by email",
                            lambda: billing.ensure_customer(client))
    if not made["customer"]:
        print("\nCannot continue without a customer.")
        return 1
    client["stripe_customer_id"] = made["customer"]
    price = step("a $6,000/month price (throwaway)", lambda: call("prices", {
        "unit_amount": 600000, "currency": "usd", "recurring[interval]": "month",
        "product_data[name]": f"Hubricon smoke test {stamp}"}))

    if price:
        made["price"], made["product"] = price["id"], price["product"]
        sub = step("start_billing: send_invoice, ACH only, net 7",
                   lambda: billing.start_billing(client, price["id"]))
        if sub:
            made["sub"] = sub["id"]
            step("start_billing again returns the same subscription, never a second",
                 lambda: expect(billing.start_billing(client, price["id"])["id"] == sub["id"], "a second subscription"))
            latest = sub.get("latest_invoice")
            first = step("the subscription's first invoice exists",
                         lambda: call(f"invoices/{latest if isinstance(latest, str) else (latest or {})['id']}"))
            if first and first.get("status") == "draft":
                step("the webhook's hold: auto_advance=false on a draft",
                     lambda: expect(call(f"invoices/{first['id']}", {"auto_advance": "false"})["auto_advance"] is False,
                                    "auto_advance still true"))
                sent = step("release_invoice: finalize without auto-send, then send",
                            lambda: billing.release_invoice(_inv(first)))
                if sent:
                    step("the released invoice is open, with a payment page",
                         lambda: expect(sent.get("status") == "open" and sent.get("hosted_invoice_url"), str(sent.get("status"))))
                    step("void it (cleanup)", lambda: call(f"invoices/{first['id']}/void", {}))
            elif first:
                print(f"  note  Stripe finalized the first invoice at once (status {first.get('status')}); "
                      f"the gate judges it as open. Voiding it (cleanup).")
                step("void the first invoice", lambda: call(f"invoices/{first['id']}/void", {}))

    draft = step("a held one-off draft", lambda: one_off(600000))
    if draft:
        step("waive_invoice on a draft: finalized unsent, then void",
             lambda: expect(billing.waive_invoice(_inv(draft), client) == ("voided", 0.0)
                            and call(f"invoices/{draft['id']}")["status"] == "void", "not void"))

    opened = step("an open invoice", lambda: call(f"invoices/{one_off(600000)['id']}/finalize", {"auto_advance": "false"}))
    if opened:
        step("waive_invoice on an open invoice: void",
             lambda: expect(billing.waive_invoice(_inv(opened), client)[0] == "voided"
                            and call(f"invoices/{opened['id']}")["status"] == "void", "not void"))

    def paid_invoice(cents: int) -> dict:
        pm = call("payment_methods/pm_card_visa/attach", {"customer": made["customer"]})
        inv = call(f"invoices/{one_off(cents, ach_only=False)['id']}/finalize", {"auto_advance": "false"})
        return call(f"invoices/{inv['id']}/pay", {"payment_method": pm["id"]})

    paid = step("a paid invoice ($100, test card standing in for ACH)", lambda: paid_invoice(10000))
    if paid:
        def refunded_in_full():
            how, cash = billing.waive_invoice(_inv(paid), client)
            notes = call(f"credit_notes?{urllib.parse.urlencode({'invoice': paid['id']})}")["data"]
            expect(how == "refunded" and cash == 100.0, f"{how} {cash}")
            expect(bool(notes), "no credit note on the invoice")
            expect(bool(notes[0].get("refunds") or notes[0].get("refund")), "the credit note carries no refund")
        step("waive_invoice on a paid invoice: a credit note that refunds, not a balance credit", refunded_in_full)
    partly = step("another paid invoice ($100)", lambda: paid_invoice(10000))
    if partly:
        step("refund_invoice for part of it (the exit true-up)",
             lambda: expect(billing.refund_invoice(_inv(partly), 25.0, "exit").get("amount") == 2500, "wrong amount"))

    due = {"share": 0.25, "recovered": 400.0, "amount": 100.0, "n_claims": 1,
           "period_start": "2026-08-01", "period_end": "2026-08-31", "claims": [{"id": f"smoke-{stamp}"}]}
    rec = step("invoice_recovery_share: invoice first, item attached, finalized, sent",
               lambda: billing.invoice_recovery_share(client, due))
    if rec:
        step("the recovery invoice bills exactly the share",
             lambda: expect(call(f"invoices/{rec['id']}")["amount_due"] == 10000, "wrong amount"))
        step("a retry returns the same invoice (idempotency key)",
             lambda: expect(billing.invoice_recovery_share(client, due)["id"] == rec["id"], "a second invoice"))
        step("void it (cleanup)", lambda: call(f"invoices/{rec['id']}/void", {}))

    if made.get("sub"):
        step("cancel_subscription: ended at once, no final invoice",
             lambda: expect(billing.cancel_subscription(made["sub"]).get("status") == "canceled", "not canceled"))
    print()
    step("cleanup: delete the test customer", lambda: call(f"customers/{made['customer']}", method="DELETE"))
    if made.get("price"):
        step("cleanup: archive the test price and product", lambda: (
            call(f"prices/{made['price']}", {"active": "false"}), call(f"products/{made['product']}", {"active": "false"})))

    print(f"\n{'Every Stripe call the billing path makes worked.' if not failures else f'{failures} step(s) FAILED.'}")
    return 1 if failures else 0
