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
position and are computed explicitly: the low-inventory-level fee (both the
30- and 90-day days of supply under 28, priced by size tier since 2026-10-01;
low_inventory_assessment), the aged-inventory surcharge (units past 181 days, escalating
to $5.45+/cu ft after 270), and the Oct–Dec storage rate (roughly 3× the
off-peak rate). The Inventory Age export carries Amazon's own estimates of
the last two; when it is on file those numbers win and the schedule is
only a fallback, labeled as such.

Liquidate vs hold.  For excess units, hold value is the discounted sum of
CASH CONTRIBUTION earned as they sell — price net of fees, landed cost
excluded — less storage and surcharge along the way; liquidation is what
Amazon's program returns today. The larger number is the recommendation, both
are shown. The three-way decision that adds a markdown lives in
models/markdown.py and shares this module's valuation.

Corrected 2026-09-23. Until then hold value subtracted landed cost per unit
while liquidation value was gross recovery; for units already on the shelf the
landed cost is sunk on both sides, and charging it on one biased thin-margin
SKUs toward liquidating stock that would have netted several times more sold.
The excess was also sold from month one, though it sits behind the target
cover; it now sells last. And `demand_over_cycle` drew a normal clipped at zero
until this date, the generator every other simulation retired on 2026-09-11 —
it is the moment-matched lognormal now, as the docstring always claimed.

