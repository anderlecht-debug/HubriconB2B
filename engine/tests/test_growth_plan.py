from datetime import date

import pytest

from hubricon_engine.growth_plan import next_quarter, pace, propose_plan

MARGINS = [
    {"sku": "A", "period_start": "2026-06-01", "revenue": 9000.0, "net_margin": 1800.0},
    {"sku": "A", "period_start": "2026-07-01", "revenue": 10000.0, "net_margin": 2000.0},
    {"sku": "B", "period_start": "2026-07-01", "revenue": 5000.0, "net_margin": 500.0},
]
DIRECTIVES = [
    {"module": "pricing", "expected_impact_usd": 300.0},
    {"module": "pricing", "expected_impact_usd": None},
    {"module": "advertising", "expected_impact_usd": 500.0},
    {"module": "inventory", "expected_impact_usd": None},
]


def test_propose_plan_baseline_targets_and_clustering():
    p = propose_plan(MARGINS, DIRECTIVES, today=date(2026, 8, 27))
    assert p["label"] == "Q3 2026"
    assert p["baseline"] == {"net": 2500.0, "revenue": 15000.0, "margin_pct": pytest.approx(0.1667, abs=1e-4)}
    assert p["opportunity"] == 800.0
    assert p["targets"]["net"] == 2500.0 + 0.7 * 800.0        # the stated 30% haircut
    assert p["targets"]["revenue"] == 15000.0                  # hold revenue while margin repairs
    modules = [i["module"] for i in p["initiatives"]]
    assert modules == ["pricing", "advertising", "inventory"]  # fixed order, margin absent (no steps)
    pricing = p["initiatives"][0]
    assert pricing["steps"] == 2 and pricing["expected_impact_usd"] == 300.0
    assert "optimum" in pricing["title"]


def test_propose_plan_requires_margin_data():
    assert propose_plan([], DIRECTIVES) is None


def test_next_quarter_window_is_90_days():
    label, start, end = next_quarter(date(2026, 11, 15))
    assert label == "Q4 2026"
    assert (end - start).days == 90


def test_pace_math():
    # halfway through, target +1000 over baseline: need +500 covered
    assert pace(current=2600, baseline=2000, target=3000, elapsed_fraction=0.5) == "on_pace"
    assert pace(current=2400, baseline=2000, target=3000, elapsed_fraction=0.5) == "behind"
    assert pace(current=2000, baseline=2000, target=2000, elapsed_fraction=0.9) == "on_pace"
    assert pace(current=5000, baseline=2000, target=3000, elapsed_fraction=1.2) == "on_pace"
