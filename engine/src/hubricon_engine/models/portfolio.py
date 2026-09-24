"""The sweep as one book.

Every directive is sized and guarded on its own: a price step against 15% of
its own SKU's monthly net, a reorder against the cash cone one wire at a
time. A seller executes the sweep all at once, and a book is not the sum of
its trades' separate risks. Two things compound across a book that no single
directive can see:

  shared estimation error  every shrunk elasticity leans on the same pool
                           mean, and every corrected one on the same
                           reaction-bias estimate; an error there moves every
                           price step in the same direction at once
  shared cash              forty reorders that each leave the cone above its
                           ruin line can, wired together, take it below

This module draws the book: each promised directive as a split-normal on its
own 5th/50th/95th percentiles, with the part of a price step's uncertainty
that is shared across the catalogue (its elasticity's common error, as a
share of its whole error) loaded on one common factor, everything else
independent. The shared share is taken as an upper bound — all of the step's
spread is treated as elasticity-driven — so the book's band errs wide, which
is the direction to be wrong in on a figure a client plans against.

It publishes a band per group (price steps, stock protection, markdowns,
advertising, fee avoidance, recovery) and for the standing book — the
directives the mandate lets the engine execute without asking — its 5%
expected shortfall against the client's budget: their risk-budget share of
the catalogue's trailing monthly net. When the standing book breaches it,
directives are demoted to explicit, largest tail contribution first, until
it does not. Then the sweep's cash moves together: when their combined effect
on the cone would take P(ruin) past the warning line, the moves with the
least profit per dollar of cash are deferred — asked for, not wired — until
it would not.

WHAT IT CANNOT TELL YOU. Dependence the engine does not model (a competitor
cutting across the whole category, a platform fee change) is in the stress
table, not here; a directive with no band enters at its point value.
"""
import numpy as np

from .cashflow import RUIN_WARNING, ruin_delta
from .common import num
from .pricing_engine import RISK_BUDGET_SHARE, trailing_monthly_net

BOOK_DRAWS = 4000
BOOK_SEED = 20260924
GROUPS = {
    "price_steps": ("price_step",),
    "markdowns": ("markdown",),
    "advertising": ("budget_reallocation", "campaign_trim", "ad_bleed_terms", "branded_pause", "spend_step"),
    "fee_avoidance": ("low_inventory_fee", "aged_surcharge", "peak_storage_premium", "fee_anomaly",
                      "referral_anomaly", "negative_margin_sku", "sku_exit"),
    "recovery": ("recovery_filing",),
}
Z95 = 1.6448536269514722


def key(d: dict) -> str:
    ev = d.get("evidence") or {}
    return f"{d['kind']}|{ev.get('sku') or ev.get('campaign_name') or ''}|{ev.get('reason') or ''}"


def group_of(d: dict) -> str:
    if d["kind"] == "price_step" and (d.get("evidence") or {}).get("reason") == "stretch":
        return "stock_protection"
    for g, kinds in GROUPS.items():
        if d["kind"] in kinds:
            return g
    return "other"


def _band(d: dict):
    """(p5, p50, p95) of a promise, the point three times when it has no band."""
    ev = d.get("evidence") or {}
    p50 = d.get("expected_impact_usd")
    if p50 is None:
        return None
    p5, p95 = ev.get("delta_p5"), ev.get("delta_p95")
    if p5 is None or p95 is None:
        return float(p50), float(p50), float(p50)
    return float(p5), float(p50), float(p95)


def _common_share(d: dict) -> float:
    ev = d.get("evidence") or {}
    if d["kind"] not in ("price_step", "markdown"):
        return 0.0
    se = ev.get("std_err") or (ev.get("mc_inputs") or {}).get("eps_se")
    common = ev.get("eps_common_se")
    if not se or common is None:
        return 0.0
    return float(min(1.0, (float(common) / float(se)) ** 2))


def draws(drafts: list[dict], n: int = BOOK_DRAWS, seed: int = BOOK_SEED):
    """One column of profit draws per promised directive, in draft order, on a
    shared common factor. Returns (keys, matrix n × k)."""
    rng = np.random.default_rng(seed)
    z_common = rng.standard_normal(n)
    keys, cols = [], []
    for d in drafts:
        b = _band(d)
        if b is None:
            continue
        p5, p50, p95 = b
        rho = _common_share(d)
        own = np.random.default_rng([seed, len(keys) + 1]).standard_normal(n)
        z = np.sqrt(rho) * z_common + np.sqrt(1.0 - rho) * own
        lo, hi = max(p50 - p5, 0.0) / Z95, max(p95 - p50, 0.0) / Z95
        cols.append(p50 + np.where(z < 0, lo, hi) * z)
        keys.append(key(d))
    return keys, (np.column_stack(cols) if cols else np.zeros((n, 0)))


def _summary(x: np.ndarray) -> dict:
    srt = np.sort(x)
    tail = srt[: max(1, int(0.05 * len(srt)))]
    return {"p5": num(float(np.quantile(x, 0.05))), "p50": num(float(np.quantile(x, 0.5))),
            "p95": num(float(np.quantile(x, 0.95))), "es5": num(float(tail.mean())),
            "p_loss": num(float(np.mean(x < 0)), 4)}


