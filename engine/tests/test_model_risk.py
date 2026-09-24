"""Model risk, measured: the changes the three-world harness of 2026-09-24 forced.

Four findings, each with the test that pins its fix:

  1. A seller who reprices off last month's demand biases the static fit
     toward zero (§2 of MATH_METHODS.md, +0.5 at phi 0.4, rho 0.6). Controlling
     for last period's price and demand removes it; the catalogue pays for the
     control once, as a trimmed mean of the per-SKU difference, and the
     correction stays silent on a catalogue that does not react.
  2. A common season read as a response to price inflates every standard
     error and, in the cross-price fit, hands the identification gate noise.
     The catalogue index is divided out before the fit.
  3. A family cross-elasticity two standard errors from nothing was fed into a
     step's sibling term. Unidentified families are published and not used.
  4. A margin row carrying an itemised split without its dollar totals was read
     as fee-free, and a counterfactual at the old price then charged no referral
     fee. The reader rebuilds the totals from the rate and the per-unit fee.

Plus the loss gate the harness priced: off by default, and when set, a step
whose 25th percentile is a loss is refused and says which gate bound it.
"""

import numpy as np
import pytest

from hubricon_engine import measurement
from hubricon_engine.models import cross_price, elasticity, pricing_engine, seasonality
from hubricon_engine.models.pricing_engine import price_move

from test_cross_price import _family
from test_endogeneity import _reactive_catalog
from test_robust_step import INTERIOR, INTERIOR_EPS, fit, sku


def _errors(rows, truth):
    return np.array([r["elasticity"] - truth[r["item_id"]] for r in rows if r["level"] == "sku" and r["status"] == "ok"])


# ── 1. the reaction bias, removed once per catalogue ─────────────────────────

def test_controlling_for_last_periods_demand_removes_the_reaction_bias():
    """phi 0.4, rho 0.6, twelve periods, eighty SKUs: the static fit reads +0.4
    to +0.6 too flat; the controlled fit is within ±0.15 of the truth; the
    corrected catalogue within ±0.2. Six seeds, so a lucky one cannot carry it."""
    raw, ctl, fixed = [], [], []
    for seed in range(6):
        data, truth = _reactive_catalog(seed, 0.4, 0.6, n_skus=80, n_periods=12)
        rows0 = elasticity.run(data, correct_reaction=False)
        rows1 = elasticity.run(data)
        raw.append(float(np.median(_errors(rows0, truth))))
        fixed.append(float(np.median(_errors(rows1, truth))))
        ctl.append(float(np.median([r["details"]["epsilon_controlled"] - truth[r["item_id"]]
                                    for r in rows1 if r["details"].get("epsilon_controlled") is not None])))
        en = rows1[0]["details"]["endogeneity"]
        assert en["applied"] is True and en["phi"] > 0 and en["t_phi"] >= elasticity.REACTION_T
        assert en["bias_hat"] > 0 and en["bias_se"] > 0
        for r in rows1:
            if r["level"] == "sku" and r["status"] == "ok":
                # the correction is one number for the catalogue, and the interval widens by its error
                assert r["details"]["epsilon_uncorrected"] - r["elasticity"] == pytest.approx(en["bias_hat"], abs=1e-3)
                assert r["std_err"] >= r["details"]["std_err_uncorrected"]
    assert np.median(raw) > 0.3, raw
    assert abs(np.median(ctl)) < 0.15, ctl
    assert abs(np.median(fixed)) < 0.2, fixed
    assert np.median(fixed) < np.median(raw) - 0.25


def test_the_correction_stays_silent_on_a_catalogue_that_does_not_react():
    fired = 0
    for seed in range(6):
        data, truth = _reactive_catalog(seed, 0.0, 0.6, n_skus=80, n_periods=12)
        rows = elasticity.run(data)
        en = rows[0]["details"]["endogeneity"]
        fired += en["applied"]
        if not en["applied"]:
            assert "no significant reaction" in en["reason"] or "do not differ" in en["reason"]
            assert all("epsilon_uncorrected" not in r["details"] for r in rows)
    assert fired <= 1


def test_the_controlled_fit_refuses_a_short_series_and_an_experiment_is_never_corrected():
    short = [{"price": 20.0 * (1 + 0.05 * (i % 3)), "units": 100.0 - 3 * i, "days": 28} for i in range(6)]
    assert elasticity._fit_controlled(short)["status"] == "insufficient_data"
    data, truth = _reactive_catalog(0, 0.4, 0.6, n_skus=80, n_periods=12)
    exp = {"level": "sku", "item_id": "S000", "status": "ok", "elasticity": -2.5, "std_err": 0.2,
           "details": {"ci95": [-2.9, -2.1], "dof": 4, "t_critical": 2.776}}
    rows = elasticity.run(data, experiments=[exp])
    row = next(r for r in rows if r["item_id"] == "S000")
    assert row["details"]["source"] == "experiment" and row["elasticity"] == -2.5
    assert "epsilon_uncorrected" not in row["details"]


# ── 2. the season divided out before the fit ─────────────────────────────────

