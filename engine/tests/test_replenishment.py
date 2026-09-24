"""The purchase order as a supplier writes it: MOQ, case pack, price break,
one wire per supplier, and air against sea."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from hubricon_engine import directives
from hubricon_engine.ingest import cogs
from hubricon_engine.models import replenishment as rep
from hubricon_engine.models.replenishment import expedite, joint_orders, price_break, round_to_terms

TODAY = date(2026, 9, 1)
LADDER = [[0.5, 100.0], [0.6, 106.0], [0.7, 113.0], [0.75, 117.0], [0.8, 121.0], [0.85, 126.0],
          [0.9, 133.0], [0.925, 137.0], [0.95, 142.0], [0.975, 150.0], [0.99, 160.0], [0.995, 166.0]]


def _demand(n=4000, seed=1):
    return np.random.default_rng(seed).normal(100.0, 20.0, n).clip(0)


def test_moq_and_case_pack_round_up_and_the_forced_units_cost_their_overage():
    d = _demand()
    t = round_to_terms(112, {"moq_units": 150, "case_pack_units": 24}, c_o=1.2, demand=d)
    assert t["q"] == 168 and t["forced_units"] == 56 and t["moq"] == 150
    assert t["moq_cost"] > 0
    none = round_to_terms(112, {"moq_units": 100, "case_pack_units": 4}, c_o=1.2, demand=d)
    assert none["q"] == 112 and none["moq_cost"] == 0.0


def test_a_price_break_that_pays_and_one_that_does_not():
    d = _demand()
    pays = price_break(120, 5.0, {"price_break_qty": 200, "price_break_unit_cost_usd": 4.0}, c_o=0.5, demand=d,
                       cycle_days=52)
    assert pays and pays["take"] and pays["net"] > 0 and pays["net_p5"] <= pays["net"] <= pays["net_p95"]
    assert pays["wire_at_break"] == pytest.approx(800.0)
    tiny = price_break(120, 5.0, {"price_break_qty": 600, "price_break_unit_cost_usd": 4.95}, c_o=1.5, demand=d,
                       cycle_days=52)
    assert tiny and not tiny["take"] and tiny["net"] < 0
    assert price_break(120, 5.0, {"price_break_qty": 100, "price_break_unit_cost_usd": 4.0}, 0.5, d, 52) is None


def _econ(sku, rate=3.0, position=200, rop=160, qty=180, up_to=380, margin=9.0, lead=45, sd=0.4):
    return {"sku": sku, "status": "ok", "rate_mean": rate, "rate_sd": sd, "position": position, "reorder_point": rop,
            "order_qty_econ": qty, "order_up_to": up_to, "unit_margin": margin, "lead_time_days": lead,
            "unit_cost": 5.0, "c_o": 0.6, "wire_econ": qty * 5.0, "size_tier": "standard",
            "details": {"demand_ladder": LADDER}}


def test_the_joint_order_fires_siblings_inside_the_can_order_band():
    a = _econ("A", position=170, rop=160, qty=180)     # due in ~3 days
    b = _econ("B", position=185, rop=160, qty=180)     # due in ~8 days: joins A's wire (review period 7)... just outside
    c = _econ("C", position=400, rop=160, qty=180)     # due in 80 days: its own clock
    j = joint_orders("Shenzhen", [a, b, c], horizon_days=180)
    assert j["wire_events_independent"] > j["wire_events_joint"]
    assert j["wire_events_saved"] >= 1
    first = j["events"][0]
    assert "A" in first["skus"]


def test_air_beats_sea_when_the_sea_lead_time_exposes_the_position():
    rng = np.random.default_rng(3)
    exposed = _econ("A", rate=4.0, position=120, lead=60)           # 240 expected by sea, 48 by air
    terms = {"inbound_freight_per_unit_usd": 0.6, "air_freight_per_unit_usd": 1.4, "air_lead_time_days": 12}
    ex = expedite(exposed, terms, rng)
    assert ex["status"] == "ok" and ex["recommend_air"]
    assert ex["p_stockout_sea"] > ex["p_stockout_air"] and ex["net_p50"] > 0 and ex["p_positive"] >= rep.EXPEDITE_MIN_P
    assert ex["freight_premium"] == pytest.approx(0.8 * 180)
    covered = _econ("B", rate=1.0, position=400, lead=45)
    no = expedite(covered, terms, np.random.default_rng(3))
    assert no["status"] == "ok" and not no["recommend_air"] and no["net_p50"] < 0
    assert expedite(exposed, {"inbound_freight_per_unit_usd": 0.6}, rng)["status"] == "no_freight_options"


def test_blank_terms_refuse_and_the_reader_maps_the_new_columns():
    inv_econ = {"rows": [_econ("A"), _econ("B")]}
    data = {"cogs_inputs": [{"sku": "A", "supplier": "S", "moq_units": 240, "case_pack_units": 24,
                             "inbound_freight_per_unit_usd": 0.6, "air_freight_per_unit_usd": 1.4, "air_lead_time_days": 12},
                            {"sku": "B"}]}
    out = rep.run(inv_econ, data, np.random.default_rng(1), TODAY)
    by = {r["sku"]: r for r in out["rows"]}
    assert by["A"]["status"] == "ok" and by["A"]["order_qty"] == 240 and by["A"]["terms"]["forced_units"] == 60
    assert by["B"]["status"] == "no_supplier_terms" and by["B"]["order_qty"] == 180
    assert by["B"]["expedite"]["status"] == "no_freight_options"
    assert out["seed"] == rep.REPLENISH_SEED
    df = pd.DataFrame([{"sku": "X", "unit_cost_usd": "4.20", "supplier_lead_time_days": "45", "Supplier": "Acme",
                        "MOQ": "500", "Case pack": "50", "Price break qty": "2000", "Price break unit cost usd": "3.90",
                        "Air freight per unit usd": "2.10", "Air lead time days": "12"}])
    table, rows, _ = cogs.parse(df, {"client_id": "c", "id": "u"})
    assert table == "cogs_inputs" and rows[0]["supplier"] == "Acme" and rows[0]["moq_units"] == 500
    assert rows[0]["price_break_unit_cost_usd"] == 3.9 and rows[0]["air_lead_time_days"] == 12
    # the shipped template parses with its example row dropped
    tdf = pd.read_csv("../cogs-template.csv")
    assert cogs.parse(tdf, {"client_id": "c", "id": "u"})[1] == []


def test_the_reorder_directive_carries_the_terms_and_the_expedite_is_unbankable():
    inv = [{"sku": "A", "stockout_probability": 0.6, "reorder_qty": 180, "reorder_point": 160, "lead_time_days": 45,
            "daily_velocity_mean": 3.0, "on_hand_units": 120, "inbound_units": 0}]
    margins = [{"sku": "A", "period_start": "2026-08-01", "units": 90, "revenue": 2700.0, "amazon_fees": 810.0,
                "cogs": 450.0, "net_margin": 1340.0}]
    econ_row = {**_econ("A"), "critical_fractile": 0.95, "wire_econ": 900.0}
    rep_out = {"rows": [{"sku": "A", "supplier": "S", "status": "ok", "order_qty": 240, "wire": 1200.0,
                         "terms": {"q_star": 180, "q": 240, "forced_units": 60, "moq_cost": 30.0},
                         "price_break": None,
                         "expedite": {"status": "ok", "recommend_air": True, "net_p5": 50.0, "net_p50": 400.0, "net_p95": 900.0,
                                      "p_positive": 0.8, "freight_premium": 144.0, "stockout_units_sea": 40.0,
                                      "stockout_units_air": 5.0, "p_stockout_sea": 0.7, "p_stockout_air": 0.1,
                                      "sea_lead_days": 45, "air_lead_days": 12, "order_qty": 240, "mc_inputs": {}}}],
               "suppliers": [{"supplier": "S", "wire_events_saved": 2, "horizon_days": 180,
                              "events": [{"day": 3.0, "skus": ["A", "B"]}]}]}
    drafts = directives.draft_directives(inv, [], [], margins, inv_econ={"rows": [econ_row]}, replenishment=rep_out)
    reorder = next(d for d in drafts if d["kind"] == "inventory_reorder")
    assert "Wire $1,200" in reorder["action_text"] and "240 units of A" in reorder["action_text"]
    assert "Rounded up from 180" in reorder["action_text"] and "Order it with B from S" in reorder["action_text"]
    assert reorder["evidence"]["joint_order"]["wire_events_saved"] == 2
    air = next(d for d in drafts if d["kind"] == "expedite_air")
    assert air["mandate"] == "explicit" and air["expected_impact_usd"] is None
    assert "by air (12 days) rather than sea (45 days)" in air["action_text"] and "not banked" in air["action_text"]
    from hubricon_engine.measurement import UNBANKABLE_KINDS
    assert "expedite_air" in UNBANKABLE_KINDS
