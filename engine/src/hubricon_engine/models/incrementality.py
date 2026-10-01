"""Ad incrementality and the organic halo: is the break-even too generous or
too strict?

The break-even in §4 is computed on the platform's ATTRIBUTED sales. Two things
are wrong with that at once, in opposite directions. Some attributed sales would
have happened organically — the customer searched the brand, clicked the ad
because it sat on top, and would have bought from the organic listing an inch
lower — so attribution overstates what the ads earned. And ad-driven sales
improve organic rank, so ads earn sales the attribution window never sees, and
attribution understates. The number that settles it is the incrementality
ratio

    ι = d(total sales) / d(spend)  ÷  d(attributed sales) / d(spend)

ι < 1: attribution overstates and the break-even is too generous. ι > 1: a halo,
and the break-even is too strict. Nothing in a monthly export identifies ι
cleanly, and this module says so; it offers two estimators of different
honesty.

OBSERVATIONAL. Per export period: total sales S_t across the catalog (the
Business Report's ordered product sales, else SKU Economics sales), attributed
sales A_t and spend X_t summed from the daily campaign file. First differences
remove the level and the trend; the two slopes ΔS on ΔX and ΔA on ΔX are fitted
by OLS with HC3 standard errors and ι is their ratio, with a delta-method
interval on a Student-t critical value at the residual degrees of freedom.
Refused below eight periods or when spend barely moved between periods
(coefficient of variation under 10%), because a slope on a flat regressor is a
number with no meaning. Seasonality and everything else that moves total sales
sits in the residual, so with monthly data this will refuse or publish a wide
band more often than not — which is the truthful answer, and the reason the
second estimator exists.

SWITCHBACK. A campaign is turned ON and OFF in randomised two-day blocks over
four weeks, the order drawn from a generator seeded by the client, the campaign
and the start date and nothing else. Daily total sales from the settlement file
(models/daily.py) and daily attributed sales from the campaign file are then
compared ON against OFF: ι = (mean total ON − mean total OFF) ÷ (mean
attributed ON − mean attributed OFF), the interval by a seeded block bootstrap,
the sharpness by a permutation test of the block labels. Randomisation is what
makes E[shock | ON] = E[shock | OFF]. What it does not remove is CARRYOVER, and
carryover works on both lifts at once. Real sales that arrive on OFF days from
ON-day clicks — rank that persists, a customer who came back — shrink the
total-sales lift and pull ι toward zero. Attribution that follows the click
into OFF days (the platform's seven-day window) shrinks the attributed lift and
pushes ι up. Which wins depends on whether the window carries further than the
real effect, and nothing in the data says which; the first draft of this module
claimed a direction, and the simulation in tests/test_incrementality.py showed
each mechanism moving ι the opposite way. Stated in the payload, not corrected.
The test is only executed if OFF days actually stopped spending, and the
analysis refuses otherwise.

Catalog-level only. No export links a campaign to the SKUs it advertises, so the
total is the account's total and a campaign's incremental effect is measured
against everything else the account sold. That is diluted, not biased.
"""

import hashlib
from datetime import date, timedelta

import numpy as np
from scipy import stats

from .common import num, period_days

MIN_PERIODS = 8
MIN_SPEND_CV = 0.10
CI_LEVEL = 0.95
BLOCK_DAYS = 2
N_BLOCKS = 14
BOOTSTRAP_DRAWS = 2000
PERMUTATIONS = 2000
# OFF-day spend above this share of ON-day spend means the campaign was not
# actually paused on that day.
OFF_SPEND_SHARE = 0.10
MIN_COMPLIANCE = 0.80
MIN_BLOCKS_ANALYSED = 10


# ── observational ────────────────────────────────────────────────────────────

