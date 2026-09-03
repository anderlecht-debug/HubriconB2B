"""hubricon — operator CLI.

    hubricon clients
    hubricon ingest     <client> [--reparse] [--upload-id ID]
    hubricon run        <client> [--models margin,forecast,inventory,...] [--simulations N] [--seed N]
    hubricon directives <client> [--run ID] [--issue]
    hubricon ledger     <client>
    hubricon measure    <client> --directive <id-prefix> --impact <usd> [--notes TEXT]
    hubricon recover    <client> list | file --claim ID [--case N] | paid --claim ID --amount X | deny | dismiss
    hubricon health     <client>
    hubricon value      <client>
    hubricon script     <client> [--no-ai]
    hubricon report     <client> [--run ID] [--out DIR]
    hubricon all        <client>

<client> is a client uuid, uuid prefix, or contact email.
"""

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timezone

import numpy as np

from . import __version__
from . import chart_pack
from . import db as dbmod
from . import narrate
from . import storage
from . import value as valuemod
from .alerts import DEDUPE_DAYS, compute_alerts, dedupe
from .briefing import build_memo, build_script, parse_loom_id, period_deltas
from .directives import draft_directives, resolve_brand_terms
from .growth_plan import latest_period_totals, pace, propose_plan
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
from .models import (
    ad_efficiency, anomaly, cashflow, elasticity, forecast, health_score,
    inventory_econ, inventory_sim, margin, recovery, risk,
)
from .models.anomaly import summarize as summarize_anomalies

DATA_TABLES = (
    "asin_traffic",
    "sku_economics",
    "ppc_search_terms",
    "ppc_spend",
    "inventory_levels",
    "cogs_inputs",
    "fba_reimbursements",
    "fba_returns",
    "inventory_ledger",
    "inventory_health",
    "settlement_transactions",
)

# Every model, in dependency order: forecast feeds inventory, inventory
# economics and risk; cash feeds health; value closes the loop.
ALL_MODELS = ("margin", "forecast", "inventory", "elasticity", "ads", "recovery",
              "anomaly", "invecon", "risk", "cash", "health")
DEFAULT_MODELS = ",".join(ALL_MODELS)

CLAIM_FIELDS = ("claim_type", "sku", "fnsku", "asin", "order_id", "event_date", "units", "unit_value",
                "value", "value_basis", "p_approve", "expected_value", "eligible_from", "deadline", "evidence")

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


def _save_output(db, run_id: str, client_id: str, model: str, payload) -> None:
    dbmod.chunked_upsert(
        db, "model_outputs",
        [{"run_id": run_id, "client_id": client_id, "model": model, "payload": payload}],
        on_conflict="run_id,model",
    )


def _load_outputs(db, run_id: str | None) -> dict:
    if not run_id:
        return {}
    rows = db.table("model_outputs").select("model, payload").eq("run_id", run_id).execute().data
    return {r["model"]: r["payload"] for r in rows}


def _fetch_claims(db, client_id: str) -> list[dict]:
    return (db.table("recovery_claims").select("*").eq("client_id", client_id)
            .order("deadline").execute().data)


def _sync_claims(db, client_id: str, run_id: str, rec: dict, today: date) -> list[dict]:
    """Detected claims land in recovery_claims without touching a claim's
    lifecycle (filed/paid/denied are the operator's and Amazon's to set).
    Returns every claim on file for the client."""
    claims = rec.get("claims", [])
    if claims:
        existing = {r["claim_key"] for r in
                    db.table("recovery_claims").select("claim_key").eq("client_id", client_id).execute().data}
        new, seen = [], []
        for c in claims:
            row = {**{k: c.get(k) for k in CLAIM_FIELDS}, "client_id": client_id,
                   "claim_key": c["claim_key"], "last_seen_run_id": run_id}
            if c["claim_key"] in existing:
                seen.append(row)
            else:
                new.append({**row, "first_seen_run_id": run_id,
                            "status": "expired" if c["status"] == "expired" else "detected"})
        if new:
            dbmod.chunked_upsert(db, "recovery_claims", new, on_conflict="client_id,claim_key")
        if seen:
            dbmod.chunked_upsert(db, "recovery_claims", seen, on_conflict="client_id,claim_key")
    (db.table("recovery_claims").update({"status": "expired"}).eq("client_id", client_id)
     .eq("status", "detected").lt("deadline", today.isoformat()).execute())
    return _fetch_claims(db, client_id)


