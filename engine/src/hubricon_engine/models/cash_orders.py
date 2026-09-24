"""Inventory under a cash budget: the order set the cash actually supports.

The cash cone and the order-sizing model did not talk to each other. The
newsvendor recommended an order-up-to level per SKU and the cone then warned
that the wires it implied might cross zero — "you may need bridge capital" —
and stopped there. When a client cannot fund every order, the right answer is
the same service-level mathematics with one more constraint, and it turns the
warning into an action: here is the order set your cash supports, here is what
it defers, and here is the bridge that would fund the rest.

THE PROBLEM. Maximise Σ_i E[profit_i(Q_i)] subject to Σ_i c_i·Q_i ≤ K, each
E[profit_i] the newsvendor's. The Lagrangian has a shadow price of cash λ ≥ 0,
and the first-order condition per SKU is

    F_i(Q_i) = (C_u,i − λ·c_i) / (C_u,i + C_o,i)

— the critical fractile with the cash a unit ties up priced at λ. Q_i(λ) is
read off the demand ladder the newsvendor stored (F_i⁻¹ at the funded
fractile, less the position) and the total wire W(λ) is non-increasing in λ,
so a bisection on λ finds the budget exactly. The ranking this induces is by
C_u,i / c_i: contribution at risk per dollar of inventory, which is the
gross-margin-return-on-inventory order the trade already uses, derived rather
than asserted. λ = 0 reproduces the unconstrained newsvendor to the unit.

THE BUDGET. Not a re-run of the cone (thirty-seven seconds on four hundred
SKUs). The cone already published the trough of its 5th-percentile path and
the expected shortfall behind it, both computed WITH the planned wires. If the
trough is negative, that is the cash the first cycle's wires overdraw in the
bad twentieth of paths, so K = (first-cycle wires) + min(0, trough_p5), with
the expected-shortfall variant beside it as the harsher reading. The
approximation — the wires precede the trough — is stated on the payload.

WHAT IS PUBLISHED. λ, the funded order per SKU with its service level and its
residual stockout probability (with Monte Carlo error from the ladder's own
draw count), the wire total, the deferred dollars and the bridge capital that
would fund the whole newsvendor set. No dollars are promised: the avoided
stockout is unobservable (§10 #5), so the directive that replaces the
individual reorders — `budget_order_set` — is explicit and unbankable.

REFUSALS. No cash inputs on the client (`no_cash_inputs`): the individual
reorders stand. Cash that covers every wire (`fully_funded`): likewise.
"""

import numpy as np

from .common import num
from .inventory_econ import FRACTILE_CEIL, FRACTILE_FLOOR

LAMBDA_ITERATIONS = 60
RUIN_WARNING = 0.05


def _inverse_ladder(ladder: list, q: float) -> float:
    qs = np.array([p[0] for p in ladder], dtype=float)
    xs = np.array([p[1] for p in ladder], dtype=float)
    return float(np.interp(q, qs, xs))


