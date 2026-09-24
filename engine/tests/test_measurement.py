"""The measurement engine's job is to refuse credit it has not earned.

Most of these assert a ZERO or an "unmeasurable", because that is where a
ledger loses a client's trust: not by under-counting, but by claiming a win it
cannot prove from the client's own files.
"""
from datetime import date

from hubricon_engine import measurement as m

TODAY = date(2026, 9, 1)
SINCE = "2026-06-15T00:00:00+00:00"


def _d(kind, evidence, **kw):
    base = {"id": "d0000000-0000-0000-0000-000000000001", "kind": kind, "status": "approved",
            "measured_at": None, "responded_at": SINCE, "evidence": evidence,
            "expected_impact_usd": None}
    base.update(kw)
    return base


def _margin(sku, period, units, revenue, fees, cogs, ads=0.0, net=None):
    return {"sku": sku, "period_start": period, "period_end": period[:8] + "28",
            "units": units, "revenue": revenue, "amazon_fees": fees, "cogs": cogs,
            "ad_spend_allocated": ads,
            "net_margin": net if net is not None else revenue - fees - cogs - ads}


# ── price steps ──────────────────────────────────────────────────────────────

def test_a_price_step_that_was_never_executed_banks_nothing():
    """The largest class of false credit: recommended, approved, never made."""
    d = _d("price_step", {"sku": "W1", "p0": 10.0, "p_new": 10.5, "elasticity": -2.0},
           expected_impact_usd=500.0)
    margins = [_margin("W1", "2026-07-01", 100, 1000.0, 150.0, 400.0)]   # still $10.00
    out = m.measure_price_step(d, margins, [], date(2026, 6, 15), TODAY)
    # Not banked — but not closed either: a step approved and not yet made can
    # still be made next week, and closing it now would mean never measuring it.
    assert out["verdict"] == "not_yet"
    assert "has not been made" in out["measurement_notes"]
    assert out["measured_impact_usd"] is None

    # Once the trail is cold it closes honestly, rather than retrying forever.
    stale = m.measure_price_step(d, margins, [], date(2026, 1, 1), TODAY)
    assert stale["verdict"] == "closed"
    assert "never carried out" in stale["measurement_notes"]
    assert stale["measured_impact_usd"] is None


def test_a_wide_confidence_interval_costs_us_credit():
    """Uncertainty is expensive for us rather than for the client, and it is now
    expensive SMOOTHLY.

    This used to assert that two intervals both came back "measured" with the
    wider one lower. It is replaced by a strictly stronger claim over a whole
    sweep of widths: the banked figure falls monotonically as the interval widens,
    and it falls because the engine integrates its own posterior and banks the
    25th percentile — not because it takes the worse of two endpoints, which the
    replay harness showed books losses on moves that made money once the interval
    is honestly wide (engine/MATH_SCORECARD.md, iteration 2)."""
    ev = {"sku": "W1", "p0": 10.0, "p_new": 10.5, "elasticity": -0.5, "std_err": None}
    margins = [_margin("W1", "2026-07-01", 95, 997.5, 150.0, 380.0)]     # sold at $10.50
    banked = []
    for half in (0.05, 0.2, 0.6, 1.5):
        out = m.measure_price_step(
            _d("price_step", {**ev, "ci95": [-0.5 - half, -0.5 + half]}),
            margins, [], date(2026, 6, 15), TODAY)
        # below the materiality floor the directive closes rather than banking
        # noise, and the uncapped figure is still on the record
        uncapped = (out.get("evidence_after") or {}).get("uncapped")
        banked.append(out.get("measured_impact_usd") if uncapped is None else uncapped)
    assert all(b is not None for b in banked), banked
    assert banked == sorted(banked, reverse=True), banked
    assert banked[0] > banked[-1]

    # and the widest one is still a positive number, not a loss booked on a move
    # that earned money
    assert banked[-1] > 0


