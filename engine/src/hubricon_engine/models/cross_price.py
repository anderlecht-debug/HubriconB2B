"""Cross-price effects inside a variant family: the demand a price move sends
to a sibling.

A colour or size variant does not have its own demand curve so much as a share
of the family's. Raise the price on Blue and some of Blue's buyers take Red, so
the per-SKU optimum in §3 overstates the gain from a rise (the lost units are
partly recovered on Red) and understates the loss from a cut (the gained units
are partly stolen from Red). MATH_METHODS.md §10 listed this as a thing the
engine could not tell you. Where a variant family exists, it now can.

THE MODEL. Within a family g, children i, periods t:

    log q_it = α_i + ε_own·log p_it + ε_cross·log p̃_{−i,t} + e_it

with p̃_{−i,t} the revenue-weighted mean of the SIBLINGS' log prices (weights
fixed over the window, so the index moves only when prices move). One own and
one cross elasticity per family, because the data is thin: four children over
eight periods is thirty-two observations, and a full matrix of cross terms
would have more parameters than that. The child intercepts are absorbed by a
within transformation (demeaning each child's series), the two slopes are fitted
by OLS on the demeaned regressors, the standard errors are HC3 and the interval
is Student-t on N − n_children − 2 degrees of freedom — the same estimator as
§2, for the same reasons. The family's ε_cross is then shrunk toward the
catalogue's cross-elasticity by the empirical-Bayes rule of §2 (a family fitted
from thirty-two points borrows from the others), and the sign is whatever the
data says: substitutes are positive, complements negative.

WHERE THE FAMILY COMES FROM. Amazon: `asin_traffic.parent_asin` groups child
ASINs, and `sku_economics.asin` maps each SKU to its child. Shopify: the product
handle sits in the `asin` column of the cost sheet and the stock snapshot, and
`common.sku_asin_bridge` returns it. No mapping at all is `no_variant_mapping`
for the whole model — the brief's `insufficient_data` — and the pricing engine
runs exactly as before.

HOW PRICING USES IT. pricing_engine.price_move takes the family's ε_cross with
its posterior and the siblings' baseline volumes and contributions, and every
candidate step is valued on OWN + SIBLING profit: sibling j's units move by
(p_new/p_0)^(ε_cross·w_ij) − 1, w_ij being i's share of j's sibling index. The
step is sized on the total. When the own-only objective would have moved and
the total will not, the move is refused with the status `cannibalisation` and
the sibling is named — a finding, not a silence.

WHAT IT CANNOT TELL YOU. It is one cross term for the whole family: a family
where Red steals from Blue but not from Green gets the average. Substitution
from outside the family — a competitor's listing — is not in any export and is
not modelled. And the observational caveat of §2 applies to both slopes.
"""

import numpy as np
from scipy import stats

from .common import num, period_days, sku_asin_bridge
from .elasticity import MIN_LEVERAGE_SLACK, eb_shrink

MIN_CHILDREN = 2
MIN_PERIODS = 5
MIN_SIBLING_PRICE_SD = 0.02      # log scale ≈ coefficient of variation
MIN_POOL_FAMILIES = 3
CI_LEVEL = 0.95
# A family whose shrunk cross-elasticity sits this many of its own standard
# errors from zero is published as `identified`. Every fitted family's
# posterior enters the price steps of its children whether identified or
# not, and a family too thin to fit at all carries the catalogue's prior —
# the pool mean with the between-family spread and the pool mean's own
# error as its standard error.
#
# Corrected 2026-09-24 (the same day the gate was added). For a few hours
# only identified families reached a step, on the reasoning that an
# unidentified estimate is noise. The model-risk bench showed the opposite:
# leaving a family out sets its cross-elasticity to zero WITH NO
# UNCERTAINTY, the most overconfident choice there is. On the clean world
# the truth of a step sat inside its promised 90% band for 49% of the steps
# whose family was left out and 75% of those whose family was used; the
# omitted sibling effect was as large as the step's own. An estimate you do
# not trust enters with the uncertainty that says so, not as a zero.
MIN_CROSS_T = 2.0


def families(data: dict) -> dict[str, list[str]]:
    """{family_id: [sku, ...]} with at least two members."""
    econ = data.get("sku_economics") or []
    bridge = sku_asin_bridge(econ, data.get("cogs_inputs") or [])
    parent_of_child = {r["child_asin"]: r["parent_asin"] for r in (data.get("asin_traffic") or [])
                       if r.get("child_asin") and r.get("parent_asin")}
    out: dict[str, set] = {}
    for sku, asin in bridge.items():
        family = parent_of_child.get(asin) or (asin if asin and not parent_of_child else None)
        if family:
            out.setdefault(str(family), set()).add(sku)
    # Shopify: the bridge value IS the handle, and several SKUs share it
    if not parent_of_child:
        out = {}
        for sku, handle in bridge.items():
            if handle:
                out.setdefault(str(handle), set()).add(sku)
    return {f: sorted(m) for f, m in out.items() if len(m) >= MIN_CHILDREN}


