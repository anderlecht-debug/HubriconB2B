"""The month after the sweep, simulated FROM THE TRUTH, with every directive
executed as written: prices moved, campaigns re-budgeted and trimmed, wasted
search terms negated. Then the truth of each promise, computed from the
generator's own parameters — the quantity the promise is about, never a
figure the engine produced.

  price step   this SKU's profit change from its own move plus its siblings'
               change from that move, every other price at its after value,
               every SKU at its realised September demand shock
  half step    the same at half the move (the over-betting check)
  reallocation 30 days of margin on the true curves, less the spend moved
  trim         30 days of spend saved less the margin the true curve loses
  bleed        30 days of spend on terms that sold nothing
  reorder      the expected newsvendor cost of the engine's order-up-to level
               under the TRUE demand over the cycle (the after price, the
               season ahead, the persistent shock, a lead time that varies by
               20%), against the true optimum at the engine's own critical
               fractile — the cost parameters are accounting, the demand is
               the estimate under test
"""
from datetime import date, timedelta

import numpy as np

from hubricon_engine.models import ad_efficiency

from .worlds import FBA, FEE, FREIGHT, STORAGE, TODAY, hill, season_factor

AFTER_START, AFTER_END = "2026-09-02", "2026-09-29"
LEAD_TIME_CV_TRUE = 0.20
INVENTORY_PATHS = 4000