def _run_models(db, client: dict, wanted: set[str], simulations: int, seed: int) -> str:
    data = _load_data(db, client["id"])
    counts = {t: len(rows) for t, rows in data.items() if rows}
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
    today = date.today()

    try:
        avg_margin = None
        margin_rows = inventory_rows = elast_rows = ads_rows = forecast_rows = anomaly_rows = None
        rec = inv_econ = risk_out = cash = health = claims = None

        if "margin" in wanted:
            margin_rows = margin.run(data)
            avg_margin = margin.average_margin(margin_rows)
            _write_results(db, "margin_results", margin_rows, run_id, client["id"])
        if "forecast" in wanted:
            forecast_rows = forecast.run(data)
            _save_output(db, run_id, client["id"], "forecast", {"rows": forecast_rows})
            ok = [f for f in forecast_rows if f["status"] == "ok"]
            gains = [float(f["fva_pct"]) for f in ok if f.get("fva_pct") is not None]
            print(f"  forecast: {len(ok)} of {len(forecast_rows)} items backtested"
                  + (f", mean gain vs naive {sum(gains) / len(gains):+.0f}%" if gains else ""))
        if "inventory" in wanted:
            overrides = {f["item_id"]: forecast.rate_moments(f) for f in (forecast_rows or [])
                         if f["status"] == "ok" and f["level"] == "sku"}
            inventory_rows = inventory_sim.run(data, rng, simulations=simulations, rate_overrides=overrides)
            _write_results(db, "inventory_sim_results", inventory_rows, run_id, client["id"])
        if "elasticity" in wanted:
            elast_rows = elasticity.run(data)
            _write_results(db, "elasticity_results", elast_rows, run_id, client["id"])
        if "ads" in wanted:
            ads_rows = ad_efficiency.run(data, avg_margin=avg_margin)
            _write_results(db, "ad_efficiency_results", ads_rows, run_id, client["id"])
        if "recovery" in wanted:
            rec = recovery.run(data, today=today)
            _save_output(db, run_id, client["id"], "recovery", rec)
            claims = _sync_claims(db, client["id"], run_id, rec, today)
            s = rec["summary"]
            if rec["status"] == "ok":
                print(f"  recovery: {s['n_live']} live claim(s) — ${float(s['live_value'] or 0):,.0f} face, "
                      f"${float(s['live_ev'] or 0):,.0f} expected, {s['n_expiring']} expiring")
            else:
                print("  recovery: no bleed reports on file yet (ledger, returns, reimbursements, transactions)")
        if "anomaly" in wanted:
            anomaly_rows = anomaly.run(data)
            _save_output(db, run_id, client["id"], "anomaly", {"rows": anomaly_rows})
            s = summarize_anomalies(anomaly_rows)
            print(f"  anomaly: {s['scanned']} series scanned, {s['flagged']} flagged, "
                  f"${float(s['dollar_impact_total'] or 0):,.0f}/period adverse")
        base_inventory = inventory_rows if inventory_rows is not None else inventory_sim.run(data, rng, simulations=simulations)
        base_margins = margin_rows if margin_rows is not None else margin.run(data)
        if "invecon" in wanted:
            inv_econ = inventory_econ.run(data, base_inventory, base_margins, forecast_rows, rng, simulations, today)
            _save_output(db, run_id, client["id"], "invecon", inv_econ)
            if inv_econ["status"] == "ok":
                b = inv_econ["summary"]["bleed"]
                print(f"  inventory economics: {inv_econ['summary']['n_skus']} SKUs priced, fee bleed "
                      f"${float(b['total_month'] or 0):,.0f}/month, {len(inv_econ['summary']['econ_orders'])} "
                      f"economic order(s), {len(inv_econ['summary']['liquidation_candidates'])} liquidation candidate(s)")
        if "risk" in wanted:
            risk_out = risk.run(data, base_margins, forecast_rows, base_inventory, ads_rows, rng, min(simulations, 10000))
            _save_output(db, run_id, client["id"], "risk", risk_out)
            v = risk_out.get("var") or {}
            c = (risk_out.get("concentration") or {}).get("sku_revenue") or {}
            print("  risk: "
                  + (f"expected net ${float(v['expected_net']):,.0f}, worst-5% ${float(v['worst_5pct_net']):,.0f}"
                     if v.get("status") == "ok" else "VaR skipped (no unit economics)")
                  + (f"; HHI {float(c['hhi']):,.0f} ({c.get('level')})" if c.get("hhi") is not None else ""))
        if "cash" in wanted:
            cash = cashflow.run(client, base_inventory, base_margins, rng)
            if cash is None:
                print("  cash horizon: skipped (set inputs with `hubricon cash <client> --balance --opex`)")
            else:
                dbmod.chunked_upsert(
                    db, "cash_horizon_results",
                    [{**cash, "run_id": run_id, "client_id": client["id"]}],
                    on_conflict="run_id",
                )
                print(f"  cash_horizon_results: p(ruin) {float(cash['p_ruin']):.1%}, "
                      f"5th-pct low ${float(cash['min_p5']):,.0f} on day {cash['min_p5_day']}")
        if "health" in wanted:
            data_present = {t: bool(data[t]) for t in DATA_TABLES}
            health = health_score.compute(base_margins, cash, risk_out, base_inventory, inv_econ,
                                          ads_rows, forecast_rows, rec, data_present)
            _save_output(db, run_id, client["id"], "health", health)
            if health["status"] == "ok":
                top = health["top_drivers"][0] if health["top_drivers"] else None
                print(f"  health score: {float(health['score']):.0f}/100 (grade {health['grade']})"
                      + (f" — largest deduction {top['label'].lower()}, ${float(top['dollars_at_stake'] or 0):,.0f}" if top else ""))

        # the value ledger closes the loop on every run: what was delivered vs what was paid
        directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
        if claims is None:
            claims = _fetch_claims(db, client["id"])
        value_out = valuemod.compute(client, directives, claims, today)
        _save_output(db, run_id, client["id"], "value", value_out)
        print(f"  value ledger: ${float(value_out['value_total']):,.0f} delivered vs "
              f"${float(value_out['fees_paid']):,.0f} fees"
              + (f" — {float(value_out['roi_multiple']):.1f}× ({value_out['status']})"
                 if value_out["roi_multiple"] is not None else " (free month)"))

        if {"margin", "inventory", "elasticity", "ads"} <= wanted:
            pack = chart_pack.build_pack(
                margin_rows, elast_rows, inventory_rows, ads_rows,
                data["ppc_search_terms"], resolve_brand_terms(client),
                value=value_out, health=health, claims=claims, recovery=rec, forecast_rows=forecast_rows,
                inv_econ=inv_econ, risk=risk_out, anomaly_rows=anomaly_rows, today=today,
            )
            dbmod.chunked_upsert(db, "chart_packs",
                                 [{"run_id": run_id, "client_id": client["id"], "payload": pack}],
                                 on_conflict="run_id")
            print(f"  chart_packs: {', '.join(sorted(pack)) or 'empty'}")
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
    unknown = wanted - set(ALL_MODELS)
    if unknown:
        sys.exit(f"Unknown model(s): {', '.join(sorted(unknown))} — choose from {DEFAULT_MODELS}")
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
    search_terms = db.table("ppc_search_terms").select("*").eq("client_id", client["id"]).execute().data
    outputs = _load_outputs(db, run_id)
    drafts = draft_directives(results["inventory_sim_results"], results["ad_efficiency_results"],
                              results["elasticity_results"], results["margin_results"],
                              search_terms=search_terms, brand_terms=resolve_brand_terms(client),
                              recovery=outputs.get("recovery"), inv_econ=outputs.get("invecon"),
                              anomaly_rows=(outputs.get("anomaly") or {}).get("rows"))

    # file each directive into the active plan's matching initiative
    initiative_by_module = {}
    active = (db.table("plans").select("id").eq("client_id", client["id"])
              .eq("status", "active").limit(1).execute().data)
    if active:
        for i in db.table("initiatives").select("id, module").eq("plan_id", active[0]["id"]).execute().data:
            initiative_by_module[i["module"]] = i["id"]
    db.table("directives").delete().eq("client_id", client["id"]).eq("run_id", run_id).eq("status", "draft").execute()
    if not drafts:
        return []
    rows = [{
        "client_id": client["id"],
        "run_id": run_id,
        "module": d["module"],
        "action_text": d["action_text"],
        "expected_impact_usd": d["expected_impact_usd"],
        "initiative_id": initiative_by_module.get(d["module"]),
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


def cmd_approve(args):
    """Operator records the client's standing-mandate outcome for a directive:
    approved (default, veto window passed or explicit yes) or declined."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    candidates = (db.table("directives").select("id, status, action_text")
                  .eq("client_id", client["id"]).eq("status", "issued").execute().data)
    rows = [r for r in candidates if r["id"].startswith(args.directive.lower())]
    if len(rows) != 1:
        sys.exit(f"Issued-directive prefix {args.directive!r} matched {len(rows)} row(s) — need exactly 1.")
    status = "declined" if args.decline else "approved"
    db.table("directives").update({"status": status, "responded_at": _now()}).eq("id", rows[0]["id"]).execute()
    print(f"{status.capitalize()}: {rows[0]['action_text'][:80]}…"
          + ("" if args.decline else "  → execute it, then record the outcome with `hubricon measure`."))


def cmd_measure(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    candidates = (db.table("directives").select("id, status, action_text")
                  .eq("client_id", client["id"]).execute().data)
    rows = [r for r in candidates if r["id"].startswith(args.directive.lower())]
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


def _find_claim(db, client_id: str, prefix: str) -> dict:
    candidates = db.table("recovery_claims").select("*").eq("client_id", client_id).execute().data
    rows = [r for r in candidates if r["id"].startswith(prefix.lower())]
    if len(rows) != 1:
        sys.exit(f"Claim prefix {prefix!r} matched {len(rows)} row(s) — need exactly 1.")
    return rows[0]


def cmd_recover(args):
    """The reimbursement desk: list what the reconciliation found, mark
    claims filed, and record what Amazon actually paid — which is the only
    moment recovered money lands on the value ledger."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    today = date.today()

    if args.action == "list":
        rows = (db.table("recovery_claims").select("*").eq("client_id", client["id"])
                .neq("status", "dismissed").order("deadline").execute().data)
        if not rows:
            print("No claims on file — ingest the bleed reports (ledger, returns, reimbursements, "
                  "transactions) and `hubricon run`.")
            return
        print(f"Reimbursement desk — {client['company_name'] or client['contact_email']} (as of {today})\n")
        live_value = paid = 0.0
        for r in rows:
            state = chart_pack.claim_window_state(r, today)
            if state in ("open", "expiring", "filed", "not_yet_eligible"):
                live_value += float(r["value"] or 0)
            if r["status"] == "paid":
                paid += float(r["paid_amount"] or 0)
            extra = (f"paid ${float(r['paid_amount']):,.0f}" if r["status"] == "paid"
                     else f"case {r['case_id']}" if r.get("case_id") else "")
            print(f"  {r['id'][:8]}  {state:<17} {r['claim_type']:<23} {(r['sku'] or '')[:18]:<18} "
                  f"{int(r['units'] or 0):>4}u  ${float(r['value'] or 0):>9,.0f}  closes {r['deadline'] or '—'}  {extra}")
        print(f"\n  live face value ${live_value:,.0f} · recovered to date ${paid:,.0f} across "
              f"{sum(1 for r in rows if r['status'] == 'paid')} paid claim(s)")
        return

    if not args.claim:
        sys.exit(f"{args.action} needs --claim <id prefix>")
    claim = _find_claim(db, client["id"], args.claim)
    patch = {}
    if args.action == "file":
        patch = {"status": "filed", "filed_at": _now(), "case_id": args.case}
    elif args.action == "paid":
        if args.amount is None:
            sys.exit("paid needs --amount <usd Amazon actually sent>")
        patch = {"status": "paid", "paid_amount": args.amount, "paid_at": _now()}
        if args.case:
            patch["case_id"] = args.case
    elif args.action == "deny":
        patch = {"status": "denied", "denied_at": _now()}
    elif args.action == "dismiss":
        patch = {"status": "dismissed"}
    if args.notes:
        patch["notes"] = args.notes
    db.table("recovery_claims").update(patch).eq("id", claim["id"]).execute()
    print(f"{patch['status'].capitalize()}: {claim['claim_type']} · {claim['sku']} · {claim['units']} unit(s)"
          + (f" · ${args.amount:,.2f} lands on the value ledger at the next run" if args.action == "paid" else ""))


def cmd_health(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], None)
    h = _load_outputs(db, run["id"]).get("health")
    if not h or h.get("status") != "ok":
        sys.exit("No Health Score on the latest run — `hubricon run` (the health model needs margin data).")
    print(f"Health Score — {client['company_name'] or client['contact_email']}: "
          f"{float(h['score']):.0f}/100, grade {h['grade']} (period {h.get('period')})\n")
    for s in h["sub_scores"]:
        print(f"  {s['label']:<24} {float(s['score']):>5.0f}  weight {float(s['weight']):.0%}  "
              f"−{float(s['points_lost']):.1f} pts  ${float(s['dollars_at_stake'] or 0):>9,.0f} at stake")
        print(f"  {'':<24} {s['note']}")
    if h.get("excluded"):
        print(f"\n  excluded for lack of data: {', '.join(h['excluded'])}")


def cmd_value(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
    v = valuemod.compute(client, directives, _fetch_claims(db, client["id"]))
    print(f"Value ledger — {client['company_name'] or client['contact_email']} (as of {v['as_of']})")
    print(f"  engagement since {v['engagement_start']} · {v['months_elapsed']} month(s) · "
          f"{v['billed_months']} billed at ${float(v['monthly_fee']):,.0f}")
    print(f"  measured on directives  ${float(v['measured']):>10,.0f}  ({v['measured_count']})")
    print(f"  recovered from Amazon   ${float(v['recovered']):>10,.0f}  ({v['recovered_count']})")
    print(f"  value delivered         ${float(v['value_total']):>10,.0f}")
    print(f"  fees to date            ${float(v['fees_paid']):>10,.0f}")
    print(f"  return on fees          {str(round(float(v['roi_multiple']), 1)) + '×' if v['roi_multiple'] is not None else '— (free month)':>10}  [{v['status']}]")
    print(f"  identified, unbanked    ${float(v['identified_unbanked']):>10,.0f}  "
          f"(directives ${float(v['identified_parts']['directives']):,.0f}, claims ${float(v['identified_parts']['claims']):,.0f})")


def _find_test(db, client_id: str, prefix: str) -> dict:
    candidates = db.table("price_tests").select("*").eq("client_id", client_id).execute().data
    rows = [r for r in candidates if r["id"].startswith(prefix.lower())]
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


def cmd_plan(args):
    from datetime import date

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)

    if args.action == "status":
        plans = (db.table("plans").select("*").eq("client_id", client["id"])
                 .eq("status", "active").limit(1).execute().data)
        if not plans:
            sys.exit("No active plan — `hubricon plan <client> draft`, then commit.")
        plan = plans[0]
        run = _latest_run(db, client["id"], None)
        margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
        current = latest_period_totals(margins)
        total = (date.fromisoformat(plan["ends_on"]) - date.fromisoformat(plan["starts_on"])).days or 1
        elapsed = min(1.0, max(0.0, (date.today() - date.fromisoformat(plan["starts_on"])).days / total))
        print(f"{plan['label']} — day {int(elapsed * total)} of {total}")
        for metric, cur in (("net", current["net"]), ("revenue", current["revenue"])):
            b, t = float(plan[f"baseline_{metric}"] or 0), float(plan[f"target_{metric}"] or 0)
            state = pace(cur, b, t, elapsed)
            print(f"  {metric:<8} ${b:,.0f} → ${cur:,.0f} of ${t:,.0f}  [{state}]")
        return

    run = _latest_run(db, client["id"], None)
    margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .in_("status", ["draft", "issued", "approved", "done"]).execute().data)
    proposal = propose_plan(margins, directives)
    if proposal is None:
        sys.exit("No margin data yet — run the models first.")

    b, t = proposal["baseline"], proposal["targets"]
    print(f"{proposal['label']}  ({proposal['starts_on']} → {proposal['ends_on']})")
    print(f"  baseline: ${b['net']:,.0f} net / ${b['revenue']:,.0f} revenue"
          + (f" / {b['margin_pct']:.1%}" if b["margin_pct"] is not None else ""))
    print(f"  targets:  ${t['net']:,.0f} net / ${t['revenue']:,.0f} revenue"
          + (f" / {t['margin_pct']:.1%}" if t["margin_pct"] is not None else "")
          + f"   (70% of ${proposal['opportunity']:,.0f} identified)")
    for i in proposal["initiatives"]:
        exp = f" · ~${i['expected_impact_usd']:,.0f}" if i["expected_impact_usd"] else ""
        print(f"  — {i['title']} ({i['steps']} step(s){exp})")

    if args.action == "draft":
        print("\nEdit targets with --target-net/--target-revenue/--target-margin, then `plan commit`.")
        return

    # commit
    db.table("plans").update({"status": "superseded"}).eq("client_id", client["id"]).eq("status", "active").execute()
    plan_row = db.table("plans").insert({
        "client_id": client["id"],
        "label": args.label or proposal["label"],
        "starts_on": proposal["starts_on"],
        "ends_on": proposal["ends_on"],
        "baseline_net": b["net"], "baseline_revenue": b["revenue"], "baseline_margin_pct": b["margin_pct"],
        "target_net": args.target_net or t["net"],
        "target_revenue": args.target_revenue or t["revenue"],
        "target_margin_pct": args.target_margin or t["margin_pct"],
    }).execute().data[0]
    for sort, i in enumerate(proposal["initiatives"]):
        row = db.table("initiatives").insert({
            "client_id": client["id"], "plan_id": plan_row["id"],
            "title": i["title"], "thesis": i["thesis"], "module": i["module"],
            "expected_impact_usd": i["expected_impact_usd"], "sort": sort,
        }).execute().data[0]
        ids = [d["id"] for d in directives if d["module"] == i["module"]]
        if ids:
            db.table("directives").update({"initiative_id": row["id"]}).in_("id", ids).execute()
    print(f"\nCommitted {plan_row['label']} — live in the portal.")


