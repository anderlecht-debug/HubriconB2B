"""Calibration: honest about n, silent without consent, and a fallback that
leaves the published card in charge."""

import math

import pytest

from hubricon_engine import calibration
from hubricon_engine.cold import priors
from hubricon_engine.harvest import amazon, shopify
from fakedb import FakeDB


@pytest.fixture(autouse=True)
def _clean():
    calibration.reset()
    yield
    calibration.reset()


def test_the_fit_recovers_a_known_curve():
    a, b = 5.9, 0.9
    pairs = [(r, 10 ** (a - b * math.log10(r))) for r in (100, 500, 1000, 5000, 20000, 90000)]
    fa, fb, n = calibration.fit_loglog(pairs)
    assert n == 6 and abs(fa - a) < 1e-6 and abs(fb - b) < 1e-6
    assert calibration.fit_loglog([(100, 5)]) is None
    assert calibration.fit_loglog([(100, 5), (100, 7)]) is None      # no spread in x


def test_below_the_floor_the_row_says_insufficient_and_carries_no_value():
    r = calibration._row("shopify.orders_per_review", 41.2, n_clients=1, n_obs=12, method="ratio")
    assert r["value"] is None and r["method"] == "insufficient" and "have 1 and 12" in r["note"]
    r = calibration._row("shopify.orders_per_review", 41.2, n_clients=2, n_obs=40, method="ratio")
    assert r["value"] == 41.2 and r["method"] == "ratio"


def test_readers_fall_back_to_the_published_figure_when_nothing_is_loaded():
    assert calibration.get("amazon.referral_rate.home & kitchen", 0.15) == 0.15
    assert calibration.describe("anything") is None
    assert priors.referral_rate("Home & Kitchen") == priors.REFERRAL_BY_CATEGORY.get("home & kitchen", priors.REFERRAL_DEFAULT)
    base = amazon.estimate_units(5000, "Home & Kitchen")
    assert base and base > 0


def test_a_loaded_row_overrides_the_card_and_says_so():
    db = FakeDB(calibration=[
        {"key": "amazon.referral_rate.home & kitchen", "value": 0.1512, "n_clients": 2, "n_obs": 88, "method": "ratio"},
        {"key": "amazon.bsr_curve.home & kitchen.a", "value": 5.5, "n_clients": 2, "n_obs": 40, "method": "fit"},
        {"key": "amazon.bsr_curve.home & kitchen.b", "value": 0.8, "n_clients": 2, "n_obs": 40, "method": "fit"},
        {"key": "shopify.orders_per_review", "value": 33.0, "n_clients": 3, "n_obs": 120, "method": "ratio"},
        {"key": "amazon.referral_rate.toys", "value": None, "n_clients": 1, "n_obs": 3, "method": "insufficient"},
    ])
    calibration.load(db)
    assert priors.referral_rate("Home & Kitchen") == 0.1512
    assert priors.referral_rate("Toys") == priors.REFERRAL_BY_CATEGORY.get("toys", priors.REFERRAL_DEFAULT)
    assert calibration.describe("amazon.referral_rate.home & kitchen") == "calibrated on 2 client accounts (88 observations)"
    assert amazon.estimate_units(1000, "Home & Kitchen") == round(10 ** (5.5 - 0.8 * 3), 1)
    assert amazon.estimate_units(1000, "Toys") == amazon.estimate_units(1000, "Toys", curve=None)
    # the Shopify size band rides on the learned ratio
    est = shopify.estimate_annual([10, 20], 20, 30.0, 2.0)
    assert est == round(30 * (20 / 2) * 33.0 * 30.0 / 2.0, 2)


def test_compute_on_an_unconsented_database_writes_only_insufficient_rows():
    db = FakeDB(consents=[], clients=[{"id": "c1", "contact_email": "a@b.com", "platform": "shopify"}], calibration=[])
    said = []
    rows = calibration.compute(db, log=said.append)
    assert rows and all(r["value"] is None and r["method"] == "insufficient" for r in rows)
    assert any("no client has granted calibration consent" in s for s in said)
    assert db.rows("calibration")[0]["key"] == "shopify.orders_per_review"