def simulate(data: dict, truth: dict, out: dict, seed: int) -> dict:
    rng = np.random.default_rng([seed, 7])
    prm = truth["params"]
    rho, sd = prm["rho"], prm["demand_sd"]
    fee = FEE + prm["fee_shock"]
    skus = truth["skus"]
    latest = max(m["period_start"] for m in out["margins"])
    last_rows = {m["sku"]: m for m in out["margins"] if m["period_start"] == latest and float(m.get("units") or 0) > 0}

    steps = {}
    for d in out["drafts"]:
        if d["kind"] in ("price_step", "markdown") and d["evidence"].get("p_new"):
            steps[d["evidence"]["sku"]] = float(d["evidence"]["p_new"])
    price_now = {s: float(m["revenue"]) / float(m["units"]) for s, m in last_rows.items()}
    for s, t in skus.items():
        price_now.setdefault(s, t["p_last"])
    after_price = {s: steps.get(s, price_now[s]) for s in skus}
    shock = {s: rho * t["shock_last"] + rng.normal(0, sd * np.sqrt(1 - rho**2)) for s, t in skus.items()}
    sea = season_factor(9, prm["season"])
    family = {}
    for s, t in skus.items():
        family.setdefault(t["family"], []).append(s)

    def units(s, prices):
        t = skus[s]
        sibs = [j for j in family[t["family"]] if j != s]
        idx = float(np.mean([np.log(prices[j] / skus[j]["p0"]) for j in sibs])) if sibs else 0.0
        return (t["base"] * 28 * (prices[s] / t["p0"]) ** t["eps_after"] * np.exp(truth["families"][t["family"]] * idx)
                * sea * np.exp(shock[s]))

    def contrib(s, p):
        return p * (1 - fee) - skus[s]["cost"] - FREIGHT - FBA - STORAGE

    def family_profit(s, prices):
        return sum(units(j, prices) * contrib(j, prices[j]) for j in family[skus[s]["family"]])

    def move_value(s, p_new, p_old):
        hi, lo = dict(after_price), dict(after_price)
        hi[s], lo[s] = p_new, p_old
        return family_profit(s, hi) - family_profit(s, lo)

    after_margins, step_truth = [], {}
    for s, m in last_rows.items():
        q = units(s, after_price)
        p1 = after_price[s]
        cogs = None if m.get("cogs") is None else (skus[s]["cost"] + FREIGHT) * q
        after_margins.append({**m, "period_start": AFTER_START, "period_end": AFTER_END, "units": q,
                              "revenue": q * p1, "amazon_fees": q * p1 * fee + (FBA + STORAGE) * q, "cogs": cogs,
                              "fee_split": {"basis": "itemized", "proportional_rate": fee,
                                            "fixed_per_unit": FBA + STORAGE, "proportional_fees": q * p1 * fee,
                                            "fixed_fees": (FBA + STORAGE) * q}})
        if s in steps:
            p_old = price_now[s]
            step_truth[s] = {"full": move_value(s, p1, p_old),
                             "half": move_value(s, p_old + 0.5 * (p1 - p_old), p_old),
                             "p_old": p_old, "p_new": p1}

    # ── advertising ──
    avg_m = float(out["avg_margin"])
    moves, realloc = {}, None
    trims = {}
    for d in out["drafts"]:
        if d["kind"] == "budget_reallocation":
            realloc = d
            for c in d["evidence"]["campaigns"]:
                if c.get("status") == "ok":
                    moves[c["campaign_name"]] = float(c["recommended"])
        if d["kind"] == "campaign_trim":
            moves[d["evidence"]["campaign_name"]] = float(d["evidence"]["breakeven_used"])
            trims[d["evidence"]["campaign_name"]] = d
    bled = {}
    bleed_truth = 0.0
    for d in out["drafts"]:
        if d["kind"] == "ad_bleed_terms":
            for t in d["evidence"]["terms"]:
                row = next((x for x in data["ppc_search_terms"] if x["campaign_name"] == t["campaign_name"]
                            and x["search_term"] == t["search_term"]), None)
                if row is not None and float(row.get("sales_7d") or 0) == 0:
                    bled[t["campaign_name"]] = bled.get(t["campaign_name"], 0.0) + float(row["spend"]) / 28.0
    bleed_truth = 30.0 * sum(bled.values())
    broken_factor = {name: (0.7 if prm["cpc_break"] and name == "Camp0" else 1.0) for name in truth["campaigns"]}

    def true_sales(name, s):
        c = truth["campaigns"][name]
        return hill(s, c["a"], c["k"], c["h"]) * broken_factor[name]

    after_ppc, camp = [], {}
    for name, c in truth["campaigns"].items():
        before = float(np.mean([p["spend"] for p in data["ppc_spend"] if p["campaign_name"] == name
                                and p["report_date"] >= (TODAY - timedelta(days=30)).isoformat()]))
        # the negated terms were a fixed daily amount with no sales: the
        # campaign keeps its blended-spend curve, and a target set on it is
        # met by spending the target less the waste (floored at a tenth)
        target = moves.get(name, before)
        waste = bled.get(name, 0.0)
        spend = max(0.1 * target, target - waste)
        camp[name] = {"before": before, "target": target, "spend_after": spend, "waste": waste}
        for dd in range(28):
            day = (TODAY + timedelta(days=dd + 1)).isoformat()
            after_ppc.append({"campaign_name": name, "campaign_id": name, "report_date": day, "spend": spend,
                              "sales": max(0.0, true_sales(name, spend + waste) + rng.normal(0, 12)),
                              "clicks": spend / 1.1, "impressions": spend * 40})
    realloc_truth = None
    if realloc is not None:
        gain = 0.0
        for c in realloc["evidence"]["campaigns"]:
            if c.get("status") != "ok":
                continue
            name = c["campaign_name"]
            cur = float(c["current"])
            eff = camp[name]["spend_after"] + camp[name]["waste"]   # the blended spend actually reached
            gain += avg_m * (true_sales(name, eff) - true_sales(name, cur)) - (eff - cur)
        realloc_truth = 30.0 * gain
    trim_truth = {}
    for name, d in trims.items():
        cur = float(d["evidence"]["current_spend"])
        new = camp[name]["spend_after"] + camp[name]["waste"]
        trim_truth[name] = 30.0 * ((cur - new) - avg_m * (true_sales(name, cur) - true_sales(name, new)))
    negated = {(x["campaign_name"], x["search_term"]) for d in out["drafts"] if d["kind"] == "ad_bleed_terms"
               for x in d["evidence"]["terms"]}
    after_terms = [{**t, "spend": 0.0 if (t["campaign_name"], t["search_term"]) in negated else t["spend"],
                    "period_start": AFTER_START, "period_end": AFTER_END} for t in data["ppc_search_terms"]]
    after_data = {**data, "ppc_spend": data["ppc_spend"] + after_ppc,
                  "ppc_search_terms": data["ppc_search_terms"] + after_terms}
    ads_after = ad_efficiency.run({**data, "ppc_spend": after_ppc}, avg_margin=avg_m)

    return {"after_data": after_data, "after_margins": after_margins, "ads_after": ads_after,
            "step_truth": step_truth, "realloc_truth": realloc_truth, "trim_truth": trim_truth,
            "bleed_truth": bleed_truth, "campaigns": camp,
            "inventory": inventory_truth(out, truth, after_price, shock, rng)}


