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
