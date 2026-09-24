"""Randomised price experiments: the instrument the elasticity needs.

MATH_METHODS.md §2 names the single most dangerous assumption in this engine:
the elasticity is a correlation, and the price was not randomised. A seller who
reprices off last month's demand produces a fitted curve about half an
elasticity too flat, in the direction that argues for raising prices. The
engine's own steps could not fix it, for two measured reasons — a step chosen by
the fit is not exogenous to demand, and a fortnight-long step blends away below
the monthly estimator's price-variation floor. This module builds the two
things that were missing: a price change whose draw is independent of the data,
and a price series fine enough to see it.

THE DESIGN. Five arms around the current price, −5%, −2.5%, 0, +2.5%, +5% — all
inside the 5% cap the standing mandate covers. Six blocks of seven days. Two
blocks are ANCHORS, one at each end: a Thompson allocation alone can put every
block on adjacent arms and hand the estimator a price series whose coefficient
of variation is under its own floor, so the anchors buy identification first
and Thompson earns during the test. The remaining four blocks are allocated by
Thompson sampling: the posterior over ε, the baseline volume and the fees is
drawn (pricing_engine.delta_draws), profit at every arm evaluated on every draw,
and each arm's share is the probability it is the best — clipped at PI_FLOOR so
no arm is ever starved. With no fit at all the shares are uniform: the test is
what creates the data. Block ORDER is a permutation drawn from a generator
seeded by the client, the SKU and the start date and nothing else; the arm a
day gets is therefore independent of that day's demand shock by construction,
which is the whole of the identification argument. Seven-day blocks hold each
weekday once, so day-of-week effects cannot load on an arm.

THE ANALYSIS. Daily units and realised price come from the settlement file
(models/daily.py). The first day of each block is a WASHOUT: Transaction View
rows post at shipment, a day after purchase, so the first day of a block carries
the previous arm's orders. Blocks aggregate to points {assigned price, units,
days} and go through the same fit as the monthly estimator (elasticity._fit:
HC3, Student-t) with the ASSIGNED price as the regressor, so slippage in the
realised price cannot re-introduce endogeneity; the first stage (realised on
assigned) and the Wald ratio are published beside it. HC3 treats blocks as
independent and understates the standard error when shocks persist, so
RANDOMISATION INFERENCE runs too: every distinct permutation of the block labels
is refitted, the Fisher p-value for ε = 0 and the permutation sd are published,
and the standard error the engine uses is the larger of the two.

WHAT THE EXPERIMENT SAYS ABOUT THE OBSERVATIONAL FIT. bias = ε_obs,raw − ε_exp,
with its own standard error, and the sentence a seller reads: how far the
history's curve was too flat. When the experiment fits, elasticity.run takes its
row for that SKU and does NOT shrink it toward the catalogue pool: the pool's
mean is the biased observational one, and shrinking an unbiased estimate toward
it would pull the bias back in.

WHAT IT CANNOT TELL YOU. Buy Box suppression at the high arm is part of the price
response the seller actually faces and is not separated out; a test with under
80% of days at the assigned price identifies nothing and says so; a SKU that
sells a unit a week has too few units per block for any six-block test, and
_fit's floor on price variation and its Student-t interval say how little was
learned rather than pretending otherwise.
"""

import hashlib
import itertools
from datetime import date, timedelta

import numpy as np
from scipy import stats

from .common import num, period_days
from .daily import daily_sku_series
from .elasticity import MIN_PRICE_CV, _fit
from .pricing_engine import _has_stated_uncertainty, _posterior_se, delta_at, delta_draws, fee_terms

ARM_GRID = (-0.05, -0.025, 0.0, 0.025, 0.05)
ANCHOR_ARMS = (0, 4)
N_BLOCKS = 6
BLOCK_DAYS = 7
WASHOUT_DAYS = 1
PI_FLOOR = 0.10
PRICE_TOLERANCE = 0.02
MIN_COMPLIANCE = 0.80
EXPERIMENT_DRAWS = 4000
MAX_PERMUTATIONS = 720
CI_LEVEL = 0.95


def schedule_seed(client_id: str, sku: str, start_date: str) -> int:
    """Seeded by identity and calendar, never by a sales figure."""
    return int(hashlib.sha1(f"{client_id}|{sku}|{start_date}".encode()).hexdigest()[:8], 16)


def _unit_economics(margin_row: dict) -> dict | None:
    units = float(margin_row.get("units") or 0)
    revenue = float(margin_row.get("revenue") or 0)
    if units <= 0 or revenue <= 0:
        return None
    f, big_f, basis = fee_terms(margin_row)
    cogs = margin_row.get("cogs")
    return {"p0": revenue / units, "q0": units, "fee_rate": f, "fixed_fee": big_f, "fee_basis": basis,
            "unit_cost": float(cogs) / units if cogs is not None else None}


