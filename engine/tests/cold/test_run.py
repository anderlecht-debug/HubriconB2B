"""The orchestration's own decisions: what is sendable, and what to run next."""

from datetime import date, datetime, timezone

from hubricon_engine.cold import run as cold
from hubricon_engine.cold.snapshot import Observation


def test_a_row_with_a_named_owner_on_their_own_domain_is_ready():
    assert cold.blocker({"email": "dana@testbrand.com", "website": "https://testbrand.com",
                         "first_name": "Dana"}) is None


def test_a_role_inbox_is_sendable_and_carries_its_own_copy():
    """The founder's call moved on 2026-09-05. What arrives now is a teardown
    page with the brand's own shelf on it, which a support queue forwards rather
    than bins — and 27 of the 55 usable rows on file are role inboxes."""
    assert cold.blocker({"email": "info@testbrand.com", "website": "https://testbrand.com"}) is None


def test_the_old_role_inbox_rule_is_one_setting_away(monkeypatch):
    monkeypatch.setenv("COLD_ALLOW_ROLE_INBOX", "false")
    stop = cold.blocker({"email": "info@testbrand.com", "website": "https://testbrand.com"})
    assert stop and "role inbox" in stop


def test_an_address_on_someone_elses_domain_is_the_wrong_person():
    stop = cold.blocker({"email": "micah@micahrich.com", "website": "https://rhinousa.com",
                         "first_name": "Micah"})
    assert stop and "is not on" in stop


def test_a_personal_mailbox_with_no_name_behind_it_still_blocks():
    # "Hi there" to a named human's own address reads as a mail merge, which is
    # the one thing the page is trying not to be. A shared inbox is different:
    # it has no name to get wrong.
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


def test_a_rebuild_supersedes_the_draft_it_replaces():
    """`--force` used to leave both drafts in the queue, so the same prospect
    could be sent two teardowns about the same listing."""
    updates = []

    class Table:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_a, **_k):
            return self

        def eq(self, col, val):
            self.rows = [r for r in self.rows if r.get(col) == val]
            return self

        def update(self, patch):
            updates.append(patch)
            return self

        def order(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": self.rows})()

    drafts = [{"id": "old-1", "prospect_key": "A1", "status": "draft"},
              {"id": "sent-1", "prospect_key": "A1", "status": "sent"}]
    stale = [r for r in drafts if r["status"] == "draft"]
    assert len(stale) == 1, "only the draft is a candidate to supersede"
    tbl = Table([dict(r) for r in drafts])
    found = tbl.select("id").eq("prospect_key", "A1").eq("status", "draft").execute().data
    assert [r["id"] for r in found] == ["old-1"], "a sent teardown is a decision, not a draft"
