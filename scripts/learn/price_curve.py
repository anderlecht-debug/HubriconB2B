"""The Price Curve: the course's worked example, its spreadsheet, and the check that holds
the spreadsheet to Hubricon's engine.

    cd engine && uv run --with openpyxl python ../scripts/learn/price_curve.py             # figures, then verify
    cd engine && uv run --with openpyxl python ../scripts/learn/price_curve.py --publish   # ...and ship the file

1. FIGURES. The worked example is an invented listing: an invented price history and
   invented costs, with Amazon's published fees. Every figure the course prints from it is
   computed here by the engine itself (models/elasticity.py `_fit`, models/pricing_engine.py
   `optimal_price`, `profit`, `profit_delta`, `near_unit_elastic`, cold/priors.py's
   fulfilment fee and referral rate) and written to data/learn-price-curve.json, which
   scripts/build-pages.mjs bakes into learn/price-curve.html. Nothing on the page is typed.

2. TEMPLATE. learn/files/hubricon-price-curve.xlsx: the same arithmetic as formulas, five
   sheets, opened on the example so it shows what it does before anything is typed.

3. VERIFY. Golden cases: random price histories through the engine's fit and through the
   recalculated "Your history" sheet, and random catalogues through the engine's optimum,
   guard and profit and through the "Catalogue" sheet, figure by figure. The example's own
   "Your price" and "Discount" sheets are checked against the figures in (1).

--publish then rebuilds the shipped file, recalculates it in LibreOffice (so a viewer that
does not calculate still shows numbers) and writes scripts/learn/price-curve.stamp.json:
the hashes of the engine sources it was checked against and of the file itself.
scripts/learn/price-curve.test.mjs fails when either has moved without a re-run.

Needs LibreOffice (soffice) on PATH.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from hubricon_engine.cold import priors  # noqa: E402
from hubricon_engine.models import elasticity, pricing_engine  # noqa: E402
from hubricon_engine.models.elasticity import MIN_PERIODS, MIN_PRICE_CV, _fit  # noqa: E402
from hubricon_engine.models.pricing_engine import (  # noqa: E402
    POLE_GUARD_SIGMAS, POLE_OPTIMUM_LOG_SD, STEP_CAP, near_unit_elastic, optimal_price, profit, profit_delta,
)

FILE = ROOT / "learn" / "files" / "hubricon-price-curve.xlsx"
FIGURES = ROOT / "data" / "learn-price-curve.json"
STAMP = ROOT / "scripts" / "learn" / "price-curve.stamp.json"
ENGINE_SOURCES = ["engine/src/hubricon_engine/models/elasticity.py", "engine/src/hubricon_engine/models/pricing_engine.py"]
PRICED_ON = date(2026, 9, 30)          # the card the example's fulfilment fee is read from
TOL = 1.5e-4                           # the engine rounds to four places

HISTORY_ROWS = 26                      # a year of half-months
CATALOGUE_ROWS = 50
EDGES = (10.0, 50.0)                   # Amazon's price-band edges, where the fulfilment fee itself changes


# ═══ 1. The worked example ═════════════════════════════════════════════════════════════════
# Invented: the history is drawn from a curve with an elasticity the reader never sees, plus
# noise, so the fit has something honest to find. The costs are invented; the fees are
# Amazon's, read from the engine's card.
EXAMPLE = {
    "what": "an invented stainless garlic press",
    "category": "home & kitchen",
    "tier": "large_standard",
    "weight_oz": 12.0,
    "price": 24.99,
    "landed_cost": 6.20,
    "other_fixed": 0.0,
    "true_elasticity": -1.6,       # the draw's, never printed
    "per_day_at_price": 17.0,
    "noise_sd": 0.06,
    "seed": 20261177,              # a draw whose standard error sits at the median of 200 (figures()["runs"])
    "periods": [                   # half-months, February to July 2026: label, days, price
        ("Feb 1–14", 14, 24.99), ("Feb 15–28", 14, 24.99), ("Mar 1–15", 15, 22.99), ("Mar 16–31", 16, 22.99),
        ("Apr 1–15", 15, 26.99), ("Apr 16–30", 15, 26.99), ("May 1–15", 15, 23.99), ("May 16–31", 16, 27.49),
        ("Jun 1–15", 15, 21.99), ("Jun 16–30", 15, 25.49), ("Jul 1–15", 15, 24.99), ("Jul 16–31", 16, 24.99),
    ],
    "runs": 200,                   # the same price test, run again on fresh noise
    "run_seed_from": 20261000,
    "discount": 0.20,
    "near_pole": {"elasticity": -1.15, "std_err": 0.22, "dof": 8},
    "inelastic": {"elasticity": -0.6, "std_err": 0.18, "dof": 8},
}


def example_history(seed: int | None = None) -> list[dict]:
    rng = np.random.default_rng(EXAMPLE["seed"] if seed is None else seed)
    rows = []
    for label, days, price in EXAMPLE["periods"]:
        mean = EXAMPLE["per_day_at_price"] * days * (price / EXAMPLE["price"]) ** EXAMPLE["true_elasticity"]
        units = int(round(mean * math.exp(rng.normal(0.0, EXAMPLE["noise_sd"]))))
        rows.append({"label": label, "days": days, "units": units, "price": price})
    return rows


def ci_of(eps: float, se: float, dof: int) -> tuple[float, float]:
    from scipy import stats
    t = float(stats.t.ppf(0.975, dof))
    return eps - t * se, eps + t * se


def guarded(eps: float, se: float, ci: tuple[float, float]) -> bool:
    return bool(near_unit_elastic(eps, se, list(ci)))


def direction(eps: float, p0: float, best: float | None, guard: bool) -> str:
    """The sheet's rule: toward the best price; up where there is none to walk to."""
    if best is not None:
        return "up" if best > p0 else ("down" if best < p0 else "hold")
    return "up" if (eps >= -1 or guard) else "hold"


