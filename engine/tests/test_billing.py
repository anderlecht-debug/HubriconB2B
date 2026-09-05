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
