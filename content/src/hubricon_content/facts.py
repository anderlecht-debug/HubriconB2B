"""Every number a video may say, produced by the engine and formatted here.

`load_data` pushes the demo exports through the engine's own parsers;
`run_models` mirrors `hubricon_engine.cli._run_models` without a database;
`build_facts` turns the outputs into `{key: {value, label, source}}` where every
value is already a formatted string, so the model that writes the script never
sees a raw float and can never round one its own way. `run.json` keeps the raw
arrays the Manim scenes draw from, and `provenance.json` records what produced
them.
"""

import hashlib
import json
import pickle
import subprocess
from datetime import date
from pathlib import Path

import numpy as np

from hubricon_engine import chart_pack
from hubricon_engine.cli import AMAZON_ONLY_TABLES, CHANNEL_TABLES, DATA_TABLES, SHARED_TABLES  # noqa: F401
from hubricon_engine.ingest import parse_all
from hubricon_engine.ingest.readers import read_table
from hubricon_engine.models import (ad_efficiency, anomaly, cashflow, dependence, elasticity, forecast,
                                    health_score, inventory_econ, inventory_sim, margin, mc, recovery, risk)
from hubricon_engine.models import pricing_engine, null_calibration
from hubricon_engine.models.anomaly import summarize as summarize_anomalies
from hubricon_engine import __version__ as ENGINE_VERSION

from .demo import CLIENT, DEMO_DIR, TODAY
from .state import CONTENT_DIR

CACHE = CONTENT_DIR / ".cache"
VIDEOS = CONTENT_DIR / "videos"
CLIENT_ID = "00000000-0000-0000-0000-0000000de300"
SIMULATIONS = 20000
SEED = 42
PATH_SAMPLE = 2000      # paths simulated for the survivorship statistics
PATHS_KEPT = 120        # paths written to run.json for drawing
DEMO_LABEL = "Tarnhollow demo data"


# ── data ───────────────────────────────────────────────────────────────────

def load_data(demo_dir: Path = DEMO_DIR) -> dict:
    manifest = json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))
    data = {t: [] for t in DATA_TABLES}
    for n, f in enumerate(manifest["files"]):
        df = read_table((demo_dir / f["file"]).read_bytes())
        upload = {"id": f"00000000-0000-0000-0000-{n:012d}", "client_id": CLIENT_ID,
                  "period_start": f["period_start"], "period_end": f["period_end"]}
        for table, rows, _ in parse_all(f["report_type"], df, upload):
            data.setdefault(table, []).extend(rows)
    return data


def demo_hash(demo_dir: Path = DEMO_DIR) -> str:
    h = hashlib.sha256()
    for p in sorted(demo_dir.glob("*.csv")):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:16]


def engine_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=CONTENT_DIR.parent,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ── the run ────────────────────────────────────────────────────────────────

def _cash_paths(params, wires, starting_cash, opex, rng, horizon, n_paths, payout_cycle_days, rho):
    """The cone's own mechanics (cashflow.simulate), returning every path so a
    scene can draw individual survivors. Same generator, same schedule."""
    sales_net = np.zeros((n_paths, horizon))
    for i, rates in dependence.rate_stream(rng, [p["mean_rate"] for p in params],
                                          [p["std_rate"] for p in params], (n_paths, horizon), rho):
        sales_net += rng.poisson(rates) * params[i]["price"] * (1 - params[i]["fee_rate"])
    ad_daily_total = float(sum(p["ad_daily"] for p in params))
    outflow = np.full(horizon, opex / cashflow.OPEX_DAYS_PER_MONTH)
    for w in wires:
        if 0 <= w["day"] < horizon:
            outflow[w["day"]] += w["amount"]
    cum_net = np.cumsum(sales_net - ad_daily_total, axis=1)
    paid = np.zeros((n_paths, horizon))
    for k in range(payout_cycle_days - 1, horizon, payout_cycle_days):
        paid[:, k:] = cum_net[:, k][:, None]
    return starting_cash - np.cumsum(outflow)[None, :] + paid


