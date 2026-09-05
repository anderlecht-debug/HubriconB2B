"""The orchestration's own decisions: what is sendable, and what to run next."""

from datetime import date, datetime, timezone

from hubricon_engine.cold import run as cold
from hubricon_engine.cold.snapshot import Observation


def test_a_row_with_a_named_owner_on_their_own_domain_is_ready():
    assert cold.blocker({"email": "dana@testbrand.com", "website": "https://testbrand.com",
                         "first_name": "Dana"}) is None


def test_a_role_inbox_is_inventory_not_a_draft_to_send():
    # The founder's standing call, 2026-09-03: info@ reaches a support queue and
    # is never cold emailed, however good the finding behind it is.
    stop = cold.blocker({"email": "info@testbrand.com", "website": "https://testbrand.com",
                         "first_name": "Dana"})
    assert stop and "role inbox" in stop


def test_an_address_on_someone_elses_domain_is_the_wrong_person():
    stop = cold.blocker({"email": "micah@micahrich.com", "website": "https://rhinousa.com",
                         "first_name": "Micah"})
    assert stop and "is not on" in stop


def test_no_name_means_no_send():
    stop = cold.blocker({"email": "dana@testbrand.com", "website": "https://testbrand.com"})
    assert stop and "name" in stop


def test_no_address_points_at_the_command_that_finds_one():
    stop = cold.blocker({"website": "https://testbrand.com"})
    assert stop and "harvest enrich" in stop


def test_the_silent_ones_are_reported_with_the_command_that_unblocks_them():
    steps = cold.next_steps({"no contact address on file": 41,
                             "no finding at all": 63,
                             "off ICP (software)": 2})
    commands = {c for _, c, _ in steps}
    assert "hubricon harvest enrich" in commands
    assert "hubricon harvest listings" in commands
    # An off-ICP company is not a company a command can fix.
    assert all("ICP" not in why for _, _, why in steps)


def test_observations_are_one_row_a_listing_a_day():
    written = {}

    class Table:
        def upsert(self, rows, on_conflict=None):
            written["rows"], written["on_conflict"] = rows, on_conflict
            return self

        def execute(self):
            return self

    cold.record_observations(type("DB", (), {"table": lambda self, _n: Table()})(), [
        {"asin": "B001", "price": 10.0, "bsr": 500},
        {"asin": "B001", "price": 10.0, "bsr": 500},      # the same listing twice in one pass
        {"asin": "B002", "price": 20.0},
        {"price": 30.0},                                   # no asin: nothing to key on
    ])
    assert [r["asin"] for r in written["rows"]] == ["B001", "B002"]
    assert written["on_conflict"] == "asin,seen_on"
    # UTC, matching the table's own default, so the two daily crawls agree on
    # which day they are in wherever the Mac happens to be.
    assert written["rows"][0]["seen_on"] == datetime.now(timezone.utc).date().isoformat()


def test_a_failure_to_keep_history_never_loses_the_crawls_real_work():
    class Angry:
        def upsert(self, *_a, **_k):
            return self

        def execute(self):
            raise RuntimeError("relation does not exist")

    said = []
    kept = cold.record_observations(type("DB", (), {"table": lambda self, _n: Angry()})(),
                                    [{"asin": "B001", "price": 10.0}], log=said.append)
    assert kept == 0
    assert said and "price history not kept" in said[0]


def test_history_returns_observations_in_the_order_they_were_seen():
    class Q:
        rows = [{"asin": "B001", "price": 12.0, "bsr": 900, "seen_on": "2026-08-01"},
                {"asin": "B001", "price": 10.5, "bsr": 910, "seen_on": "2026-08-20"}]

        def select(self, *_a):
            return self

        def in_(self, *_a):
            return self

        def order(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": self.rows})()

    hist = cold._history(type("DB", (), {"table": lambda self, _n: Q()})(), ["B001"])
    assert hist["B001"] == [Observation(date(2026, 8, 1), 12.0, 900),
                            Observation(date(2026, 8, 20), 10.5, 910)]