def step_price(p0: float, best: float | None, way: str) -> float:
    """One step toward the best price, never more than the 5% the terms authorise."""
    if way == "up":
        gap = (best / p0 - 1) if best is not None else STEP_CAP
        return round(p0 * (1 + min(STEP_CAP, gap)), 2)
    if way == "down":
        return round(p0 * (1 - min(STEP_CAP, 1 - best / p0)), 2)
    return round(p0, 2)


def crosses_edge(a: float, b: float) -> bool:
    lo, hi = min(a, b), max(a, b)
    return (lo < EDGES[0] <= hi) or (lo <= EDGES[1] < hi)


def figures() -> dict:
    hist = example_history()
    fit = _fit([{"price": r["price"], "units": r["units"], "days": r["days"]} for r in hist])
    assert fit["status"] == "ok", fit
    eps, se = fit["elasticity"], fit["std_err"]
    ci = tuple(fit["details"]["ci95"])
    lx = np.log([r["price"] for r in hist])
    ly = np.log([r["units"] / r["days"] for r in hist])
    intercept = float(ly.mean() - eps * lx.mean())       # the line the chart draws, through the means
    guard = guarded(eps, se, ci)
    p0, c, other = EXAMPLE["price"], EXAMPLE["landed_cost"], EXAMPLE["other_fixed"]
    f = priors.REFERRAL_BY_CATEGORY[EXAMPLE["category"]]
    fba = priors.fulfilment_fee(EXAMPLE["tier"], EXAMPLE["weight_oz"], p0, PRICED_ON, priors.card_named("non_peak"))
    fixed = round(fba + other, 4)
    days = sum(r["days"] for r in hist if r["price"] == p0)
    units_at_p0 = sum(r["units"] for r in hist if r["price"] == p0)
    q0 = int(round(units_at_p0 / days * 30))
    m0 = p0 * (1 - f) - c - fixed
    best = None if guard else optimal_price(eps, c, f, fixed)
    way = direction(eps, p0, best, guard)
    p1 = step_price(p0, best, way)
    month_now = float(profit(eps, p0, q0, c, f, p0, fixed))
    step_delta = float(profit_delta(eps, p0, q0, c, f, p1, fixed))
    best_delta = float(profit_delta(eps, p0, q0, c, f, best, fixed)) if best else None

    def row(change: float) -> dict:
        p = p0 * (1 + change)
        m = p * (1 - f) - c - fixed
        return {"change": change, "price": p, "margin": m,
                "breakeven": (m0 / m - 1) if m > 0 else None,
                "implied": (p / p0) ** eps - 1,
                "delta": float(profit_delta(eps, p0, q0, c, f, p, fixed))}
    table = [row(k / 100) for k in (-10, -5, -2, 2, 5, 10)]

    d = EXAMPLE["discount"]
    pd = p0 * (1 - d)
    md = pd * (1 - f) - c - fixed
    disc = {"rate": d, "price": pd, "margin": md, "needed": m0 / md - 1, "implied": (1 - d) ** eps - 1,
            "delta": float(profit_delta(eps, p0, q0, c, f, pd, fixed))}

    def side(case: dict) -> dict:
        lo, hi = ci_of(case["elasticity"], case["std_err"], case["dof"])
        g = guarded(case["elasticity"], case["std_err"], (lo, hi))
        b = None if g else optimal_price(case["elasticity"], c, f, fixed)
        return {**case, "ci": [lo, hi], "guard": g, "best": b,
                "direction": direction(case["elasticity"], p0, b, g),
                "pole_factor": case["elasticity"] / (1 + case["elasticity"]) if case["elasticity"] != -1 else None}

    # The same price test, run again on fresh noise: what one SKU's history can and cannot tell.
    runs = []
    for k in range(EXAMPLE["runs"]):
        h = example_history(EXAMPLE["run_seed_from"] + k)
        rf = _fit([{"price": r["price"], "units": r["units"], "days": r["days"]} for r in h])
        g = guarded(rf["elasticity"], rf["std_err"], tuple(rf["details"]["ci95"]))
        b = None if g else optimal_price(rf["elasticity"], c, f, fixed)
        runs.append({"se": rf["std_err"], "eps": rf["elasticity"], "guard": g,
                     "way": direction(rf["elasticity"], p0, b, g)})
    ses = sorted(r["se"] for r in runs)
    pick = lambda q: ses[int(q * (len(ses) - 1))]  # noqa: E731
    runs_summary = {"runs": len(runs), "true_elasticity": EXAMPLE["true_elasticity"],
                    "se_p10": pick(0.1), "se_p50": pick(0.5), "se_p90": pick(0.9),
                    "guard_share": sum(r["guard"] for r in runs) / len(runs),
                    "up_share": sum(r["way"] == "up" for r in runs) / len(runs),
                    "true_direction": direction(EXAMPLE["true_elasticity"], p0,
                                                optimal_price(EXAMPLE["true_elasticity"], c, f, fixed), False)}

    return {
        "about": "Generated by scripts/learn/price_curve.py from Hubricon's engine. An invented listing: the history and costs are invented, the fees are Amazon's. Do not edit.",
        "engine_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ENGINE_SOURCES},
        "priced_on": PRICED_ON.isoformat(),
        "what": EXAMPLE["what"], "category": EXAMPLE["category"], "weight_oz": EXAMPLE["weight_oz"],
        "history": hist,
        "fit": {"intercept": intercept, "n": fit["n_periods"], "price_cv": fit["price_cv"], "elasticity": eps, "std_err": se,
                "std_err_classical": fit["details"]["std_err_classical"], "ci": list(ci), "dof": fit["details"]["dof"],
                "t": fit["details"]["t_critical"], "r_squared": fit["r_squared"], "guard": guard},
        "rules": {"min_periods": MIN_PERIODS, "min_price_cv": MIN_PRICE_CV, "step_cap": STEP_CAP,
                  "pole_sigmas": POLE_GUARD_SIGMAS, "pole_optimum_log_sd": POLE_OPTIMUM_LOG_SD},
        "economics": {"price": p0, "units_month": q0, "landed_cost": c, "referral": f, "fba_fee": fba,
                      "other_fixed": other, "fixed": fixed, "margin": m0, "profit_month": month_now},
        "best": {"price": best, "factor": eps / (1 + eps), "gross_cost": fixed + c, "base": (c + fixed) / (1 - f),
                 "direction": way, "step_price": p1, "step_delta": step_delta, "best_delta": best_delta,
                 "crosses_edge": crosses_edge(p0, best or p1)},
        "table": table,
        "discount": disc,
        "runs": runs_summary,
        "near_pole": side(EXAMPLE["near_pole"]),
        "inelastic": side(EXAMPLE["inelastic"]),
    }


