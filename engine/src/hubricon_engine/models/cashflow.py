"""Cash-flow horizon: Monte Carlo value-at-risk on the client's cash position.

The flashy version of this model reaches for Geometric Brownian Motion.
We deliberately don't: GBM describes compounding asset prices, not unit
demand. Daily demand here uses the same generator the inventory simulation
is validated on (rate-uncertain Poisson), so the cash cone and the stockout
numbers can never disagree about what demand is.

Cash mechanics per simulated path over the horizon:

    in  — the platform disburses every payout_cycle_days: the accumulated
          (revenue − fees − ad spend) since the previous payout. Amazon
          settles fortnightly and the client's actual settlement phase is
          unknown, so payouts land on days 14, 28, …; Shopify Payments pays
          out daily. Either way the cycle and the assumption behind it come
          from channels.py and are surfaced in the payload.
    out — fixed operating costs accrue daily (monthly_fixed_costs / 30);
          supplier POs leave as lump-sum wires on their scheduled dates.

The wire schedule is derived from the same inventory results the reorder
directives use: the first wire when the position walks down to the reorder
point, then a steady-state cycle every reorder_qty / velocity days. COGS
never hits cash per-sale — inventory already on hand was paid for; future
inventory is paid for by exactly these wires.

Demand shares a common factor across SKUs (models/dependence.py). Drawing each
SKU's demand independently was the single most expensive assumption in this
model: the cone is an AGGREGATE of forty or four hundred SKUs, and independent
draws let their good and bad months cancel almost perfectly, so the 5th
percentile of the cash path came out far too comfortable. A seller deciding
whether they need bridge capital was reading the wrong number.

The trough is reported with its EXPECTED SHORTFALL, not only its 5th percentile.
A percentile is a threshold, not a risk measure — it says nothing about whether
the 1% case is a little worse or catastrophically worse, and it is not
sub-additive, so percentiles of parts do not bound the percentile of the whole
(Artzner et al. 1999; Rockafellar & Uryasev 2000). The mean of the worst
twentieth of troughs is the number a runway decision needs. Every published
percentile also carries its Monte Carlo standard error, because a P5 read off
10,000 paths is an estimate and the seller is entitled to know how firm it is.

Ruin here means the simulated account balance crossing zero — or, since
2026-09-23, the minimum cash buffer the client states — an honest "you would
need bridge capital" line, never a bankruptcy prophecy.
"""

import numpy as np

from .. import channels
from . import dependence
from .common import num, period_days
from .mc import expected_shortfall, quantile_se

PAYOUT_CYCLE_DAYS = channels.PAYOUT_CYCLE_DAYS["amazon"]  # the default; 14 days
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


