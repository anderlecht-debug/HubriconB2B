"""The guarantee, month by month.

HUBRICON_SPEC.md: each month is measured once, on its own; above the fee it is
billed, at or below it the month is free, with nothing credited or carried. The
point of these tests is that the promise is structural: the code that judges a
month is the only code that lets its invoice out.
"""
from datetime import date

from hubricon_engine import billing

TODAY = date(2026, 9, 4)


def test_the_terms_are_the_ones_the_site_publishes():
    assert billing.NET_DAYS == 7        # terms.html §4: ACH, net seven days


# -- the rolling gate --------------------------------------------------------------------

INV1 = {"id": "i1", "stripe_invoice_id": "in_1", "status": "paid", "amount_due": 6000, "amount_paid": 6000,
        "period_start": "2026-09-01", "period_end": "2026-10-01", "issued_at": "2026-09-01T00:00:00Z",
        "stripe_customer_id": "cus_1", "currency": "usd"}
INV2 = {"id": "i2", "stripe_invoice_id": "in_2", "status": "open", "amount_due": 6000, "amount_paid": 0,
        "period_start": "2026-10-01", "period_end": "2026-11-01", "issued_at": "2026-10-01T00:00:00Z",
        "stripe_customer_id": "cus_1", "currency": "usd"}
VOID = {"id": "i0", "stripe_invoice_id": "in_0", "status": "void", "amount_due": 6000,
        "period_start": "2026-08-01", "period_end": "2026-09-01", "issued_at": "2026-08-01T00:00:00Z"}
CLIENT = {"id": "c1", "retainer_started_at": "2026-08-02T00:00:00Z", "monthly_fee_usd": 6000, "stripe_customer_id": "cus_1"}


def test_only_undecided_invoices_inside_the_retainer_are_judged_oldest_first():
    judged = {**INV1, "gate_decision": "covered"}
    early = {**VOID, "status": "open", "id": "ix", "stripe_invoice_id": "in_x", "period_start": "2026-07-01"}
    out = billing.unjudged_invoices([INV2, judged, early, VOID], CLIENT)
    assert [i["id"] for i in out] == ["i2"]          # judged, void and pre-retainer all excluded
    out = billing.unjudged_invoices([INV2, INV1], CLIENT)
    assert [i["id"] for i in out] == ["i1", "i2"]


def test_a_held_draft_is_voided_unsent_an_open_one_voided_and_a_paid_one_refunded_not_credited():
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data, idempotency_key))
        return {}

    # A held draft is finalized WITHOUT Stripe's own send, then voided: the client never receives it.
    draft = {**INV2, "status": "draft", "stripe_invoice_id": "in_d"}
    assert billing.waive_invoice(draft, CLIENT, stripe=stripe) == ("voided", 0.0)
    assert [c[0] for c in calls] == ["invoices/in_d/finalize", "invoices/in_d/void"]
    assert calls[0][1] == {"auto_advance": "false"}
    assert billing.waive_invoice(INV2, CLIENT, stripe=stripe) == ("voided", 0.0)
    assert calls[-1][0] == "invoices/in_2/void"
    # Paid: back to the bank through a credit note on the invoice. Never a
    # customer-balance credit, which is worth nothing to a client who leaves.
    assert billing.waive_invoice(INV1, CLIENT, stripe=stripe) == ("refunded", 6000.0)
    path, data, key = calls[-1]
    assert path == "credit_notes" and data["invoice"] == "in_1" and key == "refund-gate-in_1-600000"
    assert data["amount"] == 600000 and data["refund_amount"] == 600000 and "credit_amount" not in data
    assert not any("balance_transactions" in c[0] for c in calls)


