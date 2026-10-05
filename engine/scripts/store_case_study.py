"""The proof on a real store's own orders: Hubricon's engine, given a real online retailer's order
history, calls what comes next; the store's own later orders measure every call.

    cd engine && uv run --with openpyxl python scripts/store_case_study.py      # -> ../data/store-study.json

THE DATA is public and published for exactly this: "Online Retail II", every order line a real UK
online retailer took from 1 December 2009 to 9 December 2011 (about a million lines, a customer number
on most), released by the UCI Machine Learning Repository under CC BY 4.0. Chen, D. (2012). Online
Retail II [Dataset]. https://doi.org/10.24432/C5CG6D. It is downloaded once into ~/.hubricon/uci and
never committed. The store is not a client and is not named by the dataset; nothing here is a result
for a client. Nothing written out identifies a customer: only totals.

WHAT IS CALLED, AND HOW IT IS MEASURED. Every model is the engine's own, unmodified.

  Repeat customers   models/clv.py: the engine's own calibration protocol (CALIBRATION_SHARE), fit on
                     the first three quarters of the calendar, the last quarter's repeat orders called
                     and then counted. The cut is the engine's rule, not ours.
  Slipping customers The same fit: regular customers (three or more orders before the cut) the model
                     expected to order less than once more before the end, named at the cut; then who
                     came back.
  Peak demand        models/forecast.py with models/seasonality.py: at each month-end from August to
                     October 2011, next month's units for the 200 best sellers to date, called from the
                     orders before it and nothing after; then the month's real units.

The store sells wholesale as well as retail, so its price per unit falls with order size; an elasticity
read from its average prices would measure that discount, not demand, and none is published here.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import sys
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from hubricon_engine.models import clv, forecast, seasonality  # noqa: E402

OUT = ROOT / "data" / "store-study.json"
CACHE = Path.home() / ".hubricon" / "uci"
URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SOURCE = {
    "name": "Online Retail II",
    "publisher": "UCI Machine Learning Repository",
    "url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
    "doi": "https://doi.org/10.24432/C5CG6D",
    "licence": "CC BY 4.0",
    "citation": "Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.",
}
ENGINE = ["engine/src/hubricon_engine/models/clv.py", "engine/src/hubricon_engine/models/forecast.py",
          "engine/src/hubricon_engine/models/seasonality.py"]
# Lines that are not products: postage, fees, adjustments, samples, manual entries.
NOT_PRODUCTS = {"POST", "DOT", "M", "C2", "BANK CHARGES", "PADS", "D", "AMAZONFEE", "CRUK", "S", "B",
                "ADJUST", "ADJUST2", "TEST001", "TEST002"}
TOP_N = 200
CALLS = [("2011-08", "2011-09"), ("2011-09", "2011-10"), ("2011-10", "2011-11")]
REGULAR_ORDERS = 3          # a regular: three or more orders before the cut
SLIPPING_BELOW = 1.0        # expected to order less than once more before the end


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load() -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    csv = CACHE / "online_retail_II.csv"
    if not csv.exists():
        raw = CACHE / "online_retail_ii.zip"
        if not raw.exists():
            urllib.request.urlretrieve(URL, raw)
        with zipfile.ZipFile(raw) as z:
            name = next(n for n in z.namelist() if n.endswith(".xlsx"))
            frames = pd.read_excel(io.BytesIO(z.read(name)), sheet_name=None)
        pd.concat(frames.values(), ignore_index=True).to_csv(csv, index=False)
    return pd.read_csv(csv, dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])


def store_facts(df: pd.DataFrame, sales: pd.DataFrame) -> dict:
    cancelled = df[df.Invoice.str.startswith("C")]
    by_year = sales.groupby(sales.InvoiceDate.dt.year).rev.sum()
    full = sales[sales.InvoiceDate.dt.year == 2010]
    known = sales[sales["Customer ID"].notna()]
    return {
        "from": sales.InvoiceDate.min().date().isoformat(), "to": sales.InvoiceDate.max().date().isoformat(),
        "currency": "GBP",
        "sales_2010": round(float(by_year.get(2010, 0))), "sales_2011_to_dec_9": round(float(by_year.get(2011, 0))),
        "orders": int(sales.Invoice.nunique()), "order_lines": int(len(sales)),
        "customers": int(known["Customer ID"].nunique()), "known_customer_share": round(float(known.rev.sum() / sales.rev.sum()), 3),
        "products": int(sales.StockCode.nunique()), "countries": int(sales.Country.nunique()),
        "home_share": round(float(sales[sales.Country == "United Kingdom"].rev.sum() / sales.rev.sum()), 3),
        "products_2010": int(full.StockCode.nunique()),
        "cancelled_lines": int(len(cancelled)),
        "cancelled_value": round(float(-(cancelled.Quantity * cancelled.Price).sum())),
    }


def customers(sales: pd.DataFrame) -> tuple[dict, dict]:
    """The engine's own calibration, with its totals and its week-by-week path kept, and the slipping list."""
    known = sales[sales["Customer ID"].notna()]
    inv = known.groupby("Invoice").agg(cust=("Customer ID", "first"), day=("InvoiceDate", "min"), rev=("rev", "sum"))
    inv["day"] = inv.day.dt.date
    occ = inv.groupby(["cust", "day"]).rev.sum().reset_index()      # one purchase occasion a customer a day
    orders = [{"customer_key": str(int(r.cust)), "order_date": r.day.isoformat(), "revenue": float(r.rev)} for r in occ.itertuples()]

    engine = clv.run(orders)                                        # the engine's own verdict, unmodified
    x, t_x, T, mv, fv, end = clv.customer_table(orders)
    first = end - timedelta(weeks=float(T.max()))
    cut = first + timedelta(days=int((end - first).days * clv.CALIBRATION_SHARE))
    holdout_weeks = (end - cut).days / 7.0

    by: dict[str, list[tuple[date, float]]] = {}
    for o in orders:
        by.setdefault(o["customer_key"], []).append((date.fromisoformat(o["order_date"]), o["revenue"]))
    keys = [k for k, v in by.items() if min(d for d, _ in v) <= cut]       # customer_table's order, at the cut
    xc, txc, Tc, _, _, _ = clv.customer_table(orders, end=cut)
    fit = clv.bgnbd_fit(xc, txc, Tc)
    called = clv.expected_repeats(fit, holdout_weeks, xc, txc, Tc)
    actual = np.array([sum(1 for d, _ in by[k] if cut < d <= end) for k in keys], float)
    weeks = list(range(0, math.ceil(holdout_weeks) + 1))
    called_path = [float(clv.expected_repeats(fit, min(w, holdout_weeks), xc, txc, Tc).sum()) for w in weeks]
    measured_path = [int(sum(1 for k in keys for d, _ in by[k] if cut < d <= min(end, cut + timedelta(weeks=w)))) for w in weeks]
    band = None
    if fit["cov"] is not None:
        rng = np.random.default_rng(clv.CLV_SEED)
        totals = []
        for th in rng.multivariate_normal(fit["theta"], fit["cov"], size=400):
            r_, al_, a_, b_ = np.exp(th)
            if a_ <= 1.0:
                continue
            totals.append(float(clv.expected_repeats({"r": r_, "alpha": al_, "a": a_, "b": b_}, holdout_weeks, xc, txc, Tc).sum()))
        if len(totals) >= 50:
            band = [round(float(np.quantile(totals, 0.1))), round(float(np.quantile(totals, 0.9)))]

    # Regulars the model expected to order less than once more: named at the cut, counted at the end.
    before = {k: [o for o in by[k] if o[0] <= cut] for k in keys}
    regular = np.array([len(before[k]) >= REGULAR_ORDERS for k in keys])
    flagged = regular & (called < SLIPPING_BELOW)
    steady = regular & ~flagged
    came_back = actual > 0
    year_before = np.array([sum(v for d, v in before[k] if d > cut - timedelta(days=365)) for k in keys])
    slipping = {
        "regulars": int(regular.sum()), "named": int(flagged.sum()),
        "named_came_back": int((flagged & came_back).sum()), "named_did_not": int((flagged & ~came_back).sum()),
        "named_spend_year_before": round(float(year_before[flagged].sum())),
        "lost_spend_year_before": round(float(year_before[flagged & ~came_back].sum())),
        "steady": int(steady.sum()), "steady_came_back": int((steady & came_back).sum()),
        "rule": f"a customer with {REGULAR_ORDERS} or more orders before the cut whom the model expected to order less than once more before the end",
    }
    out = {
        "engine_verdict": {k: engine.get(k) for k in ("status", "n_customers", "calibration", "expected_repeats_52w",
                                                       "first_order_value", "repeat_order_value", "clv_multiplier")},
        "cut": cut.isoformat(), "end": end.isoformat(), "holdout_weeks": round(holdout_weeks, 1),
        "customers_at_cut": len(keys), "called": round(float(called.sum())), "called_band": band,
        "measured": int(actual.sum()), "ratio": round(float(actual.sum() / called.sum()), 4),
        "path": {"weeks": weeks, "called": [round(v, 1) for v in called_path], "measured": measured_path},
        "fit": {k: round(fit[k], 4) for k in ("r", "alpha", "a", "b")},
        "top_decile_share": round(float(actual[np.argsort(-called)[: len(keys) // 10]].sum() / actual.sum()), 3),
    }
    return out, slipping


def demand(sales: pd.DataFrame) -> dict:
    s = sales.assign(month=sales.InvoiceDate.dt.to_period("M"))
    monthly = s.groupby(["StockCode", "month"]).agg(units=("Quantity", "sum"), sales=("rev", "sum")).reset_index()
    calls = []
    for cut, target in CALLS:
        cutp, tp = pd.Period(cut, "M"), pd.Period(target, "M")
        rank = s[s.month <= cutp].groupby("StockCode").rev.sum().sort_values(ascending=False)
        skus = list(rank.head(TOP_N).index)
        m = monthly[(monthly.month <= cutp) & monthly.StockCode.isin(skus)]
        rows = [{"sku": r.StockCode, "asin": None, "period_start": r.month.start_time.date().isoformat(),
                 "period_end": r.month.end_time.date().isoformat(), "units_sold": float(r.units), "sales": float(r.sales),
                 "avg_sales_price": float(r.sales / r.units)} for r in m.itertuples()]
        data = {"sku_economics": rows, "asin_traffic": [], "inventory_levels": [], "cogs_inputs": []}
        fc = forecast.run(data, horizon_days=tp.days_in_month, seasonal=seasonality.indices(data))
        actual = monthly[monthly.month == tp].set_index("StockCode").units
        last = monthly[monthly.month == cutp].set_index("StockCode").units
        last_year = monthly[monthly.month == tp - 12].set_index("StockCode").units
        ok = [r for r in fc if r.get("status") == "ok"]
        a = np.array([float(actual.get(r["item_id"], 0)) for r in ok])
        p50 = np.array([float(r["horizon_units_point"]) for r in ok])
        lo = np.array([float(r["horizon_units_p10"]) for r in ok])
        hi = np.array([float(r["horizon_units_p90"]) for r in ok])
        lm = np.array([float(last.get(r["item_id"], 0)) for r in ok])
        ly = np.array([float(last_year.get(r["item_id"], 0)) for r in ok])
        calls.append({
            "called_on": cutp.end_time.date().isoformat(), "month": target, "products": len(ok),
            "called": round(float(p50.sum())), "measured": round(float(a.sum())),
            "error": round(float(p50.sum() / a.sum() - 1), 4),
            "inside_band": int(((lo <= a) & (a <= hi)).sum()),
            "mae": {"engine": round(float(np.abs(p50 - a).mean()), 1), "last_month": round(float(np.abs(lm - a).mean()), 1),
                    "same_month_last_year": round(float(np.abs(ly - a).mean()), 1)},
        })
    tc, tm = sum(c["called"] for c in calls), sum(c["measured"] for c in calls)
    hist = (s[s.StockCode.isin(list(s[s.month <= pd.Period(CALLS[0][0], "M")].groupby("StockCode").rev.sum()
                                    .sort_values(ascending=False).head(TOP_N).index))]
            .groupby("month").Quantity.sum())
    return {"top_n": TOP_N, "calls": calls, "quarter": {"called": tc, "measured": tm, "error": round(tc / tm - 1, 4)},
            "history": [{"month": str(k), "units": int(v)} for k, v in hist.items() if str(k) <= CALLS[-1][1]]}


def main() -> None:
    df = load()
    df["rev"] = df.Quantity * df.Price
    sales = df[~df.Invoice.str.startswith("C") & (df.Quantity > 0) & (df.Price > 0)
               & ~df.StockCode.str.upper().isin(NOT_PRODUCTS)].copy()
    facts = store_facts(df, sales)
    cust, slipping = customers(sales)
    dem = demand(sales)
    out = {
        "about": "Hubricon's engine on a real online retailer's published order history: what it called, and what the store's own later orders measured (engine/scripts/store_case_study.py).",
        "label": "Modeled on published data. Not a client. Not a result.",
        "source": SOURCE, "store": facts, "customers": cust, "slipping": slipping, "demand": dem,
        "engine": {p: sha(p) for p in ENGINE},
        "not_published": "elasticity: the store sells wholesale, so its price per unit falls with order size, and an elasticity from its average prices would measure that discount, not demand",
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    c, d = cust, dem["quarter"]
    print(f"store: £{facts['sales_2010']:,} in 2010, {facts['customers']:,} customers, {facts['products']:,} products")
    print(f"customers: cut {c['cut']}, {c['holdout_weeks']} weeks; called {c['called']:,} {c['called_band']}, measured {c['measured']:,} (×{c['ratio']}); engine verdict {c['engine_verdict']['calibration']}")
    print(f"slipping: {slipping}")
    for call in dem["calls"]:
        print(f"demand {call['month']}: called {call['called']:,}, measured {call['measured']:,} ({call['error']:+.1%}); inside band {call['inside_band']}/{call['products']}; MAE {call['mae']}")
    print(f"quarter: called {d['called']:,}, measured {d['measured']:,} ({d['error']:+.2%})")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
