"""Stress scenarios: what would break you.

The cone answers "how likely is the account to dip under its buffer in the
next ninety days, given everything as it is". Platform and concentration risk
are the questions it does not ask: what if the referral fee rises, what if
the biggest listing is suppressed for a month, what if clicks get dearer,
what if the supplier is late, what if the platform holds a payout. Each of
those is a change to ONE component of the cone's arithmetic, and the cone
kept its components (cashflow.simulate keep_paths), so every scenario is the
same paths recomputed — no new draws, and the base scenario reproduces the
published cone exactly, which is the check that the rest can be trusted.

THE SCENARIOS.
  fee_rise          the platform's proportional fee up FEE_SHOCK_PP points of
                    revenue: sales net of fees falls by that share of revenue
  top_sku_suppressed the largest SKU by revenue earns nothing for
                    SUPPRESSION_DAYS from day one (a listing suppression, a
                    lost Buy Box, a stockout of the one that matters)
  cpc_rise          every ad dollar buys CPC_SHOCK less: the same clicks cost
                    (1 + CPC_SHOCK) times the ad spend
  supplier_delay    the largest SKUs' inbound lands SUPPLIER_DELAY_DAYS late:
                    each earns nothing from the day its cover runs out until
                    the delay has passed
  payout_hold       the platform holds every payout PAYOUT_HOLD_DAYS (an
                    account review, a verification): the same money, later

Each reports p(ruin), the trough's 5th percentile and expected shortfall, and
the ninety-day net change, against the base, with the Monte Carlo error on
p(ruin). The table is ranked by the change in p(ruin): the first row is what
would break you first.

WHAT IT CANNOT TELL YOU. How likely any scenario is — these are stresses, not
forecasts — and second-order responses (a seller who cuts ads when fees rise).
"""

import numpy as np

from .cashflow import cash_from_components
from .common import num
from .mc import expected_shortfall

FEE_SHOCK_PP = 0.03
SUPPRESSION_DAYS = 30
CPC_SHOCK = 0.30
SUPPLIER_DELAY_DAYS = 30
PAYOUT_HOLD_DAYS = 30


def _summary(cash: np.ndarray, floor: float) -> dict:
    trough = cash.min(axis=1)
    tail = expected_shortfall(trough, 0.05, tail="lower")
    p = float(np.mean(trough < floor))
    return {"p_ruin": num(p, 4), "p_ruin_mc_se": num(float(np.sqrt(max(p * (1 - p), 1e-12) / cash.shape[0])), 5),
            "trough_p5": num(tail["threshold"]), "trough_expected_shortfall": num(tail["shortfall"]),
            "end_cash_p50": num(float(np.median(cash[:, -1])))}


def scenarios(paths: dict) -> list[dict]:
    top = paths.get("top") or {}
    biggest = next(iter(top), None)
    out = [
        {"name": "base", "label": "as things are", "sales_net": paths["sales_net"], "ads": paths["ad_daily_total"],
         "outflow": paths["outflow"], "shift": 0},
        {"name": "fee_rise", "label": f"platform fee +{FEE_SHOCK_PP:.0%} of revenue",
         "sales_net": paths["sales_net"] - FEE_SHOCK_PP * paths["revenue"], "ads": paths["ad_daily_total"],
         "outflow": paths["outflow"], "shift": 0},
        {"name": "cpc_rise", "label": f"cost per click +{CPC_SHOCK:.0%}", "sales_net": paths["sales_net"],
         "ads": paths["ad_daily_total"] * (1 + CPC_SHOCK), "outflow": paths["outflow"], "shift": 0},
        {"name": "payout_hold", "label": f"payouts held {PAYOUT_HOLD_DAYS} days", "sales_net": paths["sales_net"],
         "ads": paths["ad_daily_total"], "outflow": paths["outflow"], "shift": PAYOUT_HOLD_DAYS},
    ]
    if biggest:
        sup = paths["sales_net"].copy()
        sup[:, :SUPPRESSION_DAYS] -= top[biggest]["sales_net"][:, :SUPPRESSION_DAYS]
        out.append({"name": "top_sku_suppressed", "label": f"{biggest} earns nothing for {SUPPRESSION_DAYS} days",
                    "sales_net": sup, "ads": paths["ad_daily_total"], "outflow": paths["outflow"], "shift": 0,
                    "sku": biggest})
        delayed = paths["sales_net"].copy()
        hit = []
        for sku, t in top.items():
            cover = t.get("days_of_cover")
            if cover is None:
                continue
            start = int(max(0, min(paths["days"], np.floor(cover))))
            end = int(min(paths["days"], start + SUPPLIER_DELAY_DAYS))
            if end > start:
                delayed[:, start:end] -= t["sales_net"][:, start:end]
                hit.append(sku)
        if hit:
            out.append({"name": "supplier_delay", "label": f"inbound {SUPPLIER_DELAY_DAYS} days late on {', '.join(hit)}",
                        "sales_net": delayed, "ads": paths["ad_daily_total"], "outflow": paths["outflow"], "shift": 0,
                        "skus": hit})
    return out


def run(paths: dict | None, cone: dict | None) -> dict:
    if not paths or not cone:
        return {"status": "no_cash_inputs", "basis": "no cone on this run; nothing to stress"}
    floor = float(paths.get("ruin_floor") or 0.0)
    rows = []
    base = None
    for sc in scenarios(paths):
        cash = cash_from_components(paths, sc["sales_net"], sc["ads"], sc["outflow"], paths["payout_days"], sc["shift"])
        summ = _summary(cash, floor)
        row = {"name": sc["name"], "label": sc["label"], **summ}
        for k in ("sku", "skus"):
            if k in sc:
                row[k] = sc[k]
        if sc["name"] == "base":
            base = row
        rows.append(row)
    for r in rows:
        r["p_ruin_delta"] = num(float(r["p_ruin"]) - float(base["p_ruin"]), 4)
        r["trough_p5_delta"] = num(float(r["trough_p5"] or 0) - float(base["trough_p5"] or 0))
        r["end_cash_delta_p50"] = num(float(r["end_cash_p50"] or 0) - float(base["end_cash_p50"] or 0))
    ranked = sorted((r for r in rows if r["name"] != "base"), key=lambda r: -(r["p_ruin_delta"] or 0))
    return {
        "status": "ok", "base": base, "scenarios": [base] + ranked,
        "worst": ranked[0]["name"] if ranked else None,
        "reproduces_cone": bool(abs(float(base["p_ruin"]) - float(cone.get("p_ruin") or 0)) < 1e-6),
        "basis": ("each scenario changes one component of the cone's arithmetic and recomputes the same "
                  f"{paths['n_paths']:,} paths; ranked by the change in p(ruin); the base row must equal the cone"),
        "assumptions": ["Stresses, not forecasts: no scenario carries a probability of happening",
                        "No second-order response is modelled (a seller who cuts ads when fees rise)"],
    }