def cmd_brand(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    db.table("clients").update({"brand_terms": args.terms}).eq("id", client["id"]).execute()
    terms = resolve_brand_terms({**client, "brand_terms": args.terms})
    print(f"Brand terms for {client['company_name'] or client['contact_email']}: {', '.join(terms)}")


def cmd_script(args):
    from datetime import date
    from .config import REPO_ROOT

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], None)
    margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
    elasticity = db.table("elasticity_results").select("*").eq("run_id", run["id"]).execute().data
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .neq("status", "draft").order("created_at", desc=True).limit(20).execute().data)
    alerts = (db.table("alerts").select("*").eq("client_id", client["id"])
              .order("created_at", desc=True).limit(10).execute().data)
    ledger_measured = sum(float(d["measured_impact_usd"] or 0) for d in directives)

    first_name = (client.get("contact_name") or "").split(" ")[0]
    company = client["company_name"] or client["contact_email"]
    deltas = period_deltas(margins)
    issue_count = db.table("briefings").select("id", count="exact", head=True).eq(
        "client_id", client["id"]).execute().count or 0

    script = build_script(company, first_name, deltas, directives, alerts, elasticity,
                          ledger_measured, len(directives))
    memo = build_memo(company, first_name, deltas, directives, alerts, elasticity,
                      ledger_measured, len(directives), issue_number=issue_count + 1)

    folder = REPO_ROOT / "reports" / (client["company_name"] or client["id"][:8]).lower().replace(" ", "-")
    folder.mkdir(parents=True, exist_ok=True)
    script_path = folder / f"script-{date.today().isoformat()}.md"
    memo_path = folder / f"memo-{date.today().isoformat()}.md"
    script_path.write_text(script, encoding="utf-8")
    memo_path.write_text(memo, encoding="utf-8")
    print(script)
    print(f"\nSaved narration: {script_path}")
    print(f"Saved letter draft (edit, then `hubricon brief --memo-file`): {memo_path}")

    # The narrated letter: Claude writes, the engine supplies every number.
    outputs = _load_outputs(db, run["id"])
    facts = narrate.build_facts(
        company, first_name, deltas, directives, alerts, ledger_measured, len(directives),
        issue_number=issue_count + 1, health=outputs.get("health"), value=outputs.get("value"),
        recovery=outputs.get("recovery"), forecast_rows=(outputs.get("forecast") or {}).get("rows"),
        risk=outputs.get("risk"), anomaly_summary=summarize_anomalies((outputs.get("anomaly") or {}).get("rows") or []),
        inv_econ=outputs.get("invecon"),
    )
    if args.facts:
        print("\nFACTS the narrator may cite (every figure the engine computed):")
        print(narrate.facts_json(facts))
    if args.no_ai or not narrate.available():
        print("\nNarrated letter: skipped" + ("" if args.no_ai else " (set ANTHROPIC_API_KEY to enable)")
              + " — the template letter above is the draft.")
        return
    result = narrate.narrate(facts)
    if result["text"]:
        ai_path = folder / f"memo-ai-{date.today().isoformat()}.md"
        ai_path.write_text(result["text"], encoding="utf-8")
        print(f"\nNarrated letter by {result['model']}: {result['placeholders']} figures substituted from the "
              f"engine, none originated by the model (number guard passed in {result['attempts']} attempt(s)).")
        print(f"Saved: {ai_path}")
    else:
        print(f"\nNarrated letter fell back to the template: {result['reason']}")