def inventory_truth(out: dict, truth: dict, after_price: dict, shock: dict, rng) -> dict:
    """Expected newsvendor cost at the engine's order-up-to level against the
    true optimum, SKU by SKU, under the true demand over the cycle."""
    prm = truth["params"]
    rho, sd = prm["rho"], prm["demand_sd"]
    skus = truth["skus"]
    family = {}
    for s, t in skus.items():
        family.setdefault(t["family"], []).append(s)
    rows = []
    for r in (out["ie"].get("rows") or []):
        if r.get("status") != "ok" or r.get("order_up_to") is None or r.get("c_u") is None:
            continue
        s = r["sku"]
        t = skus.get(s)
        if t is None:
            continue
        sibs = [j for j in family[t["family"]] if j != s]
        idx = float(np.mean([np.log(after_price[j] / skus[j]["p0"]) for j in sibs])) if sibs else 0.0
        level = (t["base"] * (after_price[s] / t["p0"]) ** t["eps_after"]
                 * np.exp(truth["families"][t["family"]] * idx))
        lead = float(r["lead_time_days"]) * np.exp(rng.normal(-0.5 * LEAD_TIME_CV_TRUE**2, LEAD_TIME_CV_TRUE,
                                                              INVENTORY_PATHS))
        horizon = lead + float(r.get("review_days") or 7)
        max_days = int(np.ceil(horizon.max())) + 1
        # monthly AR(1) shocks from the LAST OBSERVED month's, as they stand when
        # the order is placed on the first of September: the oracle knows the
        # model and every parameter, never the future (September's shock was
        # a known number here until 2026-09-24, an optimum no one could reach)
        months = [(TODAY + timedelta(days=d)).month for d in range(max_days)]
        month_keys = sorted(set((TODAY + timedelta(days=d)).strftime("%Y-%m") for d in range(max_days)))
        sh = np.zeros((INVENTORY_PATHS, len(month_keys)))
        sh[:, 0] = rho * t["shock_last"] + rng.normal(0, sd * np.sqrt(1 - rho**2), INVENTORY_PATHS)
        for k in range(1, len(month_keys)):
            sh[:, k] = rho * sh[:, k - 1] + rng.normal(0, sd * np.sqrt(1 - rho**2), INVENTORY_PATHS)
        day_month = [month_keys.index((TODAY + timedelta(days=d)).strftime("%Y-%m")) for d in range(max_days)]
        daily = np.array([season_factor(months[d], prm["season"]) for d in range(max_days)])
        rate = level * daily[None, :] * np.exp(sh[:, day_month])
        cum = np.cumsum(rate, axis=1)
        whole = np.floor(horizon).astype(int)
        frac = horizon - whole
        mean_d = cum[np.arange(INVENTORY_PATHS), whole - 1] + frac * rate[np.arange(INVENTORY_PATHS), whole]
        demand = rng.poisson(mean_d)
        q = float(r["critical_fractile"])
        c_u, c_o = float(r["c_u"]), float(r["c_o"])
        position = float(r.get("position") or 0)

        def cost(level_):
            return float(c_u * np.maximum(demand - level_, 0).mean() + c_o * np.maximum(level_ - demand, 0).mean())
        s_eng = max(float(r["order_up_to"]), position)
        s_opt = max(float(np.quantile(demand, q)), position)
        rows.append({"sku": s, "cost_engine": cost(s_eng), "cost_optimal": cost(s_opt),
                     "s_engine": s_eng, "s_optimal": s_opt, "position": position,
                     "orders": float(r["order_up_to"]) > position})
    ordering = [x for x in rows if x["orders"] or x["s_optimal"] > x["position"]]
    ce = sum(x["cost_engine"] for x in ordering)
    co = sum(x["cost_optimal"] for x in ordering)
    # the criterion asks whether orders are BIGGER than the evidence pays for:
    # the excess cost of ordering above the optimum, under-ordering apart
    over = sum(x["cost_engine"] - x["cost_optimal"] for x in ordering if x["s_engine"] > x["s_optimal"])
    under = sum(x["cost_engine"] - x["cost_optimal"] for x in ordering if x["s_engine"] < x["s_optimal"])
    return {"n": len(ordering), "cost_engine": ce, "cost_optimal": co,
            "excess": (ce / co - 1.0) if co > 0 else None,
            "over_excess": (over / co) if co > 0 else None, "under_excess": (under / co) if co > 0 else None,
            "rows": ordering}