def _rate_panel(margin_rows: list[dict]) -> dict[str, list[float]]:
    """{sku: [daily rate per shared period]} from the margin rows — the panel the
    catalog's demand correlation is estimated on. Only periods every SKU has are
    used, because a cross-sectional correlation needs a rectangle."""
    per_sku: dict[str, dict[str, float]] = {}
    for m in margin_rows or []:
        units = m.get("units")
        if units is None or float(units) <= 0:
            continue
        days = period_days(str(m["period_start"]), str(m["period_end"]))
        per_sku.setdefault(m["sku"], {})[str(m["period_start"])] = float(units) / days
    if not per_sku:
        return {}
    shared = set.intersection(*(set(v) for v in per_sku.values()))
    if len(shared) < dependence.MIN_PANEL_PERIODS:
        return {}
    order = sorted(shared)
    return {sku: [v[p] for p in order] for sku, v in per_sku.items()}


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
             n_paths: int = DEFAULT_PATHS,
             payout_cycle_days: int = PAYOUT_CYCLE_DAYS,
             payout_note: str | None = None,
             correlation: dict | None = None,
             index_paths: list[np.ndarray] | None = None,
             ruin_floor: float = 0.0, keep_paths: bool = False, top_k: int = 3) -> dict:
    """The cone. Returns a JSON-safe payload with daily p5/p50/p95 cash
    paths (day 0 = today = starting cash), ruin probability, and the
    schedule that produced it.

    payout_cycle_days and payout_note are the platform's disbursement
    mechanics and the sentence that explains them — a number and a label, so
    the simulation itself stays channel-blind. run() takes them from
    channels.py; the defaults are Amazon's."""
    days = horizon_days
    payout_cycle_days = max(1, int(payout_cycle_days))
    correlation = correlation or dependence.estimate_pairwise_corr({})
    rho = float(correlation.get("rho") or 0.0)

    # Every SKU's rate for a given (path, day) shares one common factor, so a bad
    # day is bad across the catalog rather than averaging out. Streamed one SKU at
    # a time: the whole (n_skus, n_paths, days) array is 2.9 GB on a 400-SKU
    # catalog, and nothing needs it at once.
    sales_net = np.zeros((n_paths, days))
    revenue = np.zeros((n_paths, days)) if keep_paths else None
    # the largest SKUs by revenue rate, kept apart so a stress scenario can
    # suppress or delay one of them without re-simulating anything
    by_size = sorted(range(len(params)), key=lambda i: -params[i]["mean_rate"] * params[i]["price"])[:top_k]
    top_paths = {i: None for i in by_size} if keep_paths else {}
    for i, rates in dependence.rate_stream(
            rng, [p["mean_rate"] for p in params], [p["std_rate"] for p in params],
            (n_paths, days), rho):
        if index_paths is not None:
            # the seasonal index per calendar day, the same for every path
            rates = rates * np.asarray(index_paths[i], dtype=float)[None, :days]
        units = rng.poisson(rates)
        net_i = units * params[i]["price"] * (1 - params[i]["fee_rate"])
        sales_net += net_i
        if keep_paths:
            revenue += units * params[i]["price"]
            if i in top_paths:
                top_paths[i] = net_i
    ad_daily_total = float(sum(p["ad_daily"] for p in params))

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
    payout_days = list(range(payout_cycle_days - 1, days, payout_cycle_days))
    for k in payout_days:
        paid[:, k:] = cum_net[:, k][:, None]
    cash = starting_cash - np.cumsum(outflow)[None, :] + paid

    p5, p50, p95 = (np.quantile(cash, q, axis=0) for q in (0.05, 0.50, 0.95))
    # ruin is the balance crossing the client's stated buffer, zero by default
    ruined = (cash.min(axis=1) < float(ruin_floor)).mean()
    min_p5_day = int(np.argmin(p5))

    # The trough of each path, and the tail mean of those troughs. This is the
    # number a runway decision is made on: not "the 5th-worst month in a
    # hundred" but "how deep does it get once you are in that fifth percentile".
    trough = cash.min(axis=1)
    trough_tail = expected_shortfall(trough, 0.05, tail="lower")
    ruin_se = float(np.sqrt(max(0.0, ruined * (1 - ruined)) / n_paths))
    ladder = ruin_ladder(cash, float(ruin_floor))
    paths = None
    if keep_paths:
        paths = {"sales_net": sales_net, "revenue": revenue, "outflow": outflow, "ad_daily_total": ad_daily_total,
                 "payout_days": payout_days, "starting_cash": float(starting_cash), "ruin_floor": float(ruin_floor),
                 "top": {params[i]["sku"]: {"sales_net": v, "days_of_cover": None} for i, v in top_paths.items()},
                 "n_paths": n_paths, "days": days}
    out = {
        "horizon_days": days,
        "n_paths": n_paths,
        "starting_cash": num(starting_cash),
        "monthly_fixed_costs": num(monthly_fixed_costs),
        "p_ruin": num(float(ruined), 4),
        "p_ruin_mc_se": num(ruin_se, 5),
        "min_p5": num(float(p5[min_p5_day])),
        "min_p5_day": min_p5_day + 1,
        "min_median": num(float(p50.min())),
        # the coherent pair: the familiar percentile, and the tail mean behind it
        "trough_p5": num(trough_tail["threshold"]),
        "trough_expected_shortfall": num(trough_tail["shortfall"]),
        "trough_expected_shortfall_se": num(trough_tail["se"], 3),
        "trough_median": num(float(np.median(trough))),
        "details": {
            "p5": [num(float(v)) for v in p5],
            "p50": [num(float(v)) for v in p50],
            "p95": [num(float(v)) for v in p95],
            # the error bar on every published percentile, at the trough day —
            # where the cone is read and where the decision is made
            "mc_se_at_trough": {
                "p5": num(quantile_se(cash[:, min_p5_day], 0.05), 2),
                "p50": num(quantile_se(cash[:, min_p5_day], 0.50), 2),
                "p95": num(quantile_se(cash[:, min_p5_day], 0.95), 2),
            },
            "demand_correlation": correlation,
            "wires": wires,
            "payout_days": [d + 1 for d in payout_days],
            "payout_cycle_days": payout_cycle_days,
            "skus_modeled": len(params),
            "seasonal": "index applied per calendar day" if index_paths is not None else "flat rate",
            "ruin_floor": num(float(ruin_floor)),
            "ruin_floor_basis": "client-stated minimum cash buffer" if ruin_floor else "zero (no buffer stated)",
            # what a wire on day d would do to the ruin probability, without
            # re-running the cone: see ruin_ladder / ruin_delta
            "ruin_ladder": ladder,
            "assumptions": [
                payout_note or channels.payout_note("amazon"),
                ("Demand follows the catalog's seasonal index by calendar day" if index_paths is not None
                 else "Demand rate is flat over the horizon (no seasonal estimate on file)"),
                f"Fixed costs accrue daily (monthly / {OPEX_DAYS_PER_MONTH}); real due dates may be lumpier",
                "Cash on hand and monthly fixed costs are client-stated, not modeled",
                "Demand generator identical to the inventory simulation "
                "(lognormal rate, Poisson counts)",
                f"Demand shares a common factor across SKUs: pairwise log-demand "
                f"correlation {correlation.get('pairwise_corr')}, "
                + ("measured from this catalog's own history"
                   if correlation.get("basis") == "estimated"
                   else "a conservative default — the history is too thin to measure one"),
                "The trough is reported with its expected shortfall (the mean of the "
                "worst 5% of troughs), not only its 5th percentile",
            ],
        },
    }
    if keep_paths:
        # numpy arrays for the stress pass; never persisted — the caller pops it
        out["_paths"] = paths
    return out


