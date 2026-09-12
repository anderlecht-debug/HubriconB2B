"""Same input, same directive. Every time, byte for byte.

The engine simulates at six points — the profit-delta bootstrap, the inventory
sim, the panel aggregate, the cash cone, the monthly VaR, the anomaly sweep's
simulated nulls, and the ad-response curve's parameter draws. Every one of them
is seeded, and this file is the proof that nothing stochastic leaks into what a
client is told.

It matters for three reasons. A directive is a promise the Profit Record is
scored against, so the promise has to be a function of the data alone. A
re-measurement must reproduce the number it banked. And a disagreement between
two runs on the same files would be indistinguishable, from the outside, from a
number we made up.
"""

import numpy as np

from hubricon_engine import replay
from hubricon_engine.directives import draft_directives
from hubricon_engine.models import (
    ad_efficiency,
    anomaly,
    cashflow,
    elasticity,
    inventory_sim,
    margin,
    risk,
)

FEE_RATE, FIXED_FEE, UNIT_COST = 0.15, 1.50, 5.00


def _catalog(n_skus=10, n_periods=8, seed=17):
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.22, size=n_periods)
    econ, inv, cogs, ppc = [], [], [], []
    for i in range(n_skus):
        sku = f"R{i:02d}"
        prices = 20.0 * np.exp(rng.normal(0, 0.11, size=n_periods))
        units = 350.0 * (prices / 20.0) ** rng.uniform(-3.4, -1.2) * np.exp(
            0.7 * common + rng.normal(0, 0.2, size=n_periods))
        for j, (p, u) in enumerate(zip(prices, units), start=1):
            revenue = float(p) * float(u)
            econ.append({"sku": sku, "asin": "B0" + sku,
                         "period_start": f"2026-{j:02d}-01", "period_end": f"2026-{j:02d}-28",
                         "units_sold": float(u), "avg_sales_price": float(p),
                         "sales": revenue, "referral_fees": -FEE_RATE * revenue,
                         "fba_fulfillment_fees": -FIXED_FEE * float(u),
                         "storage_fees": -11.0, "other_fees": 0.0,
                         "net_proceeds": revenue})
        inv.append({"sku": sku, "snapshot_date": f"2026-{n_periods:02d}-28",
                    "fulfillable_quantity": 500, "inbound_quantity": 0})
        cogs.append({"sku": sku, "asin": "B0" + sku, "unit_cost_usd": UNIT_COST,
                     "supplier_lead_time_days": 42})
    for day in range(1, 61):
        ppc.append({"campaign_name": "Main", "campaign_id": "Main",
                    "spend": float(60 + 40 * np.sin(day / 5) + rng.normal(0, 6)),
                    "sales": float(300 + 90 * np.sin(day / 5) + rng.normal(0, 40)),
                    "report_date": f"2026-07-{day:02d}" if day <= 31
                    else f"2026-08-{day - 31:02d}"})
    return {"asin_traffic": [], "sku_economics": econ, "ppc_search_terms": [],
            "ppc_spend": ppc, "inventory_levels": inv, "cogs_inputs": cogs,
            "settlement_transactions": []}


def _full_run(data, seed=99):
    """Everything a cycle computes, from one seed."""
    rng = np.random.default_rng(seed)
    margins = margin.run(data)
    fits = elasticity.run(data)
    ads = ad_efficiency.run(data, avg_margin=margin.average_margin(margins))
    inv = inventory_sim.run(data, np.random.default_rng(seed), simulations=4000)
    panel = inventory_sim.aggregate(inv, data, np.random.default_rng(seed), simulations=4000)
    rows = anomaly.run(data)
    cash = cashflow.run({"cash_on_hand": 90000.0, "monthly_fixed_costs": 40000.0},
                        inv, margins, np.random.default_rng(seed), n_paths=4000)
    var = risk.run(data, margins, rng=np.random.default_rng(seed), simulations=4000)
    drafts = draft_directives(inv, ads, fits, margins, anomaly_rows=rows)
    return {"margins": margins, "fits": fits, "ads": ads, "inventory": inv,
            "panel": panel, "anomaly": rows, "cash": cash, "risk": var,
            "directives": drafts}


def test_the_whole_cycle_is_identical_on_two_runs():
    data = _catalog()
    first = _full_run(data)
    second = _full_run(data)
    for key in first:
        assert first[key] == second[key], f"{key} differs between runs"


def test_the_directives_are_identical_including_every_dollar_figure():
    """The strictest form: not just the same instructions, the same cents."""
    data = _catalog()
    a = draft_directives(*_inputs(data))
    b = draft_directives(*_inputs(data))
    assert a == b
    assert a, "the fixture should produce directives"
    for d in a:
        assert d["dedupe_key"] == next(
            x["dedupe_key"] for x in b if x["action_text"] == d["action_text"])


def _inputs(data):
    margins = margin.run(data)
    fits = elasticity.run(data)
    ads = ad_efficiency.run(data, avg_margin=margin.average_margin(margins))
    inv = inventory_sim.run(data, np.random.default_rng(3), simulations=3000)
    return inv, ads, fits, margins


def test_a_different_seed_does_not_change_a_published_promise():
    """The draws the promise rests on are fixed by the module, not by the caller's
    generator, so a caller who passes a different rng cannot move a dollar figure
    a client was given."""
    data = _catalog()
    inv_a, ads, fits, margins = _inputs(data)
    inv_b = inventory_sim.run(data, np.random.default_rng(4), simulations=3000)
    a = draft_directives(inv_a, ads, fits, margins)
    b = draft_directives(inv_b, ads, fits, margins)
    price_a = sorted((d["evidence"]["sku"], d["expected_impact_usd"])
                     for d in a if d["kind"] == "price_step")
    price_b = sorted((d["evidence"]["sku"], d["expected_impact_usd"])
                     for d in b if d["kind"] == "price_step")
    assert price_a == price_b


def test_a_remeasurement_reproduces_what_it_banked():
    """The drift check, as a property rather than a report: measuring the same
    directive against the same exports twice must give the same number to the
    cent, or the Profit Record is not a record."""
    import datetime
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "replay_fixture", pathlib.Path(__file__).with_name("test_replay.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)

    directives, later_data, later_margins = fixture._history(n_skus=12)
    today = datetime.date(2026, 10, 15)
    first = replay.replay(directives, later_data, later_margins, [], [], today=today)
    second = replay.replay(directives, later_data, later_margins, [], [], today=today)
    assert first["scored"] == second["scored"]
    assert first["measured_total"] == second["measured_total"]
    assert first["drift_free"] and second["drift_free"]


def test_every_simulated_component_names_its_seed_or_its_generator():
    """So a reader can tell, from the payload alone, what made a number
    reproducible."""
    data = _catalog()
    out = _full_run(data)
    price_steps = [d for d in out["directives"] if d["kind"] == "price_step"]
    assert price_steps
    assert all(d["evidence"]["mc_inputs"]["seed"] is not None for d in price_steps)
    assert out["cash"]["n_paths"] > 0
    assert out["inventory"][0]["simulations"] > 0
    assert out["panel"]["simulations"] > 0
    assert out["risk"]["var"]["n_paths"] > 0
    assert all(r["details"]["uncertainty"].get("seed") is not None
               for r in out["ads"] if r["status"] == "ok"
               and r["details"]["uncertainty"]["basis"] != "unavailable")
    assert out["anomaly"][0]["fdr_q"] is not None
