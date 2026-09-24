"""Drafts Decision Ledger directives from a run's results.

Doctrine: the client's effort is zero. A directive is a pure financial
instruction — an exact action, an exact number, the expected dollars, and
the promise that the Ledger measures what actually happened. The math
stays on our side.

Cannibalization note: true organic-vs-paid inference needs organic-rank
data we don't collect yet (the Brand Analytics "Search Query Performance"
report, or SP-API, unlocks the full posterior later). V1 flags the
highest-probability case computable today — paid spend on the client's own
branded search terms — using the documented 25–60% incrementality range,
framed as a tracked test the Ledger then measures.
"""

import hashlib
import json

import numpy as np
from datetime import date, timedelta

from . import channels
from .models import fee_schedule
from .models.common import num
from .models.margin import average_margin
from .models.pricing_engine import (
    INELASTIC_STEP,
    RISK_BUDGET_SHARE,
    STEP_CAP,
    fee_terms,
    price_move,
    trailing_monthly_net,
)

# What the standing mandate covers, read off terms.html §6 — "price steps of
# up to five percent per SKU per two-week cycle" and advertising corrections —
# rather than invented here. Everything else needs an explicit yes, and a
# price step past the cap is demoted to explicit at the point it is drafted.
STANDING = {"ad_bleed_terms", "campaign_trim", "branded_pause", "spend_step", "price_step",
            "budget_reallocation", "price_experiment", "markdown"}

# How much of a SKU's own trailing monthly net a single directive's
# 5th-percentile outcome may put at risk before the move stops travelling under
# the standing mandate and needs the client's explicit yes. The same share the
# step size is solved against in pricing_engine, enforced a second time here
# because the two rules answer to different things: one is how far to walk, this
# is whether we may walk without asking. A directive can exceed it only by the
# client's own decision.
DOWNSIDE_GUARD_SHARE = RISK_BUDGET_SHARE
STOCKOUT_ALERT = 0.25
MEASUREMENT_HORIZON_DAYS = 30
BRANDED_SPEND_MIN = 25.0
INCREMENTALITY_MID = 0.4       # midpoint of the 25–60% industry range
GENERIC_NAME_WORDS = {"inc", "llc", "ltd", "the", "and", "co", "company"}
RECOVERY_MIN_VALUE = 50.0      # below this, filing costs more attention than it returns
RUIN_WARNING = 0.05            # mirrors cashflow.RUIN_WARNING: a cash decision that pushes ruin past it asks first
ANOMALY_MIN_IMPACT = 100.0     # per period
LIQUIDATION_MIN_GAIN = 100.0
ANOMALY_LABELS = {
    "fee_per_unit": "total Amazon fees per unit", "fba_fee_per_unit": "FBA fulfillment fee per unit",
    "referral_rate": "referral fee rate", "storage_fee": "storage fee",
    "sessions": "traffic", "unit_session_pct": "conversion", "buy_box_pct": "Buy Box share", "spend": "daily spend",
    "cpc": "cost per click", "sales_per_click": "sales per click",
}


def _labels(channel: str | None) -> dict:
    """Metric labels with the platform named; the FBA, referral and Buy Box
    metrics only ever come from Amazon data, so those stand."""
    return {**ANOMALY_LABELS, "fee_per_unit": f"total {channels.fee_label(channel)} per unit"}


def _money(v: float) -> str:
    return f"${abs(v):,.0f}"


def dedupe_key(module: str, kind: str, subject) -> str:
    """One finding, one open directive.

    Stable across runs so the weekly sweep re-drafting the same fee creep does
    not re-issue it — the same job `claim_key` does in models/recovery.py, and
    deliberately the same shape."""
    blob = f"{module}|{kind}|{json.dumps(subject, sort_keys=True, default=str)}"
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def _draft(module: str, kind: str, subject, score: float, expected: float | None,
           action_text: str, evidence: dict, mandate: str | None = None) -> dict:
    """Every draft goes through here, so none can ship without the subject and
    evidence a later sweep needs to measure it."""
    return {
        "module": module,
        "kind": kind,
        "score": score,
        "expected_impact_usd": expected,
        "action_text": action_text,
        "evidence": evidence,
        "dedupe_key": dedupe_key(module, kind, subject),
        "mandate": mandate or ("standing" if kind in STANDING else "explicit"),
    }


def downside_guard(draft: dict, margin_row: dict | None,
                   share: float = DOWNSIDE_GUARD_SHARE,
                   monthly_net: float | None = None) -> dict:
    """Route a draft to an explicit yes when its bad case is too big, in place.

    A directive that carries a simulated profit-delta distribution carries its
    own 5th percentile. If the loss at that percentile exceeds `share` of the
    SKU's trailing monthly net, the move is no longer inside what the standing
    mandate covers — whatever its step size — and it goes to the client for a
    signature with the reason on the record.

    Drafts with no delta distribution are left alone: this guard is about a
    quantified downside, and inventing one in order to gate on it would be the
    thing the engine does not do.

    `monthly_net` states the budget's base directly, for a draft whose subject is
    not one SKU — a campaign set, a variant family — and so has no margin row to
    read a trailing net off."""
    evidence = draft.get("evidence") or {}
    p5 = evidence.get("delta_p5")
    if p5 is None or (margin_row is None and monthly_net is None):
        return draft
    if monthly_net is None:
        monthly_net = trailing_monthly_net(margin_row)
    budget = share * max(monthly_net, 0.0)
    downside = max(0.0, -float(p5))
    evidence["downside_guard"] = {
        "delta_p5": float(p5),
        "downside_usd": round(downside, 2),
        "trailing_monthly_net": round(monthly_net, 2),
        "budget_usd": round(budget, 2),
        "share": share,
        "within_budget": downside <= budget,
    }
    if downside > budget:
        draft["mandate"] = "explicit"
        draft["mandate_reason"] = (
            f"the worst realistic case risks {_money(downside)} against "
            f"{_money(budget)} ({share:.0%} of this SKU's {_money(monthly_net)} monthly net)"
        )
    return draft


def _latest_margins_by_sku(margins: list[dict]) -> dict[str, dict]:
    if not margins:
        return {}
    latest = max(m["period_start"] for m in margins)
    return {m["sku"]: m for m in margins if m["period_start"] == latest}


def resolve_brand_terms(client: dict) -> list[str]:
    """Explicit clients.brand_terms wins; else significant company_name words."""
    raw = (client.get("brand_terms") or "").strip()
    if raw:
        return [t.strip().lower() for t in raw.split(",") if t.strip()]
    name = (client.get("company_name") or "").lower()
    return [w for w in name.split() if len(w) >= 3 and w not in GENERIC_NAME_WORDS]


def branded_spend(search_terms: list[dict], brand_terms: list[str]) -> tuple[float, int]:
    """Paid spend on the client's own brand in the latest export window.
    Zero-sale terms are excluded — those are already covered by the bleed
    directive, and double-counting dollars would be dishonest."""
    if not search_terms or not brand_terms:
        return 0.0, 0
    latest_end = max(r["period_end"] for r in search_terms)
    total, n = 0.0, 0
    for r in search_terms:
        if r["period_end"] != latest_end or not (r["sales_7d"] or 0):
            continue
        term = (r["search_term"] or "").lower()
        if any(b in term for b in brand_terms):
            total += float(r["spend"] or 0)
            n += 1
    return total, n


def _expedite_directive(rep_row: dict, econ_row: dict | None) -> dict | None:
    """Air instead of sea on an order at stockout risk. Explicit — it is new
    money — and unbankable: the avoided stockout is the counterfactual §10
    calls unobservable, so the expected net rides in evidence and nothing is
    promised."""
    ex = (rep_row or {}).get("expedite") or {}
    if ex.get("status") != "ok" or not ex.get("recommend_air"):
        return None
    sku = rep_row["sku"]
    return _draft(
        "inventory", "expedite_air", sku,
        score=28 + float(ex["net_p50"]) / 100,
        expected=None,
        action_text=(
            f"Ship the {int(ex['order_qty'])}-unit order of {sku} by air ({int(ex['air_lead_days'])} days) rather than sea "
            f"({int(ex['sea_lead_days'])} days): the {_money(float(ex['freight_premium']))} freight premium buys back about "
            f"{float(ex['stockout_units_sea']) - float(ex['stockout_units_air']):.0f} units that would otherwise sell out, "
            f"a net of about {'+' if float(ex['net_p50']) >= 0 else '−'}{_money(float(ex['net_p50']))} (90% range "
            f"{'+' if float(ex['net_p5']) >= 0 else '−'}{_money(float(ex['net_p5']))} to "
            f"{'+' if float(ex['net_p95']) >= 0 else '−'}{_money(float(ex['net_p95']))}; stockout risk "
            f"{float(ex['p_stockout_sea']):.0%} by sea, {float(ex['p_stockout_air']):.0%} by air). The avoided stockout is "
            f"not banked: no later export can show a sale that did not fail to happen."
        ),
        evidence={"sku": sku, **{k: v for k, v in ex.items() if k != "basis"}, "order_qty": ex["order_qty"]},
    )


def _budget_order_set_directive(cash_orders: dict | None) -> dict | None:
    """When the cash cannot fund every order: the set it supports, in the order
    capital should go, and the bridge that would fund the rest. Explicit and
    unbankable, like the reorders it replaces."""
    if not cash_orders or cash_orders.get("status") != "constrained":
        return None
    orders = cash_orders.get("orders") or []
    funded = [o for o in orders if o["order_qty"] > 0]
    deferred = [o for o in orders if o["deferred_units"] > 0]
    k = cash_orders.get("budget") or {}

    def _one(o):
        return (f"{o['sku']} {int(o['order_qty'])} units ({_money(float(o['wire']))}, "
                f"{float(o['fractile']):.0%} service)")

    text = (f"Your cash supports {_money(float(cash_orders['wire_total']))} of the "
            f"{_money(float(cash_orders['unconstrained_total']))} of orders due this cycle "
            f"(the 90-day cone's worst-twentieth trough is {_money(float(k.get('trough_p5') or 0))}). Fund these first, "
            f"in the order capital earns most contribution per dollar: "
            f"{'; '.join(_one(o) for o in funded[:6])}{'…' if len(funded) > 6 else ''}."
            + (f" Deferred or trimmed: {', '.join(f'{o['sku']} {int(o['deferred_units'])} units' for o in deferred[:6])}"
               f"{'…' if len(deferred) > 6 else ''}, carrying "
               f"{', '.join(f'{float(o['p_stockout_cycle']):.0%}' for o in deferred[:3])} stockout risk over the cycle."
               if deferred else "")
            + f" Bridge capital of {_money(float(cash_orders['bridge_capital']))} would fund the whole set. "
            f"No dollars are promised: an avoided stockout cannot be measured after the fact.")
    return _draft(
        "inventory", "budget_order_set", sorted((o["sku"], o["order_qty"]) for o in orders),
        score=45,
        expected=None,
        action_text=text,
        evidence={"orders": orders, "budget": k, "lambda": cash_orders.get("lambda"),
                  "wire_total": cash_orders.get("wire_total"), "unconstrained_total": cash_orders.get("unconstrained_total"),
                  "deferred": cash_orders.get("deferred"), "bridge_capital": cash_orders.get("bridge_capital")},
    )


