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
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np

from . import __version__
from . import db as dbmod
from . import storage
from .alerts import DEDUPE_DAYS, compute_alerts, dedupe
from .directives import draft_directives
from .ingest import PARSERS
from .notify import alert_email_body, email_configured, send_email
from .price_tests import (
    DEFAULT_TEST_DAYS,
    buybox_warning,
    latest_elasticity,
    predict_units_change,
    resolve_baseline,
)
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


def _ingest_client(db, client: dict, reparse: bool = False, upload_id: str | None = None) -> tuple[int, int]:
    """Parse this client's pending uploads; returns (parsed, failed)."""
    statuses = ["uploaded", "parsed", "failed"] if reparse else ["uploaded"]
    q = db.table("uploads").select("*").eq("client_id", client["id"]).in_("status", statuses)
    if upload_id:
        q = q.eq("id", upload_id)
    uploads = q.order("created_at").execute().data

    parsed = failures = 0
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
            parsed += 1
            print(f"  parsed  {label}: {len(rows)} rows -> {table}")
        except (ReadError, IngestError) as err:
            failures += 1
            db.table("uploads").update({"status": "failed", "parse_error": str(err)}).eq("id", upload["id"]).execute()
            print(f"  FAILED  {label}: {err}", file=sys.stderr)
    return parsed, failures


def cmd_ingest(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    parsed, failures = _ingest_client(db, client, reparse=args.reparse, upload_id=args.upload_id)
    if parsed == 0 and failures == 0:
        print("Nothing to ingest.")
    if failures:
        sys.exit(f"{failures} upload(s) failed — fix the synonym maps and rerun with --reparse.")


def _load_data(db, client_id: str) -> dict:
    return {table: dbmod.fetch_all(db, table, client_id) for table in DATA_TABLES}


def _pad(rows: list[dict], table: str) -> list[dict]:
    cols = RESULT_COLUMNS[table]
    return [{c: row.get(c) for c in cols} for row in rows]


def _run_models(db, client: dict, wanted: set[str], simulations: int, seed: int) -> str:
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
                "params": {"models": sorted(wanted), "simulations": simulations, "seed": seed},
            }
        )
        .execute()
        .data
    )
    run_id = run[0]["id"]
    rng = np.random.default_rng(seed)

    try:
        avg_margin = None
        if "margin" in wanted:
            rows = margin.run(data)
            avg_margin = margin.average_margin(rows)
            _write_results(db, "margin_results", rows, run_id, client["id"])
        if "inventory" in wanted:
            rows = inventory_sim.run(data, rng, simulations=simulations)
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


def cmd_run(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    wanted = set(args.models.split(","))
    unknown = wanted - {"margin", "inventory", "elasticity", "ads"}
    if unknown:
        sys.exit(f"Unknown model(s): {', '.join(sorted(unknown))}")
    return _run_models(db, client, wanted, args.simulations, args.seed)


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


def _draft_for_run(db, client: dict, run_id: str) -> list[dict]:
    """Regenerate this run's draft directives idempotently; issued/answered
    rows are untouched. Returns the inserted rows (possibly empty)."""
    results = {t: db.table(t).select("*").eq("run_id", run_id).execute().data
               for t in ("inventory_sim_results", "ad_efficiency_results", "elasticity_results", "margin_results")}
    drafts = draft_directives(results["inventory_sim_results"], results["ad_efficiency_results"],
                              results["elasticity_results"], results["margin_results"])
    db.table("directives").delete().eq("client_id", client["id"]).eq("run_id", run_id).eq("status", "draft").execute()
    if not drafts:
        return []
    rows = [{
        "client_id": client["id"],
        "run_id": run_id,
        "module": d["module"],
        "action_text": d["action_text"],
        "expected_impact_usd": d["expected_impact_usd"],
    } for d in drafts]
    return db.table("directives").insert(rows).execute().data


def cmd_directives(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], args.run)
    inserted = _draft_for_run(db, client, run["id"])
    if not inserted:
        print("No directives drafted — clean run.")
        return

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


def _find_test(db, client_id: str, prefix: str) -> dict:
    rows = db.table("price_tests").select("*").eq("client_id", client_id).like("id", f"{prefix}%").execute().data
    if len(rows) != 1:
        sys.exit(f"Test prefix {prefix!r} matched {len(rows)} row(s) — need exactly 1.")
    return rows[0]


