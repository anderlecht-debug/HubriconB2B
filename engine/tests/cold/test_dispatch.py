"""Approved teardowns into Instantly.

The campaign is a delivery shell: subject and body are one merge field each, so
the bytes a prospect reads are the bytes the founder approved. Most of these
tests exist to keep it that way, and to prove that compliance still runs on
every single lead on the way out.
"""

import pytest

from hubricon_engine.cold import dispatch
from hubricon_engine.instantly import InstantlyError


class FakeAPI:
    def __init__(self, senders=("a@gethubricon.com", "b@tryhubricon.com"), refuse=False):
        self._senders = list(senders)
        self.refuse = refuse
        self.created, self.leads, self.updated, self.activated = [], [], [], []

    def ready_senders(self):
        return [{"email": e} for e in self._senders]

    def campaigns(self):
        return self.created

    def find_campaign(self, name):
        return next((c for c in self.created if c["name"] == name), None)

    def create_campaign(self, spec):
        c = {"id": "camp-1", **spec}
        self.created.append(c)
        return c

    def update_campaign(self, cid, fields):
        self.updated.append((cid, fields))
        return {}

    def activate_campaign(self, cid):
        self.activated.append(cid)
        return {}

    def create_lead(self, campaign_id, email, **kw):
        if self.refuse:
            raise InstantlyError(400, "/leads", "bounce protect")
        self.leads.append({"campaign": campaign_id, "email": email, **kw})
        return {"id": f"lead-{len(self.leads)}"}


class Table:
    def __init__(self, store, name):
        self.store, self.name, self._f = store, name, []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._f.append((col, val))
        return self

    def in_(self, col, vals):
        self._f.append((col, vals))
        return self

    def gte(self, *_a):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def insert(self, row):
        self.store.setdefault(self.name, []).append(row)
        return self

    def upsert(self, rows, **_k):
        # A caller may upsert one row or many; extending with a bare dict
        # extends with its keys, which is a list of strings and a confusing
        # traceback three frames later.
        rows = rows if isinstance(rows, list) else [rows]
        held = self.store.setdefault(self.name, [])
        for row in rows:
            existing = next((r for r in held if r.get("key") and r.get("key") == row.get("key")),
                            None)
            if existing:
                existing.update(row)
            else:
                held.append(dict(row))
        return self

    def update(self, patch):
        for r in self._rows():
            r.update(patch)
        return self

    def _rows(self):
        rows = self.store.get(self.name, [])
        for col, val in self._f:
            rows = [r for r in rows
                    if (r.get(col) in val if isinstance(val, list) else r.get(col) == val)]
        return rows

    def execute(self):
        rows = self._rows()
        self._f = []
        return type("R", (), {"data": rows})()


class FakeDB:
    def __init__(self, **store):
        self.store = store

    def table(self, name):
        return Table(self.store, name)


def a_db(status="approved"):
    return FakeDB(
        teardowns=[{"id": "td-1", "prospect_key": "shop.myshopify.com", "status": status,
                    "token": "tok123", "subject": "A fraction of an ounce over a band",
                    "body": "Hi —\nBarnes & Noble <ok>\nHagen"}],
        harvest_sellers=[{"seller_id": "shop.myshopify.com", "platform": "shopify",
                          "brand": "Riverbend Goods", "website": "https://riverbend.com",
                          "email": "hello@riverbend.com", "country": "US",
                          "first_name": None, "last_name": None, "est_monthly_revenue": 90000}],
        harvest_products=[], outreach_sends=[], suppressions=[],
        operator_state=[], funnel_events=[])


@pytest.fixture(autouse=True)
def _sendable(monkeypatch):
    monkeypatch.setenv("COLD_DRY_RUN", "false")
    monkeypatch.setenv("POSTAL_ADDRESS", "PO Box 1, Austin TX 78701")


def test_the_campaign_body_is_one_merge_field_so_nothing_rewrites_the_finding():
    step = dispatch.campaign_spec(["a@x.com"])["sequences"][0]["steps"][0]["variants"][0]
    assert step["subject"] == "{{teardownSubject}}"
    assert step["body"] == "{{teardownBody}}"


