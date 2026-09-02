"""Inventory economics — the newsvendor with Amazon's fee cliffs priced in.

The inventory simulation answers "how likely is a stockout at a 95%
service target". This module answers the better question: what service
level does the money justify, SKU by SKU?

Critical fractile.  For one replenishment cycle the optimal in-stock
probability is q* = C_u / (C_u + C_o):

    C_u  cost of being one unit short  = lost contribution margin
                                          + the low-inventory-level fee Amazon
                                            charges on every unit shipped while
                                            cover is thin
    C_o  cost of one unit left over     = storage for the cycle (peak-season
                                          aware) + capital tied up + a small
                                          obsolescence charge

A high-margin SKU earns a 99% service level; a thin one earns 85%. The
order-up-to level is the q*-quantile of demand over lead time plus the
weekly review period, simulated with the same rate-uncertain Poisson
generator the stockout model uses, so the two can never disagree.

Fee cliffs.  Three of Amazon's charges are step functions of inventory
position and are computed explicitly: the low-inventory-level fee (days of
supply < 28), the aged-inventory surcharge (units past 181 days, escalating
to $5.45+/cu ft after 270), and the Oct–Dec storage rate (roughly 3× the
off-peak rate). The Inventory Age export carries Amazon's own estimates of
the last two; when it is on file those numbers win and the schedule is
only a fallback, labeled as such.

Liquidate vs hold.  For excess units, hold value is the discounted sum of
margin earned as they sell at the median rate, less storage and surcharge
along the way; liquidation is what Amazon's program returns today. The
larger number is the recommendation, both are shown.
"""

from datetime import date

import numpy as np

from . import fee_schedule as fees
from .common import num

REVIEW_PERIOD_DAYS = 7          # the weekly sweep
ANNUAL_CAPITAL_RATE = 0.12
OBSOLESCENCE_RATE = 0.02        # of unit cost, per cycle
LEAD_TIME_CV = 0.2              # mirrors inventory_sim
FRACTILE_FLOOR, FRACTILE_CEIL = 0.50, 0.995
HOLD_HORIZON_DAYS = 90          # cover beyond this counts as excess
MAX_HOLD_MONTHS = 24
LIQUIDATION_RECOVERY_OF_PRICE = 0.10   # Amazon liquidation returns ~5–10% of ASP
BUCKET_MID_AGE = {"inv_age_181_to_270": 225, "inv_age_271_to_365": 318, "inv_age_365_plus": 400}


def _latest_by_sku(rows: list[dict], key: str) -> dict[str, dict]:
    if not rows:
        return {}
    latest = max(r[key] for r in rows)
    return {r["sku"]: r for r in rows if r[key] == latest}


def critical_fractile(unit_margin: float, unit_cost: float, item_volume: float,
                      cycle_days: float, month: int, size_tier: str = "standard") -> dict:
    """q* and its two ingredients, itemised so the Desk can show the arithmetic."""
    storage = fees.storage_rate(month, size_tier) * item_volume * cycle_days / 30
    capital = unit_cost * ANNUAL_CAPITAL_RATE * cycle_days / 365
    obsolescence = unit_cost * OBSOLESCENCE_RATE
    c_o = storage + capital + obsolescence
    lilf = fees.LOW_INVENTORY_FEE_PER_UNIT.get(size_tier, fees.LOW_INVENTORY_FEE_PER_UNIT["standard"])["lt14"]
    c_u = max(0.0, unit_margin) + lilf
    q = c_u / (c_u + c_o) if (c_u + c_o) > 0 else FRACTILE_FLOOR
    return {
        "c_u": c_u, "c_o": c_o, "q": min(FRACTILE_CEIL, max(FRACTILE_FLOOR, q)),
        "c_u_parts": {"margin": max(0.0, unit_margin), "low_inventory_fee": lilf},
        "c_o_parts": {"storage": storage, "capital": capital, "obsolescence": obsolescence},
    }