def cmd_brief(args):
    from pathlib import Path

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)

    video_id = None
    if args.video:
        video_id = parse_loom_id(args.video)
        if not video_id:
            sys.exit(f"Couldn't read a Loom video id from {args.video!r} — paste the share URL.")
    memo = Path(args.memo_file).read_text(encoding="utf-8") if args.memo_file else None
    if not video_id and not memo:
        sys.exit("An issue needs a --video, a --memo-file, or both.")

    issue = (db.table("briefings").select("id", count="exact", head=True)
             .eq("client_id", client["id"]).execute().count or 0) + 1

    report_path = None
    if args.report:
        report_file = Path(args.report)
        if not report_file.exists():
            sys.exit(f"No such report file: {args.report}")
        report_path = f"reports/{client['id']}/issue-{issue:03d}.html"
        db.storage.from_(storage.BUCKET).upload(
            report_path, report_file.read_bytes(),
            {"content-type": "text/html", "upsert": "true"},
        )

    run = _latest_run(db, client["id"], None) if not args.no_run else None
    db.table("briefings").insert({
        "client_id": client["id"],
        "run_id": run["id"] if run else None,
        "video_id": video_id,
        "memo": memo,
        "issue_number": issue,
        "report_path": report_path,
        "title": args.title,
        "tldr": args.tldr,
        "headline": args.headline,
    }).execute()
    parts = [p for p, on in (("video", video_id), ("letter", memo), ("report", report_path)) if on]
    print(f"Issue No. {issue:03d} ({' + '.join(parts)}) published to the portal for "
          f"{client['company_name'] or client['contact_email']}.")