def test_a_month_paid_partly_from_a_referral_credit_refunds_the_cash_and_returns_the_credit():
    calls = []
    part = {**INV1, "stripe_invoice_id": "in_p", "amount_due": 5000, "amount_paid": 5000, "raw": {"total": 600000}}
    how, cash = billing.waive_invoice(part, CLIENT, stripe=lambda path, data=None, idempotency_key=None:
                                      calls.append((path, data)) or {})
    assert (how, cash) == ("refunded", 5000.0)
    assert calls[-1][1]["refund_amount"] == 500000 and calls[-1][1]["credit_amount"] == 100000
    assert calls[-1][1]["amount"] == 600000


def test_a_covered_draft_is_finalized_without_the_auto_send_then_sent_once():
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data))
        return {"id": "in_d", "status": "open", "hosted_invoice_url": "https://pay/in_d"}

    sent = billing.release_invoice({**INV2, "status": "draft", "stripe_invoice_id": "in_d"}, stripe=stripe)
    assert calls == [("invoices/in_d/finalize", {"auto_advance": "false"}), ("invoices/in_d/send", {})]
    assert sent["hosted_invoice_url"] == "https://pay/in_d"


def test_a_refund_is_a_credit_note_with_a_key_made_of_what_it_returns():
    calls = []
    billing.refund_invoice(INV1, 2500.0, "exit", stripe=lambda path, data=None, idempotency_key=None:
                           calls.append((path, data, idempotency_key)) or {})
    path, data, key = calls[0]
    assert path == "credit_notes" and data["amount"] == 250000 and data["refund_amount"] == 250000
    assert data["metadata[hubricon_reason]"] == "exit" and key == "refund-exit-in_1-250000"


def test_billing_never_starts_a_second_subscription_for_the_same_client():
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data, idempotency_key))
        if path.startswith("subscriptions?"):
            return {"data": [{"id": "sub_old", "status": "canceled", "metadata": {"hubricon_client_id": "c1"}},
                             {"id": "sub_live", "status": "active", "metadata": {"hubricon_client_id": "c1"}}]}
        return {"id": "sub_new"}

    client = {**CLIENT, "contact_email": "a@b.com"}
    assert billing.start_billing(client, "price_1", stripe=stripe)["id"] == "sub_live"
    assert not any(c[0] == "subscriptions" for c in calls)
    calls.clear()
    fresh = lambda path, data=None, idempotency_key=None: calls.append((path, data, idempotency_key)) or (
        {"data": []} if path.startswith("subscriptions?") else {"id": "sub_new"})
    assert billing.start_billing(client, "price_1", stripe=fresh)["id"] == "sub_new"
    path, data, key = calls[-1]
    assert path == "subscriptions" and key == "subscribe-c1-2026-08-02"
    assert data["collection_method"] == "send_invoice" and data["payment_settings[payment_method_types][0]"] == "us_bank_account"


def test_cancelling_ends_the_subscription_at_once_with_no_final_invoice():
    calls = []
    billing.cancel_subscription("sub_1", stripe=lambda path, data=None, idempotency_key=None, method=None:
                                calls.append((path, data, method)) or {})
    assert calls == [("subscriptions/sub_1", {"invoice_now": "false", "prorate": "false"}, "DELETE")]


def test_every_call_is_made_at_the_webhooks_api_version():
    """The engine pins the version the webhook's Node SDK pins, so both read one
    shape. Checked against the installed SDK when node_modules is present."""
    import pathlib
    import re
    sdk = pathlib.Path(__file__).parents[2] / "node_modules/stripe/cjs/apiVersion.js"
    if sdk.exists():
        assert billing.STRIPE_VERSION == re.search(r"ApiVersion = '([^']+)'", sdk.read_text()).group(1)


def _claim(i, paid_on, amount, ours=True, status="paid", invoiced=None):
    return {"id": f"k{i}", "status": status, "paid_amount": amount, "paid_at": f"{paid_on}T12:00:00Z",
            "filed_at": "2026-08-01T00:00:00Z" if ours else None, "recovery_invoice_id": invoiced,
            "claim_type": "lost"}