def run(drafts: list[dict], margins: list[dict], cash: dict | None = None, risk_share: float | None = None,
        apply: bool = True) -> dict:
    share = float(risk_share) if risk_share is not None else RISK_BUDGET_SHARE
    latest = {}
    for m in margins or []:
        if m.get("sku") and (m["sku"] not in latest or str(m["period_start"]) > str(latest[m["sku"]]["period_start"])):
            latest[m["sku"]] = m
    monthly_net = sum(max(0.0, trailing_monthly_net(m) or 0.0) for m in latest.values())
    budget = share * monthly_net
    keys, mat = draws(drafts)
    if mat.shape[1] == 0:
        return {"status": "empty", "groups": {}, "members": {}, "risk_budget": num(budget)}
    by_key = {key(d): d for d in drafts}
    col = {k: i for i, k in enumerate(keys)}
    members = {}
    for k in keys:
        members.setdefault(group_of(by_key[k]), []).append(k)
    groups = {g: {**_summary(mat[:, [col[k] for k in ks]].sum(axis=1)), "n": len(ks)} for g, ks in members.items()}

    # ── the standing book against the client's budget ──
    demoted = []
    standing = [k for k in keys if by_key[k].get("mandate") == "standing"]
    def standing_es(ks):
        return float(np.sort(mat[:, [col[k] for k in ks]].sum(axis=1))[: max(1, int(0.05 * mat.shape[0]))].mean()) if ks else 0.0
    es = standing_es(standing)
    while standing and es < -budget:
        # the directive whose removal most improves the standing book's shortfall
        base_tail = np.argsort(mat[:, [col[k] for k in standing]].sum(axis=1))[: max(1, int(0.05 * mat.shape[0]))]
        worst = min(standing, key=lambda k: float(mat[base_tail, col[k]].mean()) - float(np.median(mat[:, col[k]])))
        standing.remove(worst)
        demoted.append(worst)
        es = standing_es(standing)
    if apply:
        for k in demoted:
            d = by_key[k]
            d["mandate"] = "explicit"
            d.setdefault("evidence", {})["book"] = {"demoted": True, "reason": (
                f"the standing book's 5% expected shortfall would pass the client's budget of ${budget:,.0f}")}

    # ── the sweep's cash moves together ──
    ruin = combined_ruin(drafts, cash)
    deferred = []
    if ruin and ruin["p_after"] > max(ruin["p_before"], RUIN_WARNING):
        movers = [d for d in drafts if ((d.get("evidence") or {}).get("ruin_delta") or {}).get("amount", 0) > 0]
        movers.sort(key=lambda d: (float(d.get("expected_impact_usd") or 0)
                                   / max(float(d["evidence"]["ruin_delta"]["amount"]), 1.0)))
        for d in movers:
            if ruin["p_after"] <= max(ruin["p_before"], RUIN_WARNING):
                break
            deferred.append(key(d))
            if apply:
                d["mandate"] = "explicit"
                d["evidence"].setdefault("book", {})["deferred_for_cash"] = True
            ruin = combined_ruin(drafts, cash, skip=set(deferred))
    return {
        "status": "ok", "groups": groups, "members": members,
        "total": _summary(mat.sum(axis=1)),
        "standing": {**_summary(mat[:, [col[k] for k in standing]].sum(axis=1)), "n": len(standing)} if standing else None,
        "es5": num(es), "risk_budget": num(budget), "risk_budget_share": share,
        "monthly_net": num(monthly_net), "demoted": demoted, "deferred_for_cash": deferred, "ruin": ruin,
        "draws": BOOK_DRAWS, "seed": BOOK_SEED,
        "basis": ("each promise a split normal on its own 5th/50th/95th percentiles; a price step's shared "
                  "elasticity error on one common factor, taken as an upper bound; the standing book's 5% "
                  "expected shortfall against the client's risk-budget share of trailing monthly net"),
    }


def combined_ruin(drafts: list[dict], cash: dict | None, skip: set | None = None) -> dict | None:
    """P(ruin) with every cash move of the sweep applied at once, read off the
    cone's stored ladder. The ladder holds one wire per day, so the moves are
    taken together at the earliest outflow's day — every dollar paid sooner
    than it will be, which can only overstate the ruin. None without a cone."""
    moves = [(int(rd.get("day") or 0), float(rd["amount"])) for d in drafts
             if key(d) not in (skip or set())
             for rd in [((d.get("evidence") or {}).get("ruin_delta") or {})] if rd.get("amount") is not None]
    if not cash or not moves:
        return None
    out = sum(a for _, a in moves if a > 0)
    inflow = sum(-a for _, a in moves if a < 0)
    first = min((day for day, a in moves if a > 0), default=0)
    rd = ruin_delta(cash, first, out)
    if rd is None:
        return None
    return {"p_before": float(rd["p_ruin_before"]), "p_after": float(rd["p_ruin_after"]),
            "outflow": num(out), "inflow_not_counted": num(inflow), "n_moves": len(moves), "day": first,
            "basis": "every outflow of the sweep at the earliest outflow's day; inflows not counted"}