def _sku_exit_directive(row: dict, margin_row: dict | None) -> dict | None:
    """Cut or merge a SKU on its fully loaded, survival-discounted contribution.
    Explicit — an exit is the client's — and the promise is the twelve-month
    loss avoided, banked only as the periods without the SKU actually pass."""
    if row.get("decision") not in ("cut", "merge") or not row.get("avoided_loss_12m"):
        return None
    sku = row["sku"]
    av = row["avoided_loss_12m"]
    comp = row.get("components_latest") or {}
    z = float(row.get("credibility_z") or 0)
    if row["decision"] == "merge":
        text = (f"Merge {sku} into its family: it carries {float(row.get('family_revenue_share') or 0):.1%} of the "
                f"family's revenue and a loaded contribution of {'−' if comp.get('loaded', 0) < 0 else ''}"
                f"{_money(float(comp.get('loaded') or 0))} last period. Delist the variant and let its buyers land on "
                f"the siblings; expected {_money(float(av['p50']))} of loss avoided over twelve months "
                f"(90% range {_money(float(av['p5']))} to {_money(float(av['p95']))}).")
    else:
        text = (f"Plan the exit of {sku}: fully loaded — net margin less the surcharge and low-inventory fee it bills, "
                f"its returns and the cost of carrying it — it loses about {_money(abs(float(row['blended_monthly'])))} a "
                f"month, negative in {int(row['negative_periods'])} of {int(row['n_periods'])} periods, with a "
                f"{float(row['p_negative']):.0%} chance the true figure is below zero"
                + (f" (this is {z:.0%} the SKU's own history and the rest the catalogue's)" if z < 0.8 else "")
                + f". Discounted by how long SKUs like it keep selling, that is {_money(float(av['p50']))} of loss avoided "
                f"over twelve months (90% range {_money(float(av['p5']))} to {_money(float(av['p95']))}). Sell down the "
                f"stock on hand first — the markdown and liquidation calls cover that.")
    return _draft(
        "margin", "sku_exit", (sku, row["decision"]),
        score=30 + float(av["p50"]) / 100,
        expected=av["p50"],
        action_text=text,
        evidence={
            "sku": sku, "decision": row["decision"], "blended_monthly": row.get("blended_monthly"),
            "credibility_z": z, "n_periods": row.get("n_periods"), "n_negative_periods": row.get("negative_periods"),
            "p_negative": row.get("p_negative"), "ci95": row.get("ci95"), "survival_12m": row.get("survival_12m"),
            "delta_p5": av["p5"], "delta_p50": av["p50"], "delta_p95": av["p95"], "p_loss": av.get("p_loss"),
            "mc_inputs": {"draws": 4000, "seed": row.get("seed") or 20260911},
            "components_latest": comp, "family": row.get("family"),
            "baseline_period": str((margin_row or {}).get("period_start")),
            "baseline_units": float((margin_row or {}).get("units") or 0),
            "baseline_revenue": float((margin_row or {}).get("revenue") or 0),
            "baseline_net": float((margin_row or {}).get("net_margin") or 0) if margin_row else None,
        },
    )


def _inventory_directive(r: dict, margin_row: dict | None, today: date, econ_row: dict | None = None,
                         channel: str | None = "amazon", rep_row: dict | None = None,
                         supplier_events: dict | None = None) -> dict:
    p = float(r["stockout_probability"] or 0)
    rate = float(r["daily_velocity_mean"] or 0)
    position = int(r.get("on_hand_units") or 0) + int(r.get("inbound_units") or 0)
    days_until = max(0, int((position - int(r["reorder_point"] or 0)) / rate)) if rate > 0 else 0
    by = today + timedelta(days=days_until)
    by_text = by.strftime("%a %b %d").replace(" 0", " ")

    unit_cost = None
    if margin_row and margin_row.get("cogs") is not None and float(margin_row.get("units") or 0) > 0:
        unit_cost = float(margin_row["cogs"]) / float(margin_row["units"])

    wire_amount, order_qty = None, None
    if econ_row and econ_row.get("order_qty_econ") and econ_row.get("wire_econ") is not None:
        wire_amount, order_qty = float(econ_row["wire_econ"]), int(econ_row["order_qty_econ"])
    elif unit_cost:
        wire_amount, order_qty = float(r["reorder_qty"]) * unit_cost, int(r["reorder_qty"])
    else:
        order_qty = int(r["reorder_qty"])

    joint = None
    terms_note = ""
    if rep_row and rep_row.get("status") == "ok" and rep_row.get("order_qty"):
        # the supplier's terms reshape the order: MOQ, case pack, a price break
        order_qty, wire_amount = int(rep_row["order_qty"]), float(rep_row["wire"] or 0)
        t = rep_row.get("terms") or {}
        pb = rep_row.get("price_break") or {}
        if t.get("forced_units"):
            terms_note += (f" Rounded up from {t['q_star']} to the supplier's minimum and case pack; the extra "
                           f"{t['forced_units']} units cost about {_money(float(t['moq_cost'] or 0))} in overage this cycle.")
        if pb.get("take"):
            terms_note += (f" Raised to the {pb['q_break']}-unit price break at ${float(pb['unit_cost_break']):.2f}: "
                           f"{_money(float(pb['net']))} net of the extra stock it carries "
                           f"({float(pb['p_positive']):.0%} of draws agree).")
        if supplier_events and rep_row.get("supplier"):
            ev_ = supplier_events.get(rep_row["supplier"])
            if ev_ and ev_.get("wire_events_saved"):
                joint = {"supplier": rep_row["supplier"], "skus": next((e["skus"] for e in ev_.get("events", [])
                                                                        if r["sku"] in e["skus"]), [r["sku"]]),
                         "wire_events_saved": ev_["wire_events_saved"], "horizon_days": ev_["horizon_days"]}
                others = [s_ for s_ in joint["skus"] if s_ != r["sku"]]
                if others:
                    terms_note += (f" Order it with {', '.join(others[:3])}{'…' if len(others) > 3 else ''} from "
                                   f"{rep_row['supplier']} on the same wire; ordering the supplier's SKUs together saves "
                                   f"{ev_['wire_events_saved']} wire(s) over {ev_['horizon_days']} days.")

    if econ_row and econ_row.get("order_qty_econ") and econ_row.get("wire_econ") is not None:
        # the newsvendor sized it: the service level is the one the margin justifies
        q = float(econ_row["critical_fractile"])
        text = (
            f"Wire {_money(float(wire_amount))} to your supplier by {by_text} — "
            f"{int(order_qty)} units of {r['sku']}. Sized to a {q:.0%} service level, "
            f"the level your margin justifies (C_u ÷ (C_u + C_o), storage and the season priced in); "
            f"lead time {r['lead_time_days']}d, current stockout risk {p:.0%}.{terms_note}"
        )
    elif unit_cost:
        wire = float(r["reorder_qty"]) * unit_cost
        cliff = " and clears Amazon's low-inventory-fee window" if channels.has_fee_cliffs(channel) else ""
        text = (
            f"Wire {_money(wire)} to your supplier by {by_text} — {r['reorder_qty']} units of "
            f"{r['sku']}. That keeps stockout risk under 5%{cliff} "
            f"(lead time {r['lead_time_days']}d, current risk {p:.0%})."
        )
    else:
        text = (
            f"Order {r['reorder_qty']} units of {r['sku']} by {by_text} — {p:.0%} stockout risk "
            f"without it (lead time {r['lead_time_days']}d). Upload unit costs and the next "
            f"move states the exact PO amount to wire."
        )
    return _draft(
        "inventory", "inventory_reorder", r["sku"],
        score=p * 100,
        # Avoided-stockout value isn't honestly computable: the counterfactual
        # (units you would have sold while out of stock) is unobservable.
        # measurement.py proves the PO landed instead, and banks nothing.
        expected=None,
        action_text=text,
        evidence={
            "sku": r["sku"],
            "reorder_qty": order_qty,
            "wire_usd": round(wire_amount, 2) if wire_amount else None,
            "position_units": position,
            "reorder_point": int(r["reorder_point"] or 0),
            "stockout_probability": p,
            "lead_time_days": r.get("lead_time_days"),
            "supplier_terms": (rep_row or {}).get("terms"),
            "price_break": (rep_row or {}).get("price_break"),
            "joint_order": joint,
        },
    )


def _fee_history(sku: str, margins: list[dict]) -> list[tuple[float, float]]:
    """Every period's (proportional rate, fixed per-unit fee) for one SKU.

    Its dispersion is what the profit-delta simulation draws the fee structure
    from: a SKU whose FBA fee moved $0.40 between periods has more uncertainty
    in its promise than one whose fees have not moved, and the published range
    should show it."""
    out = []
    for m in margins or []:
        if m.get("sku") != sku:
            continue
        if float(m.get("units") or 0) <= 0 or float(m.get("revenue") or 0) <= 0:
            continue
        f, big_f, _ = fee_terms(m)
        out.append((f, big_f))
    return out


def _cannibalisation_directive(move: dict, fit: dict, margin_row: dict, sku: str) -> dict:
    """The family absorbed the move: the SKU alone would have stepped, the
    family together would not. No step is issued; the finding is."""
    step = float(move["own_step_fraction"])
    verb = "rise" if step > 0 else "cut"
    own, total = float(move.get("own_delta_p50") or 0), float(move.get("total_delta_p50") or 0)
    return _draft(
        "pricing", "cannibalisation_watch", (sku, move.get("family")),
        score=8,
        expected=None,
        action_text=(
            f"No step on {sku}. A {abs(step):.1%} {verb} would earn about {'+' if own >= 0 else '−'}{_money(own)}/period "
            f"on its own, but its variant family absorbs it: with a cross-elasticity of {float(move['eps_cross']):+.2f} "
            f"the volume moves {'to' if step > 0 else 'from'} {move.get('sibling') or 'its siblings'}, and across the "
            f"family the move nets {'+' if total >= 0 else '−'}{_money(total)}. We price the family together rather "
            f"than one variant against another."
        ),
        evidence={"sku": sku, "family": move.get("family"), "sibling": move.get("sibling"),
                  "own_step_fraction": step, "own_delta_p50": own, "total_delta_p50": total,
                  "sibling_delta_p50": move.get("sibling_delta_p50"), "eps_cross": move.get("eps_cross"),
                  "cross_std_err": move.get("cross_std_err"), "n_siblings": move.get("n_siblings"),
                  "elasticity": float(fit["elasticity"]), "ci95": (fit.get("details") or {}).get("ci95"),
                  "baseline_period": str(margin_row.get("period_start"))},
    )