def test_a_price_step_is_capped_at_what_we_promised():
    d = _d("price_step", {"sku": "W1", "p0": 10.0, "p_new": 10.5, "elasticity": -0.5},
           expected_impact_usd=26.0)
    margins = [_margin("W1", "2026-07-01", 95, 997.5, 150.0, 380.0)]
    out = m.measure_price_step(d, margins, [], date(2026, 6, 15), TODAY)
    assert out["measured_impact_usd"] == 26.0
    assert "Capped at" in out["measurement_notes"]


def test_a_step_that_cost_the_buy_box_is_recorded_as_the_loss_it_was():
    d = _d("price_step", {"sku": "W1", "p0": 10.0, "p_new": 10.5, "elasticity": -0.5})
    margins = [_margin("W1", "2026-07-01", 40, 420.0, 63.0, 160.0)]
    traffic = [{"sku": "W1", "period_start": "2026-05-01", "buy_box_pct": 92.0},
               {"sku": "W1", "period_start": "2026-07-01", "buy_box_pct": 55.0}]
    out = m.measure_price_step(d, margins, traffic, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured"
    assert "cost the Featured Offer" in out["measurement_notes"]


# ── ad bleed ─────────────────────────────────────────────────────────────────

def _term(camp, term, spend, start="2026-07-01", end="2026-07-31", sales=0.0):
    return {"campaign_name": camp, "search_term": term, "spend": spend,
            "period_start": start, "period_end": end, "sales_7d": sales}


def test_bleed_saving_is_banked_when_the_campaign_stayed_alive():
    d = _d("ad_bleed_terms", {"terms": [{"campaign_name": "C1", "search_term": "waste", "spend": 300.0}],
                              "baseline_spend": 300.0,
                              "campaign_baseline_spend": {"C1": 1000.0}}, expected_impact_usd=300.0)
    after = [_term("C1", "waste", 0.0), _term("C1", "good", 700.0, sales=2000.0)]
    out = m.measure_ad_bleed(d, after, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured" and out["measured_impact_usd"] > 0
    assert out["attribution"] == "isolated"


def test_a_paused_campaign_banks_nothing_and_says_why():
    """If the whole campaign went dark, the saving was not the negative match."""
    d = _d("ad_bleed_terms", {"terms": [{"campaign_name": "C1", "search_term": "waste", "spend": 300.0}],
                              "baseline_spend": 300.0})
    after = [_term("C1", "waste", 0.0)]          # campaign spends nothing at all
    out = m.measure_ad_bleed(d, after, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "unmeasurable"
    assert "stopped spending entirely" in out["measurement_notes"]


def test_a_window_too_short_is_not_yet_rather_than_zero():
    d = _d("ad_bleed_terms", {"terms": [{"campaign_name": "C1", "search_term": "waste", "spend": 300.0}]})
    out = m.measure_ad_bleed(d, [], date(2026, 6, 15), TODAY)
    assert out["verdict"] == "not_yet" and out["measured_impact_usd"] is None


# ── fee anomalies ────────────────────────────────────────────────────────────

def _econ(sku, period, units, sales, referral, fba):
    return {"sku": sku, "period_start": period, "period_end": period[:8] + "28",
            "units_sold": units, "sales": sales, "referral_fees": referral,
            "fba_fulfillment_fees": fba, "storage_fees": 0.0, "other_fees": 0.0}


def test_a_recovered_fee_is_banked_at_the_after_periods_volume():
    d = _d("fee_anomaly", {"item_id": "W1", "metric": "fba_fee_per_unit",
                           "baseline": 3.0, "current": 5.0}, expected_impact_usd=400.0)
    econ = [_econ("W1", "2026-07-01", 200, 4000.0, 600.0, 600.0)]     # back to $3.00/unit
    out = m.measure_fee_anomaly(d, econ, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured"
    assert out["measured_impact_usd"] == 400.0                        # (5 − 3) × 200
    assert out["attribution"] == "isolated"


def test_a_catalog_wide_fee_drop_is_amazons_rate_card_not_our_fix():
    """The control group is free: it is the client's own other SKUs."""
    d = _d("fee_anomaly", {"item_id": "W1", "metric": "fba_fee_per_unit",
                           "baseline": 3.0, "current": 5.0})
    econ = []
    for sku in ("W1", "W2", "W3", "W4"):
        econ.append(_econ(sku, "2026-05-01", 100, 2000.0, 300.0, 500.0))   # $5.00/unit before
        econ.append(_econ(sku, "2026-07-01", 100, 2000.0, 300.0, 300.0))   # $3.00/unit after
    out = m.measure_fee_anomaly(d, econ, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "unmeasurable"
    assert "fee-schedule change" in out["measurement_notes"]


def test_a_fee_that_never_came_down_is_measured_as_zero_not_hidden():
    d = _d("fee_anomaly", {"item_id": "W1", "metric": "fba_fee_per_unit",
                           "baseline": 3.0, "current": 5.0})
    econ = [_econ("W1", "2026-07-01", 200, 4000.0, 600.0, 1100.0)]    # $5.50, still high
    out = m.measure_fee_anomaly(d, econ, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured" and out["measured_impact_usd"] == 0.0


# ── exits vs stockouts ───────────────────────────────────────────────────────

def test_a_stockout_is_never_banked_as_a_deliberate_exit():
    d = _d("negative_margin_sku", {"sku": "W1", "baseline_net": -900.0, "baseline_units": 30,
                                   "baseline_revenue": 3000.0, "baseline_ad_spend": 100.0})
    margins = [_margin("W1", "2026-07-01", 0, 0.0, 0.0, 0.0)]
    inventory = [{"sku": "W1", "on_hand_units": 400, "inbound_units": 0}]
    out = m.measure_negative_margin(d, margins, inventory, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "not_yet"
    assert "stockout" in out["measurement_notes"]
    assert out["measured_impact_usd"] is None


def test_a_real_exit_banks_the_loss_it_stopped():
    d = _d("negative_margin_sku", {"sku": "W1", "baseline_net": -900.0, "baseline_units": 30,
                                   "baseline_revenue": 3000.0, "baseline_ad_spend": 100.0})
    margins = [_margin("W1", "2026-07-01", 0, 0.0, 0.0, 0.0)]
    out = m.measure_negative_margin(d, margins, [], date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured" and out["measured_impact_usd"] == 900.0


# ── the guards ───────────────────────────────────────────────────────────────

def test_one_dollar_is_only_ever_banked_once():
    """A price step and a negative-margin instruction can both fire on one SKU
    and both read the same margin rows."""
    a = _d("price_step", {"sku": "W1", "p0": 10.0, "p_new": 10.5, "elasticity": -0.5},
           id="aaaaaaaa-0000-0000-0000-000000000001")
    b = _d("negative_margin_sku", {"sku": "W1", "baseline_net": -900.0, "baseline_units": 30,
                                   "baseline_revenue": 285.0, "baseline_ad_spend": 100.0},
           id="bbbbbbbb-0000-0000-0000-000000000002")
    margins = [_margin("W1", "2026-07-01", 95, 997.5, 150.0, 380.0)]
    out = m.measure([a, b], {"asin_traffic": [], "inventory_levels": []}, margins, [], [], today=TODAY)
    banked = [v for v in out if v["verdict"] == "measured"]
    assert len(banked) == 1
    dropped = next(v for v in out if v["verdict"] == "unmeasurable")
    assert "already banked on directive" in dropped["measurement_notes"]


def test_unbankable_kinds_close_with_the_work_recorded_and_no_dollars():
    for kind in ("inventory_reorder", "buybox_watch", "settlement_step", "traffic_watch"):
        out = m.measure([_d(kind, {"sku": "W1"})], {}, [], [], [], today=TODAY)
        assert out[0]["verdict"] == "closed"
        assert out[0]["measured_impact_usd"] is None


def test_immaterial_movements_close_rather_than_banking_noise():
    # a trim is banked over its window since 2026-09-24 (it was one day's net
    # before): half a dollar a day is $15 over thirty days, under the floor
    d = _d("campaign_trim", {"campaign_name": "C1", "current_spend": 1000.0, "avg_margin": 0.3})
    ads = [{"campaign_name": "C1", "current_spend": 999.5, "marginal_roas": 0.0}]
    out = m.measure_campaign_trim(d, ads, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "closed"


def test_a_branded_pause_is_allowed_to_come_out_negative():
    d = _d("branded_pause", {"brand_terms": ["acme"], "baseline_spend": 500.0,
                             "baseline_sales": 6000.0, "avg_margin": 0.4})
    after = [_term("C1", "acme widget", 50.0, sales=1000.0)]
    out = m.measure_branded_pause(d, after, [], date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured"
    # saved $450, but $2,000 of branded sales stopped arriving at a 40% margin.
    assert out["measured_impact_usd"] < 0
    assert "cost more than it saved" in out["measurement_notes"]


def test_recovery_banks_only_claims_we_filed():
    d = _d("recovery_filing", {"claim_keys": ["k1", "k2"]}, expected_impact_usd=800.0)
    claims = {
        "k1": {"claim_key": "k1", "status": "paid", "paid_amount": 600.0, "filed_at": "2026-07-01"},
        "k2": {"claim_key": "k2", "status": "paid", "paid_amount": 900.0},   # Amazon's own reconciliation
    }
    out = m.measure_recovery_filing(d, claims)
    assert out["attribution"] == "direct"
    # Face value above our expected-value estimate is fine for Tier A, but the
    # unfiled claim is not ours.
    assert out["measured_impact_usd"] == 600.0
    assert "$1,500.00" in out["measurement_notes"]


# ── fee bleed: Amazon's own published charges on the client's own units ──────

def _econ_row(sku, lilf=0.0, aged=0.0, peak=0.0):
    return {"sku": sku, "low_inventory_fee_month": lilf,
            "aged_surcharge_month": aged, "peak_storage_premium_month": peak}


def test_a_cleared_low_inventory_fee_is_banked_from_the_inventory_export():
    d = _d("low_inventory_fee", {"skus": ["W1", "W2"], "monthly_fee": 400.0,
                                 "per_sku": {"W1": 250.0, "W2": 150.0}},
           expected_impact_usd=400.0)
    after = {"rows": [_econ_row("W1"), _econ_row("W2")]}
    out = m.measure_fee_bleed(d, after, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured" and out["measured_impact_usd"] == 400.0
    assert out["attribution"] == "isolated"
    assert "gone entirely on W1, W2" in out["measurement_notes"]


def test_a_fee_still_being_billed_is_measured_as_zero():
    d = _d("aged_surcharge", {"skus": ["W1"], "monthly_surcharge": 300.0, "per_sku": {"W1": 300.0}})
    after = {"rows": [_econ_row("W1", aged=300.0)]}
    out = m.measure_fee_bleed(d, after, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "measured" and out["measured_impact_usd"] == 0.0
    assert "has not come off yet" in out["measurement_notes"]


def test_peak_premium_raised_inside_the_window_claims_nothing():
    """The money was already spent when we raised it; promising it back would
    be promising a refund we cannot get."""
    d = _d("peak_storage_premium", {"skus": ["W1"], "monthly_premium": 900.0,
                                    "already_in_peak": True})
    out = m.measure_fee_bleed(d, {"rows": [_econ_row("W1")]}, date(2026, 6, 15), TODAY)
    assert out["verdict"] == "closed" and out["measured_impact_usd"] is None


def test_a_directive_from_before_the_measurement_contract_is_left_alone():
    """The 57 directives already on file carry no kind and no evidence. There
    is nothing to measure them against, and closing them would silently retire
    work that is genuinely pending."""
    legacy = {"id": "old", "kind": None, "status": "approved", "measured_at": None,
              "responded_at": SINCE, "evidence": {}, "expected_impact_usd": 500.0}
    out = m.measure([legacy], {}, [], [], [], today=TODAY)
    assert out == []