# ═══ 2. The spreadsheet ════════════════════════════════════════════════════════════════════
INPUT = PatternFill("solid", fgColor="FFF2CC")       # yellow: the reader's cells
WORK = PatternFill("solid", fgColor="F2F4F7")        # grey: the working
HEAD = Font(name="Arial", bold=True, size=11)
TITLE = Font(name="Arial", bold=True, size=16)
BODY = Font(name="Arial", size=10)
NOTE = Font(name="Arial", size=9, italic=True, color="555555")
BOLD = Font(name="Arial", bold=True, size=10)
THIN = Side(style="thin", color="CDD2DA")
USD, USD4, PCT, PCT1, NUM2, NUM4 = '"$"#,##0.00', '"$"#,##0.0000', "0%", "0.0%", "0.00", "0.0000"
SIGNED_USD = '"+$"#,##0;"−$"#,##0;"$0"'
SIGNED_PCT = '+0.0%;−0.0%;0.0%'


def put(ws, ref, value, font=BODY, fmt=None, fill=None, bold=False, wrap=False):
    cell = ws[ref]
    cell.value = value
    cell.font = BOLD if bold else font
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    if wrap:
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    return cell


def history_sheet(ws, rows: list[dict]) -> None:
    ws.title = "Your history"
    put(ws, "A1", "Your history: read your elasticity from your own sales", TITLE)
    put(ws, "A2", "One row per period. Yellow cells are yours. The grey columns are the working, so you can check every step.", NOTE)
    for col, head in zip("ABCD", ["Period", "Days in it", "Units sold", "Average price ($)"]):
        put(ws, f"{col}4", head, HEAD)
    for col, head in zip("FGHIJKLMN", ["Used", "ln price", "ln units a day", "x − x̄", "y − ȳ", "Residual", "Leverage", "HC3 term", "(price − mean)²"]):
        put(ws, f"{col}4", head, HEAD, fill=WORK)
    first, last = 5, 5 + HISTORY_ROWS - 1
    for i in range(HISTORY_ROWS):
        r = first + i
        row = rows[i] if i < len(rows) else None
        put(ws, f"A{r}", row["label"] if row else None, fill=INPUT)
        put(ws, f"B{r}", row["days"] if row else None, fill=INPUT, fmt="0")
        put(ws, f"C{r}", row["units"] if row else None, fill=INPUT, fmt="#,##0")
        put(ws, f"D{r}", row["price"] if row else None, fill=INPUT, fmt=USD)
        put(ws, f"F{r}", f"=IF(AND(ISNUMBER(C{r}),ISNUMBER(D{r})),IF(AND(C{r}>0,D{r}>0),1,0),0)", fill=WORK, fmt="0")
        put(ws, f"G{r}", f"=IF(F{r}=1,LN(D{r}),0)", fill=WORK, fmt=NUM4)
        put(ws, f"H{r}", f"=IF(F{r}=1,LN(C{r}/IF(ISNUMBER(B{r}),IF(B{r}>0,B{r},1),1)),0)", fill=WORK, fmt=NUM4)
        put(ws, f"I{r}", f"=IF(F{r}=1,G{r}-$Q$8,0)", fill=WORK, fmt=NUM4)
        put(ws, f"J{r}", f"=IF(F{r}=1,H{r}-$Q$9,0)", fill=WORK, fmt=NUM4)
        put(ws, f"K{r}", f"=IF(F{r}=1,J{r}-$Q$12*I{r},0)", fill=WORK, fmt=NUM4)
        put(ws, f"L{r}", f"=IF(F{r}=1,1/$Q$5+I{r}^2/$Q$10,0)", fill=WORK, fmt=NUM4)
        put(ws, f"M{r}", f"=IF(F{r}=1,IFERROR(I{r}^2*K{r}^2/(1-L{r})^2,0),0)", fill=WORK, fmt="0.000000")
        put(ws, f"N{r}", f"=IF(F{r}=1,(D{r}-$Q$6)^2,0)", fill=WORK, fmt=NUM4)
    R = f"{first}:{last}"
    rng = lambda c: f"{c}{first}:{c}{last}"  # noqa: E731
    results = [
        (5, "Periods used", f"=SUM({rng('F')})", "0"),
        (6, "Average price", f"=IFERROR(SUMPRODUCT({rng('F')},{rng('D')})/Q5,\"\")", USD),
        (7, "Price variation (CV)", f"=IFERROR(SQRT(SUM({rng('N')})/Q5)/Q6,\"\")", PCT1),
        (8, "Mean ln price (x̄)", f"=IFERROR(SUM({rng('G')})/Q5,0)", NUM4),
        (9, "Mean ln units a day (ȳ)", f"=IFERROR(SUM({rng('H')})/Q5,0)", NUM4),
        (10, "Sxx", f"=SUMPRODUCT({rng('I')},{rng('I')})", "0.000000"),
        (11, "Sxy", f"=SUMPRODUCT({rng('I')},{rng('J')})", "0.000000"),
        (12, "Elasticity", "=IFERROR(Q11/Q10,\"\")", NUM2),
        (13, "Intercept", "=IFERROR(Q9-Q12*Q8,\"\")", NUM4),
        (14, "Degrees of freedom", "=Q5-2", "0"),
        (15, "Residual sum of squares", f"=SUMSQ({rng('K')})", "0.000000"),
        (16, "R²", f"=IFERROR(1-Q15/SUMPRODUCT({rng('J')},{rng('J')}),\"\")", NUM2),
        (17, "Leverage too high for HC3", f"=IF(MAX({rng('L')})>=1-0.000001,\"yes: classical\",\"no\")", None),
        (18, "Standard error (HC3)", f"=IFERROR(IF(Q17=\"no\",SQRT(SUM({rng('M')})/Q10^2),SQRT(Q15/Q14/Q10)),\"\")", NUM2),
        (19, "t for 95%", "=IFERROR(TINV(0.05,Q14),\"\")", NUM2),
        (20, "95% interval: low", "=IFERROR(Q12-Q19*Q18,\"\")", NUM2),
        (21, "95% interval: high", "=IFERROR(Q12+Q19*Q18,\"\")", NUM2),
        (22, "Status", f"=IF(Q5<{MIN_PERIODS},\"Too few periods: {MIN_PERIODS} is the least\",IF(Q7<{MIN_PRICE_CV},\"The price has not moved enough to read: 2% is the least\",\"Read\"))", None),
        (23, "Near −1?", f"=IF(Q22<>\"Read\",\"\",IF(OR(AND(Q20<=-1,Q21>=-1),ABS(1+Q12)<{POLE_GUARD_SIGMAS}*Q18,AND(Q12<-1,Q18/ABS(Q12*(1+Q12))>{POLE_OPTIMUM_LOG_SD})),\"Too close to −1 to name a price\",\"Clear of −1\"))", None),
    ]
    put(ws, "P4", "The fit", HEAD)
    for r, label, formula, fmt in results:
        put(ws, f"P{r}", label, BOLD if r in (12, 18, 22, 23) else BODY)
        put(ws, f"Q{r}", formula, BOLD if r in (12, 18, 22, 23) else BODY, fmt=fmt)
    put(ws, "P25", "Read the elasticity with its interval. A wide one is the answer, not a failure.", NOTE)
    put(ws, "P26", "Units are per day before the log, so a 16-day period is not read as a better one.", NOTE)
    for col, width in zip("ABCDEFGHIJKLMNOPQ", [12, 10, 11, 16, 3, 7, 9, 13, 9, 9, 9, 9, 10, 14, 3, 30, 22]):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A5"


