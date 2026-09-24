"""Money between campaigns: the same total, moved to where the marginal dollar
returns more.

The engine trimmed each campaign toward its own break-even and never looked at
the gap between campaigns. With the response curves it already fits, the exact
allocation is a small dynamic program, and the money it finds exists even when
no campaign is past break-even.
"""

from datetime import date

import numpy as np
import pytest

from hubricon_engine import directives, measurement
from hubricon_engine.models import ad_allocation, ad_efficiency
from hubricon_engine.models.ad_allocation import allocate_dp, gain_draws, run


def _hill(s, a, k, h):
    return a * s**h / (k**h + s**h)


def _account(specs, n=14, seed=2, noise=8.0):
    """specs: [(name, mean_spend, a, k, h)] — daily points spread ±40% around
    the campaign's mean spend so the fit has a range to learn on."""
    rng = np.random.default_rng(seed)
    ppc = []
    for name, mean_spend, a, k, h in specs:
        spend = mean_spend * np.linspace(0.6, 1.4, n)
        sales = _hill(spend, a, k, h) + rng.normal(0, noise, size=n)
        for i, (s, v) in enumerate(zip(spend, sales)):
            ppc.append({"campaign_name": name, "campaign_id": name, "spend": float(s),
                        "sales": float(max(0.0, v)), "report_date": f"2026-08-{i + 1:02d}"})
    return {"asin_traffic": [], "sku_economics": [], "ppc_search_terms": [],
            "ppc_spend": ppc, "inventory_levels": [], "cogs_inputs": []}


def _rows(specs, **kw):
    return ad_efficiency.run(_account(specs, **kw), avg_margin=0.35)


# ── the solver ───────────────────────────────────────────────────────────────

def test_dp_equalises_marginal_returns_on_concave_curves():
    grid = np.arange(0, 1002) * 0.2      # budget 200 in 1000 steps
    curves = np.vstack([_hill(grid, 1000, 50, 1.0), _hill(grid, 600, 80, 1.0)])
    picks, v = allocate_dp(curves, [(0, 1001), (0, 1001)], 1000)
    assert picks.sum() == 1000
    s = picks * 0.2
    marginal = [np.gradient(c, grid)[p] for c, p in zip(curves, picks)]
    assert abs(marginal[0] - marginal[1]) / marginal[0] < 0.03
    # exact: no split of the same budget does better
    best = max(curves[0, j] + curves[1, 1000 - j] for j in range(0, 1001))
    assert curves[0, picks[0]] + curves[1, picks[1]] == pytest.approx(best)
    assert np.isfinite(v[1001]) and v[1001] >= v[1000]


def test_dp_is_exact_on_s_shaped_curves_where_a_lagrangian_bisection_gaps():
    grid = np.arange(0, 1002) * 0.3
    curves = np.vstack([_hill(grid, 900, 120, 2.5), _hill(grid, 700, 60, 2.5)])
    picks, _ = allocate_dp(curves, [(0, 1001), (0, 1001)], 1000)
    brute = max(range(0, 1001), key=lambda j: curves[0, j] + curves[1, 1000 - j])
    assert picks[0] == brute and picks.sum() == 1000
    # A bisection on the multiplier picks, for each λ, the grid point maximising
    # f_i − λ·s; on an S-shaped curve that argmax JUMPS as λ falls, so the set of
    # totals the Lagrangian can reach has holes. Either the budget is a hole (a
    # gap the bisection cannot close) or the Lagrangian lands on the DP's value:
    # in no case does it beat the DP.
    dp_value = curves[0, picks[0]] + curves[1, picks[1]]
    reached = {}
    for lam in np.linspace(0.0, 20.0, 4001):
        j = [int(np.argmax(c - lam * grid)) for c in curves]
        reached.setdefault(j[0] + j[1], j)
    if 1000 in reached:
        j0, j1 = reached[1000]
        assert curves[0, j0] + curves[1, j1] <= dp_value + 1e-9
    else:
        below = max(t for t in reached if t < 1000)
        above = min(t for t in reached if t > 1000)
        assert above - below > 1, "the Lagrangian skipped the budget"


# ── the pipeline ─────────────────────────────────────────────────────────────

