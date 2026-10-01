"""Which SKUs to cut or merge, on a loaded contribution the survival curve has
discounted, with a credibility weight on how much is the SKU's own history."""

from datetime import date

import numpy as np
import pytest

from hubricon_engine import directives, measurement, replay
from hubricon_engine.models import assortment, risk

TODAY = date(2026, 9, 1)


def _period(i):
    year, month = 2025 + (i - 1) // 12, (i - 1) % 12 + 1
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-28"


def _margins(sku, nets, revenue=3000.0, cogs=900.0, start=1):
    rows = []
    for k, net in enumerate(nets):
        s, e = _period(start + k)
        rows.append({"sku": sku, "period_start": s, "period_end": e, "units": 100, "revenue": revenue,
                     "amazon_fees": 600.0, "cogs": cogs, "ad_spend_allocated": 100.0, "net_margin": net})
    return rows


def _catalog():
    margins = []
    rng = np.random.default_rng(1)
    for i in range(10):                       # ten healthy SKUs over eight periods
        margins += _margins(f"OK{i}", list(rng.normal(800, 60, 8)))
    margins += _margins("LOSER", [-300, -250, -320, -280, -310, -290, -330, -300])   # loses every month
    margins += _margins("ONEBAD", [700, 650, 720, 690, 710, 680, 700, -900])          # one bad month
    margins += _margins("DYING", [600, 500, 400, 0, 0, 0, 0, 0])                        # dead: no units lately
    for m in margins:
        if m["sku"] == "DYING" and m["net_margin"] == 0:
            m["units"] = 0
    return margins


def test_a_persistent_loser_is_cut_and_one_bad_month_is_not():
    margins = _catalog()
    risk_out = risk.run({"sku_economics": [], "fba_returns": []}, margins, None, [], None, np.random.default_rng(1), 200)
    out = assortment.run(margins, None, {}, risk_out, None, TODAY)
    by = {r["sku"]: r for r in out["rows"]}
    assert by["LOSER"]["decision"] == "cut"
    assert by["LOSER"]["credibility_z"] >= 0.5 and by["LOSER"]["negative_periods"] == 8 and by["LOSER"]["p_negative"] >= 0.75
    assert by["LOSER"]["avoided_loss_12m"]["p50"] > 0
    assert by["ONEBAD"]["decision"] == "keep" and by["ONEBAD"]["negative_periods"] == 1
    assert by["OK0"]["decision"] == "keep"
    assert out["summary"]["cut"] == ["LOSER"] and out["seed"] == assortment.ASSORTMENT_SEED


def test_survival_conditioning_lowers_the_value_of_an_old_sku_on_a_dying_catalogue():
    margins = _catalog()
    # a catalogue where many SKUs die young
    for i in range(6):
        rows = _margins(f"DEAD{i}", [500, 400, 0, 0, 0, 0, 0, 0])
        for m in rows:
            if m["net_margin"] == 0:
                m["units"] = 0
        margins += rows
    margins += _margins("YOUNG", [800.0, 820.0], start=7)     # two periods old, on a catalogue that dies at two or three
    risk_out = risk.run({"sku_economics": [], "fba_returns": []}, margins, None, [], None, np.random.default_rng(1), 200)
    assert risk_out["survival"]["status"] == "ok"
    with_curve = assortment.run(margins, None, {}, risk_out, None, TODAY)
    flat = assortment.run(margins, None, {}, None, None, TODAY)
    young_c, young_f = ({r["sku"]: r for r in o["rows"]}["YOUNG"] for o in (with_curve, flat))
    assert young_c["value_12m"]["p50"] < young_f["value_12m"]["p50"]
    assert young_c["survival_basis"].startswith("Kaplan") and all(0 <= f <= 1 for f in young_c["survival_12m"])
    # a SKU as old as the catalogue: the curve has no information beyond the
    # longest observed life, so its conditional survival is one and its value
    # is the flat one — the estimator says nothing it has not seen
    old_c, old_f = ({r["sku"]: r for r in o["rows"]}["OK0"] for o in (with_curve, flat))
    assert old_c["value_12m"]["p50"] == pytest.approx(old_f["value_12m"]["p50"], rel=1e-6)