def demand_over_cycle(mean_rate: float, std_rate: float, lead_days: float,
                      rng: np.random.Generator, simulations: int) -> np.ndarray:
    lead = rng.lognormal(mean=np.log(max(1.0, lead_days)), sigma=LEAD_TIME_CV, size=simulations)
    rates = np.clip(rng.normal(mean_rate, std_rate, size=simulations), 0, None)
    return rng.poisson(rates * (lead + REVIEW_PERIOD_DAYS))


def hold_vs_liquidate(excess_units: int, mean_rate: float, unit_margin: float, unit_cost: float,
                      price: float, item_volume: float, start_age_days: float, today: date,
                      size_tier: str = "standard") -> dict:
    """NPV of selling the excess down at the median rate vs liquidating now."""
    remaining = float(excess_units)
    monthly_units = max(1e-9, mean_rate * 30)
    npv, months = 0.0, 0
    discount = 1 + ANNUAL_CAPITAL_RATE / 12
    month = today.month
    age = start_age_days
    while remaining > 0 and months < MAX_HOLD_MONTHS:
        months += 1
        month = month % 12 + 1
        age += 30
        sold = min(remaining, monthly_units)
        carry = remaining * item_volume * (fees.storage_rate(month, size_tier) + fees.aged_surcharge_rate(int(age)))
        if age > 365:
            carry = max(carry, remaining * fees.AGED_SURCHARGE_MIN_PER_UNIT_365_PLUS)
        npv += (sold * unit_margin - carry) / discount ** months
        remaining -= sold
    liquidate = excess_units * price * LIQUIDATION_RECOVERY_OF_PRICE
    return {
        "hold_npv": npv, "liquidate_value": liquidate, "months_to_clear": months,
        "decision": "liquidate" if liquidate > npv else "hold",
        "per_unit_hold": npv / excess_units if excess_units else None,
    }


