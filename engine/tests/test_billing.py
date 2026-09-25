"""The day-30 guarantee.

terms.html §3: "if we don't find you more than we cost, you walk away owing
nothing." The point of these tests is that the promise is structural — the same
code that checks it is the only code that starts billing, so it cannot be
broken by forgetting.
"""
from datetime import date

from hubricon_engine import billing

TODAY = date(2026, 9, 4)


def test_nothing_is_decided_before_the_free_month_is_up():
    due, why = billing.due_for_decision({"retainer_started_at": "2026-08-20"}, TODAY)
    assert due is False and "day 15 of the free 30" in why


def test_a_client_with_no_agreed_start_date_is_never_billed():
    """The clock used to run from the day the row was provisioned — at booking,
    before the Teardown existed. A missing start date must stall billing, not
    guess at it."""
    due, why = billing.due_for_decision({"created_at": "2026-01-01"}, TODAY)
    assert due is False and "no retainer start date" in why


def test_billing_is_never_started_twice():
    due, why = billing.due_for_decision(
        {"retainer_started_at": "2026-06-01", "stripe_subscription_id": "sub_1"}, TODAY)
    assert due is False and why == "already billing"


def test_the_bar_is_measured_plus_identified_against_the_fee():
    """The measurement engine deliberately under-claims; it must not under-claim
    its way into refusing revenue for work that was really delivered."""
    v = billing.verdict({"value_total": 4000, "identified_unbanked": 3000}, {"monthly_fee_usd": 6000})
    assert v["total"] == 7000 and v["clears"] is True

    short = billing.verdict({"value_total": 1000, "identified_unbanked": 500}, {"monthly_fee_usd": 6000})
    assert short["total"] == 1500 and short["clears"] is False


def test_exactly_the_fee_does_not_clear_it():
    """'More than we cost' means more, not equal."""
    v = billing.verdict({"value_total": 6000, "identified_unbanked": 0}, {"monthly_fee_usd": 6000})
    assert v["clears"] is False


def test_the_short_email_says_no_invoice_exists_not_that_one_was_waived():
    v = billing.verdict({"value_total": 900, "identified_unbanked": 100}, {"monthly_fee_usd": 6000})
    blocks = billing.short_email_blocks(v, "https://x/portal")
    text = " ".join(b.get("p", "") for b in blocks)
    assert "there is no invoice" in text
    assert "isn't a discount or a credit" in text
    assert "nothing was raised at all" in text
    # The three lines use the names in force, and the retired words never appear.
    listed = next(b["ol"] for b in blocks if "ol" in b)
    assert listed == ["Proven on your Profit Record, from your own exports: $900",
                      "Found and filed, not yet banked: $100",
                      "Against Managed Profit: $6,000 a month"]
    whole = text + " " + " ".join(listed)
    assert "Decision Ledger" not in whole and "retainer" not in whole
    # The door back in is the same arithmetic, later: the Record clearing the fee, then an invoice.
    later = ("If the Record clears $6,000 later — a claim Amazon pays, a price step that reads out — "
             "the first invoice comes then, by email, with this same arithmetic on top of it. Not before.")
    assert later in text
    paras = [b["p"] for b in blocks if "p" in b]
    assert paras.index(later) == len(paras) - 1                 # the last word before any smaller door


def test_the_cleared_email_shows_the_arithmetic_before_the_invoice():
    v = billing.verdict({"value_total": 20000, "identified_unbanked": 4000}, {"monthly_fee_usd": 6000})
    blocks = billing.cleared_email_blocks(v, "https://x/portal")
    listed = next(b["ol"] for b in blocks if "ol" in b)
    assert any("$20,000" in x for x in listed) and any("$4,000" in x for x in listed)
    assert any("$6,000" in x for x in listed)
    assert "Found and filed, not yet banked: $4,000" in listed
    text = " ".join(b.get("p", "") for b in blocks)
    assert "4.0× the fee" in text and "net seven days" in text
    # The Proving Month was already Managed Profit; what starts now is the paid months.
    assert "so the paid months start and your first invoice comes by email" in text
    assert "Managed Profit starts" not in text


def test_the_terms_are_the_ones_the_site_publishes():
    assert billing.NET_DAYS == 7        # terms.html §4: ACH, net seven days
    assert billing.FREE_DAYS == 30      # welcome.html: "Day 30 — your first invoice"


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


def test_fees_billed_through_counts_up_to_this_invoice_and_skips_void_ones():
    assert billing.fees_billed_through([VOID, INV1, INV2], INV1) == 6000
    assert billing.fees_billed_through([VOID, INV1, INV2], INV2) == 12000


def test_the_rolling_bar_is_ahead_of_the_bills_and_a_tie_goes_to_the_client():
    """Both gates now read the same. `verdict` has always required the Record to
    EXCEED the fee ("$6,000 or under and there is no invoice"); `rolling_verdict`
    used to settle for level, so the two disagreed on an exact tie and no single
    sentence could describe both. A tie is now uncovered, which is the reading
    that costs us the invoice rather than the client."""
    ledger = {"value_total": 9000, "identified_unbanked": 3001}
    v = billing.rolling_verdict(ledger, [INV1, INV2], INV2, CLIENT)
    assert v["fees_billed"] == 12000 and v["total"] == 12001 and v["covered"] is True
    level = billing.rolling_verdict({"value_total": 9000, "identified_unbanked": 3000},
                                    [INV1, INV2], INV2, CLIENT)
    assert level["total"] == 12000 and level["covered"] is False        # a tie is not covered
    short = billing.rolling_verdict({"value_total": 9000, "identified_unbanked": 2999}, [INV1, INV2], INV2, CLIENT)
    assert short["covered"] is False
    # The day-30 gate reads the same way, so one sentence describes both.
    assert billing.verdict({"value_total": 6000, "identified_unbanked": 0}, CLIENT)["clears"] is False
    assert billing.verdict({"value_total": 6001, "identified_unbanked": 0}, CLIENT)["clears"] is True


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