def test_compute_reads_only_consenting_non_internal_clients():
    db = FakeDB(
        consents=[{"client_id": "c1", "kind": "calibration", "granted": True},
                  {"client_id": "c2", "kind": "calibration", "granted": True},
                  {"client_id": "c3", "kind": "anonymised_results", "granted": True}],
        clients=[{"id": "c1", "contact_email": "a@brand.com", "platform": "amazon"},
                 {"id": "c2", "contact_email": "dry@hubricon.internal", "platform": "amazon"},
                 {"id": "c3", "contact_email": "c@brand.com", "platform": "amazon"}],
    )
    assert [c["id"] for c in calibration.consented_clients(db)] == ["c1"]


def test_a_client_who_left_or_said_no_calibrates_nothing_whatever_they_once_granted():
    """The consent was given by a client, about the work we were doing for them:
    from the day they leave (churned) or say no (declined) their data calibrates
    nothing, the rule fleet.py keeps for the network's sources."""
    db = FakeDB(
        consents=[{"client_id": c, "kind": "calibration", "granted": True} for c in ("c1", "c2", "c3", "c4", "c5")],
        clients=[{"id": "c1", "contact_email": "a@brand.com", "status": "active"},
                 {"id": "c2", "contact_email": "b@brand.com", "status": "churned"},
                 {"id": "c3", "contact_email": "c@brand.com", "status": "declined"},
                 {"id": "c4", "contact_email": "d@brand.com", "status": "past_due"},
                 {"id": "c5", "contact_email": "e@brand.com", "status": "pending"}],
    )
    # past_due is still a current client (terms §5: only an email ends it); churned and declined are not
    assert sorted(c["id"] for c in calibration.consented_clients(db)) == ["c1", "c4", "c5"]
    assert sorted(c["id"] for c in calibration.consented_clients(db, statuses=None)) == ["c1", "c2", "c3", "c4", "c5"]


def test_calibration_and_the_fleet_read_the_same_current_clients():
    """Two network uses, one definition of who is a source: the calibration gate's
    default is exactly fleet.SOURCE_STATUSES, so the two can never disagree."""
    from hubricon_engine import fleet
    assert calibration.current_statuses() is fleet.SOURCE_STATUSES
    statuses = ("pending", "active", "past_due", "churned", "declined")
    db = FakeDB(
        consents=[{"client_id": f"c{i}", "kind": k, "granted": True}
                  for i in range(len(statuses)) for k in ("calibration", "network")],
        clients=[{"id": f"c{i}", "contact_email": f"x{i}@brand.com", "status": s} for i, s in enumerate(statuses)],
    )
    calibrating = sorted(c["id"] for c in calibration.consented_clients(db))
    assert calibrating == sorted(c["id"] for c in fleet.consenting_accounts(db))
    assert calibrating == sorted(f"c{i}" for i, s in enumerate(statuses) if s in fleet.SOURCE_STATUSES)


def test_a_past_due_client_still_sources_and_still_hears_about_its_fees():
    """A failed ACH debit does not end the relationship (terms §5), so a past-due client keeps
    calibrating, keeps sourcing the network and keeps receiving fee-change alerts; a churned
    one does none of the three (the founder's call, 2026-10-06)."""
    from hubricon_engine import fleet
    assert "past_due" in fleet.SOURCE_STATUSES and "past_due" in fleet.RECIPIENT_STATUSES
    assert "churned" not in fleet.SOURCE_STATUSES and "churned" not in fleet.RECIPIENT_STATUSES
    db = FakeDB(
        consents=[{"client_id": c, "kind": "calibration", "granted": True} for c in ("late", "gone")],
        clients=[{"id": "late", "contact_email": "l@brand.com", "status": "past_due"},
                 {"id": "gone", "contact_email": "g@brand.com", "status": "churned"}],
    )
    assert [c["id"] for c in calibration.consented_clients(db)] == ["late"]