Channels.  Every cliff above is Amazon's. A Shopify store ships from its own
shelf or a 3PL: there is no marketplace storage rate, no low-inventory fee
and no aged surcharge to price, and the 3PL's own rate is not on file, so
those three lines are zero and say so rather than being estimated off
Amazon's schedule (decided 2026-09-04). The newsvendor still runs on both —
lost margin against capital and obsolescence is not a marketplace fact.
"""

import re
from datetime import date

import numpy as np

from .. import channels
from ..ingest.headers import clean_bool, clean_money
from . import dependence
from . import fee_schedule as fees
from .common import num
from .pricing_engine import fee_terms

REVIEW_PERIOD_DAYS = 7          # the weekly sweep
ANNUAL_CAPITAL_RATE = 0.12
OBSOLESCENCE_RATE = 0.02        # of unit cost, per cycle
LEAD_TIME_CV = 0.2              # mirrors inventory_sim
# Each SKU's cycle demand is drawn from its own stream, keyed on the SKU: its
# order does not depend on the caller's seed or on the SKUs drawn before it
# (2026-09-24; the shared stream made one SKU's order move when another was
# added to the catalogue). Changing it moves every draw.
DEMAND_STREAM_SEED = 20260924
FRACTILE_FLOOR, FRACTILE_CEIL = 0.50, 0.995
HOLD_HORIZON_DAYS = 90          # cover beyond this counts as excess
MAX_HOLD_MONTHS = 24
LIQUIDATION_RECOVERY_OF_PRICE = 0.10   # Amazon liquidation returns ~5–10% of ASP
BUCKET_MID_AGE = {"inv_age_181_to_270": 225, "inv_age_271_to_365": 318, "inv_age_365_plus": 400}
NO_CLIFF_BASIS = "no storage or fee cliff on file (Shopify: self-fulfilled or 3PL rate not stated)"


def _latest_by_sku(rows: list[dict], key: str) -> dict[str, dict]:
    if not rows:
        return {}
    latest = max(r[key] for r in rows)
    return {r["sku"]: r for r in rows if r[key] == latest}


# The low-inventory-level fee's inputs an export may carry beyond the parsed
# columns (inventory_health keeps every source column in `raw`): Amazon's own
# 30- and 90-day historical days of supply, its exemption flag, and a size tier
# and weight. Matched on normalized headers, as the ingest matches.
SHORT_TERM_DOS = ("shorttermhistoricaldaysofsupply", "historicaldaysofsupply30days", "historicaldaysofsupplyt30")
LONG_TERM_DOS = ("longtermhistoricaldaysofsupply", "historicaldaysofsupply90days", "historicaldaysofsupplyt90")
LILF_EXEMPT = ("exemptedfromlowinventorylevelfee", "lowinventorylevelfeeexempt", "lowinventorylevelfeeexemption")
SIZE_TIER = ("productsizetier", "sizetier")
WEIGHT = ("itempackageweight", "itemweight", "packageweight")
WEIGHT_UNIT = ("unitofweight", "weightunit")
PRODUCT_GROUP = ("productgroup", "category")
# pounds per unit of weight: lib/call.js's ounces-per-unit table over 16, so the
# call and the engine split large standard at 3 lb on the same number
LB_PER = {k: v / 16 for k, v in {"pounds": 16, "pound": 16, "lb": 16, "lbs": 16, "ounces": 1, "ounce": 1, "oz": 1,
                                 "kilograms": 35.274, "kilogram": 35.274, "kg": 35.274, "grams": 0.035274,
                                 "gram": 0.035274, "g": 0.035274}.items()}
LILF_UNMODELLED = ("not applied, because no export shows them: the exemptions for a new Professional seller "
                   "(365 days), an FBA New Selection parent (180 days) and a SKU at least 70% auto-replenished "
                   "through AWD")


def _export_field(h: dict, names: tuple[str, ...]):
    """A column from the health row itself, else from its raw source row."""
    for n in names:
        if h.get(n) not in (None, ""):
            return h[n]
    raw = h.get("raw") or {}
    if isinstance(raw, dict):
        by_norm = {re.sub(r"[^a-z0-9]", "", str(k).lower()): v for k, v in raw.items()}
        for n in names:
            v = by_norm.get(n)
            if v not in (None, "") and str(v).strip().lower() not in ("n/a", "na", "-", "--"):
                return v
    return None


def _number(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return clean_money(str(v))


def low_inventory_assessment(h: dict, on_hand: float, mean_rate: float, storage_class: str) -> dict:
    """The low-inventory-level fee for one SKU, on the rule Amazon states.

    Days of supply: Amazon's own 30- and 90-day historical figures when the
    export carries them; else on-hand stock at the last 30 and 90 days'
    shipping pace (today's stock standing in for the period's average); else
    on-hand at the modelled rate for both. The higher of the two sets the band
    and both must be under 28. Size tier: the export's own when it names one,
    else assumed (fee_schedule.low_inventory_tier). Exemptions the export can
    show are applied; the rest are named."""
    dos_30, dos_90 = _number(_export_field(h, SHORT_TERM_DOS)), _number(_export_field(h, LONG_TERM_DOS))
    if dos_30 is not None or dos_90 is not None:
        source = "Amazon's own 30- and 90-day historical days of supply"
    else:
        t30, t90 = h.get("units_shipped_t30"), h.get("units_shipped_t90")
        if t30 is not None or t90 is not None:
            pace = lambda units, window: on_hand / (units / window) if units else float("inf")
            dos_30 = pace(t30, 30) if t30 is not None else None
            dos_90 = pace(t90, 90) if t90 is not None else None
            source = ("on hand at the last 30 and 90 days' shipping pace" if t30 is not None and t90 is not None
                      else f"on hand at the last {30 if t30 is not None else 90} days' shipping pace "
                           f"(the {90 if t30 is not None else 30}-day history is not on file)")
        else:
            dos_30 = dos_90 = on_hand / mean_rate
            source = "on hand at the modelled rate (no shipping history on file stands in for the 30 and 90 days)"
    band = fees.low_inventory_band_days(dos_30, dos_90)

    weight = _number(_export_field(h, WEIGHT))
    if weight is not None:
        unit = str(_export_field(h, WEIGHT_UNIT) or "pounds").strip().lower()
        weight = weight * LB_PER.get(unit, 1.0)
    tier, tier_basis = fees.low_inventory_tier(_export_field(h, SIZE_TIER) or h.get("storage_type") or storage_class,
                                               weight)

    exempt, notes = None, []
    flag = _export_field(h, LILF_EXEMPT)
    t7 = h.get("units_shipped_t7")
    group = str(_export_field(h, PRODUCT_GROUP) or "")
    if flag is not None and clean_bool(str(flag)) is True:
        exempt = "Amazon's export marks this SKU exempt"
    elif t7 is not None and int(t7) < fees.LOW_INVENTORY_MIN_UNITS_T7:
        exempt = f"exempt: {int(t7)} units shipped in the past 7 days, under {fees.LOW_INVENTORY_MIN_UNITS_T7}"
    elif "grocery" in group.lower():
        exempt = "exempt: Grocery"
    if t7 is None and exempt is None:
        notes.append(f"the under-{fees.LOW_INVENTORY_MIN_UNITS_T7}-units-in-7-days exemption is unchecked "
                     f"(no units-shipped-t7 on file)")
    notes.append(LILF_UNMODELLED)
    rate = 0.0 if exempt else fees.low_inventory_fee(band, tier)
    basis = (f"{tier_basis}; days of supply: {source}; "
             + (f"{exempt}; " if exempt else "")
             + "; ".join(notes))
    return {"rate": rate, "tier": tier, "tier_basis": tier_basis, "lt14": fees.low_inventory_fee(0.0, tier),
            "dos_30": dos_30, "dos_90": dos_90, "band": band, "source": source, "exempt": exempt, "basis": basis}


def critical_fractile(unit_margin: float, unit_cost: float, item_volume: float,
                      cycle_days: float, month: int, size_tier: str = "standard",
                      fee_cliffs: bool = True, obsolescence_per_unit: float | None = None,
                      obsolescence_basis: str | None = None, low_inventory_per_unit: float | None = None) -> dict:
    """q* and its two ingredients, itemised so the Desk can show the arithmetic.

    fee_cliffs=False drops the two Amazon-only terms — marketplace storage
    out of C_o, the low-inventory fee out of C_u — leaving lost margin
    against capital and obsolescence, which is the newsvendor a Shopify
    store actually faces.

    `obsolescence_per_unit` replaces the flat OBSOLESCENCE_RATE with the
    expected write-off on a unit that outlives its SKU (see obsolescence_charge,
    2026-09-23); None keeps the flat rate and says so in `c_o_parts`.

    `low_inventory_per_unit` is the SKU's own size tier's under-14-days rate
    (low_inventory_assessment); None prices `size_tier`'s assumed row."""
    storage = fees.storage_rate(month, size_tier) * item_volume * cycle_days / 30 if fee_cliffs else 0.0
    capital = unit_cost * ANNUAL_CAPITAL_RATE * cycle_days / 365
    if obsolescence_per_unit is not None:
        obsolescence = max(0.0, float(obsolescence_per_unit))
        basis = obsolescence_basis or "survival curve"
    else:
        obsolescence = unit_cost * OBSOLESCENCE_RATE
        basis = f"flat rate ({OBSOLESCENCE_RATE:.0%} of cost per cycle): survival curve unavailable"
    c_o = storage + capital + obsolescence
    # a unit short is sold when cover is thinnest: the under-14-days rate
    lilf = ((low_inventory_per_unit if low_inventory_per_unit is not None else fees.low_inventory_fee(0.0, size_tier))
            if fee_cliffs else 0.0)
    c_u = max(0.0, unit_margin) + lilf
    q = c_u / (c_u + c_o) if (c_u + c_o) > 0 else FRACTILE_FLOOR
    return {
        "c_u": c_u, "c_o": c_o, "q": min(FRACTILE_CEIL, max(FRACTILE_FLOOR, q)),
        "c_u_parts": {"margin": max(0.0, unit_margin), "low_inventory_fee": lilf},
        "c_o_parts": {"storage": storage, "capital": capital, "obsolescence": obsolescence},
        "obsolescence_basis": basis,
    }


