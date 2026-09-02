"""Actuarial layer: value-at-risk, concentration, credibility, reserves, survival.

Five instruments, each a textbook estimator rather than a fitted model, so
every number has a name a client's accountant or insurer would recognise:

    var_cvar                 — value-at-risk and expected shortfall (CVaR) of a
                               loss sample. VaR answers "how bad is the
                               5th-worst-in-100 month"; CVaR answers "and how
                               bad is it on average once you are there".
    hhi                      — Herfindahl–Hirschman concentration index, the
                               antitrust measure, applied to the client's own
                               revenue / ad spend / traffic so that a single
                               listing suppression or campaign pause has a size.
    buhlmann                 — Bühlmann–Straub credibility: shrink a thin SKU's
                               own margin toward the catalog mean by exactly as
                               much as its sample size warrants.
    compound_poisson_reserve — the actuary's aggregate-loss model: N ~ Poisson
                               claims, each with a severity drawn from history.
                               Here: returned units next period and their cost.
    kaplan_meier             — product-limit survival curve on SKU "lives",
                               treating SKUs that are still selling as
                               right-censored rather than pretending they died.

The Monte Carlo behind `run()["var"]` uses the same demand generator as the
inventory simulation and the cash-flow cone (rate-uncertain Poisson), so the
three can never disagree about what demand is.

Honesty discipline: every section carries a `status`; thin inputs yield
`insufficient_data` and no number that looks like a finding; every modelling
choice with a dollar consequence is spelled out under `assumptions` / `basis`
— that text is shown to clients.
"""

import math
from collections import Counter, defaultdict
from datetime import date, timedelta

import numpy as np

from .common import num, period_days

DEFAULT_PATHS = 10000
FALLBACK_RATE_CV = 0.35  # single observed period: same assumption as inventory_sim
HHI_HIGHLY_CONCENTRATED = 1800  # DOJ/FTC Merger Guidelines (Dec 2023) §2.1
HHI_MODERATE = 1000
CAMPAIGN_WINDOW_DAYS = 30
CREDIBILITY_MIN_PERIODS = 2
CREDIBILITY_MIN_GROUPS = 3
BOOTSTRAP_MIN_SEVERITIES = 5
RESERVE_CHUNK_DRAWS = 2_000_000  # memory guard for the compound-Poisson sampler
RETURN_LOSS_FRACTION = {
    "SELLABLE": 0.20,
    "DAMAGED": 1.00,
    "CUSTOMER_DAMAGED": 1.00,
    "DEFECTIVE": 1.00,
    "EXPIRED": 1.00,
    "CARRIER_DAMAGED": 1.00,
}
RETURN_LOSS_FRACTION_UNKNOWN = 0.60
SURVIVAL_MIN_SKUS = 8
SURVIVAL_MIN_PERIODS = 6
DEATH_ZERO_PERIODS = 2
DECLINE_RECENT_PERIODS = 3
DECLINE_THRESHOLD = 0.50


# ── pure estimators ───────────────────────────────────────────────────────


def _var_cvar_raw(losses: np.ndarray, alpha: float) -> tuple[float, float]:
    var = float(np.quantile(losses, alpha))
    tail = losses[losses >= var]
    cvar = float(tail.mean()) if tail.size else var
    return var, cvar


def var_cvar(losses, alpha: float = 0.95) -> dict:
    """Value-at-risk and conditional VaR (expected shortfall) of a loss sample.

    Losses are positive-is-bad. VaR_α is the empirical α-quantile: the loss
    exceeded in only (1 − α) of outcomes. CVaR_α is the mean of the losses at
    or beyond VaR_α: the average outcome *given* that you are in the bad tail,
    so CVaR ≥ VaR always.

    Coherence (Artzner, Delbaen, Eber & Heath 1999): CVaR is a coherent risk
    measure — monotone, positively homogeneous, translation-invariant and
    sub-additive, so a portfolio's CVaR never exceeds the sum of its parts'.
    VaR is not sub-additive: two SKUs' VaRs can sum to *less* than the VaR of
    the pair, which is why the payload leads the client with CVaR and reports
    VaR only as the familiar headline. An empty or all-NaN sample yields None
    fields rather than a number.
    """
    arr = np.asarray(losses, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"var": None, "cvar": None, "alpha": alpha, "n": 0}
    var, cvar = _var_cvar_raw(arr, alpha)
    return {"var": num(var), "cvar": num(cvar), "alpha": alpha, "n": int(arr.size)}


