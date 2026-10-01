"""The Record month by month (monthly.py): a sealed leak earns in every month it
still holds, nothing in a month it has stopped, and no dollar is counted twice,
across months or across moves."""
from datetime import date

from hubricon_engine import monthly

CLIENT = {"id": "c1", "retainer_started_at": "2026-08-02", "free_months": 1, "monthly_fee_usd": 6000}


def _months(today=date(2026, 12, 20)):
    return {m["index"]: m for m in monthly.billing_months(CLIENT, today)}


def _bleed(**kw):
    d = {"id": "d1", "kind": "ad_bleed_terms", "status": "done", "measured_at": "2026-09-12",
         "measured_impact_usd": 300.0, "executed_at": "2026-08-10", "issued_at": "2026-08-07",
         "expected_impact_usd": 300.0,
         "evidence": {"terms": [{"campaign_name": "C1", "search_term": "waste", "spend": 300.0}],
                      "baseline_spend": 300.0, "baseline_days": 30.0,
                      "campaign_baseline_spend": {"C1": 1000.0}}}
    d.update(kw)
    return d


def _term(term, spend, start, end, sales=0.0):
    return {"campaign_name": "C1", "search_term": term, "spend": spend, "sales_7d": sales,
            "period_start": start, "period_end": end}


def _month_rows(start, end, waste):
    return [_term("waste", waste, start, end), _term("good", 700.0, start, end, sales=2000.0)]


DATA = {"ppc_search_terms": (
    [_term("waste", 300.0, "2026-07-01", "2026-07-30"), _term("good", 700.0, "2026-07-01", "2026-07-30", 2000.0)]  # before the move
    + _month_rows("2026-08-12", "2026-08-31", 0.0)      # between the move and month 1: nobody's month
    + _month_rows("2026-09-02", "2026-10-01", 0.0)      # month 1: the leak holds
    + _month_rows("2026-10-02", "2026-11-01", 0.0)      # month 2: still holds
    + _month_rows("2026-11-02", "2026-12-01", 300.0)    # month 3: the term spends again
)}


def test_months_run_from_the_yes_and_close_a_week_after_they_end():
    ms = monthly.billing_months(CLIENT, date(2026, 11, 10))
    assert [(m["start"].isoformat(), m["end"].isoformat()) for m in ms] == [
        ("2026-08-02", "2026-09-01"), ("2026-09-02", "2026-10-01"),
        ("2026-10-02", "2026-11-01"), ("2026-11-02", "2026-12-01")]
    assert [m["free"] for m in ms] == [True, False, False, False]
    assert [m["closed"] for m in ms] == [True, True, True, False]      # Nov 1 + 7 days = Nov 8
    assert monthly.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert monthly.billing_months({"retainer_started_at": None}, date(2026, 11, 10)) == []


def test_a_leak_that_holds_earns_every_month_and_never_above_the_promise():
    m = _months()
    for k in (1, 2):
        v = monthly.measure_month([_bleed()], DATA, [], [], [], m[k])
        total = monthly.month_total(v)
        assert v[0]["verdict"] == "measured" and 0 < total <= 300.0, (k, v)
        # the month's own rows, and only those
        assert v[0]["window"][0] >= m[k]["start"].isoformat()


def test_a_leak_that_stopped_holding_earns_nothing_that_month():
    m = _months()
    assert monthly.month_total(monthly.measure_month([_bleed()], DATA, [], [], [], m[3])) == 0


def test_no_row_is_counted_in_two_months():
    m = _months()
    straddling = {"ppc_search_terms": DATA["ppc_search_terms"][:2] + _month_rows("2026-10-01", "2026-10-30", 0.0)}
    # It starts on Oct 1, inside month 1, so it is month 1's and not month 2's.
    assert monthly.measure_month([_bleed()], straddling, [], [], [], m[1])[0]["verdict"] == "measured"
    assert monthly.measure_month([_bleed()], straddling, [], [], [], m[2])[0]["verdict"] != "measured"


def test_rows_between_the_move_and_the_month_belong_to_no_month():
    m = _months()
    sliced = monthly._slice(DATA["ppc_search_terms"], date(2026, 8, 10), m[1])
    starts = sorted({r["period_start"] for r in sliced})
    assert starts == ["2026-07-01", "2026-09-02"]


def test_a_reimbursement_counts_once_in_the_month_amazon_paid_it():
    m = _months()
    d = {"id": "d2", "kind": "recovery_filing", "status": "done", "executed_at": "2026-08-20",
         "issued_at": "2026-08-18", "expected_impact_usd": 400.0, "evidence": {"claim_keys": ["k1", "k2"]}}
    claims = [{"claim_key": "k1", "status": "paid", "paid_amount": 250.0, "paid_at": "2026-10-15", "filed_at": "2026-08-21"},
              {"claim_key": "k2", "status": "paid", "paid_amount": 90.0, "paid_at": "2026-10-20"}]   # Amazon's own: not ours
    assert monthly.month_total(monthly.measure_month([d], {}, [], [], claims, m[1])) == 0
    v = monthly.measure_month([d], {}, [], [], claims, m[2])
    assert monthly.month_total(v) == 250.0 and v[0]["attribution"] == "direct"
    assert monthly.month_total(monthly.measure_month([d], {}, [], [], claims, m[3])) == 0


def test_a_move_made_after_the_month_or_that_carries_no_dollars_is_left_out():
    m = _months()
    late = _bleed(id="late", executed_at="2026-10-05", issued_at="2026-10-01")
    info = _bleed(id="info", kind="price_experiment")
    reorder = _bleed(id="reorder", kind="inventory_reorder")
    declined = _bleed(id="no", status="declined")
    assert monthly.measure_month([late, info, reorder, declined], DATA, [], [], [], m[1]) == []


def test_two_moves_on_the_same_movement_are_credited_once_to_the_oldest():
    """The rule as the terms state it: the same movement on the same SKU in the same
    period is credited to one move only (measurement._dedupe_overlapping)."""
    m = _months()
    def on_sku(**kw):
        d = _bleed(**kw)
        return {**d, "evidence": {**d["evidence"], "sku": "W1"}}
    older = on_sku(id="a", issued_at="2026-08-01")
    newer = on_sku(id="b", issued_at="2026-08-05")
    v = {x["directive_id"]: x for x in monthly.measure_month([newer, older], DATA, [], [], [], m[1])}
    assert v["a"]["verdict"] == "measured" and v["b"]["verdict"] == "unmeasurable"


def test_the_month_row_clears_only_above_the_fee_and_a_dispute_comes_off_it():
    m = _months()
    v = monthly.measure_month([_bleed()], DATA, [], [], [], m[1])
    row = monthly.month_row(CLIENT, m[1], v)
    assert row["clears"] is False and row["fee_usd"] == 6000.0 and row["free"] is False
    assert row["attributed_usd"] == monthly.month_total(v) and row["moves"][0]["directive_id"] == "d1"
    rich = monthly.month_row(CLIENT, m[1], [{"directive_id": "x", "verdict": "measured", "measured_impact_usd": 6000.01}])
    assert rich["clears"] is True
    level = monthly.month_row(CLIENT, m[1], [{"directive_id": "x", "verdict": "measured", "measured_impact_usd": 6000.0}])
    assert level["clears"] is False                                   # a tie goes to the client
    assert monthly.standing({"attributed_usd": 7000, "disputed_usd": 1200}) == 5800.0