LADDER_QUANTILES = 101


def ruin_ladder(cash: np.ndarray, floor: float = 0.0) -> dict:
    """Enough of the simulated paths to price any later cash decision.

    A wire of W on day d lowers every path by W from d on, so a path is ruined
    afterwards when its minimum before d is under the floor, or its minimum
    from d on is under floor + W. Per day the ladder keeps P(pre-minimum under
    the floor) and the quantiles of the post-minimum among the paths still
    above it — a few thousand numbers, from which ruin_delta reads
    P(ruin | W on day d) exactly up to the quantile grid, for any W, with no
    second simulation."""
    n_paths, days = cash.shape
    qs = np.linspace(0.0, 1.0, LADDER_QUANTILES)
    pre_p, post_q, post_p5 = [], [], []
    running_min = np.minimum.accumulate(cash, axis=1)
    suffix_min = np.minimum.accumulate(cash[:, ::-1], axis=1)[:, ::-1]
    for d in range(days):
        pre_ok = running_min[:, d - 1] >= floor if d > 0 else np.ones(n_paths, dtype=bool)
        pre_p.append(float(1.0 - pre_ok.mean()))
        post = suffix_min[pre_ok, d] if pre_ok.any() else np.array([floor])
        post_q.append([num(float(v)) for v in np.quantile(post, qs)])
        post_p5.append(num(float(np.quantile(suffix_min[:, d], 0.05))))
    return {"days": days, "floor": num(floor), "quantiles": LADDER_QUANTILES, "p_pre": [num(v, 5) for v in pre_p],
            "post_min_q": post_q, "post_min_p5": post_p5, "n_paths": int(n_paths)}


