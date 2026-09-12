"""The harness above the measurement pass: were the promises calibrated?

measurement.py answers "did this move earn what we said" one directive at a time.
This answers the question that only exists over many of them — is the dollar
figure the engine attaches to a directive an honest forecast, or does it
systematically over-promise — and it answers it by replay, against the client's
own later exports, with no model in the loop.

No real client history exists in this repository, so these tests build one. The
harness is the deliverable; the numbers it reports on a real client arrive when
that client's second export does, and until then it reports pending rather than a
ratio computed on nothing.
"""

import numpy as np
import pytest

from hubricon_engine import replay
from hubricon_engine.directives import draft_directives
from hubricon_engine.models import elasticity, margin
from hubricon_engine.models.pricing_engine import price_move

FEE_RATE, FIXED_FEE, UNIT_COST, BASE = 0.15, 1.50, 5.00, 20.0


def _period(i: int, length: int = 28) -> tuple[str, str]:
    """(start, end) for the i-th period, 1-indexed, rolling into the next year.

    Fixtures used to write f"2026-{i:02d}-01" directly, which produces month 13
    past a year of history. Nothing caught it until elasticity._fit began reading
    period_end to normalise units by period length (2026-09-12) — a real export
    never has a thirteenth month."""
    year, month = 2026 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{length:02d}"


def _econ_rows(sku, prices, units, start_month=1):
    rows = []
    for i, (p, u) in enumerate(zip(prices, units), start=start_month):
        revenue = float(p) * float(u)
        rows.append({
            "sku": sku, "asin": "B0" + sku,
            "period_start": _period(i)[0], "period_end": _period(i)[1],
            "units_sold": float(u), "avg_sales_price": float(p), "sales": revenue,
            "referral_fees": -FEE_RATE * revenue,
            "fba_fulfillment_fees": -FIXED_FEE * float(u),
            "storage_fees": 0.0, "other_fees": 0.0, "net_proceeds": revenue,
        })
    return rows


def _data(econ, cogs_skus):
    return {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": [], "inventory_levels": [],
            "cogs_inputs": [{"sku": s, "asin": "B0" + s, "unit_cost_usd": UNIT_COST,
                             "supplier_lead_time_days": 40} for s in cogs_skus],
            "settlement_transactions": []}


def _history(n_skus=14, n_periods=8, seed=21, eps_true=-2.4, realisation=1.0):
    """A seller's first eight periods, the directives the engine drafted from
    them, and then a ninth period in which the steps were actually taken.

    `realisation` scales how much of the modelled volume response actually
    happened, so the harness can be tested against an engine that is right, one
    that over-promises, and one that under-promises."""
    rng = np.random.default_rng(seed)
    econ, truth = [], {}
    for i in range(n_skus):
        sku = f"H{i:02d}"
        prices = BASE * np.exp(rng.normal(0, 0.11, size=n_periods))
        units = 400.0 * (prices / BASE) ** eps_true * np.exp(rng.normal(0, 0.15, size=n_periods))
        econ += _econ_rows(sku, prices, units)
        truth[sku] = {"eps": eps_true, "p0": float(prices[-1]), "q0": float(units[-1])}

    skus = list(truth)
    data = _data(econ, skus)
    margins = margin.run(data)
    fits = elasticity.run(data)
    drafts = [d for d in draft_directives([], [], fits, margins)
              if d["kind"] == "price_step" and d["expected_impact_usd"] is not None]

    # the ninth period: the price moved, and demand responded by `realisation`
    # times what the fitted curve said it would
    after = []
    for d in drafts:
        ev = d["evidence"]
        t = truth[ev["sku"]]
        modelled = (ev["p_new"] / t["p0"]) ** t["eps"]
        actual = 1.0 + realisation * (modelled - 1.0)
        units = t["q0"] * actual
        after += _econ_rows(ev["sku"], [ev["p_new"]], [units], start_month=n_periods + 1)

    directives = [
        {**d, "id": f"id-{i}", "status": "approved",
         "issued_at": f"2026-{n_periods:02d}-20T00:00:00+00:00",
         "approved_at": f"2026-{n_periods:02d}-21T00:00:00+00:00",
         "measured_at": None, "measured_impact_usd": None,
         "channel": "amazon"}
        for i, d in enumerate(drafts)
    ]
    later_data = _data(econ + after, skus)
    later_margins = margin.run(later_data)
    return directives, later_data, later_margins


