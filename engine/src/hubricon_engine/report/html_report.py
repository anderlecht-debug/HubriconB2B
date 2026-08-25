"""Renders one self-contained HTML report per model run — the artifact the
operator narrates over in the recorded walkthrough."""

import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import REPO_ROOT
from ..directives import draft_directives
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
    drafts = draft_directives(inventory, ads, elasticity, margins)
    return [{"tag": d["module"].upper(), "text": d["action_text"]} for d in drafts[:5]]


def generate(db, client: dict, run_id: str | None = None, out_dir: str | None = None) -> Path:
    run = _resolve_run(db, client["id"], run_id)
    inventory = _fetch_results(db, "inventory_sim_results", run["id"])
    elasticity = _fetch_results(db, "elasticity_results", run["id"])
    ads = _fetch_results(db, "ad_efficiency_results", run["id"])
    margins = _fetch_results(db, "margin_results", run["id"])

    # Decision Ledger: cumulative across all runs, clients never see drafts.
    ledger = (
        db.table("directives").select("*").eq("client_id", client["id"])
        .neq("status", "draft").order("created_at", desc=True).execute().data
    )
    ledger_measured = sum(float(d["measured_impact_usd"] or 0) for d in ledger)
    price_tests = (
        db.table("price_tests").select("*").eq("client_id", client["id"])
        .order("created_at", desc=True).execute().data
    )

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
        ledger=ledger,
        ledger_measured=ledger_measured,
        price_tests=price_tests,
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
