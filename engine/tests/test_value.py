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
    # The printed rule is "what we proved, plus what we found and filed": the
    # $4,000 move is only issued (not made) and the $1,200 claim is detected,
    # not filed, so neither is found money yet.
    assert out["identified_unbanked"] == 0


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


def test_found_is_moves_made_and_claims_filed_at_expected_dollars_only():
    """index.html: 'what we proved, plus what we found and filed'. Found = a move
    actually made (executed_at set, or status done) at its expected dollars and
    not yet measured, plus a claim actually filed and not yet paid. Issued,
    approved, detected and expired rows are not found money and cannot cover
    an invoice."""
    client = {"retainer_started_at": "2026-05-01", "monthly_fee_usd": 6000}
    directives = [
        {"status": "approved", "executed_at": "2026-08-20T10:00:00Z",
         "measured_impact_usd": None, "expected_impact_usd": 700},          # made, unmeasured: counts
        {"status": "done", "measured_impact_usd": None, "expected_impact_usd": 300},   # done: counts
        {"status": "done", "executed_at": "2026-08-01", "measured_impact_usd": 900,
         "expected_impact_usd": 1000},                                      # measured: proven, not found
        {"status": "issued", "measured_impact_usd": None, "expected_impact_usd": 4000},    # not made
        {"status": "approved", "measured_impact_usd": None, "expected_impact_usd": 2500},  # not made
        {"status": "done", "measured_impact_usd": None, "expected_impact_usd": None},      # no number
    ]
    claims = [
        {"status": "filed", "expected_value": 1200, "filed_at": "2026-08-10",
         "eligible_from": "2026-06-01", "deadline": "2026-12-01"},          # filed: counts
        {"status": "detected", "expected_value": 800,
         "eligible_from": "2026-06-01", "deadline": "2026-12-01"},          # open, unfiled: no
        {"status": "expired", "expected_value": 650, "filed_at": "2026-02-10",
         "eligible_from": "2026-01-01", "deadline": "2026-08-01"},          # expired: no
        {"status": "denied", "expected_value": 400, "filed_at": "2026-07-01"},            # denied: no
    ]
    out = value.compute(client, directives, claims, today=date(2026, 9, 1))
    assert value.IDENTIFIED_CLAIM_STATES == ("filed",)
    assert out["identified_parts"] == {"directives": 1000.0, "claims": 1200.0}
    assert out["identified_unbanked"] == 2200
    assert out["measured"] == 900 and out["value_total"] == 900     # found is shown, never added
    assert "found = moves made and claims filed" in out["basis"]
    # LIVE_CLAIM_STATES is untouched: the portal still shows detected claims in flight.
    assert "open" in value.LIVE_CLAIM_STATES and "filed" in value.LIVE_CLAIM_STATES


def test_a_move_closed_as_unmeasurable_is_not_found_money():
    """The sweep closes a move it could not measure with measured_at set and
    no dollars. That move has been measured and found nothing: it is neither
    proven nor found, and its expected dollars can never cover an invoice."""
    client = {"retainer_started_at": "2026-05-01", "monthly_fee_usd": 6000}
    closed = {"status": "closed", "executed_at": "2026-08-20T10:00:00Z", "measured_at": "2026-09-01T00:00:00Z",
              "measured_impact_usd": None, "expected_impact_usd": 4000}
    out = value.compute(client, [closed], [], today=date(2026, 9, 1))
    assert out["identified_unbanked"] == 0 and out["measured"] == 0 and out["value_total"] == 0
    # A lapsed move never happened; measured_at alone is also enough to retire the promise.
    lapsed = {"status": "lapsed", "executed_at": "2026-08-20T10:00:00Z",
              "measured_impact_usd": None, "expected_impact_usd": 4000}
    dated = {"status": "approved", "executed_at": "2026-08-20T10:00:00Z", "measured_at": "2026-09-01T00:00:00Z",
             "measured_impact_usd": None, "expected_impact_usd": 4000}
    assert value.compute(client, [lapsed, dated], [], today=date(2026, 9, 1))["identified_unbanked"] == 0
    # ...while the same move, made and simply not yet measured, still counts.
    open_move = {"status": "approved", "executed_at": "2026-08-20T10:00:00Z",
                 "measured_impact_usd": None, "expected_impact_usd": 4000}
    assert value.compute(client, [open_move], [], today=date(2026, 9, 1))["identified_unbanked"] == 4000


def test_record_line_is_the_portal_strip_in_one_sentence():
    line = value.record_line({"value_total": 5415.4, "identified_unbanked": 2400, "fees_billed": 0})
    assert line == ("Your Profit Record: $5,415 proven since day one · $2,400 found and filed, "
                    "not yet banked · $0 billed to date.")
    assert "×" not in line                      # nothing billed: no multiple to state
    assert value.record_line({}) == ("Your Profit Record: $0 proven since day one · $0 found and filed, "
                                     "not yet banked · $0 billed to date.")
    # Once something is billed the fourth number is the strip's multiple, proven over billed.
    billed = value.record_line({"value_total": 13870, "identified_unbanked": 2400, "fees_billed": 6000})
    assert billed.endswith("· 2.3× proven ÷ billed.")
    assert billed == ("Your Profit Record: $13,870 proven since day one · $2,400 found and filed, "
                      "not yet banked · $6,000 billed to date · 2.3× proven ÷ billed.")