def cmd_goals(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    db.table("clients").update({"goals": args.set}).eq("id", client["id"]).execute()
    print(f"Objective on file for {client['company_name'] or client['contact_email']}: {args.set}")


def cmd_cash(args):
    """Record the client-stated cash inputs, then compute and store the
    horizon against the latest run so the number is never stale."""
    from datetime import date, timedelta

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    patch = {}
    if args.balance is not None:
        patch["cash_on_hand"] = args.balance
        patch["cash_as_of"] = args.as_of or date.today().isoformat()
    if args.opex is not None:
        patch["monthly_fixed_costs"] = args.opex
    if patch:
        db.table("clients").update(patch).eq("id", client["id"]).execute()
        client = {**client, **patch}
    if client.get("cash_on_hand") is None or client.get("monthly_fixed_costs") is None:
        sys.exit("Need both --balance and --opex on file before the horizon can run.")

    run = _latest_run(db, client["id"], None)
    inventory = db.table("inventory_sim_results").select("*").eq("run_id", run["id"]).execute().data
    margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
    cash = cashflow.run(client, inventory, margins, np.random.default_rng(42))
    if cash is None:
        sys.exit("No revenue machinery to simulate yet — ingest data and `hubricon run` first.")
    dbmod.chunked_upsert(db, "cash_horizon_results",
                         [{**cash, "run_id": run["id"], "client_id": client["id"]}],
                         on_conflict="run_id")

    today = date.today()
    print(f"Cash horizon — {client['company_name'] or client['contact_email']}")
    print(f"  inputs: ${float(client['cash_on_hand']):,.0f} on hand "
          f"(as of {client.get('cash_as_of') or today.isoformat()}), "
          f"${float(client['monthly_fixed_costs']):,.0f}/mo fixed costs")
    print(f"  p(dip below $0 in {cash['horizon_days']}d): {float(cash['p_ruin']):.1%}")
    print(f"  5th-percentile low: ${float(cash['min_p5']):,.0f} around "
          f"{(today + timedelta(days=cash['min_p5_day'])).strftime('%b %d')}")
    for w in cash["details"]["wires"][:6]:
        print(f"  wire {(today + timedelta(days=w['day'])).strftime('%b %d')}: "
              f"${w['amount']:,.0f} — {w['sku']}")


def cmd_console(args):
    """Self-contained dark console (HTML file) to screen-share while
    recording the Loom. Internal artifact — clients receive the brief."""
    from datetime import date
    from .config import REPO_ROOT
    from .console import build_console

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], None)
    margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
    fits = db.table("elasticity_results").select("*").eq("run_id", run["id"]).execute().data
    inventory = db.table("inventory_sim_results").select("*").eq("run_id", run["id"]).execute().data
    cash_rows = db.table("cash_horizon_results").select("*").eq("run_id", run["id"]).execute().data
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .neq("status", "draft").order("created_at", desc=True).execute().data)

    html = build_console(
        company=client["company_name"] or client["contact_email"],
        directives=directives,
        cash=cash_rows[0] if cash_rows else None,
        margins=margins,
        elasticity_rows=fits,
        inventory_rows=inventory,
        generated_on=date.today(),
    )
    folder = REPO_ROOT / "reports" / (client["company_name"] or client["id"][:8]).lower().replace(" ", "-")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"console-{date.today().isoformat()}.html"
    path.write_text(html, encoding="utf-8")
    print(f"Briefing console: {path}")
    print("Open it full-screen, hit record — it is internal; the client gets the Loom link.")


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
    prev_health = _load_outputs(db, prev_runs[0]["id"] if prev_runs else None).get("health")

    run_id = _run_models(db, client, set(ALL_MODELS), 20000, 42)
    summary["ran"] = True
    summary["drafts"] = len(_draft_for_run(db, client, run_id))

    inventory = db.table("inventory_sim_results").select("*").eq("run_id", run_id).execute().data
    margins = db.table("margin_results").select("*").eq("run_id", run_id).execute().data
    tests = db.table("price_tests").select("*").eq("client_id", client["id"]).execute().data
    cash_rows = db.table("cash_horizon_results").select("*").eq("run_id", run_id).execute().data
    outputs = _load_outputs(db, run_id)

    from datetime import timedelta
    window = (datetime.now(timezone.utc) - timedelta(days=DEDUPE_DAYS)).isoformat()
    recent = {a["message"] for a in
              db.table("alerts").select("message").eq("client_id", client["id"])
              .gte("created_at", window).execute().data}
    fresh = dedupe(compute_alerts(inventory, prev_inventory, margins, tests,
                                  cash_rows[0] if cash_rows else None,
                                  recovery=outputs.get("recovery"),
                                  anomaly_rows=(outputs.get("anomaly") or {}).get("rows"),
                                  health=outputs.get("health"), previous_health=prev_health), recent)
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
    if not args.alert:
        return
    if not founder or not email_configured():
        print("\nDigest not emailed: set FOUNDER_EMAIL and RESEND_API_KEY.")
    elif send_email(founder, "Hubricon sweep digest", digest):
        print(f"\nDigest emailed to {founder}.")
    else:
        print(f"\nDigest NOT emailed to {founder} — see the error above.")