def obsolescence_charge(risk_out: dict | None, sku_age_periods: float, cycle_days: float,
                        unit_cost: float, price: float) -> dict | None:
    """The expected write-off on a unit ordered now, from the catalogue's own
    survival curve: P(the SKU dies before this order sells through) × (landed
    cost − liquidation recovery). P is 1 − S(age + cycle | age) on the
    Kaplan–Meier curve in periods, with a Greenwood-style error read off the
    curve's event count. None when the risk pass has no curve."""
    surv = (risk_out or {}).get("survival") or {}
    if surv.get("status") != "ok" or not surv.get("t"):
        return None
    t = np.array(surv["t"], dtype=float)
    s_ = np.array(surv["s"], dtype=float)
    per_days = float(surv.get("period_days_typical") or 30)

    def S(x: float) -> float:
        idx = int(np.searchsorted(t, x, side="right")) - 1
        return float(s_[max(0, min(idx, len(s_) - 1))])
    age = float(sku_age_periods)
    ahead = age + cycle_days / per_days
    s_age, s_ahead = S(age), S(ahead)
    p_death = 1.0 - (s_ahead / s_age if s_age > 0 else 0.0)
    p_death = min(1.0, max(0.0, p_death))
    events = max(1, int(surv.get("events") or 1))
    n = max(1, int(surv.get("n") or 1))
    # a crude standard error on a survival difference: binomial on the
    # at-risk count, which is what Greenwood's formula reduces to per step
    se = float(np.sqrt(p_death * (1 - p_death) / n))
    loss = max(0.0, float(unit_cost) - float(price) * LIQUIDATION_RECOVERY_OF_PRICE)
    return {"per_unit": p_death * loss, "per_unit_se": se * loss, "p_death_before_sellthrough": num(p_death, 4),
            "p_death_se": num(se, 4), "s_age": num(s_age, 4), "s_ahead": num(s_ahead, 4), "events": events,
            "basis": f"Kaplan–Meier on the catalogue's SKU lifetimes, conditioned on {age:.0f} period(s) of age"}