def _usable(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows or []:
        if r.get("status") != "ok" or (r.get("details") or {}).get("demand_ladder") is None:
            continue
        if r.get("c_u") is None or r.get("c_o") is None or not r.get("unit_cost"):
            continue
        out.append(r)
    return out


def funded_orders(rows: list[dict], lam: float) -> list[dict]:
    """Each SKU's order at shadow price λ."""
    out = []
    for r in rows:
        c_u, c_o, c = float(r["c_u"]), float(r["c_o"]), float(r["unit_cost"])
        q = (c_u - lam * c) / (c_u + c_o) if (c_u + c_o) > 0 else FRACTILE_FLOOR
        q = min(FRACTILE_CEIL, max(0.0, q))
        ladder = r["details"]["demand_ladder"]
        if q < ladder[0][0]:
            order_up_to = 0.0
        else:
            order_up_to = _inverse_ladder(ladder, q)
        position = float(r.get("position") or 0)
        qty = max(0, int(np.ceil(order_up_to - position)))
        n_sims = int(r.get("simulations") or 20000)
        out.append({"sku": r["sku"], "fractile": q, "order_qty": qty, "wire": qty * c,
                    "gmroi": c_u / c if c > 0 else None,
                    # the service level the funded order buys, and its complement
                    "p_stockout_cycle": num(1.0 - q, 4),
                    "p_stockout_mc_se": num(float(np.sqrt(q * (1 - q) / n_sims)), 5)})
    return out


def funded_set(rows: list[dict], budget: float) -> dict:
    """Bisect λ so the wires meet the budget; λ = 0 is the unconstrained set."""
    rows = _usable(rows)
    if not rows:
        return {"status": "insufficient_data", "reason": "no SKU carries a demand ladder and unit economics"}
    free = funded_orders(rows, 0.0)
    total_free = sum(o["wire"] for o in free)
    if total_free <= budget:
        return {"status": "fully_funded", "lambda": 0.0, "orders": free, "wire_total": num(total_free),
                "budget_usd": num(budget), "deferred": 0.0}
    lo, hi = 0.0, 1.0
    while sum(o["wire"] for o in funded_orders(rows, hi)) > budget and hi < 1e6:
        hi *= 2
    for _ in range(LAMBDA_ITERATIONS):
        mid = 0.5 * (lo + hi)
        if sum(o["wire"] for o in funded_orders(rows, mid)) > budget:
            lo = mid
        else:
            hi = mid
    lam = hi
    orders = funded_orders(rows, lam)
    total = sum(o["wire"] for o in orders)
    by_free = {o["sku"]: o for o in free}
    for o in orders:
        o["order_qty_unconstrained"] = by_free[o["sku"]]["order_qty"]
        o["wire_unconstrained"] = num(by_free[o["sku"]]["wire"])
        o["deferred_units"] = max(0, by_free[o["sku"]]["order_qty"] - o["order_qty"])
        o["wire"] = num(o["wire"])
        o["fractile"] = num(o["fractile"], 4)
        o["gmroi"] = num(o["gmroi"], 4)
    orders.sort(key=lambda o: -(o["gmroi"] or 0))
    return {"status": "constrained", "lambda": num(lam, 6), "orders": orders, "wire_total": num(total),
            "budget_usd": num(budget), "deferred": num(total_free - total), "unconstrained_total": num(total_free)}


def cash_budget(cash: dict | None, wires: list[dict] | None) -> dict | None:
    """K from the cone already computed: the first cycle's wires plus the
    trough's overdraft, if any."""
    if not cash:
        return None
    wires = wires or (cash.get("details") or {}).get("wires") or []
    first_cycle = {}
    for w in wires:
        if w["sku"] not in first_cycle:
            first_cycle[w["sku"]] = float(w["amount"])
    planned = sum(first_cycle.values())
    trough = cash.get("trough_p5")
    es = cash.get("trough_expected_shortfall")
    if trough is None:
        return None
    floor = float((cash.get("details") or {}).get("ruin_floor") or 0.0)
    k_p5 = planned + min(0.0, float(trough) - floor)
    k_es = planned + min(0.0, float(es) - floor) if es is not None else None
    return {"planned_first_cycle": num(planned), "trough_p5": num(trough), "trough_expected_shortfall": num(es),
            "ruin_floor": num(floor),
            "budget_p5": num(max(0.0, k_p5)), "budget_expected_shortfall": num(max(0.0, k_es)) if k_es is not None else None,
            "p_ruin": cash.get("p_ruin"),
            "basis": ("first-cycle wires plus the 5th-percentile trough's overdraft, both from the cone already "
                      "computed; the wires precede the trough, which is the approximation")}


def run(inv_econ: dict | None, cash: dict | None, today=None) -> dict:
    rows = (inv_econ or {}).get("rows") or []
    k = cash_budget(cash, None)
    if k is None:
        return {"status": "no_cash_inputs", "basis": "no cash cone on this run; the individual reorders stand"}
    fs = funded_set(rows, float(k["budget_p5"]))
    out = {"status": fs["status"], "budget": k, **{kk: v for kk, v in fs.items() if kk != "status"}}
    if fs["status"] == "constrained":
        out["bridge_capital"] = num(float(fs["unconstrained_total"]) - float(k["budget_p5"]))
        n_deferred = sum(1 for o in fs["orders"] if o["deferred_units"] > 0)
        out["basis"] = (f"the cash supports ${fs['wire_total']:,.0f} of the newsvendor's ${fs['unconstrained_total']:,.0f} "
                        f"of first-cycle orders; shadow price of cash {fs['lambda']:.4f} per dollar; capital goes first to "
                        f"the SKUs with the highest contribution at risk per inventory dollar; {n_deferred} order(s) trimmed "
                        f"or deferred; ${out['bridge_capital']:,.0f} of bridge capital would fund the rest")
    return out