def _pricing_directive(fit: dict, margin_row: dict, margins: list[dict] | None = None,
                       cross: dict | None = None, risk_share: float | None = None) -> dict | None:
    move = price_move(margin_row, fit, fee_history=_fee_history(fit["item_id"], margins or []), cross=cross,
                      risk_share=risk_share)
    sku = fit["item_id"]
    if move and move.get("status") == "cannibalisation":
        return _cannibalisation_directive(move, fit, margin_row, sku)
    if move and move.get("status") == "near_unit_elastic":
        return _near_unit_elastic_directive(move, fit, margin_row, sku)
    if move:
        step = move["p_new"] - move["p0"]
        dest = f"; optimum ${move['destination']:.2f}" if move["destination"] else ""
        rng = ""
        if move["delta_range"] and move["delta_range"][0] is not None:
            lo, hi = move["delta_range"]
            # P5 to P95 is a 90% band. Calling it a 95% range was wrong twice
            # over — wrong level, and built from two elasticity endpoints
            # rather than from the uncertainty in everything.
            rng = (f" (90% range {'+' if lo >= 0 else '−'}{_money(lo)} to "
                   f"{'+' if hi >= 0 else '−'}{_money(hi)}")
            if move.get("p_loss") is not None:
                loss = float(move["p_loss"])
                # 0 out of 6,000 draws is not proof of impossibility, so the
                # floor is "under 1%" and never "0%"
                rng += ("; under a 1% chance it goes the other way" if loss < 0.01
                        else f"; a {loss:.0%} chance it goes the other way")
            rng += ")"
        sign = "+" if move["expected_delta"] >= 0 else "−"
        # A step inside the cap is what the client already authorised; anything
        # larger is a different promise and needs its own yes.
        #
        # price_move caps the ratio at STEP_CAP and THEN rounds the new price to
        # cents, so a step the engine deliberately held at exactly 5% can read
        # as 5.002% here. Allowing that half-cent of rounding back keeps a move
        # the client already authorised from being sent back to them for a
        # signature; a genuinely larger step is nowhere near this tolerance.
        fraction = abs(move["p_new"] / move["p0"] - 1) if move["p0"] else 0.0
        rounding_slack = 0.005 / move["p0"] if move["p0"] else 0.0
        return _draft(
            "pricing", "price_step", sku,
            score=20 + abs(move["expected_delta"]) / 100,
            expected=move["expected_delta"],
            action_text=(
                f"Move {sku} ${move['p0']:.2f} → ${move['p_new']:.2f} "
                f"({'+' if step >= 0 else '−'}${abs(step):.2f}{dest}). "
                f"Expected {sign}{_money(move['expected_delta'])}/period{rng}. "
                f"Run as a tracked test — Buy Box watched while the step is live."
            ),
            evidence={
                "sku": sku,
                **move,
                # The fitted curve and its uncertainty, kept so the measurement
                # pass rebuilds the counterfactual with the SAME numbers that
                # made the promise instead of a later, different fit.
                "elasticity": float(fit["elasticity"]),
                "elasticity_raw": (fit.get("details") or {}).get("epsilon_raw"),
                "shrinkage_weight": (fit.get("details") or {}).get("shrinkage_weight"),
                "std_err": fit.get("std_err"),
                "eps_common_se": (fit.get("details") or {}).get("common_se"),
                "ci95": (fit.get("details") or {}).get("ci95"),
                "baseline_units": float(margin_row.get("units") or 0),
                "baseline_revenue": float(margin_row.get("revenue") or 0),
                "baseline_cogs": float(margin_row["cogs"]) if margin_row.get("cogs") is not None else None,
                "baseline_fees": float(margin_row.get("amazon_fees") or 0),
                "baseline_period": str(margin_row.get("period_start")),
            },
            mandate="standing" if fraction <= STEP_CAP + rounding_slack else "explicit",
        )
    # inelastic without landed cost: bounded test, honest about what's missing
    eps = float(fit["elasticity"]) if fit.get("elasticity") is not None else None
    if eps is not None and -1 < eps < 0:
        return _draft(
            "pricing", "price_step", sku,
            score=20 + 10 * (1 + eps),
            # No landed cost, no dollar-exact promise — and a promise we cannot
            # state is one measurement must not later invent.
            expected=None,
            action_text=(
                f"Price-test {sku} +3%: demand is price-insensitive (ε = {eps:.2f}), so volume "
                f"loss should be smaller than the margin gain. Upload unit costs and the next "
                f"move states the exact optimum. Buy Box watched while the step is live."
            ),
            evidence={
                "sku": sku,
                "p0": round(float(margin_row["revenue"]) / float(margin_row["units"]), 2)
                      if float(margin_row.get("units") or 0) > 0 else None,
                "step_fraction": INELASTIC_STEP,
                "elasticity": eps,
                "ci95": (fit.get("details") or {}).get("ci95"),
                "baseline_units": float(margin_row.get("units") or 0),
                "baseline_revenue": float(margin_row.get("revenue") or 0),
                "baseline_cogs": None,
                "baseline_period": str(margin_row.get("period_start")),
            },
        )
    return None


def _near_unit_elastic_directive(move: dict, fit: dict, margin_row: dict, sku: str) -> dict:
    """The fit cannot be separated from ε = −1, so there is no destination to
    quote — the optimum diverges at that point and any price we printed would be
    an artifact of where the estimate happened to land.

    What survives is a step: the size comes from the robust objective, which
    integrates over the whole range the data allows, and it is small when that
    range is wide. No dollar promise travels with it, because the expected delta
    at a pole-adjacent ε is not a figure measurement could be scored against."""
    eps = float(fit["elasticity"])
    ci = (fit.get("details") or {}).get("ci95")
    band = f", and the history supports anywhere from {ci[0]:.2f} to {ci[1]:.2f}" \
        if ci and ci[0] is not None else ""
    step = move["step_fraction"]
    verb = "Raise" if step > 0 else "Cut"
    return _draft(
        "pricing", "price_step", sku,
        score=18,
        # No honest dollar figure exists here. ε/(1+ε) is unbounded this close
        # to −1, so any expected delta we printed would be an artifact of where
        # the point estimate happened to land.
        expected=None,
        action_text=(
            f"{verb} {sku} {abs(step):.1%} as a measured step: ${move['p0']:.2f} → "
            f"${move['p_new']:.2f}. We cannot separate this SKU's demand from the break-even "
            f"point where a price move pays for itself (ε = {eps:.2f}{band}), and the optimum "
            f"is unbounded at that point — so there is no destination to quote and no dollar "
            f"figure we would stand behind. The step is sized to what the range allows; the "
            f"next two periods narrow it. Buy Box watched while the step is live."
        ),
        evidence={
            "sku": sku,
            **move,
            "elasticity": eps,
            "elasticity_raw": (fit.get("details") or {}).get("epsilon_raw"),
            "shrinkage_weight": (fit.get("details") or {}).get("shrinkage_weight"),
            "ci95": ci,
            "std_err": fit.get("std_err"),
            "eps_common_se": (fit.get("details") or {}).get("common_se"),
            "baseline_units": float(margin_row.get("units") or 0),
            "baseline_revenue": float(margin_row.get("revenue") or 0),
            "baseline_cogs": float(margin_row["cogs"]) if margin_row.get("cogs") is not None else None,
            "baseline_fees": float(margin_row.get("amazon_fees") or 0),
            "baseline_period": str(margin_row.get("period_start")),
        },
    )


def _recovery_directive(recovery: dict | None) -> dict | None:
    if not recovery or recovery.get("status") != "ok":
        return None
    live = [c for c in recovery.get("claims", []) if c["status"] in ("open", "expiring")]
    value = sum(float(c.get("value") or 0) for c in live)
    ev = sum(float(c.get("expected_value") or 0) for c in live)
    if not live or value < RECOVERY_MIN_VALUE:
        return None
    expiring = [c for c in live if c["status"] == "expiring"]
    closes = ""
    if expiring:
        soonest = min(c["deadline"] for c in expiring)
        closes = f" {len(expiring)} of them close by {date.fromisoformat(soonest).strftime('%b %d').replace(' 0', ' ')}."
    keys = sorted(c["claim_key"] for c in live if c.get("claim_key"))
    return _draft(
        "recovery", "recovery_filing", keys,
        score=60 + ev / 100,
        expected=round(ev, 2),
        action_text=(
            f"Authorize us to file {len(live)} reimbursement claim{'s' if len(live) != 1 else ''} with Amazon — "
            f"{_money(value)} at face value, {_money(ev)} expected after approval odds.{closes} "
            f"We file through your account, with your yes; your Profit Record books only what Amazon actually pays."
        ),
        evidence={
            "claim_keys": keys,
            "face_value": round(value, 2),
            "expected_value": round(ev, 2),
            "n_claims": len(live),
        },
    )


def ruin_guard(draft: dict, cash: dict | None, day: int, amount: float) -> dict:
    """The sequence-of-returns risk of one decision, in place: what this wire
    (or inflow) does to the cone's ruin probability. A decision that pushes
    ruin past the warning line where it sat under it is no longer inside the
    standing mandate whatever its own economics, and says why. Nothing is
    attached without a cone, and nothing is invented."""
    from .models.cashflow import ruin_delta

    rd = ruin_delta(cash, day, amount)
    if rd is None:
        return draft
    draft["evidence"]["ruin_delta"] = rd
    if rd["p_ruin_after"] > RUIN_WARNING >= rd["p_ruin_before"]:
        draft["mandate"] = "explicit"
        draft["mandate_reason"] = (
            f"this {'wire' if amount > 0 else 'inflow'} of {_money(abs(amount))} on day {rd['day']} moves the 90-day "
            f"chance of dipping below {_money(rd['ruin_floor'])} from {rd['p_ruin_before']:.1%} to "
            f"{rd['p_ruin_after']:.1%}, past the {RUIN_WARNING:.0%} line")
    return draft


def _baseline(margin_row: dict | None) -> dict:
    if not margin_row:
        return {}
    return {"baseline_units": float(margin_row.get("units") or 0),
            "baseline_revenue": float(margin_row.get("revenue") or 0),
            "baseline_cogs": float(margin_row["cogs"]) if margin_row.get("cogs") is not None else None,
            "baseline_fees": float(margin_row.get("amazon_fees") or 0),
            "baseline_period": str(margin_row.get("period_start"))}