def test_a_held_draft_counts_toward_its_own_bar_and_a_refund_comes_off_the_bills():
    draft = {**INV2, "status": "draft"}
    assert billing.fees_billed_through([INV1, draft], draft) == 12000         # judged with itself in
    assert billing.fees_billed_through([INV1, {**draft, "id": "o"}], INV1) == 6000
    refunded = {**INV1, "refunded_usd": 6000}
    assert billing.fees_billed_through([refunded, INV2], INV2) == 6000       # a refunded month was not billed
    assert [i["id"] for i in billing.unjudged_invoices([draft, INV1], CLIENT)] == ["i1", "i2"]
    recovery = {**INV2, "id": "r", "raw": {"metadata": {"hubricon_plan": "recovery"}}}
    assert billing.unjudged_invoices([recovery], CLIENT) == []                # priced off money that landed


def test_the_waived_letter_says_void_or_refunded_and_never_discount_or_credit():
    v = billing.rolling_verdict({"value_total": 5000, "identified_unbanked": 0}, [INV1, INV2], INV2, CLIENT)
    blocks = billing.waived_email_blocks(v, "voided", "https://x/portal")
    text = " ".join(b.get("p", "") for b in blocks)
    assert "the invoice is void" in text and "hasn't covered is void" in text and "discount" not in text
    assert "Found and filed, not yet banked: $0" in next(b["ol"] for b in blocks if "ol" in b)
    text = " ".join(b.get("p", "") for b in billing.waived_email_blocks(v, "refunded", "https://x/portal"))
    assert "refunded in full to the bank account it came from" in text and "credited" not in text


# -- the exit true-up ----------------------------------------------------------------------

def test_at_the_exit_an_unpaid_invoice_is_voided_before_any_refund_and_the_rest_is_refunded():
    paid_a = {**INV1, "id": "a", "stripe_invoice_id": "in_a", "period_start": "2026-09-01"}
    paid_b = {**INV1, "id": "b", "stripe_invoice_id": "in_b", "period_start": "2026-10-01"}
    open_c = {**INV2, "id": "c", "stripe_invoice_id": "in_c", "period_start": "2026-11-01"}
    # Billed $18,000; the Record fell to $9,500 after found dollars measured short.
    t = billing.exit_true_up({"value_total": 8000, "identified_unbanked": 1500}, [paid_a, paid_b, open_c])
    assert t["billed"] == 18000 and t["gap"] == 8500
    assert [i["id"] for i in t["voids"]] == ["c"] and t["voided"] == 6000
    assert [(i["id"], a) for i, a in t["refunds"]] == [("b", 2500.0)] and t["refunded"] == 2500
    # Ahead of the bills, or level: nothing changes hands.
    level = billing.exit_true_up({"value_total": 18000, "identified_unbanked": 0}, [paid_a, paid_b, open_c])
    assert level["gap"] == 0 and not level["voids"] and not level["refunds"]
    # Earlier refunds are counted once, never twice.
    again = billing.exit_true_up({"value_total": 0, "identified_unbanked": 0},
                                 [{**paid_a, "refunded_usd": 6000}, {**paid_b, "refunded_usd": 1000}])
    assert again["billed"] == 5000 and [(i["id"], a) for i, a in again["refunds"]] == [("b", 5000.0)]


def test_the_exit_letter_names_the_arithmetic_and_what_came_back():
    t = billing.exit_true_up({"value_total": 8000, "identified_unbanked": 1500},
                             [{**INV1, "id": "a", "stripe_invoice_id": "in_a"},
                              {**INV2, "id": "c", "stripe_invoice_id": "in_c"}])
    text = " ".join(b.get("p", "") for b in billing.exit_email_blocks(t, "https://x"))
    assert "$2,500 more than the Record shows" in text and "is void" in text and "credited" not in text
    ahead = billing.exit_true_up({"value_total": 20000, "identified_unbanked": 0}, [INV1])
    text = " ".join(b.get("p", "") for b in billing.exit_email_blocks(ahead, "https://x"))
    assert "nothing changes hands" in text


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


def test_the_short_letter_names_the_smaller_door_only_when_asked():
    v = billing.verdict({"value_total": 900, "identified_unbanked": 100}, {"monthly_fee_usd": 6000})
    plain = " ".join(b.get("p", "") for b in billing.short_email_blocks(v, "https://x/portal"))
    assert "RECOVERY" not in plain
    door = " ".join(b.get("p", "") for b in billing.short_email_blocks(v, "https://x/portal", recovery_door=True, share=0.2))
    assert "Reply RECOVERY" in door and "20% of what actually lands" in door and "nothing until it lands" in door
    assert door.index("Not before.") < door.index("Reply RECOVERY")    # the later-invoice line precedes the door


# -- the recovery-only plan ---------------------------------------------------------------

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
