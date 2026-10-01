"""The headline number with a range, and the client against the book."""

from datetime import date

import numpy as np
import pytest

from fakedb import FakeDB

from hubricon_engine import narrate, value
from hubricon_engine.models import benchmark

CLIENT = {"id": "c1", "company_name": "Acme", "monthly_fee_usd": 6000.0, "free_months": 0,
          "retainer_started_at": "2026-06-01T00:00:00+00:00"}


def _step(i, usd, p5, p95, attribution="attributable"):
    return {"id": f"d{i}", "kind": "price_step", "status": "done", "measured_impact_usd": usd, "attribution": attribution,
            "expected_impact_usd": usd * 1.2, "executed_at": "2026-07-01T00:00:00+00:00",
            "evidence": {"sku": f"S{i}", "after": {"measured_distribution": {"p5": p5, "p95": p95}}}}


def test_the_headline_carries_a_band_when_most_of_the_dollars_have_one():
    ds = [_step(1, 400.0, 100.0, 900.0), _step(2, 300.0, 50.0, 700.0),
          {"id": "r", "kind": "recovery_filing", "status": "done", "measured_impact_usd": 200.0, "attribution": "direct",
           "expected_impact_usd": 150.0, "executed_at": "2026-07-01T00:00:00+00:00", "evidence": {}}]
    ledger = value.compute(CLIENT, ds, [], [], today=date(2026, 9, 1))
    assert ledger["value_total"] == 900.0
    assert ledger["value_p5"] == pytest.approx(150.0 + 200.0) and ledger["value_p95"] == pytest.approx(1600.0 + 200.0)
    assert ledger["value_interval_basis"]["banded_share_of_measured"] == pytest.approx(700 / 900, abs=1e-4)
    line = value.record_line(ledger)
    assert "(range $350–$1,800)" in line
    facts = narrate.build_facts("Acme", "Ann", None, [], [], 900.0, 3, 1, value=ledger)
    assert facts["value_range"]["value"] == "$350 to $1,800"
    # recoveries only: a point, and the basis says no dollar carried a band
    only = value.compute(CLIENT, [ds[2]], [], [], today=date(2026, 9, 1))
    assert only["value_p5"] == only["value_p95"] == only["value_total"]
    assert only["value_interval_basis"]["banded_share_of_measured"] == 0.0
    assert "(range" not in value.record_line(only)
    assert "value_range" not in narrate.build_facts("Acme", "Ann", None, [], [], 200.0, 1, 1, value=only)


def _ratios(seed):
    rng = np.random.default_rng(seed)
    return {"tacos": float(rng.uniform(0.05, 0.35)), "net_margin_pct": float(rng.uniform(0.02, 0.25)),
            "stockout_share": float(rng.uniform(0.0, 0.5)), "fee_bleed_share": float(rng.uniform(0.0, 0.05)),
            "realisation_ratio": float(rng.uniform(0.3, 1.3))}


def test_the_book_places_a_client_and_refuses_below_ten_clients():
    book = {f"c{i}": _ratios(i) for i in range(12)}
    mine = {"tacos": 0.08, "net_margin_pct": 0.22, "stockout_share": 0.45, "fee_bleed_share": 0.01}
    out = benchmark.compare(book, mine)
    assert out["status"] == "ok" and out["n_clients"] == 12
    t = out["ratios"]["tacos"]
    assert t["percentile"] == pytest.approx(np.mean([v["tacos"] <= 0.08 for v in book.values()]), abs=1e-4)
    assert t["percentile_p5"] <= t["percentile"] <= t["percentile_p95"]
    assert "better than" in t["reading"]                                 # a low TACoS is good
    assert "worse than" in out["ratios"]["stockout_share"]["reading"]    # a high stockout share is not
    assert out["ratios"]["realisation_ratio"]["status"] == "insufficient_data"
    short = benchmark.compare({f"c{i}": _ratios(i) for i in range(9)}, mine)
    assert short["status"] == "insufficient_clients" and "1 more" in short["basis"]


def test_ratios_come_from_a_clients_own_results_and_the_book_reads_only_consenting_clients():
    margins = [{"sku": "A", "period_start": "2026-08-01", "period_end": "2026-08-28", "units": 100, "revenue": 4000.0,
                "amazon_fees": 600.0, "cogs": 1000.0, "ad_spend_allocated": 400.0, "net_margin": 2000.0}]
    inv = [{"sku": "A", "stockout_probability": 0.4}, {"sku": "B", "stockout_probability": 0.1}]
    inv_econ = {"summary": {"bleed": {"total_month": 120.0}}}
    r = benchmark.ratios_for(margins, inv, inv_econ, [])
    assert r["tacos"] == pytest.approx(0.1) and r["net_margin_pct"] == pytest.approx(0.5)
    assert r["stockout_share"] == 0.5 and r["fee_bleed_share"] == pytest.approx(120.0 / (4000.0 * 30 / 28))
    db = FakeDB(consents=[{"client_id": "c1", "kind": "calibration"}], clients=[{"id": "c1", "status": "active"}],
                model_runs=[{"id": "r1", "client_id": "c1", "status": "succeeded", "started_at": "2026-08-01"}],
                margin_results=[{**margins[0], "run_id": "r1"}], inventory_sim_results=[{**i, "run_id": "r1"} for i in inv],
                model_outputs=[{"run_id": "r1", "model": "invecon", "payload": inv_econ}], directives=[])
    out = benchmark.run(db, "c1", date(2026, 9, 1))
    assert out["status"] == "insufficient_clients" and out["client_ratios"]["tacos"] == 0.1