def _markdown_directive(row: dict, margin_row: dict | None, fit: dict | None) -> dict | None:
    """Clear the excess at a lower price rather than dumping it or carrying it.
    Standing while the depth sits inside the 5% cap; deeper is the client's
    call. Measured before landed cost — the dollars are cash proceeds."""
    if row.get("decision") != "markdown" or row.get("delta_p50") is None:
        return None
    sku, depth = row["sku"], float(row["depth"])
    gain, vs_liq = row["delta_vs_hold"], row.get("delta_vs_liquidate") or {}
    months = (row.get("months_to_clear") or {}).get("markdown")
    lo, hi = gain["p5"], gain["p95"]
    p_loss = row.get("p_loss")
    rng = (f" (90% range {'+' if lo >= 0 else '−'}{_money(lo)} to {'+' if hi >= 0 else '−'}{_money(hi)}"
           + ("; under a 1% chance it goes the other way" if p_loss is not None and p_loss < 0.01
              else f"; a {p_loss:.0%} chance it goes the other way" if p_loss is not None else "") + ")")
    range_note = (" The markdown price sits below anything this SKU has sold at, so the demand response there is "
                  "an extrapolation of the fitted curve; the range carries that." if row.get("beyond_observed_range") else "")
    text = (f"Mark {sku} down {depth:.0%} to ${float(row['p_new']):.2f} until the {int(row['excess_units'])} excess units "
            f"clear (about {months:.0f} month{'s' if months != 1 else ''}), then back to ${float(row['p0']):.2f}. "
            f"It nets +{_money(gain['p50'])} against holding at today's price{rng}"
            + (f" and {'+' if (vs_liq.get('p50') or 0) >= 0 else '−'}{_money(vs_liq['p50'])} against liquidating"
               if vs_liq.get("p50") is not None else "")
            + f", with storage and the aged surcharge priced in.{range_note} Buy Box watched while the markdown is live.")
    draft = _draft(
        "pricing", "markdown", sku,
        score=25 + float(gain["p50"]) / 100,
        expected=gain["p50"],
        action_text=text,
        evidence={
            "sku": sku, "p0": row["p0"], "p_new": row["p_new"], "depth": depth, "destination": row["p_new"],
            "excess_units": int(row["excess_units"]), "months_to_clear": months,
            "hold_npv": (row.get("npv") or {}).get("hold", {}).get("p50"),
            "liquidate_value": (row.get("npv") or {}).get("liquidate", {}).get("p50"),
            "markdown_npv": (row.get("npv") or {}).get(f"markdown_{int(depth * 100)}", {}).get("p50"),
            "delta_p5": row["delta_p5"], "delta_p50": row["delta_p50"], "delta_p95": row["delta_p95"],
            "delta_vs_liquidate_p50": vs_liq.get("p50"), "p_loss": p_loss, "mc_se": row.get("mc_se"),
            "mc_inputs": row.get("mc_inputs"), "carry_saving_p50": row.get("carry_saving_p50"),
            "carry_month_now": row.get("carry_month_now"), "beyond_observed_range": row.get("beyond_observed_range"),
            "elasticity": row.get("elasticity"), "std_err": row.get("std_err"), "ci95": row.get("ci95"),
            "fee_rate": row.get("fee_rate"), "fixed_fee_per_unit": row.get("fixed_fee_per_unit"),
            **_baseline(margin_row),
        },
        mandate="standing" if depth <= STEP_CAP + 1e-9 else "explicit",
    )
    return downside_guard(draft, margin_row)


def _stretch_directive(row: dict, margin_row: dict | None, fit: dict | None) -> dict | None:
    """A rise inside the cap so thin stock lasts until the replenishment lands.
    An ordinary price step to the Profit Record, with the reason on it."""
    st = row.get("stretch") or {}
    if st.get("status") != "ok":
        return None
    sku, gain = row["sku"], st["gain"]
    lo, hi = gain["p5"], gain["p95"]
    text = (f"Raise {sku} ${float(st['p0']):.2f} → ${float(st['p_new']):.2f} (+{float(st['step_fraction']):.1%}) to stretch "
            f"the units on hand across the {int(st['mc_inputs']['lead_days'])}-day lead time: stockout risk falls from "
            f"{float(st['p_stockout_before']):.0%} to {float(st['p_stockout_after']):.0%}, and the units sell at the higher "
            f"price rather than running out — about +{_money(gain['p50'])} over the window (90% range "
            f"{'+' if lo >= 0 else '−'}{_money(lo)} to {'+' if hi >= 0 else '−'}{_money(hi)}). Back to "
            f"${float(st['p0']):.2f} when the replenishment lands. Buy Box watched while the step is live.")
    draft = _draft(
        "pricing", "price_step", (sku, "stretch"),
        score=22 + float(gain["p50"]) / 100,
        expected=gain["p50"],
        action_text=text,
        evidence={
            "sku": sku, "status": "stretch", "reason": "stretch", "p0": st["p0"], "p_new": st["p_new"],
            "step_fraction": st["step_fraction"], "destination": None,
            "expected_delta": gain["p50"], "delta_range": (gain["p5"], gain["p95"]),
            "delta_p5": gain["p5"], "delta_p50": gain["p50"], "delta_p95": gain["p95"],
            "p_loss": st.get("p_loss"), "mc_se": gain.get("mc_se"), "mc_inputs": st.get("mc_inputs"),
            "p_stockout_before": st["p_stockout_before"], "p_stockout_after": st["p_stockout_after"],
            "lead_time_days": st["mc_inputs"].get("lead_days"),
            "elasticity": row.get("elasticity"), "std_err": row.get("std_err"), "ci95": row.get("ci95"),
            "fee_rate": row.get("fee_rate"), "fixed_fee_per_unit": row.get("fixed_fee_per_unit"),
            **_baseline(margin_row),
        },
    )
    return downside_guard(draft, margin_row)


def _liquidation_directives(inv_econ: dict | None, channel: str | None = "amazon",
                            markdown: dict | None = None) -> list[dict]:
    """Liquidate only when it beats holding AND every markdown depth (the
    three-way rows), or when no three-way row exists for the SKU."""
    out = []
    program = "Amazon's liquidation program" if channels.has_fee_cliffs(channel) else "a clearance sale"
    md_rows = {r["sku"]: r for r in (markdown or {}).get("rows", []) if r.get("decision")}
    for r in (inv_econ or {}).get("rows", []):
        md = md_rows.get(r["sku"])
        if md is not None:
            if md["decision"] != "liquidate" or md.get("delta_p50") is None:
                continue
            gain = float(md["delta_p50"])
            liquidate_value = float(md["npv"]["liquidate"]["p50"] or 0)
            hold_npv = float(md["npv"]["hold"]["p50"] or 0)
            extra = {"delta_p5": md["delta_p5"], "delta_p50": md["delta_p50"], "delta_p95": md["delta_p95"],
                     "p_loss": md.get("p_loss"), "mc_inputs": md.get("mc_inputs"),
                     "markdown_considered": md["status"] == "ok"}
            considered = (" No markdown depth nets more." if md["status"] == "ok"
                          else " No elasticity is fitted, so a markdown could not be priced against it.")
        elif r.get("decision") == "liquidate":
            gain = float(r.get("liquidate_value") or 0) - float(r.get("hold_npv") or 0)
            liquidate_value, hold_npv = float(r["liquidate_value"]), float(r["hold_npv"])
            extra, considered = {}, ""
        else:
            continue
        if gain < LIQUIDATION_MIN_GAIN:
            continue
        aged = float(r.get("aged_surcharge_month") or 0)
        out.append(_draft(
            "inventory", "liquidation", r["sku"],
            score=30 + gain / 100,
            expected=round(gain, 2),
            action_text=(
                f"Liquidate {int(r['excess_units'])} excess units of {r['sku']}: {program} returns about "
                f"{_money(liquidate_value)} now, against {_money(hold_npv)} from holding and "
                f"selling them down with storage and the aged surcharge priced in"
                + (f" — the surcharge alone is {_money(aged)}/month." if aged else ".") + considered
            ),
            evidence={
                "sku": r["sku"],
                "excess_units": int(r["excess_units"]),
                "liquidate_value": liquidate_value,
                "hold_npv": hold_npv,
                "aged_surcharge_month": aged,
                **extra,
            },
        ))
    return out


BLEED_MIN_MONTH = 75.0     # below this a fee line is not worth a decision


def _fee_bleed_directives(inv_econ: dict | None, today: date, channel: str | None = "amazon",
                          exclude: set[str] | None = None) -> list[dict]:
    """Amazon's own published charges, on the client's own units.

    inventory_econ has always computed these three and only fed them to the
    Health Score — money the models found and then dropped. Each becomes its
    own directive because each has a different action and a different proof
    line in a later export; one combined "fee bleed" number would be a promise
    nothing could measure."""
    if not inv_econ or not channels.has_fee_cliffs(channel):
        return []
    rows = inv_econ.get("rows") or []
    if not rows:
        return []
    out = []

    # — low-inventory-level fee: replenish above the threshold and it stops —
    at_risk = [r for r in rows if r.get("low_inventory_fee_risk") and (r.get("low_inventory_fee_month") or 0) > 0]
    lilf = sum(float(r.get("low_inventory_fee_month") or 0) for r in at_risk)
    if lilf >= BLEED_MIN_MONTH:
        skus = sorted(r["sku"] for r in at_risk)
        out.append(_draft(
            "inventory", "low_inventory_fee", skus,
            score=20 + lilf / 100,
            expected=round(lilf, 2),
            action_text=(
                f"{len(skus)} SKU{'s' if len(skus) != 1 else ''} are billing Amazon's low-inventory-level fee — "
                f"{_money(lilf)}/month at current velocity. Replenish above the 28-day cover threshold "
                f"({', '.join(skus[:4])}{'…' if len(skus) > 4 else ''}) and the fee stops at the next "
                f"assessment; the Inventory Health export is where it shows up gone."
            ),
            evidence={"skus": skus, "monthly_fee": round(lilf, 2),
                      "per_sku": {r["sku"]: float(r.get("low_inventory_fee_month") or 0) for r in at_risk}},
        ))

    # — aged surcharge: the units are already old, removal or discount is the fix —
    exclude = exclude or set()
    aged_rows = [r for r in rows if (r.get("aged_surcharge_month") or 0) > 0
                 and r.get("decision") != "liquidate"     # liquidation owns those SKUs
                 and r["sku"] not in exclude]              # and a markdown owns its own
    aged = sum(float(r.get("aged_surcharge_month") or 0) for r in aged_rows)
    if aged >= BLEED_MIN_MONTH:
        skus = sorted(r["sku"] for r in aged_rows)
        units = sum(int(r.get("aged_units_181_plus") or 0) for r in aged_rows)
        out.append(_draft(
            "inventory", "aged_surcharge", skus,
            score=20 + aged / 100,
            expected=round(aged, 2),
            action_text=(
                f"{units:,} units across {len(skus)} SKU{'s' if len(skus) != 1 else ''} have been in the "
                f"warehouse 181+ days and are billing {_money(aged)}/month in aged-inventory surcharge. "
                f"Create a removal order or discount them through the threshold; the surcharge falls out of "
                f"the next Inventory Health export."
            ),
            evidence={"skus": skus, "monthly_surcharge": round(aged, 2), "aged_units": units,
                      "per_sku": {r["sku"]: float(r.get("aged_surcharge_month") or 0) for r in aged_rows}},
        ))

    # — peak storage premium: only promisable while there is still time to act —
    peak = sum(float(r.get("peak_storage_premium_month") or 0) for r in rows)
    months_to_peak = fee_schedule.months_until_peak(today)
    if peak >= BLEED_MIN_MONTH:
        skus = sorted(r["sku"] for r in rows if (r.get("peak_storage_premium_month") or 0) > 0)
        # Inside the peak window the money is already spent. Promising it back
        # would be promising a refund we cannot get.
        in_peak = months_to_peak == 0
        out.append(_draft(
            "inventory", "peak_storage_premium", skus,
            score=15 + peak / 100,
            expected=None if in_peak else round(peak, 2),
            action_text=(
                (f"{_money(peak)}/month of Q4 peak storage premium is already being billed on stock that "
                 f"went in before the window closed — it is spent, and the number is here so next year's "
                 f"plan is sized against it."
                 if in_peak else
                 f"{_money(peak)}/month of Q4 peak storage premium is coming on units that will still be "
                 f"in the warehouse in October. {months_to_peak} month(s) to move them: pull the excess "
                 f"forward or hold it at the 3PL until the rate drops.")
            ),
            evidence={"skus": skus, "monthly_premium": round(peak, 2),
                      "months_to_peak": months_to_peak, "already_in_peak": in_peak},
        ))
    return out