def cmd_all(args):
    cmd_ingest(args)
    cmd_run(args)
    args.run = None
    cmd_report(args)


def cmd_operator(args):
    from . import operator

    operator.run(send=args.send, dry=args.dry_run, digest=args.digest)


def cmd_scoreboard(_args):
    import json

    db = dbmod.connect()
    print(json.dumps(db.rpc("pmf_scoreboard", {}).execute().data, indent=2, default=str))


def cmd_doctor(args):
    """Why is or isn't the cold campaign sending. Read-only; never sends anything.

    On the founder's Mac there is no INSTANTLY_API_KEY (it lives in the GitHub
    Actions Production environment) and no gh CLI, so a live check is usually
    impossible here. The hourly operator writes its findings to operator_state,
    and this command reads them back — the database is the shared log.
    """
    import json

    from . import outbound
    from .instantly import Instantly

    db = dbmod.connect()
    out: dict = {}

    have_key = bool(os.environ.get("INSTANTLY_API_KEY"))
    print("Environment")
    for name in ("INSTANTLY_API_KEY", "POSTAL_ADDRESS", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                 "RESEND_API_KEY", "ANTHROPIC_API_KEY", "CALENDLY_URL"):
        mark = "set" if os.environ.get(name) else "missing"
        print(f"  {name:<26} {mark}")
    if not have_key:
        print("  (INSTANTLY_API_KEY lives in GitHub → Settings → Environments → Production;")
        print("   without it this command reports what the hourly operator last saw.)")
    print()

    state = outbound.get_state(db, "instantly.campaign", {}) or {}
    cid = state.get("id")
    if have_key and cid:
        health = outbound.health(db, Instantly(), cid)
        source = "live"
    else:
        health = outbound.get_state(db, "instantly.health", {}) or {}
        source = f"recorded by the operator at {health.get('as_of', 'never')}"
    out["health"] = health

    print(f"Instantly ({source})")
    if not health:
        print("  nothing recorded yet — the operator has not run since this check was added.")
    else:
        camp = health.get("campaign") or {}
        print(f"  campaign   {cid} status {camp.get('status')} ({camp.get('status_name')})")
        print(f"  mailboxes  " + ", ".join(
            f"{m['email']} (status {m['status']}, warmup {m['warmup_status']})"
            for m in health.get("mailboxes") or []) or "  mailboxes  none")
        leads = health.get("leads") or {}
        print(f"  leads      {leads.get('total', 0)} enrolled, {leads.get('contacted', 0)} ever contacted")
        print(f"  analytics  {health.get('analytics')}")
    print()

    sb = db.rpc("pmf_scoreboard", {}).execute().data
    out["scoreboard"] = sb
    print("Funnel")
    print(f"  {sb}")
    print()

    try:
        from .harvest import run as harvest
        print(harvest.status_text(db))
        print()
    except Exception as err:
        print(f"Harvest status unavailable: {err}\n")

    verdicts = (health or {}).get("verdicts") or []
    print("Verdicts")
    if verdicts:
        for v in verdicts:
            print(f"  - {v}")
    else:
        print("  nothing flagged.")

    if args.json:
        print(json.dumps(out, indent=2, default=str))