def price_sheet(ws, fig: dict) -> None:
    ws.title = "Your price"
    e = fig["economics"]
    put(ws, "A1", "Your price: the best price, the next step, and what a change costs", TITLE)
    put(ws, "A2", "Yellow cells are yours. The elasticity comes from Your history; type over it to try another.", NOTE)
    inputs = [
        (4, "Today's price", e["price"], USD), (5, "Units a month at today's price", e["units_month"], "#,##0"),
        (6, "Landed cost per unit", e["landed_cost"], USD), (7, "Referral rate", e["referral"], PCT),
        (8, "Fulfilment fee per unit", e["fba_fee"], USD), (9, "Storage and other per-unit costs", e["other_fixed"], USD),
        (10, "Elasticity", "='Your history'!Q12", NUM2), (11, "Standard error", "='Your history'!Q18", NUM2),
        (12, "95% interval: low", "='Your history'!Q20", NUM2), (13, "95% interval: high", "='Your history'!Q21", NUM2),
        (14, "Status of the fit", "='Your history'!Q22", None),
    ]
    for r, label, value, fmt in inputs:
        put(ws, f"A{r}", label)
        put(ws, f"B{r}", value, fmt=fmt, fill=INPUT)
    out = [
        (16, "Cost per unit that doesn't move with price", "=B6+B8+B9", USD),
        (17, "Contribution per unit today", "=B4*(1-B7)-B16", USD),
        (18, "Profit a month today", "=B5*B17", USD),
        (19, "Near −1?", f"=IF(B14<>\"Read\",\"\",IF(OR(AND(B12<=-1,B13>=-1),ABS(1+B10)<{POLE_GUARD_SIGMAS}*B11,AND(B10<-1,B11/ABS(B10*(1+B10))>{POLE_OPTIMUM_LOG_SD})),\"yes\",\"no\"))", None),
        (20, "Best price", "=IF(AND(B14=\"Read\",B19=\"no\",B10<-1,B16>0,B7<1),B16/(1-B7)*B10/(1+B10),\"none\")", USD),
        (21, "Why there is none", "=IF(ISNUMBER(B20),\"\",IF(B14<>\"Read\",\"The fit is not read yet: see Your history.\",IF(B10>=-1,\"Demand this inelastic has no best price: profit rises with the price. Walk up and measure.\",\"Too close to −1: the direction is up, the distance is unknown.\")))", None),
        (22, "Direction", "=IF(ISNUMBER(B20),IF(B20>B4,\"up\",IF(B20<B4,\"down\",\"hold\")),IF(B14<>\"Read\",\"hold\",IF(OR(B10>=-1,B19=\"yes\"),\"up\",\"hold\")))", None),
        (23, "Next price (one step, at most 5%)", f"=ROUND(IF(B22=\"up\",B4*(1+MIN({STEP_CAP},IF(ISNUMBER(B20),B20/B4-1,{STEP_CAP}))),IF(B22=\"down\",B4*(1-MIN({STEP_CAP},1-B20/B4)),B4)),2)", USD),
        (24, "Profit a month at the next price", "=B5*(B23/B4)^B10*(B23*(1-B7)-B16)", USD),
        (25, "Change a month", "=B24-B18", SIGNED_USD),
        (26, "Change a month at the best price", "=IF(ISNUMBER(B20),B5*(B20/B4)^B10*(B20*(1-B7)-B16)-B18,\"\")", SIGNED_USD),
        (27, "Fee edge in between?", f"=IF(OR(AND(MIN(B4,IF(ISNUMBER(B20),B20,B23))<{EDGES[0]},MAX(B4,IF(ISNUMBER(B20),B20,B23))>={EDGES[0]}),AND(MIN(B4,IF(ISNUMBER(B20),B20,B23))<={EDGES[1]},MAX(B4,IF(ISNUMBER(B20),B20,B23))>{EDGES[1]})),\"Yes: Amazon's fulfilment fee changes at $10 and $50. Price both sides on The Fee Staircase sheet.\",\"No\")", None),
    ]
    for r, label, formula, fmt in out:
        put(ws, f"A{r}", label, bold=r in (20, 23, 25))
        put(ws, f"B{r}", formula, fmt=fmt, bold=r in (20, 23, 25))
    put(ws, "A29", "What a change in price costs you, and what your elasticity says it does", HEAD)
    for col, head in zip("ABCDEF", ["Change", "Price", "Contribution per unit", "Units can fall (or must rise) by", "Your elasticity says units move", "Profit change a month"]):
        put(ws, f"{col}30", head, BOLD)
    for i, k in enumerate(range(-10, 11)):
        r = 31 + i
        put(ws, f"A{r}", k / 100, fmt=SIGNED_PCT)
        put(ws, f"B{r}", f"=$B$4*(1+A{r})", fmt=USD)
        put(ws, f"C{r}", f"=B{r}*(1-$B$7)-$B$16", fmt=USD)
        put(ws, f"D{r}", f"=IF(C{r}>0,$B$17/C{r}-1,\"loses on every unit\")", fmt=SIGNED_PCT)
        put(ws, f"E{r}", f"=(B{r}/$B$4)^$B$10-1", fmt=SIGNED_PCT)
        put(ws, f"F{r}", f"=$B$5*(B{r}/$B$4)^$B$10*C{r}-$B$18", fmt=SIGNED_USD)
    put(ws, "A53", "Break-even: profit is unchanged when units change by (contribution today ÷ contribution at the new price) − 1.", NOTE)
    for col, width in zip("ABCDEF", [44, 16, 20, 30, 30, 22]):
        ws.column_dimensions[col].width = width


