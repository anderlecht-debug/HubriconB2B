"""Renders one self-contained HTML report per model run — the artifact the
operator narrates over in the recorded walkthrough."""

import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import REPO_ROOT
from . import charts

STOCKOUT_ALERT = 0.25
TEMPLATES = Path(__file__).parent / "templates"


def _fetch_results(db, table: str, run_id: str) -> list[dict]:
    return db.table(table).select("*").eq("run_id", run_id).execute().data


def _resolve_run(db, client_id: str, run_id: str | None) -> dict:
    q = db.table("model_runs").select("*").eq("client_id", client_id)
    if run_id:
        rows = q.eq("id", run_id).execute().data
    else:
        rows = q.eq("status", "succeeded").order("started_at", desc=True).limit(1).execute().data
    if not rows:
        sys.exit("No succeeded model run for this client — `hubricon run` first.")
    return rows[0]


def _top_actions(inventory, ads, elasticity, margins) -> list[dict]:
    actions = []
    for r in inventory:
        p = float(r["stockout_probability"] or 0)
        if p >= STOCKOUT_ALERT:
            actions.append({
                "score": p * 100,
                "tag": "INVENTORY",
                "text": f"Reorder {r['sku']} now — {p:.0%} chance of stocking out before a "
                        f"replenishment lands. Suggested order: {r['reorder_qty']} units.",
            })
    bleed_total = sum(t["spend"] or 0 for r in ads for t in (r["bleed_terms"] or []))
    if bleed_total > 0:
        n = sum(len(r["bleed_terms"] or []) for r in ads)
        actions.append({
            "score": bleed_total,
            "tag": "ADVERTISING",
            "text": f"Negative-match {n} search terms spending with zero attributed sales — "
                    f"${bleed_total:,.0f} of pure bleed in the export window.",
        })
    for r in ads:
        if r["status"] == "ok" and r["current_spend"] and r["breakeven_spend"] \
                and float(r["current_spend"]) > float(r["breakeven_spend"]):
            excess = float(r["current_spend"]) - float(r["breakeven_spend"])
            actions.append({
                "score": excess,
                "tag": "ADVERTISING",
                "text": f"“{r['campaign_name']}” is past its marginal break-even — trim spend "
                        f"toward ${float(r['breakeven_spend']):,.0f} (currently "
                        f"${float(r['current_spend']):,.0f} per point).",
            })
    for r in elasticity:
        if r["status"] == "ok" and r["elasticity"] is not None and -1 < float(r["elasticity"]) < 0:
            actions.append({
                "score": 20 + 10 * (1 + float(r["elasticity"])),
                "tag": "PRICING",
                "text": f"{r['item_id']} demand is price-insensitive (ε = {float(r['elasticity']):.2f}) — "
                        f"test a 3–5% price increase; volume loss should be smaller than the margin gain.",
            })
    if margins:
        latest = max(m["period_start"] for m in margins)
        for m in margins:
            if m["period_start"] == latest and m["net_margin"] is not None and float(m["net_margin"]) < 0:
                actions.append({
                    "score": abs(float(m["net_margin"])),
                    "tag": "MARGIN",
                    "text": f"{m['sku']} sold at a loss last period (net ${float(m['net_margin']):,.0f} "
                            f"after fees, COGS and ads) — reprice or cut its ad allocation.",
                })
    actions.sort(key=lambda a: a["score"], reverse=True)
    return actions[:5]


def generate(db, client: dict, run_id: str | None = None, out_dir: str | None = None) -> Path:
    run = _resolve_run(db, client["id"], run_id)
    inventory = _fetch_results(db, "inventory_sim_results", run["id"])
    elasticity = _fetch_results(db, "elasticity_results", run["id"])
    ads = _fetch_results(db, "ad_efficiency_results", run["id"])
    margins = _fetch_results(db, "margin_results", run["id"])

    latest = max((m["period_start"] for m in margins), default=None)
    latest_margins = [m for m in margins if m["period_start"] == latest] if latest else []
    totals = {
        "revenue": sum(float(m["revenue"] or 0) for m in latest_margins),
        "net": sum(float(m["net_margin"] or 0) for m in latest_margins),
        "skus_at_risk": sum(1 for r in inventory if float(r["stockout_probability"] or 0) >= STOCKOUT_ALERT),
        "bleed": sum(t["spend"] or 0 for r in ads for t in (r["bleed_terms"] or [])),
    }

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    html = env.get_template("report.html.j2").render(
        client=client,
        run=run,
        today=date.today().isoformat(),
        actions=_top_actions(inventory, ads, elasticity, margins),
        totals=totals,
        latest_period=latest,
        inventory=sorted(inventory, key=lambda r: float(r["stockout_probability"] or 0), reverse=True),
        elasticity=elasticity,
        ads=ads,
        chart_stockout=charts.stockout_bars(inventory),
        chart_elasticity=charts.elasticity_scatter(elasticity),
        chart_ads=charts.ad_curves(ads),
        chart_margin=charts.margin_bars(margins),
    )

    base = Path(out_dir) if out_dir else REPO_ROOT / "reports"
    folder = base / (client["company_name"] or client["id"][:8]).lower().replace(" ", "-")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date.today().isoformat()}-{run['id'][:8]}.html"
    path.write_text(html, encoding="utf-8")
    return path