def hhi(values: dict[str, float]) -> dict:
    """Herfindahl–Hirschman index on the 0–10,000 scale (sum of squared
    percentage shares). 10,000 = one item is everything; N equal items = 10,000/N,
    so `effective_n` = 10,000 / HHI reads as "how many equal-sized items this
    is equivalent to".

    Levels follow the U.S. DOJ/FTC Merger Guidelines (December 2023, §2.1):
    HHI above 1,800 is "highly concentrated", 1,000–1,800 "moderately
    concentrated", below 1,000 unconcentrated (here "diversified"). The
    thresholds were written for markets, not catalogs, but they are the
    published line and the intuition transfers: above 1,800 one item's loss
    is a business event, not a line item.

    Negative and None values are ignored (shares are of positive mass). Empty
    input or zero total → status insufficient_data with no index.
    """
    clean = {}
    for key, value in values.items():
        if value is None:
            continue
        v = float(value)
        if math.isfinite(v) and v > 0:
            clean[key] = v
    total = sum(clean.values())
    if not clean or total <= 0:
        return {"status": "insufficient_data", "hhi": None, "effective_n": None,
                "top_item": None, "top_share": None, "n": len(clean), "level": None}
    shares = {k: v / total for k, v in clean.items()}
    index = 10000.0 * sum(s * s for s in shares.values())
    top = max(shares, key=shares.get)
    if index >= HHI_HIGHLY_CONCENTRATED:
        level = "highly_concentrated"
    elif index >= HHI_MODERATE:
        level = "moderate"
    else:
        level = "diversified"
    return {
        "status": "ok",
        "hhi": num(index, 1),
        "effective_n": num(10000.0 / index, 2),
        "top_item": top,
        "top_share": num(shares[top], 4),
        "n": len(clean),
        "level": level,
    }


