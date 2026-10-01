from hubricon_engine.alerts import (
    buybox_alerts,
    compute_alerts,
    dedupe,
    margin_flip_alerts,
    stockout_alerts,
)


def _inv(sku, p):
    return {"sku": sku, "stockout_probability": p, "lead_time_days": 40, "reorder_qty": 500}


def test_stockout_fires_on_new_crossing_only():
    current = [_inv("A", 0.30), _inv("B", 0.30), _inv("C", 0.10)]
    previous = [_inv("A", 0.05), _inv("B", 0.28)]  # A newly crossed; B already known, barely moved
    alerts = stockout_alerts(current, previous)
    assert [a["message"][:1] for a in alerts] == ["A"]
    assert alerts[0]["severity"] == "warning"


def test_stockout_refires_when_meaningfully_worse():
    alerts = stockout_alerts([_inv("A", 0.55)], [_inv("A", 0.30)])
    assert len(alerts) == 1 and alerts[0]["severity"] == "critical"
    # small drift does not re-fire
    assert stockout_alerts([_inv("A", 0.33)], [_inv("A", 0.30)]) == []


def test_margin_flip_needs_two_periods_and_a_sign_change():
    rows = [
        {"sku": "A", "period_start": "2026-06-01", "net_margin": 500.0},
        {"sku": "A", "period_start": "2026-07-01", "net_margin": -180.0},   # flip -> alert
        {"sku": "B", "period_start": "2026-06-01", "net_margin": -50.0},
        {"sku": "B", "period_start": "2026-07-01", "net_margin": -60.0},    # already negative -> no alert
    ]
    alerts = margin_flip_alerts(rows)
    assert len(alerts) == 1 and "A flipped" in alerts[0]["message"]
    assert margin_flip_alerts(rows[:1]) == []  # one period: nothing to compare


def test_buybox_alert_only_for_running_tests_with_real_drop():
    tests = [
        {"sku": "A", "status": "running", "buy_box_share_before": 92, "buy_box_share_during": 70, "test_price": 24.99},
        {"sku": "B", "status": "running", "buy_box_share_before": 92, "buy_box_share_during": 88, "test_price": 21.99},
        {"sku": "C", "status": "completed", "buy_box_share_before": 92, "buy_box_share_during": 40, "test_price": 19.99},
    ]
    alerts = buybox_alerts(tests)
    assert len(alerts) == 1 and "A" in alerts[0]["message"] and alerts[0]["severity"] == "critical"


def test_dedupe_drops_recent_repeats():
    fresh = compute_alerts([_inv("A", 0.6)], [], [], [])
    assert len(fresh) == 1
    assert dedupe(fresh, {fresh[0]["message"]}) == []
    assert dedupe(fresh, {"something else"}) == fresh


# -- the aged-inventory cliff, flagged early (HUBRICON_SPEC.md: the scoreboard's 10 of 5) --

from datetime import date, timedelta  # noqa: E402

from hubricon_engine.alerts import aged_cliff_alerts  # noqa: E402

SNAP = date(2026, 9, 28)


def _age(sku, b91, shipped_t30, older=0, snap=SNAP, **kw):
    """One row of an Inventory Age export (ingest/inventory_health.py's columns)."""
    return {"sku": sku, "snapshot_date": snap.isoformat(), "inv_age_0_to_90": 200, "inv_age_91_to_180": b91,
            "inv_age_181_to_270": older, "inv_age_271_to_365": 0, "inv_age_365_plus": 0,
            "units_shipped_t30": shipped_t30, "item_volume": 0.08, **kw}


def test_a_sku_whose_pace_will_not_clear_its_91_to_180_day_stock_is_flagged_before_181_days():
    rows = [
        _age("SLOW", 300, 60),                 # 2 a day: 92 of 300 sell in 46 days, 208 reach the cliff
        _age("FAST", 300, 600),                # 20 a day: all of it sells first
        _age("BEHIND", 300, 240, older=200),   # 8 a day, but 200 older units ship first: 300 - (368 - 200) = 132
        _age("FEW", 15, 3, item_volume=1.2),   # 0.1 a day: 4.6 sell, 10 left (12 cubic feet), at the floor
        _age("FEWER", 15, 9, item_volume=1.2),  # 0.3 a day: 13.8 sell, 1 left, under it
        _age("TINY", 8, 0),                    # under the unit floor: cents, not news
        _age("SMALL", 40, 0),                  # 40 left, but 3.2 cubic feet: a few dollars a month at most
    ]
    alerts = aged_cliff_alerts(rows, "amazon", today=SNAP)
    by = {a["message"].split(" units of ")[1].split(" ")[0]: a for a in alerts}
    assert set(by) == {"SLOW", "BEHIND", "FEW"}
    slow = by["SLOW"]
    assert slow["severity"] == "warning" and slow["module"] == "inventory"
    assert slow["message"].startswith(f"208 units of SLOW reach 181 days around {SNAP + timedelta(days=46):%b %-d}; ")
    assert ("Amazon's aged-inventory surcharge starts at $0.50 per cubic foot a month (about $0.04 a unit"
            in slow["message"])
    assert "An estimate from the age bucket's midpoint" in slow["message"]
    assert "last 30 days' pace of 2.0 units a day (your Inventory Age report)" in slow["message"]
    assert by["BEHIND"]["message"].startswith("132 units of BEHIND")


def test_the_cliff_warning_says_nothing_it_cannot_back():
    # No units-shipped column at all: no pace, so no claim.
    no_pace = {k: v for k, v in _age("X", 300, 0).items() if k != "units_shipped_t30"}
    assert aged_cliff_alerts([no_pace], "amazon", today=SNAP) == []
    # A longer window stands in when the 30-day one is missing, and the message names the window used.
    [a] = aged_cliff_alerts([{**no_pace, "units_shipped_t90": 90}], "amazon", today=SNAP)
    assert "last 90 days' pace of 1.0 units a day" in a["message"]
    # No volume on file: the per-unit figure is left out rather than guessed.
    bare = {**_age("V", 300, 0), "item_volume": None}
    assert "a unit at" not in aged_cliff_alerts([bare], "amazon", today=SNAP)[0]["message"]
    # A Shopify store has no aged-inventory surcharge to warn about.
    assert aged_cliff_alerts([_age("S", 300, 0)], "shopify", today=SNAP) == []
    # A date already past is not an early warning.
    assert aged_cliff_alerts([_age("OLD", 300, 0)], "amazon", today=SNAP + timedelta(days=60)) == []


def test_the_cliff_warning_fires_once_and_again_only_when_it_grows():
    before, now = SNAP - timedelta(days=7), SNAP
    known = [_age("A", 300, 60, snap=before), _age("A", 300, 60, snap=now)]
    assert aged_cliff_alerts(known, "amazon", today=now) == []                 # named last week, no worse
    grew = [_age("A", 300, 60, snap=before), _age("A", 400, 60, snap=now)]   # 208 -> 308 units
    assert len(aged_cliff_alerts(grew, "amazon", today=now)) == 1
    new = [_age("A", 300, 600, snap=before), _age("A", 300, 60, snap=now)]   # was clearing, now is not
    assert len(aged_cliff_alerts(new, "amazon", today=now)) == 1


def test_compute_alerts_carries_the_cliff_when_the_age_rows_are_passed():
    fresh = compute_alerts([], [], [], [], inventory_health=[_age("SLOW", 300, 60, snap=date.today())])
    assert [a["module"] for a in fresh] == ["inventory"] and "reach 181 days" in fresh[0]["message"]
    assert compute_alerts([], [], [], []) == []
