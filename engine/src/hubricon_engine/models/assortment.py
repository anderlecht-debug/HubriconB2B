"""SKU rationalisation: which SKUs to cut or merge, on a fully loaded
contribution the survival curve has already discounted.

The negative-margin directive flags a SKU that lost money last period on net
margin — revenue less fees, landed cost and allocated ads. That is one period
of one measure. A SKU earns or loses more than that: it bills storage and an
aged surcharge going forward, its returns cost what returns cost, and it
carries the operational cost of being one more thing to manage. And a SKU that
is dying is worth less than its last month says. This module puts those
together, with a credibility weight on how much of the answer is the SKU's own
history and how much the catalogue's, and flags what to cut.

THE LOADED CONTRIBUTION per period is net margin (already net of fees, landed
cost and allocated ads; storage fees sit inside the fee lines and are not
counted twice) less the forward carry the fee lines do not yet show — the aged
surcharge and low-inventory fee the inventory-economics pass prices — less the
returns cost (returned units × the loss fraction of their disposition × landed
cost) less an operational cost per active SKU, which is zero until the client
states one and says so on the row.

CREDIBILITY. A SKU with two months of history has a contribution whose
sampling error is as large as the real differences between SKUs.
risk.buhlmann blends each SKU's own mean with the catalogue's by exactly as
much as its sample size warrants, and the weight Z rides on the row: a SKU cut
on Z = 0.2 is being cut on the catalogue's number, and the text says so. The
interval on the blended contribution is a normal on the pooled within-SKU
variance over n, and P(contribution < 0) comes from it.

SURVIVAL. risk.kaplan_meier on the catalogue's SKU lifetimes gives S(t) in
periods. A SKU alive for `age` periods has conditional survival
S(age + k) / S(age) for the k months ahead, and its expected twelve-month
value is Σ_k S(age + k | age) × blended contribution / (1 + i/12)^k. An old SKU
on a declining catalogue is worth less than a young one with the same
contribution, which is the difference between "loses $200 a month" and "loses
$200 a month and is going to die anyway".

WHAT IS FLAGGED. Cut: blended contribution below zero, Z at least 0.5, at
least two negative periods, and P(contribution < 0) at least 0.75 — four gates
so that one bad month never names a SKU. Merge: a variant (models/cross_price
families) with under 5% of its family's revenue and a loaded contribution at
or below zero. The exit directive promises the avoided twelve-month loss; the
Profit Record banks it only as the periods without the SKU actually pass.

WHAT IT CANNOT TELL YOU. Whether a cut SKU's buyers move to a sibling (the
merge case says which variants might; the family's cross-elasticity in §3b is
the only evidence). What a SKU is worth to the listing's rank or to a bundle.
The operational cost, until the client states it.
"""

from datetime import date

import numpy as np
from scipy import stats

from .common import num, period_days
from .risk import RETURN_LOSS_FRACTION, RETURN_LOSS_FRACTION_UNKNOWN, buhlmann

OPERATIONAL_COST_PER_SKU_MONTH = 0.0    # not stated by any client yet; the row says so
MIN_PERIODS = 2
MIN_CREDIBILITY = 0.5
MIN_NEGATIVE_PERIODS = 2
MIN_P_NEGATIVE = 0.75
MERGE_SHARE = 0.05
HORIZON_MONTHS = 12
ANNUAL_DISCOUNT = 0.12
ASSORTMENT_DRAWS = 4000
ASSORTMENT_SEED = 20260911


