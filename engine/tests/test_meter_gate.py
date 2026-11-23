"""The fee question and its pre-registered kill counter."""

from datetime import UTC, datetime, timedelta

import pytest
from fakedb import FakeDB

from hubricon_engine import hwm
from hubricon_engine import meter_gate as mg

NOW = datetime(2026, 11, 23, 12, tzinfo=UTC)


def _rows(approved=0, declined=0, open_=0, none=0, old_open=0):
    rows, i = [], 0
    for state, n, age in (("approved", approved, 1), ("declined", declined, 1), ("ask", open_, 1),
                          ("none", none, 1), ("ask", old_open, 30)):
        for _ in range(n):
            i += 1
            rows.append({"shop_domain": f"s{i:03d}.myshopify.com", "fee_question": state,
                         "fee_question_at": None if state == "none" else (NOW - timedelta(days=age, minutes=i)).isoformat()})
    return rows


def test_the_constants_are_the_pre_registered_ones():
    assert (mg.DECIDE_AT, mg.KILL_BELOW, mg.CONFIRM_AT) == (20, 0.2, 0.4)


def test_first_proven_dollar_opens_the_question_once():
    statements = hwm.run("s.myshopify.com", [
        {"month": "2026-10", "dollars": [{"id": "a", "usd": -50, "grade": "isolated"}]},
        {"month": "2026-11", "dollars": [{"id": "b", "usd": 300, "grade": "isolated"}]}])
    assert mg.first_proven(statements) == 250.0
    patch = mg.ask_patch({"fee_question": "none"}, statements, NOW)
    assert patch["fee_question"] == "ask" and patch["first_proven_usd"] == 250.0
    assert mg.ask_patch({"fee_question": "ask"}, statements, NOW) is None
    assert mg.ask_patch({"fee_question": "none"}, statements[:1], NOW) is None     # a loss proves nothing


def test_answers_are_recorded_once():
    db = FakeDB()
    db.table("shopify_shops").insert({"shop_domain": "s.myshopify.com", "fee_question": "none"}).execute()
    assert mg.mark_ask(db, "s.myshopify.com", {"fee_question": "none"}, [{"cumulative": 10}], NOW)
    mg.record(db, "s.myshopify.com", True, NOW)
    assert db.store["shopify_shops"][0]["fee_question"] == "approved"
    with pytest.raises(ValueError):
        mg.record(db, "s.myshopify.com", False, NOW)


def test_undecided_before_twenty_whatever_the_answers():
    assert mg.rule(_rows(declined=19), NOW)["verdict"] == mg.UNDECIDED
    assert mg.rule(_rows(approved=19, none=50), NOW)["verdict"] == mg.UNDECIDED
    assert "1 more store" in mg.lines(mg.rule(_rows(approved=19), NOW))[1]


def test_kill_confirm_between_at_twenty():
    assert mg.rule(_rows(approved=3, declined=17), NOW)["verdict"] == mg.KILL        # 1.5 in 10
    assert mg.rule(_rows(approved=8, declined=12), NOW)["verdict"] == mg.CONFIRM     # 4 in 10
    assert mg.rule(_rows(approved=5, declined=15), NOW)["verdict"] == mg.BETWEEN
    # sequential: confirmed as soon as 8 approve, killed once open answers cannot reach 4
    assert mg.rule(_rows(approved=8, open_=12), NOW)["verdict"] == mg.CONFIRM
    assert mg.rule(_rows(approved=2, declined=17, open_=1), NOW)["verdict"] == mg.KILL
    assert mg.rule(_rows(approved=3, declined=16, open_=1), NOW)["verdict"] == mg.UNDECIDED
    # silence past the window is a decline
    assert mg.rule(_rows(approved=3, declined=7, old_open=10), NOW)["verdict"] == mg.KILL
    # only the first twenty count
    late = [{"shop_domain": f"late{i}.myshopify.com", "fee_question": "approved",
             "fee_question_at": NOW.isoformat()} for i in range(10)]
    r = mg.rule(_rows(approved=3, declined=17) + late, NOW)
    assert r["verdict"] == mg.KILL and r["cohort"] == 20 and r["after_cohort"] == 10


def test_digest_prints_the_verdict():
    db = FakeDB()
    for r in _rows(approved=3, declined=17):
        db.table("shopify_shops").insert(r).execute()
    lines = mg.digest_lines(db, NOW)
    assert "20 saw proof" in lines[0] and "KILL" in lines[1]
    assert mg.digest_lines(FakeDB(), NOW) == []
