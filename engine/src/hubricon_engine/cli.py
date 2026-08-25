"""hubricon — operator CLI.

    hubricon clients
    hubricon ingest     <client> [--reparse] [--upload-id ID]
    hubricon run        <client> [--models margin,inventory,elasticity,ads] [--simulations N] [--seed N]
    hubricon directives <client> [--run ID] [--issue]
    hubricon ledger     <client>
    hubricon measure    <client> --directive <id-prefix> --impact <usd> [--notes TEXT]
    hubricon report     <client> [--run ID] [--out DIR]
    hubricon all        <client>

<client> is a client uuid, uuid prefix, or contact email.
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np

from . import __version__
from . import db as dbmod
from . import storage
from .directives import draft_directives
from .ingest import PARSERS
from .ingest.headers import IngestError
from .ingest.readers import ReadError, read_table
from .models import ad_efficiency, elasticity, inventory_sim, margin

DATA_TABLES = (
    "asin_traffic",
    "sku_economics",
    "ppc_search_terms",
    "ppc_spend",
    "inventory_levels",
    "cogs_inputs",
)

# Bulk PostgREST inserts need uniform keys, so every result row is padded to
# its table's full column list.
RESULT_COLUMNS = {
    "inventory_sim_results": (
        "sku", "daily_velocity_mean", "daily_velocity_std", "lead_time_days", "on_hand_units",
        "inbound_units", "stockout_probability", "days_of_cover", "reorder_point", "reorder_qty",
        "safety_stock", "simulations", "details",
    ),
    "elasticity_results": (
        "level", "item_id", "status", "elasticity", "std_err", "r_squared", "n_periods",
        "price_cv", "details",
    ),
    "ad_efficiency_results": (
        "campaign_name", "status", "curve_model", "curve_params", "current_spend", "current_sales",
        "marginal_roas", "breakeven_spend", "recommended_spend", "bleed_terms", "details",
    ),
    "margin_results": (
        "sku", "asin", "period_start", "period_end", "units", "revenue", "amazon_fees", "cogs",
        "ad_spend_allocated", "net_margin", "net_margin_pct", "forecast",
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def cmd_clients(_args):
    db = dbmod.connect()
    rows = db.table("clients").select("id, company_name, contact_email, status").order("created_at").execute().data
    if not rows:
        print("No clients yet — run `npm run new-client` first.")
        return
    for r in rows:
        print(f"{r['id'][:8]}  {r['status']:<9} {r['company_name'] or '—':<28} {r['contact_email'] or ''}")


def cmd_ingest(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    statuses = ["uploaded", "parsed", "failed"] if args.reparse else ["uploaded"]
    q = db.table("uploads").select("*").eq("client_id", client["id"]).in_("status", statuses)
    if args.upload_id:
        q = q.eq("id", args.upload_id)
    uploads = q.order("created_at").execute().data
    if not uploads:
        print("Nothing to ingest.")
        return

    failures = 0
    for upload in uploads:
        label = f"{upload['report_type']} {upload['original_filename']}"
        try:
            data = storage.download(db, upload["storage_path"])
            table, rows, on_conflict = PARSERS[upload["report_type"]].parse(read_table(data), upload)
            if not rows:
                raise IngestError("No usable data rows after parsing")
            dbmod.chunked_upsert(db, table, rows, on_conflict)
            db.table("uploads").update(
                {"status": "parsed", "row_count": len(rows), "parse_error": None, "parsed_at": _now()}
            ).eq("id", upload["id"]).execute()
            print(f"  parsed  {label}: {len(rows)} rows -> {table}")
        except (ReadError, IngestError) as err:
            failures += 1
            db.table("uploads").update({"status": "failed", "parse_error": str(err)}).eq("id", upload["id"]).execute()
            print(f"  FAILED  {label}: {err}", file=sys.stderr)
    if failures:
        sys.exit(f"{failures} upload(s) failed — fix the synonym maps and rerun with --reparse.")


def _load_data(db, client_id: str) -> dict:
    return {table: dbmod.fetch_all(db, table, client_id) for table in DATA_TABLES}


def _pad(rows: list[dict], table: str) -> list[dict]:
    cols = RESULT_COLUMNS[table]
    return [{c: row.get(c) for c in cols} for row in rows]


def cmd_run(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    wanted = set(args.models.split(","))
    unknown = wanted - {"margin", "inventory", "elasticity", "ads"}
    if unknown:
        sys.exit(f"Unknown model(s): {', '.join(sorted(unknown))}")

    data = _load_data(db, client["id"])
    counts = {t: len(rows) for t, rows in data.items()}
    print(f"Data: {counts}")

    run = (
        db.table("model_runs")
        .insert(
            {
                "client_id": client["id"],
                "engine_version": __version__,
                "git_sha": _git_sha(),
                "params": {"models": sorted(wanted), "simulations": args.simulations, "seed": args.seed},
            }
        )
        .execute()
        .data
    )
    run_id = run[0]["id"]
    rng = np.random.default_rng(args.seed)

    try:
        avg_margin = None
        if "margin" in wanted:
            rows = margin.run(data)
            avg_margin = margin.average_margin(rows)
            _write_results(db, "margin_results", rows, run_id, client["id"])
        if "inventory" in wanted:
            rows = inventory_sim.run(data, rng, simulations=args.simulations)
            _write_results(db, "inventory_sim_results", rows, run_id, client["id"])
        if "elasticity" in wanted:
            _write_results(db, "elasticity_results", elasticity.run(data), run_id, client["id"])
        if "ads" in wanted:
            rows = ad_efficiency.run(data, avg_margin=avg_margin)
            _write_results(db, "ad_efficiency_results", rows, run_id, client["id"])
    except Exception as err:
        db.table("model_runs").update({"status": "failed", "error": str(err), "finished_at": _now()}).eq(
            "id", run_id
        ).execute()
        raise

    db.table("model_runs").update({"status": "succeeded", "finished_at": _now()}).eq("id", run_id).execute()
    print(f"Run {run_id} succeeded.")
    return run_id


RESULT_KEYS = {
    "inventory_sim_results": "run_id,sku",
    "elasticity_results": "run_id,level,item_id",
    "ad_efficiency_results": "run_id,campaign_name",
    "margin_results": "run_id,sku,period_start",
}


def _write_results(db, table: str, rows: list[dict], run_id: str, client_id: str):
    padded = [{**row, "run_id": run_id, "client_id": client_id} for row in _pad(rows, table)]
    if padded:
        dbmod.chunked_upsert(db, table, padded, on_conflict=RESULT_KEYS[table])
    print(f"  {table}: {len(padded)} rows")


def _latest_run(db, client_id: str, run_id: str | None) -> dict:
    q = db.table("model_runs").select("id, started_at").eq("client_id", client_id)
    rows = (q.eq("id", run_id) if run_id else q.eq("status", "succeeded").order("started_at", desc=True).limit(1)).execute().data
    if not rows:
        sys.exit("No succeeded model run for this client — `hubricon run` first.")
    return rows[0]


def cmd_directives(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], args.run)
    results = {t: db.table(t).select("*").eq("run_id", run["id"]).execute().data
               for t in ("inventory_sim_results", "ad_efficiency_results", "elasticity_results", "margin_results")}
    drafts = draft_directives(results["inventory_sim_results"], results["ad_efficiency_results"],
                              results["elasticity_results"], results["margin_results"])
    if not drafts:
        print("No directives drafted — clean run.")
        return

    # regenerate this run's drafts idempotently; issued/answered rows are untouched
    db.table("directives").delete().eq("client_id", client["id"]).eq("run_id", run["id"]).eq("status", "draft").execute()
    rows = [{
        "client_id": client["id"],
        "run_id": run["id"],
        "module": d["module"],
        "action_text": d["action_text"],
        "expected_impact_usd": d["expected_impact_usd"],
    } for d in drafts]
    inserted = db.table("directives").insert(rows).execute().data

    if args.issue:
        ids = [r["id"] for r in inserted]
        db.table("directives").update({"status": "issued", "issued_at": _now()}).in_("id", ids).execute()

    state = "issued" if args.issue else "draft (review, then rerun with --issue)"
    print(f"{len(inserted)} directive(s) {state}:")
    for r in inserted:
        expected = f"~${float(r['expected_impact_usd']):,.0f}" if r["expected_impact_usd"] else "—"
        print(f"  {r['id'][:8]}  {r['module']:<12} {expected:>10}  {r['action_text'][:90]}")


def cmd_ledger(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    rows = db.table("directives").select("*").eq("client_id", client["id"]).order("created_at", desc=True).execute().data
    if not rows:
        print("Ledger is empty — `hubricon directives` after a run.")
        return
    measured = sum(float(r["measured_impact_usd"] or 0) for r in rows)
    print(f"Decision Ledger — {client['company_name'] or client['contact_email']}")
    print(f"Measured impact to date: ${measured:,.0f} across {len(rows)} directive(s)\n")
    for r in rows:
        expected = f"~${float(r['expected_impact_usd']):,.0f}" if r["expected_impact_usd"] else "        —"
        actual = f"${float(r['measured_impact_usd']):,.0f}" if r["measured_impact_usd"] is not None else "—"
        print(f"  {r['id'][:8]}  {r['status']:<9} {r['module']:<12} exp {expected:>10}  got {actual:>9}  {r['action_text'][:70]}")


def cmd_measure(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    rows = (db.table("directives").select("id, status, action_text").eq("client_id", client["id"])
            .like("id", f"{args.directive}%").execute().data)
    if len(rows) != 1:
        sys.exit(f"Directive prefix {args.directive!r} matched {len(rows)} row(s) — need exactly 1.")
    patch = {
        "measured_impact_usd": args.impact,
        "measured_at": _now(),
        "status": "done",
    }
    if args.notes:
        patch["measurement_notes"] = args.notes
    db.table("directives").update(patch).eq("id", rows[0]["id"]).execute()
    print(f"Recorded ${args.impact:,.0f} on {rows[0]['id'][:8]} ({rows[0]['action_text'][:60]}…)")


def cmd_report(args):
    from .report.html_report import generate

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    path = generate(db, client, run_id=args.run, out_dir=args.out)
    print(f"Report: {path}")


def cmd_all(args):
    cmd_ingest(args)
    cmd_run(args)
    args.run = None
    cmd_report(args)


def main():
    parser = argparse.ArgumentParser(prog="hubricon", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("clients", help="list clients").set_defaults(fn=cmd_clients)

    p = sub.add_parser("ingest", help="parse uploaded files into typed tables")
    p.add_argument("client")
    p.add_argument("--reparse", action="store_true", help="also reprocess parsed/failed uploads")
    p.add_argument("--upload-id", help="only this upload")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("run", help="run the models")
    p.add_argument("client")
    p.add_argument("--models", default="margin,inventory,elasticity,ads")
    p.add_argument("--simulations", type=int, default=20000)
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("directives", help="draft (and optionally issue) Decision Ledger directives from a run")
    p.add_argument("client")
    p.add_argument("--run", help="model_runs id (default: latest succeeded)")
    p.add_argument("--issue", action="store_true", help="issue the drafts to the client portal")
    p.set_defaults(fn=cmd_directives)

    p = sub.add_parser("ledger", help="print the client's Decision Ledger")
    p.add_argument("client")
    p.set_defaults(fn=cmd_ledger)

    p = sub.add_parser("measure", help="record the measured impact of a directive")
    p.add_argument("client")
    p.add_argument("--directive", required=True, help="directive id prefix")
    p.add_argument("--impact", required=True, type=float, help="measured impact in USD")
    p.add_argument("--notes", help="how the measurement was made")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("report", help="render the HTML report for a run")
    p.add_argument("client")
    p.add_argument("--run", help="model_runs id (default: latest succeeded)")
    p.add_argument("--out", default=None, help="output directory (default: <repo>/reports)")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("all", help="ingest + run + report")
    p.add_argument("client")
    p.set_defaults(
        fn=cmd_all, reparse=False, upload_id=None, models="margin,inventory,elasticity,ads",
        simulations=20000, seed=42, run=None, out=None,
    )

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
