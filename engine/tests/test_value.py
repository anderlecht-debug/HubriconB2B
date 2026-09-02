from datetime import date

from hubricon_engine import value


def test_months_elapsed_counts_whole_months():
    assert value.months_elapsed(date(2026, 5, 15), date(2026, 9, 1)) == 3
    assert value.months_elapsed(date(2026, 5, 15), date(2026, 9, 15)) == 4
    assert value.months_elapsed(date(2026, 9, 1), date(2026, 9, 1)) == 0


def test_free_month_then_fees_and_roi_multiple():
    client = {"created_at": "2026-05-01T00:00:00+00:00", "monthly_fee_usd": 6000, "free_months": 1}
    directives = [
        {"status": "done", "measured_impact_usd": 30000, "expected_impact_usd": 25000},
        {"status": "issued", "measured_impact_usd": None, "expected_impact_usd": 4000},
    ]
    claims = [{"status": "paid", "paid_amount": 5000, "expected_value": 4000},
              {"status": "open", "expected_value": 1200}]
    out = value.compute(client, directives, claims, today=date(2026, 9, 1))
    assert out["billed_months"] == 3 and out["fees_paid"] == 18000
    assert out["value_total"] == 35000 and out["recovered"] == 5000
    assert out["roi_multiple"] == round(35000 / 18000, 2) and out["status"] == "at_risk"
    assert out["identified_unbanked"] == 5200


def test_status_thresholds_and_free_month():
    client = {"created_at": "2026-08-20", "monthly_fee_usd": 6000}
    out = value.compute(client, [], [], today=date(2026, 9, 1))
    assert out["status"] == "free_month" and out["roi_multiple"] is None
    strong = value.compute({"created_at": "2026-01-01"}, [{"status": "done", "measured_impact_usd": 300000}], [],
                           today=date(2026, 9, 1))
    assert strong["status"] == "strong" and strong["roi_multiple"] >= 5
