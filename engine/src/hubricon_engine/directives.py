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
from datetime import date, timedelta

from . import channels
from .models import fee_schedule
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
STANDING = {"ad_bleed_terms", "campaign_trim", "branded_pause", "spend_step", "price_step"}

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
ANOMALY_MIN_IMPACT = 100.0     # per period
LIQUIDATION_MIN_GAIN = 100.0
ANOMALY_LABELS = {
    "fee_per_unit": "total Amazon fees per unit", "fba_fee_per_unit": "FBA fulfillment fee per unit",
    "referral_rate": "referral fee rate", "storage_fee": "storage fee",
    "sessions": "traffic", "unit_session_pct": "conversion", "buy_box_pct": "Buy Box share", "spend": "daily spend",
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
                   share: float = DOWNSIDE_GUARD_SHARE) -> dict:
    """Route a draft to an explicit yes when its bad case is too big, in place.

    A directive that carries a simulated profit-delta distribution carries its
    own 5th percentile. If the loss at that percentile exceeds `share` of the
    SKU's trailing monthly net, the move is no longer inside what the standing
    mandate covers — whatever its step size — and it goes to the client for a
    signature with the reason on the record.

    Drafts with no delta distribution are left alone: this guard is about a
    quantified downside, and inventing one in order to gate on it would be the
    thing the engine does not do."""
    evidence = draft.get("evidence") or {}
    p5 = evidence.get("delta_p5")
    if p5 is None or margin_row is None:
        return draft
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


