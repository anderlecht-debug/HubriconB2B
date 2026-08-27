"""Cash-flow horizon: Monte Carlo value-at-risk on the client's cash position.

The flashy version of this model reaches for Geometric Brownian Motion.
We deliberately don't: GBM describes compounding asset prices, not unit
demand. Daily demand here uses the same generator the inventory simulation
is validated on (rate-uncertain Poisson), so the cash cone and the stockout
numbers can never disagree about what demand is.

Cash mechanics per simulated path over the horizon:

    in  — Amazon disburses every PAYOUT_CYCLE_DAYS: the accumulated
          (revenue − fees − ad spend) since the previous payout. The
          client's actual settlement phase is unknown, so payouts land on
          days 14, 28, … — an assumption surfaced in the payload.
    out — fixed operating costs accrue daily (monthly_fixed_costs / 30);
          supplier POs leave as lump-sum wires on their scheduled dates.

The wire schedule is derived from the same inventory results the reorder
directives use: the first wire when the position walks down to the reorder
point, then a steady-state cycle every reorder_qty / velocity days. COGS
never hits cash per-sale — inventory already on hand was paid for; future
inventory is paid for by exactly these wires.

Ruin here means the simulated account balance crossing zero — an honest
"you would need bridge capital" line, never a bankruptcy prophecy.
"""

import numpy as np

from .common import num, period_days

PAYOUT_CYCLE_DAYS = 14
DEFAULT_HORIZON_DAYS = 90
DEFAULT_PATHS = 10000
OPEX_DAYS_PER_MONTH = 30  # daily accrual approximation, surfaced in payload
RUIN_WARNING = 0.05
RUIN_CRITICAL = 0.15


def _latest_margins_by_sku(margin_rows: list[dict]) -> dict[str, dict]:
    if not margin_rows:
        return {}
    latest = max(m["period_start"] for m in margin_rows)
    return {m["sku"]: m for m in margin_rows if m["period_start"] == latest}


def sku_cash_params(inventory_rows: list[dict], margin_rows: list[dict]) -> list[dict]:
    """Per-SKU daily cash machinery: velocity moments from the inventory sim,
    unit price / fee rate / daily ad spend from the latest margin period."""
    latest = _latest_margins_by_sku(margin_rows)
    params = []
    for r in inventory_rows:
        m = latest.get(r["sku"])
        if not m:
            continue
        units = float(m.get("units") or 0)
        revenue = float(m.get("revenue") or 0)
        if units <= 0 or revenue <= 0:
            continue
        days = period_days(m["period_start"], m["period_end"])
        params.append({
            "sku": r["sku"],
            "mean_rate": float(r["daily_velocity_mean"] or 0),
            "std_rate": float(r["daily_velocity_std"] or 0),
            "price": revenue / units,
            "fee_rate": min(0.9, max(0.0, float(m.get("amazon_fees") or 0) / revenue)),
            "ad_daily": float(m.get("ad_spend_allocated") or 0) / days,
        })
    return [p for p in params if p["mean_rate"] > 0]


def wire_schedule(inventory_rows: list[dict], margin_rows: list[dict],
                  horizon_days: int = DEFAULT_HORIZON_DAYS) -> list[dict]:
    """Deterministic supplier-PO outflows: same reorder points, quantities
    and unit costs the inventory directives are built from."""
    latest = _latest_margins_by_sku(margin_rows)
    wires = []
    for r in inventory_rows:
        m = latest.get(r["sku"])
        rate = float(r["daily_velocity_mean"] or 0)
        qty = int(r.get("reorder_qty") or 0)
        if not m or rate <= 0 or qty <= 0:
            continue
        units = float(m.get("units") or 0)
        if m.get("cogs") is None or units <= 0:
            continue  # no landed cost on file — no honest wire amount
        unit_cost = float(m["cogs"]) / units
        position = int(r.get("on_hand_units") or 0) + int(r.get("inbound_units") or 0)
        first = max(0, int((position - int(r.get("reorder_point") or 0)) / rate))
        cycle = max(1, int(qty / rate))
        day = first
        while day < horizon_days:
            wires.append({"day": day, "sku": r["sku"], "amount": round(qty * unit_cost, 2)})
            day += cycle
    return sorted(wires, key=lambda w: w["day"])