def _returns_cost_by_period(returns_rows: list[dict], unit_cost: dict[str, float],
                            periods: list[tuple[str, str]]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for r in returns_rows or []:
        sku = r.get("sku") or r.get("fnsku")
        d = str(r.get("return_date") or "")[:10]
        if not sku or not d or sku not in unit_cost:
            continue
        disp = (r.get("detailed_disposition") or "").strip().upper()
        frac = RETURN_LOSS_FRACTION.get(disp, RETURN_LOSS_FRACTION_UNKNOWN)
        for start, end in periods:
            if start <= d <= end:
                out[(sku, start)] = out.get((sku, start), 0.0) + float(r.get("quantity") or 1) * frac * unit_cost[sku]
                break
    return out


def loaded_contribution(margins: list[dict], inv_econ: dict | None, returns_rows: list[dict] | None,
                        operational_cost_month: float = OPERATIONAL_COST_PER_SKU_MONTH) -> dict[str, list[dict]]:
    """{sku: [{period_start, days, net, carry, returns, operational, loaded}]}."""
    periods = sorted({(str(m["period_start"]), str(m["period_end"])) for m in margins if m.get("period_end")})
    unit_cost = {}
    for m in margins:
        if m.get("cogs") is not None and float(m.get("units") or 0) > 0:
            unit_cost[m["sku"]] = float(m["cogs"]) / float(m["units"])
    returns = _returns_cost_by_period(returns_rows, unit_cost, periods)
    carry_month = {}
    for r in (inv_econ or {}).get("rows", []):
        carry_month[r["sku"]] = float(r.get("aged_surcharge_month") or 0) + float(r.get("low_inventory_fee_month") or 0)
    out: dict[str, list[dict]] = {}
    for m in sorted(margins, key=lambda x: str(x["period_start"])):
        if m.get("net_margin") is None or not m.get("period_end"):
            continue
        days = period_days(str(m["period_start"]), str(m["period_end"]))
        scale = days / 30.0
        carry = carry_month.get(m["sku"], 0.0) * scale
        ret = returns.get((m["sku"], str(m["period_start"])), 0.0)
        oper = operational_cost_month * scale
        loaded = float(m["net_margin"]) - carry - ret - oper
        out.setdefault(m["sku"], []).append({
            "period_start": str(m["period_start"]), "days": days, "net": float(m["net_margin"]),
            "carry": round(carry, 2), "returns": round(ret, 2), "operational": round(oper, 2),
            "loaded": round(loaded, 2), "loaded_monthly": round(loaded / scale, 2),
            "revenue": float(m.get("revenue") or 0),
        })
    return out


def _survival_curve(risk_out: dict | None):
    surv = (risk_out or {}).get("survival") or {}
    if surv.get("status") != "ok" or not surv.get("t"):
        return None
    t = np.array(surv["t"], dtype=float)
    s = np.array(surv["s"], dtype=float)
    per_days = float(surv.get("period_days_typical") or 30)

    def S(periods: float) -> float:
        idx = np.searchsorted(t, periods, side="right") - 1
        return float(s[max(0, min(idx, len(s) - 1))])
    return S, per_days


def run(margins: list[dict], inv_econ: dict | None, data: dict, risk_out: dict | None,
        families: dict | None = None, today: date | None = None,
        operational_cost_month: float = OPERATIONAL_COST_PER_SKU_MONTH) -> dict:
    today = today or date.today()
    series = loaded_contribution(margins, inv_econ, (data or {}).get("fba_returns"), operational_cost_month)
    if not series:
        return {"status": "insufficient_data", "basis": "no margin rows with a net margin"}
    monthly = {sku: [p["loaded_monthly"] for p in rows] for sku, rows in series.items()}
    cred = buhlmann({sku: v for sku, v in monthly.items() if len(v) >= 1})
    curve = _survival_curve(risk_out)
    by_sku_family = ((families or {}).get("by_sku") or {})
    family_revenue: dict[str, float] = {}
    for sku, info in by_sku_family.items():
        rev = sum(p["revenue"] for p in series.get(sku, [])[-1:])
        family_revenue[info["family"]] = family_revenue.get(info["family"], 0.0) + rev
    rng = np.random.default_rng(ASSORTMENT_SEED)
    rows = []
    for sku, rows_in in series.items():
        n = len(rows_in)
        g = (cred.get("by_group") or {}).get(sku) if cred.get("status") == "ok" else None
        blended = float(g["blended"]) if g else float(np.mean(monthly[sku]))
        z = float(g["z"]) if g else 1.0
        within = float(cred.get("within_var") or 0.0) if cred.get("status") == "ok" else float(np.var(monthly[sku], ddof=1)) if n > 1 else 0.0
        se = float(np.sqrt(max(within, 0.0) / n)) if n > 0 else 0.0
        p_neg = float(stats.norm.cdf(0.0, loc=blended, scale=se)) if se > 0 else float(blended < 0)
        negative_periods = sum(1 for v in monthly[sku] if v < 0)
        # survival-conditioned twelve-month value
        age_periods = n
        factors = []
        if curve:
            S, per_days = curve
            s_age = S(age_periods)
            for k in range(1, HORIZON_MONTHS + 1):
                ahead = age_periods + k * 30.0 / per_days
                factors.append(S(ahead) / s_age if s_age > 0 else 0.0)
        else:
            factors = [1.0] * HORIZON_MONTHS
        disc = np.array([(1 + ANNUAL_DISCOUNT / 12) ** -k for k in range(1, HORIZON_MONTHS + 1)])
        weight = float(np.sum(np.array(factors) * disc))
        draws = blended + se * rng.standard_normal(ASSORTMENT_DRAWS) if se > 0 else np.full(ASSORTMENT_DRAWS, blended)
        value = draws * weight
        row = {
            "sku": sku, "n_periods": n, "loaded_monthly_mean": num(float(np.mean(monthly[sku]))),
            "blended_monthly": num(blended), "credibility_z": num(z, 4), "se": num(se, 2),
            "ci95": [num(blended - 1.96 * se), num(blended + 1.96 * se)], "p_negative": num(p_neg, 4),
            "negative_periods": negative_periods,
            "survival_12m": [num(f, 4) for f in factors], "survival_basis": "Kaplan–Meier, conditioned on the SKU's age" if curve else "no survival curve (flat)",
            "value_12m": {"p5": num(float(np.quantile(value, 0.05))), "p50": num(float(np.quantile(value, 0.5))),
                          "p95": num(float(np.quantile(value, 0.95)))},
            "components_latest": {k: rows_in[-1][k] for k in ("net", "carry", "returns", "operational", "loaded")},
            "operational_cost_basis": ("client-stated" if operational_cost_month else "not stated: zero"),
        }
        cut = (blended < 0 and z >= MIN_CREDIBILITY and negative_periods >= MIN_NEGATIVE_PERIODS and p_neg >= MIN_P_NEGATIVE)
        info = by_sku_family.get(sku)
        merge = False
        if info and family_revenue.get(info["family"], 0) > 0:
            share = rows_in[-1]["revenue"] / family_revenue[info["family"]]
            row["family"] = info["family"]
            row["family_revenue_share"] = num(share, 4)
            merge = share < MERGE_SHARE and rows_in[-1]["loaded"] <= 0 and n >= MIN_PERIODS
        row["decision"] = "cut" if cut else ("merge" if merge else "keep")
        if cut or merge:
            avoided = -value
            row["avoided_loss_12m"] = {"p5": num(float(np.quantile(avoided, 0.05))), "p50": num(float(np.quantile(avoided, 0.5))),
                                       "p95": num(float(np.quantile(avoided, 0.95))),
                                       "p_loss": num(float(np.mean(avoided < 0)), 4)}
        rows.append(row)
    rows.sort(key=lambda r: (r["decision"] != "cut", r["decision"] != "merge", r["blended_monthly"] or 0))
    return {
        "status": "ok", "as_of": today.isoformat(), "seed": ASSORTMENT_SEED, "rows": rows,
        "credibility": {k: cred.get(k) for k in ("status", "k", "within_var", "between_var", "mu", "n_groups")},
        "summary": {"n_skus": len(rows), "cut": [r["sku"] for r in rows if r["decision"] == "cut"],
                    "merge": [r["sku"] for r in rows if r["decision"] == "merge"],
                    "avoided_loss_12m_p50": num(sum(float(r["avoided_loss_12m"]["p50"] or 0) for r in rows if r.get("avoided_loss_12m")))},
        "assumptions": [
            "Loaded contribution = net margin − forward carry (aged surcharge, low-inventory fee) − returns cost − operational cost per SKU",
            f"Operational cost per active SKU: {'client-stated' if operational_cost_month else 'not stated, zero'}",
            "Per-SKU contribution blended with the catalogue by Bühlmann–Straub credibility; a cut needs Z ≥ 0.5, two negative periods and P(<0) ≥ 0.75",
            "Twelve-month value discounts by the catalogue's Kaplan–Meier survival conditioned on the SKU's age",
        ],
    }