def _inventory_directive(r: dict, margin_row: dict | None, today: date, econ_row: dict | None = None,
                         channel: str | None = "amazon") -> dict:
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

    if econ_row and econ_row.get("order_qty_econ") and econ_row.get("wire_econ") is not None:
        # the newsvendor sized it: the service level is the one the margin justifies
        q = float(econ_row["critical_fractile"])
        text = (
            f"Wire {_money(float(econ_row['wire_econ']))} to your supplier by {by_text} — "
            f"{int(econ_row['order_qty_econ'])} units of {r['sku']}. Sized to a {q:.0%} service level, "
            f"the level your margin justifies (C_u ÷ (C_u + C_o), storage and the season priced in); "
            f"lead time {r['lead_time_days']}d, current stockout risk {p:.0%}."
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


def _pricing_directive(fit: dict, margin_row: dict, margins: list[dict] | None = None) -> dict | None:
    move = price_move(margin_row, fit, fee_history=_fee_history(fit["item_id"], margins or []))
    sku = fit["item_id"]
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


def _liquidation_directives(inv_econ: dict | None, channel: str | None = "amazon") -> list[dict]:
    out = []
    program = "Amazon's liquidation program" if channels.has_fee_cliffs(channel) else "a clearance sale"
    for r in (inv_econ or {}).get("rows", []):
        if r.get("decision") != "liquidate":
            continue
        gain = float(r.get("liquidate_value") or 0) - float(r.get("hold_npv") or 0)
        if gain < LIQUIDATION_MIN_GAIN:
            continue
        aged = float(r.get("aged_surcharge_month") or 0)
        out.append(_draft(
            "inventory", "liquidation", r["sku"],
            score=30 + gain / 100,
            expected=round(gain, 2),
            action_text=(
                f"Liquidate {int(r['excess_units'])} excess units of {r['sku']}: {program} returns about "
                f"{_money(float(r['liquidate_value']))} now, against {_money(float(r['hold_npv']))} from holding and "
                f"selling them down with storage, the aged surcharge and capital priced in"
                + (f" — the surcharge alone is {_money(aged)}/month." if aged else ".")
            ),
            evidence={
                "sku": r["sku"],
                "excess_units": int(r["excess_units"]),
                "liquidate_value": float(r["liquidate_value"]),
                "hold_npv": float(r["hold_npv"]),
                "aged_surcharge_month": aged,
            },
        ))
    return out


BLEED_MIN_MONTH = 75.0     # below this a fee line is not worth a decision


def _fee_bleed_directives(inv_econ: dict | None, today: date, channel: str | None = "amazon") -> list[dict]:
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
    aged_rows = [r for r in rows if (r.get("aged_surcharge_month") or 0) > 0
                 and r.get("decision") != "liquidate"]   # liquidation owns those SKUs
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
        adverse_up = r["metric"] in ("fee_per_unit", "fba_fee_per_unit", "referral_rate", "storage_fee", "spend", "monthly_total")
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


def draft_directives(inventory, ads, elasticity, margins,
                     search_terms=None, brand_terms=None,
                     recovery=None, inv_econ=None, anomaly_rows=None,
                     channel: str | None = "amazon",
                     downside_share: float = DOWNSIDE_GUARD_SHARE) -> list[dict]:
    """`channel` names the platform the run was computed on (channels.py):
    it changes the words, never the arithmetic.

    `downside_share` is the downside guard: a directive whose 5th-percentile
    outcome risks more than this share of its SKU's trailing monthly net is
    routed to an explicit yes whatever its step size."""
    today = date.today()
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
    drafts += _liquidation_directives(inv_econ, channel)
    drafts += _fee_bleed_directives(inv_econ, today, channel)
    drafts += _anomaly_directives(anomaly_rows, channel)

    for r in inventory:
        if float(r["stockout_probability"] or 0) >= STOCKOUT_ALERT:
            drafts.append(_inventory_directive(r, latest_by_sku.get(r["sku"]), today, econ_by_sku.get(r["sku"]), channel))

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
        drafts.append(_draft(
            "advertising", "ad_bleed_terms",
            [(t["campaign_name"], t["search_term"]) for t in terms],
            score=bleed_total,
            expected=round(bleed_total, 2),
            action_text=(
                f"Negative-match {n} search terms that spent with zero attributed sales — "
                f"{_money(bleed_total)} of pure bleed in the export window. "
                f"Term list attached to this cycle's report."
            ),
            evidence={
                "terms": terms,
                "baseline_spend": round(bleed_total, 2),
                # The campaign's WHOLE baseline spend, not just the bleed terms':
                # measurement caps the saving at how far the campaign's own
                # spend actually fell, and that comparison is only honest
                # between two totals of the same shape.
                "campaign_baseline_spend": {
                    r["campaign_name"]: float(r.get("current_spend") or 0)
                    for r in ads if r.get("campaign_name") and r.get("bleed_terms")
                },
                "baseline_period_end": max((r.get("period_end") for r in ads
                                            if r.get("period_end")), default=None),
            },
        ))

    for r in ads:
        if r["status"] == "ok" and r["current_spend"] and r["breakeven_spend"] \
                and float(r["current_spend"]) > float(r["breakeven_spend"]):
            excess = float(r["current_spend"]) - float(r["breakeven_spend"])
            # Promise the NET saving, not the gross. Those dollars were buying
            # something; a promise measurement can never confirm is a promise
            # we should not make.
            roas = float(r.get("marginal_roas") or 0)
            keep = max(0.0, min(1.0, roas * avg_margin)) if roas > 0 else 0.0
            net = excess * MEASUREMENT_HORIZON_DAYS * (1 - keep)
            drafts.append(_draft(
                "advertising", "campaign_trim", r["campaign_name"],
                score=excess,
                expected=round(net, 2) if net > 0 else None,
                action_text=(
                    f"Trim “{r['campaign_name']}” toward its marginal break-even: "
                    f"${float(r['breakeven_spend']):,.0f} vs ${float(r['current_spend']):,.0f} today. "
                    f"The last dollars in are buying less than a dollar back."
                ),
                evidence={
                    "campaign_name": r["campaign_name"],
                    "current_spend": float(r["current_spend"]),
                    "breakeven_spend": float(r["breakeven_spend"]),
                    "marginal_roas": roas or None,
                    "avg_margin": avg_margin,
                    "horizon_days": MEASUREMENT_HORIZON_DAYS,
                },
            ))

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

    for fit in elasticity:
        if fit.get("status") != "ok" or fit.get("level") != "sku":
            continue
        margin_row = latest_by_sku.get(fit["item_id"])
        if not margin_row:
            continue
        d = _pricing_directive(fit, margin_row, margins)
        if d:
            drafts.append(downside_guard(d, margin_row, downside_share))

    if margins:
        latest = max(m["period_start"] for m in margins)
        for m in margins:
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
    return drafts
