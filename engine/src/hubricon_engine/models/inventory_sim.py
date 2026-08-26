"""Monte Carlo inventory simulation, per SKU.

Demand during a replenishment lead time is simulated as
    lead_time ~ lognormal(median = supplier lead time, sigma = 0.2)
    daily_rate ~ normal(mean, std) truncated at 0  (moments from observed periods)
    demand    ~ poisson(daily_rate * lead_time)
against the current inventory position (fulfillable + inbound). With a single
observed period the rate std is assumed at 35% of the mean — both assumptions
are surfaced in the details payload.
"""

import numpy as np

from .common import latest_snapshot, num, period_days, sku_asin_bridge

DEFAULT_LEAD_TIME_DAYS = 45
FALLBACK_RATE_CV = 0.35
SERVICE_LEVEL = 0.95
TARGET_COVER_EXTRA_DAYS = 30
Z_95 = 1.645
LEAD_TIME_CV = 0.2  # same lognormal lead-time assumption the simulation uses


def closed_form_rop(mean_rate: float, std_rate: float, lead: float) -> float:
    """Textbook variance-aware reorder point as a cross-check on the Monte
    Carlo: ROP = mu_d*mu_L + Z*sqrt(mu_L*sigma_d^2 + mu_d^2*sigma_L^2),
    Z = 1.645 (95% service). Daily demand variance combines Poisson noise
    with rate uncertainty (sigma_d^2 = mu_d + std_rate^2); sigma_L = 0.2*mu_L."""
    var_d = mean_rate + std_rate**2
    sd_l = LEAD_TIME_CV * lead
    return mean_rate * lead + Z_95 * (lead * var_d + (mean_rate * sd_l) ** 2) ** 0.5


def _daily_rates(rows: list[dict], units_key: str) -> list[float]:
    rates = []
    for row in rows:
        units = row.get(units_key)
        if units is None:
            continue
        rates.append(float(units) / period_days(row["period_start"], row["period_end"]))
    return rates


def run(data: dict, rng: np.random.Generator, simulations: int = 20000) -> list[dict]:
    on_hand = latest_snapshot(data["inventory_levels"])
    bridge = sku_asin_bridge(data["sku_economics"], data["cogs_inputs"])
    cogs_by_sku = {r["sku"]: r for r in data["cogs_inputs"]}

    econ_by_sku: dict[str, list[dict]] = {}
    for row in data["sku_economics"]:
        econ_by_sku.setdefault(row["sku"], []).append(row)
    traffic_by_asin: dict[str, list[dict]] = {}
    for row in data["asin_traffic"]:
        traffic_by_asin.setdefault(row["child_asin"], []).append(row)

    results = []
    for sku in sorted(set(on_hand) | set(econ_by_sku)):
        rates = _daily_rates(econ_by_sku.get(sku, []), "units_sold")
        if not rates and bridge.get(sku):
            rates = _daily_rates(traffic_by_asin.get(bridge[sku], []), "units_ordered")
        if not rates:
            continue

        mean_rate = float(np.mean(rates))
        std_rate = float(np.std(rates, ddof=1)) if len(rates) >= 2 else mean_rate * FALLBACK_RATE_CV
        if mean_rate <= 0:
            continue

        cogs_row = cogs_by_sku.get(sku, {})
        lead = int(cogs_row.get("supplier_lead_time_days") or DEFAULT_LEAD_TIME_DAYS)
        inv = on_hand.get(sku, {})
        fulfillable = int(inv.get("fulfillable_quantity") or 0)
        inbound = int(inv.get("inbound_quantity") or 0)
        position = fulfillable + inbound

        lead_times = rng.lognormal(mean=np.log(lead), sigma=0.2, size=simulations)
        sim_rates = np.clip(rng.normal(mean_rate, std_rate, size=simulations), 0, None)
        demand = rng.poisson(sim_rates * lead_times)

        reorder_point = int(np.ceil(np.quantile(demand, SERVICE_LEVEL)))
        results.append(
            {
                "sku": sku,
                "daily_velocity_mean": num(mean_rate, 4),
                "daily_velocity_std": num(std_rate, 4),
                "lead_time_days": lead,
                "on_hand_units": fulfillable,
                "inbound_units": inbound,
                "stockout_probability": num(float(np.mean(demand > position)), 4),
                "days_of_cover": num(position / mean_rate, 1),
                "reorder_point": reorder_point,
                "reorder_qty": int(np.ceil(mean_rate * (lead + TARGET_COVER_EXTRA_DAYS))),
                "safety_stock": max(0, reorder_point - int(round(float(np.mean(demand))))),
                "simulations": simulations,
                "details": {
                    "demand_percentiles": {
                        f"p{p}": num(float(np.quantile(demand, p / 100)), 1) for p in (5, 25, 50, 75, 95)
                    },
                    "closed_form_rop": num(closed_form_rop(mean_rate, std_rate, lead), 1),
                    "observed_periods": len(rates),
                    "lead_time_assumed": sku not in cogs_by_sku
                    or cogs_by_sku[sku].get("supplier_lead_time_days") is None,
                    "rate_std_assumed": len(rates) < 2,
                },
            }
        )
    return results