def _series(data: dict) -> dict[str, dict[str, tuple[float, float, float]]]:
    """{sku: {period_start: (price, units_per_day, revenue)}}."""
    out: dict[str, dict] = {}
    for r in data.get("sku_economics") or []:
        units = r.get("units_sold")
        if not units or units <= 0:
            continue
        price = r.get("avg_sales_price") or ((r.get("sales") or 0) / units)
        if not price or price <= 0:
            continue
        days = period_days(str(r["period_start"]), str(r["period_end"]))
        out.setdefault(r["sku"], {})[str(r["period_start"])] = (float(price), float(units) / days,
                                                               float(r.get("sales") or 0))
    return out


def fit_family(family_id: str, members: dict[str, dict]) -> dict:
    children = sorted(members)
    shared = sorted(set.intersection(*(set(v) for v in members.values()))) if members else []
    base = {"family": family_id, "children": children, "n_children": len(children),
            "n_periods": len(shared), "details": {}}
    if len(children) < MIN_CHILDREN or len(shared) < MIN_PERIODS:
        return {**base, "status": "insufficient_data"}
    # revenue weights over the window, fixed
    revenue = {c: sum(members[c][t][2] for t in shared) for c in children}
    total_rev = sum(revenue.values())
    if total_rev <= 0:
        return {**base, "status": "insufficient_data"}
    logp = {c: np.array([np.log(members[c][t][0]) for t in shared]) for c in children}
    logq = {c: np.array([np.log(members[c][t][1]) for t in shared]) for c in children}
    weights = {}   # w[i][j]: share of j in i's sibling index
    rows_y, rows_own, rows_sib = [], [], []
    for i in children:
        others = [j for j in children if j != i]
        wsum = sum(revenue[j] for j in others)
        w = {j: (revenue[j] / wsum if wsum > 0 else 1.0 / len(others)) for j in others}
        weights[i] = w
        sib = sum(w[j] * logp[j] for j in others)
        rows_y.append(logq[i] - logq[i].mean())
        rows_own.append(logp[i] - logp[i].mean())
        rows_sib.append(sib - sib.mean())
    y = np.concatenate(rows_y)
    x_own = np.concatenate(rows_own)
    x_sib = np.concatenate(rows_sib)
    n = len(y)
    base["details"]["sibling_price_sd"] = num(float(x_sib.std()), 4)
    base["details"]["own_price_sd"] = num(float(x_own.std()), 4)
    if float(x_sib.std()) < MIN_SIBLING_PRICE_SD or float(x_own.std()) <= 0:
        return {**base, "status": "insufficient_price_variation"}
    X = np.column_stack([x_own, x_sib])
    dof = n - len(children) - 2
    if dof < 1:
        return {**base, "status": "insufficient_data"}
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    hat = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    slack = 1.0 - hat
    if np.min(slack) <= MIN_LEVERAGE_SLACK:
        cov = float(resid @ resid) / dof * xtx_inv
        se_est = "classical_hc3_degenerate"
    else:
        omega = (resid / slack) ** 2
        cov = xtx_inv @ (X.T * omega) @ X @ xtx_inv
        se_est = "HC3"
    se_own, se_cross = float(np.sqrt(max(cov[0, 0], 0))), float(np.sqrt(max(cov[1, 1], 0)))
    se_cross_classical = float(np.sqrt(max(float(resid @ resid) / dof * xtx_inv[1, 1], 0)))
    t_crit = float(stats.t.ppf(0.5 + CI_LEVEL / 2, dof))
    return {**base, "status": "ok", "eps_own": num(beta[0], 4), "se_own": num(se_own, 4),
            "eps_cross": num(beta[1], 4), "se_cross": num(se_cross, 4),
            "se_cross_classical": num(se_cross_classical, 4),
            "ci95_cross": [num(beta[1] - t_crit * se_cross, 4), num(beta[1] + t_crit * se_cross, 4)],
            "n_obs": int(n), "dof": int(dof), "t_critical": num(t_crit, 4),
            "weights": {i: {j: num(w, 4) for j, w in wi.items()} for i, wi in weights.items()},
            "details": {**base["details"], "se_estimator": se_est,
                        "basis": (f"{len(children)} children × {len(shared)} shared periods, within-transformed; "
                                  f"one own and one cross elasticity per family; t({dof})")}}