def test_a_planted_misallocation_is_corrected_toward_equal_spend():
    rows = _rows([("small", 40.0, 1000, 60, 1.0), ("big", 160.0, 1000, 60, 1.0)])
    out = run(rows, 0.35)
    assert out["status"] == "ok", out
    by = {c["campaign_name"]: c for c in out["campaigns"]}
    assert by["small"]["recommended"] > by["small"]["current"]
    assert by["big"]["recommended"] < by["big"]["current"]
    assert out["total_spend"] == pytest.approx(by["small"]["current"] + by["big"]["current"], abs=0.01)
    assert by["small"]["recommended"] + by["big"]["recommended"] == pytest.approx(out["total_spend"], abs=0.5)
    assert out["delta_p50"] > 0 and out["delta_p5"] < out["delta_p50"] < out["delta_p95"]
    assert out["p_loss"] is not None and out["p_loss"] < 0.2
    assert 0 < out["alpha"] <= 1.0
    assert by["big"]["marginal_roas_now"] < by["small"]["marginal_roas_now"]
    # the move cap is the binding rail on a misallocation this large
    assert by["small"]["move_cap_bound"] or by["big"]["move_cap_bound"]


def test_the_posterior_mean_allocation_dominates_every_grid_alternative():
    rows = _rows([("A", 60.0, 900, 40, 1.2), ("B", 140.0, 700, 90, 1.0)])
    out = run(rows, 0.35)
    ok = [c for c in out["campaigns"] if c["status"] == "ok"]
    models = [c["curve_model"] for c in ok]
    rng = np.random.default_rng(ad_allocation.ALLOC_SEED)
    thetas = [ad_efficiency.draw_params(c["curve_model"], ad_allocation.params_vector(c),
                                        np.asarray(c["curve_cov"]), 400, rng) for c in ok]
    m = min(len(t) for t in thetas)
    thetas = [t[:m] for t in thetas]
    s0 = np.array([c["current"] for c in ok])
    s_star = np.array([c["s_star"] for c in ok])
    best = gain_draws(models, thetas, s0, s_star).mean()
    # alternatives inside the same move caps, same total
    for frac in np.linspace(-0.3, 0.3, 13):
        alt = s0 + np.array([frac * s0[0], -frac * s0[0]])
        if alt.min() <= 0:
            continue
        assert gain_draws(models, thetas, s0, alt).mean() <= best + 1e-6


def test_the_move_shrinks_with_the_variance_of_the_gain_and_stops_at_a_zero_budget():
    """The sizing rule, isolated: the same expected gain, three widths of
    posterior. α is the certainty-equivalent maximiser inside the shortfall
    constraint, so a wider posterior walks a shorter way; no budget, no move."""
    rng = np.random.default_rng(7)
    s0, s_star = np.array([40.0, 160.0]), np.array([100.0, 100.0])
    alphas = []
    for sd in (5.0, 60.0, 200.0):
        thetas = [np.column_stack([1000 + sd * rng.standard_normal(400), np.full(400, 60.0), np.full(400, 1.0)])
                  for _ in range(2)]
        alphas.append(ad_allocation.shrink_move(["hill", "hill"], thetas, s0, s_star, tol=300.0, avg_margin=0.35)["alpha"])
    assert alphas[0] >= alphas[1] >= alphas[2]
    assert alphas[0] > alphas[2]
    # No budget: any move that carries variance at all is refused. (An EXACT
    # posterior with a positive gain would still move under a zero budget, as
    # a price step does — there is no downside to guard.)
    thetas = [np.column_stack([1000 + 5.0 * rng.standard_normal(400), np.full(400, 60.0), np.full(400, 1.0)])
              for _ in range(2)]
    assert ad_allocation.shrink_move(["hill", "hill"], thetas, s0, s_star, tol=0.0, avg_margin=0.35)["alpha"] == 0.0


def test_a_noisier_fit_widens_the_band_and_an_unsupported_posterior_is_refused():
    tight = run(_rows([("A", 40.0, 1000, 60, 1.0), ("B", 160.0, 1000, 60, 1.0)], noise=5.0), 0.35)
    loose = run(_rows([("A", 40.0, 1000, 60, 1.0), ("B", 160.0, 1000, 60, 1.0)], noise=40.0), 0.35)
    assert tight["status"] == loose["status"] == "ok"
    assert (loose["delta_p95"] - loose["delta_p5"]) > (tight["delta_p95"] - tight["delta_p5"])
    # so noisy that fewer than MIN_DRAWS parameter draws land inside the fit's
    # own bounds: no allocation is printed on a posterior the bounds cannot hold
    hopeless = run(_rows([("A", 40.0, 1000, 60, 1.0), ("B", 160.0, 1000, 60, 1.0)], noise=120.0), 0.35)
    assert hopeless["status"] == "insufficient_draws" and hopeless["draws"] < ad_allocation.MIN_DRAWS
    assert all(c["reason"] == "posterior_unsupported" for c in hopeless["campaigns"])


