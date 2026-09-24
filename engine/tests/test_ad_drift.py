"""Ad cost drift: the cost of a click and what a click brings back, scanned
for regime breaks that the spend series never shows."""

import numpy as np

from hubricon_engine import directives
from hubricon_engine.models import ad_efficiency, anomaly


def _ppc(days=40, cpc_step_at=None, cpc_jump=0.5, spc_drop_at=None, seed=1, campaign="C", spend=120.0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(days):
        cpc = 1.0 + (cpc_jump if cpc_step_at is not None and i >= cpc_step_at else 0.0) + rng.normal(0, 0.03)
        clicks = spend / cpc
        spc = 2.5 * (0.5 if spc_drop_at is not None and i >= spc_drop_at else 1.0) + rng.normal(0, 0.08)
        rows.append({"campaign_name": campaign, "campaign_id": campaign, "report_date": f"2026-07-{1 + i:02d}" if i < 31
                     else f"2026-08-{i - 30:02d}", "spend": spend * (1 + 0.3 * np.sin(i)), "clicks": clicks * (1 + 0.3 * np.sin(i)),
                     "sales": clicks * (1 + 0.3 * np.sin(i)) * spc})
    return rows


def test_a_planted_cost_per_click_step_is_detected_and_valued_at_the_campaigns_clicks():
    rows = anomaly.run({"ppc_spend": _ppc(cpc_step_at=25)})
    cpc = [r for r in rows if r["scope"] == "campaign" and r["metric"] == "cpc" and r.get("flagged")]
    assert cpc and cpc[0]["direction"] == "up"
    assert cpc[0]["dollar_impact"] > 0 and cpc[0]["details"]["clicks_per_day"] > 0
    assert str(cpc[0]["since"]).startswith("2026-07-2") or str(cpc[0]["since"]).startswith("2026-07-3")
    quiet = anomaly.run({"ppc_spend": _ppc()})
    assert not [r for r in quiet if r["metric"] in ("cpc", "sales_per_click") and r.get("flagged")]


def test_a_conversion_drop_is_a_drift_directive_and_a_cost_rise_is_another():
    rows = anomaly.run({"ppc_spend": _ppc(spc_drop_at=25) + _ppc(cpc_step_at=25, campaign="D")})
    drafts = directives._anomaly_directives(rows)
    kinds = {(d["kind"], d["evidence"]["item_id"]) for d in drafts}
    assert ("conversion_drift", "C") in kinds and ("cpc_drift", "D") in kinds
    d = next(x for x in drafts if x["kind"] == "cpc_drift")
    assert d["expected_impact_usd"] is None and "refit on the new regime" in d["action_text"]
    from hubricon_engine.measurement import UNBANKABLE_KINDS
    assert {"cpc_drift", "conversion_drift"} <= UNBANKABLE_KINDS


def test_the_response_curve_is_refitted_after_the_break_or_held():
    ppc = _ppc(cpc_step_at=25)
    rows = anomaly.run({"ppc_spend": ppc})
    breaks = ad_efficiency.regime_breaks(rows)
    assert "C" in breaks and breaks["C"]["metric"] == "cpc"
    data = {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [], "ppc_spend": ppc,
            "inventory_levels": [], "cogs_inputs": []}
    whole = ad_efficiency.run(data, avg_margin=0.35)[0]
    after = ad_efficiency.run(data, avg_margin=0.35, breaks=breaks)[0]
    assert after["details"]["regime_break"]["since"] == breaks["C"]["since"]
    assert after["details"]["regime_break"]["points_before_break_dropped"] > 0
    assert after["details"]["n_points"] < whole["details"]["n_points"]
    # a break so recent that under five points follow it: held, not fitted stale
    late = ad_efficiency.run(data, avg_margin=0.35, breaks={"C": {"since": "2026-08-08", "metric": "cpc"}})[0]
    assert late["status"] == "regime_break" and "breakeven_spend" not in late
    from hubricon_engine.models import ad_allocation
    held = ad_allocation.run([late, whole], 0.35)
    assert any(c["status"] == "held" and c["reason"] == "status:regime_break" for c in held["campaigns"])