def _period_totals(data: dict) -> list[dict]:
    """One row per export period: total sales, attributed sales, spend."""
    totals: dict[tuple[str, str], dict] = {}
    source = "asin_traffic" if data.get("asin_traffic") else "sku_economics"
    key_field = "ordered_product_sales" if source == "asin_traffic" else "sales"
    for r in data.get(source) or []:
        k = (str(r["period_start"]), str(r["period_end"]))
        t = totals.setdefault(k, {"period_start": k[0], "period_end": k[1], "total": 0.0,
                                  "attributed": 0.0, "spend": 0.0, "ad_days": 0})
        t["total"] += float(r.get(key_field) or 0)
    for (start, end), t in totals.items():
        for r in data.get("ppc_spend") or []:
            d = str(r.get("report_date") or "")[:10]
            if d and start <= d <= end:
                t["attributed"] += float(r.get("sales") or 0)
                t["spend"] += float(r.get("spend") or 0)
                t["ad_days"] += 1
    rows = [t for t in totals.values() if t["ad_days"] > 0]
    for t in rows:
        days = period_days(t["period_start"], t["period_end"])
        t["total"] /= days
        t["attributed"] /= days
        t["spend"] /= days
    return sorted(rows, key=lambda t: t["period_start"])


def _slope_hc3(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """OLS slope with intercept, HC3 standard error, residual dof."""
    n = len(x)
    X = np.column_stack([np.ones(n), x])
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    xtx_inv = np.linalg.inv(X.T @ X)
    hat = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    slack = np.maximum(1.0 - hat, 1e-6)
    omega = (resid / slack) ** 2
    cov = xtx_inv @ (X.T * omega) @ X @ xtx_inv
    return float(beta[1]), float(np.sqrt(max(cov[1, 1], 0.0))), n - 2


def observational(data: dict) -> dict:
    rows = _period_totals(data)
    base = {"estimator": "observational", "n_periods": len(rows),
            "details": {"periods": [{k: (num(v, 2) if isinstance(v, float) else v) for k, v in t.items()}
                                    for t in rows]}}
    if len(rows) < MIN_PERIODS:
        return {**base, "status": "insufficient_data"}
    spend = np.array([t["spend"] for t in rows])
    cv = float(spend.std() / spend.mean()) if spend.mean() > 0 else 0.0
    base["spend_cv"] = num(cv, 4)
    if cv < MIN_SPEND_CV:
        return {**base, "status": "insufficient_spend_variation"}
    dx = np.diff(spend)
    ds = np.diff(np.array([t["total"] for t in rows]))
    da = np.diff(np.array([t["attributed"] for t in rows]))
    if float(np.std(dx)) <= 0:
        return {**base, "status": "insufficient_spend_variation"}
    b_total, se_total, dof = _slope_hc3(dx, ds)
    b_attr, se_attr, _ = _slope_hc3(dx, da)
    if b_attr <= 0:
        return {**base, "status": "attributed_slope_not_positive",
                "details": {**base["details"], "slope_total": num(b_total, 4), "slope_attributed": num(b_attr, 4)}}
    iota = b_total / b_attr
    # delta method on a ratio of two independent-ish slopes
    se = abs(iota) * float(np.sqrt((se_total / b_total) ** 2 + (se_attr / b_attr) ** 2)) if b_total != 0 \
        else se_total / b_attr
    t_crit = float(stats.t.ppf(0.5 + CI_LEVEL / 2, max(dof, 1)))
    lo, hi = iota - t_crit * se, iota + t_crit * se
    reading = ("attribution overstates: the break-even is too generous" if hi < 1
               else "a halo: the break-even is too strict" if lo > 1
               else "the interval includes 1 — no correction is supported by this history")
    return {**base, "status": "ok", "incrementality": num(iota, 4), "std_err": num(se, 4),
            "ci95": [num(lo, 4), num(hi, 4)], "reading": reading,
            "details": {**base["details"], "slope_total": num(b_total, 4), "slope_attributed": num(b_attr, 4),
                        "se_total": num(se_total, 4), "se_attributed": num(se_attr, 4),
                        "dof": int(dof), "t_critical": num(t_crit, 4), "se_estimator": "HC3",
                        "basis": ("first differences of daily-rate period totals; total sales from "
                                  + ("the Business Report" if data.get("asin_traffic") else "SKU Economics")
                                  + "; the residual carries season and everything else that moves total sales")}}


# ── switchback ───────────────────────────────────────────────────────────────

def switchback_seed(client_id: str, campaign: str, start_date: str) -> int:
    """A seed that depends on nothing the data could move."""
    return int(hashlib.sha1(f"{client_id}|{campaign}|{start_date}".encode()).hexdigest()[:8], 16)


def design_switchback(client_id: str, campaign: str, start_date: str,
                      n_blocks: int = N_BLOCKS, block_days: int = BLOCK_DAYS) -> dict:
    """ON/OFF in randomised blocks, half each, order from the seeded generator."""
    seed = switchback_seed(client_id, campaign, start_date)
    rng = np.random.default_rng(seed)
    arms = ["on"] * (n_blocks // 2) + ["off"] * (n_blocks - n_blocks // 2)
    order = rng.permutation(len(arms))
    start = date.fromisoformat(start_date)
    blocks = []
    for i, idx in enumerate(order):
        b0 = start + timedelta(days=i * block_days)
        blocks.append({"block": i, "arm": arms[idx], "start": b0.isoformat(),
                       "end": (b0 + timedelta(days=block_days - 1)).isoformat()})
    return {"campaign": campaign, "start_date": start_date,
            "end_date": (start + timedelta(days=n_blocks * block_days - 1)).isoformat(),
            "block_days": block_days, "n_blocks": n_blocks, "seed": seed, "blocks": blocks,
            "basis": ("randomised block design; the order is drawn from a generator seeded by client, "
                      "campaign and start date, independent of any sales figure")}


def analyze_switchback(schedule: dict, daily_totals: list[dict], ppc_spend: list[dict]) -> dict:
    """ι from the blocks, with a bootstrap interval and a permutation p-value."""
    campaign = schedule["campaign"]
    tot_by_day = {t["date"]: float(t.get("revenue") or 0) for t in daily_totals}
    spend_by_day, attr_by_day = {}, {}
    for r in ppc_spend:
        if r.get("campaign_name") != campaign or not r.get("report_date"):
            continue
        d = str(r["report_date"])[:10]
        spend_by_day[d] = spend_by_day.get(d, 0.0) + float(r.get("spend") or 0)
        attr_by_day[d] = attr_by_day.get(d, 0.0) + float(r.get("sales") or 0)

    blocks = []
    for b in schedule["blocks"]:
        days = []
        d = date.fromisoformat(b["start"])
        while d <= date.fromisoformat(b["end"]):
            days.append(d.isoformat())
            d += timedelta(days=1)
        covered = [x for x in days if x in tot_by_day]
        if not covered:
            continue
        blocks.append({
            "arm": b["arm"],
            "total": float(np.mean([tot_by_day[x] for x in covered])),
            "attributed": float(np.mean([attr_by_day.get(x, 0.0) for x in covered])),
            "spend": float(np.mean([spend_by_day.get(x, 0.0) for x in covered])),
            "days": len(covered),
        })
    base = {"estimator": "switchback", "campaign": campaign, "n_blocks": len(blocks),
            "seed": schedule.get("seed")}
    if len(blocks) < MIN_BLOCKS_ANALYSED:
        return {**base, "status": "insufficient_data",
                "details": {"basis": f"{len(blocks)} block(s) with settlement data; {MIN_BLOCKS_ANALYSED} needed"}}
    on = [b for b in blocks if b["arm"] == "on"]
    off = [b for b in blocks if b["arm"] == "off"]
    if not on or not off:
        return {**base, "status": "insufficient_data"}
    on_spend = float(np.mean([b["spend"] for b in on]))
    compliant = [b["spend"] <= OFF_SPEND_SHARE * on_spend for b in off] if on_spend > 0 else [False] * len(off)
    compliance = float(np.mean(compliant))
    base["compliance"] = num(compliance, 3)
    if compliance < MIN_COMPLIANCE:
        return {**base, "status": "not_executed",
                "details": {"basis": f"OFF blocks still spent on {1 - compliance:.0%} of days; the campaign was not paused"}}

    tot_on, tot_off = np.array([b["total"] for b in on]), np.array([b["total"] for b in off])
    att_on, att_off = np.array([b["attributed"] for b in on]), np.array([b["attributed"] for b in off])
    lift_total = float(tot_on.mean() - tot_off.mean())
    lift_attr = float(att_on.mean() - att_off.mean())
    if lift_attr <= 0:
        return {**base, "status": "attributed_lift_not_positive",
                "lift_total_daily": num(lift_total), "lift_attributed_daily": num(lift_attr)}
    iota = lift_total / lift_attr

    rng = np.random.default_rng(int(schedule.get("seed") or 0) + 1)
    boot = []
    for _ in range(BOOTSTRAP_DRAWS):
        i_on = rng.integers(0, len(on), len(on))
        i_off = rng.integers(0, len(off), len(off))
        la = att_on[i_on].mean() - att_off[i_off].mean()
        if la <= 0:
            continue
        boot.append((tot_on[i_on].mean() - tot_off[i_off].mean()) / la)
    boot = np.array(boot)
    # permutation: relabel blocks, keep the arm counts, how often |lift| this big
    all_tot = np.array([b["total"] for b in blocks])
    n_on = len(on)
    perms = 0
    for _ in range(PERMUTATIONS):
        idx = rng.permutation(len(blocks))
        l = all_tot[idx[:n_on]].mean() - all_tot[idx[n_on:]].mean()
        perms += abs(l) >= abs(lift_total)
    p_perm = perms / PERMUTATIONS

    lo, hi = (float(np.quantile(boot, 0.05)), float(np.quantile(boot, 0.95))) if boot.size >= 50 else (None, None)
    reading = ("attribution overstates: the break-even is too generous" if hi is not None and hi < 1
               else "a halo: the break-even is too strict" if lo is not None and lo > 1
               else "the interval includes 1")
    return {**base, "status": "ok", "incrementality": num(iota, 4),
            "ci90": [num(lo, 4), num(hi, 4)], "p_permutation": num(p_perm, 4),
            "lift_total_daily": num(lift_total), "lift_attributed_daily": num(lift_attr),
            "reading": reading,
            "details": {"bootstrap_draws": int(boot.size), "permutations": PERMUTATIONS,
                        "on_blocks": len(on), "off_blocks": len(off),
                        "basis": ("randomised ON/OFF blocks; ι = total-sales lift ÷ attributed lift; 90% "
                                  "band by block bootstrap; carryover is not corrected — real effect "
                                  "arriving on OFF days pulls ι toward zero, attribution following the "
                                  "click into OFF days pushes it up")}}


def run(data: dict, experiments: list[dict] | None = None) -> dict:
    """The observational estimate, plus every switchback with a result."""
    obs = observational(data)
    tests = []
    for e in experiments or []:
        result = e.get("result")
        if result:
            tests.append(result)
    live = [t for t in tests if t.get("status") == "ok"]
    # the ι the ad break-even may use: only an executed switchback earns it
    usable = live[-1]["incrementality"] if live else None
    return {"status": "ok" if (obs.get("status") == "ok" or live) else obs.get("status", "insufficient_data"),
            "observational": obs, "switchbacks": tests,
            "incrementality_for_breakeven": usable,
            "basis": ("the observational ratio is information; only an executed randomised switchback "
                      "adjusts the ad break-even")}