def discount_sheet(ws, fig: dict) -> None:
    ws.title = "Discount"
    put(ws, "A1", "Discount: what a sale has to sell to pay for itself", TITLE)
    put(ws, "A2", "Today's price, costs and elasticity come from Your price. Yellow cells are yours.", NOTE)
    rows = [
        (4, "Discount", fig["discount"]["rate"], PCT, True),
        (5, "Any fee per unit sold on the deal (a coupon's, a deal's)", 0, USD, True),
        (7, "Price on the discount", "='Your price'!B4*(1-B4)", USD, False),
        (8, "Contribution per unit on the discount", "=B7*(1-'Your price'!B7)-'Your price'!B16-B5", USD, False),
        (9, "Contribution per unit today", "='Your price'!B17", USD, False),
        (10, "Extra units it must sell to break even", "=IF(B8>0,B9/B8-1,\"none: every unit loses money\")", SIGNED_PCT, False),
        (11, "Extra units your elasticity says it sells", "=(1-B4)^'Your price'!B10-1", SIGNED_PCT, False),
        (12, "Profit change a month, at your elasticity", "='Your price'!B5*(1+B11)*B8-'Your price'!B18", SIGNED_USD, False),
        (13, "Verdict", "=IF(NOT(ISNUMBER(B10)),\"Loses money on every unit sold.\",IF(B11>=B10,\"Pays for itself at your elasticity.\",\"Costs you money at your elasticity.\"))", None, False),
    ]
    for r, label, value, fmt, inp in rows:
        put(ws, f"A{r}", label, bold=r in (10, 11, 13))
        put(ws, f"B{r}", value, fmt=fmt, fill=INPUT if inp else None, bold=r in (10, 11, 13))
    put(ws, "A15", "A discount that wins a better rank can be worth more later; that is a bet on rank, and this sheet does not price it.", NOTE)
    ws.column_dimensions["A"].width = 56
    ws.column_dimensions["B"].width = 26