def _anomaly_directives(anomaly_rows: list[dict] | None, channel: str | None = "amazon") -> list[dict]:
    """One instruction per (item, metric) for adverse shifts worth ≥ $100/period."""
    labels, plat = _labels(channel), channels.label(channel)
    best: dict[tuple, dict] = {}
    for r in anomaly_rows or []:
        if not r.get("flagged") or (r.get("dollar_impact") or 0) < ANOMALY_MIN_IMPACT:
            continue
        adverse_up = r["metric"] in ("fee_per_unit", "fba_fee_per_unit", "referral_rate", "storage_fee", "spend",
                                     "monthly_total", "cpc")
        if (adverse_up and r.get("direction") != "up") or (not adverse_up and r.get("direction") != "down"):
            continue
        key = (r.get("scope"), r.get("item_id"), r.get("metric"))
        if key not in best or (r.get("detector") == "changepoint" and best[key].get("detector") != "changepoint"):
            best[key] = r
    out = []
    for r in best.values():
        since = date.fromisoformat(str(r["since"])[:10]).strftime("%b %Y") if r.get("since") else "recently"
        impact = float(r["dollar_impact"])
        b, c = float(r.get("baseline") or 0), float(r.get("current") or 0)
        m = r["metric"]
        details = r.get("details") or {}
        subject = (r.get("scope"), r.get("item_id"), m)
        ev = {
            "scope": r.get("scope"), "item_id": r.get("item_id"), "metric": m,
            "baseline": b, "current": c, "since": str(r.get("since") or ""),
            "dollar_impact": impact, "detector": r.get("detector"),
            "units_basis": details.get("units_basis"),
            "sales_basis": details.get("sales_basis"),
        }
        if m in ("fee_per_unit", "fba_fee_per_unit"):
            fix = ("Verify the listing's weight and dimensions in Seller Central and request a re-measure; "
                   "overcharged fees are reimbursable." if channels.has_fee_cliffs(channel) else
                   "Check the order mix: smaller orders each carry the fixed processing fee, and a refund "
                   "returns none of it. A minimum order value or a bundle moves it back.")
            out.append(_draft(
                "margin", "fee_anomaly", subject, 25 + impact / 100, round(impact, 2),
                (f"{plat}'s {labels[m]} on {r['item_id']} rose from ${b:.2f} to ${c:.2f} since {since} "
                 f"— {_money(impact)}/period at last period's volume. {fix}"), ev))
        elif m == "referral_rate":
            out.append(_draft(
                "margin", "referral_anomaly", subject, 25 + impact / 100, round(impact, 2),
                (f"The referral fee rate on {r['item_id']} moved from {b:.1%} to {c:.1%} since {since} — "
                 f"{_money(impact)}/period. Check the listing's category assignment; a wrong category "
                 f"bills a higher rate and the difference is reimbursable."), ev))
        elif m == "monthly_total":
            # De-banked deliberately: the action text says "we are tracing the
            # lines to the SKUs behind the step", and tracing is not an action
            # a later export can prove. It re-banks as a SKU-level finding once
            # we know which SKUs moved.
            out.append(_draft(
                "margin", "settlement_step", subject, 20 + impact / 100, None,
                (f"{plat}'s {r['item_id']} charges rose from {_money(b)} to {_money(c)} per month since "
                 f"{since} — {_money(impact)}/period at stake. We are tracing the lines to the SKUs "
                 f"behind the step."), ev))
        elif m == "unit_session_pct":
            # Display-only by design: the dollars are real EXPOSURE, but
            # conversion moves with season, competitors and ranking. Banking it
            # would credit us with the market. The corrective that follows
            # banks its own measurable dollars.
            out.append(_draft(
                "general", "conversion_watch", subject, 15 + impact / 100, None,
                (f"Conversion on {r['item_id']} fell from {b:.1f}% to {c:.1f}% since {since} — "
                 f"{_money(impact)}/period at current traffic. We check the Buy Box, price against "
                 f"competitors, and recent listing or review changes before touching price."), ev))
        elif m == "sessions":
            out.append(_draft(
                "general", "traffic_watch", subject, 15 + impact / 100, None,
                (f"Traffic on {r['item_id']} fell from {b:,.0f} to {c:,.0f} sessions a period since {since} — "
                 f"{_money(impact)}/period at current conversion. Ranking, ads, or a suppressed listing; "
                 f"we find which."), ev))
        elif m == "buy_box_pct":
            out.append(_draft(
                "pricing", "buybox_watch", subject, 40 + impact / 100, None,
                (f"Buy Box share on {r['item_id']} fell from {b:.0f}% to {c:.0f}% since {since}. "
                 f"Amazon is suppressing the Featured Offer — price, competitor, or account health; "
                 f"we step the price back if that is the cause."), ev))
        elif m == "cpc":
            # The auction moved under the campaign. Not banked: the response
            # curve is refitted on the new regime and the trim or reallocation
            # that follows carries its own promise.
            out.append(_draft(
                "advertising", "cpc_drift", subject, 15 + impact / 100, None,
                (f"The cost of a click on “{r['item_id']}” rose from ${b:.2f} to ${c:.2f} since {since} — about "
                 f"{_money(impact)} of extra ad cost per 30 days at its own click volume. The response curve fitted "
                 f"before that date no longer describes it; we refit on the new regime and hold the campaign out of "
                 f"reallocation until enough days have run. Check bids, match types and new competitors in the auction."), ev))
        elif m == "sales_per_click":
            out.append(_draft(
                "advertising", "conversion_drift", subject, 15 + impact / 100, None,
                (f"Sales per click on “{r['item_id']}” fell from ${b:.2f} to ${c:.2f} since {since} — about "
                 f"{_money(impact)} of attributed sales per 30 days at its own click volume. The clicks are landing on "
                 f"a page that converts worse: price, Buy Box, reviews or the listing itself. The response curve is "
                 f"refitted on the new regime."), ev))
        elif m == "spend":
            # Banked (was None): the dollars are already computed, the action
            # is inside the standing mandate, and the proof is direct in the
            # next ppc_spend export. Measurement's first gate returns
            # "unmeasurable" when the client confirms the step-up was intended.
            out.append(_draft(
                "advertising", "spend_step", subject, 15 + impact / 100, round(impact, 2),
                (f"Daily spend on “{r['item_id']}” stepped up from {_money(b)} to {_money(c)} since "
                 f"{since} — about {_money(impact)} per 30 days. Confirm it was intended; we hold it "
                 f"at the marginal break-even otherwise."), ev))
    return out


def _latest_term_window(search_terms):
    rows = [r for r in search_terms or [] if r.get("period_start") and r.get("period_end")]
    if not rows:
        return None
    return max((str(r["period_start"]), str(r["period_end"])) for r in rows)


def _campaign_window_spend(search_terms, campaigns) -> dict:
    window = _latest_term_window(search_terms)
    out = {}
    for r in search_terms or []:
        if window and (str(r.get("period_start")), str(r.get("period_end"))) == window and r.get("campaign_name") in campaigns:
            out[r["campaign_name"]] = round(out.get(r["campaign_name"], 0.0) + float(r.get("spend") or 0), 2)
    return out


def _term_window_days(search_terms):
    window = _latest_term_window(search_terms)
    if not window:
        return None
    return (date.fromisoformat(window[1][:10]) - date.fromisoformat(window[0][:10])).days + 1


TRIM_DRAWS = 400
TRIM_MIN_PRODUCTIVE_SHARE = 0.25


def _trim_net_draws(r: dict, new_spend: float, avg_margin: float):
    """30 days of spend saved less the margin the fitted curve gives up
    between today's spend and the trimmed one, on the curve's own parameter
    draws. None without a curve and a covariance to draw from."""
    from .models.ad_allocation import params_vector
    from .models.ad_efficiency import CURVE_SEED, curve_values, draw_params
    model = r.get("curve_model")
    cov = (r.get("details") or {}).get("curve_cov")
    if model not in ("hill", "log") or cov is None or not r.get("current_spend"):
        return None
    theta = draw_params(model, params_vector(r), np.asarray(cov, dtype=float), TRIM_DRAWS,
                        np.random.default_rng(CURVE_SEED))
    if theta is None or len(theta) < 50:
        return None
    cur = float(r["current_spend"])
    vals = curve_values(model, theta, [cur, max(float(new_spend), 0.01)])
    net = MEASUREMENT_HORIZON_DAYS * ((cur - float(new_spend)) - avg_margin * (vals[:, 0] - vals[:, 1]))
    net = net[np.isfinite(net)]
    return net if net.size >= 50 else None