def run_models(data: dict, client: dict = CLIENT, seed: int = SEED, simulations: int = SIMULATIONS,
               today: date = TODAY) -> dict:
    rng = np.random.default_rng(seed)
    out = {"today": today.isoformat(), "seed": seed, "simulations": simulations}
    out["margin"] = margin.run(data)
    avg_margin = margin.average_margin(out["margin"])
    out["forecast"] = forecast.run(data)
    overrides = {f["item_id"]: forecast.rate_moments(f) for f in out["forecast"]
                 if f["status"] == "ok" and f["level"] == "sku"}
    out["inventory"] = inventory_sim.run(data, rng, simulations=simulations, rate_overrides=overrides)
    out["inventory_panel"] = inventory_sim.aggregate(out["inventory"], data, rng, simulations=simulations)
    out["elasticity"] = elasticity.run(data)
    out["ads"] = ad_efficiency.run(data, avg_margin=avg_margin)
    out["recovery"] = recovery.run(data, today=today)
    out["anomaly"] = anomaly.run(data)
    out["anomaly_summary"] = summarize_anomalies(out["anomaly"])
    out["invecon"] = inventory_econ.run(data, out["inventory"], out["margin"], out["forecast"], rng,
                                        simulations, today, channel="amazon")
    out["risk"] = risk.run(data, out["margin"], out["forecast"], out["inventory"], out["ads"], rng,
                           min(simulations, 10000))
    out["cash"] = cashflow.run(client, out["inventory"], out["margin"], rng, channel="amazon")
    data_present = {t: bool(data.get(t)) for t in DATA_TABLES}
    out["health"] = health_score.compute(out["margin"], out["cash"], out["risk"], out["inventory"], out["invecon"],
                                         out["ads"], out["forecast"], out["recovery"], data_present, channel="amazon")
    # price moves: one per SKU the engine is willing to recommend on
    latest = chart_pack._latest_rows(out["margin"])[1]
    el_by_sku = {e["item_id"]: e for e in out["elasticity"] if e.get("level") == "sku"}
    moves = []
    for m in latest:
        e = el_by_sku.get(m["sku"])
        if e and e.get("status") == "ok":
            mv = pricing_engine.price_move(m, e, rng=np.random.default_rng(seed))
            if mv:
                moves.append({"sku": m["sku"], **mv})
    out["price_moves"] = moves
    # chart-pack pieces the scenes reuse
    out["waterfall"] = chart_pack.waterfall(out["margin"])
    out["sku_stacks"] = chart_pack.sku_stacks(out["margin"])
    out["elasticity_curves"] = chart_pack.elasticity_curves(out["elasticity"])
    out["profit_curves"] = chart_pack.profit_curves(out["margin"], out["elasticity"])
    out["ad_curves"] = chart_pack.ad_curves(out["ads"])
    out["bleed"] = chart_pack.bleed(out["ads"])
    # survivorship: individual paths from the cone's own generator
    if out["cash"]:
        params = cashflow.sku_cash_params(out["inventory"], out["margin"])
        wires = cashflow.wire_schedule(out["inventory"], out["margin"], cashflow.DEFAULT_HORIZON_DAYS)
        corr = dependence.estimate_pairwise_corr(cashflow._rate_panel(out["margin"]))
        paths = _cash_paths(params, wires, float(client["cash_on_hand"]), float(client["monthly_fixed_costs"]),
                            np.random.default_rng(seed + 1), cashflow.DEFAULT_HORIZON_DAYS, PATH_SAMPLE,
                            out["cash"]["details"]["payout_cycle_days"], float(corr.get("rho") or 0))
        out["paths"] = _path_stats(paths)
        # a full year of the same strategy: enough time for luck alone to spread outcomes
        wires_y = cashflow.wire_schedule(out["inventory"], out["margin"], 365)
        paths_y = _cash_paths(params, wires_y, float(client["cash_on_hand"]), float(client["monthly_fixed_costs"]),
                              np.random.default_rng(seed + 2), 365, PATH_SAMPLE,
                              out["cash"]["details"]["payout_cycle_days"], float(corr.get("rho") or 0))
        out["paths_year"] = _path_stats(paths_y)
    return out


def _path_stats(paths: np.ndarray) -> dict:
    if True:
        terminal = paths[:, -1]
        trough = paths.min(axis=1)
        top = terminal >= np.quantile(terminal, 0.9)
        bottom = terminal <= np.quantile(terminal, 0.1)
        return {
            "n": PATH_SAMPLE, "kept": PATHS_KEPT, "horizon_days": int(paths.shape[1]),
            "sample": [[round(float(v)) for v in row] for row in paths[:PATHS_KEPT]],
            "sample_terminal_rank": [int(r) for r in np.argsort(np.argsort(-terminal[:PATHS_KEPT]))],
            "terminal_p10": float(np.quantile(terminal, 0.10)), "terminal_p50": float(np.median(terminal)),
            "terminal_p90": float(np.quantile(terminal, 0.90)),
            "top_decile_mean_terminal": float(terminal[top].mean()),
            "top_decile_mean_trough": float(trough[top].mean()),
            "all_mean_trough": float(trough.mean()),
            "top_decile_hit_zero": float((trough[top] < 0).mean()),
            "all_hit_zero": float((trough < 0).mean()),
            "bottom_decile_mean_terminal": float(terminal[bottom].mean()),
            "luck_spread": float(np.quantile(terminal, 0.90) - np.quantile(terminal, 0.10)),
            "p5": [float(v) for v in np.quantile(paths, 0.05, axis=0)],
            "p50": [float(v) for v in np.quantile(paths, 0.50, axis=0)],
            "p95": [float(v) for v in np.quantile(paths, 0.95, axis=0)],
        }


def cached_run(force: bool = False) -> dict:
    CACHE.mkdir(exist_ok=True)
    key = f"{demo_hash()}-{ENGINE_VERSION}-{SEED}-{SIMULATIONS}"
    p = CACHE / f"run-{key}.pkl"
    if p.exists() and not force:
        return pickle.loads(p.read_bytes())
    out = run_models(load_data())
    p.write_bytes(pickle.dumps(out))
    return out