def test_recovery_due_counts_only_our_paid_claims_from_finished_months_not_yet_invoiced():
    today = date(2026, 10, 8)
    claims = [
        _claim(1, "2026-09-03", 1200.0),
        _claim(2, "2026-09-20", 800.0),
        _claim(3, "2026-09-25", 500.0, ours=False),          # Amazon's own initiative
        _claim(4, "2026-10-02", 900.0),                       # this month: not finished
        _claim(5, "2026-08-14", 400.0, invoiced="ri-0"),      # already billed
        _claim(6, "2026-09-10", 300.0, status="filed"),       # not paid yet
    ]
    due = billing.recovery_due(claims, today, share=0.25, min_usd=50)
    assert due["recovered"] == 2000.0 and due["amount"] == 500.0 and due["n_claims"] == 2
    assert due["period_start"] == date(2026, 9, 1) and due["period_end"] == date(2026, 9, 30)
    assert [c["id"] for c in due["claims"]] == ["k1", "k2"] and "deferred" not in due
    assert billing.recovery_due([_claim(4, "2026-10-02", 900.0)], today) is None


def test_a_share_under_the_minimum_rolls_forward_instead_of_becoming_a_nine_dollar_invoice():
    due = billing.recovery_due([_claim(1, "2026-09-03", 36.0)], date(2026, 10, 8), share=0.25, min_usd=50)
    assert due["deferred"] and "$9.00" in due["deferred"] and due["amount"] == 9.0


def test_a_recovery_invoice_is_one_item_one_invoice_finalized_and_sent_with_no_subscription():
    calls, keys = [], []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data))
        keys.append(idempotency_key)
        if path.startswith("customers?"):
            return {"data": []}
        if path == "customers":
            return {"id": "cus_new"}
        if path == "invoices":
            return {"id": "in_r1"}
        if path.endswith("/finalize"):
            return {"id": "in_r1", "status": "open", "hosted_invoice_url": "https://pay/in_r1"}
        if path.endswith("/send"):
            return {"id": "in_r1", "status": "open", "hosted_invoice_url": "https://pay/in_r1"}
        return {}

    due = billing.recovery_due([_claim(1, "2026-09-03", 2000.0)], date(2026, 10, 8), share=0.25)
    inv = billing.invoice_recovery_share({"id": "c1", "contact_email": "a@b.com", "company_name": "Alpha"}, due, stripe=stripe)
    paths = [p for p, _ in calls]
    # The invoice first and the item attached to it by id, so a failure between
    # the two can never leave a pending item to ride along on the next invoice.
    assert paths == ["customers?email=a%40b.com&limit=1", "customers", "invoices?customer=cus_new&limit=100",
                     "invoices", "invoiceitems", "invoices/in_r1/finalize", "invoices/in_r1/send"]
    invoice = dict(calls[3][1]); item = dict(calls[4][1])
    assert item["amount"] == 50000 and "25% of $2,000.00" in item["description"] and item["invoice"] == "in_r1"
    assert invoice["pending_invoice_items_behavior"] == "exclude" and invoice["auto_advance"] == "false"
    assert invoice["collection_method"] == "send_invoice" and invoice["days_until_due"] == 7
    assert invoice["metadata[hubricon_plan]"] == "recovery" and "subscriptions" not in paths
    assert inv["customer"] == "cus_new" and inv["hosted_invoice_url"] == "https://pay/in_r1"
    # A retry bills the same claims under the same keys, so Stripe returns the first attempt's objects.
    assert keys[3].startswith("recovery-invoice-") and keys[4].startswith("recovery-item-") and keys[3][17:] == keys[4][14:]
    assert invoice["metadata[hubricon_claims]"] == keys[3][17:]
    text = " ".join(b.get("p", "") for b in billing.recovery_email_blocks(due, inv["hosted_invoice_url"], "https://x"))
    assert "$2,000.00" in text and "$500.00" in text and "no monthly fee on this plan" in text
    assert "retainer" not in text


