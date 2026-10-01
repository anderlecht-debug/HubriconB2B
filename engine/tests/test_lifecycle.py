"""The five stages and what each may be sent. The rule the machine was missing:
nobody is treated as a client before they say yes, and nobody who said no or
left is sent anything unasked."""

from datetime import datetime, timezone

from hubricon_engine import lifecycle
from fakedb import FakeDB

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


def test_a_booking_before_its_call_is_booked():
    assert lifecycle.stage({"status": "pending"}, "2026-10-06T15:00:00Z", NOW) == "booked"
    assert lifecycle.stage({"status": "pending"}, None, NOW) == "booked"


def test_after_the_call_with_no_answer_recorded_it_is_called():
    assert lifecycle.stage({"status": "pending"}, "2026-10-02T15:00:00Z", NOW) == "called"


def test_the_yes_is_retainer_started_at():
    c = {"status": "pending", "retainer_started_at": "2026-10-03T00:00:00Z"}
    assert lifecycle.stage(c, "2026-10-02T15:00:00Z", NOW) == "agreed"
    assert lifecycle.stage({"status": "active"}, None, NOW) == "agreed"


def test_no_and_leaving_beat_everything_else():
    assert lifecycle.stage({"status": "declined", "retainer_started_at": "2026-10-03"}, None, NOW) == "declined"
    assert lifecycle.stage({"status": "churned", "retainer_started_at": "2026-10-03"}, None, NOW) == "churned"


def test_nothing_that_belongs_to_a_client_reaches_someone_who_has_not_said_yes():
    for s in ("booked", "called"):
        for kind in ("moves", "brief", "weekly_note", "alerts", "agreed"):
            assert not lifecycle.may_send(s, kind), (s, kind)


def test_before_the_call_only_the_call_prep_and_a_first_read_they_asked_for():
    assert lifecycle.ALLOWED["booked"] == {"call_prep", "first_read"}
    assert not lifecycle.may_send("booked", "nudge")
    assert not lifecycle.may_send("booked", "downsell")


def test_a_no_or_an_exit_silences_every_automated_email():
    for s in ("declined", "churned"):
        assert lifecycle.ALLOWED[s] == frozenset()


def test_the_call_is_the_latest_booking_that_is_not_a_kickoff():
    db = FakeDB(bookings=[
        {"client_id": "c1", "starts_at": "2026-10-02T15:00:00Z", "event_type": "Margin audit", "created_at": "2026-09-30T00:00:00Z"},
        {"client_id": "c1", "starts_at": "2026-10-09T15:00:00Z", "event_type": "Margin audit", "created_at": "2026-10-01T00:00:00Z"},
        {"client_id": "c1", "starts_at": "2026-10-20T15:00:00Z", "event_type": "Hubricon Kickoff", "created_at": "2026-10-04T00:00:00Z"},
    ])
    assert lifecycle.call_at(db, "c1") == datetime(2026, 10, 9, 15, tzinfo=timezone.utc)
    assert lifecycle.stage_of(db, {"id": "c1", "status": "pending"}, NOW) == "booked"   # rescheduled to the 9th