def catalogue_sheet(ws, rows: list[dict] | None = None) -> None:
    ws.title = "Catalogue"
    put(ws, "A1", "Catalogue: every SKU, in order of what its next step is worth", TITLE)
    put(ws, "A2", "One row per SKU. Copy each SKU's elasticity, standard error and interval from its own Your history. Yellow cells are yours.", NOTE)
    heads = ["SKU", "Price", "Units a month", "Landed cost", "Referral rate", "Fixed fees per unit", "Elasticity", "Standard error",
             "Interval low", "Interval high", "Contribution today", "Near −1?", "Best price", "Direction", "Next price", "Change a month", "Rank"]
    for i, h in enumerate(heads):
        put(ws, f"{get_column_letter(i + 1)}4", h, HEAD, fill=INPUT if i < 10 else None)
    for i in range(CATALOGUE_ROWS):
        r = 5 + i
        v = rows[i] if rows and i < len(rows) else None
        for j, key in enumerate(["sku", "price", "units", "cost", "referral", "fixed", "eps", "se", "lo", "hi"]):
            fmt = {1: USD, 2: "#,##0", 3: USD, 4: PCT, 5: USD, 6: NUM2, 7: NUM2, 8: NUM2, 9: NUM2}.get(j)
            put(ws, f"{get_column_letter(j + 1)}{r}", v[key] if v else None, fmt=fmt, fill=INPUT)
        ok = f"AND(ISNUMBER(B{r}),ISNUMBER(G{r}),ISNUMBER(H{r}))"
        put(ws, f"K{r}", f"=IF({ok},B{r}*(1-E{r})-D{r}-F{r},\"\")", fmt=USD)
        put(ws, f"L{r}", f"=IF({ok},IF(OR(AND(I{r}<=-1,J{r}>=-1),ABS(1+G{r})<{POLE_GUARD_SIGMAS}*H{r},AND(G{r}<-1,H{r}/ABS(G{r}*(1+G{r}))>{POLE_OPTIMUM_LOG_SD})),\"yes\",\"no\"),\"\")")
        put(ws, f"M{r}", f"=IF({ok},IF(AND(L{r}=\"no\",G{r}<-1,D{r}+F{r}>0,E{r}<1),(D{r}+F{r})/(1-E{r})*G{r}/(1+G{r}),\"none\"),\"\")", fmt=USD)
        put(ws, f"N{r}", f"=IF({ok},IF(ISNUMBER(M{r}),IF(M{r}>B{r},\"up\",IF(M{r}<B{r},\"down\",\"hold\")),IF(OR(G{r}>=-1,L{r}=\"yes\"),\"up\",\"hold\")),\"\")")
        put(ws, f"O{r}", f"=IF({ok},ROUND(IF(N{r}=\"up\",B{r}*(1+MIN({STEP_CAP},IF(ISNUMBER(M{r}),M{r}/B{r}-1,{STEP_CAP}))),IF(N{r}=\"down\",B{r}*(1-MIN({STEP_CAP},1-M{r}/B{r})),B{r})),2),\"\")", fmt=USD)
        put(ws, f"P{r}", f"=IF({ok},C{r}*(O{r}/B{r})^G{r}*(O{r}*(1-E{r})-D{r}-F{r})-C{r}*K{r},\"\")", fmt=SIGNED_USD)
        put(ws, f"Q{r}", f"=IF(ISNUMBER(P{r}),RANK(P{r},$P$5:$P${4 + CATALOGUE_ROWS}),\"\")", fmt="0")
    widths = [16, 10, 12, 11, 11, 13, 10, 11, 11, 11, 13, 9, 11, 10, 11, 14, 6]
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w
    ws.freeze_panes = "B5"