def test_a_recovery_invoice_a_failed_run_left_behind_is_finished_never_duplicated():
    """Stripe's idempotency keys last a day; the claims key on the invoice
    lasts for ever. A run that died after creating the invoice (item attached,
    not finalized) is finished; one that died after sending it is left alone."""
    due = billing.recovery_due([_claim(1, "2026-09-03", 2000.0)], date(2026, 10, 8), share=0.25)
    client = {"id": "c1", "contact_email": "a@b.com", "stripe_customer_id": "cus_1"}
    import hashlib
    key = hashlib.sha256(",".join(sorted(str(c.get("id")) for c in due["claims"])).encode()).hexdigest()[:24]
    for left_behind, expected in (
        ({"id": "in_old", "status": "draft", "amount_due": 50000, "metadata": {"hubricon_claims": key}},
         ["invoices?customer=cus_1&limit=100", "invoices/in_old/finalize", "invoices/in_old/send"]),
        ({"id": "in_old", "status": "open", "amount_due": 50000, "metadata": {"hubricon_claims": key}},
         ["invoices?customer=cus_1&limit=100"]),
    ):
        calls = []

        def stripe(path, data=None, idempotency_key=None):
            calls.append(path)
            return {"data": [left_behind]} if path.startswith("invoices?") else {"id": "in_old", "status": "open"}

        assert billing.invoice_recovery_share(client, due, stripe=stripe)["id"] == "in_old"
        assert calls == expected


# -- per month ----------------------------------------------------------------------

CLIENT = {"id": "c1", "retainer_started_at": "2026-08-02", "free_months": 1, "monthly_fee_usd": 6000,
          "platform": "amazon"}


def _months(today=date(2026, 12, 20)):
    from hubricon_engine import monthly
    return monthly.billing_months(CLIENT, today)


def _row(k, usd, channel="amazon", disputed=0.0):
    return {"client_id": "c1", "month_index": k, "channel": channel, "attributed_usd": usd, "disputed_usd": disputed}


def test_nothing_starts_until_the_free_months_are_over():
    due, why, first = billing.due_to_start(CLIENT, date(2026, 8, 20))
    assert due is False and first is None and "free" in why
    due, why, first = billing.due_to_start(CLIENT, date(2026, 9, 2))
    assert due is True and first["index"] == 1 and first["end"] == date(2026, 10, 1)
    two_free = {**CLIENT, "free_months": 2}
    assert billing.due_to_start(two_free, date(2026, 9, 20))[0] is False
    assert billing.due_to_start(two_free, date(2026, 10, 2))[2]["index"] == 2


def test_a_client_with_no_agreed_start_date_is_never_billed_and_billing_never_starts_twice():
    due, why, _ = billing.due_to_start({"created_at": "2026-01-01"}, TODAY)
    assert due is False and "no retainer start date" in why
    due, why, _ = billing.due_to_start({**CLIENT, "stripe_subscription_id": "sub_1"}, date(2026, 12, 1))
    assert due is False and why == "already billing"


def test_the_subscription_trials_to_the_day_after_the_first_billed_month(monkeypatch):
    sent = {}
    def fake(path, data=None, idempotency_key=None, method=None):
        if path.startswith("customers?"):
            return {"data": [{"id": "cus_1"}]}
        if path.startswith("subscriptions?"):
            return {"data": []}
        sent.update(data or {})
        return {"id": "sub_1"}
    monkeypatch.setattr(billing, "_stripe", fake)
    first = _months()[1]
    billing.start_billing({**CLIENT, "contact_email": "a@b.co"}, "price_1", first)
    from datetime import datetime, timezone
    assert datetime.fromtimestamp(int(sent["trial_end"]), timezone.utc).date() == date(2026, 10, 2)
    assert sent["collection_method"] == "send_invoice" and sent["metadata[hubricon_first_billed_month]"] == "1"


