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
    text = " ".join(b.get("p", "") for b in billing.short_email_blocks(v, "https://x/portal"))
    assert "there is no invoice" in text
    assert "isn't a discount or a credit" in text
    assert "nothing was raised at all" in text


def test_the_cleared_email_shows_the_arithmetic_before_the_invoice():
    v = billing.verdict({"value_total": 20000, "identified_unbanked": 4000}, {"monthly_fee_usd": 6000})
    blocks = billing.cleared_email_blocks(v, "https://x/portal")
    listed = next(b["ol"] for b in blocks if "ol" in b)
    assert any("$20,000" in x for x in listed) and any("$4,000" in x for x in listed)
    assert any("$6,000" in x for x in listed)
    text = " ".join(b.get("p", "") for b in blocks)
    assert "4.0× the fee" in text and "net seven days" in text


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


def test_the_rolling_bar_is_level_with_the_bills_not_above_them():
    ledger = {"value_total": 9000, "identified_unbanked": 3000}
    v = billing.rolling_verdict(ledger, [INV1, INV2], INV2, CLIENT)
    assert v["fees_billed"] == 12000 and v["total"] == 12000 and v["covered"] is True   # level is covered
    short = billing.rolling_verdict({"value_total": 9000, "identified_unbanked": 2999}, [INV1, INV2], INV2, CLIENT)
    assert short["covered"] is False


def test_an_open_invoice_is_voided_and_a_paid_one_is_credited_with_an_idempotency_key():
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data, idempotency_key))
        return {}

    assert billing.waive_invoice(INV2, CLIENT, stripe=stripe) == "voided"
    assert calls[-1][0] == "invoices/in_2/void"
    assert billing.waive_invoice(INV1, CLIENT, stripe=stripe) == "credited"
    path, data, key = calls[-1]
    assert path == "customers/cus_1/balance_transactions" and data["amount"] == -600000 and key == "gate-in_1"


def test_the_waived_letter_says_void_or_credited_and_never_discount():
    v = billing.rolling_verdict({"value_total": 5000, "identified_unbanked": 0}, [INV1, INV2], INV2, CLIENT)
    text = " ".join(b.get("p", "") for b in billing.waived_email_blocks(v, "voided", "https://x/portal"))
    assert "the invoice is void" in text and "never run ahead of your ledger" in text and "discount" not in text
    text = " ".join(b.get("p", "") for b in billing.waived_email_blocks(v, "credited", "https://x/portal"))
    assert "credited to your next one" in text


def test_the_short_letter_names_the_smaller_door_only_when_asked():
    v = billing.verdict({"value_total": 900, "identified_unbanked": 100}, {"monthly_fee_usd": 6000})
    plain = " ".join(b.get("p", "") for b in billing.short_email_blocks(v, "https://x/portal"))
    assert "RECOVERY" not in plain
    door = " ".join(b.get("p", "") for b in billing.short_email_blocks(v, "https://x/portal", recovery_door=True, share=0.2))
    assert "Reply RECOVERY" in door and "20% of what actually lands" in door and "nothing until it lands" in door


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
    calls = []

    def stripe(path, data=None, idempotency_key=None):
        calls.append((path, data))
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
    assert paths == ["customers?email=a%40b.com&limit=1", "customers", "invoiceitems", "invoices",
                     "invoices/in_r1/finalize", "invoices/in_r1/send"]
    item = dict(calls[2][1]); invoice = dict(calls[3][1])
    assert item["amount"] == 50000 and "25% of $2,000.00" in item["description"]
    assert invoice["collection_method"] == "send_invoice" and invoice["days_until_due"] == 7
    assert invoice["metadata[hubricon_plan]"] == "recovery" and "subscriptions" not in paths
    assert inv["customer"] == "cus_new" and inv["hosted_invoice_url"] == "https://pay/in_r1"
    text = " ".join(b.get("p", "") for b in billing.recovery_email_blocks(due, inv["hosted_invoice_url"], "https://x"))
    assert "$2,000.00" in text and "$500.00" in text and "no retainer on this plan" in text