def thompson_shares(margin_row: dict, elasticity_row: dict | None, arms=ARM_GRID,
                    fee_history=None, draws: int = EXPERIMENT_DRAWS) -> tuple[np.ndarray, dict | None]:
    """P(arm k is the most profitable) over the posterior, clipped at PI_FLOOR.
    Uniform with no usable fit or no landed cost. Returns the shares and the
    draw set (None when uniform) so the cost of the test can be priced on it."""
    k = len(arms)
    econ = _unit_economics(margin_row)
    usable = (elasticity_row is not None and elasticity_row.get("status") == "ok"
              and elasticity_row.get("elasticity") is not None and _has_stated_uncertainty(elasticity_row)
              and econ is not None and econ["unit_cost"] is not None)
    if not usable:
        return np.full(k, 1.0 / k), None
    se, dof = _posterior_se(elasticity_row)
    draw_set = delta_draws(eps=float(elasticity_row["elasticity"]), std_err=se, dof=dof, p0=econ["p0"],
                           q0=econ["q0"], unit_cost=econ["unit_cost"], fee_rate=econ["fee_rate"],
                           fixed_fee=econ["fixed_fee"],
                           demand_sd_log=(elasticity_row.get("details") or {}).get("residual_sd_log"),
                           fee_history=fee_history, draws=draws)
    deltas = np.column_stack([delta_at(draw_set, econ["p0"] * (1 + d)) for d in arms])
    deltas = np.where(np.isfinite(deltas), deltas, -np.inf)
    best = np.argmax(deltas, axis=1)
    pi = np.array([float(np.mean(best == j)) for j in range(k)])
    # the floor as a mixture with uniform: every arm keeps at least PI_FLOOR
    # exactly, and the best arm can reach at most 1 − (k − 1)·PI_FLOOR
    pi = PI_FLOOR + (1.0 - k * PI_FLOOR) * pi
    return pi / pi.sum(), draw_set


def block_counts(pi: np.ndarray, n_blocks: int = N_BLOCKS, anchors=ANCHOR_ARMS) -> list[int]:
    """Anchors first, the rest by largest remainder on the Thompson shares."""
    counts = [0] * len(pi)
    for a in anchors:
        counts[a] += 1
    remaining = n_blocks - len(anchors)
    raw = np.asarray(pi, dtype=float) * remaining
    floor = np.floor(raw).astype(int)
    left = remaining - int(floor.sum())
    order = np.argsort(-(raw - floor))
    for j in range(len(pi)):
        counts[j] += int(floor[j])
    for j in order[:left]:
        counts[int(j)] += 1
    return counts


def design(client_id: str, sku: str, start_date: str, margin_row: dict,
           elasticity_row: dict | None = None, fee_history=None,
           n_blocks: int = N_BLOCKS, block_days: int = BLOCK_DAYS, arms=ARM_GRID) -> dict:
    econ = _unit_economics(margin_row)
    if econ is None:
        return {"sku": sku, "status": "insufficient_data", "basis": "no units or revenue on the latest margin row"}
    p0 = econ["p0"]
    prices = [round(p0 * (1 + d), 2) for d in arms]
    pi, draw_set = thompson_shares(margin_row, elasticity_row, arms, fee_history)
    counts = block_counts(pi, n_blocks)
    sequence = [j for j, c in enumerate(counts) for _ in range(c)]
    seed = schedule_seed(client_id, sku, start_date)
    order = np.random.default_rng(seed).permutation(len(sequence))
    start = date.fromisoformat(start_date)
    blocks = []
    for i, idx in enumerate(order):
        b0 = start + timedelta(days=i * block_days)
        arm = sequence[idx]
        blocks.append({"block": i, "arm": arm, "price": prices[arm], "start": b0.isoformat(),
                       "end": (b0 + timedelta(days=block_days - 1)).isoformat()})
    block_prices = np.array([b["price"] for b in blocks])
    price_cv = float(block_prices.std() / block_prices.mean())
    out = {"sku": sku, "status": "ok", "p0": round(p0, 2), "arms": list(arms), "prices": prices,
           "pi": [num(v, 4) for v in pi], "block_counts": counts, "n_blocks": n_blocks,
           "block_days": block_days, "washout_days": WASHOUT_DAYS, "seed": seed,
           "start_date": start_date, "end_date": (start + timedelta(days=n_blocks * block_days - 1)).isoformat(),
           "blocks": blocks, "price_cv": num(price_cv, 4),
           "allocation": "thompson" if draw_set is not None else "uniform (no usable fit)",
           "basis": ("five arms inside the 5% cap; anchors at −5% and +5%; the rest by Thompson sampling on "
                     "the fitted posterior; block order from a generator seeded by client, SKU and start date")}
    if price_cv < MIN_PRICE_CV:
        return {**out, "status": "insufficient_price_variation"}
    if draw_set is not None:
        shares = np.array(counts, dtype=float) / n_blocks
        test_days = n_blocks * block_days
        scale = test_days / period_days(str(margin_row["period_start"]), str(margin_row["period_end"])) \
            if margin_row.get("period_start") and margin_row.get("period_end") else test_days / 30.0
        cost = sum(shares[j] * delta_at(draw_set, prices[j]) for j in range(len(arms))) * scale
        cost = cost[np.isfinite(cost)]
        out["expected_test_cost"] = {"p5": num(float(np.quantile(cost, 0.05))),
                                     "p50": num(float(np.quantile(cost, 0.50))),
                                     "p95": num(float(np.quantile(cost, 0.95))),
                                     "basis": "profit vs holding the current price, on realised block shares, "
                                              "scaled to the test window", "draws": int(cost.size)}
    else:
        out["expected_test_cost"] = None
    return out