# ── formatting ─────────────────────────────────────────────────────────────

def _money(v) -> str:
    v = float(v or 0)
    return ("−" if v < 0 else "") + f"${abs(v):,.0f}"


def _money2(v) -> str:
    v = float(v or 0)
    return ("−" if v < 0 else "") + f"${abs(v):,.2f}"


def _pct(v, digits=0) -> str:
    return f"{float(v or 0) * 100:.{digits}f}%"


def _n(v, digits=0) -> str:
    return f"{float(v):,.{digits}f}"


def _days(v) -> str:
    v = int(round(float(v)))
    return f"{v} day" + ("" if v == 1 else "s")


class Facts(dict):
    def put(self, key: str, value, label: str, source: str) -> None:
        self[key] = {"value": str(value), "label": label, "source": source}


def build_facts(run: dict, data: dict) -> Facts:
    f = Facts()
    S = lambda model: f"{model} on {DEMO_LABEL} (seed {run['seed']}, as of {run['today']})"
    f.put("demo_brand", "Tarnhollow", "the demo brand's name", "demo catalogue")
    f.put("demo_label", "demo data", "the label every demo figure carries", "demo catalogue")
    f.put("n_skus", len({m['sku'] for m in run["margin"]}), "SKUs in the demo catalogue", "demo catalogue")
    f.put("n_periods", len({m['period_start'] for m in run["margin"]}), "monthly periods of history", "demo catalogue")
    annual = sum(float(m["revenue"] or 0) for m in run["margin"])
    f.put("annual_revenue", _money(annual), "trailing twelve-month revenue", S("MARGIN.DECOMP"))
    f.put("annual_revenue_m", f"${annual / 1e6:.1f}M", "trailing twelve-month revenue, in millions", S("MARGIN.DECOMP"))

    # margin: latest period and per-SKU
    w = run["waterfall"]
    if w:
        f.put("rev_latest", _money(w["revenue"]), "revenue, latest month", S("MARGIN.DECOMP"))
        f.put("fees_latest", _money(w["fees"]), "Amazon fees, latest month", S("MARGIN.DECOMP"))
        f.put("cogs_latest", _money(w["cogs"]), "landed cost of goods sold, latest month", S("MARGIN.DECOMP"))
        f.put("ads_latest", _money(w["ads"]), "ad spend allocated, latest month", S("MARGIN.DECOMP"))
        f.put("net_latest", _money(w["net"]), "true net profit, latest month", S("MARGIN.DECOMP"))
        f.put("net_pct_latest", _pct(w["net"] / w["revenue"], 1), "net margin, latest month", S("MARGIN.DECOMP"))
        f.put("fee_share_latest", _pct(w["fees"] / w["revenue"], 1), "Amazon fees as a share of revenue", S("MARGIN.DECOMP"))
        f.put("gross_pct_latest", _pct((w["revenue"] - w["cogs"]) / w["revenue"], 1), "gross margin (revenue less landed cost), latest month", S("MARGIN.DECOMP"))
        f.put("contribution_pct_latest", _pct(w["net"] / w["revenue"], 1), "contribution margin after fees, cost and ads, latest month", S("MARGIN.DECOMP"))
        f.put("gross_vs_contribution_gap", _pct((w["revenue"] - w["cogs"]) / w["revenue"] - w["net"] / w["revenue"], 1), "points of margin between gross and contribution", S("MARGIN.DECOMP"))
    latest = chart_pack._latest_rows(run["margin"])[1]
    if latest:
        by_rev = sorted(latest, key=lambda r: float(r["revenue"] or 0), reverse=True)
        best = by_rev[0]
        f.put("bestseller_sku", best["sku"], "the SKU with the most revenue", S("MARGIN.DECOMP"))
        f.put("bestseller_revenue", _money(best["revenue"]), "the bestseller's monthly revenue", S("MARGIN.DECOMP"))
        f.put("bestseller_net", _money(best["net_margin"]), "the bestseller's monthly net profit", S("MARGIN.DECOMP"))
        f.put("bestseller_net_pct", _pct(best["net_margin_pct"] or 0, 1), "the bestseller's net margin", S("MARGIN.DECOMP"))
        f.put("bestseller_rank_by_net", str(sorted(latest, key=lambda r: float(r["net_margin"] or 0), reverse=True).index(best) + 1), "where the bestseller ranks by net profit", S("MARGIN.DECOMP"))
        by_pct = sorted([r for r in latest if r.get("net_margin_pct") is not None], key=lambda r: float(r["net_margin_pct"]))
        f.put("worst_net_sku", by_pct[0]["sku"], "the SKU with the lowest net margin", S("MARGIN.DECOMP"))
        f.put("worst_net_pct", _pct(by_pct[0]["net_margin_pct"], 1), "the lowest net margin in the catalogue", S("MARGIN.DECOMP"))
        f.put("best_net_sku", by_pct[-1]["sku"], "the SKU with the highest net margin", S("MARGIN.DECOMP"))
        f.put("best_net_pct", _pct(by_pct[-1]["net_margin_pct"], 1), "the highest net margin in the catalogue", S("MARGIN.DECOMP"))
        f.put("n_skus_negative_net", str(sum(1 for r in latest if float(r["net_margin"] or 0) < 0)), "SKUs losing money after ads, latest month", S("MARGIN.DECOMP"))

    # cash cone
    c = run.get("cash")
    if c:
        f.put("cash_on_hand", _money(c["starting_cash"]), "cash on hand today (client-stated)", S("cash horizon"))
        f.put("monthly_fixed_costs", _money(c["monthly_fixed_costs"]), "monthly fixed costs (client-stated)", S("cash horizon"))
        f.put("horizon_days", _days(c["horizon_days"]), "the cash horizon", S("cash horizon"))
        f.put("n_paths", _n(c["n_paths"]), "simulated cash paths", S("cash horizon"))
        f.put("p_ruin", _pct(c["p_ruin"], 1), "probability the cash balance crosses zero inside the horizon", S("cash horizon"))
        f.put("p_ruin_se", _pct(c["p_ruin_mc_se"], 2), "Monte Carlo standard error on that probability", S("cash horizon"))
        f.put("min_p5", _money(c["min_p5"]), "the fifth-percentile low point of cash", S("cash horizon"))
        f.put("min_p5_day", _days(c["min_p5_day"]), "the day the fifth-percentile low arrives", S("cash horizon"))
        f.put("min_median", _money(c["min_median"]), "the median path's low point", S("cash horizon"))
        f.put("trough_p5", _money(c["trough_p5"]), "fifth percentile of each path's own trough", S("cash horizon"))
        f.put("trough_es", _money(c["trough_expected_shortfall"]), "expected shortfall: the mean trough of the worst five percent of paths", S("cash horizon"))
        f.put("trough_median", _money(c["trough_median"]), "the median path's trough", S("cash horizon"))
        wires = c["details"]["wires"]
        f.put("wire_count", str(len(wires)), "supplier wires inside the horizon", S("cash horizon"))
        if wires:
            big = max(wires, key=lambda x: x["amount"])
            f.put("largest_wire", _money(big["amount"]), "the largest supplier wire in the horizon", S("cash horizon"))
            f.put("largest_wire_day", _days(big["day"]), "when the largest wire leaves", S("cash horizon"))
            f.put("largest_wire_sku", big["sku"], "the SKU behind the largest wire", S("cash horizon"))
            f.put("wires_total", _money(sum(x["amount"] for x in wires)), "all supplier wires inside the horizon", S("cash horizon"))
        f.put("payout_cycle", _days(c["details"]["payout_cycle_days"]), "the platform's payout cycle", S("cash horizon"))
        f.put("demand_corr", _n(c["details"]["demand_correlation"].get("pairwise_corr") or 0, 2), "pairwise demand correlation across SKUs", S("cash horizon"))
        f.put("skus_in_cone", str(c["details"]["skus_modeled"]), "SKUs feeding the cash cone", S("cash horizon"))
    p = run.get("paths")
    if p:
        src = S("cash horizon paths")
        f.put("paths_sampled", _n(p["n"]), "paths drawn for the survivorship comparison", src)
        f.put("terminal_p50", _money(p["terminal_p50"]), "median cash at the end of the horizon", src)
        f.put("terminal_p90", _money(p["terminal_p90"]), "ninetieth-percentile cash at the end of the horizon", src)
        f.put("terminal_p10", _money(p["terminal_p10"]), "tenth-percentile cash at the end of the horizon", src)
        f.put("top_decile_terminal", _money(p["top_decile_mean_terminal"]), "mean ending cash of the top tenth of paths", src)
        f.put("top_decile_trough", _money(p["top_decile_mean_trough"]), "mean trough of the top tenth of paths", src)
        f.put("all_trough", _money(p["all_mean_trough"]), "mean trough across every path", src)
        f.put("top_decile_hit_zero", _pct(p["top_decile_hit_zero"], 1), "share of the top tenth that ever crossed zero", src)
        f.put("all_hit_zero", _pct(p["all_hit_zero"], 1), "share of all paths that ever crossed zero", src)

    py = run.get("paths_year")
    if py:
        src = S("cash horizon paths, one-year horizon")
        f.put("year_paths", _n(py["n"]), "one-year paths of the same strategy", src)
        f.put("year_terminal_p50", _money(py["terminal_p50"]), "median cash after a year", src)
        f.put("year_terminal_p90", _money(py["terminal_p90"]), "ninetieth-percentile cash after a year", src)
        f.put("year_terminal_p10", _money(py["terminal_p10"]), "tenth-percentile cash after a year", src)
        f.put("year_top_decile", _money(py["top_decile_mean_terminal"]), "mean ending cash of the top tenth of paths after a year", src)
        f.put("year_bottom_decile", _money(py["bottom_decile_mean_terminal"]), "mean ending cash of the bottom tenth after a year", src)
        f.put("year_luck_spread", _money(py["luck_spread"]), "gap between the ninetieth and tenth percentiles after a year, same strategy, different demand draws", src)
        f.put("year_luck_spread_pct", _pct(py["luck_spread"] / max(1.0, py["terminal_p50"]), 0), "that gap as a share of the median outcome", src)
        f.put("year_top_vs_median", _money(py["top_decile_mean_terminal"] - py["terminal_p50"]), "how far the top tenth finished above the median with an identical strategy", src)
        f.put("year_hit_zero", _pct(py["all_hit_zero"], 1), "share of one-year paths that ever crossed zero", src)
        f.put("year_top_decile_hit_zero", _pct(py["top_decile_hit_zero"], 1), "share of the top tenth that ever crossed zero", src)
        f.put("year_top_trough", _money(py["top_decile_mean_trough"]), "mean trough of the top tenth over the year", src)
        f.put("year_all_trough", _money(py["all_mean_trough"]), "mean trough of every path over the year", src)

    # inventory simulation
    inv = run.get("inventory") or []
    if inv:
        src = S("MONTE_CARLO.RUN")
        f.put("inv_skus", str(len(inv)), "SKUs simulated", src)
        f.put("inv_sims", _n(inv[0]["simulations"]), "simulated lead times per SKU", src)
        worst = max(inv, key=lambda r: float(r["stockout_probability"] or 0))
        f.put("stockout_worst_sku", worst["sku"], "the SKU most likely to run out inside its lead time", src)
        f.put("stockout_worst_p", _pct(worst["stockout_probability"], 0), "its stockout probability", src)
        f.put("stockout_worst_cover", _days(worst["days_of_cover"]), "its days of cover", src)
        f.put("stockout_worst_lead", _days(worst["lead_time_days"]), "its supplier lead time", src)
        f.put("stockout_worst_rop", _n(worst["reorder_point"]), "its reorder point at the default service level", src)
        f.put("n_skus_stockout_gt_20", str(sum(1 for r in inv if float(r["stockout_probability"] or 0) > 0.2)), "SKUs with more than a one-in-five stockout chance", src)
        f.put("service_level_default", _pct(inventory_sim.SERVICE_LEVEL), "the flat service level most tools assume", src)
        f.put("lead_time_typical", _days(np.median([r["lead_time_days"] for r in inv])), "median supplier lead time", src)
    panel = run.get("inventory_panel") or {}
    if panel.get("status") == "ok":
        src = S("MONTE_CARLO.RUN panel")
        f.put("panel_expected_stockouts", _n(panel["correlated"]["expected_stockouts"], 1), "SKUs expected out of stock in the same lead time, demand correlated", src)
        f.put("panel_p95_correlated", _n(panel["correlated"]["p95_stockouts"]), "ninety-fifth percentile of simultaneous stockouts, demand correlated", src)
        f.put("panel_p95_independent", _n(panel["independent"]["p95_stockouts"]), "the same percentile if SKUs were independent", src)

    # newsvendor
    ie = run.get("invecon") or {}
    if ie.get("status") == "ok":
        src = S("NEWSVENDOR")
        rows = ie.get("rows") or ie.get("skus") or []
        f.put("nv_skus", str(ie["summary"]["n_skus"]), "SKUs priced by the newsvendor", src)
        f.put("nv_bleed_month", _money(ie["summary"]["bleed"].get("total_month")), "monthly inventory fee bleed", src)
        f.put("nv_econ_orders", str(len(ie["summary"]["econ_orders"])), "economic orders recommended", src)
        f.put("nv_liquidations", str(len(ie["summary"]["liquidation_candidates"])), "liquidation candidates", src)
        if rows:
            qs = [float(r["critical_fractile"]) for r in rows if r.get("critical_fractile") is not None]
            if qs:
                f.put("nv_fractile_min", _pct(min(qs)), "lowest margin-justified service level in the catalogue", src)
                f.put("nv_fractile_max", _pct(max(qs)), "highest margin-justified service level in the catalogue", src)
                f.put("nv_fractile_median", _pct(float(np.median(qs))), "median margin-justified service level", src)
                f.put("nv_skus_below_95", str(sum(1 for q in qs if q < 0.95)), "SKUs whose own margin justifies less than the flat default", src)
            ex = max(rows, key=lambda r: float(r.get("unit_margin") or 0))
            f.put("nv_sku", ex["sku"], "the worked newsvendor example SKU", src)
            f.put("nv_unit_margin", _money2(ex["unit_margin"]), "its unit margin", src)
            f.put("nv_unit_cost", _money2(ex["unit_cost"]), "its landed unit cost", src)
            f.put("nv_cu", _money2(ex["c_u"]), "its cost of being one unit short", src)
            f.put("nv_co", _money2(ex["c_o"]), "its cost of holding one unit too many over a cycle", src)
            f.put("nv_fractile", _pct(ex["critical_fractile"]), "its margin-justified service level", src)
            lo = min(rows, key=lambda r: float(r.get("critical_fractile") or 1))
            f.put("nv_low_sku", lo["sku"], "the SKU with the lowest justified service level", src)
            f.put("nv_low_fractile", _pct(lo["critical_fractile"]), "that SKU's justified service level", src)
            f.put("nv_low_cu", _money2(lo["c_u"]), "that SKU's cost of a stockout, per unit", src)
            f.put("nv_low_co", _money2(lo["c_o"]), "that SKU's cost of overstock, per unit per cycle", src)

    # elasticity and pricing
    el = [e for e in run.get("elasticity") or [] if e.get("level") == "sku"]
    ok = [e for e in el if e.get("status") == "ok" and e.get("elasticity") is not None]
    if el:
        src = S("ELASTICITY.FIT")
        f.put("el_skus_fit", str(len(ok)), "SKUs with a usable elasticity fit", src)
        f.put("el_skus_insufficient", str(len(el) - len(ok)), "SKUs the fit refused (too few periods or no price movement)", src)
        f.put("el_min_periods", str(elasticity.MIN_PERIODS), "periods the fit needs before it will speak", src)
        f.put("el_min_price_cv", _pct(elasticity.MIN_PRICE_CV), "price movement the fit needs before it will speak", src)
        if ok:
            best = max(ok, key=lambda e: float(e.get("r_squared") or 0))
            d = best.get("details") or {}
            f.put("el_sku", best["item_id"], "the worked elasticity example SKU", src)
            f.put("el_point", f"{float(best['elasticity']):.2f}", "its elasticity point estimate", src)
            se = best.get("std_err")
            if se is not None:
                f.put("el_se", f"{float(se):.2f}", "its HC3 robust standard error", src)
                f.put("el_ci_low", f"{float(best['elasticity']) - 1.96 * float(se):.2f}", "lower bound of its ninety-five percent interval", src)
                f.put("el_ci_high", f"{float(best['elasticity']) + 1.96 * float(se):.2f}", "upper bound of its ninety-five percent interval", src)
                f.put("el_ci_width", f"{2 * 1.96 * float(se):.2f}", "width of that interval", src)
            f.put("el_periods", str(len(d.get("points") or [])), "periods the example fit used", src)
            f.put("el_r2", f"{float(best.get('r_squared') or 0):.2f}", "its R-squared", src)
            eps = [float(e["elasticity"]) for e in ok]
            f.put("el_median", f"{float(np.median(eps)):.2f}", "median elasticity across fitted SKUs", src)
            f.put("el_inelastic_count", str(sum(1 for x in eps if -1 < x < 0)), "SKUs that are price-inelastic (a raise adds profit)", src)
            f.put("el_elastic_count", str(sum(1 for x in eps if x <= -1)), "SKUs that are price-elastic", src)
            # sample size, derived from the fit's own standard error (SE scales with 1/sqrt(n))
            if best.get("std_err") and d.get("points"):
                n0 = len(d["points"]); se0 = float(best["std_err"])
                for target, key in ((0.5, "n_for_se_half"), (0.25, "n_for_se_quarter"), (0.1, "n_for_se_tenth")):
                    f.put(key, _n(n0 * (se0 / target) ** 2), f"periods needed to shrink that error to {target:g}", "derived from ELASTICITY.FIT standard error, " + DEMO_LABEL)
    moves = run.get("price_moves") or []
    if moves:
        src = S("PRICE.OPTIMUM")
        f.put("pm_count", str(len(moves)), "SKUs with an honest price move available", src)
        up = [m for m in moves if float(m["p_new"]) > float(m.get("p0") or m["p_new"] - 1)]
        best = max(moves, key=lambda m: float(m.get("expected_delta") or 0))
        f.put("pm_sku", best["sku"], "the SKU with the largest expected gain from a price move", src)
        f.put("pm_new_price", _money2(best["p_new"]), "its recommended new price", src)
        f.put("pm_step", _pct(best["step_fraction"], 1), "the size of the step", src)
        f.put("pm_delta", _money(best["expected_delta"]), "expected profit change per month", src)
        rng_ = best.get("delta_range") or (None, None)
        if rng_[0] is not None:
            f.put("pm_delta_p5", _money(rng_[0]), "fifth percentile of that change", src)
            f.put("pm_delta_p95", _money(rng_[1]), "ninety-fifth percentile of that change", src)
        if best.get("p_loss") is not None:
            f.put("pm_p_loss", _pct(best["p_loss"], 0), "probability the move loses money", src)
        f.put("pm_total_delta", _money(sum(float(m.get("expected_delta") or 0) for m in moves)), "expected monthly profit across every recommended move", src)
        f.put("pm_step_cap", _pct(pricing_engine.STEP_CAP), "the hard cap on any single price step", src)

    # advertising
    ads = run.get("ads") or []
    if ads:
        src = S("SPEND.RESPONSE")
        bleed_terms = [t for a in ads for t in (a.get("bleed_terms") or [])]
        bleed_spend = sum(float(t.get("spend") or 0) for t in bleed_terms)
        f.put("ad_campaigns", str(len(ads)), "campaigns analysed", src)
        f.put("ad_campaigns_fit", str(sum(1 for a in ads if a.get("status") == "ok")), "campaigns with a fitted response curve", src)
        f.put("ad_bleed_terms", str(len(bleed_terms)), "search terms spending with zero attributed sales", src)
        f.put("ad_bleed_spend", _money(bleed_spend), "spend on those terms over the periods on file", src)
        f.put("ad_breakeven_roas", f"{float(ads[0]['details']['breakeven_marginal_roas']):.2f}", "the break-even marginal return on ad spend at this margin", src)
        okc = [a for a in ads if a.get("status") == "ok"]
        if okc:
            worst = min(okc, key=lambda a: float(a.get("marginal_roas") or 9))
            f.put("ad_worst_campaign", worst["campaign_name"], "the campaign with the lowest marginal return", src)
            f.put("ad_worst_marginal_roas", f"{float(worst['marginal_roas']):.2f}", "its marginal return on the last dollar", src)
            f.put("ad_worst_spend", _money(worst["current_spend"]), "its current daily spend", src)
            f.put("ad_worst_breakeven", _money(worst["breakeven_spend"]), "the daily spend where its last dollar breaks even", src)
    b = run.get("bleed")
    if b:
        f.put("ad_bleed_month", _money(b.get("monthly") or b.get("total") or 0), "monthly ad spend with zero attributed sales", S("SPEND.RESPONSE"))

    # recovery
    rec = run.get("recovery") or {}
    if rec.get("status") == "ok":
        src = S("RECOVERY.EV")
        s = rec["summary"]
        f.put("rec_n_claims", str(s["n_claims"]), "reimbursement claims detected", src)
        f.put("rec_n_live", str(s["n_live"]), "claims open right now", src)
        f.put("rec_live_value", _money(s["live_value"]), "face value of open claims", src)
        f.put("rec_live_ev", _money(s["live_ev"]), "expected value of open claims after approval odds", src)
        f.put("rec_n_expiring", str(s["n_expiring"]), "claims expiring within two weeks", src)
        f.put("rec_expiring_value", _money(s["expiring_value"]), "value expiring within two weeks", src)
        f.put("rec_expired_value", _money(s["expired_value"]), "value already lost to closed windows", src)
        f.put("rec_pending_value", _money(s["pending_value"]), "value not yet eligible to file", src)
        f.put("rec_reimbursed_90d", _money(s["reimbursed_90d"]), "what Amazon paid in the last ninety days", src)
        f.put("rec_annualised_live", _money(float(s["live_value"] or 0) * 4), "open claim value, annualised at this quarter's rate", src)
        for t, v in (s.get("by_type") or {}).items():
            f.put(f"rec_{t}_n", str(v["n"]), f"{t.replace('_', ' ')} claims", src)
            f.put(f"rec_{t}_value", _money(v["value"]), f"{t.replace('_', ' ')} value", src)
        f.put("win_warehouse_eligible", _days(recovery.WAREHOUSE_ELIGIBLE_AFTER_DAYS), "days after a warehouse loss before a claim is eligible", "RECOVERY.EV policy constants")
        f.put("win_warehouse_deadline", _days(recovery.WAREHOUSE_DEADLINE_DAYS), "days after a warehouse loss until the window shuts", "RECOVERY.EV policy constants")
        f.put("win_refund_eligible", _days(recovery.REFUND_ELIGIBLE_AFTER_DAYS), "days after a refund before a no-return claim is eligible", "RECOVERY.EV policy constants")
        f.put("win_refund_deadline", _days(recovery.REFUND_DEADLINE_DAYS), "days after a refund until the window shuts", "RECOVERY.EV policy constants")
        f.put("win_refund_min_age", _days(recovery.REFUND_MIN_AGE_DAYS), "days a refund must age before it counts", "RECOVERY.EV policy constants")
        f.put("win_damaged_deadline", _days(recovery.DAMAGED_RETURN_DEADLINE_DAYS), "days after a damaged return until the window shuts", "RECOVERY.EV policy constants")
        f.put("win_found_match", _days(recovery.FOUND_MATCH_WINDOW_DAYS), "days inside which a found unit offsets a loss", "RECOVERY.EV policy constants")
        f.put("win_reimb_match", _days(recovery.REIMBURSEMENT_MATCH_WINDOW_DAYS), "days inside which a paid reimbursement offsets a loss", "RECOVERY.EV policy constants")
        f.put("win_expiring_within", _days(recovery.EXPIRING_WITHIN_DAYS), "days before a deadline a claim is called expiring", "RECOVERY.EV policy constants")
        for t, pv in recovery.P_APPROVE.items():
            f.put(f"p_approve_{t}", _pct(pv), f"assumed approval probability for {t.replace('_', ' ')}", "RECOVERY.EV policy constants")
        f.put("no_cost_fraction", _pct(recovery.NO_COST_VALUE_FRACTION_OF_PRICE), "value fallback when no landed cost is on file, as a share of price", "RECOVERY.EV policy constants")
        f.put("recovery_service_cut", "25%", "the share a typical recovery service keeps", "hubricon-capital-position-build-prompt.md §2 (stated assumption)")

    # anomalies and null calibration
    a = run.get("anomaly_summary") or {}
    if a.get("scanned"):
        src = S("ANOMALY.SCAN")
        f.put("anom_scanned", _n(a["scanned"]), "series and detectors scanned", src)
        f.put("anom_detector_flagged", _n(a["detector_flagged"]), "flags the detectors alone would have raised", src)
        f.put("anom_flagged", _n(a["flagged"]), "flags that survived false-discovery control", src)
        f.put("anom_fdr_q", _pct(a["fdr_q"] or anomaly.FDR_Q), "the false-discovery rate the sweep controls to", src)
        f.put("anom_dollars", _money(a["dollar_impact_total"]), "monthly dollars behind surviving flags", src)
        f.put("null_replicates", _n(null_calibration.NULL_REPLICATES), "null replicates each detector's threshold is calibrated on", "ANOMALY.SCAN null calibration")

    # risk
    r = run.get("risk") or {}
    var = r.get("var") or {}
    if var.get("status") == "ok":
        src = S("risk")
        f.put("risk_expected_net", _money(var["expected_net"]), "expected net profit next period", src)
        f.put("risk_worst_5", _money(var["worst_5pct_net"]), "net profit in the worst five percent of periods", src)
        f.put("risk_cvar_95", _money(var["cvar_95"]), "expected shortfall below plan in a bad period", src)
    conc = (r.get("concentration") or {}).get("sku_revenue") or {}
    if conc.get("hhi") is not None:
        f.put("hhi", _n(conc["hhi"]), "revenue concentration index (HHI)", S("risk"))
        f.put("top_sku_share", _pct(conc["top_share"]), "revenue share of the largest SKU", S("risk"))
        f.put("effective_skus", _n(conc["effective_n"], 1), "effective number of SKUs", S("risk"))

    # forecast
    fc = [x for x in run.get("forecast") or [] if x.get("status") == "ok" and x.get("fva_pct") is not None]
    if fc:
        f.put("forecast_skus", str(len(fc)), "SKUs with a backtested forecast", S("forecast ladder"))
        f.put("forecast_fva", f"{float(np.mean([float(x['fva_pct']) for x in fc])):.0f}%", "average accuracy gain over the naive forecast", S("forecast ladder"))
    h = run.get("health") or {}
    if h.get("status") == "ok":
        f.put("health_score", f"{float(h['score']):.0f}", "Health Score out of one hundred", S("health score"))
        f.put("health_grade", h["grade"], "Health Score grade", S("health score"))
    return f


