"""Lead-time demand against the inventory position, per SKU and across the catalog.

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

Computed exactly, not simulated, since 2026-09-24. The rate and the lead time
are independent lognormals, so their product Λ is lognormal too: log Λ ~
N(log(rate·lead) − σ_r²/2, σ_r² + 0.2²). Lead-time demand is Poisson(Λ), and
    P(D > x) = E_Z[ P(Gamma(x + 1) ≤ exp(μ + sZ)) ],  Z ~ N(0, 1),
a one-dimensional integral taken by the trapezoid rule on a grid fine enough
to resolve the Poisson step (spacing an eighth of its width, 1/(s·√(x+1))),
which converges geometrically for an integrand this smooth. The reorder point
and the demand percentiles are exact quantiles of the same mixture, found by
bisection on the integers. Against four million simulated draws the exact
figures sat within the simulation's own error in every case checked. Why it
matters: with 8,000 draws the stockout probability carried a Monte Carlo error
of about half a point, and a SKU whose true probability sat at the 25% alert
line was drafted a reorder under one simulation seed and not under another
(the Simons–Thorp–Griffin bench, seed 303). The same data now gives the same
advice, and a SKU's figures no longer depend on how many SKUs were simulated
before it.

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
# the exact computation: grid spacing as a share of the Poisson step's width
# in z (smaller is more accurate and slower; an eighth is below 1e-9), and
# the half-width of the grid in standard deviations of the lognormal
QUAD_STEP_SHARE = 1.0 / 8.0
QUAD_MAX_STEP = 0.05
QUAD_HALF_WIDTH = 9.0
PERCENTILES = (5, 25, 50, 75, 95)


def lead_time_mixture(mean_rate: float, std_rate: float, lead: float) -> tuple[float, float]:
    """(μ, s) of log Λ, Λ = rate × lead time, both lognormal and independent."""
    sr = dependence.log_sigma(mean_rate, std_rate)
    mu = float(np.log(mean_rate * lead) - 0.5 * sr * sr)
    return mu, float(np.sqrt(sr * sr + LEAD_TIME_CV * LEAD_TIME_CV))


def demand_sf(x: int, mu: float, s: float) -> float:
    """P(D > x) for D ~ Poisson(Λ), log Λ ~ N(μ, s²), by the trapezoid rule in z."""
    from scipy.special import gammainc
    if x < 0:
        return 1.0
    width = 1.0 / (s * np.sqrt(x + 1.0))
    h = min(QUAD_MAX_STEP, QUAD_STEP_SHARE * width)
    zc = (np.log(x + 1.0) - mu) / s
    z = np.arange(min(-QUAD_HALF_WIDTH, zc - 12 * width), max(QUAD_HALF_WIDTH, zc + 12 * width) + h, h)
    w = np.exp(-0.5 * z * z) * (h / np.sqrt(2.0 * np.pi))
    return float(min(1.0, max(0.0, np.dot(w, gammainc(x + 1.0, np.exp(mu + s * z))))))


def demand_quantile(q: float, mu: float, s: float) -> int:
    """The smallest integer x with P(D ≤ x) ≥ q."""
    lo, hi = -1, max(1, int(np.ceil(1.5 * np.exp(mu + 4.0 * s) + 20)))
    while 1.0 - demand_sf(hi, mu, s) < q:
        hi *= 2
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if 1.0 - demand_sf(mid, mu, s) >= q:
            hi = mid
        else:
            lo = mid
    return hi


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
    """`rng` and `simulations` are accepted for interface parity and unused
    here: each SKU's figures are exact (see the module docstring), so they do
    not depend on a seed or on the SKUs simulated before it.

    `rate_overrides` — {sku: (mean_rate, std_rate)} from the forecast
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

        # exact, not simulated: a single SKU's stockout probability is a
        # marginal statement (a shared factor cannot change it; the joint
        # question is answered by `aggregate` below), and its marginal is a
        # lognormal–Poisson mixture with a one-dimensional integral
        mu, s_log = lead_time_mixture(mean_rate, std_rate, lead)
        reorder_point = demand_quantile(SERVICE_LEVEL, mu, s_log)
        p_out = demand_sf(position, mu, s_log)
        expected_demand = mean_rate * lead * float(np.exp(0.5 * LEAD_TIME_CV ** 2))
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
                "safety_stock": max(0, reorder_point - int(round(expected_demand))),
                "simulations": 0,
                "details": {
                    "method": "exact: lognormal–Poisson mixture, trapezoid rule in z",
                    "demand_percentiles": {
                        f"p{p}": float(demand_quantile(p / 100, mu, s_log)) for p in PERCENTILES
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
                    # no simulation error: the figures are exact for the model
                    "stockout_probability_mc_se": 0.0,
                    "reorder_point_mc_se": 0.0,
                    "lead_demand_log_mu": num(mu, 6),
                    "lead_demand_log_sd": num(s_log, 6),
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