def trim_candidates(ads: list[dict], avg_margin: float) -> dict[str, dict]:
    """The campaigns a trim will be drafted for this run, with the break-even
    the trim is sized against — one rule, used by the trim loop below and by the
    budget reallocation so no campaign carries two promises in one cycle.

    The trim is sized off the CONSERVATIVE end of the break-even's own interval
    when the fit produced one: a higher break-even means a smaller trim and a
    smaller promise, which is the direction to be wrong in on a number the
    client is billed against. No trim when the interval reaches current spend."""
    out = {}
    for r in ads:
        if not (r.get("status") == "ok" and r.get("current_spend") and r.get("breakeven_spend")
                and float(r["current_spend"]) > float(r["breakeven_spend"])):
            continue
        uncertainty = (r.get("details") or {}).get("uncertainty") or {}
        breakeven = float(r["breakeven_spend"])
        if uncertainty.get("breakeven_p95") is not None:
            breakeven = max(breakeven, float(uncertainty["breakeven_p95"]))
        if float(r["current_spend"]) <= breakeven:
            continue
        out[r["campaign_name"]] = {"breakeven": breakeven, "excess": float(r["current_spend"]) - breakeven,
                                   "uncertainty": uncertainty}
    return out


def _budget_reallocation_directive(alloc: dict | None, share: float = DOWNSIDE_GUARD_SHARE) -> dict | None:
    """Money between campaigns: the same total, moved to where the marginal
    dollar returns more. Standing under the advertising mandate — no total
    changes — unless its own bad case exceeds the campaign set's risk budget."""
    if not alloc or alloc.get("status") != "ok":
        return None
    moved = [c for c in alloc.get("campaigns") or []
             if c.get("status") == "ok" and abs(float(c.get("move") or 0)) >= 1.0]
    if not moved:
        return None
    gives = sorted((c for c in moved if float(c["move"]) < 0), key=lambda c: float(c["move"]))
    takes = sorted((c for c in moved if float(c["move"]) > 0), key=lambda c: -float(c["move"]))
    total_moved = sum(-float(c["move"]) for c in gives)

    def _named(cs):
        return ", ".join(f"“{c['campaign_name']}” ${float(c['current']):,.0f}→${float(c['recommended']):,.0f}"
                         for c in cs[:4]) + ("…" if len(cs) > 4 else "")

    lam, be = float(alloc.get("lambda") or 0), float(alloc.get("breakeven_marginal_roas") or 0)
    lo, hi = alloc.get("delta_p5"), alloc.get("delta_p95")
    rng = ""
    if lo is not None and hi is not None:
        rng = (f" (90% range {'+' if lo >= 0 else '−'}{_money(lo)} to {'+' if hi >= 0 else '−'}{_money(hi)}")
        if alloc.get("p_loss") is not None:
            loss = float(alloc["p_loss"])
            rng += ("; under a 1% chance it goes the other way" if loss < 0.01
                    else f"; a {loss:.0%} chance it goes the other way")
        rng += ")"
    total_note = ""
    if lam and be:
        total_note = (f" That common return is {'above' if lam > be else 'below'} the {be:.2f} break-even, so the "
                      f"total is {'under' if lam > be else 'over'}-spent as a whole; the next cycle re-measures "
                      f"before the total moves.")
    horizon = int(alloc.get("horizon_days") or MEASUREMENT_HORIZON_DAYS)
    text = (f"Move {_money(total_moved)}/day between campaigns at the same {_money(alloc['total_spend'])}/day total — "
            f"from {_named(gives)} to {_named(takes)}. Every campaign then returns about the same "
            f"${lam:,.2f} of sales per marginal dollar.{total_note} "
            f"Expected +{_money(alloc['delta_p50'])} over {horizon} days{rng}.")
    subject = sorted((c["campaign_name"], c["current"], c["recommended"]) for c in moved)
    ok_rows = [c for c in alloc["campaigns"] if c.get("status") == "ok"]
    margin = float(alloc.get("avg_margin") or 0)
    monthly_net = horizon * max(0.0, sum(margin * float(c.get("current_sales") or 0) - float(c.get("current") or 0)
                                         for c in ok_rows))
    draft = _draft(
        "advertising", "budget_reallocation", subject,
        score=10 + float(alloc["delta_p50"]) / 100,
        expected=alloc["delta_p50"],
        action_text=text,
        evidence={
            "campaigns": alloc["campaigns"],
            "total_spend": alloc["total_spend"],
            "total_moved": round(total_moved, 2),
            "lambda": alloc.get("lambda"),
            "breakeven_marginal_roas": alloc.get("breakeven_marginal_roas"),
            "avg_margin": alloc.get("avg_margin"),
            "horizon_days": horizon,
            "delta_p5": alloc.get("delta_p5"), "delta_p50": alloc.get("delta_p50"),
            "delta_p95": alloc.get("delta_p95"), "delta_mean": alloc.get("delta_mean"),
            "p_loss": alloc.get("p_loss"), "mc_se": alloc.get("mc_se"), "mc_inputs": alloc.get("mc_inputs"),
            "alpha": alloc.get("alpha"), "policy": alloc.get("policy"),
            "free_budget": alloc.get("free_budget"),
            "campaign_monthly_net": round(monthly_net, 2),
        },
    )
    return downside_guard(draft, None, share=share, monthly_net=monthly_net)


SWITCHBACK_MIN_SPEND = 20.0     # a campaign under this a day is not worth a four-week test
EXPERIMENTS_PER_RUN = 3         # randomised price tests drafted per cycle, largest SKUs first


def _price_experiment_directive(fit: dict | None, margin_row: dict, sku: str, reason: str,
                                client_id: str | None, today: date, fee_history=None) -> dict | None:
    """The instrument: a randomised six-block price test inside the 5% cap.
    Standing under the pricing mandate — every arm is a step the client already
    authorised — and worth no dollars in itself; the next fit uses its answer."""
    from .models.price_experiment import design

    start = (today + timedelta(days=1)).isoformat()
    d = design(client_id or "", sku, start, margin_row,
               fit if fit and fit.get("status") == "ok" else None, fee_history)
    if d.get("status") != "ok":
        return None
    seq = " → ".join(f"${b['price']:.2f}" for b in d["blocks"])
    why = {
        "no_variation": ("The price has barely moved in the history, so no elasticity can be fitted at all; "
                         "the test creates the variation."),
        "near_unit_elastic": ("The history cannot separate this SKU's demand from the point where a price move "
                              "pays for itself, and a history set in response to demand reads about half an "
                              "elasticity too flat; a randomised test is the one measurement that does not."),
    }.get(reason, "A randomised test is the one price measurement not set in response to demand.")
    cost = d.get("expected_test_cost")
    if cost:
        p50 = float(cost["p50"])
        cost_text = (f" Expected {'+' if p50 >= 0 else '−'}{_money(p50)} against holding ${d['p0']:.2f} over the "
                     f"six weeks (90% range {'+' if cost['p5'] >= 0 else '−'}{_money(cost['p5'])} to "
                     f"{'+' if cost['p95'] >= 0 else '−'}{_money(cost['p95'])}).")
    else:
        cost_text = " No fit yet, so the arms are weighted equally and the cost of the test is not priced."
    text = (f"Run a randomised price test on {sku}: six 7-day blocks from {start}, {seq} — every price inside "
            f"the 5% cap. {why}{cost_text} Buy Box watched throughout; nothing is banked on the test itself.")
    return _draft(
        "pricing", "price_experiment", (sku, start),
        score=16,
        expected=None,
        action_text=text,
        evidence={
            "sku": sku, "p0": d["p0"], "reason": reason, "design": d,
            "start_date": d["start_date"], "end_date": d["end_date"], "seed": d["seed"],
            "expected_test_cost": cost,
            "elasticity": fit.get("elasticity") if fit else None,
            "std_err": fit.get("std_err") if fit else None,
            "ci95": (fit.get("details") or {}).get("ci95") if fit else None,
            "baseline_units": float(margin_row.get("units") or 0),
            "baseline_revenue": float(margin_row.get("revenue") or 0),
            "baseline_period": str(margin_row.get("period_start")),
        },
    )


def _switchback_directive(incr: dict | None, ads: list[dict], avg_margin: float,
                          client_id: str | None, today: date) -> dict | None:
    """Design the switchback when nothing yet identifies ι: no executed test on
    file, and the observational estimate either refused or straddles 1. One
    campaign at a time — the largest ok campaign without a test — because the
    test costs four weeks of that campaign's OFF days."""
    from .models.incrementality import design_switchback

    if not incr:
        return None
    if incr.get("incrementality_for_breakeven") is not None:
        return None
    obs = incr.get("observational") or {}
    if obs.get("status") == "ok" and obs.get("ci95") and (obs["ci95"][1] < 1 or obs["ci95"][0] > 1):
        return None   # the history already says which way, no experiment needed
    tested = {t.get("campaign") for t in incr.get("switchbacks") or []}
    candidates = sorted((r for r in ads if r.get("status") == "ok" and r.get("campaign_name") not in tested
                         and float(r.get("current_spend") or 0) >= SWITCHBACK_MIN_SPEND),
                        key=lambda r: -float(r.get("current_spend") or 0))
    if not candidates:
        return None
    r = candidates[0]
    start = (today + timedelta(days=1)).isoformat()
    schedule = design_switchback(client_id or "", r["campaign_name"], start)
    off_days = sum(1 for b in schedule["blocks"] if b["arm"] == "off") * schedule["block_days"]
    prior = float(obs["incrementality"]) if obs.get("status") == "ok" else 1.0
    spend, sales = float(r.get("current_spend") or 0), float(r.get("current_sales") or 0)
    cost = off_days * max(0.0, avg_margin * sales - spend) * prior
    lo = hi = None
    unc = (r.get("details") or {}).get("uncertainty") or {}
    if unc.get("basis") == "parameter_covariance" and r.get("details", {}).get("curve_cov") is not None:
        from .models.ad_efficiency import curve_values, draw_params
        from .models.ad_allocation import params_vector
        theta = draw_params(r["curve_model"], params_vector(r), r["details"]["curve_cov"])
        if theta is not None:
            sales_draws = curve_values(r["curve_model"], theta, [spend])[:, 0]
            costs = off_days * np.maximum(0.0, avg_margin * sales_draws - spend) * prior
            lo, hi = float(np.quantile(costs, 0.05)), float(np.quantile(costs, 0.95))
            # the point and the band on one basis: the curve's own draws
            cost = float(np.quantile(costs, 0.5))
    band = f" (90% range {_money(lo)} to {_money(hi)})" if lo is not None else ""
    text = (f"Run a four-week ON/OFF test on “{r['campaign_name']}”: {schedule['n_blocks']} randomised "
            f"{schedule['block_days']}-day blocks from {start}, {off_days} days paused. It measures how much of "
            f"the campaign's attributed sales are truly incremental — the one number that says whether its "
            f"break-even is too generous or too strict, which no monthly export can. Expected cost about "
            f"{_money(cost)} of attributed profit on the paused days{band}; nothing is banked on the test "
            f"itself, and the break-even is corrected from the next run.")
    return _draft(
        "advertising", "ad_switchback", (r["campaign_name"], start),
        score=12 + spend / 10,
        expected=None,
        action_text=text,
        evidence={"campaign_name": r["campaign_name"], "schedule": schedule,
                  "current_spend": spend, "current_sales": sales, "avg_margin": avg_margin,
                  "incrementality_prior": prior, "expected_cost": round(cost, 2),
                  "expected_cost_p5": num(lo), "expected_cost_p95": num(hi),
                  "observational": {k: obs.get(k) for k in ("status", "incrementality", "ci95")}},
    )