def simulate(params: list[dict], wires: list[dict], starting_cash: float,
             monthly_fixed_costs: float, rng: np.random.Generator,
             horizon_days: int = DEFAULT_HORIZON_DAYS,
             n_paths: int = DEFAULT_PATHS) -> dict:
    """The cone. Returns a JSON-safe payload with daily p5/p50/p95 cash
    paths (day 0 = today = starting cash), ruin probability, and the
    schedule that produced it."""
    days = horizon_days
    sales_net = np.zeros((n_paths, days))
    ad_daily_total = 0.0
    for p in params:
        rates = np.clip(rng.normal(p["mean_rate"], p["std_rate"], size=(n_paths, days)), 0, None)
        units = rng.poisson(rates)
        sales_net += units * p["price"] * (1 - p["fee_rate"])
        ad_daily_total += p["ad_daily"]

    outflow = np.full(days, monthly_fixed_costs / OPEX_DAYS_PER_MONTH)
    for w in wires:
        if 0 <= w["day"] < days:
            outflow[w["day"]] += w["amount"]

    # payout accumulator: (revenue − fees − ads) held until the next payout
    # day. Paid-through-t is the cumulative net at the latest payout day ≤ t
    # — a negative settlement carries forward, exactly like Amazon's.
    net_daily = sales_net - ad_daily_total
    cum_net = np.cumsum(net_daily, axis=1)
    paid = np.zeros((n_paths, days))
    payout_days = list(range(PAYOUT_CYCLE_DAYS - 1, days, PAYOUT_CYCLE_DAYS))
    for k in payout_days:
        paid[:, k:] = cum_net[:, k][:, None]
    cash = starting_cash - np.cumsum(outflow)[None, :] + paid

    p5, p50, p95 = (np.quantile(cash, q, axis=0) for q in (0.05, 0.50, 0.95))
    ruined = (cash.min(axis=1) < 0).mean()
    min_p5_day = int(np.argmin(p5))
    return {
        "horizon_days": days,
        "n_paths": n_paths,
        "starting_cash": num(starting_cash),
        "monthly_fixed_costs": num(monthly_fixed_costs),
        "p_ruin": num(float(ruined), 4),
        "min_p5": num(float(p5[min_p5_day])),
        "min_p5_day": min_p5_day + 1,
        "min_median": num(float(p50.min())),
        "details": {
            "p5": [num(float(v)) for v in p5],
            "p50": [num(float(v)) for v in p50],
            "p95": [num(float(v)) for v in p95],
            "wires": wires,
            "payout_days": [d + 1 for d in payout_days],
            "payout_cycle_days": PAYOUT_CYCLE_DAYS,
            "skus_modeled": len(params),
            "assumptions": [
                f"Amazon settlement phase unknown — payouts assumed on days {PAYOUT_CYCLE_DAYS}, {2 * PAYOUT_CYCLE_DAYS}, …",
                f"Fixed costs accrue daily (monthly / {OPEX_DAYS_PER_MONTH}); real due dates may be lumpier",
                "Cash on hand and monthly fixed costs are client-stated, not modeled",
                "Demand generator identical to the inventory simulation (rate-uncertain Poisson)",
            ],
        },
    }


def run(client: dict, inventory_rows: list[dict], margin_rows: list[dict],
        rng: np.random.Generator, horizon_days: int = DEFAULT_HORIZON_DAYS,
        n_paths: int = DEFAULT_PATHS) -> dict | None:
    """None when the client hasn't stated cash inputs or there's no revenue
    machinery to simulate — the caller reports the skip, never fakes it."""
    cash_on_hand = client.get("cash_on_hand")
    opex = client.get("monthly_fixed_costs")
    if cash_on_hand is None or opex is None:
        return None
    params = sku_cash_params(inventory_rows, margin_rows)
    if not params:
        return None
    wires = wire_schedule(inventory_rows, margin_rows, horizon_days)
    return simulate(params, wires, float(cash_on_hand), float(opex), rng,
                    horizon_days=horizon_days, n_paths=n_paths)
