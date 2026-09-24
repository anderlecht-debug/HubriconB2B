"""Joint replenishment and the freight choice: the purchase order as a supplier
actually writes it.

The newsvendor in inventory_econ sizes each SKU on its own — an order-up-to
level at the service level the margin justifies. A real purchase order is
none of that. It has a minimum quantity, a case pack, a price break at some
volume, it shares a wire (and often a container) with every other SKU from the
same supplier, and it can come by air or by sea. This module takes the
per-SKU order the newsvendor already sized and answers those four questions
on the same simulated demand, so nothing is re-simulated and nothing can
disagree with the stockout model.

THE TERMS come from the client's cost sheet — optional columns `supplier`,
`moq_units`, `case_pack_units`, `price_break_qty`, `price_break_unit_cost_usd`,
`air_freight_per_unit_usd`, `air_lead_time_days` (cogs-template.csv). The
existing `inbound_freight_per_unit_usd` and `supplier_lead_time_days` are the
default mode, sea. A SKU whose sheet leaves the terms blank is priced as
before and says `no_supplier_terms`; one with no air option says
`no_freight_options`. Nothing is invented for a blank column.

ROUNDING. q rises to the MOQ and then to a whole number of cases. The cost of
the forced extra units is the newsvendor's own overage cost on them:
C_o × (E[max(0, q − D)] − E[max(0, q* − D)]) on the cycle's demand draws,
published with its band, so a client sees what the supplier's minimum is
costing them per cycle.

THE PRICE BREAK. Take it when the unit saving on every unit of the larger
order exceeds the extra expected overage cost plus the capital on the larger
wire; P(saving > 0) from the same draws. Both wires are shown.

THE JOINT ORDER. A can-order policy per supplier: when any SKU of the supplier
hits its reorder point, every sibling whose position is below its order-up-to
less one review period of demand is topped up in the same wire. The count of
wire events over the horizon, against ordering every SKU on its own clock, is
what the joint order saves — and every wire event is a fee, a container
minimum, and a week of someone's attention.

EXPEDITE. Air against sea for a SKU at stockout risk, on common random numbers:
the stockout units avoided — E[max(0, D_sea − position)] − E[max(0, D_air −
position)] — times the margin per unit plus the low-inventory fee, less the
freight premium on the order. Recommended when the median is positive and at
least 60% of draws agree. No dollars are promised on it: the avoided stockout
is the counterfactual MATH_METHODS.md §10 lists as unobservable, and the
directive says the expected net and banks nothing.

WHAT IT CANNOT TELL YOU. Container capacity (no column carries it), supplier
lead-time variance beyond the assumed 20%, and whether the price break is
still on offer.
"""

from datetime import date

import numpy as np

from . import dependence
from . import fee_schedule as fees
from .common import num
from .inventory_econ import ANNUAL_CAPITAL_RATE, LEAD_TIME_CV, REVIEW_PERIOD_DAYS

EXPEDITE_MIN_P = 0.6
EXPEDITE_DRAWS = 20000
REPLENISH_SEED = 20260911
HORIZON_DAYS = 180
TERM_FIELDS = ("supplier", "moq_units", "case_pack_units", "price_break_qty", "price_break_unit_cost_usd",
               "air_freight_per_unit_usd", "air_lead_time_days")