def test_the_campaign_matches_the_conventions_of_the_one_beside_it():
    spec = dispatch.campaign_spec(["a@x.com", "b@y.com"])
    assert spec["insert_unsubscribe_header"] and spec["stop_on_reply"]
    assert spec["stop_for_company"] and not spec["allow_risky_contacts"]
    assert not spec["open_tracking"] and not spec["link_tracking"]
    assert len(spec["sequences"][0]["steps"]) == 1, "no follow-ups on a first touch"
    assert spec["daily_limit"] == dispatch.PER_MAILBOX_DAILY * 2


def test_an_approved_teardown_goes_out_with_its_own_words():
    db, api = a_db(), FakeAPI()
    sent, notes = dispatch.push(db, api)
    assert sent == 1
    lead = api.leads[0]
    assert lead["email"] == "hello@riverbend.com"
    assert lead["custom"]["teardownSubject"] == "A fraction of an ounce over a band"
    assert lead["custom"]["teardownBody"].startswith("Hi —<br/>")
    assert "&amp;" in lead["custom"]["teardownBody"] and "<ok>" not in lead["custom"]["teardownBody"]
    assert db.store["teardowns"][0]["status"] == "sent"


def test_the_send_is_recorded_so_the_ninety_day_rule_is_real():
    db, api = a_db(), FakeAPI()
    dispatch.push(db, api)
    row = db.store["outreach_sends"][0]
    assert row["prospect_key"] == "shop.myshopify.com"
    assert row["teardown_id"] == "td-1"
    assert row["provider_message_id"] == "lead-1"
    assert "legitimate interest" in row["basis"]


def test_only_approved_teardowns_are_dispatched():
    for status in ("draft", "rejected", "sent", "expired"):
        db, api = a_db(status), FakeAPI()
        assert dispatch.push(db, api)[0] == 0, status
        assert not api.leads


def test_a_suppressed_prospect_is_reported_not_sent():
    db, api = a_db(), FakeAPI()
    db.store["suppressions"] = [{"email": "hello@riverbend.com", "reason": "asked us to stop"}]
    sent, notes = dispatch.push(db, api)
    assert sent == 0 and not api.leads
    assert any("asked us to stop" in n for n in notes)
    assert db.store["teardowns"][0]["status"] == "approved", "it stays approved to be seen"


def test_dry_run_names_who_would_go_and_sends_nothing():
    db, api = a_db(), FakeAPI()
    sent, notes = dispatch.push(db, api, dry=True)
    assert sent == 1 and not api.leads
    assert any("[dry]" in n and "hello@riverbend.com" in n for n in notes)
    assert db.store["teardowns"][0]["status"] == "approved"


def test_the_global_dry_run_flag_stops_it_too(monkeypatch):
    monkeypatch.setenv("COLD_DRY_RUN", "true")
    db, api = a_db(), FakeAPI()
    assert dispatch.push(db, api)[0] == 0 and not api.leads


def test_no_api_key_is_reported_rather_than_looking_like_silence():
    db = a_db()
    sent, notes = dispatch.push(db, None)
    assert sent == 0
    assert any("INSTANTLY_API_KEY" in n and "1 teardown" in n for n in notes)


def test_a_refused_lead_leaves_the_teardown_approved_and_says_why():
    db, api = a_db(), FakeAPI(refuse=True)
    sent, notes = dispatch.push(db, api)
    assert sent == 0
    assert db.store["teardowns"][0]["status"] == "approved"
    assert any("bounce protect" in n for n in notes)


def test_no_warmed_mailbox_means_no_campaign():
    db, api = a_db(), FakeAPI(senders=())
    sent, notes = dispatch.push(db, api)
    assert sent == 0 and not api.created
    assert any("past warmup" in n for n in notes)


def test_the_sending_pool_is_recorded_rather_than_a_guessed_domain():
    # Instantly picks the mailbox, so which domain a teardown left from is not
    # knowable here; recording a guess would make outreach_sends wrong.
    assert dispatch._pool_domain(["a@gethubricon.com", "b@tryhubricon.com"]) == \
        "gethubricon.com+tryhubricon.com"
    assert dispatch._pool_domain([]) is None