def ruin_delta(cash_payload: dict | None, day: int, amount: float) -> dict | None:
    """P(ruin) before and after a cash movement of `amount` on `day` (positive
    = out, negative = in), from the ladder the cone stored. None without a cone."""
    ladder = ((cash_payload or {}).get("details") or {}).get("ruin_ladder")
    if not ladder or not ladder.get("post_min_q"):
        return None
    d = int(max(0, min(day, ladder["days"] - 1)))
    floor = float(ladder["floor"] or 0.0)
    p_pre = float(ladder["p_pre"][d])
    q = np.array(ladder["post_min_q"][d], dtype=float)
    grid = np.linspace(0.0, 1.0, len(q))
    threshold = floor + float(amount)

    def cdf(x):
        # share of the surviving paths whose post-minimum is under x
        return float(np.interp(x, q, grid, left=0.0, right=1.0))
    before = p_pre + (1 - p_pre) * cdf(floor)
    after = p_pre + (1 - p_pre) * cdf(threshold)
    n = int(ladder.get("n_paths") or 10000)
    return {"day": d, "amount": round(float(amount), 2),
            "p_ruin_before": num(before, 4), "p_ruin_after": num(after, 4),
            "p_ruin_delta": num(after - before, 4),
            "mc_se": num(float(np.sqrt(max(after * (1 - after), 1e-12) / n)), 5),
            "trough_p5_after": num(float(ladder["post_min_p5"][d] or 0.0) - float(amount)),
            "ruin_floor": num(floor),
            "basis": "read off the cone's stored path minima: the wire lowers every path from its day on"}


def cash_from_components(paths: dict, sales_net: np.ndarray, ad_daily_total: float, outflow: np.ndarray,
                         payout_days: list[int], payout_shift: int = 0) -> np.ndarray:
    """Rebuild the cash matrix from its components — the same arithmetic as
    simulate, exposed so a stress scenario can change one component and
    recompute the rest without drawing a single new number."""
    n_paths, days = sales_net.shape
    net_daily = sales_net - ad_daily_total
    cum_net = np.cumsum(net_daily, axis=1)
    paid = np.zeros((n_paths, days))
    for k in payout_days:
        land = k + payout_shift
        if land < days:
            paid[:, land:] = cum_net[:, k][:, None]
    return paths["starting_cash"] - np.cumsum(outflow)[None, :] + paid


def run(client: dict, inventory_rows: list[dict], margin_rows: list[dict],
        rng: np.random.Generator, horizon_days: int = DEFAULT_HORIZON_DAYS,
        n_paths: int = DEFAULT_PATHS, channel: str | None = None,
        seasonal: dict | None = None, today=None, keep_paths: bool = False) -> dict | None:
    """None when the client hasn't stated cash inputs or there's no revenue
    machinery to simulate — the caller reports the skip, never fakes it.

    channel is the platform the run was computed on; None means "read it off
    the client", which is right for every single-platform client and falls
    back to Amazon for a client selling on both (the caller then passes each
    channel explicitly)."""
    cash_on_hand = client.get("cash_on_hand")
    opex = client.get("monthly_fixed_costs")
    if cash_on_hand is None or opex is None:
        return None
    params = sku_cash_params(inventory_rows, margin_rows)
    if not params:
        return None
    channel = channel or channels.client_channel(client) or "amazon"
    wires = wire_schedule(inventory_rows, margin_rows, horizon_days)
    correlation = dependence.estimate_pairwise_corr(_rate_panel(margin_rows))
    index_paths = None
    if seasonal and seasonal.get("status") == "ok":
        from datetime import date as _date
        from .seasonality import daily_path
        start = today or _date.today()
        index_paths = [daily_path(seasonal, p["sku"], start, horizon_days) for p in params]
    out = simulate(params, wires, float(cash_on_hand), float(opex), rng,
                   horizon_days=horizon_days, n_paths=n_paths,
                   payout_cycle_days=channels.payout_cycle_days(channel),
                   payout_note=channels.payout_note(channel),
                   correlation=correlation, index_paths=index_paths,
                   ruin_floor=float(client.get("min_cash_buffer_usd") or 0.0), keep_paths=keep_paths)
    if keep_paths and out.get("_paths"):
        cover = {r["sku"]: float(r.get("days_of_cover") or 0) for r in inventory_rows}
        for sku, t in out["_paths"]["top"].items():
            t["days_of_cover"] = cover.get(sku)
    return out