def draft_directives(inventory, ads, elasticity, margins,
                     search_terms=None, brand_terms=None,
                     recovery=None, inv_econ=None, anomaly_rows=None,
                     channel: str | None = "amazon",
                     downside_share: float = DOWNSIDE_GUARD_SHARE,
                     ad_allocation: dict | None = None,
                     incrementality: dict | None = None,
                     client_id: str | None = None,
                     experiments: list[dict] | None = None,
                     cross_price: dict | None = None,
                     markdown: dict | None = None,
                     replenishment: dict | None = None,
                     cash_orders: dict | None = None,
                     assortment: dict | None = None,
                     risk_share: float | None = None,
                     cash: dict | None = None,
                     book_out: dict | None = None,
                     ppc_spend_rows: list[dict] | None = None) -> list[dict]:
    """`channel` names the platform the run was computed on (channels.py):
    it changes the words, never the arithmetic.

    `downside_share` is the downside guard: a directive whose 5th-percentile
    outcome risks more than this share of its SKU's trailing monthly net is
    routed to an explicit yes whatever its step size.

    `ad_allocation` is models.ad_allocation's output for this run; campaigns it
    moves were excluded from the trims at the point it was computed
    (trim_candidates), so the two never promise on the same campaign."""
    today = date.today()
    # the client's stated risk tolerance governs both how far a move walks and
    # whether it may walk under the standing mandate
    if risk_share is not None:
        downside_share = float(risk_share)
    latest_by_sku = _latest_margins_by_sku(margins)
    econ_by_sku = {r["sku"]: r for r in (inv_econ or {}).get("rows", [])}
    # The margin the ad lever is evaluated against — the same figure
    # ad_efficiency uses for break-even, so a trim's promise and its later
    # measurement are computed on one number.
    avg_margin = average_margin(margins) or 0.0
    drafts = []

    rec = _recovery_directive(recovery)
    if rec:
        drafts.append(rec)
    # Excess stock, three ways. A markdown or a stretch on a SKU is its price
    # instruction for the cycle: the ordinary price step stands aside, and the
    # aged-surcharge draft too, since the markdown is what clears it.
    md_rows = {r["sku"]: r for r in (markdown or {}).get("rows", [])}
    fits_by_sku = {f["item_id"]: f for f in elasticity if f.get("level") == "sku"}
    md_skus: set[str] = set()
    for sku, row in md_rows.items():
        d = _markdown_directive(row, latest_by_sku.get(sku), fits_by_sku.get(sku))
        if d:
            drafts.append(downside_guard(d, latest_by_sku.get(sku), downside_share))
            md_skus.add(sku)
        st = _stretch_directive(row, latest_by_sku.get(sku), fits_by_sku.get(sku))
        if st:
            drafts.append(downside_guard(st, latest_by_sku.get(sku), downside_share))
            md_skus.add(sku)
    for liq in _liquidation_directives(inv_econ, channel, markdown):
        # an inflow: the program pays out within a week or two
        ruin_guard(liq, cash, 14, -float(liq["evidence"].get("liquidate_value") or 0))
        drafts.append(liq)
    drafts += _fee_bleed_directives(inv_econ, today, channel,
                                    exclude={s for s, r in md_rows.items() if r.get("decision") == "markdown"})
    drafts += _anomaly_directives(anomaly_rows, channel)

    rep_by_sku = {x["sku"]: x for x in (replenishment or {}).get("rows", [])}
    supplier_events = {x["supplier"]: x for x in (replenishment or {}).get("suppliers", [])}
    # When the cash cannot fund every order, one directive carries the set it
    # supports and the individual reorders for those SKUs stand aside.
    budget_set = _budget_order_set_directive(cash_orders)
    funded_skus = {o["sku"] for o in (budget_set["evidence"]["orders"] if budget_set else [])}
    if budget_set:
        drafts.append(budget_set)
    planned = ((cash or {}).get("details") or {}).get("wires") or []

    def _in_plan(skus, day=None) -> float:
        """What the cone's own plan already wires for these SKUs (on `day`, or
        their first wire): the ruin a directive adds is only its difference.
        Corrected 2026-09-24 — the guard charged every reorder in full on a
        cone whose plan already paid for it, so a sweep of reorders read as
        ruin on the model-risk bench when the plan itself did not."""
        total, seen = 0.0, set()
        for w in planned:
            if w.get("sku") in skus and w["sku"] not in seen and (day is None or int(w.get("day") or 0) == day):
                total += float(w.get("amount") or 0)
                seen.add(w["sku"])
        return total

    if budget_set:
        first_day = min((int(w.get("day") or 0) for w in planned), default=0)
        covered = {o.get("sku") for o in budget_set["evidence"].get("orders") or [] if isinstance(o, dict)}
        in_plan = _in_plan(covered)
        budget_set["evidence"]["wire_in_plan_usd"] = round(in_plan, 2)
        ruin_guard(budget_set, cash, first_day, float(budget_set["evidence"].get("wire_total") or 0) - in_plan)
    for r in inventory:
        if float(r["stockout_probability"] or 0) >= STOCKOUT_ALERT:
            if r["sku"] in funded_skus:
                continue
            reorder = _inventory_directive(r, latest_by_sku.get(r["sku"]), today, econ_by_sku.get(r["sku"]), channel,
                                           rep_row=rep_by_sku.get(r["sku"]), supplier_events=supplier_events)
            if reorder["evidence"].get("wire_usd"):
                rate = float(r.get("daily_velocity_mean") or 0)
                position = int(r.get("on_hand_units") or 0) + int(r.get("inbound_units") or 0)
                day = max(0, int((position - int(r.get("reorder_point") or 0)) / rate)) if rate > 0 else 0
                in_plan = _in_plan({r["sku"]}, day)
                reorder["evidence"]["wire_in_plan_usd"] = round(in_plan, 2)
                ruin_guard(reorder, cash, day, float(reorder["evidence"]["wire_usd"]) - in_plan)
            drafts.append(reorder)
            ex = _expedite_directive(rep_by_sku.get(r["sku"]), econ_by_sku.get(r["sku"]))
            if ex:
                ruin_guard(ex, cash, 0, float(ex["evidence"].get("freight_premium") or 0))
                drafts.append(ex)

    bleed_total = sum(t["spend"] or 0 for r in ads for t in (r["bleed_terms"] or []))
    if bleed_total > 0:
        n = sum(len(r["bleed_terms"] or []) for r in ads)
        # The exact terms, and the campaign each sits in — measurement proves
        # this by finding their spend gone from the next search-term export,
        # and needs the campaign to check it was not simply paused wholesale.
        terms = sorted(
            ({"campaign_name": r.get("campaign_name"), "search_term": t.get("search_term"),
              "spend": float(t.get("spend") or 0), "clicks": t.get("clicks")}
             for r in ads for t in (r["bleed_terms"] or [])),
            key=lambda t: (t["campaign_name"] or "", t["search_term"] or ""),
        )
        # Corrected 2026-09-24: the promise was the export window's spend (28
        # days here) with no band, beside thirty-day promises with bands. Now
        # the window's daily rate over the horizon, with the spread of the
        # campaigns' own daily spend over the days on file as its band.
        window_days_b = float(_term_window_days(search_terms) or 30)
        bleed_30 = bleed_total * MEASUREMENT_HORIZON_DAYS / window_days_b
        camps_b = {t["campaign_name"] for t in terms}
        daily_b = {}
        for row in (ppc_spend_rows or []):
            if row.get("campaign_name") in camps_b and row.get("report_date"):
                daily_b.setdefault(str(row["report_date"])[:10], 0.0)
                daily_b[str(row["report_date"])[:10]] += float(row.get("spend") or 0)
        vals_b = np.array(list(daily_b.values()), dtype=float)
        cv_b = float(vals_b.std(ddof=1) / vals_b.mean()) if vals_b.size >= 14 and vals_b.mean() > 0 else 0.25
        half_b = 1.645 * cv_b / np.sqrt(window_days_b)
        drafts.append(_draft(
            "advertising", "ad_bleed_terms",
            [(t["campaign_name"], t["search_term"]) for t in terms],
            score=bleed_total,
            expected=round(bleed_30, 2),
            action_text=(
                f"Negative-match {n} search terms that spent with zero attributed sales — "
                f"{_money(bleed_total)} of pure bleed in the export window. "
                f"Term list attached to this cycle's report."
            ),
            evidence={
                "terms": terms,
                "baseline_spend": round(bleed_total, 2),
                "horizon_days": MEASUREMENT_HORIZON_DAYS,
                "delta_p5": round(bleed_30 * (1 - half_b), 2),
                "delta_p50": round(bleed_30, 2),
                "delta_p95": round(bleed_30 * (1 + half_b), 2),
                "band_basis": (f"the campaigns' daily spend varies {cv_b:.0%} day to day; the window's "
                               f"{window_days_b:.0f}-day rate carries that spread over the horizon"),
                # The campaign's WHOLE baseline spend, not just the bleed terms':
                # measurement caps the saving at how far the campaign's own
                # spend actually fell, and that comparison is only honest
                # between two totals of the same shape.
                # Corrected 2026-09-24: this held each campaign's DAILY spend,
                # and the measurement caps the saving at how far the campaign's
                # WINDOW total fell — a day against a month, so the cap zeroed
                # every saving and no negation was ever banked. Now the
                # campaign's search-term spend over the same export window.
                "campaign_baseline_spend": _campaign_window_spend(search_terms, {r.get("campaign_name")
                                                                              for r in ads if r.get("bleed_terms")}),
                "campaign_baseline_basis": "search-term export window total",
                "baseline_days": _term_window_days(search_terms),
                "baseline_period_end": max((r.get("period_end") for r in ads
                                            if r.get("period_end")), default=None),
            },
        ))

    trims = trim_candidates(ads, avg_margin)
    # zero-sale spend the negation above removes, per campaign per day: a trim
    # on the same campaign is a budget ON TOP of it (break-even less the waste),
    # and one whose target sits under a quarter of the productive spend left
    # after the negation waits a cycle — the curve fitted on blended spend
    # cannot size a cut that deep once the waste is gone (added 2026-09-24)
    window_days = float(_term_window_days(search_terms) or 30)
    waste_daily = {}
    for r in ads:
        for t in (r.get("bleed_terms") or []):
            waste_daily[r.get("campaign_name")] = waste_daily.get(r.get("campaign_name"), 0.0) + float(t.get("spend") or 0) / window_days
    for r in ads:
        name = r.get("campaign_name")
        if name in trims:
            w = waste_daily.get(name, 0.0)
            cur_ = float(r["current_spend"])
            if w > 0 and trims[name]["breakeven"] - w < TRIM_MIN_PRODUCTIVE_SHARE * (cur_ - w):
                trims.pop(name)
    for r in ads:
        if r.get("campaign_name") in trims:
            uncertainty = trims[r["campaign_name"]]["uncertainty"]
            breakeven = trims[r["campaign_name"]]["breakeven"]
            excess = trims[r["campaign_name"]]["excess"]
            # Promise the NET saving, not the gross. Those dollars were buying
            # something; a promise measurement can never confirm is a promise
            # we should not make.
            roas = float(r.get("marginal_roas") or 0)
            keep = max(0.0, min(1.0, roas * avg_margin)) if roas > 0 else 0.0
            net = excess * MEASUREMENT_HORIZON_DAYS * (1 - keep)
            # Corrected 2026-09-24: the margin a trim gives up is the curve's
            # own drop between the two spends, not the cut times the marginal
            # return at today's spend — that return is the LOWEST on the cut,
            # so the linear figure overstated every trim's net saving (the
            # model-risk bench: true saving 0.58 of the promise). On the
            # fitted curve's own draws when it has a covariance.
            net_draws = _trim_net_draws(r, breakeven, avg_margin)
            band = {}
            if net_draws is not None:
                net = float(np.quantile(net_draws, 0.5))
                band = {"delta_p5": round(float(np.quantile(net_draws, 0.05)), 2),
                        "delta_p50": round(net, 2),
                        "delta_p95": round(float(np.quantile(net_draws, 0.95)), 2),
                        "p_loss": round(float(np.mean(net_draws < 0)), 4),
                        "curve_model": r.get("curve_model"), "curve_params": r.get("curve_params"),
                        "curve_cov": (r.get("details") or {}).get("curve_cov"),
                        "current_sales": r.get("current_sales"), "net_basis": "fitted curve, parameter draws"}
            drafts.append(_draft(
                "advertising", "campaign_trim", r["campaign_name"],
                score=excess,
                expected=round(net, 2) if net > 0 else None,
                action_text=(
                    f"Trim “{r['campaign_name']}” toward its marginal break-even: "
                    f"${breakeven:,.0f} vs ${float(r['current_spend']):,.0f} today. "
                    f"The last dollars in are buying less than a dollar back."
                    + (f" With this sweep's negative matches removing ${waste_daily[r['campaign_name']]:,.0f} a day "
                       f"of zero-sale spend, set the daily budget to "
                       f"${breakeven - waste_daily[r['campaign_name']]:,.0f}."
                       if waste_daily.get(r["campaign_name"], 0.0) > 0.5 else "")
                    + (f" The fitted break-even sits between ${float(uncertainty['breakeven_p5']):,.0f} "
                       f"and ${float(uncertainty['breakeven_p95']):,.0f}; we trim to the cautious end."
                       if uncertainty.get("breakeven_p5") is not None else "")
                ),
                evidence={
                    "campaign_name": r["campaign_name"],
                    "current_spend": float(r["current_spend"]),
                    "breakeven_spend": float(r["breakeven_spend"]),
                    "breakeven_used": round(breakeven, 2),
                    "negated_daily": round(waste_daily.get(r["campaign_name"], 0.0), 2),
                    "budget_after_negation": round(breakeven - waste_daily.get(r["campaign_name"], 0.0), 2),
                    "breakeven_p5": uncertainty.get("breakeven_p5"),
                    "breakeven_p95": uncertainty.get("breakeven_p95"),
                    "p_below_breakeven": uncertainty.get("p_below_breakeven"),
                    "marginal_roas": roas or None,
                    "avg_margin": avg_margin,
                    "horizon_days": MEASUREMENT_HORIZON_DAYS,
                    **band,
                    "incrementality": (r.get("details") or {}).get("incrementality"),
                    "clv_multiplier": (r.get("details") or {}).get("clv_multiplier"),
                    "clv_basis": (r.get("details") or {}).get("clv_basis"),
                    "ltv_cac": (r.get("details") or {}).get("ltv_cac"),
                    "payback_weeks": (r.get("details") or {}).get("payback_weeks"),
                },
            ))

    realloc = _budget_reallocation_directive(ad_allocation, downside_share)
    if realloc:
        drafts.append(realloc)
    switchback = _switchback_directive(incrementality, ads, avg_margin, client_id, today)
    if switchback:
        drafts.append(switchback)

    spend, n_terms = branded_spend(search_terms or [], brand_terms or [])
    if spend >= BRANDED_SPEND_MIN:
        saving = round(spend * INCREMENTALITY_MID, 2)
        drafts.append(_draft(
            "advertising", "branded_pause", sorted(brand_terms or []),
            score=spend,
            expected=saving,
            action_text=(
                f"You're paying for your own brand: {_money(spend)} across {n_terms} branded "
                f"search terms last window. Industry incrementality studies put 25–60% of that "
                f"as sales you'd capture organically anyway. Pause exact-match branded targeting "
                f"as a tracked test — expected savings ≈ {_money(saving)}/period, and the Profit Record "
                f"measures the truth."
            ),
            evidence={
                "brand_terms": sorted(brand_terms or []),
                "baseline_spend": round(spend, 2),
                "n_terms": n_terms,
                "incrementality_mid": INCREMENTALITY_MID,
                "avg_margin": avg_margin,
            },
        ))

    cross_by_sku = (cross_price or {}).get("by_sku") or {}

    def _cross_for(sku: str) -> dict | None:
        """The family's side of a move on `sku`: each sibling's baseline
        volume, contribution and the weight this SKU's price carries in the
        sibling's index. Siblings without landed cost are left out and said."""
        info = cross_by_sku.get(sku)
        if not info:
            return None
        sibs = []
        for sib in info.get("siblings") or []:
            m = latest_by_sku.get(sib["sku"])
            if not m or m.get("cogs") is None:
                continue
            units, revenue = float(m.get("units") or 0), float(m.get("revenue") or 0)
            if units <= 0 or revenue <= 0:
                continue
            f, big_f, _ = fee_terms(m)
            fees = float(m.get("amazon_fees") or 0)
            sibs.append({"sku": sib["sku"], "q0": units, "weight": float(sib["weight"]),
                         "contribution": revenue / units * (1 - f) - float(m["cogs"]) / units - big_f,
                         "baseline_units": units, "baseline_profit": revenue - fees - float(m["cogs"])})
        if not sibs:
            return None
        return {"eps": info["eps_cross"], "std_err": info["se_cross"], "dof": info.get("dof"),
                "family": info["family"], "siblings": sibs}

    near_unit: set[str] = set()
    for fit in elasticity:
        if fit.get("status") != "ok" or fit.get("level") != "sku" or fit["item_id"] in md_skus:
            continue
        margin_row = latest_by_sku.get(fit["item_id"])
        if not margin_row:
            continue
        d = _pricing_directive(fit, margin_row, margins, cross=_cross_for(fit["item_id"]), risk_share=risk_share)
        if d:
            if (d.get("evidence") or {}).get("status") == "near_unit_elastic":
                near_unit.add(fit["item_id"])
            drafts.append(downside_guard(d, margin_row, downside_share))

    # The instrument. SKUs the history cannot price — no price variation at all,
    # or a fit that cannot be separated from the pole — get a randomised test,
    # largest first, a few per cycle, never one that already has a live test.
    live_tests = {t.get("sku") for t in experiments or []
                  if t.get("design") and t.get("status") in ("planned", "running")}
    candidates = []
    for fit in elasticity:
        if fit.get("level") != "sku" or fit["item_id"] in live_tests:
            continue
        if (fit.get("details") or {}).get("source") == "experiment":
            continue
        margin_row = latest_by_sku.get(fit["item_id"])
        if not margin_row:
            continue
        if fit.get("status") == "insufficient_price_variation":
            candidates.append((float(margin_row.get("revenue") or 0), fit, margin_row, "no_variation"))
        elif fit["item_id"] in near_unit:
            candidates.append((float(margin_row.get("revenue") or 0), fit, margin_row, "near_unit_elastic"))
    for _, fit, margin_row, reason in sorted(candidates, key=lambda c: -c[0])[:EXPERIMENTS_PER_RUN]:
        d = _price_experiment_directive(fit, margin_row, fit["item_id"], reason, client_id, today,
                                        _fee_history(fit["item_id"], margins or []))
        if d:
            drafts.append(d)

    # SKUs to cut or merge on the loaded, survival-discounted contribution; an
    # exit supersedes the one-period negative-margin instruction for its SKU
    exits: set[str] = set()
    for row in (assortment or {}).get("rows", []):
        d = _sku_exit_directive(row, latest_by_sku.get(row["sku"]))
        if d:
            drafts.append(d)
            exits.add(row["sku"])

    if margins:
        latest = max(m["period_start"] for m in margins)
        for m in margins:
            if m["sku"] in exits:
                continue
            if m["period_start"] == latest and m["net_margin"] is not None and float(m["net_margin"]) < 0:
                loss = abs(float(m["net_margin"]))
                # The instruction is a menu of three, so measurement has to read
                # from the client's own data WHICH one happened before it can
                # value it — the baseline for all three is captured here.
                drafts.append(_draft(
                    "margin", "negative_margin_sku", m["sku"],
                    score=loss,
                    expected=round(loss, 2),
                    action_text=(
                        f"{m['sku']} sold at a loss last period (net -{_money(loss)} after fees, "
                        f"COGS and ads) — reprice, cut its ad allocation, or plan its exit."
                    ),
                    evidence={
                        "sku": m["sku"],
                        "baseline_period": str(latest),
                        "baseline_units": float(m.get("units") or 0),
                        "baseline_revenue": float(m.get("revenue") or 0),
                        "baseline_net": float(m["net_margin"]),
                        "baseline_cogs": float(m["cogs"]) if m.get("cogs") is not None else None,
                        "baseline_fees": float(m.get("amazon_fees") or 0),
                        "baseline_ad_spend": float(m.get("ad_spend_allocated") or 0),
                    },
                ))

    drafts.sort(key=lambda d: d["score"], reverse=True)
    # the sweep as one book: the standing directives' joint shortfall against
    # the client's budget, and the sweep's cash moves together against the
    # ruin line; demotions and deferrals land on the drafts themselves
    from .models import portfolio
    book = portfolio.run(drafts, margins, cash=cash, risk_share=risk_share)
    if book_out is not None:
        book_out.clear()
        book_out.update(book)
    return drafts
