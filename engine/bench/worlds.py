"""Six worlds with a planted truth. Each is a catalogue of SKUs in variant
families, a year of monthly exports, eight ad campaigns, a supplier sheet,
inventory and a settlement file — and a private truth the engine never sees.

  clean     exogenous prices, persistent demand (rho 0.6), a 1.6x fourth
            quarter: the engine's own assumptions hold
  reactive  the seller reprices off last month's demand (phi 0.4)
  drifting  phi 0.2; every SKU's true elasticity moves by N(0, 0.6^2) between
            the fit and the promise; a cost-per-click break under one
            campaign; referral fees up three points in the month after
  thin      seven months of history, demand noise 0.35, price noise 0.04,
            persistence 0.3: a first upload from a small seller
  dirty     the clean world with the pathologies real exports carry:
            stockout months (the seller raised the price as stock ran out,
            and the Buy Box share fell with it), deal months (a 15% cut with
            a placement lift the price does not explain, visible as
            promotional rebates in the settlement file), duplicated rows,
            SKUs with no landed cost, a month exported as two half-months
  optimal   every SKU already sits at its true profit-maximising price and
            no family cross effect exists: there is no edge in price at all

A world is a pure function of (name, seed).
"""
from datetime import date, timedelta

import numpy as np

TODAY = date(2026, 9, 1)
FEE, FBA, STORAGE, FREIGHT = 0.15, 3.0, 0.15, 0.5

WORLDS = {
    "clean": dict(phi=0.0),
    "reactive": dict(phi=0.4),
    "drifting": dict(phi=0.2, eps_drift_sd=0.6, cpc_break=True, fee_shock=0.03),
    "thin": dict(n_periods=7, demand_sd=0.35, price_noise=0.04, rho=0.3),
    "dirty": dict(dirty=True),
    "optimal": dict(optimal=True),
}
WORLD_OFFSET = {name: i + 1 for i, name in enumerate(WORLDS)}

CLIENT = {"id": "c-bench", "company_name": "Bench Co", "cash_on_hand": 60000.0, "monthly_fixed_costs": 20000.0,
          "brand_terms": "acme"}


def period(i: int, n_periods: int) -> tuple[str, str]:
    """Periods end in August 2026, so the month after is September 2026."""
    k = i - n_periods + 20
    y, m = 2025 + (k - 1) // 12, (k - 1) % 12 + 1
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-28"


def season_factor(month: int, season: float) -> float:
    sea = season if month in (10, 11, 12) else 1.0
    return sea / ((3 * season + 9) / 12)


def hill(s, a, k, h):
    return a * s**h / (k**h + s**h)


def optimal_price(eps: float, landed: float, fixed: float, fee: float) -> float:
    """argmax_p p^eps (p(1-f) - c - F) for eps < -1."""
    return eps * (landed + fixed) / ((1 + eps) * (1 - fee))


