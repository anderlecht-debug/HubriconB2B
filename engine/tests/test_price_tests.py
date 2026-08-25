import pytest

from hubricon_engine.price_tests import (
    buybox_warning,
    latest_elasticity,
    predict_units_change,
    resolve_baseline,
)

ECON = [
    {"sku": "A", "period_start": "2026-06-01", "avg_sales_price": 19.99, "sales": None, "units_sold": None},
    {"sku": "A", "period_start": "2026-07-01", "avg_sales_price": 21.99, "sales": None, "units_sold": None},
    {"sku": "B", "period_start": "2026-07-01", "avg_sales_price": None, "sales": 1500.0, "units_sold": 50},
]


def test_baseline_is_latest_observed_price():
    assert resolve_baseline(ECON, "A") == 21.99          # latest period wins
    assert resolve_baseline(ECON, "B") == 30.0           # falls back to sales/units
    assert resolve_baseline(ECON, "MISSING") is None


def test_predicted_units_change_follows_the_curve():
    # inelastic: +10% price at e=-0.5 loses ~4.7% of units
    assert predict_units_change(-0.5, 20.0, 22.0) == pytest.approx(-0.0465, abs=1e-3)
    # elastic: same move at e=-2 loses ~17.4%
    assert predict_units_change(-2.0, 20.0, 22.0) == pytest.approx(-0.1736, abs=1e-3)
    assert predict_units_change(-1.0, 20.0, 20.0) == 0.0


def test_buybox_warning_thresholds():
    assert buybox_warning(92.0, 88.0) is None            # normal wobble
    warning = buybox_warning(92.0, 70.0)                 # suppression signature
    assert warning and "suppressing" in warning
    assert buybox_warning(None, 70.0) is None            # can't judge without a baseline


def test_latest_elasticity_picks_ok_sku_fit():
    rows = [
        {"level": "asin", "item_id": "A", "status": "ok", "elasticity": -1.0},
        {"level": "sku", "item_id": "A", "status": "insufficient_data"},
        {"level": "sku", "item_id": "A", "status": "ok", "elasticity": -1.4},
    ]
    assert latest_elasticity(rows, "A")["elasticity"] == -1.4
    assert latest_elasticity(rows, "B") is None