def test_an_invoice_bills_the_month_that_ended_before_it_began():
    months = _months()
    assert billing.invoice_month({"period_start": "2026-10-02"}, months)["index"] == 1
    assert billing.invoice_month({"period_start": "2026-11-02"}, months)["index"] == 2
    assert billing.invoice_month({"period_start": "2026-08-10"}, months) is None


def test_a_month_clears_only_above_the_fee_on_its_own_number_after_disputes():
    m = _months()[1]
    assert billing.month_verdict([_row(1, 6000.01)], m, CLIENT)["clears"] is True
    assert billing.month_verdict([_row(1, 6000.0)], m, CLIENT)["clears"] is False          # a tie is the client's
    assert billing.month_verdict([_row(1, 7000.0, disputed=1200.0)], m, CLIENT)["clears"] is False
    # Other months' numbers say nothing about this one: no surplus carries in.
    assert billing.month_verdict([_row(0, 50000.0), _row(2, 50000.0), _row(1, 100.0)], m, CLIENT)["clears"] is False
    # The Proving Month is free whatever it measures.
    assert billing.month_verdict([_row(0, 50000.0)], _months()[0], CLIENT)["clears"] is False


def test_a_two_platform_month_waits_for_both_channels_then_adds_them():
    both = {**CLIENT, "platform": "both"}
    m = _months()[1]
    v = billing.month_verdict([_row(1, 9000.0, "amazon")], m, both)
    assert v["measured"] is False and v["clears"] is False
    v = billing.month_verdict([_row(1, 4000.0, "amazon"), _row(1, 2500.0, "shopify")], m, both)
    assert v["measured"] is True and v["total"] == 6500.0 and v["clears"] is True


def test_the_letters_say_the_month_number_first_and_never_discount_or_credit():
    m = _months()[1]
    cleared = billing.cleared_month_email_blocks(billing.month_verdict([_row(1, 8000.0)], m, CLIENT), "https://x/portal")
    assert "$8,000" in cleared[0]["p"] and "clears the $6,000 fee by $2,000" in cleared[0]["p"]
    v = billing.month_verdict([_row(1, 2500.0)], m, CLIENT)
    for how in ("voided", "refunded"):
        text = " ".join(b.get("p", "") for b in billing.unbilled_email_blocks(v, how, "https://x/portal"))
        assert "the month is free" in text and "nothing carried" in text
        assert "discount" not in text.lower() and "credited" not in text.lower()
        assert ("refunded in full" in text) is (how == "refunded")


def test_at_the_exit_months_that_do_not_clear_come_back_and_months_that_did_stand():
    months = _months()
    invoices = [_inv("cleared", "paid", "2026-10-02"), _inv("short", "paid", "2026-11-02"),
                _inv("open", "open", "2026-12-02")]
    for i in invoices:
        i["amount_paid"] = 6000 if i["status"] == "paid" else 0
    rows = [_row(1, 9000.0), _row(2, 7000.0, disputed=2000.0)]           # month 3 was never measured
    t = billing.exit_true_up(rows, months, invoices, CLIENT)
    assert [i["stripe_invoice_id"] for i in t["voids"]] == ["in_open"]
    assert [(i["stripe_invoice_id"], a) for i, a in t["refunds"]] == [("in_short", 6000.0)]
    assert t["voided"] == 6000.0 and t["refunded"] == 6000.0 and t["gap"] == 12000.0
    letter = " ".join(b.get("p", "") + " ".join(b.get("ol", [])) for b in billing.exit_email_blocks(t, "https://x"))
    assert "did not clear" in letter and "cleared" in letter


def _inv(i, status, start, amount=6000):
    return {"id": f"i{i}", "client_id": "c1", "stripe_invoice_id": f"in_{i}", "status": status,
            "amount_due": amount, "amount_paid": amount if status == "paid" else 0,
            "period_start": start, "issued_at": f"{start}T00:00:00Z", "gate_decision": None}
