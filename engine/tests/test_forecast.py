import numpy as np
import pytest

from hubricon_engine.models import forecast
from hubricon_engine.models.forecast import (
    candidate_models, croston_tsb, holt_damped, naive, quantiles_from_errors, rate_moments,
    rolling_origin_backtest, seasonal_naive, select_model, ses, to_rates,
)


def _period(i: int) -> tuple[str, str]:
    year, month = 2025 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _econ_rows(units, sku="S1", asin="B0TEST", price=20.0):
    rows = []
    for i, u in enumerate(units, start=1):
        start, end = _period(i)
        rows.append({
            "sku": sku, "asin": asin, "period_start": start, "period_end": end,
            "units_sold": u, "avg_sales_price": price, "sales": price * u,
            "referral_fees": 0, "fba_fulfillment_fees": 0, "storage_fees": 0,
            "other_fees": 0, "net_proceeds": price * u,
        })
    return rows


def _traffic_rows(units, asin="B0X"):
    rows = []
    for i, u in enumerate(units, start=1):
        start, end = _period(i)
        rows.append({
            "child_asin": asin, "parent_asin": None, "period_start": start, "period_end": end,
            "units_ordered": u, "ordered_product_sales": 20.0 * u, "sessions": 500,
        })
    return rows


def _data(**overrides):
    base = {
        "asin_traffic": [], "sku_economics": [], "ppc_search_terms": [],
        "ppc_spend": [], "inventory_levels": [], "cogs_inputs": [],
    }
    base.update(overrides)
    return base


# ── models ────────────────────────────────────────────────────────────────

def test_ses_recovers_level_and_wins_on_flat_series():
    rng = np.random.default_rng(11)
    level = 10.0
    y = level + rng.normal(0, 0.5, size=30)
    fit = ses(y)
    assert fit["point"] == pytest.approx(level, abs=0.5)
    assert 0.05 <= fit["params"]["alpha"] <= 0.95
    name, bt = select_model(y)
    assert name in ("naive", "ses")  # nothing to extrapolate: the trend model must not win
    assert bt["candidates"]["ses"] < bt["candidates"]["naive"]  # smoothing beats copying noise
    assert bt["mase"] <= bt["candidates"]["naive"]


def test_holt_damped_beats_naive_on_clean_trend():
    slope = 0.5
    y = 10.0 + slope * np.arange(16)
    assert rolling_origin_backtest(y, holt_damped)["mase"] < rolling_origin_backtest(y, naive)["mase"]
    fit = holt_damped(y)
    assert fit["point"] > y[-1]  # continues the trend instead of flat-lining
    assert fit["point"] == pytest.approx(y[-1] + slope, abs=0.15)  # damping (phi <= 0.98) shaves a little
    assert select_model(y)[0] == "holt_damped"


def test_croston_tsb_selected_on_intermittent_series():
    # 60% zeros with sizes swinging 1..6: naive copies whatever size came last, TSB smooths it
    y = np.array([0, 0, 6, 0, 1, 0, 0, 5, 0, 2], dtype=float)
    assert float(np.mean(y == 0)) == pytest.approx(0.6)
    assert set(candidate_models(y)) == {"naive", "croston_tsb"}
    name, bt = select_model(y)
    assert name == "croston_tsb"
    assert bt["mase"] < bt["candidates"]["naive"]
    fit = croston_tsb(y)
    assert 0 < fit["point"] < y.max()
    assert fit["point"] == pytest.approx(y.mean(), abs=0.5)  # p*z lands near the long-run rate
    assert fit["params"]["alphas_fitted"] is True
    short = croston_tsb(y[:6])  # too short to fit the smoothing constants
    assert short["params"]["alphas_fitted"] is False
    assert (short["params"]["alpha_p"], short["params"]["alpha_z"]) == forecast.CROSTON_FIXED_ALPHAS


def test_seasonal_naive_only_offered_with_13_periods():
    rng = np.random.default_rng(2)
    y12, y13 = rng.uniform(1, 5, size=12), rng.uniform(1, 5, size=13)
    assert "seasonal_naive" not in candidate_models(y12)
    assert "seasonal_naive" in candidate_models(y13)
    assert "seasonal_naive" not in select_model(y12)[1]["candidates"]
    assert "seasonal_naive" in select_model(y13)[1]["candidates"]
    assert seasonal_naive(y13)["point"] == y13[-12]


