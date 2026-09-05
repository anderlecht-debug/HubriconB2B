from datetime import date

from hubricon_engine import value


def test_months_elapsed_counts_whole_months():
    assert value.months_elapsed(date(2026, 5, 15), date(2026, 9, 1)) == 3
    assert value.months_elapsed(date(2026, 5, 15), date(2026, 9, 15)) == 4
    assert value.months_elapsed(date(2026, 9, 1), date(2026, 9, 1)) == 0


def test_free_month_then_fees_and_roi_multiple():
    # The retainer date is what starts the clock — terms.html §3, "the day you
    # say yes after the Teardown" — not the day the row was provisioned.
    client = {"retainer_started_at": "2026-05-01T00:00:00+00:00", "retainer_source": "client_yes",
              "monthly_fee_usd": 6000, "free_months": 1}
    directives = [
        {"status": "done", "measured_impact_usd": 30000, "expected_impact_usd": 25000,
         "attribution": "isolated"},
        {"status": "issued", "measured_impact_usd": None, "expected_impact_usd": 4000},
    ]
    claims = [
        {"status": "paid", "paid_amount": 5000, "expected_value": 4000, "filed_at": "2026-07-01"},
        # A real 'detected' claim whose window is still open. The old code
        # counted a status of "open", which the CHECK constraint never allowed —
        # a branch that could not fire on any row the database can hold.
        {"status": "detected", "expected_value": 1200,
         "eligible_from": "2026-06-01", "deadline": "2026-12-01"},
    ]
    out = value.compute(client, directives, claims, today=date(2026, 9, 1))
    assert out["billed_months"] == 3 and out["fees_paid"] == 18000
    assert out["fees_basis"] == "assumed"
    assert out["value_total"] == 35000 and out["recovered"] == 5000
    assert out["roi_multiple"] == round(35000 / 18000, 2) and out["status"] == "at_risk"
    assert out["identified_unbanked"] == 5200


def test_uninvoiced_client_is_in_their_free_month_not_at_risk():
    """The live harm this replaces: a client whose row was provisioned months
    ago but who was never invoiced was shown '0.0x — at risk' in their own desk,
    because the denominator was assumed from created_at."""
    client = {"created_at": "2026-01-01", "monthly_fee_usd": 6000}
    out = value.compute(client, [], [], today=date(2026, 9, 1))
    assert out["fees_basis"] == "unknown"
    assert out["fees_paid"] == 0 and out["roi_multiple"] is None
    assert out["status"] == "free_month"
    assert out["engagement_start_source"] == "provisioned"


def test_fees_come_from_invoices_when_they_exist():
    client = {"retainer_started_at": "2026-01-01", "monthly_fee_usd": 6000}
    invoices = [
        {"status": "paid", "amount_due": 6000, "amount_paid": 6000},
        {"status": "paid", "amount_due": 6000, "amount_paid": 6000},
        {"status": "open", "amount_due": 6000, "amount_paid": 0},
        {"status": "void", "amount_due": 6000, "amount_paid": 0},
    ]
    out = value.compute(client, [{"status": "done", "measured_impact_usd": 48000}], [],
                        invoices=invoices, today=date(2026, 9, 1))
    # Eight months elapsed, but only two invoices were actually paid.
    assert out["fees_basis"] == "invoiced"
    assert out["fees_paid"] == 12000 and out["fees_billed"] == 18000
    assert out["roi_multiple"] == 4.0 and out["status"] == "holding"


def test_only_claims_we_filed_reach_the_total():
    """Amazon auto-reimburses a lot of warehouse loss unprompted. Banking those
    would credit us with money that would have arrived anyway."""
    client = {"retainer_started_at": "2026-05-01", "monthly_fee_usd": 6000}
    claims = [
        {"status": "paid", "paid_amount": 4000, "filed_at": "2026-06-02"},
        {"status": "paid", "paid_amount": 9000},          # Amazon's own reconciliation
    ]
    out = value.compute(client, [], claims, today=date(2026, 9, 1))
    assert out["recovered"] == 4000 and out["recovered_count"] == 1
    assert out["recovered_unattributed"] == 9000
    assert out["value_total"] == 4000


def test_expired_claim_is_neither_banked_nor_identified():
    client = {"retainer_started_at": "2026-05-01"}
    claims = [{"status": "detected", "expected_value": 2500,
               "eligible_from": "2026-01-01", "deadline": "2026-08-01"}]
    out = value.compute(client, [], claims, today=date(2026, 9, 1))
    assert out["identified_unbanked"] == 0


def test_measured_dollars_are_split_by_attribution_tier():
    client = {"retainer_started_at": "2026-05-01"}
    directives = [
        {"status": "done", "measured_impact_usd": 1000, "attribution": "direct"},
        {"status": "done", "measured_impact_usd": 500, "attribution": "isolated"},
        {"status": "done", "measured_impact_usd": -200, "attribution": "attributable"},
    ]
    out = value.compute(client, directives, [], today=date(2026, 9, 1))
    # A miss stays on the record: portal.html promises exactly that.
    assert out["measured_by_attribution"] == {"direct": 1000.0, "isolated": 500.0, "attributable": -200.0}
    assert out["value_total"] == 1300


def test_status_thresholds():
    strong = value.compute({"retainer_started_at": "2026-01-01"},
                           [{"status": "done", "measured_impact_usd": 300000}], [],
                           today=date(2026, 9, 1))
    assert strong["status"] == "strong" and strong["roi_multiple"] >= 5
    new = value.compute({"retainer_started_at": "2026-08-20", "monthly_fee_usd": 6000}, [], [],
                        today=date(2026, 9, 1))
    assert new["status"] == "free_month" and new["roi_multiple"] is None