def buhlmann(groups: dict[str, list[float]]) -> dict:
    """Bühlmann–Straub credibility with one unit of weight per observation.

    Why: a SKU with two months of history has a margin estimate whose sampling
    error is as large as the genuine differences between SKUs. Credibility
    theory answers "how much should I believe this SKU's own number versus the
    catalog?" with the linear Bayes estimator

        blended_g = Z_g · raw_mean_g + (1 − Z_g) · mu,   Z_g = n_g / (n_g + k),
        k = within_var / between_var.

    k is the number of observations at which a SKU's own mean earns exactly
    half the weight. If SKUs genuinely differ a lot (large between-variance),
    k is small and even thin SKUs stand on their own; if the spread of SKU
    means is explained by noise (between ≈ 0), k → ∞, Z = 0 and every SKU is
    reported at the catalog mean. Unlike a fixed "minimum three periods" rule
    this degrades smoothly and never invents precision.

    Estimators (Bühlmann & Gisler 2005, §4.8; Klugman, Panjer & Willmot §16.4):
        mu          = grand mean over all observations
        within_var  = pooled within-group variance, Σ_g Σ_i (x_gi − x̄_g)² / Σ_g (n_g − 1)
        between_var = max(0, [Σ_g n_g (x̄_g − mu)² − (G − 1)·within_var] / [N − Σ_g n_g² / N])
    With equal group sizes the between estimator reduces to the familiar
    "variance of group means − within_var / n"; the general form above is the
    unbiased version for unequal n_g (a 1-period SKU next to a 12-period SKU).
    Needs ≥ 2 groups and at least one group with ≥ 2 observations, else
    status insufficient_data. `k` is None (with `k_infinite` True) when
    between_var is zero.
    """
    clean: dict[str, np.ndarray] = {}
    for name, obs in groups.items():
        arr = np.asarray([float(x) for x in obs if x is not None], dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            clean[name] = arr
    n_by = {g: int(a.size) for g, a in clean.items()}
    n_total = sum(n_by.values())
    n_groups = len(clean)
    df_within = sum(n - 1 for n in n_by.values())
    if n_groups < 2 or df_within == 0:
        return {"status": "insufficient_data", "k": None, "k_infinite": False,
                "within_var": None, "between_var": None, "mu": None,
                "n_groups": n_groups, "by_group": {}}

    mu = float(sum(a.sum() for a in clean.values()) / n_total)
    means = {g: float(a.mean()) for g, a in clean.items()}
    within = float(sum(((a - a.mean()) ** 2).sum() for a in clean.values()) / df_within)
    ss_between = sum(n_by[g] * (means[g] - mu) ** 2 for g in clean)
    denom = n_total - sum(n * n for n in n_by.values()) / n_total
    between = max(0.0, (ss_between - (n_groups - 1) * within) / denom)
    k = within / between if between > 0 else math.inf

    by_group = {}
    for g in clean:
        n = n_by[g]
        z = 0.0 if math.isinf(k) else n / (n + k)
        by_group[g] = {
            "n": n,
            "raw_mean": num(means[g], 4),
            "z": num(z, 4),
            "blended": num(z * means[g] + (1 - z) * mu, 4),
        }
    return {
        "status": "ok",
        "k": num(k, 2),
        "k_infinite": math.isinf(k),
        "within_var": num(within, 6),
        "between_var": num(between, 6),
        "mu": num(mu, 4),
        "n_groups": n_groups,
        "by_group": by_group,
    }


def compound_poisson_reserve(lam: float, exposure: float, severities,
                             rng: np.random.Generator, n_paths: int = DEFAULT_PATHS) -> dict:
    """Aggregate loss S = X_1 + … + X_N with N ~ Poisson(lam · exposure).

    The classic collective-risk model: claim *frequency* and claim *severity*
    are modelled separately, so a change in either (a return-rate spike, a
    price rise) moves the reserve for a reason you can name. E[S] =
    lam · exposure · E[X]; the quantiles are read off `n_paths` simulated
    periods.

    Severity sampling: with ≥ 5 observed severities we bootstrap (draw with
    replacement from the empirical distribution — no shape assumption); with
    fewer we fit a Gamma by method of moments to what exists (shape = m²/v,
    scale = v/m) and sample from it; a single or constant severity is used as
    is. `method` records which. Paths are generated in chunks so a large
    expected count never allocates more than ~2M draws at once.
    """
    sev = np.asarray(severities, dtype=float).ravel()
    sev = sev[np.isfinite(sev) & (sev >= 0)]
    lam = float(lam or 0)
    exposure = float(exposure or 0)
    if sev.size == 0 or lam <= 0 or exposure <= 0:
        return {"status": "insufficient_data", "expected": None, "p50": None, "p95": None,
                "p99": None, "lam": num(lam, 4), "exposure": num(exposure),
                "severity_mean": num(sev.mean()) if sev.size else None,
                "method": None, "n_paths": 0, "n_severities": int(sev.size)}

    mean = float(sev.mean())
    if sev.size >= BOOTSTRAP_MIN_SEVERITIES:
        method = "bootstrap"

        def sampler(m):
            return rng.choice(sev, size=m, replace=True)
    else:
        var = float(sev.var(ddof=1)) if sev.size >= 2 else 0.0
        if var > 0 and mean > 0:
            method = "gamma_mom"
            shape, scale = mean * mean / var, var / mean

            def sampler(m):
                return rng.gamma(shape, scale, size=m)
        else:
            method = "constant"

            def sampler(m):
                return np.full(m, mean)

    expected_n = lam * exposure
    agg = np.zeros(n_paths)
    chunk = max(1, int(RESERVE_CHUNK_DRAWS // max(1.0, expected_n)))
    for start in range(0, n_paths, chunk):
        counts = rng.poisson(expected_n, size=min(chunk, n_paths - start))
        total = int(counts.sum())
        if total == 0:
            continue
        draws = sampler(total)
        idx = np.repeat(np.arange(counts.size), counts)
        agg[start:start + counts.size] = np.bincount(idx, weights=draws, minlength=counts.size)

    return {
        "status": "ok",
        "expected": num(float(agg.mean())),
        "p50": num(float(np.quantile(agg, 0.50))),
        "p95": num(float(np.quantile(agg, 0.95))),
        "p99": num(float(np.quantile(agg, 0.99))),
        "lam": num(lam, 4),
        "exposure": num(exposure),
        "expected_claims": num(expected_n, 2),
        "severity_mean": num(mean),
        "method": method,
        "n_paths": int(n_paths),
        "n_severities": int(sev.size),
    }


def kaplan_meier(durations: list[float], observed: list[bool]) -> dict:
    """Product-limit survival estimator.

    S(t) = Π_{t_j ≤ t} (1 − d_j / n_j) over the distinct event times t_j, with
    d_j events at t_j and n_j subjects still at risk (duration ≥ t_j). A
    censored subject (observed=False — still alive when the data ends) stays
    in the risk set up to its duration and then leaves without an event,
    which is the whole point: ignoring it would bias lifetimes short, and
    counting it as a death would bias them shorter still.

    Returns the step curve as parallel lists (anchored at t=0, S=1), the
    median lifetime (first t with S ≤ 0.5, None if the curve never gets
    there — more than half are still alive), n and the event count.
    """
    dur = np.asarray(durations, dtype=float).ravel()
    obs = np.asarray(observed, dtype=bool).ravel()
    if dur.size == 0 or dur.size != obs.size:
        return {"status": "insufficient_data", "t": [], "s": [], "median": None,
                "n": int(dur.size), "events": 0}
    t_out, s_out = [0.0], [1.0]
    survival, median = 1.0, None
    for t in np.unique(dur[obs]):
        at_risk = int(np.sum(dur >= t))
        events = int(np.sum((dur == t) & obs))
        survival *= 1.0 - events / at_risk
        t_out.append(float(t))
        s_out.append(survival)
        if median is None and survival <= 0.5:
            median = float(t)
    return {
        "status": "ok",
        "t": [num(t, 2) for t in t_out],
        "s": [num(s, 4) for s in s_out],
        "median": num(median, 2) if median is not None else None,
        "n": int(dur.size),
        "events": int(obs.sum()),
    }


# ── run() sections ────────────────────────────────────────────────────────


def _insufficient(reason: str, **extra) -> dict:
    out = {"status": "insufficient_data", "reason": reason, "assumptions": []}
    out.update(extra)
    return out


def _latest_margins_by_sku(margin_rows: list[dict]) -> dict[str, dict]:
    if not margin_rows:
        return {}
    latest = max(m["period_start"] for m in margin_rows)
    return {m["sku"]: m for m in margin_rows if m["period_start"] == latest}


def _var_section(margin_rows: list[dict], forecast_rows: list[dict] | None,
                 rng: np.random.Generator, n_paths: int) -> dict:
    latest = _latest_margins_by_sku(margin_rows)
    if not latest:
        return _insufficient("no margin rows")
    sample = next(iter(latest.values()))
    start, end = sample["period_start"], sample["period_end"]
    days = period_days(start, end)

    history: dict[str, list[float]] = defaultdict(list)
    for m in margin_rows:
        if m.get("units") is not None:
            history[m["sku"]].append(float(m["units"]) / period_days(m["period_start"], m["period_end"]))
    forecasts = {}
    for f in forecast_rows or []:
        # forecast.run() emits sku- and asin-level rows; only ok sku-level rows carry a usable rate
        if f.get("level", "sku") != "sku" or f.get("status", "ok") != "ok":
            continue
        key = f.get("item_id") or f.get("sku")
        if key:
            forecasts[key] = f

    params = []
    n_forecast = n_observed = n_cv_fallback = n_no_cogs = 0
    for sku, m in sorted(latest.items()):
        units = float(m.get("units") or 0)
        revenue = float(m.get("revenue") or 0)
        if units <= 0 or revenue <= 0:
            continue
        fees = float(m.get("amazon_fees") or 0)
        cogs = m.get("cogs")
        if cogs is None:
            n_no_cogs += 1
        rate = sd = None
        f = forecasts.get(sku)
        if f and f.get("daily_rate_point") is not None:
            rate = float(f["daily_rate_point"])
            err = (f.get("details") or {}).get("error_sd")
            sd = float(err) if err is not None else None
            n_forecast += 1
        else:
            rates = history.get(sku) or []
            if not rates:
                continue
            rate = float(np.mean(rates))
            sd = float(np.std(rates, ddof=1)) if len(rates) >= 2 else None
            n_observed += 1
        if rate <= 0:
            continue
        if sd is None:
            sd = rate * FALLBACK_RATE_CV
            n_cv_fallback += 1
        params.append({
            "sku": sku, "rate": rate, "sd": sd,
            "contribution": (revenue - fees - float(cogs or 0)) / units,
            "price": revenue / units,
            "ads": float(m.get("ad_spend_allocated") or 0),
        })
    if not params:
        return _insufficient("no SKU in the latest margin period with units, revenue and a demand rate")

    net = np.zeros(n_paths)
    rev = np.zeros(n_paths)
    for p in params:
        rates = np.clip(rng.normal(p["rate"], p["sd"], size=n_paths), 0, None)
        units = rng.poisson(rates * days)
        net += units * p["contribution"] - p["ads"]
        rev += units * p["price"]
    expected = float(net.mean())
    losses = expected - net
    var95, cvar95 = _var_cvar_raw(losses, 0.95)
    var99, cvar99 = _var_cvar_raw(losses, 0.99)

    assumptions = [
        "Demand per SKU: daily rate ~ normal(point, sd) truncated at 0, units ~ Poisson(rate × days) — "
        "the same generator as the inventory simulation and cash-flow cone",
        f"Unit contribution (revenue − Amazon fees − COGS) / units and ad spend are frozen at the latest "
        f"period ({start} to {end}); only unit volume is uncertain",
        "Loss = expected net − simulated net; VaR/CVaR are dollars below expectation, not absolute losses",
    ]
    if n_forecast:
        assumptions.append(f"{n_forecast} SKU(s) use the forecast model's daily rate and error sd")
    if n_observed:
        assumptions.append(f"{n_observed} SKU(s) use the mean/sd of their observed period rates")
    if n_cv_fallback:
        assumptions.append(f"{n_cv_fallback} SKU(s) had no rate sd — assumed {int(FALLBACK_RATE_CV * 100)}% of the mean")
    if n_no_cogs:
        assumptions.append(f"{n_no_cogs} SKU(s) have no landed cost on file — their contribution excludes COGS")
    return {
        "status": "ok",
        "expected_net": num(expected),
        "var_95": num(var95),
        "cvar_95": num(cvar95),
        "var_99": num(var99),
        "cvar_99": num(cvar99),
        "worst_5pct_net": num(expected - cvar95),
        "p5_net": num(float(np.quantile(net, 0.05))),
        "p50_net": num(float(np.quantile(net, 0.50))),
        "revenue_p5": num(float(np.quantile(rev, 0.05))),
        "revenue_p50": num(float(np.quantile(rev, 0.50))),
        "n_paths": int(n_paths),
        "skus_modeled": len(params),
        "period_start": start,
        "period_end": end,
        "period_days": days,
        "rate_source": {"forecast": n_forecast, "observed": n_observed},
        "assumptions": assumptions,
    }


def _dimension(name: str, values: dict[str, float], basis: str) -> dict:
    out = {"dimension": name}
    out.update(hhi(values))
    out["basis"] = basis
    return out


def _concentration_section(data: dict, margin_rows: list[dict]) -> dict:
    latest = _latest_margins_by_sku(margin_rows)
    sku_revenue = _dimension(
        "sku_revenue",
        {sku: float(m.get("revenue") or 0) for sku, m in latest.items()},
        "share of revenue by SKU in the latest margin period",
    )
    if sku_revenue["status"] == "ok":
        top = latest[sku_revenue["top_item"]]
        sku_revenue["top_item_asin"] = top.get("asin")
        sku_revenue["dollar_at_risk_top_item"] = num(top.get("net_margin") or 0)
        sku_revenue["basis"] += (
            "; dollar_at_risk_top_item = that SKU's latest-period net margin, "
            "i.e. what one listing suppression costs per period"
        )

    ppc_spend = data.get("ppc_spend") or []
    ppc_terms = data.get("ppc_search_terms") or []
    campaign_values: dict[str, float] = defaultdict(float)
    campaign_basis = "no campaign spend data"
    dated = [r for r in ppc_spend if r.get("report_date")]
    if dated:
        newest = max(r["report_date"] for r in dated)
        window_start = (date.fromisoformat(newest) - timedelta(days=CAMPAIGN_WINDOW_DAYS - 1)).isoformat()
        for r in dated:
            if window_start <= r["report_date"] <= newest:
                key = r.get("campaign_name") or r.get("campaign_id") or "?"
                campaign_values[key] += float(r.get("spend") or 0)
        campaign_basis = f"share of campaign spend over the last {CAMPAIGN_WINDOW_DAYS} days present ({window_start} to {newest})"
    elif ppc_terms:
        latest_start = max(r["period_start"] for r in ppc_terms)
        for r in ppc_terms:
            if r["period_start"] == latest_start:
                campaign_values[r.get("campaign_name") or "?"] += float(r.get("spend") or 0)
        campaign_basis = f"share of campaign spend in the latest search-term report window (from {latest_start})"
    campaign_spend = _dimension("campaign_spend", dict(campaign_values), campaign_basis)

    term_values: dict[str, float] = defaultdict(float)
    term_basis = "no search-term data"
    if ppc_terms:
        latest_start = max(r["period_start"] for r in ppc_terms)
        for r in ppc_terms:
            if r["period_start"] == latest_start:
                term_values[r.get("search_term") or "?"] += float(r.get("spend") or 0)
        term_basis = f"share of spend by search term in the latest report window (from {latest_start})"
    search_term_spend = _dimension("search_term_spend", dict(term_values), term_basis)

    traffic = data.get("asin_traffic") or []
    session_values: dict[str, float] = defaultdict(float)
    session_basis = "no traffic data"
    if traffic:
        latest_start = max(r["period_start"] for r in traffic)
        for r in traffic:
            if r["period_start"] == latest_start:
                session_values[r.get("child_asin") or "?"] += float(r.get("sessions") or 0)
        session_basis = f"share of sessions by child ASIN in the latest traffic period (from {latest_start})"
    asin_sessions = _dimension("asin_sessions", dict(session_values), session_basis)

    dims = {"sku_revenue": sku_revenue, "campaign_spend": campaign_spend,
            "search_term_spend": search_term_spend, "asin_sessions": asin_sessions}
    status = "ok" if any(d["status"] == "ok" for d in dims.values()) else "insufficient_data"
    return {
        "status": status,
        **dims,
        "assumptions": [
            f"HHI on the 0–10,000 scale; levels per DOJ/FTC 2023 Merger Guidelines "
            f"(≥{HHI_HIGHLY_CONCENTRATED} highly concentrated, ≥{HHI_MODERATE} moderate)",
            "effective_n = 10,000 / HHI: the number of equal-sized items this mix is equivalent to",
        ],
    }


def _credibility_section(margin_rows: list[dict]) -> dict:
    groups: dict[str, list[float]] = defaultdict(list)
    for m in margin_rows:
        if m.get("net_margin_pct") is not None:
            groups[m["sku"]].append(float(m["net_margin_pct"]))
    groups = {g: v for g, v in groups.items() if len(v) >= CREDIBILITY_MIN_PERIODS}
    basis = (f"Bühlmann–Straub credibility on net margin % per SKU per period; SKUs with ≥ "
             f"{CREDIBILITY_MIN_PERIODS} periods, ≥ {CREDIBILITY_MIN_GROUPS} SKUs required")
    if len(groups) < CREDIBILITY_MIN_GROUPS:
        return _insufficient(f"{len(groups)} SKU(s) with ≥ {CREDIBILITY_MIN_PERIODS} margin periods; "
                             f"need {CREDIBILITY_MIN_GROUPS}", basis=basis)
    result = buhlmann(groups)
    if result["status"] != "ok":
        return _insufficient("credibility variance components not identifiable", basis=basis)
    by_sku = result.pop("by_group")
    adjustments = sorted(
        ({"sku": sku, **vals, "adjustment": num(vals["blended"] - vals["raw_mean"], 4)}
         for sku, vals in by_sku.items()),
        key=lambda r: -abs(r["adjustment"] or 0),
    )
    return {
        **result,
        "by_sku": by_sku,
        "largest_adjustments": adjustments[:5],
        "basis": basis,
        "assumptions": [
            "k = within-SKU variance / between-SKU variance: the number of periods at which a SKU's own "
            "margin earns half the weight; z = n / (n + k)",
            "blended = z × SKU's own mean + (1 − z) × catalog mean — the linear Bayes estimate, so a "
            "2-period SKU's margin is pulled toward the catalog until it earns its own number",
            "No outlier trimming: extreme margin months count as observed",
        ],
    }


def _latest_prices(econ: list[dict]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for r in sorted(econ, key=lambda r: r["period_start"]):
        price = r.get("avg_sales_price")
        if price is None and r.get("units_sold") and r.get("sales"):
            price = float(r["sales"]) / float(r["units_sold"])
        if price is not None and float(price) > 0:
            prices[r["sku"]] = float(price)
    return prices


def _returns_section(data: dict, rng: np.random.Generator, n_paths: int) -> dict:
    returns = data.get("fba_returns") or []
    econ = data.get("sku_economics") or []
    basis = ("Compound Poisson: returned units next period ~ Poisson(return rate × units sold in the "
             "latest period); each returned unit costs its SKU's latest price × loss fraction by disposition")
    if not returns:
        return _insufficient("no FBA returns rows", basis=basis)
    if not econ:
        return _insufficient("no sku_economics rows to give the returns an exposure base", basis=basis)

    periods = sorted({(r["period_start"], r["period_end"]) for r in econ
                      if r.get("period_start") and r.get("period_end")})
    if not periods:
        return _insufficient("sku_economics rows carry no periods", basis=basis)
    latest_start = max(p[0] for p in periods)
    exposure = sum(float(r.get("units_sold") or 0) for r in econ if r["period_start"] == latest_start)
    if exposure <= 0:
        return _insufficient("no units sold in the latest sku_economics period", basis=basis)

    dated = [(str(r["return_date"])[:10], r) for r in returns if r.get("return_date")]
    if not dated:
        return _insufficient("returns rows carry no return_date", basis=basis)
    r_min, r_max = min(d for d, _ in dated), max(d for d, _ in dated)
    window = [p for p in periods if p[0] <= r_max and p[1] >= r_min]
    in_window = [(d, r) for d, r in dated if any(s <= d <= e for s, e in window)]
    overlap = bool(window and in_window)
    if not overlap:
        window, in_window = periods, dated
    window_set = set(window)
    units_window = sum(float(r.get("units_sold") or 0) for r in econ
                       if (r["period_start"], r["period_end"]) in window_set)
    units_window_by_sku: dict[str, float] = defaultdict(float)
    for r in econ:
        if (r["period_start"], r["period_end"]) in window_set:
            units_window_by_sku[r["sku"]] += float(r.get("units_sold") or 0)
    returned_units = sum(int(r.get("quantity") or 1) for _, r in in_window)
    if units_window <= 0 or returned_units <= 0:
        return _insufficient("no units sold (or none returned) in the returns window", basis=basis)
    lam = returned_units / units_window

    prices = _latest_prices(econ)
    catalog_price = float(np.mean(list(prices.values()))) if prices else None
    severities: list[float] = []
    by_disposition: Counter = Counter()
    by_sku_units: Counter = Counter()
    unpriced = 0
    for _, r in in_window:
        qty = int(r.get("quantity") or 1)
        disposition = str(r.get("detailed_disposition") or "UNKNOWN").strip().upper() or "UNKNOWN"
        fraction = RETURN_LOSS_FRACTION.get(disposition, RETURN_LOSS_FRACTION_UNKNOWN)
        price = prices.get(r.get("sku"))
        if price is None:
            price = catalog_price
            unpriced += qty
        by_disposition[disposition] += qty
        by_sku_units[r.get("sku") or "?"] += qty
        if price is None:
            continue
        severities.extend([price * fraction] * qty)
    if not severities:
        return _insufficient("no sale price available to cost the returned units", basis=basis)

    reserve = compound_poisson_reserve(lam, exposure, np.asarray(severities), rng, n_paths=n_paths)
    if reserve["status"] != "ok":
        return _insufficient("reserve simulation had no frequency or severity to work with", basis=basis)

    by_sku = []
    for sku, units in by_sku_units.most_common(5):
        sold = units_window_by_sku.get(sku, 0.0)
        by_sku.append({
            "sku": sku,
            "units_returned": int(units),
            "share_of_returns": num(units / returned_units, 4),
            "units_sold_window": num(sold, 0),
            "return_rate_pct": num(100.0 * units / sold, 2) if sold > 0 else None,
        })
    assumptions = [
        "Loss fractions of sale price per returned unit: SELLABLE 20% (refund processing + return "
        "shipping, unit resold); DAMAGED / CUSTOMER_DAMAGED / DEFECTIVE / EXPIRED / CARRIER_DAMAGED "
        "100% (unit written off); any other disposition 60%",
        "Return rate = returned units / units sold over the sku_economics periods the returns report "
        "overlaps; the returns report is assumed to cover those periods fully",
        "Exposure = units sold in the latest sku_economics period (all SKUs); next period assumed similar",
        f"Severity sampling: {reserve['method']} over {reserve['n_severities']} costed returned units",
    ]
    if not overlap:
        assumptions.append("Returns dates do not overlap the sku_economics periods — rate uses all returns "
                           "over all units sold; treat as rough")
    if unpriced:
        assumptions.append(f"{unpriced} returned unit(s) belong to SKUs with no sale price on file — "
                           "costed at the catalog average price")
    return {
        **reserve,
        "return_rate_pct": num(100.0 * lam, 2),
        "returned_units": int(returned_units),
        "units_sold_window": num(units_window, 0),
        "returns_window": {
            "start": window[0][0], "end": window[-1][1], "periods": len(window),
            "overlap_with_economics": overlap,
        },
        "by_disposition": {
            d: {"units": int(u), "loss_fraction": RETURN_LOSS_FRACTION.get(d, RETURN_LOSS_FRACTION_UNKNOWN)}
            for d, u in by_disposition.most_common()
        },
        "by_sku": by_sku,
        "loss_fractions": {**RETURN_LOSS_FRACTION, "UNKNOWN": RETURN_LOSS_FRACTION_UNKNOWN},
        "basis": basis,
        "assumptions": assumptions,
    }


def _survival_section(margin_rows: list[dict]) -> dict:
    periods = sorted({(m["period_start"], m["period_end"]) for m in margin_rows})
    n_periods = len(periods)
    index = {p: i for i, p in enumerate(periods)}
    units: dict[str, list[float]] = defaultdict(lambda: [0.0] * n_periods)
    rates: dict[str, list[float]] = defaultdict(lambda: [0.0] * n_periods)
    for m in margin_rows:
        i = index[(m["period_start"], m["period_end"])]
        u = float(m.get("units") or 0)
        units[m["sku"]][i] = u
        rates[m["sku"]][i] = u / period_days(m["period_start"], m["period_end"])
    sold = {sku: u for sku, u in units.items() if any(x > 0 for x in u)}
    basis = (f"Kaplan–Meier on SKU lifetimes in catalog periods; death = no units in the last "
             f"{DEATH_ZERO_PERIODS} periods after having sold; still-selling SKUs are right-censored")
    if n_periods < SURVIVAL_MIN_PERIODS or len(sold) < SURVIVAL_MIN_SKUS:
        return _insufficient(
            f"{len(sold)} SKU(s) over {n_periods} period(s); need {SURVIVAL_MIN_SKUS} SKUs and "
            f"{SURVIVAL_MIN_PERIODS} periods", basis=basis, n=len(sold), periods=n_periods)

    durations, observed, dead, declining = [], [], [], []
    cutoff = n_periods - DECLINE_RECENT_PERIODS
    for sku, u in sorted(sold.items()):
        first = min(i for i, x in enumerate(u) if x > 0)
        last = max(i for i, x in enumerate(u) if x > 0)
        is_dead = last < n_periods - DEATH_ZERO_PERIODS
        durations.append((last - first + 1) if is_dead else (n_periods - first))
        observed.append(is_dead)
        if is_dead:
            dead.append({"sku": sku, "last_period": periods[last][0], "periods_alive": last - first + 1})
            continue
        if first < cutoff:
            prior = float(np.mean(rates[sku][first:cutoff]))
            recent = float(np.mean(rates[sku][cutoff:]))
            if prior > 0 and recent < DECLINE_THRESHOLD * prior:
                declining.append({
                    "sku": sku,
                    "prior_rate": num(prior, 4),
                    "recent_rate": num(recent, 4),
                    "drop_pct": num(100.0 * (prior - recent) / prior, 1),
                })
    declining.sort(key=lambda r: -(r["drop_pct"] or 0))
    km = kaplan_meier(durations, observed)
    return {
        **km,
        "censored": int(km["n"] - km["events"]),
        "periods": n_periods,
        "period_days_typical": int(np.median([period_days(s, e) for s, e in periods])),
        "dead": dead,
        "declining": declining,
        "basis": basis,
        "assumptions": [
            "Duration = catalog periods from a SKU's first sale to its last (dead) or to the catalog's "
            "end (censored); t is in periods, not days",
            f"Declining = last-{DECLINE_RECENT_PERIODS}-period mean daily rate below "
            f"{int(DECLINE_THRESHOLD * 100)}% of the SKU's earlier mean — a hazard flag, not a Cox model",
            "Median lifetime is None when more than half the catalog is still alive at the end of the data",
        ],
    }


def run(data: dict, margin_rows: list[dict], forecast_rows: list[dict] | None = None,
        inventory_rows: list[dict] | None = None, ads_rows: list[dict] | None = None,
        rng: np.random.Generator | None = None, simulations: int = DEFAULT_PATHS) -> dict:
    """Five independent sections, each tolerant of missing inputs.

    `margin_rows` are margin.run() rows; `forecast_rows` (optional) carry
    {item_id, daily_rate_point, details.error_sd} and take precedence over
    observed rates in the VaR simulation. `inventory_rows` and `ads_rows`
    are accepted for integrator uniformity and unused in v1. The top-level
    status is "ok" when at least one section produced a finding.
    """
    rng = np.random.default_rng(42) if rng is None else rng
    n_paths = int(simulations or DEFAULT_PATHS)
    margin_rows = margin_rows or []
    sections = {
        "var": _var_section(margin_rows, forecast_rows, rng, n_paths),
        "concentration": _concentration_section(data, margin_rows),
        "credibility": _credibility_section(margin_rows),
        "returns_reserve": _returns_section(data, rng, n_paths),
        "survival": _survival_section(margin_rows),
    }
    status = "ok" if any(s["status"] == "ok" for s in sections.values()) else "insufficient_data"
    return {"status": status, **sections}