def start_sheet(ws, fig: dict) -> None:
    ws.title = "Start here"
    lines = [
        ("The Price Curve", TITLE),
        ("A free course from Hubricon: hubricon.com/learn/price-curve", BODY),
        ("", BODY),
        ("What this file does", HEAD),
        ("Your history reads your price elasticity from your own sales: how much your units move when your price does.", BODY),
        ("Your price turns it into the price that makes the most, the next step toward it (never more than 5%), and what any change costs.", BODY),
        ("Discount tells you how many extra units a sale has to sell to pay for itself, and how many your elasticity says it will.", BODY),
        ("Catalogue ranks every SKU by what its next step is worth.", BODY),
        ("", BODY),
        ("How to use it", HEAD),
        ("Yellow cells are yours. Everything else is a formula, and the grey columns show the working.", BODY),
        (f"It opens on an example: {fig['what']}. The history and the costs are invented; the fees are Amazon's, from its published 2026 schedule. Type over it.", BODY),
        ("", BODY),
        ("Where the arithmetic comes from", HEAD),
        ("The same arithmetic Hubricon's engine runs (models/elasticity.py and models/pricing_engine.py), checked against it figure by figure before this file was published.", BODY),
        ("What one sheet cannot do: pool a SKU with its neighbours, correct for prices you set because demand moved, or put a range around the profit. The course says what each is for.", BODY),
    ]
    for i, (text, font) in enumerate(lines):
        put(ws, f"A{i + 1}", text, font, wrap=False)
    ws.column_dimensions["A"].width = 120


def build(path: Path, fig: dict, history: list[dict] | None = None, catalogue: list[dict] | None = None) -> Workbook:
    wb = Workbook()
    start_sheet(wb.active, fig)
    history_sheet(wb.create_sheet(), history if history is not None else fig["history"])
    price_sheet(wb.create_sheet(), fig)
    discount_sheet(wb.create_sheet(), fig)
    catalogue_sheet(wb.create_sheet(), catalogue)
    wb.properties.creator = "Hubricon"
    wb.properties.title = "The Price Curve"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return wb


# ═══ 3. Recalculation and the check ════════════════════════════════════════════════════════
def recalc(path: Path) -> None:
    """The first course's LibreOffice recalculation, one implementation for both."""
    sys.path.insert(0, str(ROOT / "scripts" / "learn"))
    from verify_fee_staircase import recalc as lo_recalc
    lo_recalc(path)


def random_history(rng: random.Random) -> list[dict]:
    """A golden history: sometimes too short, sometimes too flat, mostly readable."""
    kind = rng.random()
    n = rng.randint(2, 4) if kind < 0.1 else rng.randint(5, HISTORY_ROWS)
    base = rng.uniform(6, 90)
    eps = rng.uniform(-3.5, -0.3)
    spread = rng.uniform(0.001, 0.012) if 0.1 <= kind < 0.2 else rng.uniform(0.03, 0.18)
    per_day = rng.uniform(0.5, 60)
    rows = []
    for i in range(n):
        days = rng.choice([7, 14, 15, 16, 28, 30, 31])
        price = round(base * math.exp(rng.gauss(0, spread)), 2)
        units = max(1, int(round(per_day * days * (price / base) ** eps * math.exp(rng.gauss(0, 0.15)))))
        rows.append({"label": f"P{i + 1}", "days": days, "units": units, "price": price})
    if rng.random() < 0.15 and len(rows) > 5:
        rows[rng.randrange(len(rows))]["units"] = 0          # a period with no sales is not used
    return rows


def random_catalogue_row(rng: random.Random, i: int) -> dict:
    from scipy import stats
    eps = rng.choice([rng.uniform(-4.0, -1.3), rng.uniform(-1.3, -0.95), rng.uniform(-0.95, -0.2)])
    se = rng.uniform(0.03, 0.9)
    dof = rng.randint(3, 22)
    t = float(stats.t.ppf(0.975, dof))
    return {"sku": f"SKU-{i + 1}", "price": round(rng.uniform(5, 80), 2), "units": rng.randint(20, 3000),
            "cost": round(rng.uniform(0.8, 30), 2), "referral": rng.choice([0.08, 0.15, 0.17]),
            "fixed": round(rng.uniform(2.4, 9.5), 2), "eps": round(eps, 4), "se": round(se, 4),
            "lo": round(eps - t * se, 4), "hi": round(eps + t * se, 4)}