def _seasonal_catalogue(seed, n_skus=60, peak=1.6):
    rng = np.random.default_rng(seed)
    econ, truth = [], {}
    for i in range(n_skus):
        s = f"K{i:03d}"
        eps = float(rng.uniform(-3.0, -1.4))
        truth[s] = eps
        for k in range(1, 13):
            y, m = 2025 + (k + 7) // 12, (k + 7) % 12 + 1   # 2025-09 .. 2026-08
            p = 30.0 * np.exp(rng.normal(0, 0.06))
            sea = peak if m in (10, 11, 12) else 1.0
            u = 200.0 * (p / 30.0) ** eps * sea * np.exp(rng.normal(0, 0.15))
            econ.append({"sku": s, "asin": "B0" + s, "period_start": f"{y}-{m:02d}-01", "period_end": f"{y}-{m:02d}-28",
                         "units_sold": float(u), "avg_sales_price": float(p), "sales": float(u * p),
                         "referral_fees": -0.15 * u * p, "fba_fulfillment_fees": -3.0 * u, "storage_fees": 0.0, "other_fees": 0.0})
    return {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [], "ppc_spend": [],
            "inventory_levels": [], "cogs_inputs": []}, truth


def test_the_catalogue_index_divided_out_tightens_the_fit_and_leaves_the_flat_case_alone():
    """Four catalogues with a 1.4× fourth quarter, pooled: the standard error
    falls by a fifth or more and the fit stays centred. Pooled, because one
    60-SKU catalogue's median error moves ±0.2 between seeds either way."""
    se_plain, se_adj, err_plain, err_adj = [], [], [], []
    for seed in range(4):
        data, truth = _seasonal_catalogue(seed)
        seas = seasonality.indices(data)
        assert seas["status"] == "ok"
        plain = elasticity.run(data)
        adjusted = elasticity.run(data, seasonal=seas)
        se_plain += [r["std_err"] for r in plain if r["status"] == "ok"]
        se_adj += [r["std_err"] for r in adjusted if r["status"] == "ok"]
        err_plain += list(_errors(plain, truth))
        err_adj += list(_errors(adjusted, truth))
        assert adjusted[0]["details"]["seasonal_adjustment"]["deseasonalised"] is True
        assert plain[0]["details"]["seasonal_adjustment"]["deseasonalised"] is False
    assert np.median(se_adj) < 0.8 * np.median(se_plain), (np.median(se_adj), np.median(se_plain))
    assert abs(np.median(err_adj)) < 0.12, np.median(err_adj)
    assert np.median(np.abs(err_adj)) <= np.median(np.abs(err_plain))
    # no index on file: the rows are the input, untouched
    same, note = seasonality.deseasonalise_economics(data, None)
    assert same is data and note["deseasonalised"] is False
    same, note = seasonality.deseasonalise_economics(data, {"status": "insufficient_history"})
    assert same is data


# ── 3. a cross term is used only when identified ─────────────────────────────

def test_an_unidentified_family_is_published_and_kept_out_of_the_steps():
    out = cross_price.run(_family(0, eps_cross=0.0, noise=0.3))
    f = out["families"][0]
    assert f["status"] == "ok" and f["identified"] is False and f["t_cross"] is not None
    assert out["by_sku"] == {} and out["n_identified"] == 0 and out["n_fitted"] == 1
    strong = cross_price.run(_family(2, eps_cross=0.8, price_cv=0.15, noise=0.05))
    g = strong["families"][0]
    assert g["identified"] is True and abs(g["t_cross"]) >= cross_price.MIN_CROSS_T
    assert set(strong["by_sku"]) == set(g["children"])


# ── 4. the fee split without its totals ──────────────────────────────────────