def test_seasonal_naive_wins_on_seasonal_series():
    rng = np.random.default_rng(0)
    t = np.arange(26)
    y = 10 + 5 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 0.2, size=26)
    name, bt = select_model(y)
    assert name == "seasonal_naive"
    assert bt["mase"] < min(v for k, v in bt["candidates"].items() if k != "seasonal_naive")


# ── backtest, quantiles, fva ──────────────────────────────────────────────

def test_quantiles_monotone_and_clipped_at_zero():
    # linear-interpolated error quantiles: q10 = -2.2, q50 = 0, q90 = +2.2
    q = quantiles_from_errors(0.5, [-3.0, -1.0, 0.0, 1.0, 3.0])
    assert q["p10"] == 0.0  # 0.5 - 2.2 clipped at zero
    assert q["p10"] <= q["p25"] <= q["p50"] <= q["p75"] <= q["p90"]
    assert q["p50"] == pytest.approx(0.5)
    assert q["p90"] == pytest.approx(0.5 + 2.2)


def test_backtest_errors_are_one_step_and_out_of_sample():
    y = np.array([1.0, 2.0, 3.0, 4.0, 10.0, 6.0])
    bt = rolling_origin_backtest(y, naive, min_train=4)
    assert bt["origins"] == 2
    assert bt["errors"] == [10.0 - 4.0, 6.0 - 10.0]
    assert bt["wape"] == pytest.approx(10 / 16)
    # scale per origin = in-sample naive MAE of the training window: 1, then 9/4
    assert bt["mase"] == pytest.approx((6 / 1 + 4 / (9 / 4)) / 2)
    assert bt["pinball_p10"] >= 0 and bt["pinball_p90"] >= 0


def test_insufficient_data_below_four_periods():
    assert select_model(np.array([1.0, 2.0, 3.0])) == (None, {"status": "insufficient_data", "candidates": {}})
    row = forecast.run(_data(sku_economics=_econ_rows([300, 310, 290])))[0]
    assert row["status"] == "insufficient_data"
    assert row["method"] is None
    assert row["n_periods"] == 3
    assert not any(k.startswith(("daily_rate", "horizon_units", "mase", "fva")) for k in row)
    assert rate_moments(row) == (None, None)


def test_fva_is_zero_for_naive_winner_and_positive_when_beaten():
    # regime steps: copying the last period is the best anyone can do
    steps = forecast.run(_data(sku_economics=_econ_rows([280] * 6 + [560] * 6 + [840] * 6)))[0]
    assert steps["method"] == "naive"
    assert steps["fva_pct"] == 0.0
    assert steps["mase"] == steps["naive_mase"]

    trend = forecast.run(_data(sku_economics=_econ_rows([280 + 14 * i for i in range(16)])))[0]
    assert trend["method"] == "holt_damped"
    assert trend["fva_pct"] > 0
    assert trend["mase"] <= trend["naive_mase"]
    assert trend["details"]["candidates"]["naive"] == trend["naive_mase"]


def test_chosen_mase_never_exceeds_naive():
    rng = np.random.default_rng(5)
    for _ in range(10):
        y = np.clip(rng.normal(8, 3, size=int(rng.integers(4, 20))), 0, None)
        name, bt = select_model(y)
        if bt["mase"] is not None:
            assert bt["mase"] <= bt["candidates"]["naive"]


# ── censoring ─────────────────────────────────────────────────────────────

def _zero_snapshot(day: str) -> dict:
    return {"sku": "S1", "asin": "B0TEST", "snapshot_date": day, "fulfillable_quantity": 0, "inbound_quantity": 0}


def test_censored_periods_are_flagged_and_excluded():
    inv = [
        _zero_snapshot("2025-03-15"), _zero_snapshot("2025-06-10"),
        {"sku": "S1", "asin": "B0TEST", "snapshot_date": "2025-07-10", "fulfillable_quantity": 40, "inbound_quantity": 0},
    ]
    row = forecast.run(_data(sku_economics=_econ_rows([300] * 8), inventory_levels=inv))[0]
    assert row["status"] == "ok"
    assert [s["censored"] for s in row["details"]["series"]] == [False, False, True, False, False, True, False, False]
    assert row["n_periods"] == 8 and row["n_used"] == 6
    assert row["details"]["censored_periods"] == 2
    assert row["details"]["censoring_ignored"] is False