def test_refusals_are_statuses_not_numbers():
    one = run(_rows([("A", 60.0, 900, 40, 1.2)]), 0.35)
    assert one["status"] == "insufficient_campaigns" and "delta_p50" not in one
    no_margin = run(_rows([("A", 60.0, 900, 40, 1.2), ("B", 140.0, 700, 90, 1.0)]), None)
    assert no_margin["status"] == "insufficient_margin"
    # identical campaigns at identical spend: the marginals already agree
    same = run(_rows([("A", 100.0, 900, 60, 1.0), ("B", 100.0, 900, 60, 1.0)], noise=3.0), 0.35)
    assert same["status"] == "no_reallocation", same.get("reason")
    # a losing set has no risk budget, so no move travels under the mandate
    losing = run(_rows([("A", 40.0, 30, 60, 1.0), ("B", 160.0, 30, 60, 1.0)], noise=1.0), 0.35)
    assert losing["status"] == "no_reallocation" and losing["alpha"] == 0.0


def test_a_row_without_a_covariance_is_held_not_guessed():
    rows = _rows([("A", 40.0, 1000, 60, 1.0), ("B", 160.0, 1000, 60, 1.0), ("C", 90.0, 800, 50, 1.0)])
    rows[2]["details"]["curve_cov"] = None
    out = run(rows, 0.35)
    held = {c["campaign_name"]: c for c in out["campaigns"] if c["status"] == "held"}
    assert held["C"]["reason"] == "no_covariance"
    assert out["status"] == "ok"


def test_reproducible_and_seeded():
    rows = _rows([("A", 40.0, 1000, 60, 1.0), ("B", 160.0, 1000, 60, 1.0)])
    a, b = run(rows, 0.35), run(rows, 0.35)
    assert a == b
    assert a["seed"] == ad_allocation.ALLOC_SEED and a["mc_inputs"]["seed"] == a["seed"]


# ── the directive ────────────────────────────────────────────────────────────

def _alloc(p5=-40.0, p50=300.0, p95=700.0, sales=400.0):
    return {
        "status": "ok", "total_spend": 200.0, "lambda": 3.1, "breakeven_marginal_roas": 2.86,
        "avg_margin": 0.35, "horizon_days": 30, "alpha": 0.6, "policy": {}, "seed": 1,
        "delta_p5": p5, "delta_p50": p50, "delta_p95": p95, "delta_mean": p50, "p_loss": 0.04,
        "mc_se": {}, "mc_inputs": {"draws": 400, "seed": 1}, "free_budget": {"total": 230.0},
        "campaigns": [
            {"campaign_name": "Fine", "status": "ok", "current": 40.0, "recommended": 60.0, "move": 20.0,
             "current_sales": sales, "curve_model": "hill", "curve_params": {"a": 1000, "k": 60, "h": 1.0},
             "curve_cov": [[100.0, 0, 0], [0, 4.0, 0], [0, 0, 0.01]], "max_spend": 60.0},
            {"campaign_name": "Over", "status": "ok", "current": 160.0, "recommended": 140.0, "move": -20.0,
             "current_sales": sales, "curve_model": "hill", "curve_params": {"a": 1000, "k": 60, "h": 1.0},
             "curve_cov": [[100.0, 0, 0], [0, 4.0, 0], [0, 0, 0.01]], "max_spend": 200.0},
        ],
    }


def test_the_directive_names_the_moves_and_is_standing_until_the_guard_bites():
    d = directives._budget_reallocation_directive(_alloc())
    assert d["kind"] == "budget_reallocation" and d["module"] == "advertising"
    assert d["mandate"] == "standing"
    assert "$20/day" in d["action_text"] and "$200/day total" in d["action_text"]
    assert "“Over” $160→$140" in d["action_text"] and "“Fine” $40→$60" in d["action_text"]
    assert "3.10 of sales per marginal dollar" in d["action_text"]
    assert "above the 2.86 break-even" in d["action_text"] and "under-spent" in d["action_text"]
    assert "+$300 over 30 days" in d["action_text"] and "90% range −$40 to +$700" in d["action_text"]
    assert d["expected_impact_usd"] == 300.0 and d["evidence"]["delta_p50"] == 300.0
    # the campaign set's net is 30·(0.35·800 − 200) = 2,400; budget 15% = 360.
    # A bad case of −$900 exceeds it: explicit, with the reason on the record.
    bad = directives._budget_reallocation_directive(_alloc(p5=-900.0))
    assert bad["mandate"] == "explicit" and "worst realistic case" in bad["mandate_reason"]
    assert directives._budget_reallocation_directive({"status": "no_reallocation"}) is None