def cmd_outreach(args):
    """The manual lane. Prints briefs and drafts; never sends anything."""
    from . import outbound, outreach

    db = dbmod.connect()

    if args.action == "dq":
        rows = outreach.dq_scan(db)
        print(outreach.dq_text(rows))
        if args.apply and rows:
            print()
            outreach.apply_dq(db, rows)
        elif rows:
            print("\nNothing was written. Re-run with --apply to disqualify these.")
        return

    if args.action == "targets":
        keep = outreach.targets(db, args.limit)
        ready = sum(1 for r in keep if r["ready"])
        print(f"{len(keep)} seller(s) worth a hand-written email, best first.")
        print(f"{ready} are ready to write: a named owner and a number to open with.\n")
        for r in keep:
            rev = float(r.get("est_monthly_revenue") or 0)
            print(f"  {outreach.target_label(r):<28} {(r.get('brand') or '')[:22]:<22} "
                  f"{(r.get('email') or '')[:30]:<30} ${rev:,.0f}/mo  {r['seller_id']}")
        print("\nNext: hubricon outreach pack --limit 8   (the whole batch, briefs and drafts)")
        return

    if args.action == "pack":
        text = outreach.pack_text(db, args.limit, outbound.CALENDLY_URL)
        if args.out:
            with open(args.out, "w") as fh:
                fh.write(text + "\n")
            print(f"Wrote {args.out}")
        else:
            print(text)
        return

    facts = outreach.seller_facts(db, args.seller)
    if facts is None:
        print(f"No seller {args.seller!r} on file.")
        return
    if args.action == "brief":
        print(outreach.brief_text(facts))
        return
    if args.action == "draft":
        first = args.first_name or facts["seller"].get("first_name")
        if not first:
            print("No first name. Find the owner's name and pass --first-name; "
                  "a cold email that opens 'Hi Acme team' is not the founder lane.")
            return
        d = outreach.founder_email(facts, first, outbound.CALENDLY_URL)
        print(f"To:      {d['to']}\nSubject: {d['subject']}\n\n{d['body']}")
        print("--- send this by hand from your own mailbox, after editing it. ---")
        return
    if args.action == "partner":
        if not args.partner or not args.referral:
            print("Need --partner 'Name' and --referral 'the terms you are offering', e.g. "
                  "--referral '15% of anything that renews'. Do not send a template that "
                  "promises a number you have not decided.")
            return
        d = outreach.partner_email(facts, args.partner, args.referral)
        print(f"Subject: {d['subject']}\n\n{d['body']}")
        print(outreach.PARTNER_TARGETS)
        return