# ── the step ───────────────────────────────────────────────────────────────

def write(slug: str, force: bool = False) -> Path:
    d = VIDEOS / slug
    d.mkdir(parents=True, exist_ok=True)
    run = cached_run(force=force)
    data = load_data()
    facts = build_facts(run, data)
    (d / "facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    keep = {k: run.get(k) for k in ("today", "seed", "simulations", "waterfall", "sku_stacks", "elasticity_curves",
                                    "profit_curves", "ad_curves", "bleed", "paths", "paths_year", "inventory_panel", "anomaly_summary")}
    keep["cash"] = run.get("cash")
    keep["inventory"] = run.get("inventory")
    keep["invecon_summary"] = (run.get("invecon") or {}).get("summary")
    keep["invecon_rows"] = (run.get("invecon") or {}).get("rows") or (run.get("invecon") or {}).get("skus")
    keep["elasticity"] = [{k: v for k, v in e.items() if k != "details"} | {"points": (e.get("details") or {}).get("points")}
                          for e in run.get("elasticity") or [] if e.get("level") == "sku"]
    keep["price_moves"] = [{k: v for k, v in m.items() if k not in ("mc_inputs", "candidates")} for m in run.get("price_moves") or []]
    keep["recovery_summary"] = (run.get("recovery") or {}).get("summary")
    keep["recovery_claims"] = [{k: c.get(k) for k in ("claim_type", "sku", "units", "value", "expected_value", "eligible_from", "deadline", "days_left", "status")}
                               for c in (run.get("recovery") or {}).get("claims") or []]
    keep["risk_var"] = (run.get("risk") or {}).get("var")
    (d / "run.json").write_text(json.dumps(keep, indent=None, default=float) + "\n", encoding="utf-8")
    prov = {"engine_version": ENGINE_VERSION, "repo_sha": engine_sha(), "demo_hash": demo_hash(),
            "seed": run["seed"], "simulations": run["simulations"], "as_of": run["today"],
            "label": DEMO_LABEL, "facts": len(facts)}
    (d / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8")
    return d / "facts.json"