def run(data: dict, elasticity_rows: list[dict] | None = None, seasonal: dict | None = None) -> dict:
    from .data_quality import clean_for_fitting
    from .seasonality import deseasonalise_economics
    data, _ = clean_for_fitting(data)
    data, season_note = deseasonalise_economics(data, seasonal)
    fams = families(data)
    if not fams:
        return {"status": "no_variant_mapping", "families": [], "by_sku": {},
                "basis": "no parent ASIN or product handle links any two SKUs; per-SKU pricing runs unchanged"}
    series = _series(data)
    fits = [fit_family(f, {c: series.get(c, {}) for c in members}) for f, members in sorted(fams.items())]
    ok = [f for f in fits if f["status"] == "ok"]
    prior = None
    if len(ok) >= MIN_POOL_FAMILIES:
        eb = eb_shrink([f["eps_cross"] for f in ok], [f["se_cross"] for f in ok],
                       pool_ses=[f.get("se_cross_classical") or f["se_cross"] for f in ok])
        prior = {"eps_cross": num(eb["mu"], 4), "se_cross": num(float(np.sqrt(eb["tau2"] + eb["var_mu"])), 4)}
        for f, w, sh, se in zip(ok, eb["weights"], eb["shrunk"], eb["post_se"]):
            f["eps_cross_raw"], f["se_cross_raw"] = f["eps_cross"], f["se_cross"]
            f["eps_cross"], f["se_cross"] = num(float(sh), 4), num(float(se), 4)
            f["shrinkage_weight"] = num(float(w), 4)
            f["pooled_eps_cross"], f["tau2"] = num(eb["mu"], 4), num(eb["tau2"], 6)
            f["ci95_cross"] = [num(f["eps_cross"] - f["t_critical"] * f["se_cross"], 4),
                               num(f["eps_cross"] + f["t_critical"] * f["se_cross"], 4)]
            f["shrinkage"] = "empirical_bayes"
    else:
        for f in ok:
            f["shrinkage"], f["shrinkage_weight"] = "none_pool_too_small", 1.0
    for f in ok:
        se = float(f["se_cross"] or 0)
        f["t_cross"] = num(float(f["eps_cross"]) / se, 3) if se > 0 else None
        f["identified"] = bool(se > 0 and abs(float(f["eps_cross"])) >= MIN_CROSS_T * se)
    by_sku = {}
    for f in ok:
        for i in f["children"]:
            by_sku[i] = {"family": f["family"], "eps_cross": f["eps_cross"], "se_cross": f["se_cross"],
                         "ci95_cross": f["ci95_cross"], "dof": f["dof"], "eps_own_family": f["eps_own"],
                         "basis": "family fit" if f["identified"] else "family fit, not separable from zero",
                         # w[j][i]: how much of sibling j's index is THIS SKU's price
                         "siblings": [{"sku": j, "weight": f["weights"][j][i]} for j in f["children"] if j != i]}
    # families too thin to fit carry the catalogue's prior predictive
    n_prior = 0
    if prior is not None:
        revenue = {}
        for sku, per in series.items():
            revenue[sku] = sum(v[2] for v in per.values())
        for fam, members in fams.items():
            if any(f["family"] == fam and f["status"] == "ok" for f in fits) or len(members) < MIN_CHILDREN:
                continue
            for i in members:
                others = [j for j in members if j != i]
                if not others:
                    continue
                sibs = []
                for j in others:
                    peers = [x for x in members if x != j]
                    tot = sum(revenue.get(x, 0.0) for x in peers)
                    sibs.append({"sku": j, "weight": num(revenue.get(i, 0.0) / tot if tot > 0 else 1.0 / len(peers), 4)})
                by_sku[i] = {"family": fam, "eps_cross": prior["eps_cross"], "se_cross": prior["se_cross"],
                             "ci95_cross": [num(prior["eps_cross"] - 1.96 * prior["se_cross"], 4),
                                            num(prior["eps_cross"] + 1.96 * prior["se_cross"], 4)],
                             "dof": None, "eps_own_family": None, "basis": "catalogue prior (family not fitted)",
                             "siblings": sibs}
                n_prior += 1
    return {"status": "ok" if ok else "insufficient_data", "families": fits, "by_sku": by_sku,
            "n_families": len(fams), "n_fitted": len(ok), "n_identified": sum(1 for f in ok if f["identified"]),
            "n_on_prior": n_prior, "prior": prior, "min_t": MIN_CROSS_T,
            "seasonal_adjustment": season_note,
            "basis": ("one own and one cross elasticity per variant family, HC3 and Student-t, families shrunk "
                      "toward the catalogue cross-elasticity; substitutes read positive")}
