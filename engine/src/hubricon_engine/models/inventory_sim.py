"""Monte Carlo inventory simulation, per SKU and across the catalog.

Demand during a replenishment lead time is simulated as
    lead_time  ~ lognormal(median = supplier lead time, sigma = 0.2)
    daily_rate ~ lognormal matched to the observed mean and sd, with a shared
                 demand factor across SKUs (models/dependence.py)
    demand     ~ poisson(daily_rate * lead_time)
against the current inventory position (fulfillable + inbound). With a single
observed period the rate std is assumed at 35% of the mean — both assumptions
are surfaced in the details payload.

The rate was a normal truncated at zero until 2026-09-11. Clipping a normal at
zero raises its mean above the one it was calibrated to and removes the skew
demand actually has, and it bit hardest on the thin volatile SKUs where the
stockout question is live. The lognormal is moment-matched, so the marginal mean
and variance are the ones the data showed, and it cannot go negative.

`aggregate` is the panel view and it is the reason the shared factor exists. A
per-SKU stockout probability is a marginal statement and correlation does not
change it. "How many of my SKUs run out in the same month" is a joint statement,
and under independence the answer is far too comfortable — the payload reports
both so the difference is visible.
"""

import numpy as np

from . import dependence
from .common import latest_snapshot, num, period_days, sku_asin_bridge
from .mc import expected_shortfall, quantile_se

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


def _log_rate_panel(econ_by_sku: dict[str, list[dict]]) -> dict[str, list[float]]:
    """{sku: [daily rate per period]} over the periods every SKU shares, which
    is what a cross-sectional correlation has to be computed on."""
    per_sku: dict[str, dict[str, float]] = {}
    for sku, rows in econ_by_sku.items():
        for row in rows:
            units = row.get("units_sold")
            if units is None:
                continue
            rate = float(units) / period_days(row["period_start"], row["period_end"])
            if rate > 0:
                per_sku.setdefault(sku, {})[row["period_start"]] = rate
    if not per_sku:
        return {}
    shared = set.intersection(*(set(v) for v in per_sku.values())) if per_sku else set()
    if len(shared) < dependence.MIN_PANEL_PERIODS:
        return {}
    order = sorted(shared)
    return {sku: [v[p] for p in order] for sku, v in per_sku.items()}


def run(data: dict, rng: np.random.Generator, simulations: int = 20000,
        rate_overrides: dict[str, tuple[float, float]] | None = None,
        seasonal: dict | None = None, today=None) -> list[dict]:
    """`rate_overrides` — {sku: (mean_rate, std_rate)} from the forecast
    ladder; when present for a SKU it replaces the mean/std of observed
    periods so the stockout probability and the demand forecast are the
    same distribution. Surfaced as details.rate_source.

    `seasonal` — models/seasonality.indices(data). With it, the rate over the
    lead time is the flat rate times the mean index over that window's
    calendar days, and the index's own uncertainty widens the rate's sd."""
    from datetime import date as _date
    from .seasonality import seasonal_rate
    rate_overrides = rate_overrides or {}
    today = today or _date.today()
    on_hand = latest_snapshot(data["inventory_levels"])
    bridge = sku_asin_bridge(data["sku_economics"], data["cogs_inputs"])
    cogs_by_sku = {r["sku"]: r for r in data["cogs_inputs"]}

    econ_by_sku: dict[str, list[dict]] = {}
    for row in data["sku_economics"]:
        econ_by_sku.setdefault(row["sku"], []).append(row)
    traffic_by_asin: dict[str, list[dict]] = {}
    for row in data["asin_traffic"]:
        traffic_by_asin.setdefault(row["child_asin"], []).append(row)

    from .data_quality import contaminated_periods
    from .seasonality import index_for
    bad = contaminated_periods(data)
    results = []
    for sku in sorted(set(on_hand) | set(econ_by_sku)):
        # the same history the forecast reads: one row per period, contaminated months out
        rows = [r for r in {(str(r["period_start"]), str(r["period_end"])): r
                            for r in econ_by_sku.get(sku, [])}.values()
                if str(r["period_start"])[:10] not in (bad.get(sku) or {})]
        rates = _daily_rates(rows, "units_sold")
        months = [int(str(r["period_start"])[5:7]) for r in rows if r.get("units_sold") is not None]
        if not rates and bridge.get(sku):
            rows = traffic_by_asin.get(bridge[sku], [])
            rates = _daily_rates(rows, "units_ordered")
            months = [int(str(r["period_start"])[5:7]) for r in rows if r.get("units_ordered") is not None]
        if not rates:
            continue
        # observed periods at an index of one: each divided by its own month's
        # index, so a history that happens to end in a peak does not read as
        # a higher base (corrected 2026-09-24 with forecast.rate_moments)
        if seasonal and seasonal.get("status") == "ok" and len(months) == len(rates):
            rates = [x / max(index_for(seasonal, sku, mo)[0], 1e-6) for x, mo in zip(rates, months)]

        mean_rate = float(np.mean(rates))
        std_rate = float(np.std(rates, ddof=1)) if len(rates) >= 2 else mean_rate * FALLBACK_RATE_CV
        rate_source = "observed periods"
        if sku in rate_overrides and rate_overrides[sku][0] and rate_overrides[sku][0] > 0:
            mean_rate, std_rate = float(rate_overrides[sku][0]), float(rate_overrides[sku][1] or mean_rate * FALLBACK_RATE_CV)
            rate_source = "forecast"
        if mean_rate <= 0:
            continue

        cogs_row = cogs_by_sku.get(sku, {})
        lead = int(cogs_row.get("supplier_lead_time_days") or DEFAULT_LEAD_TIME_DAYS)
        base_rate, base_sd = mean_rate, std_rate
        mean_rate, std_rate, season_note = seasonal_rate(mean_rate, std_rate, seasonal, sku, today, lead)
        inv = on_hand.get(sku, {})
        fulfillable = int(inv.get("fulfillable_quantity") or 0)
        inbound = int(inv.get("inbound_quantity") or 0)
        position = fulfillable + inbound

        lead_times = rng.lognormal(mean=np.log(lead), sigma=0.2, size=simulations)
        # marginal draws: rho = 0 here on purpose. A single SKU's stockout
        # probability is a marginal statement and a shared factor cannot change
        # it; the joint question is answered by `aggregate` below.
        sim_rates = dependence.correlated_rates(
            rng, [mean_rate], [std_rate], (simulations,), 0.0)[0]
        demand = rng.poisson(sim_rates * lead_times)

        reorder_point = int(np.ceil(np.quantile(demand, SERVICE_LEVEL)))
        p_out = float(np.mean(demand > position))
        results.append(
            {
                "sku": sku,
                "daily_velocity_mean": num(mean_rate, 4),
                "daily_velocity_std": num(std_rate, 4),
                "lead_time_days": lead,
                "on_hand_units": fulfillable,
                "inbound_units": inbound,
                "stockout_probability": num(p_out, 4),
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
                    "rate_source": rate_source,
                    # the rate at a seasonal index of one; daily_velocity_mean
                    # is the lead window's. A model that applies its own
                    # window's index (the cash cone) must start from this one.
                    "daily_velocity_base": num(base_rate, 4),
                    "daily_velocity_base_std": num(base_sd, 4),
                    "lead_time_assumed": sku not in cogs_by_sku
                    or cogs_by_sku[sku].get("supplier_lead_time_days") is None,
                    "rate_std_assumed": len(rates) < 2,
                    "rate_distribution": "lognormal, moments matched to observed",
                    **season_note,
                    "stockout_probability_mc_se": num(
                        float(np.sqrt(max(0.0, p_out * (1 - p_out)) / simulations)), 5),
                    "reorder_point_mc_se": num(
                        quantile_se(demand.astype(float), SERVICE_LEVEL), 3),
                },
            }
        )
    return results