def test_censoring_ignored_when_too_few_clean_periods():
    inv = [_zero_snapshot("2025-02-15"), _zero_snapshot("2025-04-10")]
    row = forecast.run(_data(sku_economics=_econ_rows([300] * 5), inventory_levels=inv))[0]
    assert row["status"] == "ok"
    assert row["n_periods"] == 5 and row["n_used"] == 5  # 3 clean < 4 -> fit on everything
    assert row["details"]["censored_periods"] == 2
    assert row["details"]["censoring_ignored"] is True


# ── run() ─────────────────────────────────────────────────────────────────

def test_run_row_shape():
    assert forecast.run(_data()) == []
    rng = np.random.default_rng(4)
    units = [int(v) for v in rng.normal(300, 15, size=12)]
    row = forecast.run(_data(sku_economics=_econ_rows(units)))[0]
    assert row["level"] == "sku" and row["item_id"] == "S1" and row["status"] == "ok"
    expected = {
        "level", "item_id", "status", "method", "n_periods", "n_used",
        "daily_rate_point", "daily_rate_p10", "daily_rate_p25", "daily_rate_p50",
        "daily_rate_p75", "daily_rate_p90", "horizon_days", "horizon_units_point",
        "horizon_units_p10", "horizon_units_p90", "mase", "wape", "pinball_p10",
        "pinball_p90", "naive_mase", "fva_pct", "intermittent", "details",
    }
    assert expected <= set(row)
    assert {"params", "series", "backtest_origins", "candidates", "error_sd", "basis"} <= set(row["details"])
    assert row["method"] in row["details"]["candidates"]
    assert row["details"]["backtest_origins"] == 12 - 4
    assert (row["daily_rate_p10"] <= row["daily_rate_p25"] <= row["daily_rate_p50"]
            <= row["daily_rate_p75"] <= row["daily_rate_p90"])
    assert row["horizon_days"] == 30
    assert row["horizon_units_point"] == pytest.approx(row["daily_rate_point"] * 30, abs=0.1)
    assert row["horizon_units_p90"] == pytest.approx(row["daily_rate_p90"] * 30, abs=0.1)
    assert "30 days" in row["details"]["basis"]
    assert row["intermittent"] is False
    assert len(row["details"]["series"]) == 12
    assert row["details"]["series"][0]["period_start"] == "2025-01-01"
    mean, sd = rate_moments(row)
    assert mean == row["daily_rate_point"] and sd == row["details"]["error_sd"]


def test_run_flags_intermittent_series():
    units = [0, 0, 168, 0, 28, 0, 0, 140, 0, 56]  # 28-day months -> rates 0, 0, 6, 0, 1, ...
    row = forecast.run(_data(sku_economics=_econ_rows(units)))[0]
    assert row["intermittent"] is True
    assert row["method"] == "croston_tsb"
    assert row["daily_rate_point"] > 0


def test_run_respects_horizon_days():
    row = forecast.run(_data(sku_economics=_econ_rows([280] * 6)), horizon_days=45)[0]
    assert row["horizon_days"] == 45
    assert row["horizon_units_point"] == pytest.approx(row["daily_rate_point"] * 45, abs=0.1)


def test_asin_fallback_for_uncovered_asins():
    traffic = _traffic_rows([100 + 10 * i for i in range(8)], asin="B0X")
    rows = forecast.run(_data(asin_traffic=traffic))
    assert [(r["level"], r["item_id"], r["status"]) for r in rows] == [("asin", "B0X", "ok")]
    # once a SKU with economics bridges to that ASIN, the ASIN row is dropped (no double counting)
    rows = forecast.run(_data(asin_traffic=traffic, sku_economics=_econ_rows([300] * 6, asin="B0X")))
    assert [(r["level"], r["item_id"]) for r in rows] == [("sku", "S1")]


def test_rate_moments_falls_back_to_band_width():
    row = {"status": "ok", "daily_rate_point": 10.0, "daily_rate_p10": 7.437, "daily_rate_p90": 12.563,
           "details": {"error_sd": None}}
    mean, sd = rate_moments(row)
    assert mean == 10.0
    assert sd == pytest.approx((12.563 - 7.437) / 2.563)


def test_to_rates_handles_uneven_periods():
    rows = [
        {"period_start": "2026-02-01", "period_end": "2026-02-28", "units_sold": 280},   # 28 days
        {"period_start": "2026-01-01", "period_end": "2026-01-31", "units_sold": 310},   # 31 days
        {"period_start": "2026-03-01", "period_end": "2026-03-31", "units_sold": None},  # skipped
    ]
    assert to_rates(rows, "units_sold") == [("2026-01-01", pytest.approx(10.0)), ("2026-02-01", pytest.approx(10.0))]
