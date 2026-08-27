"""Briefing console: renders the four instruments honestly from run data."""

from datetime import date

from hubricon_engine.console import build_console

TODAY = date(2026, 8, 27)


def _cash(min_p5=5_000.0):
    rising = [min_p5 + 40 * i for i in range(90)]
    return {
        "n_paths": 10000, "horizon_days": 90,
        "p_ruin": 0.0 if min_p5 >= 0 else 0.31,
        "min_p5": min_p5, "min_p5_day": 13, "min_median": min_p5 + 2_000,
        "starting_cash": 10_000.0, "monthly_fixed_costs": 3_000.0,
        "details": {
            "p5": rising, "p50": [v + 3_000 for v in rising], "p95": [v + 7_000 for v in rising],
            "wires": [{"day": 10, "sku": "SKU-A", "amount": 3_600.0}],
            "payout_days": list(range(14, 91, 14)), "payout_cycle_days": 14,
            "skus_modeled": 2, "assumptions": ["settlement phase assumed"],
        },
    }


def _directives():
    return [
        {"status": "done", "action_text": "Move SKU-A $30.00 → $28.50", "measured_impact_usd": 2105},
        {"status": "done", "action_text": "Negative-match 11 terms", "measured_impact_usd": 92},
        {"status": "done", "action_text": "Pause branded exact-match", "measured_impact_usd": 780},
        {"status": "issued", "action_text": "Wire $3,600 by Sep 26", "measured_impact_usd": None},
    ]


def _margins():
    return [{"sku": "SKU-A", "period_start": "2026-07-01", "period_end": "2026-07-30",
             "units": 300, "revenue": 9_000.0, "amazon_fees": 2_700.0, "cogs": 1_800.0,
             "ad_spend_allocated": 450.0}]


def _fits():
    return [{"status": "ok", "level": "sku", "item_id": "SKU-A", "elasticity": -1.8,
             "details": {"ci95": [-2.2, -1.4]}}]


def _inventory():
    return [{"sku": "SKU-A", "stockout_probability": 0.62, "days_of_cover": 8.0},
            {"sku": "SKU-B", "stockout_probability": 0.05, "days_of_cover": 70.0}]


def _build(**overrides):
    kwargs = dict(company="Dry & Run Co", directives=_directives(), cash=_cash(),
                  margins=_margins(), elasticity_rows=_fits(),
                  inventory_rows=_inventory(), generated_on=TODAY)
    kwargs.update(overrides)
    return build_console(**kwargs)


def test_ledger_totals_and_escaping():
    html = _build()
    assert html.startswith("<!doctype html>")
    assert "Dry &amp; Run Co" in html
    assert "$2,977" in html          # 2105 + 92 + 780, measured only
    assert "3 executed directive(s)" in html
    assert "1 on the desk" in html


def test_cash_chip_flips_with_the_5th_percentile():
    assert "above zero" in _build()                       # calm state
    breach = _build(cash=_cash(min_p5=-1_200.0))
    assert "bridge capital" in breach                     # breach state
    assert "$0 — bridge-capital line" in breach           # ruin line drawn


def test_cash_empty_state_when_inputs_missing():
    html = _build(cash=None)
    assert "Not armed yet" in html
    assert "hubricon cash" in html


def test_profit_curve_shows_capped_step_toward_optimum():
    html = _build()
    # eps -1.8 puts P* below the 5%-cap window: label the honest next step
    assert "next step (5% cap)" in html
    assert "ε = -1.80" in html


def test_risk_scatter_pulses_only_real_danger():
    html = _build()
    assert html.count('class="ping"') == 1               # SKU-A only
    assert "SKU-A — 62% stockout risk" in html
    assert "SKU-B — 5% stockout risk" in html            # tooltip, no label/pulse
