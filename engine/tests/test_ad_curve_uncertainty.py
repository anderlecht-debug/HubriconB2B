"""The break-even spend is an estimate, and now it says so.

A campaign trim is a promise sized against a fitted break-even. The fit came from
eight or ten daily points and curve_fit handed back a parameter covariance that
was being discarded. A published number with no interval is the gap dimension 3
of the scorecard exists to close.
"""

import numpy as np
import pytest

from hubricon_engine.models import ad_efficiency


def _campaign(noise, n=10, a=1000.0, k=50.0, h=1.2, seed=2):
    rng = np.random.default_rng(seed)
    spend = np.linspace(10, 300, n)
    sales = a * spend**h / (k**h + spend**h) + rng.normal(0, noise, size=n)
    ppc = [{"campaign_name": "C", "campaign_id": "C", "spend": float(s),
            "sales": float(max(0.0, v)), "report_date": f"2026-08-{i + 1:02d}"}
           for i, (s, v) in enumerate(zip(spend, sales))]
    return {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [],
            "ppc_spend": ppc, "inventory_levels": [], "cogs_inputs": []}


def _run(noise, **kw):
    return ad_efficiency.run(_campaign(noise, **kw), avg_margin=0.35)[0]


def test_the_breakeven_carries_an_interval_from_the_fits_own_covariance():
    r = _run(10.0)
    u = r["details"]["uncertainty"]
    assert u["basis"] == "parameter_covariance"
    assert u["draws"] > 300
    assert u["breakeven_p5"] < r["breakeven_spend"] * 1.05
    assert u["breakeven_p95"] > r["breakeven_spend"] * 0.95
    assert u["breakeven_p5"] < u["breakeven_p95"]
    assert u["marginal_roas_p5"] < r["marginal_roas"] < u["marginal_roas_p95"]


def test_the_interval_widens_with_the_noise_in_the_response():
    """The only property that makes an interval worth printing."""
    tight = _run(10.0)["details"]["uncertainty"]
    loose = _run(90.0)["details"]["uncertainty"]
    tight_width = tight["breakeven_p95"] - tight["breakeven_p5"]
    loose_width = loose["breakeven_p95"] - loose["breakeven_p5"]
    assert loose_width > tight_width * 2
    roas_tight = tight["marginal_roas_p95"] - tight["marginal_roas_p5"]
    roas_loose = loose["marginal_roas_p95"] - loose["marginal_roas_p5"]
    assert roas_loose > roas_tight * 2


def test_it_reports_how_often_the_marginal_dollar_is_already_underwater():
    """The number a trim decision actually rests on, rather than a point estimate
    either side of a threshold."""
    r = _run(10.0)
    u = r["details"]["uncertainty"]
    assert 0.0 <= u["p_below_breakeven"] <= 1.0
    # the break-even threshold here is 1/0.35 = 2.86 and the marginal ROAS at mean
    # spend is well under it, so the answer is certainty
    assert u["p_below_breakeven"] == 1.0


def test_a_campaign_whose_spend_never_moved_is_a_status_not_a_curve():
    """Six identical points. curve_fit converges — onto an arbitrary point of a
    flat likelihood ridge, returning a ZERO covariance that reads as certainty.
    That is the worst possible failure mode for a published interval, so the guard
    runs before the fit and the answer is a named status, the same way a SKU with
    one price gets one."""
    ppc = [{"campaign_name": "C", "campaign_id": "C", "spend": 100.0, "sales": 300.0,
            "report_date": f"2026-08-{i + 1:02d}"} for i in range(6)]
    data = {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [],
            "ppc_spend": ppc, "inventory_levels": [], "cogs_inputs": []}
    r = ad_efficiency.run(data, avg_margin=0.35)[0]
    assert r["status"] == "insufficient_spend_variation"
    assert r.get("breakeven_spend") is None
    assert r["details"]["spend_cv"] == 0.0


def test_a_zero_covariance_is_reported_as_unavailable_not_as_certainty():
    """The same guard one level down, on the function itself."""
    import numpy as np

    out = ad_efficiency.curve_uncertainty("hill", (900.0, 200.0, 1.0),
                                          np.zeros((3, 3)), 100.0, 100.0, 2.86)
    assert out["basis"] == "unavailable"
    assert "breakeven_p5" not in out


def test_the_interval_is_reproducible():
    a = _run(40.0)["details"]["uncertainty"]
    b = _run(40.0)["details"]["uncertainty"]
    assert a == b
    assert a["seed"] == ad_efficiency.CURVE_SEED


def test_the_trim_directive_is_sized_to_the_cautious_end_of_the_interval():
    """A higher break-even means a smaller trim and a smaller promise. That is the
    direction to be wrong in on a number the client is billed against."""
    from hubricon_engine.directives import draft_directives

    row = _run(90.0)
    # put current spend above the whole interval so a trim is drafted at all
    row = {**row, "current_spend": row["details"]["uncertainty"]["breakeven_p95"] * 2.0,
           "period_end": "2026-08-31", "bleed_terms": []}
    margins = [{"sku": "A", "period_start": "2026-08-01", "period_end": "2026-08-31",
                "units": 100, "revenue": 2000.0, "amazon_fees": 300.0, "cogs": 900.0,
                "ad_spend_allocated": 200.0, "net_margin": 600.0}]
    drafts = draft_directives([], [row], [], margins)
    trim = next(d for d in drafts if d["kind"] == "campaign_trim")
    ev = trim["evidence"]
    # since 2026-09-24 the cautious end is taken across every curve form the
    # backtest could not separate from the chosen one (and never below the
    # spend the campaign has run): here the other form breaks even higher
    fits = row["details"]["form_fits"]
    cautious = max([ev["breakeven_p95"]] + [f["breakeven_p95"] or f["breakeven"] for f in fits[1:]])
    assert ev["breakeven_used"] == pytest.approx(max(cautious, row["details"]["spend_p10"]))
    assert ev["breakeven_used"] >= ev["breakeven_p95"] >= ev["breakeven_spend"] - 1e-9
    if ev["target_bound_by"] == "breakeven":
        assert "we trim to the cautious end" in trim["action_text"]
    elif ev["target_bound_by"] == "form_disagreement":
        assert "Two curve shapes fit these days equally well" in trim["action_text"]
        assert len(ev["form_fits"]) == 2 and "pooled over the forms" in ev["net_basis"]


def test_no_trim_is_drafted_when_the_interval_reaches_current_spend():
    """If the fitted break-even could plausibly be where the campaign already
    spends, there is no honest trim to instruct."""
    from hubricon_engine.directives import draft_directives

    row = _run(90.0)
    u = row["details"]["uncertainty"]
    row = {**row, "current_spend": u["breakeven_p95"] * 0.98,
           "period_end": "2026-08-31", "bleed_terms": []}
    drafts = draft_directives([], [row], [], [])
    assert not [d for d in drafts if d["kind"] == "campaign_trim"]