def aggregate(results: list[dict], data: dict, rng: np.random.Generator,
              simulations: int = 20000) -> dict:
    """How many SKUs run out in the same lead time, with the catalog's own
    demand correlation and without it.

    A per-SKU stockout probability says nothing about whether the bad months
    arrive together. Demand shocks are shared — a slow season is slow across the
    catalog — so the count of simultaneous stockouts has a much fatter upper tail
    than independence implies. Both are reported, along with the expected
    shortfall of the count: the mean number out of stock in the worst 5% of
    months, which is the number a replenishment budget should be sized against,
    not the 95th percentile at its edge.
    """
    usable = [r for r in results
              if (r.get("daily_velocity_mean") or 0) > 0 and r.get("lead_time_days")]
    if not usable:
        return {"status": "insufficient_data",
                "reason": "no SKU with a positive demand rate"}

    econ_by_sku: dict[str, list[dict]] = {}
    for row in data.get("sku_economics") or []:
        econ_by_sku.setdefault(row["sku"], []).append(row)
    correlation = dependence.estimate_pairwise_corr(_log_rate_panel(econ_by_sku))

    means = [float(r["daily_velocity_mean"]) for r in usable]
    sds = [float(r["daily_velocity_std"] or 0) for r in usable]
    positions = np.array([int(r.get("on_hand_units") or 0) + int(r.get("inbound_units") or 0)
                          for r in usable])
    leads = np.array([float(r["lead_time_days"]) for r in usable])

    out = {"status": "ok", "skus": len(usable), "simulations": int(simulations),
           "correlation": correlation}
    # two independent streams derived from the caller's generator: the comparison
    # must be between the two dependence models, not between two draw sets that
    # happen to share numbers
    seeds = [int(v) for v in rng.integers(0, 2**62, size=2)]
    for (label, rho), seed in zip((("correlated", correlation["rho"]),
                                   ("independent", 0.0)), seeds):
        stream = np.random.default_rng(seed)
        # streamed per SKU: the count is all that is needed, not the panel
        count = np.zeros(simulations, dtype=float)
        for i, rates in dependence.rate_stream(stream, means, sds, (simulations,), rho):
            lead_draws = stream.lognormal(mean=np.log(leads[i]), sigma=LEAD_TIME_CV,
                                          size=simulations)
            demand = stream.poisson(rates * lead_draws)
            count += demand > positions[i]
        tail = expected_shortfall(count, 0.05, tail="upper")
        out[label] = {
            "expected_stockouts": num(float(count.mean()), 3),
            "p95_stockouts": num(float(np.quantile(count, 0.95)), 1),
            "p95_mc_se": num(quantile_se(count, 0.95), 3),
            "expected_shortfall_stockouts": num(tail["shortfall"], 3),
            "expected_shortfall_mc_se": num(tail["se"], 3),
            "p_at_least_one": num(float((count >= 1).mean()), 4),
            "p_three_or_more": num(float((count >= 3).mean()), 4),
        }
    out["basis"] = (
        f"{len(usable)} SKUs, {simulations:,} simulated lead times. Demand shares a "
        f"common factor with pairwise log-demand correlation "
        f"{correlation['pairwise_corr']:.2f} "
        f"({'measured from ' + str(correlation['panel_periods']) + ' shared periods' if correlation['basis'] == 'estimated' else 'a conservative default: the history is too thin to measure one'}). "
        f"The independent figures are what the engine reported before and are kept "
        f"beside these so the difference is visible."
    )
    return out