def cmd_pricetest(args):
    from datetime import date, timedelta

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)

    if args.action == "plan":
        if not args.sku or args.to is None:
            sys.exit("plan needs --sku and --to <test price>")
        econ = (db.table("sku_economics").select("sku, asin, period_start, avg_sales_price, sales, units_sold")
                .eq("client_id", client["id"]).eq("sku", args.sku).execute().data)
        baseline = args.baseline or resolve_baseline(econ, args.sku)
        if baseline is None:
            sys.exit(f"No observed price for {args.sku} — pass --baseline explicitly.")
        row = {
            "client_id": client["id"],
            "sku": args.sku,
            "asin": next((r["asin"] for r in econ if r.get("asin")), None),
            "baseline_price": round(float(baseline), 2),
            "test_price": round(float(args.to), 2),
            "start_date": args.start,
            "end_date": (date.fromisoformat(args.start) + timedelta(days=args.days)).isoformat() if args.start else None,
        }
        test = db.table("price_tests").insert(row).execute().data[0]
        move = (row["test_price"] / row["baseline_price"] - 1) * 100
        print(f"Planned {test['id'][:8]}: {args.sku} ${row['baseline_price']:.2f} → ${row['test_price']:.2f} ({move:+.1f}%)")

        run = _latest_run(db, client["id"], None)
        fit = latest_elasticity(
            db.table("elasticity_results").select("*").eq("run_id", run["id"]).execute().data, args.sku)
        if fit:
            predicted = predict_units_change(float(fit["elasticity"]), row["baseline_price"], row["test_price"])
            print(f"Model expects units {predicted:+.1%} at ε = {float(fit['elasticity']):.2f} — "
                  f"revenue change ≈ {((1 + move / 100) * (1 + predicted) - 1):+.1%}.")
        else:
            print("No elasticity fit for this SKU yet — this test is what creates the data.")
        return

    if args.action == "list":
        rows = db.table("price_tests").select("*").eq("client_id", client["id"]).order("created_at", desc=True).execute().data
        if not rows:
            print("No price tests yet — `hubricon pricetest <client> plan --sku ... --to ...`")
            return
        for r in rows:
            bb = f"BB {r['buy_box_share_before'] or '—'}→{r['buy_box_share_during'] or '—'}"
            window = f"{r['start_date'] or '—'}..{r['end_date'] or '—'}"
            print(f"  {r['id'][:8]}  {r['status']:<9} {r['sku']:<18} ${float(r['baseline_price']):.2f}→${float(r['test_price']):.2f}  {window}  {bb}")
        return

    if not args.test:
        sys.exit(f"{args.action} needs --test <id prefix>")
    test = _find_test(db, client["id"], args.test)

    if args.action == "start":
        patch = {"status": "running", "start_date": test["start_date"] or date.today().isoformat()}
        patch["end_date"] = test["end_date"] or (date.fromisoformat(patch["start_date"]) + timedelta(days=args.days)).isoformat()
        if args.buybox is not None:
            patch["buy_box_share_before"] = args.buybox
        db.table("price_tests").update(patch).eq("id", test["id"]).execute()
        print(f"Running {test['id'][:8]} through {patch['end_date']}. Set the price in Seller Central now.")
    elif args.action == "track":
        if args.buybox is None:
            sys.exit("track needs --buybox <current featured-offer share %>")
        db.table("price_tests").update({"buy_box_share_during": args.buybox}).eq("id", test["id"]).execute()
        warning = buybox_warning(test["buy_box_share_before"], args.buybox)
        print(warning if warning else f"Buy Box holding at {args.buybox:.0f}% — test continues.")
    elif args.action in ("complete", "abort"):
        patch = {"status": "completed" if args.action == "complete" else "aborted"}
        if args.notes:
            patch["outcome_notes"] = args.notes
        db.table("price_tests").update(patch).eq("id", test["id"]).execute()
        print(f"{patch['status'].capitalize()} {test['id'][:8]}. The next monthly upload carries this "
              f"price variation into the elasticity fit.")
    else:
        sys.exit(f"Unknown action {args.action!r}")


def cmd_report(args):
    from .report.html_report import generate

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    path = generate(db, client, run_id=args.run, out_dir=args.out)
    print(f"Report: {path}")