def test_the_loaded_contribution_subtracts_carry_returns_and_a_stated_operational_cost():
    margins = _margins("X", [800.0, 800.0])
    inv_econ = {"rows": [{"sku": "X", "aged_surcharge_month": 120.0, "low_inventory_fee_month": 30.0}]}
    returns = [{"sku": "X", "return_date": _period(1)[0], "quantity": 5, "detailed_disposition": "DAMAGED"},
               {"sku": "X", "return_date": _period(1)[0], "quantity": 10, "detailed_disposition": "SELLABLE"}]
    series = assortment.loaded_contribution(margins, inv_econ, returns)["X"]
    first = series[0]
    scale = 28 / 30
    assert first["carry"] == pytest.approx(150.0 * scale, abs=0.01)
    assert first["returns"] == pytest.approx(5 * 1.0 * 9.0 + 10 * 0.2 * 9.0)     # landed $9 a unit
    assert first["loaded"] == pytest.approx(800 - 150 * scale - 63.0, abs=0.01)
    stated = assortment.loaded_contribution(margins, inv_econ, returns, operational_cost_month=200.0)["X"][0]
    assert stated["operational"] == pytest.approx(200.0 * scale, abs=0.01)


def test_a_small_losing_variant_is_a_merge_candidate():
    margins = _margins("BIG", [900.0] * 6, revenue=20000.0) + _margins("TINY", [-20.0] * 6, revenue=400.0)
    families = {"by_sku": {"BIG": {"family": "F", "siblings": [{"sku": "TINY", "weight": 1.0}]},
                           "TINY": {"family": "F", "siblings": [{"sku": "BIG", "weight": 1.0}]}}}
    out = assortment.run(margins, None, {}, None, families, TODAY)
    by = {r["sku"]: r for r in out["rows"]}
    assert by["TINY"]["decision"] in ("merge", "cut") and by["TINY"]["family_revenue_share"] < 0.05
    assert by["BIG"]["decision"] == "keep"


def test_the_exit_directive_supersedes_the_negative_margin_draft_and_banks_per_period_gone():
    margins = _catalog()
    risk_out = risk.run({"sku_economics": [], "fba_returns": []}, margins, None, [], None, np.random.default_rng(1), 200)
    out = assortment.run(margins, None, {}, risk_out, None, TODAY)
    drafts = directives.draft_directives([], [], [], margins, assortment=out)
    kinds = [(d["kind"], d["evidence"].get("sku")) for d in drafts]
    assert ("sku_exit", "LOSER") in kinds and ("negative_margin_sku", "LOSER") not in kinds
    d = next(x for x in drafts if x["kind"] == "sku_exit")
    assert d["mandate"] == "explicit" and d["expected_impact_usd"] == d["evidence"]["delta_p50"] > 0
    assert "Plan the exit of LOSER" in d["action_text"] and "loss avoided over twelve months" in d["action_text"]
    assert replay.completeness(d)["complete"] and replay.completeness(d)["distribution_complete"]
    d = {**d, "id": "x1", "status": "approved", "issued_at": "2026-08-31T00:00:00+00:00"}
    gone = [{"sku": "LOSER", "period_start": "2026-09-01", "period_end": "2026-09-30", "units": 0, "net_margin": 0.0},
            {"sku": "LOSER", "period_start": "2026-10-01", "period_end": "2026-10-31", "units": 0, "net_margin": 0.0}]
    v = measurement.measure_sku_exit(d, gone, date(2026, 8, 31), date(2026, 11, 5))
    assert v["verdict"] == "measured" and v["evidence_after"]["periods_gone"] == 2
    assert v["measured_impact_usd"] <= d["expected_impact_usd"] + 0.01
    assert v["measured_impact_usd"] == pytest.approx(abs(float(d["evidence"]["blended_monthly"])) * 61 / 30, rel=0.01)
    selling = [{**gone[0], "units": 40, "net_margin": -280.0}]
    assert measurement.measure_sku_exit(d, selling, date(2026, 8, 31), date(2026, 10, 5))["verdict"] == "not_yet"
    via = measurement.measure([d], {}, gone, [], [], today=date(2026, 11, 5))
    assert via[0]["verdict"] == "measured"