def test_trimmed_campaigns_are_held_out_of_the_reallocation():
    # A and B sit under break-even (marginal ROAS 6.0 and 3.1 against 2.86); C
    # is far past it and gets a trim
    rows = _rows([("A", 40.0, 1000, 60, 1.0), ("B", 160.0, 2000, 200, 1.0), ("C", 300.0, 500, 30, 1.0)])
    trims = directives.trim_candidates(rows, 0.35)
    assert "C" in trims and trims["C"]["excess"] > 0
    out = run(rows, 0.35, exclude=set(trims))
    held = {c["campaign_name"]: c["reason"] for c in out["campaigns"] if c["status"] == "held"}
    assert held == {"C": "trimmed_this_run"}
    drafts = directives.draft_directives([], rows, [], [], ad_allocation=out)
    kinds = {(d["kind"], d["evidence"].get("campaign_name")) for d in drafts}
    assert ("campaign_trim", "C") in kinds
    assert any(k == "budget_reallocation" for k, _ in kinds)
    moved = {c["campaign_name"] for d in drafts if d["kind"] == "budget_reallocation"
             for c in d["evidence"]["campaigns"] if c["status"] == "ok"}
    assert "C" not in moved


# ── the measurement ──────────────────────────────────────────────────────────

def _directive(alloc):
    d = directives._budget_reallocation_directive(alloc)
    return {**d, "id": "d1", "status": "approved", "issued_at": "2026-08-01T00:00:00+00:00"}


def _after(spends, sales, days=20, start=date(2026, 8, 2)):
    rows = []
    for i in range(days):
        day = date.fromordinal(start.toordinal() + i).isoformat()
        for name in spends:
            rows.append({"campaign_name": name, "report_date": day, "spend": spends[name], "sales": sales[name]})
    return rows


def test_an_executed_reallocation_banks_the_conservative_quantile_capped_at_the_promise():
    d = _directive(_alloc())
    since, today = date(2026, 8, 1), date(2026, 9, 1)
    # the move was made, and each campaign's sales followed its curve
    v = measurement.measure_budget_reallocation(
        d, _after({"Fine": 60.0, "Over": 140.0}, {"Fine": 500.0, "Over": 875.0}), since, today)
    assert v["verdict"] == "measured" and v["attribution"] == "attributable"
    assert v["measured_impact_usd"] is not None
    assert v["measured_impact_usd"] <= 300.0 * 20 / 30 + 0.01
    assert v["evidence_after"]["executed_share"] >= 0.99
    assert v["evidence_after"]["measured_distribution"]["quantile_banked"] == 0.25
    # a much larger observed gain is capped at the prorated promise, and says so
    big = measurement.measure_budget_reallocation(
        d, _after({"Fine": 60.0, "Over": 140.0}, {"Fine": 900.0, "Over": 900.0}), since, today)
    assert big["measured_impact_usd"] == pytest.approx(300.0 * 20 / 30, abs=0.01)
    assert "promised for 20 days" in big["measurement_notes"]


def test_an_unexecuted_reallocation_is_stalled_then_closed():
    d = _directive(_alloc())
    since = date(2026, 8, 1)
    v = measurement.measure_budget_reallocation(
        d, _after({"Fine": 40.0, "Over": 160.0}, {"Fine": 400.0, "Over": 400.0}), since, date(2026, 9, 1))
    assert v["verdict"] == "not_yet" and "has not been made" in v["measurement_notes"]
    cold = measurement.measure_budget_reallocation(
        d, _after({"Fine": 40.0, "Over": 160.0}, {"Fine": 400.0, "Over": 400.0}), since, date(2026, 12, 1))
    assert cold["verdict"] == "closed"
    short = measurement.measure_budget_reallocation(
        d, _after({"Fine": 60.0, "Over": 140.0}, {"Fine": 500.0, "Over": 875.0}, days=5), since, date(2026, 9, 1))
    assert short["verdict"] == "not_yet" and "5 day(s)" in short["measurement_notes"]


def test_spend_step_reads_report_date():
    """`measure_spend_step` filtered on a `date` key the rows never carry, so
    every spend step came back not_yet. Pinned here."""
    d = {"id": "s1", "kind": "spend_step", "status": "approved", "expected_impact_usd": 600.0,
         "evidence": {"item_id": "Over", "baseline": 100.0, "current": 160.0}}
    rows = _after({"Over": 100.0}, {"Over": 300.0})
    v = measurement.measure_spend_step(d, rows, date(2026, 8, 1), date(2026, 9, 1))
    assert v["verdict"] == "measured" and v["measured_impact_usd"] > 0


def test_the_kind_is_dispatched_and_replay_can_audit_it():
    from hubricon_engine import replay
    d = _directive(_alloc())
    verdicts = measurement.measure(
        [d], {"ppc_spend": _after({"Fine": 60.0, "Over": 140.0}, {"Fine": 500.0, "Over": 875.0})},
        [], [], [], today=date(2026, 9, 1))
    assert verdicts[0]["kind"] == "budget_reallocation" and verdicts[0]["verdict"] == "measured"
    audit = replay.completeness(d)
    assert audit["complete"] and audit["distribution_complete"] and audit["promise_matches_distribution"]
