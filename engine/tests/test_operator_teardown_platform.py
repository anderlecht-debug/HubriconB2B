"""A prospect who asked for a Teardown gets the instructions for their own
platform. The harvest knows a cold prospect's platform; the 60-second
Teardown's capture (tool_runs) knows a tool lead's. Neither known: Amazon,
as before."""
from __future__ import annotations

from fakedb import FakeDB
from hubricon_engine import onboarding, operator


def _run(monkeypatch, *, harvest, runs):
    db = FakeDB(
        prospects=[{"id": "p1", "email": "owner@brand.com", "first_name": "Ada", "status": "wants_teardown", "client_id": None}],
        harvest_sellers=harvest, tool_runs=runs, funnel_events=[], client_touches=[],
    )
    seen = {}
    monkeypatch.setattr(onboarding, "provision", lambda _db, email, name, company, platform: (
        seen.__setitem__("platform", platform) or ({"id": "c1", "contact_email": email}, "https://x/upload", True)))
    monkeypatch.setattr(operator.Pass, "_touch", lambda self, client, kind, link, force=False: seen.__setitem__("kind", kind) or True)
    operator.Pass(db, send=False, dry=False).teardown_requests()
    return seen, db


def test_a_tool_lead_from_a_shopify_store_gets_shopify_instructions(monkeypatch):
    seen, db = _run(monkeypatch, harvest=[], runs=[{"email": "owner@brand.com", "platform": "shopify", "created_at": "2026-09-09T10:00:00+00:00"}])
    assert seen["platform"] == "shopify" and seen["kind"] == "files"
    assert db.rows("prospects")[0]["client_id"] == "c1"


def test_the_latest_run_decides_when_a_lead_ran_both_lanes(monkeypatch):
    seen, _ = _run(monkeypatch, harvest=[], runs=[
        {"email": "owner@brand.com", "platform": "shopify", "created_at": "2026-09-08T10:00:00+00:00"},
        {"email": "owner@brand.com", "platform": "amazon", "created_at": "2026-09-09T10:00:00+00:00"},
    ])
    assert seen["platform"] == "amazon"


def test_the_harvest_row_wins_over_the_tool_and_nothing_known_means_amazon(monkeypatch):
    seen, _ = _run(monkeypatch, harvest=[{"email": "owner@brand.com", "platform": "shopify"}],
                   runs=[{"email": "owner@brand.com", "platform": "amazon", "created_at": "2026-09-09T10:00:00+00:00"}])
    assert seen["platform"] == "shopify"
    seen, _ = _run(monkeypatch, harvest=[], runs=[])
    assert seen["platform"] == "amazon"