def make_world(name: str, seed: int, n_skus: int = 160, n_periods: int = 12, n_campaigns: int = 8,
               phi: float = 0.0, rho: float = 0.6, season: float = 1.6, eps_drift_sd: float = 0.0,
               cpc_break: bool = False, fee_shock: float = 0.0, demand_sd: float = 0.20,
               price_noise: float = 0.06, optimal: bool = False, dirty: bool = False):
    rng = np.random.default_rng([seed, WORLD_OFFSET[name]])
    params = dict(phi=phi, rho=rho, season=season, eps_drift_sd=eps_drift_sd, cpc_break=cpc_break,
                  fee_shock=fee_shock, demand_sd=demand_sd, price_noise=price_noise, n_periods=n_periods,
                  optimal=optimal, dirty=dirty)
    truth = {"world": name, "seed": seed, "params": params, "skus": {}, "campaigns": {}, "families": {},
             "pathologies": {"stockout": {}, "deal": {}, "duplicate": [], "no_cogs": [], "short_period": []}}
    n_fam = n_skus // 4
    truth["families"] = {f"P{f:03d}": (0.0 if optimal else float(rng.uniform(0.3, 1.2))) for f in range(n_fam)}

    # ── the pathologies are chosen before any number is drawn for them ──
    order = rng.permutation(n_skus)
    stockout_skus = set(order[: int(0.15 * n_skus)]) if dirty else set()
    deal_skus = set(order[int(0.15 * n_skus): int(0.25 * n_skus)]) if dirty else set()
    no_cogs = set(order[int(0.25 * n_skus): int(0.30 * n_skus)]) if dirty else set()
    dup_skus = set(order[int(0.30 * n_skus): int(0.30 * n_skus) + 3]) if dirty else set()
    short_skus = set(order[int(0.30 * n_skus) + 3: int(0.30 * n_skus) + 4]) if dirty else set()

    prices, shocks, factor = {}, {}, {}
    for i in range(n_skus):
        sku = f"SKU{i:03d}"
        base = float(rng.uniform(1.5, 14.0))
        eps = float(rng.uniform(-3.2, -1.2))
        if optimal:
            cost = float(rng.uniform(4.0, 18.0))
            p0 = optimal_price(eps, cost + FREIGHT, FBA + STORAGE, FEE)
        else:
            p0 = float(rng.uniform(15, 55))
            cost = p0 * float(rng.uniform(0.25, 0.45))
        sh = np.zeros(n_periods)
        sh[0] = rng.normal(0, demand_sd)
        for t in range(1, n_periods):
            sh[t] = rho * sh[t - 1] + rng.normal(0, demand_sd * np.sqrt(1 - rho**2))
        noise = rng.normal(0, price_noise, n_periods)
        if optimal:
            noise[-1] = 0.0          # the current price IS the optimum
        pr = np.array([p0 * np.exp(noise[t] + (phi * sh[t - 1] if t else 0.0)) for t in range(n_periods)])
        f_units = np.ones(n_periods)
        if i in stockout_skus or i in deal_skus:
            k = int(rng.integers(1, n_periods - 1))      # never the first or the last month
            if i in stockout_skus:
                in_stock = float(rng.uniform(0.4, 0.7))
                pr[k] *= 1.08
                f_units[k] = in_stock
                truth["pathologies"]["stockout"][sku] = {"k": k, "in_stock": in_stock}
            else:
                pr[k] *= 0.85
                f_units[k] = 1.8
                truth["pathologies"]["deal"][sku] = {"k": k}
        prices[sku], shocks[sku], factor[sku] = pr, sh, f_units
        truth["skus"][sku] = {"base": base, "eps": eps, "p0": p0, "cost": cost, "family": f"P{i // 4:03d}",
                              "eps_after": eps + (float(rng.normal(0, eps_drift_sd)) if eps_drift_sd else 0.0),
                              "shock_last": float(sh[-1]), "p_last": float(pr[-1])}

    econ, traffic, cogs, inv, health, txns = [], [], [], [], [], []
    for i in range(n_skus):
        sku, asin, fam = f"SKU{i:03d}", f"B0{i:06d}", f"P{i // 4:03d}"
        tr = truth["skus"][sku]
        sibs = [f"SKU{j:03d}" for j in range(4 * (i // 4), 4 * (i // 4) + 4) if j != i and j < n_skus]
        rows_i = []
        for k in range(1, n_periods + 1):
            s, e = period(k, n_periods)
            month = int(s[5:7])
            p = prices[sku][k - 1]
            sib = float(np.mean([np.log(prices[j][k - 1] / truth["skus"][j]["p0"]) for j in sibs])) if sibs else 0.0
            demand = (tr["base"] * 28 * (p / tr["p0"]) ** tr["eps"] * np.exp(truth["families"][fam] * sib)
                      * season_factor(month, season) * np.exp(shocks[sku][k - 1]))
            units = demand * factor[sku][k - 1]
            in_stock = truth["pathologies"]["stockout"].get(sku, {})
            buy_box = 92.0 * (in_stock["in_stock"] if in_stock and in_stock["k"] == k - 1 else 1.0)
            sales = units * p
            row = {"sku": sku, "asin": asin, "period_start": s, "period_end": e, "units_sold": units,
                   "avg_sales_price": p, "sales": sales, "referral_fees": -FEE * sales,
                   "fba_fulfillment_fees": -FBA * units, "storage_fees": -STORAGE * units, "other_fees": 0.0,
                   "net_proceeds": sales}
            if i in short_skus and k == n_periods // 2:
                # the month exported as two half-months
                for a, b in ((1, 14), (15, 28)):
                    frac = 0.5
                    rows_i.append({**row, "period_start": f"{s[:8]}{a:02d}", "period_end": f"{s[:8]}{b:02d}",
                                   "units_sold": units * frac, "sales": sales * frac,
                                   "referral_fees": -FEE * sales * frac, "fba_fulfillment_fees": -FBA * units * frac,
                                   "storage_fees": -STORAGE * units * frac, "net_proceeds": sales * frac})
                truth["pathologies"]["short_period"].append(sku)
            else:
                rows_i.append(row)
            traffic.append({"child_asin": asin, "parent_asin": fam, "period_start": s, "period_end": e,
                            "units_ordered": units, "ordered_product_sales": sales, "sessions": demand * 12,
                            "buy_box_pct": buy_box, "unit_session_pct": 100.0 * units / max(demand * 12, 1e-9)})
            # the settlement file: four weekly order rows a month, at the list
            # price; a deal month carries its discount as promotional rebates
            deal = truth["pathologies"]["deal"].get(sku)
            is_deal = bool(deal and deal["k"] == k - 1)
            list_price = p / 0.85 if is_deal else p
            for w, day in enumerate((1, 8, 15, 22)):
                q = units / 4.0
                txns.append({"txn_datetime": f"{s[:8]}{day:02d}T10:00:00", "txn_date": f"{s[:8]}{day:02d}",
                             "txn_type": "Order", "sku": sku, "quantity": q, "product_sales": q * list_price,
                             "promotional_rebates": -q * (list_price - p) if is_deal else 0.0,
                             "total": q * p})
        econ += rows_i
        if i in dup_skus:
            econ.append(dict(rows_i[len(rows_i) // 3]))
            truth["pathologies"]["duplicate"].append(sku)
        if i in no_cogs:
            truth["pathologies"]["no_cogs"].append(sku)
        else:
            cogs.append({"sku": sku, "asin": asin, "unit_cost_usd": tr["cost"], "inbound_freight_per_unit_usd": FREIGHT,
                         "supplier_lead_time_days": int(rng.integers(25, 55)),
                         **({"supplier": f"S{i % 4}", "moq_units": 150, "case_pack_units": 12,
                             "air_freight_per_unit_usd": 1.6, "air_lead_time_days": 10} if i % 3 == 0 else {})})
        on_hand = int(tr["base"] * rng.uniform(15, 150))
        inv.append({"snapshot_date": "2026-08-30", "sku": sku, "asin": asin, "fulfillable_quantity": on_hand,
                    "inbound_quantity": 0})
        health.append({"snapshot_date": "2026-08-30", "sku": sku, "available": on_hand, "item_volume": 0.08,
                       "inv_age_181_to_270": int(on_hand * 0.3) if i % 6 == 0 else 0, "inv_age_271_to_365": 0,
                       "inv_age_365_plus": 0, "estimated_excess_quantity": None})

    # ── advertising: daily campaign spend, and search terms that add up to it ──
    ppc, terms = [], []
    term_start, term_end = "2026-08-01", "2026-08-28"
    for c in range(n_campaigns):
        mean = float(rng.uniform(40, 260))
        a, k, h = float(rng.uniform(600, 2400)), float(rng.uniform(30, 180)), float(rng.uniform(0.9, 1.4))
        truth["campaigns"][f"Camp{c}"] = {"a": a, "k": k, "h": h, "mean": mean}
        window_spend = 0.0
        for d in range(90):
            day = (TODAY - timedelta(days=90 - d)).isoformat()
            spend = mean * float(rng.uniform(0.6, 1.4))
            broken = cpc_break and c == 0 and d >= 60
            cpc = 1.1 * (1.6 if broken else 1.0)
            sales = hill(spend, a, k, h) * (0.7 if broken else 1.0) + rng.normal(0, 12)
            ppc.append({"campaign_name": f"Camp{c}", "campaign_id": f"Camp{c}", "report_date": day, "spend": spend,
                        "sales": max(0.0, sales), "clicks": spend / cpc, "impressions": spend * 40})
            if term_start <= day <= term_end:
                window_spend += spend
        weights = rng.dirichlet(np.ones(12))
        for t in range(12):
            wasted = t % 4 == 0
            terms.append({"campaign_name": f"Camp{c}", "search_term": f"term {c} {t}" + (" acme" if t == 0 else ""),
                          "spend": float(window_spend * weights[t]),
                          "sales_7d": 0.0 if wasted else float(rng.uniform(20, 300)),
                          "clicks": 30, "period_start": term_start, "period_end": term_end})
    data = {"sku_economics": econ, "asin_traffic": traffic, "cogs_inputs": cogs, "inventory_levels": inv,
            "inventory_health": health, "inventory_ledger": [], "fba_returns": [], "fba_reimbursements": [],
            "settlement_transactions": txns, "ppc_spend": ppc, "ppc_search_terms": terms, "customer_orders": []}
    return data, truth


def build(name: str, seed: int):
    return make_world(name, seed, **WORLDS[name])
