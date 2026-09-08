"""Speed to value, as arithmetic."""

from datetime import datetime, timezone

from hubricon_engine import speed
from fakedb import FakeDB

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def test_hours_between_two_stamps_and_none_when_one_is_missing():
    assert speed.hours("2026-09-08T00:00:00+00:00", "2026-09-08T06:30:00+00:00") == 6.5
    assert speed.hours(None, "2026-09-08T06:30:00+00:00") is None
    assert speed.hours("2026-09-08T00:00:00Z", NOW) == 12.0


def test_a_client_past_the_promise_with_no_issue_is_a_breach():
    clients = [
        {"id": "a", "exports_landed_at": "2026-09-07T00:00:00Z"},                       # 36h, no issue
        {"id": "b", "exports_landed_at": "2026-09-08T06:00:00Z"},                       # 6h, still inside
        {"id": "c", "exports_landed_at": "2026-09-01T00:00:00Z", "first_issue_at": "2026-09-01T05:00:00Z"},
        {"id": "d"},                                                                     # nothing landed
    ]
    late = speed.breaches(clients, NOW)
    assert [b["client"]["id"] for b in late] == ["a"] and late[0]["hours"] == 36.0


def test_summary_medians_and_the_digest_names_the_late_one():
    clients = [
        {"id": "a", "company_name": "Alpha", "exports_landed_at": "2026-09-07T00:00:00Z"},
        {"id": "c", "exports_landed_at": "2026-09-01T00:00:00Z", "first_issue_at": "2026-09-01T05:00:00Z",
         "first_value_at": "2026-09-13T00:00:00Z"},
        {"id": "e", "exports_landed_at": "2026-09-02T00:00:00Z", "first_issue_at": "2026-09-02T09:00:00Z"},
    ]
    s = speed.summary(clients)
    assert s["n_measured"] == 2 and s["median_hours_to_first_issue"] == 7.0
    assert s["n_with_value"] == 1 and s["median_days_to_first_value"] == 12.0
    assert s["n_waiting"] == 1
    text = "\n".join(speed.digest_lines(clients, NOW))
    assert "median 7.0h" in text and "LATE: Alpha" in text and "12.0d" in text


def test_the_digest_is_honest_when_nothing_has_been_measured():
    text = "\n".join(speed.digest_lines([{"id": "x"}], NOW))
    assert "no client has had exports land" in text


def test_set_once_sets_and_then_refuses():
    db = FakeDB(clients=[{"id": "c1", "exports_landed_at": None}])
    c = {"id": "c1", "exports_landed_at": None}
    assert speed.set_once(db, c, "exports_landed_at", NOW) is True
    assert c["exports_landed_at"] == NOW.isoformat()
    assert db.rows("clients")[0]["exports_landed_at"] == NOW.isoformat()
    assert speed.set_once(db, c, "exports_landed_at") is False
    assert len([w for w in db.writes if w[1] == "update"]) == 1