# ── promise integrity: can the blob be rebuilt? ───────────────────────────

def test_every_price_step_carries_what_a_rebuild_needs():
    """Layer 3's promise-integrity check. A directive that cannot be rebuilt
    cannot be scored, so this is a property of the draft, not of the replay."""
    directives, _, _ = _history()
    assert directives
    for d in directives:
        check = replay.completeness(d)
        assert check["checked"] is True
        assert check["complete"] is True, check["missing"]


def test_a_price_step_carries_the_distribution_not_just_two_endpoints():
    """The promise is a distribution now, and the blob must carry it — otherwise
    measurement scores the promise against a range it did not make."""
    directives, _, _ = _history()
    for d in directives:
        check = replay.completeness(d)
        assert check["distribution_complete"] is True, check["distribution_missing"]
        assert check["promise_matches_distribution"] is True
        ev = d["evidence"]
        assert ev["delta_p5"] <= ev["delta_p50"] <= ev["delta_p95"]
        assert d["expected_impact_usd"] == ev["delta_p50"]
        # and the simulation's own inputs, so the draws can be reproduced exactly
        assert ev["mc_inputs"]["seed"] is not None
        assert ev["mc_inputs"]["draws"] > 0


def test_a_stripped_blob_is_caught_rather_than_scored():
    directives, _, _ = _history()
    broken = {**directives[0],
              "evidence": {k: v for k, v in directives[0]["evidence"].items()
                           if k not in ("ci95", "delta_p95")}}
    check = replay.completeness(broken)
    assert check["complete"] is False and "ci95" in check["missing"]
    assert check["distribution_complete"] is False
    assert "delta_p95" in check["distribution_missing"]


def test_a_kind_nothing_is_banked_on_is_not_audited_as_a_failure():
    check = replay.completeness({"kind": "conversion_watch", "evidence": {}})
    assert check["checked"] is False
    assert "nothing is banked" in check["reason"]


# ── the harness, end to end ───────────────────────────────────────────────

def test_replay_measures_the_history_and_scores_the_promises():
    directives, later_data, later_margins = _history(realisation=1.0)
    card = replay.replay(directives, later_data, later_margins, [], [],
                         today=__import__("datetime").date(2026, 10, 15))
    assert card["n_directives"] == len(directives)
    assert card["n_scored"] >= 1
    assert card["evidence_audit"]["incomplete"] == 0
    assert card["drift_free"] is True
    assert "realisation" in replay.render(card) or card["status"] == "pending"


def test_an_engine_that_delivers_what_it_promised_is_reported_as_calibrated():
    """The calibration check the harness exists for. Demand responds exactly as
    the fitted curve said.

    The measured total lands BELOW the promise and that is correct, not a failure:
    the Record banks the 25th percentile of the fitted range and caps each claim
    at what the SKU's profit actually rose. The target band is 0.30–1.30, and the
    note on the scorecard says so in those words so nobody reads 0.58 as a
    shortfall."""
    directives, later_data, later_margins = _history(n_skus=24, realisation=1.0)
    card = replay.replay(directives, later_data, later_margins, [], [],
                         today=__import__("datetime").date(2026, 10, 15))
    assert card["status"] == "ok"
    assert card["calibrated"] is True
    assert card["over_promising"] is False
    assert replay.MIN_REALISATION <= card["realisation_ratio"] <= replay.MAX_REALISATION
    assert card["band_coverage"] >= replay.MIN_BAND_COVERAGE
    assert "A correct engine books less than it promises" in card["note"]