def cmd_harvest(args):
    """Free leads from public pages; runs on the founder's Mac (Amazon captchas datacenters)."""
    from .harvest import run as harvest

    if args.action == "install":
        print(harvest.install_launchd())
        return
    db = dbmod.connect()
    if args.action == "status":
        print(harvest.status_text(db))
        return
    if args.action == "report":
        print(harvest.fee_cliff_text(db, args.within_oz))
        return
    max_products = args.max_products or harvest.MAX_PRODUCTS
    fetcher = harvest.Fetcher()
    if args.action == "all":
        harvest.run_all(db, fetcher, dry=args.dry_run, max_products=max_products, categories=args.categories)
    elif args.action == "crawl":
        harvest.crawl(db, fetcher, categories=args.categories, max_products=max_products)
    elif args.action == "enrich":
        harvest.enrich(db, fetcher, limit=args.limit or harvest.ENRICH_LIMIT)
    elif args.action == "push":
        from . import instantly

        api = instantly.Instantly() if instantly.configured() else None
        harvest.push(db, api, limit=args.limit or harvest.PUSH_LIMIT, dry=args.dry_run)
    elif args.action == "wayback":
        from pathlib import Path

        from .harvest import wayback

        captures = wayback.load_captures(fetcher, Path(args.cdx_file) if args.cdx_file else None)
        wayback.crawl(db, captures, limit=args.limit or wayback.LIMIT, workers=args.workers or wayback.WORKERS)
    elif args.action == "requalify":
        harvest.requalify(db, fetcher, limit=args.limit or harvest.REQUALIFY_LIMIT)
    elif args.action == "prune":
        from . import instantly

        api = instantly.Instantly() if instantly.configured() else None
        harvest.prune(db, api, dry=args.dry_run)


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
    p.add_argument("--models", default=DEFAULT_MODELS, help=f"comma-separated subset of {DEFAULT_MODELS}")
    p.add_argument("--simulations", type=int, default=20000)
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("recover", help="the reimbursement desk: list, file, paid, deny, dismiss")
    p.add_argument("client")
    p.add_argument("action", choices=["list", "file", "paid", "deny", "dismiss"])
    p.add_argument("--claim", help="claim id prefix")
    p.add_argument("--case", help="Seller Central case id")
    p.add_argument("--amount", type=float, help="USD Amazon actually paid (for `paid`)")
    p.add_argument("--notes")
    p.set_defaults(fn=cmd_recover)

    p = sub.add_parser("health", help="print the latest Health Score with its driver decomposition")
    p.add_argument("client")
    p.set_defaults(fn=cmd_health)

    p = sub.add_parser("value", help="print the value ledger: delivered vs fees")
    p.add_argument("client")
    p.set_defaults(fn=cmd_value)

    p = sub.add_parser("directives", help="draft (and optionally issue) Decision Ledger directives from a run")
    p.add_argument("client")
    p.add_argument("--run", help="model_runs id (default: latest succeeded)")
    p.add_argument("--issue", action="store_true", help="issue the drafts to the client portal")
    p.set_defaults(fn=cmd_directives)

    p = sub.add_parser("ledger", help="print the client's Decision Ledger")
    p.add_argument("client")
    p.set_defaults(fn=cmd_ledger)

    p = sub.add_parser("approve", help="record a standing-mandate outcome for an issued directive")
    p.add_argument("client")
    p.add_argument("--directive", required=True, help="directive id prefix")
    p.add_argument("--decline", action="store_true", help="client vetoed it")
    p.set_defaults(fn=cmd_approve)

    p = sub.add_parser("measure", help="record the measured impact of a directive")
    p.add_argument("client")
    p.add_argument("--directive", required=True, help="directive id prefix")
    p.add_argument("--impact", required=True, type=float, help="measured impact in USD")
    p.add_argument("--notes", help="how the measurement was made")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("plan", help="draft, commit, or check the client's 90-day growth plan")
    p.add_argument("client")
    p.add_argument("action", choices=["draft", "commit", "status"])
    p.add_argument("--label", help='override the quarter label, e.g. "Q4 2026"')
    p.add_argument("--target-net", type=float)
    p.add_argument("--target-revenue", type=float)
    p.add_argument("--target-margin", type=float)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("brand", help="set a client's brand terms for cannibalization detection")
    p.add_argument("client")
    p.add_argument("--terms", required=True, help='comma-separated, e.g. "acme,acme labs"')
    p.set_defaults(fn=cmd_brand)

    p = sub.add_parser("script", help="generate the briefing narration script and letter from the latest run")
    p.add_argument("client")
    p.add_argument("--no-ai", dest="no_ai", action="store_true", help="skip the Claude-narrated letter")
    p.add_argument("--facts", action="store_true", help="print the FACTS table the narrator may cite")
    p.set_defaults(fn=cmd_script)

    p = sub.add_parser("brief", help="publish an Issue (video and/or letter, optional full report) to the portal")
    p.add_argument("client")
    p.add_argument("--video", help="Loom share URL or video id")
    p.add_argument("--memo-file", help="path to the edited letter (markdown/plain text)")
    p.add_argument("--report", help="path to the full written report HTML to attach")
    p.add_argument("--tldr", help="3-4 sentence summary shown under the video")
    p.add_argument("--headline", help="one headline stat, e.g. '+$9,200 vs July'")
    p.add_argument("--title", help="issue title (default 'Issue No. N')")
    p.add_argument("--no-run", action="store_true", help="don't link the latest model run")
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("goals", help="record the client's stated objective (shown on their masthead)")
    p.add_argument("client")
    p.add_argument("--set", required=True, help='e.g. "Grow to $5M/yr without giving back margin"')
    p.set_defaults(fn=cmd_goals)

    p = sub.add_parser("cash", help="record cash inputs and compute the 90-day cash-flow horizon")
    p.add_argument("client")
    p.add_argument("--balance", type=float, help="cash on hand (USD)")
    p.add_argument("--opex", type=float, help="monthly fixed operating costs (USD)")
    p.add_argument("--as-of", dest="as_of", help="balance date YYYY-MM-DD (default today)")
    p.set_defaults(fn=cmd_cash)

    p = sub.add_parser("console", help="render the internal briefing console for Loom screen-share")
    p.add_argument("client")
    p.set_defaults(fn=cmd_console)

    p = sub.add_parser("sweep", help="always-on pass over every active client: ingest, run, draft, alert")
    p.add_argument("--client", help="sweep just this client")
    p.add_argument("--alert", action="store_true", help="send alert/digest emails (needs RESEND_API_KEY)")
    p.set_defaults(fn=cmd_sweep)

    p = sub.add_parser("operator", help="hourly funnel pass: outbound, bookings, nudges, teardowns, digest")
    p.add_argument("--send", action="store_true", help="actually send emails and Instantly replies")
    p.add_argument("--dry-run", action="store_true", help="read everything, change nothing")
    p.add_argument("--digest", action="store_true", help="email the founder the digest (with --send)")
    p.set_defaults(fn=cmd_operator)

    sub.add_parser("scoreboard", help="print the PMF scoreboard").set_defaults(fn=cmd_scoreboard)

    p = sub.add_parser("doctor", help="why the cold campaign is or isn't sending (read-only)")
    p.add_argument("--json", action="store_true", help="also dump the raw findings as JSON")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("outreach", help="the manual lane: briefs and drafts you send by hand")
    p.add_argument("action", choices=["dq", "targets", "pack", "brief", "draft", "partner"])
    p.add_argument("--seller", help="seller_id, for brief/draft/partner")
    p.add_argument("--first-name", dest="first_name", help="the owner's name, once you have found it")
    p.add_argument("--partner", help="the partner's first name, for the partner template")
    p.add_argument("--referral", help="the referral terms you are offering")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--apply", action="store_true", help="dq: actually write the disqualifications")
    p.add_argument("--out", help="pack: write the batch to this file instead of stdout")
    p.set_defaults(fn=cmd_outreach)

    p = sub.add_parser("harvest", help="free leads: Amazon Best Sellers / archived seller profiles → brand sites → Instantly list")
    p.add_argument("action", choices=["crawl", "enrich", "push", "all", "status", "report", "install",
                                      "wayback", "requalify", "prune"])
    p.add_argument("--categories", nargs="*", help="Best Sellers slugs (default: three, rotating by day)")
    p.add_argument("--within-oz", dest="within_oz", type=float, default=1.0,
                   help="report: ounces above a lighter FBA weight band that count as a cliff (default 1)")
    p.add_argument("--max-products", dest="max_products", type=int, help="product pages per run (default 150)")
    p.add_argument("--limit", type=int, help="rows to enrich / push this run")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="push/prune: report, don't touch Instantly")
    p.add_argument("--workers", type=int, help="wayback: parallel fetchers against web.archive.org (default 3)")
    p.add_argument("--cdx-file", dest="cdx_file", help="wayback: saved CDX listing (default ~/.hubricon/harvest/wayback-sellers.cdx)")
    p.set_defaults(fn=cmd_harvest)

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
        fn=cmd_all, reparse=False, upload_id=None, models=DEFAULT_MODELS,
        simulations=20000, seed=42, run=None, out=None,
    )

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
