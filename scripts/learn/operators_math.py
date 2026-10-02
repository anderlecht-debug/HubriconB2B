"""The Operator's Math: the course's worked example, computed by Hubricon's engine, its
spreadsheet, and the check that holds the spreadsheet to the engine.

    cd engine && uv run --with openpyxl python ../scripts/learn/operators_math.py             # figures, then verify
    cd engine && uv run --with openpyxl python ../scripts/learn/operators_math.py --publish   # ...and ship the file

FIGURES. One invented Shopify store: a coffee roaster selling one 12 oz bag of whole beans.
Its price, costs, ad curve and customers are invented, and drawn from a seeded simulation
whose true parameters are written below, so the course can say how close the engine came.
Every figure the course prints is computed here and written to data/learn-operators-math.json,
which scripts/build-pages.mjs bakes into learn/operators-math.html. Nothing on the page is typed.

    the label and the payment fee              cold/priors.py              CARRIER_GROUND_COMMERCIAL, payments_fee
    what the last ad dollar returns            models/ad_efficiency.py     run (the curve, its interval, the break-even)
    repeat orders, lifetime value, payback     models/clv.py               run, expected_repeats, payback
    blended acquisition cost                   models/clv.py               cac_by_month

TEMPLATE. learn/files/hubricon-operators-math.xlsx: the same arithmetic as formulas.

VERIFY. Random inputs through the engine's own functions and through the recalculated
sheets, figure by figure; and the course's in-browser customer reading (assets/cohorts.mjs)
against this file's reference on a synthetic Orders export (scripts/learn/operators-math.golden.json).
--publish ships the file and scripts/learn/operators-math.stamp.json (the hashes of the engine
modules and the file); scripts/learn/operators-math.test.mjs fails when one moves without a re-run.

Needs LibreOffice (soffice) on PATH.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from hubricon_engine.cold import priors  # noqa: E402
from hubricon_engine.models import ad_efficiency, clv  # noqa: E402

FILE = ROOT / "learn" / "files" / "hubricon-operators-math.xlsx"
FIGURES = ROOT / "data" / "learn-operators-math.json"
STAMP = ROOT / "scripts" / "learn" / "operators-math.stamp.json"
GOLDEN = ROOT / "scripts" / "learn" / "operators-math.golden.json"
SOURCES = ["engine/src/hubricon_engine/cold/priors.py", "engine/src/hubricon_engine/models/clv.py",
           "engine/src/hubricon_engine/models/ad_efficiency.py"]

# ═══ The worked example ══════════════════════════════════════════════════════════════════
# Invented. One product, one unit an order, free shipping, Shopify Payments on the Basic plan.
EXAMPLE = {
    "what": "an invented coffee roaster's 12 oz bag of whole beans",
    "price": 24.00,
    "landed_cost": 7.20,        # green coffee, roasting, the bag
    "packing": 0.90,            # box, fill, minutes
    "plan": "basic",
    "refund_share": 0.02,       # of orders refunded in full; coffee is not sent back
    "packed_oz": 15.2,          # under a pound: the card's first row
    "target_roas": 3.0,         # the ad target the invented owner set
}
# The simulation behind the store. The truth is known only because the store is invented.
TRUTH = {"r": 1.6, "alpha": 9.0, "a": 1.4, "b": 5.5}          # BG/NBD, in weeks
CURVE = {"A": 1900.0, "K": 250.0}                               # attributed sales a day = A·s/(K+s)
NEW_SHARE = 0.30                # of attributed sales that are first orders
SPEND_RANGE = (180.0, 420.0)    # dollars a day, drawn evenly
REPEAT_BASKETS = ([24.0, 26.0, 48.0], [0.6, 0.25, 0.15])        # a bag, a bag and an add-on, two bags
START, END = date(2025, 4, 1), date(2026, 9, 30)
AD_DAYS = 90                    # the last days the ad curve is read from
SEED = 20261002
MONTH_WEEKS = 52 / 12


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def simulate(seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """(customer orders, daily ad rows). Every new customer arrives through the ad, on the curve."""
    rng = np.random.default_rng(seed)
    orders, ppc = [], []
    days = (END - START).days + 1
    cid = 0
    for i in range(days):
        day = START + timedelta(days=i)
        s = float(rng.uniform(*SPEND_RANGE))
        sales = CURVE["A"] * s / (CURVE["K"] + s) * float(rng.lognormal(0, 0.08))
        ppc.append({"campaign_name": "Prospecting", "campaign_id": "1", "report_date": day.isoformat(),
                    "spend": round(s, 2), "sales": round(sales, 2)})
        for _ in range(int(rng.poisson(NEW_SHARE * sales / EXAMPLE["price"]))):
            cid += 1
            key = f"c{cid:05d}"
            lam = float(rng.gamma(TRUTH["r"], 1 / TRUTH["alpha"]))
            p = float(rng.beta(TRUTH["a"], TRUTH["b"]))
            orders.append({"customer_key": key, "order_date": day.isoformat(), "revenue": EXAMPLE["price"]})
            t = 0.0
            while True:
                t += float(rng.exponential(1 / lam)) * 7 if lam > 0 else 1e9
                d = day + timedelta(days=int(t))
                if d > END:
                    break
                orders.append({"customer_key": key, "order_date": d.isoformat(),
                               "revenue": float(rng.choice(REPEAT_BASKETS[0], p=REPEAT_BASKETS[1]))})
                if rng.random() < p:
                    break
    return orders, ppc


def contribution(x: dict, label: float) -> dict:
    fee = priors.payments_fee(x["plan"], x["price"])
    refunds = x["price"] * x["refund_share"]
    before = x["price"] - x["landed_cost"] - fee - label - x["packing"] - refunds
    return {"fee": fee, "refunds": refunds, "before_ads": before, "rate": before / x["price"],
            "gross": x["price"] - x["landed_cost"], "gross_rate": (x["price"] - x["landed_cost"]) / x["price"]}


def new_customer_repeats(params: dict, weeks: float) -> float:
    z = np.array([0.0])
    return float(clv.expected_repeats(params, float(weeks), z, z, z)[0])


def figures() -> dict:
    x = EXAMPLE
    r2 = lambda v, d=2: None if v is None else round(float(v), d)
    label_row = priors.CARRIER_GROUND_COMMERCIAL[0]
    label = sum(label_row) / len(label_row)            # an even mix of zones, under a pound
    c = contribution(x, label)
    m = c["rate"]

    orders, ppc = simulate()
    revenue = sum(o["revenue"] for o in orders)
    spend = sum(r["spend"] for r in ppc)
    margins = [{"revenue": revenue, "net_margin": revenue * m - spend, "ad_spend_allocated": spend}]
    cv = clv.run(orders, margins=margins, ppc_spend=ppc)
    fit = cv["bgnbd"]
    pb = cv["payback"]
    cac = float(cv["cac"]["cac"])
    first, repeat = float(cv["first_order_value"]), float(cv["repeat_order_value"])
    rep_new = new_customer_repeats(fit, clv.HORIZON_WEEKS)
    rep_true = new_customer_repeats(TRUTH, clv.HORIZON_WEEKS)
    weekly = [m * (first + new_customer_repeats(fit, w) * repeat) for w in range(0, clv.HORIZON_WEEKS + 1)]
    weekly[0] = m * first
    monthly_reps = [new_customer_repeats(fit, MONTH_WEEKS * k) for k in range(1, 13)]
    mult = float(cv["clv_multiplier"])

    # the last month: what the store's P&L shows
    last_month = END.strftime("%Y-%m")
    mo_orders = [o for o in orders if o["order_date"][:7] == last_month]
    mo_spend = sum(r["spend"] for r in ppc if r["report_date"][:7] == last_month)
    mo_new = len({o["customer_key"] for o in orders if o["order_date"][:7] == last_month} -
                 {o["customer_key"] for o in orders if o["order_date"][:7] < last_month})
    ad_per_order = mo_spend / len(mo_orders)
    after_ads = c["before_ads"] - ad_per_order

    # the ad curve, on its last 90 days: first-order break-even, then with the repeat customers
    recent = ppc[-AD_DAYS:]
    data = {"ppc_search_terms": [], "ppc_spend": recent}
    ad = ad_efficiency.run(data, avg_margin=m)[0]
    ad_life = ad_efficiency.run(data, avg_margin=m, clv_multiplier=mult, clv_basis="calibrated")[0]
    unc = ad["details"]["uncertainty"]
    model, params = ad["curve_model"], ad["curve_params"]
    theta = [params[k] for k in params]
    f = lambda s: float(ad_efficiency.curve_values(model, np.array(theta), np.array([s]))[0, 0])
    cur, be = float(ad["current_spend"]), ad["breakeven_spend"]
    lost_day = (cur - be) - m * (f(cur) - f(be)) if be is not None else None
    sp = np.array([r["spend"] for r in recent])
    sa = np.array([r["sales"] for r in recent])
    slope = float(np.polyfit(sp, sa, 1)[0])
    max_seen = float(sp.max())

    be_roas = x["price"] / c["before_ads"]
    at_target = x["price"] / x["target_roas"]
    rev_ltv = first + rep_new * repeat
    ranked = sorted([
        {"key": "ltv", "number": "LTV to CAC, on revenue", "says": rev_ltv / cac, "true": pb["ltv_cac"], "kind": "ratio",
         "truth": "on 52 weeks of margin"},
        {"key": "gross", "number": "Gross margin", "says": c["gross_rate"], "true": c["rate"], "kind": "share",
         "truth": "contribution before ads"},
        {"key": "average", "number": "Average ROAS", "says": float(ad["current_sales"]) / cur, "true": float(ad["marginal_roas"]), "kind": "roas",
         "truth": "what the last dollar returns"},
        {"key": "first", "number": "Break-even ROAS on the first order", "says": be_roas, "true": be_roas / mult, "kind": "roas",
         "truth": "with the customers who come back"},
    ], key=lambda r: -max(r["says"], r["true"]) / min(r["says"], r["true"]))
    for r in ranked:
        r["factor"] = r2(max(r["says"], r["true"]) / min(r["says"], r["true"]), 2)
        r["flatters"] = r["says"] > r["true"] if r["key"] != "first" else False
        r["says"], r["true"] = r2(r["says"], 4), r2(r["true"], 4)

    return {
        "about": "The Operator's Math's worked example: an invented Shopify coffee roaster, its customers and its ad curve simulated from stated parameters, read by Hubricon's engine (scripts/learn/operators_math.py).",
        "example": dict(x),
        "truth": {**TRUTH, "curve": CURVE, "new_share": NEW_SHARE, "spend_range": list(SPEND_RANGE), "seed": SEED,
                  "repeats_52w_new": r2(rep_true, 3), "window": [START.isoformat(), END.isoformat()]},
        "unit": {"label": r2(label, 4), "label_lo": min(label_row), "label_hi": max(label_row), "fee": r2(c["fee"], 4),
                 "refunds": r2(c["refunds"], 4), "gross": r2(c["gross"], 4), "gross_rate": r2(c["gross_rate"], 4),
                 "before_ads": r2(c["before_ads"], 4), "rate": r2(m, 4), "ad_per_order": r2(ad_per_order, 4),
                 "after_ads": r2(after_ads, 4), "after_rate": r2(after_ads / x["price"], 4)},
        "month": {"month": last_month, "orders": len(mo_orders), "new": mo_new, "spend": r2(mo_spend),
                  "revenue": r2(sum(o["revenue"] for o in mo_orders)), "cash_out": r2(mo_new * cac)},
        "ads": {"be_roas": r2(be_roas, 4), "be_acos": r2(1 / be_roas, 4), "target": x["target_roas"],
                "cost_at_target": r2(at_target, 4), "kept_at_target": r2(c["before_ads"] - at_target, 4),
                "spend": r2(cur), "sales": r2(ad["current_sales"]), "average": r2(float(ad["current_sales"]) / cur, 4),
                "marginal": r2(ad["marginal_roas"], 4), "marginal_p5": r2(unc["marginal_roas_p5"], 4), "marginal_p95": r2(unc["marginal_roas_p95"], 4),
                "breakeven": r2(be), "breakeven_p5": r2(unc.get("breakeven_p5")), "breakeven_p95": r2(unc.get("breakeven_p95")),
                "lost_month": r2(lost_day * 30 if lost_day is not None else None), "model": model, "params": {k: r2(v, 6) for k, v in params.items()},
                "slope": r2(slope, 4), "max_seen": r2(max_seen), "days": AD_DAYS,
                "life_be_roas": r2(be_roas / mult, 4), "life_breakeven": r2(ad_life.get("breakeven_spend")),
                "points": [[r2(r["spend"]), r2(r["sales"])] for r in recent]},
        "customers": {"n": cv["n_customers"], "first": r2(first), "repeat": r2(repeat), "repeats_52w_new": r2(rep_new, 3),
                      "repeats_52w_base": r2(cv["expected_repeats_52w"], 3), "multiplier": r2(mult, 4),
                      "multiplier_band": [r2(cv["clv_multiplier_band"]["p5"], 4), r2(cv["clv_multiplier_band"]["p95"], 4)],
                      "calibration": r2(cv["calibration"]["actual_over_predicted"], 3), "cac": r2(cac), "cac_months": cv["cac"]["months_used"],
                      "rev_ltv": r2(rev_ltv), "rev_ltv_cac": r2(rev_ltv / cac, 4), "margin_ltv": r2(pb["ltv_52w_margin"]),
                      "margin_ltv_cac": r2(pb["ltv_cac"], 4), "margin_ltv_cac_band": [r2(v, 4) for v in pb["ltv_cac_band"]],
                      "discount": clv.ANNUAL_DISCOUNT, "fit": {k: r2(v, 4) for k, v in fit.items() if k in ("r", "alpha", "a", "b")}},
        "payback": {"weeks": pb["payback_weeks"], "band": pb["payback_weeks_band"], "weekly": [r2(v, 4) for v in weekly],
                    "monthly_repeats": [r2(v, 4) for v in monthly_reps],
                    "month": next((k for k, rv in enumerate(monthly_reps, start=1) if m * (first + rv * repeat) >= cac), None)},
        "ranked": ranked,
        "sources": {p: sha(p) for p in SOURCES},
    }


# ═══ The customer reading, as the browser does it (assets/cohorts.mjs) ═══════════════════
DROP_STATUSES = {"voided", "pending"}
DAYS_A_MONTH = 365.25 / 12


def customer_curve(orders: list[dict], months: int = 12) -> dict:
    """Orders [{email, name, created, cancelled, status, revenue}] → the cohort curve.
    One order per name; cancelled, voided and pending dropped; revenue after discounts and refunds
    (ingest/shopify_orders.py); a customer is the lower-cased email. For each month k, the customers
    whose first order is at least k months before the export's last day, and their repeat orders
    and repeat revenue within k months of that first order."""
    by: dict[str, list[tuple[date, float]]] = {}
    last = None
    for o in orders:
        if o.get("cancelled") or str(o.get("status") or "").strip().lower() in DROP_STATUSES or not o.get("created"):
            continue
        d = date.fromisoformat(o["created"])
        last = d if last is None or d > last else last
        email = str(o.get("email") or "").strip().lower()
        if email:
            by.setdefault(email, []).append((d, float(o["revenue"])))
    if not by:
        return {"customers": 0}
    firsts, repeats_all = [], []
    for v in by.values():
        v.sort()
        firsts.append(v[0][1])
        repeats_all += [r for _, r in v[1:]]
    curve = []
    for k in range(1, months + 1):
        span = k * DAYS_A_MONTH
        eligible = [v for v in by.values() if (last - v[0][0]).days >= span]
        if not eligible:
            curve.append({"month": k, "customers": 0, "repeats": None, "repeat_revenue": None})
            continue
        reps = [sum(1 for d, _ in v[1:] if (d - v[0][0]).days <= span) for v in eligible]
        revs = [sum(r for d, r in v[1:] if (d - v[0][0]).days <= span) for v in eligible]
        curve.append({"month": k, "customers": len(eligible), "repeats": round(sum(reps) / len(eligible), 6),
                      "repeat_revenue": round(sum(revs) / len(eligible), 6)})
    came_back = sum(1 for v in by.values() if len(v) > 1)
    return {"customers": len(by), "came_back": came_back, "came_back_share": round(came_back / len(by), 6),
            "first_value": round(sum(firsts) / len(firsts), 6),
            "repeat_value": round(sum(repeats_all) / len(repeats_all), 6) if repeats_all else None,
            "last": last.isoformat(), "curve": curve}


def payback_month(cv: dict, margin_rate: float, cac: float) -> int | None:
    for row in cv.get("curve", []):
        if row["repeat_revenue"] is None:
            return None
        if margin_rate * (cv["first_value"] + row["repeat_revenue"]) >= cac:
            return row["month"]
    return None


def orders_csv(orders: list[dict], customers: int = 260, seed: int = 7) -> tuple[str, list[dict]]:
    """A synthetic Shopify Orders export for the first `customers` of the simulation: one line per
    line item, order fields on the first line only, as Shopify writes it. Some orders carry a
    discount, a part refund, a second line, or are cancelled, voided or pending."""
    rng = random.Random(seed)
    keep = sorted({o["customer_key"] for o in orders})[:customers]
    keyset = set(keep)
    rows, ref = [], []
    n = 1000
    for o in sorted((o for o in orders if o["customer_key"] in keyset), key=lambda o: (o["order_date"], o["customer_key"])):
        n += 1
        name = f"#{n}"
        email = f"{o['customer_key']}@example.com" if rng.random() > 0.02 else ""
        if rng.random() < 0.15:
            email = email.upper()
        status = rng.choices(["paid", "partially_refunded", "refunded", "voided", "pending"], [0.9, 0.04, 0.02, 0.02, 0.02])[0]
        cancelled = f"{o['order_date']} 12:00:00 -0400" if rng.random() < 0.02 else ""
        lines = [("COF-12", 1, 24.0)] if o["revenue"] == 24.0 else [("COF-12", 1, 24.0), ("FLT-1", 1, 2.0)] if o["revenue"] == 26.0 else [("COF-12", 2, 24.0)]
        discount = 2.4 if rng.random() < 0.1 else 0.0
        gross = sum(q * p for _, q, p in lines)
        refund = round(gross - discount, 2) if status == "refunded" else (5.0 if status == "partially_refunded" else 0.0)
        for i, (sku, q, p) in enumerate(lines):
            rows.append({"Name": name, "Email": email if i == 0 else "", "Financial Status": status if i == 0 else "",
                         "Created at": f"{o['order_date']} 09:30:00 -0400", "Cancelled at": cancelled if i == 0 else "",
                         "Refunded Amount": f"{refund:.2f}" if i == 0 else "", "Lineitem quantity": q, "Lineitem name": "Whole beans 12 oz" if sku == "COF-12" else "Paper filters",
                         "Lineitem price": f"{p:.2f}", "Lineitem sku": sku, "Lineitem discount": f"{discount:.2f}" if i == 0 else "0.00"})
        revenue = gross - discount
        ref.append({"email": email, "name": name, "created": o["order_date"], "cancelled": cancelled, "status": status,
                    "revenue": round(revenue - max(0.0, min(refund, revenue)), 2)})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue(), ref


# ═══ The spreadsheet ═════════════════════════════════════════════════════════════════════
INPUT = PatternFill("solid", fgColor="FFF2CC")
TITLE = Font(name="Arial", bold=True, size=16)
HEAD = Font(name="Arial", bold=True, size=11)
BODY = Font(name="Arial", size=10)
BOLD = Font(name="Arial", bold=True, size=10)
LINK = Font(name="Arial", size=10, color="008000")
NOTE = Font(name="Arial", size=9, italic=True, color="555555")
USD, PCT, PCT1, NUM2, INT, X2 = '"$"#,##0.00', "0%", "0.0%", "0.00", "#,##0", '0.00"×"'
DAY_ROWS = 120


def put(ws, ref, value, font=BODY, fmt=None, fill=None, bold=False):
    cell = ws[ref]
    cell.value = value
    cell.font = BOLD if bold else font
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    return cell


def inputs(ws, start, rows):
    for i, (label, v, fmt) in enumerate(rows):
        r = start + i
        put(ws, f"A{r}", label)
        linked = isinstance(v, str) and v.startswith("=")
        put(ws, f"B{r}", v, LINK if linked else BODY, fmt=fmt, fill=None if linked else INPUT)


def contribution_sheet(ws, fig):
    """Lesson 1."""
    x, u = EXAMPLE, fig["unit"]
    ws.title = "Contribution"
    put(ws, "A1", "Contribution: what one order keeps, before ads and after", TITLE)
    put(ws, "A2", "Yellow cells are yours. One unit an order. Payment processing is charged on the whole charge; a refunded order keeps its costs.", NOTE)
    inputs(ws, 4, [("Price", x["price"], USD), ("Landed cost a unit", x["landed_cost"], USD),
                   ("Payment processing rate (Shopify Payments Basic: 2.9%)", 0.029, PCT1), ("Payment processing, fixed a charge", 0.30, USD),
                   ("Shipping label an order (yours to pay on free shipping)", u["label"], USD), ("Packing an order: box, fill, minutes", x["packing"], USD),
                   ("Share of orders refunded in full", x["refund_share"], PCT1), ("Ad spend per order: a month's ad spend ÷ its orders", u["ad_per_order"], USD)])
    rows = [(13, "Gross margin a unit: price − landed cost", "=B4-B5", USD), (14, "Gross margin, share of price", "=B13/B4", PCT1),
            (15, "Payment processing an order", "=ROUND(B4*B6+B7,4)", USD), (16, "Refunds an order: price × share refunded", "=B4*B10", USD),
            (17, "Contribution before ads: price − landed − processing − label − packing − refunds", "=B4-B5-B15-B8-B9-B16", USD),
            (18, "Contribution before ads, share of price", "=B17/B4", PCT1), (19, "Contribution after ads", "=B17-B11", USD),
            (20, "Contribution after ads, share of price", "=B19/B4", PCT1), (22, "Break-even ROAS on a first order: price ÷ contribution before ads", '=IF(B17>0,B4/B17,"loses on every order")', NUM2),
            (23, "Break-even ACOS on a first order: contribution before ads ÷ price", "=B17/B4", PCT1)]
    for r, label, f, fmt in rows:
        put(ws, f"A{r}", label, bold=r in (17, 19, 22))
        put(ws, f"B{r}", f, fmt=fmt, bold=r in (17, 19, 22))
    put(ws, "A25", "Gross margin leaves out everything an order costs after the product reaches your shelf. Contribution is what the order adds to the business.", NOTE)
    ws.column_dimensions["A"].width = 76
    ws.column_dimensions["B"].width = 16


def ads_sheet(ws, fig):
    """Lesson 2."""
    a = fig["ads"]
    ws.title = "Ad target"
    put(ws, "A1", "Ad target: the break-even from your margin, and what your last dollar returns", TITLE)
    put(ws, "A2", "Green cells come from other sheets; yellow cells are yours. Paste a campaign's days below: spend, and the sales the platform credits to it.", NOTE)
    inputs(ws, 4, [("Price", "=Contribution!B4", USD), ("Contribution before ads", "=Contribution!B17", USD),
                   ("Your ROAS target", a["target"], NUM2), ("Lifetime multiplier (Customer value sheet)", "='Customer value'!B17", NUM2)])
    rows = [(9, "Break-even ROAS on a first order: price ÷ contribution", "=B4/B5", NUM2), (10, "Break-even ACOS on a first order", "=B5/B4", PCT1),
            (11, "What one ad sale costs at your target: price ÷ target", "=B4/B6", USD), (12, "Kept (or lost, if negative) on each ad sale at your target", "=B5-B11", USD),
            (13, "Break-even ROAS with the customers who come back: first-order break-even ÷ multiplier", "=B9/B7", NUM2),
            (15, "Average ROAS over the days below: total sales ÷ total spend", f"=IFERROR(SUM(C20:C{19 + DAY_ROWS})/SUM(B20:B{19 + DAY_ROWS}),\"\")", NUM2),
            (16, "A straight line through the days: extra sales per extra dollar (a rough read of the last dollar)", f"=IFERROR(SLOPE(C20:C{19 + DAY_ROWS},B20:B{19 + DAY_ROWS}),\"\")", NUM2)]
    for r, label, f, fmt in rows:
        put(ws, f"A{r}", label, bold=r in (9, 12, 15, 16))
        put(ws, f"B{r}", f, fmt=fmt, bold=r in (9, 12, 15, 16))
    put(ws, "A17", "The straight line is a rough read. Hubricon's engine fits a curve that bends, chooses its shape out of sample, and gives the last dollar's return with an interval.", NOTE)
    for c, h in zip("ABC", ["Day", "Spend", "Sales the platform credits"]):
        put(ws, f"{c}19", h, BOLD)
    for i in range(DAY_ROWS):
        r = 20 + i
        p = a["points"][i] if i < len(a["points"]) else None
        put(ws, f"A{r}", i + 1 if p else None, fill=INPUT)
        put(ws, f"B{r}", p[0] if p else None, fmt=USD, fill=INPUT)
        put(ws, f"C{r}", p[1] if p else None, fmt=USD, fill=INPUT)
    ws.column_dimensions["A"].width = 84
    for c in "BC":
        ws.column_dimensions[c].width = 18


def customers_sheet(ws, fig):
    """Lesson 3."""
    cu = fig["customers"]
    ws.title = "Customer value"
    put(ws, "A1", "Customer value: lifetime value on revenue and on margin, against what a customer costs", TITLE)
    put(ws, "A2", "Yellow cells are yours. Read the repeat orders from your own orders (the course's reader does it in your browser), or from Hubricon's engine.", NOTE)
    inputs(ws, 4, [("First order value", cu["first"], USD), ("Repeat order value", cu["repeat"], USD),
                   ("Repeat orders a new customer makes in 52 weeks", cu["repeats_52w_new"], NUM2),
                   ("Margin rate: contribution before ads ÷ price", "=Contribution!B18", PCT1),
                   ("Acquisition cost a new customer (CAC): ad spend ÷ new customers", cu["cac"], USD),
                   ("Repeat orders in 52 weeks, the average customer already on file", cu["repeats_52w_base"], NUM2),
                   ("Annual discount rate", cu["discount"], PCT)])
    rows = [(12, "Lifetime value on revenue, 52 weeks: first + repeats × repeat value", "=B4+B6*B5", USD),
            (13, "LTV to CAC, on revenue", "=B12/B8", X2), (14, "Lifetime value on margin, 52 weeks", "=B7*B12", USD),
            (15, "LTV to CAC, on margin", "=B14/B8", X2),
            (17, "Lifetime multiplier for the ad break-even: 1 + repeats × (repeat ÷ first) × discount", "=1+B9*(B5/B4)*(1/(1+B10)^0.5)", NUM2)]
    for r, label, f, fmt in rows:
        put(ws, f"A{r}", label, bold=r in (13, 15, 17))
        put(ws, f"B{r}", f, fmt=fmt, bold=r in (13, 15, 17))
    put(ws, "A19", "The multiplier uses the customers already on file, most of whom have bought before, and a year's discount: the cautious figure, as Hubricon's engine prices it. Revenue is not what a customer is worth; margin is.", NOTE)
    ws.column_dimensions["A"].width = 84
    ws.column_dimensions["B"].width = 16


def payback_sheet(ws, fig):
    """Lesson 4."""
    pb = fig["payback"]
    ws.title = "Payback"
    put(ws, "A1", "Payback: how many months until a new customer has paid back what they cost", TITLE)
    put(ws, "A2", "Green cells come from Customer value; the repeat orders by month are yours (the course's reader counts them from your orders).", NOTE)
    inputs(ws, 4, [("First order value", "='Customer value'!B4", USD), ("Repeat order value", "='Customer value'!B5", USD),
                   ("Margin rate", "='Customer value'!B7", PCT1), ("Acquisition cost a new customer", "='Customer value'!B8", USD),
                   ("New customers a month", fig["month"]["new"], INT)])
    put(ws, "A10", "Paid back in month", BOLD)
    put(ws, "B10", '=IFERROR(MATCH("Yes",D14:D25,0),"Not within a year")', bold=True)
    put(ws, "A11", "Cash out on a month's new customers before any of it comes back")
    put(ws, "B11", "=B8*B7", fmt=USD)
    for c, h in zip("ABCD", ["Month", "Repeat orders so far, a new customer", "Margin back so far", "Paid back?"]):
        put(ws, f"{c}13", h, BOLD)
    for k in range(12):
        r = 14 + k
        put(ws, f"A{r}", k + 1)
        put(ws, f"B{r}", pb["monthly_repeats"][k], fmt=NUM2, fill=INPUT)
        put(ws, f"C{r}", f"=$B$6*($B$4+B{r}*$B$5)", fmt=USD)
        put(ws, f"D{r}", f'=IF(C{r}>=$B$7,"Yes","No")')
    put(ws, "A27", "Margin back so far = margin rate × (first order + repeat orders × repeat value). Until the month it says Yes, growth is spending cash the customers have not yet returned.", NOTE)
    ws.column_dimensions["A"].width = 60
    for c in "BCD":
        ws.column_dimensions[c].width = 22


def ranked_sheet(ws, fig):
    """Lesson 5: the numbers that mislead, on the example, by how far."""
    ws.title = "Ranked"
    put(ws, "A1", "Ranked: the numbers that mislead, on this file's own figures", TITLE)
    put(ws, "A2", "Every cell is a formula on the other sheets. Ranked on the course's example; on yours the order may differ.", NOTE)
    for c, h in zip("ABCD", ["The number", "What it says", "What is true", "How far off"]):
        put(ws, f"{c}4", h, BOLD)
    cells = {"ltv": ("'Customer value'!B13", "'Customer value'!B15", X2), "gross": ("Contribution!B14", "Contribution!B18", PCT1),
             "average": ("'Ad target'!B15", None, NUM2), "first": ("'Ad target'!B9", "'Ad target'!B13", NUM2)}
    for i, row in enumerate(fig["ranked"]):
        r = 5 + i
        says, true, fmt = cells[row["key"]]
        put(ws, f"A{r}", f"{row['number']} (true: {row['truth']})")
        put(ws, f"B{r}", f"={says}", fmt=fmt)
        if true:
            put(ws, f"C{r}", f"={true}", fmt=fmt)
        else:
            put(ws, f"C{r}", fig["ads"]["marginal"], fmt=fmt, fill=INPUT)
        put(ws, f"D{r}", f"=MAX(B{r},C{r})/MIN(B{r},C{r})", fmt=X2)
    put(ws, "A10", "The last dollar's return is the engine's curve, not a formula a spreadsheet can fit; put in your own, or use the Ad target sheet's straight line as a rough one.", NOTE)
    ws.column_dimensions["A"].width = 72
    for c in "BCD":
        ws.column_dimensions[c].width = 16


def start_sheet(ws):
    ws.title = "Start here"
    lines = [("The Operator's Math", TITLE), ("A free course from Hubricon: hubricon.com/learn/operators-math", BODY), ("", BODY),
             ("What this file does", HEAD),
             ("Contribution: what one order keeps before ads and after, and the break-even ROAS and ACOS it sets.", BODY),
             ("Ad target: your target against your break-even, and what your last ad dollar returns.", BODY),
             ("Customer value: lifetime value on revenue and on margin, LTV to CAC both ways, and the multiplier repeat customers put on the ad break-even.", BODY),
             ("Payback: the month a new customer has paid back what they cost.", BODY),
             ("Ranked: the numbers that mislead, by how far, on the file's own figures.", BODY), ("", BODY),
             ("How to use it", HEAD), ("Yellow cells are yours; green cells come from another sheet; everything else is a formula you can read.", BODY),
             (f"It opens on the course's example: {EXAMPLE['what']}. Its price, costs, customers and ads are invented; the label and payment cards are the published ones.", BODY),
             ("", BODY), ("Where the arithmetic comes from", HEAD),
             ("Hubricon's engine: cold/priors.py for the cards, models/clv.py for repeat customers and payback, models/ad_efficiency.py for the ad curve. Checked against the engine before this file was published.", BODY)]
    for i, (t, f) in enumerate(lines):
        put(ws, f"A{i + 1}", t, f)
    ws.column_dimensions["A"].width = 120


def build(path: Path, fig: dict) -> Workbook:
    wb = Workbook()
    start_sheet(wb.active)
    contribution_sheet(wb.create_sheet(), fig)
    ads_sheet(wb.create_sheet(), fig)
    customers_sheet(wb.create_sheet(), fig)
    payback_sheet(wb.create_sheet(), fig)
    ranked_sheet(wb.create_sheet(), fig)
    wb.properties.creator = "Hubricon"
    wb.properties.title = "The Operator's Math"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return wb


def recalc(path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts" / "learn"))
    from verify_fee_staircase import recalc as lo_recalc
    lo_recalc(path)


# ═══ The check ═══════════════════════════════════════════════════════════════════════════
def verify(fig: dict, cases: int = 24) -> int:
    rng = random.Random(20261004)
    problems: list[str] = []
    plans = list(priors.SHOPIFY_PAYMENTS)
    units = [{"price": round(rng.uniform(8, 140), 2), "landed": round(rng.uniform(1, 40), 2), "plan": rng.choice(plans),
              "label": round(rng.uniform(3, 14), 2), "packing": round(rng.uniform(0.2, 3), 2), "refund": round(rng.uniform(0, 0.12), 3),
              "ads": round(rng.uniform(0, 15), 2)} for _ in range(cases)]
    custs = [{"first": round(rng.uniform(10, 120), 2), "repeat": round(rng.uniform(10, 150), 2), "rep": round(rng.uniform(0, 6), 3),
              "cac": round(rng.uniform(5, 90), 2), "base": round(rng.uniform(0, 4), 3), "disc": rng.choice([0.08, 0.12, 0.2])} for _ in range(cases)]
    adays = [[(round(rng.uniform(50, 900), 2), round(rng.uniform(80, 3000), 2)) for _ in range(rng.randint(14, DAY_ROWS))] for _ in range(6)]
    with tempfile.TemporaryDirectory(prefix="hubricon-om-") as tmp:
        path = Path(tmp) / "check.xlsx"
        wb = build(path, fig)
        for k, u in enumerate(units):
            ws = wb.copy_worksheet(wb["Contribution"])
            ws.title = f"U{k}"
            rate, fixed = priors.SHOPIFY_PAYMENTS[u["plan"]]
            for ref, v in (("B4", u["price"]), ("B5", u["landed"]), ("B6", rate), ("B7", fixed), ("B8", u["label"]),
                           ("B9", u["packing"]), ("B10", u["refund"]), ("B11", u["ads"])):
                ws[ref].value = v
        for k, c in enumerate(custs):
            ws = wb.copy_worksheet(wb["Customer value"])
            ws.title = f"C{k}"
            for ref, v in (("B4", c["first"]), ("B5", c["repeat"]), ("B6", c["rep"]), ("B7", 0.3), ("B8", c["cac"]), ("B9", c["base"]), ("B10", c["disc"])):
                ws[ref].value = v
        for k, days in enumerate(adays):
            ws = wb.copy_worksheet(wb["Ad target"])
            ws.title = f"A{k}"
            for i in range(DAY_ROWS):
                p = days[i] if i < len(days) else (None, None)
                ws[f"A{20 + i}"].value = i + 1 if p[0] is not None else None
                ws[f"B{20 + i}"].value, ws[f"C{20 + i}"].value = p
        wb.save(path)
        recalc(path)
        got = load_workbook(path, data_only=True)
        for k, u in enumerate(units):
            ws = got[f"U{k}"]
            x = {"price": u["price"], "landed_cost": u["landed"], "plan": u["plan"], "refund_share": u["refund"], "packing": u["packing"]}
            want = contribution(x, u["label"])
            for ref, v in (("B15", want["fee"]), ("B17", want["before_ads"]), ("B19", want["before_ads"] - u["ads"]), ("B14", want["gross_rate"])):
                if abs(ws[ref].value - v) > 1.5e-4:
                    problems.append(f"U{k} {ref}: sheet {ws[ref].value} engine {v}")
            if want["before_ads"] > 0 and abs(ws["B22"].value - u["price"] / want["before_ads"]) > 1e-3:
                problems.append(f"U{k} break-even ROAS: sheet {ws['B22'].value}")
        for k, c in enumerate(custs):
            ws = got[f"C{k}"]
            rev = c["first"] + c["rep"] * c["repeat"]
            mult = 1.0 + c["base"] * (c["repeat"] / c["first"]) / (1 + c["disc"]) ** 0.5
            for ref, v in (("B12", rev), ("B13", rev / c["cac"]), ("B14", 0.3 * rev), ("B15", 0.3 * rev / c["cac"]), ("B17", mult)):
                if abs(ws[ref].value - v) > 1e-6 * max(1, abs(v)):
                    problems.append(f"C{k} {ref}: sheet {ws[ref].value} expected {v}")
        for k, days in enumerate(adays):
            ws = got[f"A{k}"]
            s = np.array([d[0] for d in days])
            v = np.array([d[1] for d in days])
            if abs(ws["B15"].value - v.sum() / s.sum()) > 1e-9:
                problems.append(f"A{k} average ROAS: sheet {ws['B15'].value}")
            if abs(ws["B16"].value - float(np.polyfit(s, v, 1)[0])) > 1e-6:
                problems.append(f"A{k} slope: sheet {ws['B16'].value}")
        # the example, against the figures and the engine
        u, cu, a, pb = fig["unit"], fig["customers"], fig["ads"], fig["payback"]
        co, ad, cv, py = got["Contribution"], got["Ad target"], got["Customer value"], got["Payback"]
        checks = [(co["B17"].value, u["before_ads"], 1e-3), (co["B19"].value, u["after_ads"], 1e-3), (ad["B9"].value, a["be_roas"], 1e-3),
                  (ad["B15"].value, a["average"], 0.02), (ad["B16"].value, a["slope"], 1e-3), (cv["B13"].value, cu["rev_ltv_cac"], 1e-3),
                  (cv["B14"].value, cu["margin_ltv"], 0.02), (cv["B17"].value, cu["multiplier"], 2e-3), (ad["B13"].value, a["life_be_roas"], 2e-3)]
        for i, (sheet_v, fig_v, tol) in enumerate(checks):
            if sheet_v is None or abs(sheet_v - fig_v) > tol:
                problems.append(f"Example check {i}: sheet {sheet_v} figures {fig_v}")
        if py["B10"].value != pb["month"]:
            problems.append(f"Payback month: sheet {py['B10'].value} figures {pb['month']}")
        # the engine's own payback, at month ends, against the sheet's margin back
        rate = contribution(EXAMPLE, u["label"])["rate"]      # unrounded, as the sheet computes it
        for k in range(12):
            want = rate * (cu["first"] + pb["monthly_repeats"][k] * cu["repeat"])
            if abs(py[f"C{14 + k}"].value - want) > 1e-3:
                problems.append(f"Payback month {k + 1}: sheet {py[f'C{14 + k}'].value} engine {want}")
    # the browser's customer reading, held to this file's reference
    golden = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else None
    if golden:
        orders, _ = simulate()
        text, ref = orders_csv(orders)
        if text != golden["csv"]:
            problems.append("operators-math.golden.json is stale: re-run with --publish")
        elif customer_curve(ref) != golden["expect"]:
            problems.append("the customer curve reference moved: re-run with --publish")
    for p in problems:
        print("  ✗", p)
    print(f"{len(units) + len(custs) + len(adays)} golden cases, the example and the engine's payback: {'all agree' if not problems else f'{len(problems)} disagree'}")
    return len(problems)


if __name__ == "__main__":
    fig = figures()
    FIGURES.write_text(json.dumps(fig, indent=1) + "\n")
    u, a, cu, pb = fig["unit"], fig["ads"], fig["customers"], fig["payback"]
    print(f"contribution {u['before_ads']} ({u['rate']}), after ads {u['after_ads']}; break-even ROAS {a['be_roas']}; "
          f"average {a['average']} vs last dollar {a['marginal']} ({a['marginal_p5']}–{a['marginal_p95']}), break-even spend {a['breakeven']}/day "
          f"vs {a['spend']}; lifetime break-even ROAS {a['life_be_roas']} (spend {a['life_breakeven']})")
    print(f"customers {cu['n']}, repeats/52w new {cu['repeats_52w_new']} (truth {fig['truth']['repeats_52w_new']}), multiplier {cu['multiplier']}, "
          f"CAC {cu['cac']}, LTV:CAC revenue {cu['rev_ltv_cac']} margin {cu['margin_ltv_cac']}; payback {pb['weeks']} weeks {pb['band']}, month {pb['month']}")
    print("ranked:", [(r["key"], r["factor"]) for r in fig["ranked"]])
    print(f"wrote {FIGURES.relative_to(ROOT)}")
    if "--figures-only" in sys.argv:
        raise SystemExit(0)
    if "--publish" in sys.argv:
        orders, _ = simulate()
        text, ref = orders_csv(orders)
        cv = customer_curve(ref)
        GOLDEN.write_text(json.dumps({"about": "A synthetic Shopify Orders export (the first customers of The Operator's Math's invented store) "
                                               "and what assets/cohorts.mjs must read from it: scripts/learn/operators_math.py customer_curve.",
                                      "margin_rate": u["rate"], "cac": cu["cac"], "payback_month": payback_month(cv, u["rate"], cu["cac"]),
                                      "csv": text, "expect": cv}, indent=1) + "\n")
    if verify(fig):
        raise SystemExit(1)
    if "--publish" in sys.argv:
        build(FILE, fig)
        recalc(FILE)
        STAMP.write_text(json.dumps({"file": str(FILE.relative_to(ROOT)), "file_sha256": hashlib.sha256(FILE.read_bytes()).hexdigest(),
                                     "sources_sha256": fig["sources"], "verified_on": date.today().isoformat()}, indent=2) + "\n")
        print(f"published {FILE.relative_to(ROOT)}, {STAMP.relative_to(ROOT)} and {GOLDEN.relative_to(ROOT)}")