def close(a, b, tol=TOL) -> bool:
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def verify(fig: dict, cases: int = 40) -> int:
    rng = random.Random(20261001)
    histories = [random_history(rng) for _ in range(cases)]
    catalogue = [random_catalogue_row(rng, i) for i in range(cases)]
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hubricon-pc-") as tmp:
        path = Path(tmp) / "check.xlsx"
        wb = build(path, fig, catalogue=catalogue)
        src = wb["Your history"]
        for k, hist in enumerate(histories):
            ws = wb.copy_worksheet(src)
            ws.title = f"H{k}"
            for i in range(HISTORY_ROWS):
                r = 5 + i
                row = hist[i] if i < len(hist) else None
                ws[f"A{r}"].value = row["label"] if row else None
                ws[f"B{r}"].value = row["days"] if row else None
                ws[f"C{r}"].value = row["units"] if row else None
                ws[f"D{r}"].value = row["price"] if row else None
        wb.save(path)
        recalc(path)
        got = load_workbook(path, data_only=True)

        for k, hist in enumerate(histories):
            ws = got[f"H{k}"]
            want = _fit([{"price": r["price"], "units": r["units"], "days": r["days"]} for r in hist])
            status = ws["Q22"].value
            expect = {"ok": "Read", "insufficient_data": "Too few", "insufficient_price_variation": "The price has not moved"}[want["status"]]
            if not str(status).startswith(expect):
                problems.append(f"H{k}: status {status!r}, engine {want['status']}")
                continue
            if want["status"] != "ok":
                continue
            d = want["details"]
            pairs = [("elasticity", ws["Q12"].value, want["elasticity"]), ("std_err", ws["Q18"].value, want["std_err"]),
                     ("ci low", ws["Q20"].value, d["ci95"][0]), ("ci high", ws["Q21"].value, d["ci95"][1]),
                     ("r_squared", ws["Q16"].value, want["r_squared"]), ("t", ws["Q19"].value, d["t_critical"]),
                     ("dof", ws["Q14"].value, d["dof"]), ("price_cv", ws["Q7"].value, want["price_cv"])]
            for name, sheet_v, engine_v in pairs:
                if not close(round(float(sheet_v), 4), engine_v):
                    problems.append(f"H{k}: {name} sheet {sheet_v} engine {engine_v}")
            guard_sheet = ws["Q23"].value == "Too close to −1 to name a price"
            if guard_sheet != guarded(want["elasticity"], want["std_err"], tuple(d["ci95"])):
                problems.append(f"H{k}: guard sheet {ws['Q23'].value!r}")

        cat = got["Catalogue"]
        for i, row in enumerate(catalogue):
            r = 5 + i
            g = guarded(row["eps"], row["se"], (row["lo"], row["hi"]))
            best = None if g else optimal_price(row["eps"], row["cost"], row["referral"], row["fixed"])
            way = direction(row["eps"], row["price"], best, g)
            p1 = step_price(row["price"], best, way)
            delta = float(profit_delta(row["eps"], row["price"], row["units"], row["cost"], row["referral"], p1, row["fixed"]))
            checks = [("guard", cat[f"L{r}"].value == "yes", g), ("direction", cat[f"N{r}"].value, way),
                      ("next price", cat[f"O{r}"].value, p1), ("change", cat[f"P{r}"].value, delta)]
            m = cat[f"M{r}"].value
            checks.append(("best", None if m == "none" else m, best))
            for name, a, b in checks:
                if isinstance(b, bool) or isinstance(b, str) or b is None:
                    ok = a == b
                else:
                    ok = close(a, b, 1e-6) if name != "change" else abs(float(a) - b) <= 1e-6 * max(1.0, abs(b))
                if not ok:
                    problems.append(f"Catalogue row {i + 1}: {name} sheet {a!r} engine {b!r}")

        price = got["Your price"]
        e, b = fig["economics"], fig["best"]
        hist_ws = got["Your history"]
        example_checks = [
            ("example elasticity", round(hist_ws["Q12"].value, 4), fig["fit"]["elasticity"]),
            ("example std_err", round(hist_ws["Q18"].value, 4), fig["fit"]["std_err"]),
            ("profit a month", price["B18"].value, e["profit_month"]),
            ("best price", price["B20"].value if price["B20"].value != "none" else None, b["price"]),
            ("next price", price["B23"].value, b["step_price"]),
            ("change a month", price["B25"].value, b["step_delta"]),
            ("discount: needed", got["Discount"]["B10"].value, fig["discount"]["needed"]),
            ("discount: implied", got["Discount"]["B11"].value, fig["discount"]["implied"]),
        ]
        for name, a, want_v in example_checks:
            # the sheet carries the fit at full precision; the engine rounds it to four places,
            # so the example's money figures agree to a cent, not to the last digit
            tol = TOL if name.startswith("example") else 1e-3
            if not close(a, want_v, tol):
                problems.append(f"Example: {name} sheet {a!r} engine {want_v!r}")
        for row in fig["table"]:
            k = int(round(row["change"] * 100))
            r = 31 + k + 10
            if not (close(price[f"D{r}"].value, row["breakeven"], 1e-6) and close(price[f"F{r}"].value, row["delta"], 1e-3)):
                problems.append(f"Example table {k:+d}%: sheet {price[f'D{r}'].value}, {price[f'F{r}'].value}; engine {row['breakeven']}, {row['delta']}")

    for p in problems:
        print("  ✗", p)
    print(f"{2 * cases} golden cases and the worked example: {'all agree' if not problems else f'{len(problems)} disagree'}")
    return len(problems)


def main() -> None:
    fig = figures()
    FIGURES.write_text(json.dumps(fig, indent=1) + "\n")
    print(f"wrote {FIGURES.relative_to(ROOT)}: elasticity {fig['fit']['elasticity']} ± {fig['fit']['std_err']}, best price {fig['best']['price']}")
    if verify(fig):
        raise SystemExit(1)
    if "--publish" in sys.argv:
        build(FILE, fig)
        recalc(FILE)
        STAMP.write_text(json.dumps({
            "file": str(FILE.relative_to(ROOT)),
            "file_sha256": hashlib.sha256(FILE.read_bytes()).hexdigest(),
            "engine_sha256": fig["engine_sha256"],
            "verified_on": date.today().isoformat(),
            "golden_cases": 80,
        }, indent=2) + "\n")
        print(f"published {FILE.relative_to(ROOT)} and {STAMP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