def run(data: dict, inventory_rows: list[dict], margin_rows: list[dict] | None = None,
        forecast_rows: list[dict] | None = None, rng: np.random.Generator | None = None,
        simulations: int = 20000, today: date | None = None) -> dict:
    today = today or date.today()
    rng = rng or np.random.default_rng(42)
    latest_margin = _latest_by_sku(margin_rows or [], "period_start")
    health = _latest_by_sku(data.get("inventory_health", []) or [], "snapshot_date")
    forecasts = {f["item_id"]: f for f in (forecast_rows or []) if f.get("status") == "ok"}
    next_month = today.month % 12 + 1

    rows = []
    for inv in inventory_rows:
        sku = inv["sku"]
        f = forecasts.get(sku)
        if f:
            mean_rate = float(f["daily_rate_point"] or 0)
            std_rate = float((f.get("details") or {}).get("error_sd") or 0) or mean_rate * 0.35
            rate_source = f"forecast ({f.get('method')})"
        else:
            mean_rate = float(inv.get("daily_velocity_mean") or 0)
            std_rate = float(inv.get("daily_velocity_std") or 0)
            rate_source = "observed periods"
        if mean_rate <= 0:
            continue
        lead = float(inv.get("lead_time_days") or 45)
        on_hand = int(inv.get("on_hand_units") or 0)
        inbound = int(inv.get("inbound_units") or 0)
        position = on_hand + inbound

        h = health.get(sku, {})
        vol = h.get("item_volume")
        if vol is None and h.get("storage_volume") and h.get("available"):
            vol = float(h["storage_volume"]) / float(h["available"])
        vol_assumed = vol is None
        vol = float(vol) if vol is not None else fees.DEFAULT_ITEM_VOLUME_CUFT["standard"]
        size_tier = "oversize" if (h.get("storage_type") or "").lower().startswith("over") else "standard"

        m = latest_margin.get(sku)
        econ = None
        if m and m.get("cogs") is not None and float(m.get("units") or 0) > 0 and float(m.get("revenue") or 0) > 0:
            units = float(m["units"])
            price = float(m["revenue"]) / units
            fee_rate = min(0.9, max(0.0, float(m.get("amazon_fees") or 0) / float(m["revenue"])))
            unit_cost = float(m["cogs"]) / units
            unit_margin = price * (1 - fee_rate) - unit_cost
            econ = {"price": price, "fee_rate": fee_rate, "unit_cost": unit_cost, "unit_margin": unit_margin}

        row = {
            "sku": sku, "status": "ok",
            "rate_mean": num(mean_rate, 4), "rate_sd": num(std_rate, 4), "rate_source": rate_source,
            "lead_time_days": int(lead), "review_days": REVIEW_PERIOD_DAYS,
            "on_hand": on_hand, "inbound": inbound, "position": position,
            "days_of_supply_on_hand": num(on_hand / mean_rate, 1),
            "days_of_cover_position": num(position / mean_rate, 1),
            "item_volume_cuft": num(vol, 4), "volume_assumed": vol_assumed, "size_tier": size_tier,
        }

        # — low-inventory-level fee exposure (Amazon: on-hand supply, not inbound) —
        dos = on_hand / mean_rate
        lilf_rate = fees.low_inventory_fee(dos, size_tier)
        row["low_inventory_fee_risk"] = lilf_rate > 0
        row["low_inventory_fee_month"] = num(lilf_rate * mean_rate * 30)
        if h.get("low_inventory_level_fee_applied") is not None:
            row["low_inventory_fee_applied_per_amazon"] = bool(h["low_inventory_level_fee_applied"])

        # — aged inventory surcharge —
        aged_units = sum(int(h.get(k) or 0) for k in BUCKET_MID_AGE)
        row["aged_units_181_plus"] = aged_units
        if h.get("estimated_aged_surcharge") is not None:
            row["aged_surcharge_month"] = num(float(h["estimated_aged_surcharge"]))
            row["aged_surcharge_basis"] = "Amazon's estimate (Inventory Age export)"
        else:
            surcharge = sum(int(h.get(k) or 0) * vol * fees.aged_surcharge_rate(age) for k, age in BUCKET_MID_AGE.items())
            row["aged_surcharge_month"] = num(surcharge)
            row["aged_surcharge_basis"] = f"schedule estimate ({fees.EFFECTIVE})" if aged_units else "no aged units on file"

        # — storage next month and the peak premium —
        if h.get("estimated_storage_cost_next_month") is not None:
            row["storage_next_month"] = num(float(h["estimated_storage_cost_next_month"]))
            row["storage_basis"] = "Amazon's estimate"
        else:
            row["storage_next_month"] = num(on_hand * vol * fees.storage_rate(next_month, size_tier))
            row["storage_basis"] = f"schedule estimate ({fees.EFFECTIVE})"
        to_peak = fees.months_until_peak(today)
        units_at_peak = max(0.0, position - mean_rate * 30 * to_peak) if to_peak <= 3 else 0.0
        row["peak_storage_premium_month"] = num(
            units_at_peak * vol * (fees.storage_rate(10, size_tier) - fees.storage_rate(9, size_tier)))

        if econ is None:
            row["status"] = "no_unit_economics"
            row["details"] = {"basis": "No landed cost on file — fee exposure computed, service level and liquidation skipped."}
            rows.append(row)
            continue

        # — the newsvendor —
        cf = critical_fractile(econ["unit_margin"], econ["unit_cost"], vol, lead + REVIEW_PERIOD_DAYS,
                               today.month, size_tier)
        demand = demand_over_cycle(mean_rate, std_rate, lead, rng, simulations)
        order_up_to = int(np.ceil(np.quantile(demand, cf["q"])))
        order_qty = max(0, order_up_to - position)
        implied_current = float(np.mean(demand <= position + int(inv.get("reorder_qty") or 0)))
        row.update({
            "unit_margin": num(econ["unit_margin"]), "unit_cost": num(econ["unit_cost"]), "price": num(econ["price"]),
            "c_u": num(cf["c_u"]), "c_o": num(cf["c_o"]), "critical_fractile": num(cf["q"], 4),
            "c_u_parts": {k: num(v) for k, v in cf["c_u_parts"].items()},
            "c_o_parts": {k: num(v) for k, v in cf["c_o_parts"].items()},
            "order_up_to": order_up_to,
            "order_qty_econ": order_qty,
            "wire_econ": num(order_qty * econ["unit_cost"]),
            "service_level_current_policy": num(implied_current, 4),
            "demand_cycle_p50": num(float(np.quantile(demand, 0.5)), 1),
            "demand_cycle_p95": num(float(np.quantile(demand, 0.95)), 1),
        })

        # — excess and the liquidate-vs-hold call —
        if h.get("estimated_excess_quantity") is not None:
            excess = int(h["estimated_excess_quantity"])
            excess_basis = "Amazon's excess estimate"
        else:
            excess = int(max(0.0, position - mean_rate * HOLD_HORIZON_DAYS))
            excess_basis = f"units beyond {HOLD_HORIZON_DAYS} days of cover at the median rate"
        row["excess_units"] = excess
        row["excess_basis"] = excess_basis
        if excess > 0:
            weighted_age = 90.0
            if aged_units:
                weighted_age = sum(int(h.get(k) or 0) * age for k, age in BUCKET_MID_AGE.items()) / aged_units
            hv = hold_vs_liquidate(excess, mean_rate, econ["unit_margin"], econ["unit_cost"], econ["price"],
                                   vol, weighted_age, today, size_tier)
            row.update({
                "hold_npv": num(hv["hold_npv"]), "liquidate_value": num(hv["liquidate_value"]),
                "months_to_clear": hv["months_to_clear"], "decision": hv["decision"],
            })
        row["details"] = {"basis": (
            f"q* = C_u/(C_u+C_o) = {cf['c_u']:.2f}/({cf['c_u']:.2f}+{cf['c_o']:.2f}) = {cf['q']:.1%}; "
            f"order-up-to is that quantile of {simulations:,} simulated cycles of demand over "
            f"{int(lead)}+{REVIEW_PERIOD_DAYS} days ({rate_source}). Volume "
            f"{'assumed' if vol_assumed else 'from the Inventory Age export'} at {vol:.3f} cu ft."
        )}
        rows.append(row)

    bleed = {
        "low_inventory_fee_month": sum(r.get("low_inventory_fee_month") or 0 for r in rows),
        "aged_surcharge_month": sum(r.get("aged_surcharge_month") or 0 for r in rows),
        "peak_storage_premium_month": sum(r.get("peak_storage_premium_month") or 0 for r in rows),
    }
    bleed["total_month"] = sum(bleed.values())
    liquidate = [r for r in rows if r.get("decision") == "liquidate"]
    return {
        "status": "ok" if rows else "insufficient_data",
        "as_of": today.isoformat(),
        "rows": rows,
        "summary": {
            "n_skus": len(rows),
            "bleed": {k: num(v) for k, v in bleed.items()},
            "n_low_inventory_fee_risk": sum(1 for r in rows if r.get("low_inventory_fee_risk")),
            "aged_units_181_plus": sum(r.get("aged_units_181_plus") or 0 for r in rows),
            "liquidation_candidates": [
                {"sku": r["sku"], "units": r["excess_units"], "liquidate_value": r["liquidate_value"],
                 "hold_npv": r["hold_npv"]} for r in liquidate],
            "liquidation_value": num(sum(r["liquidate_value"] or 0 for r in liquidate)),
            "econ_orders": [
                {"sku": r["sku"], "qty": r["order_qty_econ"], "wire": r["wire_econ"],
                 "service_level": r["critical_fractile"]}
                for r in rows if r.get("order_qty_econ")],
            "econ_wires_total": num(sum(r.get("wire_econ") or 0 for r in rows)),
            "fee_schedule_effective": fees.EFFECTIVE,
            "inventory_age_on_file": bool(health),
        },
        "assumptions": [
            f"Capital at {ANNUAL_CAPITAL_RATE:.0%}/yr, obsolescence {OBSOLESCENCE_RATE:.0%} of cost per cycle",
            f"Storage {fees.STORAGE_PER_CUFT['standard']['offpeak']}/{fees.STORAGE_PER_CUFT['standard']['peak']} $/cu ft "
            f"off-peak/peak (standard), schedule effective {fees.EFFECTIVE}; Amazon's own estimates override when the Inventory Age export is on file",
            f"Liquidation recovers {LIQUIDATION_RECOVERY_OF_PRICE:.0%} of selling price",
            f"Default unit volume {fees.DEFAULT_ITEM_VOLUME_CUFT['standard']} cu ft when no export states it",
        ],
    }