def block_points(schedule: dict, daily: list[dict], washout_days: int = WASHOUT_DAYS) -> tuple[list[dict], dict]:
    """Aggregate the daily series to one point per block after the washout.
    `days` is the number of scheduled days, so a day with no orders counts as a
    zero-demand day rather than vanishing."""
    by_day = {d["date"]: d for d in daily}
    points, checked, compliant = [], 0, 0
    for b in schedule["blocks"]:
        d = date.fromisoformat(b["start"]) + timedelta(days=washout_days)
        end = date.fromisoformat(b["end"])
        units, revenue, n_days = 0, 0.0, 0
        realised = []
        while d <= end:
            n_days += 1
            row = by_day.get(d.isoformat())
            if row:
                units += int(row["units"])
                revenue += float(row["revenue"] or 0)
                realised.append(float(row["price"]))
                checked += 1
                compliant += abs(float(row["price"]) - b["price"]) / b["price"] <= PRICE_TOLERANCE
            d += timedelta(days=1)
        points.append({"block": b["block"], "arm": b["arm"], "price": float(b["price"]),
                       "price_realised": float(np.mean(realised)) if realised else None,
                       "units": units, "days": n_days})
    compliance = compliant / checked if checked else 0.0
    return points, {"compliance": compliance, "days_checked": checked}


def permutation_inference(points: list[dict]) -> dict:
    """Refit the slope under every distinct permutation of the block prices."""
    usable = [p for p in points if p["units"] > 0]
    x = np.log([p["price"] for p in usable])
    y = np.log([p["units"] / p["days"] for p in usable])
    n = len(usable)
    if n < 3 or float(np.std(x)) <= 0:
        return {"sd": None, "p_value": None, "permutations": 0}
    xc = x - x.mean()
    observed = float((xc * (y - y.mean())).sum() / (xc**2).sum())
    perms = {tuple(x[list(p)]) for p in itertools.permutations(range(n))}
    P = np.array(sorted(perms))[:MAX_PERMUTATIONS]
    Pc = P - P.mean(axis=1, keepdims=True)
    slopes = (Pc * (y - y.mean())).sum(axis=1) / (Pc**2).sum(axis=1)
    return {"sd": float(np.std(slopes, ddof=1)) if len(slopes) > 1 else None,
            "p_value": float(np.mean(np.abs(slopes) >= abs(observed) - 1e-12)),
            "permutations": int(len(slopes)), "observed_slope": observed}