def test_the_harness_tracks_how_much_of_the_forecast_actually_happened():
    """The property that makes it a backtest rather than a formatter: the ratio
    has to move with reality. Four worlds, from demand responding half again as
    much as forecast to not responding at all."""
    today = __import__("datetime").date(2026, 10, 15)
    ratios = []
    for realisation in (1.5, 1.0, 0.5, 0.0):
        directives, data, margins = _history(n_skus=24, realisation=realisation)
        card = replay.replay(directives, data, margins, [], [], today=today)
        ratios.append(card["realisation_ratio"])
    assert ratios == sorted(ratios, reverse=True), ratios
    assert ratios[0] > 0.5
    assert ratios[-1] < 0          # no volume response at all: a price cut lost money


def test_an_engine_that_over_promises_is_caught_and_named():
    """Demand responds at a third of the forecast. The harness must say
    OVER-PROMISING rather than averaging it away."""
    directives, data, margins = _history(n_skus=24, realisation=0.3)
    card = replay.replay(directives, data, margins, [], [],
                         today=__import__("datetime").date(2026, 10, 15))
    assert card["status"] == "ok"
    assert card["over_promising"] is True
    assert card["calibrated"] is False
    assert "OVER-PROMISING" in card["note"]


def test_a_move_with_no_volume_response_is_booked_as_the_loss_it_was():
    """The regression the harness caught, pinned. Before the fix, a price cut that
    produced no volume response at all was booked as a GAIN, because the model
    counterfactual said the seller would have sold 12% less at the old price. The
    claim is now capped at what the SKU's profit actually did."""
    directives, data, margins = _history(n_skus=24, realisation=0.0)
    card = replay.replay(directives, data, margins, [], [],
                         today=__import__("datetime").date(2026, 10, 15))
    assert card["measured_total"] < 0
    losses = [s for s in card["scored"] if s["measured"] < 0]
    assert len(losses) > len(card["scored"]) / 2


# ── pending is an answer ──────────────────────────────────────────────────

def test_no_history_reports_pending_and_not_a_ratio():
    card = replay.score([])
    assert card["status"] == "pending"
    assert card["calibrated"] is None
    assert card["realisation_ratio"] is None
    assert str(replay.MIN_SCORED_FOR_CALIBRATION) in card["note"]
    assert "does not report a ratio" in card["note"]


def test_too_little_history_reports_pending_and_still_shows_what_exists():
    """A client with three measured moves sees their three. They do not see a
    calibration claim computed on three."""
    directives = [{"kind": "price_step", "dedupe_key": f"k{i}",
                   "expected_impact_usd": 100.0, "measured_impact_usd": 80.0,
                   "evidence": {"delta_p5": 10.0, "delta_p95": 200.0,
                                "sku": "A", "p0": 20.0, "p_new": 19.0,
                                "elasticity": -2.0, "ci95": [-2.4, -1.6],
                                "baseline_units": 100, "baseline_revenue": 2000.0,
                                "baseline_period": "2026-07-01"}}
                  for i in range(3)]
    card = replay.score(directives)
    assert card["status"] == "pending"
    assert card["n_scored"] == 3
    assert card["measured_total"] == 240.0        # what exists is still reported
    assert card["band_coverage"] == 1.0


def test_drift_between_a_banked_measurement_and_a_replay_is_reported():
    """The one thing a Profit Record cannot do is change a number it already
    banked. If the measurement code moves under a banked promise, replay says so."""
    directives, later_data, later_margins = _history()
    banked = [{**d, "measured_impact_usd": 999_999.0} for d in directives]
    card = replay.replay(banked, later_data, later_margins, [], [],
                         today=__import__("datetime").date(2026, 10, 15))
    assert card["drift_free"] is False
    assert card["drift"]
    assert "DRIFT" in replay.render(card)


def test_the_render_is_readable_without_the_payload():
    card = replay.score([])
    text = replay.render(card)
    assert "Replay:" in text and "pending" in text
    assert "evidence rebuildable" in text
