import numpy as np

from hubricon_engine.models import anomaly


def _step(n=16, at=8, shift=3.0, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.normal(10.0, 1.0, size=n)
    y[at:] += shift
    return y


def test_cusum_finds_a_planted_step_and_stays_quiet_on_noise():
    out = anomaly.cusum(_step())
    assert out["status"] == "ok" and out["flagged"] and out["direction"] == "up"
    assert abs(out["start_index"] - 8) <= 2   # the run may begin a point or two early on noise
    # CUSUM dates the run conservatively, so its shift estimate is diluted by
    # pre-shift points; the change-point test below is the precise estimator
    assert 0 < out["shift_estimate"] <= 3.6
    # two-sided CUSUM at h=4, k=0.5 has a known ~10% false-alarm rate on 16
    # points of pure noise (the materiality floor on dollars does the rest)
    alarms = sum(anomaly.cusum(np.random.default_rng(seed).normal(10.0, 1.0, size=16))["flagged"]
                 for seed in range(200))
    assert alarms / 200 < 0.15, f"false-alarm rate {alarms / 200:.0%} on white noise"


def test_changepoint_locates_the_shift_and_ignores_flat_noise():
    out = anomaly.changepoint(_step(shift=4.0))
    assert out["flagged"] and abs(out["index"] - 8) <= 1
    assert out["after_mean"] > out["before_mean"] and out["delta"] > 0
    flat = anomaly.changepoint(np.random.default_rng(3).normal(5.0, 0.5, size=16))
    assert not flat["flagged"]


def test_robust_z_flags_an_outlier_and_survives_zero_mad():
    y = np.array([10, 10.2, 9.8, 10.1, 9.9, 10.0, 10.1, 9.9, 16.0])
    out = anomaly.robust_z(y)
    assert out["flagged"] and out["direction"] == "up" and out["z"] > 3.5
    normal = anomaly.robust_z(np.array([10, 10.2, 9.8, 10.1, 9.9, 10.0, 10.1, 9.9, 10.05]))
    assert not normal["flagged"]
    constant = anomaly.robust_z(np.array([5.0] * 8 + [7.0]))
    assert constant["status"] == "ok" and constant["flagged"]
    assert anomaly.robust_z(np.array([1.0, 2.0]))["status"] == "insufficient_data"


def test_weekly_decompose_removes_weekday_pattern_and_spikes_catches_a_spike():
    rng = np.random.default_rng(1)
    n = 56
    weekday = np.array([0, 0.5, 1.0, 1.5, 2.0, -2.0, -3.0])
    y = 50 + np.tile(weekday, n // 7) * 4 + rng.normal(0, 0.5, size=n)
    dec = anomaly.weekly_decompose(y)
    assert np.std(dec["remainder"]) < np.std(y) / 3
    y[40] += 30
    dec = anomaly.weekly_decompose(y)
    sp = anomaly.spikes(dec["remainder"])
    assert sp["status"] == "ok" and 40 in sp["indices"]
    assert anomaly.weekly_decompose(y[:10])["status"] == "insufficient_data"


def _econ(sku, fees_per_unit, units=100):
    rows = []
    for i, fee in enumerate(fees_per_unit, start=1):
        rows.append({"sku": sku, "asin": "A1", "period_start": f"2026-{i:02d}-01", "period_end": f"2026-{i:02d}-28",
                     "units_sold": units, "avg_sales_price": 20.0, "sales": 20.0 * units,
                     "referral_fees": -3.0 * units, "fba_fulfillment_fees": -fee * units,
                     "storage_fees": -10.0, "other_fees": 0.0, "net_proceeds": 0.0})
    return rows


def test_run_flags_fee_creep_with_dollars_and_reports_thin_series_honestly():
    data = {"sku_economics": _econ("S1", [3.0] * 6 + [4.2] * 4) + _econ("S2", [3.0, 3.1, 3.0]),
            "asin_traffic": [], "ppc_spend": [], "ppc_search_terms": [], "settlement_transactions": []}
    rows = anomaly.run(data)
    flagged = [r for r in rows if r["flagged"] and r["item_id"] == "S1" and r["metric"] == "fba_fee_per_unit"]
    assert flagged, "planted FBA fee jump not flagged"
    r = flagged[0]
    assert r["direction"] == "up" and r["since"] == "2026-07-01"
    assert r["dollar_impact"] == 120.0          # $1.20 × 100 units per period
    assert "since 2026-07-01" in r["details"]["basis"]
    thin = [r for r in rows if r["item_id"] == "S2"]
    assert thin and all(r["status"] == "insufficient_data" for r in thin)
    s = anomaly.summarize(rows)
    assert s["flagged"] >= 2 and s["dollar_impact_total"] > 0 and s["top"][0]["item_id"] == "S1"


def test_run_on_empty_data_returns_nothing():
    assert anomaly.run({"sku_economics": [], "asin_traffic": [], "ppc_spend": []}) == []