def analyze(schedule: dict, daily: list[dict], observational: dict | None = None,
            washout_days: int = WASHOUT_DAYS, period_days_for_scale: float = 30.0) -> dict:
    sku = schedule.get("sku")
    points, execution = block_points(schedule, daily, washout_days)
    base = {"level": "sku", "item_id": sku, "n_periods": len(points), "compliance": num(execution["compliance"], 3),
            "details": {"source": "experiment", "seed": schedule.get("seed"), "washout_days": washout_days,
                        "blocks": [{k: (num(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in points],
                        "days_checked": execution["days_checked"]}}
    if execution["days_checked"] == 0:
        return {**base, "status": "insufficient_data",
                "details": {**base["details"], "basis": "no settlement Order rows for this SKU inside the test window"}}
    if execution["compliance"] < MIN_COMPLIANCE:
        return {**base, "status": "not_executed",
                "details": {**base["details"],
                            "basis": f"the realised price sat at the assigned arm on only {execution['compliance']:.0%} of days"}}
    itt = _fit([{"price": p["price"], "units": p["units"], "days": p["days"]} for p in points])
    if itt.get("status") != "ok":
        return {**base, "status": itt["status"], "details": {**base["details"], **itt.get("details", {})}}
    # first stage: realised on assigned, both in logs, across blocks with sales
    usable = [p for p in points if p["units"] > 0 and p["price_realised"]]
    xa = np.log([p["price"] for p in usable])
    xr = np.log([p["price_realised"] for p in usable])
    beta_fs = float(np.polyfit(xa, xr, 1)[0]) if float(np.std(xa)) > 0 and len(usable) >= 2 else 1.0
    beta_fs = beta_fs if abs(beta_fs) > 1e-6 else 1.0
    eps_exp = float(itt["elasticity"]) / beta_fs
    se_exp = float(itt["std_err"]) / abs(beta_fs)
    perm = permutation_inference(points)
    se_used = max(se_exp, perm["sd"]) if perm["sd"] is not None else se_exp
    dof = int(itt["details"]["dof"])
    t_crit = float(stats.t.ppf(0.5 + CI_LEVEL / 2, dof))
    details = {**base["details"], **itt["details"],
               "itt_elasticity": num(itt["elasticity"], 4), "itt_std_err": num(itt["std_err"], 4),
               "first_stage": num(beta_fs, 4), "se_hc3": num(se_exp, 4),
               "se_permutation": num(perm["sd"], 4), "p_permutation": num(perm["p_value"], 4),
               "permutations": perm["permutations"], "se_estimator": "max(HC3, permutation)",
               "ci95": [num(eps_exp - t_crit * se_used, 4), num(eps_exp + t_crit * se_used, 4)],
               "t_critical": num(t_crit, 4), "dof": dof}
    # demand dispersion at the period scale the price step is priced on
    block_sd = itt["details"].get("residual_sd_log")
    if observational and (observational.get("details") or {}).get("residual_sd_log") is not None:
        details["residual_sd_log"] = observational["details"]["residual_sd_log"]
        details["residual_sd_basis"] = "observational fit"
    elif block_sd is not None:
        eff_days = points[0]["days"] if points else BLOCK_DAYS - WASHOUT_DAYS
        details["residual_sd_log"] = num(float(block_sd) * np.sqrt(eff_days / period_days_for_scale), 6)
        details["residual_sd_basis"] = f"block residual scaled by sqrt({eff_days}/{period_days_for_scale:.0f})"
    if observational and observational.get("status") == "ok" and observational.get("elasticity") is not None:
        obs_raw = float((observational.get("details") or {}).get("epsilon_raw") or observational["elasticity"])
        obs_se = float(observational.get("std_err") or 0)
        bias = obs_raw - eps_exp
        bias_se = float(np.sqrt(obs_se**2 + se_used**2))
        details["observational"] = {"elasticity": observational.get("elasticity"), "epsilon_raw": obs_raw,
                                    "std_err": observational.get("std_err"),
                                    "ci95": (observational.get("details") or {}).get("ci95")}
        details["bias_estimate"] = num(bias, 4)
        details["bias_se"] = num(bias_se, 4)
        details["bias_sentence"] = (
            f"The history's curve read {obs_raw:.2f}; the randomised test says {eps_exp:.2f} "
            f"(±{t_crit * se_used:.2f}). "
            + ("The history was too flat by about " + f"{bias:.2f}, in the direction that argued for raising prices."
               if bias > 2 * bias_se else
               "The history was too steep by about " + f"{-bias:.2f}." if bias < -2 * bias_se else
               "The two agree within their uncertainty."))
    details["basis"] = (f"{len(points)} randomised blocks of {points[0]['days'] if points else 0} counted days; "
                        f"slope on the assigned price (HC3, t({dof})), permutation sd over {perm['permutations']} "
                        f"relabelings; first stage {beta_fs:.3f}")
    return {**base, "status": "ok", "elasticity": num(eps_exp, 4), "std_err": num(se_used, 4),
            "r_squared": itt.get("r_squared"), "price_cv": itt.get("price_cv"), "details": details}


def run(data: dict, price_tests: list[dict], observational_rows: list[dict] | None = None) -> list[dict]:
    """One analysis per randomised test on file, from the settlement file."""
    obs_by_sku = {r["item_id"]: r for r in (observational_rows or []) if r.get("level") == "sku"}
    out = []
    for t in price_tests or []:
        d = t.get("design")
        if not d or d.get("status") != "ok":
            continue
        sku = t.get("sku") or d.get("sku")
        daily = daily_sku_series(data.get("settlement_transactions") or [], sku, d["start_date"], d["end_date"])
        result = analyze({**d, "sku": sku}, daily, obs_by_sku.get(sku))
        out.append({**result, "test_id": t.get("id"), "start_date": d["start_date"], "end_date": d["end_date"]})
    return out