def sku_stream(sku: str) -> np.random.Generator:
    """The SKU's own generator: the same draws whatever else is in the run."""
    import zlib
    return np.random.default_rng([DEMAND_STREAM_SEED, zlib.crc32(str(sku).encode("utf-8"))])


def demand_over_cycle(mean_rate: float, std_rate: float, lead_days: float,
                      rng: np.random.Generator, simulations: int) -> np.ndarray:
    lead = rng.lognormal(mean=np.log(max(1.0, lead_days)), sigma=LEAD_TIME_CV, size=simulations)
    # moment-matched lognormal, the same marginal the stockout model and the
    # cash cone draw — a clipped normal has a mean above the one it was given
    # and no skew (corrected 2026-09-23)
    rates = dependence.correlated_rates(rng, [max(mean_rate, 1e-9)], [max(std_rate, 0.0)], (simulations,), 0.0)[0]
    return rng.poisson(rates * (lead + REVIEW_PERIOD_DAYS))


def hold_vs_liquidate(excess_units: int, mean_rate: float, contribution: float, price: float,
                      item_volume: float, start_age_days: float, today: date,
                      size_tier: str = "standard", fee_cliffs: bool = True) -> dict:
    """Median-rate value of selling the position down vs liquidating the excess
    now, on cash proceeds net of fees and carry with landed cost sunk.

    `contribution` is price(1 − f) − F per unit. The whole position sells
    first-in-first-out so the excess sells last; the position is the excess
    plus the target cover. Without fee cliffs the carry is zero: no
    marketplace storage rate and no aged surcharge apply, and a 3PL's own
    rate is not on file. The interval version, with the markdown option, is
    models/markdown.py."""
    from .markdown import position_value

    rate = np.array([max(float(mean_rate), 1e-9)])
    # the position is the excess plus the target cover, so the model's excess
    # is exactly the caller's (Amazon's estimate or the cover rule)
    pos = float(excess_units) + float(rate[0]) * HOLD_HORIZON_DAYS
    # contribution = price(1 − f) − F: expressed as one proportional rate so
    # liquidation still recovers a share of the PRICE
    f = np.array([1.0 - float(contribution) / float(price)]) if price and price > 0 else np.array([0.0])
    big_f = np.array([0.0])
    hold_all, hold_m = position_value(pos, rate, None, f, big_f, float(price), None, False, item_volume,
                                      start_age_days, today, size_tier, fee_cliffs)
    liq_all, _ = position_value(pos, rate, None, f, big_f, float(price), None, True, item_volume,
                                start_age_days, today, size_tier, fee_cliffs)
    liquidate = float(excess_units) * float(price) * LIQUIDATION_RECOVERY_OF_PRICE
    # the excess's own hold value: what holding the whole position earns over
    # liquidating the excess and holding only the cover, plus the recovery
    hold_npv = float(hold_all[0]) - (float(liq_all[0]) - liquidate)
    return {
        "hold_npv": hold_npv, "liquidate_value": liquidate, "months_to_clear": int(hold_m[0]),
        "decision": "liquidate" if liquidate > hold_npv else "hold",
        "per_unit_hold": hold_npv / excess_units if excess_units else None,
        "basis": "cash proceeds net of fees and carry; landed cost sunk; excess sells after the target cover",
    }