def supplier_groups(cogs_rows: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in cogs_rows or []:
        if r.get("supplier"):
            out.setdefault(str(r["supplier"]).strip(), []).append(r["sku"])
    return {k: sorted(v) for k, v in out.items()}


def _ladder_quantile(ladder: list, q: float) -> float:
    """F⁻¹(q) by interpolation on the stored demand ladder."""
    qs = np.array([p[0] for p in ladder], dtype=float)
    xs = np.array([p[1] for p in ladder], dtype=float)
    return float(np.interp(q, qs, xs))


def _overage(demand: np.ndarray, q: float) -> float:
    return float(np.mean(np.maximum(0.0, q - demand)))


def round_to_terms(q_star: int, terms: dict, c_o: float, demand: np.ndarray) -> dict:
    moq = int(terms.get("moq_units") or 0)
    case = int(terms.get("case_pack_units") or 0)
    q = max(int(q_star), moq)
    if case > 0 and q % case:
        q = (q // case + 1) * case
    extra = q - int(q_star)
    cost = c_o * (_overage(demand, q) - _overage(demand, q_star)) if extra > 0 else 0.0
    return {"q_star": int(q_star), "q": int(q), "forced_units": int(extra), "moq": moq, "case_pack": case,
            "moq_cost": num(cost), "basis": "overage cost on the units the supplier's terms force, on the cycle's demand draws"}


def price_break(q: int, unit_cost: float, terms: dict, c_o: float, demand: np.ndarray,
                cycle_days: float) -> dict | None:
    q_break = terms.get("price_break_qty")
    c_break = terms.get("price_break_unit_cost_usd")
    if not q_break or c_break is None or int(q_break) <= q or float(c_break) >= unit_cost:
        return None
    q_break = int(q_break)
    saving = (unit_cost - float(c_break)) * q_break
    extra_overage = c_o * (_overage(demand, q_break) - _overage(demand, q))
    extra_capital = (q_break - q) * float(c_break) * ANNUAL_CAPITAL_RATE * cycle_days / 365
    net = saving - extra_overage - extra_capital
    # the draws behind P(net > 0): the overage term is the only random one
    per_draw = saving - c_o * (np.maximum(0.0, q_break - demand) - np.maximum(0.0, q - demand)) - extra_capital
    return {"q_break": q_break, "unit_cost_break": float(c_break), "saving": num(saving),
            "extra_overage": num(extra_overage), "extra_capital": num(extra_capital), "net": num(net),
            "net_p5": num(float(np.quantile(per_draw, 0.05))), "net_p95": num(float(np.quantile(per_draw, 0.95))),
            "p_positive": num(float(np.mean(per_draw > 0)), 4),
            "take": bool(net > 0 and float(np.mean(per_draw > 0)) >= EXPEDITE_MIN_P),
            "wire_at_q": num(q * unit_cost), "wire_at_break": num(q_break * float(c_break))}


def joint_orders(supplier: str, rows: list[dict], horizon_days: int = HORIZON_DAYS) -> dict:
    """Wire events over the horizon, independent vs can-order, at median rates."""
    independent, joint = 0, 0
    clocks = {}
    for r in rows:
        rate = float(r.get("rate_mean") or 0)
        qty = int(r.get("order_qty_econ") or 0) or int(r.get("order_up_to") or 0)
        position = float(r.get("position") or 0)
        rop = float(r.get("reorder_point") or 0)
        if rate <= 0 or qty <= 0:
            continue
        first = max(0.0, (position - rop) / rate)
        cycle = max(1.0, qty / rate)
        clocks[r["sku"]] = {"next": first, "cycle": cycle, "rate": rate, "qty": qty,
                            "order_up_to": float(r.get("order_up_to") or position + qty),
                            "position": position, "rop": rop}
        t = first
        while t < horizon_days:
            independent += 1
            t += cycle
    # can-order: at each trigger, siblings within one review period of their
    # reorder point join the wire and reset their clocks
    state = {k: dict(v) for k, v in clocks.items()}
    events = []
    while True:
        due = [k for k, v in state.items() if v["next"] < horizon_days]
        if not due:
            break
        k0 = min(due, key=lambda k: state[k]["next"])
        t = state[k0]["next"]
        members = [k0]
        for k, v in state.items():
            if k == k0:
                continue
            # would this SKU hit its own reorder point within a review period?
            if v["next"] - t <= REVIEW_PERIOD_DAYS:
                members.append(k)
        for k in members:
            state[k]["next"] = t + state[k]["cycle"]
        events.append({"day": round(t, 1), "skus": sorted(members)})
        joint += 1
    return {"supplier": supplier, "n_skus": len(clocks), "horizon_days": horizon_days,
            "wire_events_independent": independent, "wire_events_joint": joint,
            "wire_events_saved": max(0, independent - joint), "events": events[:24],
            "basis": "can-order policy at median rates: a sibling due within one review period joins the wire"}


def expedite(row: dict, terms: dict, rng: np.random.Generator, draws: int = EXPEDITE_DRAWS,
             cliffs: bool = True) -> dict:
    air_freight = terms.get("air_freight_per_unit_usd")
    air_lead = terms.get("air_lead_time_days")
    sea_freight = float(terms.get("inbound_freight_per_unit_usd") or 0)
    if air_freight is None or not air_lead:
        return {"status": "no_freight_options"}
    rate, sd = float(row.get("rate_mean") or 0), float(row.get("rate_sd") or 0)
    if rate <= 0 or row.get("unit_margin") is None:
        return {"status": "insufficient_data"}
    position = float(row.get("position") or 0)
    sea_lead = float(row.get("lead_time_days") or 45)
    q = int(row.get("order_qty_econ") or row.get("order_up_to") or 0)
    if q <= 0:
        return {"status": "no_order_due"}
    n = int(draws)
    rates = dependence.correlated_rates(rng, [rate], [sd], (n,), 0.0)[0]
    # the same lognormal shock scales both lead times: common random numbers
    lead_shock = rng.lognormal(mean=0.0, sigma=LEAD_TIME_CV, size=n)
    u = rng.random(n)
    d_sea = _poisson_by_inversion(rates * sea_lead * lead_shock, u)
    d_air = _poisson_by_inversion(rates * float(air_lead) * lead_shock, u)
    short_sea = np.maximum(0.0, d_sea - position)
    short_air = np.maximum(0.0, d_air - position)
    lilf = fees.LOW_INVENTORY_FEE_PER_UNIT.get(row.get("size_tier") or "standard", fees.LOW_INVENTORY_FEE_PER_UNIT["standard"])["lt14"] if cliffs else 0.0
    per_unit = float(row["unit_margin"]) + lilf
    premium = (float(air_freight) - sea_freight) * q
    net = (short_sea - short_air) * per_unit - premium
    p_pos = float(np.mean(net > 0))
    median = float(np.quantile(net, 0.5))
    return {"status": "ok", "recommend_air": bool(median > 0 and p_pos >= EXPEDITE_MIN_P),
            "net_p5": num(float(np.quantile(net, 0.05))), "net_p50": num(median), "net_p95": num(float(np.quantile(net, 0.95))),
            "p_positive": num(p_pos, 4), "freight_premium": num(premium),
            "stockout_units_sea": num(float(short_sea.mean()), 2), "stockout_units_air": num(float(short_air.mean()), 2),
            "p_stockout_sea": num(float(np.mean(d_sea > position)), 4), "p_stockout_air": num(float(np.mean(d_air > position)), 4),
            "sea_lead_days": sea_lead, "air_lead_days": float(air_lead), "order_qty": q,
            "mc_inputs": {"draws": n, "seed": REPLENISH_SEED},
            "basis": ("stockout units avoided over the sea lead time versus the air lead time, on common random "
                      "numbers, at margin plus the low-inventory fee, less the freight premium on the order; "
                      "the avoided stockout is not banked")}


def _poisson_by_inversion(lam: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Poisson draws coupled across two rates through one uniform per draw
    (normal approximation with continuity correction, exact enough here)."""
    from scipy.special import erfinv
    z = np.sqrt(2.0) * erfinv(np.clip(2.0 * u - 1.0, -0.999999, 0.999999))
    return np.clip(np.rint(lam + np.sqrt(np.maximum(lam, 1e-12)) * z), 0, None)


def run(inv_econ: dict | None, data: dict, rng: np.random.Generator | None = None,
        today: date | None = None, channel: str = "amazon") -> dict:
    from .. import channels

    rng = rng or np.random.default_rng(REPLENISH_SEED)
    cliffs = channels.has_fee_cliffs(channel)
    terms_by_sku = {r["sku"]: r for r in (data.get("cogs_inputs") or [])}
    rows_in = [r for r in (inv_econ or {}).get("rows", []) if r.get("status") == "ok" and r.get("order_up_to") is not None]
    groups = supplier_groups(list(terms_by_sku.values()))
    by_sku = {r["sku"]: r for r in rows_in}

    out_rows = []
    for r in rows_in:
        sku = r["sku"]
        t = terms_by_sku.get(sku) or {}
        has_terms = any(t.get(k) is not None for k in ("moq_units", "case_pack_units", "price_break_qty"))
        row = {"sku": sku, "supplier": t.get("supplier"), "status": "ok" if has_terms else "no_supplier_terms",
               "order_qty_econ": r.get("order_qty_econ"), "wire_econ": r.get("wire_econ")}
        ladder = (r.get("details") or {}).get("demand_ladder")
        # rebuild the cycle's demand draws from the stored ladder: enough for
        # expectations of overage, and no second simulation
        if ladder:
            u = rng.random(4000)
            demand = np.array([_ladder_quantile(ladder, float(x)) for x in np.clip(u, ladder[0][0], ladder[-1][0])])
        else:
            demand = None
        q_star = int(r.get("order_qty_econ") or 0)
        if has_terms and demand is not None and q_star > 0:
            row["terms"] = round_to_terms(q_star, t, float(r.get("c_o") or 0), demand)
            row["order_qty"] = row["terms"]["q"]
            row["wire"] = num(row["order_qty"] * float(r.get("unit_cost") or 0))
            pb = price_break(row["order_qty"], float(r.get("unit_cost") or 0), t, float(r.get("c_o") or 0), demand,
                             float(r.get("lead_time_days") or 45) + REVIEW_PERIOD_DAYS)
            row["price_break"] = pb
            if pb and pb["take"]:
                row["order_qty"] = pb["q_break"]
                row["wire"] = pb["wire_at_break"]
        else:
            row["order_qty"] = q_star
            row["wire"] = r.get("wire_econ")
        row["expedite"] = expedite(r, t, rng, cliffs=cliffs)
        out_rows.append(row)

    suppliers = []
    for name, skus in groups.items():
        members = [by_sku[s] for s in skus if s in by_sku]
        if len(members) >= 2:
            suppliers.append(joint_orders(name, members))
    n_terms = sum(1 for r in out_rows if r["status"] == "ok")
    return {
        "status": "ok" if out_rows else "insufficient_data",
        "as_of": (today or date.today()).isoformat(),
        "seed": REPLENISH_SEED,
        "rows": out_rows,
        "suppliers": suppliers,
        "summary": {
            "n_skus": len(out_rows), "n_with_terms": n_terms,
            "moq_cost_total": num(sum(float((r.get("terms") or {}).get("moq_cost") or 0) for r in out_rows)),
            "price_breaks_taken": [r["sku"] for r in out_rows if (r.get("price_break") or {}).get("take")],
            "expedite_air": [r["sku"] for r in out_rows if (r.get("expedite") or {}).get("recommend_air")],
            "wire_events_saved": sum(s["wire_events_saved"] for s in suppliers),
            "n_suppliers": len(suppliers),
        },
        "assumptions": [
            "Supplier terms come from the client's cost sheet; a blank column is priced as absent, never guessed",
            "The joint order is a can-order policy at median rates; a sibling due within one review period joins the wire",
            "Air versus sea is valued on the stockout units avoided at margin plus the low-inventory fee; the avoided "
            "stockout is not banked",
        ],
    }