def _sweep_client(db, client: dict, send_alerts: bool) -> dict:
    """Ingest -> run -> draft -> alert for one client. Returns digest facts."""
    summary = {"client": client["company_name"] or client["contact_email"],
               "parsed": 0, "failed": 0, "ran": False, "drafts": 0, "alerts": 0, "emailed": False}
    summary["parsed"], summary["failed"] = _ingest_client(db, client)

    has_data = bool(
        db.table("sku_economics").select("id").eq("client_id", client["id"]).limit(1).execute().data
        or db.table("asin_traffic").select("id").eq("client_id", client["id"]).limit(1).execute().data
    )
    if not has_data:
        return summary

    # previous run's inventory picture, for crossed/worsened comparison
    prev_runs = (db.table("model_runs").select("id").eq("client_id", client["id"])
                 .eq("status", "succeeded").order("started_at", desc=True).limit(1).execute().data)
    prev_inventory = (
        db.table("inventory_sim_results").select("*").eq("run_id", prev_runs[0]["id"]).execute().data
        if prev_runs else []
    )

    run_id = _run_models(db, client, {"margin", "inventory", "elasticity", "ads"}, 20000, 42)
    summary["ran"] = True
    summary["drafts"] = len(_draft_for_run(db, client, run_id))

    inventory = db.table("inventory_sim_results").select("*").eq("run_id", run_id).execute().data
    margins = db.table("margin_results").select("*").eq("run_id", run_id).execute().data
    tests = db.table("price_tests").select("*").eq("client_id", client["id"]).execute().data

    from datetime import timedelta
    window = (datetime.now(timezone.utc) - timedelta(days=DEDUPE_DAYS)).isoformat()
    recent = {a["message"] for a in
              db.table("alerts").select("message").eq("client_id", client["id"])
              .gte("created_at", window).execute().data}
    fresh = dedupe(compute_alerts(inventory, prev_inventory, margins, tests), recent)
    summary["alerts"] = len(fresh)
    if not fresh:
        return summary

    emailed = False
    if send_alerts and email_configured() and client.get("contact_email"):
        emailed = send_email(
            client["contact_email"],
            f"Hubricon watch: {len(fresh)} alert(s) on your catalog",
            alert_email_body(summary["client"], fresh),
        )
    summary["emailed"] = emailed
    db.table("alerts").insert([
        {**a, "client_id": client["id"], "run_id": run_id,
         "emailed_at": _now() if emailed else None}
        for a in fresh
    ]).execute()
    for a in fresh:
        print(f"  ALERT [{a['severity']}] {a['message'][:90]}")
    return summary


def cmd_sweep(args):
    db = dbmod.connect()
    q = db.table("clients").select("*").in_("status", ["pending", "active"])
    if args.client:
        clients = [dbmod.resolve_client(db, args.client)]
    else:
        clients = q.execute().data
    if not clients:
        print("No active clients to sweep.")
        return

    digests = []
    for client in clients:
        print(f"== {client['company_name'] or client['contact_email']}")
        try:
            digests.append(_sweep_client(db, client, send_alerts=args.alert))
        except Exception as err:
            print(f"  SWEEP FAILED: {err}", file=sys.stderr)
            digests.append({"client": client["company_name"] or client["contact_email"],
                            "error": str(err)})

    lines = [f"Hubricon sweep — {len(digests)} client(s):", ""]
    for d in digests:
        if "error" in d:
            lines.append(f"  {d['client']}: FAILED — {d['error']}")
        else:
            lines.append(
                f"  {d['client']}: {d['parsed']} file(s) parsed"
                + (f", {d['failed']} FAILED" if d["failed"] else "")
                + (f", models ran, {d['drafts']} draft directive(s) awaiting review, "
                   f"{d['alerts']} alert(s)" + (" (emailed)" if d["emailed"] else "")
                   if d["ran"] else ", no data yet")
            )
    digest = "\n".join(lines)
    print("\n" + digest)

    founder = os.environ.get("FOUNDER_EMAIL")
    if args.alert and founder and email_configured():
        send_email(founder, "Hubricon sweep digest", digest)


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

    p = sub.add_parser("sweep", help="always-on pass over every active client: ingest, run, draft, alert")
    p.add_argument("--client", help="sweep just this client")
    p.add_argument("--alert", action="store_true", help="send alert/digest emails (needs RESEND_API_KEY)")
    p.set_defaults(fn=cmd_sweep)

    p = sub.add_parser("pricetest", help="plan and track a price test (the wedge program)")
    p.add_argument("client")
    p.add_argument("action", choices=["plan", "start", "track", "complete", "abort", "list"])
    p.add_argument("--sku")
    p.add_argument("--to", type=float, help="test price")
    p.add_argument("--baseline", type=float, help="override the observed baseline price")
    p.add_argument("--start", help="start date YYYY-MM-DD (default: when you run `start`)")
    p.add_argument("--days", type=int, default=DEFAULT_TEST_DAYS)
    p.add_argument("--test", help="test id prefix (for start/track/complete/abort)")
    p.add_argument("--buybox", type=float, help="featured-offer share %% observed")
    p.add_argument("--notes")
    p.set_defaults(fn=cmd_pricetest)

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