def run(data: dict, inventory_rows: list[dict], margin_rows: list[dict] | None = None,
        forecast_rows: list[dict] | None = None, rng: np.random.Generator | None = None,
        simulations: int = 20000, today: date | None = None,
        channel: str = "amazon", seasonal: dict | None = None, risk_out: dict | None = None,
        price_plan: dict | None = None) -> dict:
    """`price_plan` is directives.plan_prices()'s output: a SKU whose own
    price or a sibling's moves this sweep has its order sized on demand at
    the planned prices (the multiplier's own uncertainty added to the rate's
    sd), and says so under `price_plan`. Everything valued at today's price
    (fee exposure, cover, the hold-or-liquidate call) keeps today's rate.

    `rng` is accepted for interface parity; each SKU's draws come from its
    own stream (sku_stream)."""
    from .seasonality import horizon_factor, seasonal_rate
    plan_mult = (price_plan or {}).get("multipliers") or {}

    today = today or date.today()
    rng = rng or np.random.default_rng(42)
    cliffs = channels.has_fee_cliffs(channel)
    platform = channels.label(channel)
    latest_margin = _latest_by_sku(margin_rows or [], "period_start")
    health = _latest_by_sku(data.get("inventory_health", []) or [], "snapshot_date")
    forecasts = {f["item_id"]: f for f in (forecast_rows or []) if f.get("status") == "ok"}
    next_month = today.month % 12 + 1

    rows = []
    for inv in inventory_rows:
        sku = inv["sku"]
        f = forecasts.get(sku)
        if f:
            from .forecast import rate_moments
            mean_rate, std_rate = rate_moments(f)
            mean_rate = float(mean_rate or 0)
            std_rate = float(std_rate or 0) or mean_rate * 0.35
            rate_source = f"forecast ({f.get('method')}), at a seasonal index of one"
        else:
            det_inv = inv.get("details") or {}
            mean_rate = float(det_inv.get("daily_velocity_base") or inv.get("daily_velocity_mean") or 0)
            std_rate = float(det_inv.get("daily_velocity_base_std") or inv.get("daily_velocity_std") or 0)
            rate_source = "observed periods, at a seasonal index of one"
        if mean_rate <= 0:
            continue
        lead = float(inv.get("lead_time_days") or 45)
        base_rate = mean_rate
        mean_rate, std_rate, season_note = seasonal_rate(mean_rate, std_rate, seasonal, sku, today,
                                                         lead + REVIEW_PERIOD_DAYS)
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
            # the proportional / fixed split from the margin row, so the
            # contribution per unit is the one the price step is priced on
            fee_rate, fixed_fee, fee_basis = fee_terms(m)
            unit_cost = float(m["cogs"]) / units
            contribution = price * (1 - fee_rate) - fixed_fee
            unit_margin = contribution - unit_cost
            econ = {"price": price, "fee_rate": fee_rate, "fixed_fee": fixed_fee, "fee_basis": fee_basis,
                    "unit_cost": unit_cost, "unit_margin": unit_margin, "contribution": contribution}
        observed_prices = [float(e["avg_sales_price"] or ((e.get("sales") or 0) / e["units_sold"]))
                           for e in data.get("sku_economics", []) or []
                           if e.get("sku") == sku and e.get("units_sold") and (e.get("avg_sales_price") or e.get("sales"))]

        row = {
            "sku": sku, "status": "ok",
            "rate_mean": num(mean_rate, 4), "rate_sd": num(std_rate, 4), "rate_source": rate_source,
            "lead_time_days": int(lead), "review_days": REVIEW_PERIOD_DAYS,
            "on_hand": on_hand, "inbound": inbound, "position": position,
            "reorder_point": int(inv.get("reorder_point") or 0),
            "stockout_probability": inv.get("stockout_probability"),
            "days_of_supply_on_hand": num(on_hand / mean_rate, 1),
            "days_of_cover_position": num(position / mean_rate, 1),
            "item_volume_cuft": num(vol, 4), "volume_assumed": vol_assumed, "size_tier": size_tier,
            **season_note,
        }

        aged_units = sum(int(h.get(k) or 0) for k in BUCKET_MID_AGE)
        lilf = low_inventory_assessment(h, on_hand, mean_rate, size_tier) if cliffs else None
        if cliffs:
            # — low-inventory-level fee exposure (Amazon: on-hand supply, not
            # inbound; both the 30- and 90-day supply under 28, by size tier) —
            row["low_inventory_fee_risk"] = lilf["rate"] > 0
            row["low_inventory_fee_month"] = num(lilf["rate"] * mean_rate * 30)
            row["low_inventory_fee_rate"] = lilf["rate"]
            row["low_inventory_fee_lt14"] = lilf["lt14"]
            row["fee_size_tier"] = lilf["tier"]
            row["fee_size_tier_basis"] = lilf["tier_basis"]
            row["low_inventory_days_of_supply"] = {"t30": num(lilf["dos_30"], 1), "t90": num(lilf["dos_90"], 1),
                                                   "band": num(lilf["band"], 1), "source": lilf["source"]}
            row["low_inventory_fee_exempt"] = lilf["exempt"]
            row["low_inventory_fee_basis"] = lilf["basis"]
            if h.get("low_inventory_level_fee_applied") is not None:
                row["low_inventory_fee_applied_per_amazon"] = bool(h["low_inventory_level_fee_applied"])

            # — aged inventory surcharge —
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
            # the units left when the peak rate starts: sold down at the
            # seasonal rate over the months until then
            factor_to_peak, _ = horizon_factor(seasonal, sku, today, 30 * to_peak) if to_peak else (1.0, 0.0)
            units_at_peak = max(0.0, position - base_rate * factor_to_peak * 30 * to_peak) if to_peak <= 3 else 0.0
            row["peak_storage_premium_month"] = num(
                units_at_peak * vol * (fees.storage_rate(10, size_tier) - fees.storage_rate(9, size_tier)))
        else:
            # No marketplace warehouse: nothing here is a cliff this client can
            # step off, and inventing a 3PL rate would be worse than a zero.
            row["low_inventory_fee_risk"] = False
            row["low_inventory_fee_month"] = 0.0
            row["aged_units_181_plus"] = 0
            row["aged_surcharge_month"] = 0.0
            row["aged_surcharge_basis"] = NO_CLIFF_BASIS
            row["storage_next_month"] = 0.0
            row["storage_basis"] = NO_CLIFF_BASIS
            row["peak_storage_premium_month"] = 0.0

        if econ is None:
            row["status"] = "no_unit_economics"
            row["details"] = {"basis": (
                f"{platform}: no landed cost on file — "
                + ("fee exposure computed, " if cliffs else "")
                + "service level and liquidation skipped.")}
            rows.append(row)
            continue

        # — the newsvendor —
        # obsolescence from the catalogue's own survival curve, not a flat 2%
        age_periods = sum(1 for mm in (margin_rows or []) if mm.get("sku") == sku and float(mm.get("units") or 0) > 0)
        obs = obsolescence_charge(risk_out, age_periods, lead + REVIEW_PERIOD_DAYS, econ["unit_cost"], econ["price"])
        lilf_unit = lilf["lt14"] if lilf else None     # this SKU's tier, at its under-14-days rate
        cf = critical_fractile(econ["unit_margin"], econ["unit_cost"], vol, lead + REVIEW_PERIOD_DAYS,
                               today.month, size_tier, fee_cliffs=cliffs, low_inventory_per_unit=lilf_unit,
                               obsolescence_per_unit=obs["per_unit"] if obs else None,
                               obsolescence_basis=obs["basis"] if obs else None)
        if obs:
            # the interval on q* from the survival curve's own uncertainty
            hi = critical_fractile(econ["unit_margin"], econ["unit_cost"], vol, lead + REVIEW_PERIOD_DAYS,
                                   today.month, size_tier, fee_cliffs=cliffs, low_inventory_per_unit=lilf_unit,
                                   obsolescence_per_unit=obs["per_unit"] + 1.645 * obs["per_unit_se"])
            lo = critical_fractile(econ["unit_margin"], econ["unit_cost"], vol, lead + REVIEW_PERIOD_DAYS,
                                   today.month, size_tier, fee_cliffs=cliffs, low_inventory_per_unit=lilf_unit,
                                   obsolescence_per_unit=max(0.0, obs["per_unit"] - 1.645 * obs["per_unit_se"]))
            cf["q_band"] = [num(hi["q"], 4), num(lo["q"], 4)]
        order_rate, order_sd = mean_rate, std_rate
        pm = plan_mult.get(sku)
        if pm and pm.get("multiplier"):
            m, m_sd = float(pm["multiplier"]), float(pm.get("sd") or 0.0)
            order_rate = mean_rate * m
            order_sd = float(np.sqrt((std_rate * m) ** 2 + (mean_rate * m_sd) ** 2))
            row["price_plan"] = {"demand_multiplier": num(m, 4), "demand_multiplier_sd": num(m_sd, 4),
                                 "own": pm.get("own"), "cross": pm.get("cross"),
                                 "p0": pm.get("p0"), "p_new": pm.get("p_new"),
                                 "order_rate_mean": num(order_rate, 4), "order_rate_sd": num(order_sd, 4),
                                 "basis": "order sized on demand at this sweep's planned prices"}
        demand = demand_over_cycle(order_rate, order_sd, lead, sku_stream(sku), simulations)
        order_up_to = int(np.ceil(np.quantile(demand, cf["q"])))
        order_qty = max(0, order_up_to - position)
        implied_current = float(np.mean(demand <= position + int(inv.get("reorder_qty") or 0)))
        row.update({
            "unit_margin": num(econ["unit_margin"]), "unit_cost": num(econ["unit_cost"]), "price": num(econ["price"]),
            "fee_rate": num(econ["fee_rate"], 6), "fixed_fee": num(econ["fixed_fee"], 6), "fee_basis": econ["fee_basis"],
            "contribution": num(econ["contribution"]),
            "min_observed_price": num(min(observed_prices)) if observed_prices else None,
            "c_u": num(cf["c_u"]), "c_o": num(cf["c_o"]), "critical_fractile": num(cf["q"], 4),
            "c_u_parts": {k: num(v) for k, v in cf["c_u_parts"].items()},
            "c_o_parts": {k: num(v) for k, v in cf["c_o_parts"].items()},
            "obsolescence_basis": cf["obsolescence_basis"],
            "p_death_before_sellthrough": obs["p_death_before_sellthrough"] if obs else None,
            "critical_fractile_band": cf.get("q_band"),
            "order_up_to": order_up_to,
            "order_qty_econ": order_qty,
            "wire_econ": num(order_qty * econ["unit_cost"]),
            "service_level_current_policy": num(implied_current, 4),
            "demand_cycle_p50": num(float(np.quantile(demand, 0.5)), 1),
            "demand_cycle_p95": num(float(np.quantile(demand, 0.95)), 1),
        })
        # the demand distribution over the cycle at a ladder of service levels,
        # so a budget-constrained or joint order can be sized later without
        # re-simulating: F⁻¹(q) for q on the grid
        ladder_q = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.975, 0.99, 0.995]
        row["details"] = {"demand_ladder": [[q, num(float(np.quantile(demand, q)), 1)] for q in ladder_q]}

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
            hv = hold_vs_liquidate(excess, mean_rate, econ["contribution"], econ["price"],
                                   vol, weighted_age, today, size_tier, fee_cliffs=cliffs)
            row.update({
                "hold_npv": num(hv["hold_npv"]), "liquidate_value": num(hv["liquidate_value"]),
                "months_to_clear": hv["months_to_clear"], "decision": hv["decision"],
            })
            row["weighted_age"] = num(weighted_age, 1)
        row["details"] = {**row.get("details", {}), "basis": (
            f"{platform}: q* = C_u/(C_u+C_o) = {cf['c_u']:.2f}/({cf['c_u']:.2f}+{cf['c_o']:.2f}) = {cf['q']:.1%}; "
            f"order-up-to is that quantile of {simulations:,} simulated cycles of demand over "
            f"{int(lead)}+{REVIEW_PERIOD_DAYS} days ({rate_source}). "
            + (f"Volume {'assumed' if vol_assumed else 'from the Inventory Age export'} at {vol:.3f} cu ft."
               if cliffs else
               f"C_o is capital and obsolescence only — {NO_CLIFF_BASIS}.")
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
            "channel": channel,
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
            "fee_schedule_effective": fees.EFFECTIVE if cliffs else None,
            "inventory_age_on_file": bool(health),
        },
        "assumptions": [
            f"{platform} channel: "
            + (f"Storage {fees.STORAGE_PER_CUFT['standard']['offpeak']}/{fees.STORAGE_PER_CUFT['standard']['peak']} $/cu ft "
               f"off-peak/peak (standard), schedule effective {fees.EFFECTIVE}; Amazon's own estimates override when the Inventory Age export is on file"
               if cliffs else
               f"no low-inventory fee, aged surcharge or peak storage to price — {NO_CLIFF_BASIS}"),
            f"Capital at {ANNUAL_CAPITAL_RATE:.0%}/yr; obsolescence from the catalogue's survival curve when the "
            f"risk pass has one, else a flat {OBSOLESCENCE_RATE:.0%} of cost per cycle (labelled)",
            f"Liquidation recovers {LIQUIDATION_RECOVERY_OF_PRICE:.0%} of selling price; units on hand are valued "
            f"on cash contribution with landed cost sunk (corrected 2026-09-23)",
            f"Default unit volume {fees.DEFAULT_ITEM_VOLUME_CUFT['standard']} cu ft when no export states it",
            *([f"Low-inventory-level fee by size tier (schedule {fees.EFFECTIVE}, re-read 2026-10-01): charged only "
               f"when both the 30- and 90-day days of supply are under {fees.LOW_INVENTORY_DAYS_THRESHOLD}, the higher "
               f"setting the band; a SKU whose export names no size tier is priced at the small-standard row (the "
               f"lowest) and says so; bulky rates are the least certain; the storage utilization surcharge is not "
               f"modelled"] if cliffs else []),
        ],
    }