def test_an_itemised_split_without_totals_is_rebuilt_from_the_rate_and_the_unit_fee():
    row = {"units": 100.0, "revenue": 2000.0, "amazon_fees": 0.15 * 2000.0 + 3.3 * 100.0,
           "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 3.3}}
    prop, fixed = measurement._split_fees(row)
    assert prop == pytest.approx(300.0) and fixed == pytest.approx(330.0)
    # totals on file win; a blended line stays proportional; an overstated rebuild is capped at what was paid
    full = {**row, "fee_split": {**row["fee_split"], "proportional_fees": 290.0, "fixed_fees": 340.0}}
    assert measurement._split_fees(full) == (290.0, 340.0)
    assert measurement._split_fees({"amazon_fees": 500.0}) == (500.0, 0.0)
    over = {**row, "amazon_fees": 400.0}
    p, f = measurement._split_fees(over)
    assert p + f == pytest.approx(400.0) and p / f == pytest.approx(300.0 / 330.0)


# ── the loss gate, priced and off ────────────────────────────────────────────

def test_the_loss_gate_is_off_by_default_and_refuses_a_coin_flip_when_set(monkeypatch):
    assert pricing_engine.MAX_P_LOSS is None
    base = price_move(sku(**INTERIOR), fit(INTERIOR_EPS, se=0.20))
    assert base is not None and base["policy"]["gain_gate_bound"] is False and base["policy"]["max_p_loss"] is None
    monkeypatch.setattr(pricing_engine, "MAX_P_LOSS", 0.25)
    gated = price_move(sku(**INTERIOR), fit(INTERIOR_EPS, se=0.20))
    # the same SKU either stands still with the gate named, or moves with at most a one-in-four chance of loss
    if gated is None:
        return
    assert gated["policy"]["max_p_loss"] == 0.25
    if gated["policy"]["gain_gate_bound"]:
        assert gated["step_fraction"] == 0.0
    else:
        assert gated["p_loss"] <= 0.25 + 1e-6


# ── the pooled volume response, and the ceiling that no longer books the weather ──

def _batch(n, realised_of, sd=0.15):
    """n price steps of −5% on ε = −2.4 SKUs, a baseline month of 100 units at $20
    and an after month whose units are `realised_of(expected_ratio)`."""
    from datetime import date
    directives, margins = [], []
    for i in range(n):
        sku = f"V{i:02d}"
        p0, p1, eps = 20.0, 19.0, -2.4
        expected = (p1 / p0) ** eps
        units_after = 100.0 * realised_of(expected)
        directives.append({"id": f"v{i}", "kind": "price_step", "status": "approved", "issued_at": "2026-08-20T00:00:00+00:00",
                           "evidence": {"sku": sku, "p0": p0, "p_new": p1, "elasticity": eps, "std_err": 0.3,
                                        "baseline_units": 100.0, "baseline_period": "2026-08-01",
                                        "mc_inputs": {"demand_sd_log": sd, "eps_dof": 6}}})
        # equal-length periods: the regression compares DAILY rates, as the fit does
        for start, end, units, price in (("2026-08-01", "2026-08-28", 100.0, p0), ("2026-09-01", "2026-09-28", units_after, p1)):
            margins.append({"sku": sku, "period_start": start, "period_end": end, "units": units, "revenue": units * price,
                            "amazon_fees": 0.15 * units * price + 3.0 * units, "cogs": 8.0 * units,
                            "fee_split": {"basis": "itemized", "proportional_rate": 0.15, "fixed_per_unit": 3.0,
                                          "proportional_fees": 0.15 * units * price, "fixed_fees": 3.0 * units}})
    return directives, margins


def test_the_batch_pins_its_own_volume_response():
    from datetime import date
    since = lambda d: date(2026, 8, 20)
    exact = measurement.volume_realisation(*_batch(12, lambda e: e), since)
    assert exact["estimated"] and exact["kappa"] == pytest.approx(1.0, abs=1e-3) and exact["se"] <= 0.02
    assert exact["applied"] is False          # as the fits said: nothing to apply
    none = measurement.volume_realisation(*_batch(12, lambda e: 1.0), since)
    assert none["applied"] and none["kappa"] == pytest.approx(0.0, abs=1e-3)
    half = measurement.volume_realisation(*_batch(12, lambda e: 1 + 0.5 * (e - 1)), since)
    assert 0.4 < half["kappa"] < 0.6 and half["applied"]
    few = measurement.volume_realisation(*_batch(5, lambda e: e), since)
    assert few["estimated"] is False and few["applied"] is False and few["kappa"] == 1.0 and few["n_steps"] == 5
    # noise in the after month widens κ's error instead of moving its centre,
    # and a κ within its own noise of 1 leaves every counterfactual on its own fit
    rng = np.random.default_rng(3)
    noisy = measurement.volume_realisation(*_batch(40, lambda e: e * float(np.exp(rng.normal(0, 0.15)))), since)
    assert noisy["estimated"] and abs(noisy["kappa"] - 1.0) < 0.35 and noisy["se"] > 0.05
    assert noisy["applied"] == (abs(noisy["kappa"] - 1.0) >= measurement.REALISATION_T * noisy["se"])


def test_a_bad_month_is_not_booked_against_the_step_and_a_collapse_still_is():
    """The ceiling allows the SKU its own month-to-month noise: a profit that fell
    by half a noise sd leaves the anchored reading standing; a profit that fell by
    three sds holds the reading at zero; nothing is ever banked below zero by the
    ceiling alone."""
    d, obs, sd = 300.0, -100.0, 400.0
    kept, note = measurement._cap_at_observed(d, obs, "this SKU's own profit", noise_sd=sd)
    assert kept == d and note == ""
    held, note = measurement._cap_at_observed(d, -1300.0, "this SKU's own profit", noise_sd=sd)
    assert held == 0.0 and "held at $0.00" in note
    capped, note = measurement._cap_at_observed(d, 50.0, "this SKU's own profit", noise_sd=None)
    assert capped == 50.0 and "capped at the $50.00" in note
    zero, note = measurement._cap_at_observed(d, -100.0, "this SKU's own profit", noise_sd=None)
    assert zero == 0.0
    loss, note = measurement._cap_at_observed(-200.0, -900.0, "this SKU's own profit", noise_sd=sd)
    assert loss == -200.0 and note == ""
