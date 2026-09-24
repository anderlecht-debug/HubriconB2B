"""hubricon — operator CLI.

    hubricon clients
    hubricon platform   <client> amazon|shopify|both [--shopify-domain d]
    hubricon ingest     <client> [--reparse] [--upload-id ID]
    hubricon run        <client> [--models margin,forecast,inventory,...] [--simulations N] [--seed N]
                                 [--channel amazon|shopify]
    hubricon directives <client> [--run ID] [--issue]
    hubricon ledger     <client>
    hubricon measure    <client> --directive <id-prefix> --impact <usd> [--notes TEXT]
    hubricon recover    <client> list | file --claim ID [--case N] | paid --claim ID --amount X | deny | dismiss
    hubricon health     <client>
    hubricon value      <client>
    hubricon script     <client> [--no-ai]
    hubricon report     <client> [--run ID] [--out DIR]
    hubricon all        <client>

    hubricon teardown   [build|review|show|open|approve|sent|stats|ratecard]
    hubricon source     [discover|qualify|contact|sheet|push|promote|all|status|calibrate|install]

<client> is a client uuid, uuid prefix, or contact email.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

import numpy as np

from . import __version__
from . import chart_pack
from . import channels
from . import db as dbmod
from . import narrate
from . import onboarding
from . import storage
from . import issue
from . import measurement
from . import value as valuemod
from . import calibration, proof, referral, speed
from . import loop as loopmod
from .alerts import DEDUPE_DAYS, compute_alerts, dedupe
from .briefing import build_memo, build_script, parse_loom_id, period_deltas
from .directives import draft_directives, plan_prices, resolve_brand_terms, trim_candidates
from .growth_plan import latest_period_totals, pace, propose_plan
from .ingest import PARSERS, parse_all
from .notify import alert_email_body, email_configured, send_email

# One definition of where the client's desk lives, shared with the operator.
PORTAL_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com") + "/portal"
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
    ad_allocation, ad_efficiency, anomaly, assortment, cash_orders, cashflow, clv, cross_price, data_quality, drift,
    elasticity, forecast, health_score, stress,
    incrementality, inventory_econ, inventory_sim, margin, markdown, price_experiment, recovery, replenishment, risk,
    seasonality,
)
from .models.anomaly import summarize as summarize_anomalies

# The six canonical tables that carry a `channel`: a run reads only its own
# platform's rows out of them, so a brand selling on both never has its
# Amazon units added to its Shopify ones.
CHANNEL_TABLES = (
    "asin_traffic",
    "sku_economics",
    "ppc_search_terms",
    "ppc_spend",
    "inventory_levels",
    "settlement_transactions",
    "customer_orders",
)
# Amazon's bleed exports. They describe a warehouse holding a seller's units;
# a Shopify store has none, so a Shopify run loads nothing from them rather
# than reading Amazon rows into a Shopify picture.
AMAZON_ONLY_TABLES = ("fba_reimbursements", "fba_returns", "inventory_ledger", "inventory_health")
# The cost sheet is the client's own and belongs to the SKU, not a channel.
SHARED_TABLES = ("cogs_inputs",)
DATA_TABLES = CHANNEL_TABLES + SHARED_TABLES + AMAZON_ONLY_TABLES

# Every model, in dependency order: forecast feeds inventory, inventory
# economics and risk; cash feeds health; value closes the loop.
ALL_MODELS = ("dataq", "margin", "season", "experiments", "elasticity", "forecast", "inventory", "crossprice", "anomaly",
              "incrementality", "clv", "ads", "adalloc", "recovery", "risk", "invecon", "markdown", "replenish",
              "assortment", "cash", "cashorders", "stress", "health")
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
        "sku", "asin", "period_start", "period_end", "units", "revenue", "amazon_fees", "fee_split",
        "cogs", "ad_spend_allocated", "net_margin", "net_margin_pct", "forecast",
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
            # one export may feed two tables (Shopify's products export is
            # both the unit-cost sheet and the stock snapshot)
            written = parse_all(upload["report_type"], read_table(data), upload)
            total = sum(len(rows) for _, rows, _ in written)
            if not total:
                raise IngestError("No usable data rows after parsing")
            for table, rows, on_conflict in written:
                if rows:
                    dbmod.chunked_upsert(db, table, rows, on_conflict)
            db.table("uploads").update(
                {"status": "parsed", "row_count": total, "parse_error": None, "parsed_at": _now()}
            ).eq("id", upload["id"]).execute()
            parsed += 1
            print(f"  parsed  {label}: "
                  + ", ".join(f"{len(rows)} rows -> {table}" for table, rows, _ in written if rows))
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


def _load_data(db, client_id: str, channel: str = "amazon") -> dict:
    """The canonical tables as one channel sees them. Every model reads this
    dict, so filtering here is what keeps a two-platform client's Amazon and
    Shopify numbers from being added together."""
    data = {t: dbmod.fetch_all(db, t, client_id, filters={"channel": channel}) for t in CHANNEL_TABLES}
    data.update({t: dbmod.fetch_all(db, t, client_id) for t in SHARED_TABLES})
    data.update({t: (dbmod.fetch_all(db, t, client_id) if channel == "amazon" else [])
                 for t in AMAZON_ONLY_TABLES})
    return data


def _pad(rows: list[dict], table: str) -> list[dict]:
    cols = RESULT_COLUMNS[table]
    return [{c: row.get(c) for c in cols} for row in rows]


def _save_output(db, run_id: str, client_id: str, model: str, payload) -> None:
    dbmod.chunked_upsert(
        db, "model_outputs",
        [{"run_id": run_id, "client_id": client_id, "model": model, "payload": payload}],
        on_conflict="run_id,model",
    )


def _load_price_tests(db, client_id: str, designed: bool = True) -> list[dict]:
    rows = db.table("price_tests").select("*").eq("client_id", client_id).execute().data
    return [r for r in rows if r.get("design")] if designed else rows


def _load_experiments(db, run_id: str | None) -> list[dict]:
    return ((_load_outputs(db, run_id).get("price_experiments") or {}).get("rows") or []) if run_id else []


def _load_switchbacks(db, client_id: str) -> list[dict]:
    """Every ON/OFF ad test the client has planned, with its analysis when one
    has run. They live in model_outputs under `ad_switchback:<campaign>` on the
    run current when they were planned, so they outlive any single run."""
    rows = (db.table("model_outputs").select("model, payload").eq("client_id", client_id)
            .like("model", "ad_switchback:%").execute().data)
    return [r["payload"] for r in rows if r.get("payload")]


def _load_outputs(db, run_id: str | None) -> dict:
    if not run_id:
        return {}
    rows = db.table("model_outputs").select("model, payload").eq("run_id", run_id).execute().data
    return {r["model"]: r["payload"] for r in rows}


def _fetch_claims(db, client_id: str) -> list[dict]:
    return (db.table("recovery_claims").select("*").eq("client_id", client_id)
            .order("deadline").execute().data)


def _fetch_invoices(db, client_id: str) -> list[dict]:
    """What Stripe says we billed. Degrades to an empty list rather than
    failing a whole run when the invoices migration has not been applied yet —
    the ledger then reports its fee basis as 'assumed' and says so."""
    try:
        return (db.table("invoices").select("*").eq("client_id", client_id)
                .order("period_start").execute().data)
    except Exception as err:
        print(f"  invoices unavailable ({err}); fees fall back to the assumed basis")
        return []


def _close_settled_claims(db, client_id: str, settled: dict, today: date) -> int:
    """Mark claims Amazon actually paid.

    The FIFO matcher in models/recovery has always known which reimbursement
    closed which loss — it just used the answer to suppress re-detection and
    threw the pairing away. So a claim Amazon PAID stopped being re-detected,
    sat at 'detected', and was then stamped 'expired' by the sweep below: a
    third-party-confirmed win recorded as a miss, with the dollars never
    reaching the ledger. This closes them from Amazon's own record."""
    if not settled:
        return 0
    rows = (db.table("recovery_claims").select("id, claim_key, status, filed_at, case_id, notes")
            .eq("client_id", client_id).in_("status", ["detected", "filed"]).execute().data)
    closed = 0
    for row in rows:
        s = settled.get(row["claim_key"])
        if not s:
            continue
        patch = {
            "status": "paid",
            "paid_amount": s["paid_amount"],
            "paid_at": s["paid_at"],
            "case_id": row.get("case_id") or s.get("case_id"),
            "notes": " ".join(x for x in (row.get("notes"), s["note"]) if x),
        }
        db.table("recovery_claims").update(patch).eq("id", row["id"]).execute()
        closed += 1
        # Only claims we filed reach value.recovered; an unfiled one closes for
        # the client's record but is Amazon's own reconciliation, not our result.
        banked = "banked" if row.get("filed_at") else "not banked — no filing of ours"
        print(f"  claim {row['claim_key'][:8]} settled: ${s['paid_amount']:,.2f} ({banked})")
    return closed


def _sync_claims(db, client_id: str, run_id: str, rec: dict, today: date) -> list[dict]:
    """Detected claims land in recovery_claims without touching a claim's
    lifecycle (filed/denied are the operator's to set), then anything Amazon
    has settled is closed from its own reimbursement records, and only then
    does the expiry sweep run. That order matters: expiring before closing is
    what filed paid claims as misses.
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
    _close_settled_claims(db, client_id, rec.get("settlements") or {}, today)
    # Belt and braces: never expire something already recorded as paid.
    (db.table("recovery_claims").update({"status": "expired"}).eq("client_id", client_id)
     .eq("status", "detected").is_("paid_at", "null").lt("deadline", today.isoformat()).execute())
    return _fetch_claims(db, client_id)


def _run_models(db, client: dict, wanted: set[str], simulations: int, seed: int,
                channel: str | None = None) -> str:
    """One run over one channel. None means "read it off the client", which is
    every single-platform client; a client on both is run once per channel by
    the caller, and the channel is recorded in params so the report, the
    directives and the memo can say which platform they are talking about."""
    channel = channel or channels.client_channel(client) or "amazon"
    data = _load_data(db, client["id"], channel)
    counts = {t: len(rows) for t, rows in data.items() if rows}
    print(f"Data ({channels.label(channel)}): {counts}")

    run = (
        db.table("model_runs")
        .insert(
            {
                "client_id": client["id"],
                "engine_version": __version__,
                "git_sha": _git_sha(),
                "params": {"models": sorted(wanted), "simulations": simulations, "seed": seed,
                           "channel": channel},
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
        ad_breaks = cross = None
        rec = inv_econ = risk_out = cash = health = claims = None
        dq = None
        if "dataq" in wanted:
            # before any model: do the exports agree with each other, and are they all there
            dq = data_quality.run(data, today)
            _save_output(db, run_id, client["id"], "data_quality", dq)
            print(f"  data quality: {dq['status']} — {dq['basis']}")

        if "margin" in wanted:
            margin_rows = margin.run(data)
            avg_margin = margin.average_margin(margin_rows)
            _write_results(db, "margin_results", margin_rows, run_id, client["id"])
        seasonal = None
        if "season" in wanted:
            seasonal = seasonality.indices(data)
            _save_output(db, run_id, client["id"], "seasonality", seasonal)
            print("  seasonality: "
                  + (f"peak-to-trough {float(seasonal['amplitude']):.2f}× over {seasonal['months_observed']} months "
                     f"({seasonal['basis_label']})" if seasonal["status"] == "ok"
                     else f"{seasonal['status']} — {seasonal.get('basis', '')}"))
        # the fits before the forecast: it restates each month's demand at
        # today's price on the SKU's own elasticity
        experiments = None
        if "experiments" in wanted:
            tests = _load_price_tests(db, client["id"])
            if tests:
                # the observational fit first, so the experiment can say how far
                # the history's curve was off; then the fit the optimizer uses
                experiments = price_experiment.run(data, tests, elasticity.run(data, seasonal=seasonal))
                _save_output(db, run_id, client["id"], "price_experiments", {"rows": experiments})
                for e in experiments:
                    if e.get("test_id"):
                        db.table("price_tests").update({"analysis": e}).eq("id", e["test_id"]).execute()
                ok = [e for e in experiments if e["status"] == "ok"]
                print(f"  price experiments: {len(ok)} of {len(experiments)} analysed"
                      + (f"; bias vs history {', '.join(f'{e['item_id']} {e['details'].get('bias_estimate'):+.2f}' for e in ok if e['details'].get('bias_estimate') is not None)}"
                         if any(e["details"].get("bias_estimate") is not None for e in ok) else ""))
        # the previous succeeded run on this channel: what the fits looked like last time
        prev_run = _latest_run(db, client["id"], None, channel, required=False)
        prev_el = (db.table("elasticity_results").select("*").eq("run_id", prev_run["id"]).execute().data
                   if prev_run else [])
        prev_ads = (db.table("ad_efficiency_results").select("*").eq("run_id", prev_run["id"]).execute().data
                    if prev_run else [])
        if "elasticity" in wanted:
            elast_rows = elasticity.run(data, experiments=experiments, seasonal=seasonal)
            # a fit that moved since last run walks half as far this cycle; the
            # mark has to be on the row before the drafting pass reads it back
            drift_el = drift.compare_runs(elast_rows, prev_el, [], [])
            drift.apply_to_elasticity(elast_rows, drift_el)
            _write_results(db, "elasticity_results", elast_rows, run_id, client["id"])
        if "forecast" in wanted:
            forecast_rows = forecast.run(data, seasonal=seasonal, elasticity_rows=elast_rows)
            _save_output(db, run_id, client["id"], "forecast", {"rows": forecast_rows})
            ok = [f for f in forecast_rows if f["status"] == "ok"]
            gains = [float(f["fva_pct"]) for f in ok if f.get("fva_pct") is not None]
            print(f"  forecast: {len(ok)} of {len(forecast_rows)} items backtested"
                  + (f", mean gain vs naive {sum(gains) / len(gains):+.0f}%" if gains else ""))
        if "inventory" in wanted:
            overrides = {f["item_id"]: forecast.rate_moments(f) for f in (forecast_rows or [])
                         if f["status"] == "ok" and f["level"] == "sku"}
            inventory_rows = inventory_sim.run(data, rng, simulations=simulations, rate_overrides=overrides,
                                               seasonal=seasonal, today=today)
            _write_results(db, "inventory_sim_results", inventory_rows, run_id, client["id"])
            # the joint view: how many SKUs run out in the same lead time once
            # demand shares a common factor, beside the independent figure the
            # per-SKU rows imply
            inventory_panel = inventory_sim.aggregate(inventory_rows, data, rng,
                                                      simulations=simulations)
            _save_output(db, run_id, client["id"], "inventory_panel", inventory_panel)
            if inventory_panel.get("status") == "ok":
                c, i = inventory_panel["correlated"], inventory_panel["independent"]
                print(f"  inventory panel: {c['expected_stockouts']:.1f} SKUs expected out of "
                      f"stock, {c['p95_stockouts']:.0f} at the 95th percentile "
                      f"(independent draws would say {i['p95_stockouts']:.0f})")
        if "crossprice" in wanted:
            cross = cross_price.run(data, elast_rows, seasonal=seasonal)
            _save_output(db, run_id, client["id"], "cross_price", cross)
            print(f"  cross-price: {cross['status']}"
                  + (f" — {cross['n_fitted']} of {cross['n_families']} variant families fitted" if cross["status"] != "no_variant_mapping" else ""))
        if "anomaly" in wanted:
            # before the ad fit: a cost-per-click or conversion break under a
            # campaign is a regime the response curve must not average across
            anomaly_rows = anomaly.run(data)
            _save_output(db, run_id, client["id"], "anomaly", {"rows": anomaly_rows})
            s = summarize_anomalies(anomaly_rows)
            print(f"  anomaly: {s['scanned']} series scanned, {s['flagged']} flagged, "
                  f"${float(s['dollar_impact_total'] or 0):,.0f}/period adverse")
        incr = None
        if "incrementality" in wanted:
            incr = incrementality.run(data, _load_switchbacks(db, client["id"]))
            incr["data_quality_flags"] = data_quality.flags_for(dq, "ppc_spend", "asin_traffic", "sku_economics",
                                                                 "settlement_transactions")
            _save_output(db, run_id, client["id"], "incrementality", incr)
            obs = incr["observational"]
            print("  incrementality: "
                  + (f"observational ι {obs['incrementality']:.2f} ({obs['ci95'][0]:.2f}–{obs['ci95'][1]:.2f}), "
                     f"{obs['reading']}" if obs["status"] == "ok" else f"observational {obs['status']}")
                  + (f"; switchback ι {incr['incrementality_for_breakeven']:.2f} adjusts the break-even"
                     if incr.get("incrementality_for_breakeven") is not None else ""))
        clv_out = None
        if "clv" in wanted:
            clv_out = clv.run(data.get("customer_orders") or [], margin_rows, today, channel=channel,
                              ppc_spend=data.get("ppc_spend"))
            _save_output(db, run_id, client["id"], "clv", clv_out)
            print("  lifetime value: "
                  + (f"{float(clv_out['expected_repeats_52w']):.2f} repeat orders per customer over a year, "
                     f"multiplier {float(clv_out['clv_multiplier']):.2f}× on the allowable acquisition cost "
                     f"(holdout actual/predicted {clv_out['calibration']['actual_over_predicted']})"
                     if clv_out["status"] in ("ok", "poorly_calibrated", "uncalibrated") else clv_out["status"])
                  + (" — moves the ad break-even" if clv_out["status"] == "ok" else ""))
        if "ads" in wanted:
            iota = (incr or {}).get("incrementality_for_breakeven")
            mult = float(clv_out["clv_multiplier"]) if clv_out and clv_out.get("status") == "ok" else None
            pb = (clv_out or {}).get("payback") or {}
            clv_extra = ({"ltv_cac": pb.get("ltv_cac"), "payback_weeks": pb.get("payback_weeks"),
                          "cac": ((clv_out or {}).get("cac") or {}).get("cac")} if pb.get("status") == "ok" else None)
            breaks = ad_breaks = ad_efficiency.regime_breaks(anomaly_rows)
            ads_rows = ad_efficiency.run(data, avg_margin=avg_margin, incrementality=iota,
                                         incrementality_basis="switchback" if iota is not None else None,
                                         clv_multiplier=mult, clv_basis="calibrated" if mult else None,
                                         breaks=breaks, clv_extra=clv_extra)
            if breaks:
                print(f"  ad efficiency: {len(breaks)} campaign(s) refitted after a cost-per-click or conversion break")
        if "elasticity" in wanted or "ads" in wanted:
            drift_out = drift.compare_runs(elast_rows or [], prev_el, ads_rows or [], prev_ads)
            _save_output(db, run_id, client["id"], "drift", drift_out)
            print("  drift: "
                  + (f"{drift_out['n_drifted']} of {drift_out['n_pairs']} fits moved since the last run"
                     if drift_out["status"] == "ok" else drift_out["status"]))
            _write_results(db, "ad_efficiency_results", ads_rows, run_id, client["id"])
        if "recovery" in wanted and not channels.has_recovery(channel):
            print("  recovery: not applicable to Shopify (no reimbursement window)")
        elif "recovery" in wanted:
            rec = recovery.run(data, today=today)
            _save_output(db, run_id, client["id"], "recovery", rec)
            claims = _sync_claims(db, client["id"], run_id, rec, today)
            s = rec["summary"]
            if rec["status"] == "ok":
                print(f"  recovery: {s['n_live']} live claim(s) — ${float(s['live_value'] or 0):,.0f} face, "
                      f"${float(s['live_ev'] or 0):,.0f} expected, {s['n_expiring']} expiring")
            else:
                print("  recovery: no bleed reports on file yet (ledger, returns, reimbursements, transactions)")
        base_inventory = inventory_rows if inventory_rows is not None else inventory_sim.run(data, rng, simulations=simulations)
        base_margins = margin_rows if margin_rows is not None else margin.run(data)
        if "adalloc" in wanted:
            base_ads = ads_rows if ads_rows is not None else ad_efficiency.run(data, avg_margin=avg_margin)
            alloc_margin = avg_margin if avg_margin is not None else margin.average_margin(base_margins)
            # campaigns a trim will move this cycle are held out of the
            # reallocation: one promise per campaign per run
            alloc = ad_allocation.run(base_ads, alloc_margin,
                                      exclude=set(trim_candidates(base_ads, alloc_margin or 0.0)),
                                      risk_share=client.get("risk_budget_share"),
                                      daily=ad_efficiency.campaign_points(data["ppc_spend"], ad_breaks))
            _save_output(db, run_id, client["id"], "ad_allocation", alloc)
            if alloc["status"] == "ok":
                print(f"  ad allocation: ${float(alloc['total_moved_daily']) if alloc.get('total_moved_daily') else 0:,.0f}/day "
                      f"moved across {sum(1 for c in alloc['campaigns'] if c.get('status') == 'ok')} campaigns, "
                      f"+${float(alloc['delta_p50'] or 0):,.0f} expected over {alloc['horizon_days']} days")
            else:
                print(f"  ad allocation: {alloc['status']}" + (f" — {alloc['reason']}" if alloc.get("reason") else ""))
        if "risk" in wanted:
            # before the order sizing: the survival curve prices obsolescence
            risk_out = risk.run(data, base_margins, forecast_rows, base_inventory, ads_rows, rng, min(simulations, 10000))
            _save_output(db, run_id, client["id"], "risk", risk_out)
            v = risk_out.get("var") or {}
            c = (risk_out.get("concentration") or {}).get("sku_revenue") or {}
            print("  risk: "
                  + (f"expected net ${float(v['expected_net']):,.0f}, worst-5% ${float(v['worst_5pct_net']):,.0f}"
                     if v.get("status") == "ok" else "VaR skipped (no unit economics)")
                  + (f"; HHI {float(c['hhi']):,.0f} ({c.get('level')})" if c.get("hhi") is not None else ""))
        if "invecon" in wanted:
            # orders are sized on demand at the prices this sweep will set:
            # the drafter recomputes the same plan from the same inputs
            cross_now = cross if cross is not None else _load_outputs(db, run_id).get("cross_price")
            plan = (plan_prices(elast_rows, base_margins, cross_now, risk_share=client.get("risk_budget_share"))
                    if elast_rows else None)
            inv_econ = inventory_econ.run(data, base_inventory, base_margins, forecast_rows, rng,
                                          simulations, today, channel=channel, seasonal=seasonal, risk_out=risk_out,
                                          price_plan=plan)
            if "markdown" in wanted:
                md = markdown.run(data, inv_econ, elast_rows, base_margins, base_inventory, today, channel,
                                  risk_share=client.get("risk_budget_share"))
                _save_output(db, run_id, client["id"], "markdown", md)
                if md["status"] == "ok":
                    # one liquidation list on the desk: the three-way decision's
                    inv_econ["summary"]["liquidation_candidates"] = md["summary"]["liquidation_candidates"]
                    inv_econ["summary"]["liquidation_value"] = md["summary"]["liquidation_value"]
                    s_ = md["summary"]
                    print(f"  markdown: {s_['n_valued']} SKUs valued three ways — {len(s_['markdown_candidates'])} to mark "
                          f"down, {len(s_['liquidation_candidates'])} to liquidate, {len(s_['stretch_candidates'])} to stretch"
                          + (f" ({s_['n_no_elasticity']} without an elasticity, two-way only)" if s_["n_no_elasticity"] else ""))
                else:
                    print(f"  markdown: {md['status']}")
            inv_econ["data_quality_flags"] = data_quality.flags_for(dq, "sku_economics", "inventory_levels", "inventory_health")
            _save_output(db, run_id, client["id"], "invecon", inv_econ)
            if "replenish" in wanted:
                rep = replenishment.run(inv_econ, data, rng, today, channel)
                _save_output(db, run_id, client["id"], "replenishment", rep)
                rs = rep["summary"]
                print(f"  replenishment: {rs['n_with_terms']} of {rs['n_skus']} SKUs carry supplier terms; "
                      f"{len(rs['price_breaks_taken'])} price break(s) taken, {len(rs['expedite_air'])} to expedite by air, "
                      f"{rs['wire_events_saved']} wire(s) saved across {rs['n_suppliers']} supplier(s)")
            if inv_econ["status"] == "ok":
                b = inv_econ["summary"]["bleed"]
                print(f"  inventory economics: {inv_econ['summary']['n_skus']} SKUs priced, fee bleed "
                      f"${float(b['total_month'] or 0):,.0f}/month, {len(inv_econ['summary']['econ_orders'])} "
                      f"economic order(s), {len(inv_econ['summary']['liquidation_candidates'])} liquidation candidate(s)")
        if "assortment" in wanted:
            cross_out = _load_outputs(db, run_id).get("cross_price")
            asrt = assortment.run(base_margins, inv_econ, data, risk_out, cross_out, today)
            _save_output(db, run_id, client["id"], "assortment", asrt)
            if asrt["status"] == "ok":
                a_ = asrt["summary"]
                print(f"  assortment: {a_['n_skus']} SKUs loaded — {len(a_['cut'])} to cut, {len(a_['merge'])} to merge, "
                      f"${float(a_['avoided_loss_12m_p50'] or 0):,.0f} of twelve-month loss avoidable")
            else:
                print(f"  assortment: {asrt['status']}")
        if "cash" in wanted:
            cash = cashflow.run(client, base_inventory, base_margins, rng, channel=channel,
                                seasonal=seasonal, today=today, keep_paths="stress" in wanted)
            cash_paths = cash.pop("_paths", None) if cash else None
            if cash is None:
                print("  cash horizon: skipped (set inputs with `hubricon cash <client> --balance --opex`)")
            else:
                dbmod.chunked_upsert(
                    db, "cash_horizon_results",
                    [{**cash, "run_id": run_id, "client_id": client["id"]}],
                    on_conflict="run_id",
                )
                # the cone with its ruin ladder, for the drafting pass and the stress scenarios
                cash["details"]["data_quality_flags"] = data_quality.flags_for(dq, "sku_economics", "inventory_levels")
                _save_output(db, run_id, client["id"], "cash", cash)
                print(f"  cash_horizon_results: p(ruin) {float(cash['p_ruin']):.1%}, "
                      f"5th-pct low ${float(cash['min_p5']):,.0f} on day {cash['min_p5_day']}")
        if "stress" in wanted:
            st = stress.run(cash_paths, cash)
            _save_output(db, run_id, client["id"], "stress", st)
            if st["status"] == "ok":
                w = st["scenarios"][1] if len(st["scenarios"]) > 1 else None
                print(f"  stress: base p(ruin) {float(st['base']['p_ruin']):.1%}"
                      + (f"; worst is {w['label']} → {float(w['p_ruin']):.1%}" if w else "")
                      + ("" if st["reproduces_cone"] else " — BASE DOES NOT REPRODUCE THE CONE"))
            else:
                print(f"  stress: {st['status']}")
        if "cashorders" in wanted:
            co = cash_orders.run(inv_econ, cash, today)
            _save_output(db, run_id, client["id"], "cash_orders", co)
            if co["status"] == "constrained":
                print(f"  cash orders: cash funds ${float(co['wire_total']):,.0f} of ${float(co['unconstrained_total']):,.0f}; "
                      f"shadow price {float(co['lambda']):.3f}/$; bridge ${float(co['bridge_capital']):,.0f} funds the rest")
            else:
                print(f"  cash orders: {co['status']}")
        if "health" in wanted:
            data_present = {t: bool(data[t]) for t in DATA_TABLES}
            health = health_score.compute(base_margins, cash, risk_out, base_inventory, inv_econ,
                                          ads_rows, forecast_rows, rec, data_present, channel=channel,
                                          data_quality=dq)
            _save_output(db, run_id, client["id"], "health", health)
            if health["status"] == "ok":
                top = health["top_drivers"][0] if health["top_drivers"] else None
                print(f"  health score: {float(health['score']):.0f}/100 (grade {health['grade']})"
                      + (f" — largest deduction {top['label'].lower()}, ${float(top['dollars_at_stake'] or 0):,.0f}" if top else ""))

        # the value ledger closes the loop on every run: what was delivered vs what was paid
        directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
        if claims is None:
            claims = _fetch_claims(db, client["id"])
        value_out = valuemod.compute(client, directives, claims,
                                     _fetch_invoices(db, client["id"]), today)
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

    platform = client.get("platform")
    wanted_channels = channels.channels_for(platform)
    asked = getattr(args, "channel", None)
    if asked and asked not in wanted_channels:
        sys.exit(f"{client['company_name'] or client['contact_email']} sells on "
                 f"{channels.both_label(platform)} — `--channel {asked}` has no data. "
                 f"Set the platform first: `hubricon platform <client> {asked}` (or 'both').")
    running = (asked,) if asked else wanted_channels

    run_id = None
    for channel in running:
        if len(running) > 1:
            print(f"== {channels.label(channel)}")
        run_id = _run_models(db, client, wanted, args.simulations, args.seed, channel)
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


def _latest_run(db, client_id: str, run_id: str | None, channel: str | None = None,
                required: bool = True) -> dict | None:
    """The newest succeeded run, optionally on one channel only. `required`
    off returns None instead of exiting — a two-platform client may have run
    on one channel and not the other."""
    q = db.table("model_runs").select("id, started_at, params").eq("client_id", client_id)
    if run_id:
        rows = q.eq("id", run_id).execute().data
    else:
        rows = (q.eq("status", "succeeded").order("started_at", desc=True)
                .limit(1 if channel is None else 20).execute().data)
        if channel is not None:
            rows = [r for r in rows if ((r.get("params") or {}).get("channel") or "amazon") == channel][:1]
    if not rows:
        if required:
            sys.exit("No succeeded model run for this client — `hubricon run` first.")
        return None
    return rows[0]


def _run_channel(client: dict, run: dict | None = None) -> str:
    """The channel a run was computed on: recorded in model_runs.params since
    2026-09-04, otherwise the client's own platform — which is Amazon for
    every run that predates the second platform."""
    return (((run or {}).get("params") or {}).get("channel")
            or channels.client_channel(client) or "amazon")


def _draft_for_run(db, client: dict, run_id: str, channel: str | None = None) -> list[dict]:
    """Regenerate this run's draft directives idempotently; issued/answered
    rows are untouched. Returns the inserted rows (possibly empty).

    The channel decides the words, never the arithmetic — a Shopify brand is
    never told to clear Amazon's low-inventory-fee window. Unstated, it is
    read off the run."""
    if channel is None:
        run = db.table("model_runs").select("params").eq("id", run_id).limit(1).execute().data
        channel = _run_channel(client, run[0] if run else None)
    results = {t: db.table(t).select("*").eq("run_id", run_id).execute().data
               for t in ("inventory_sim_results", "ad_efficiency_results", "elasticity_results", "margin_results")}
    search_terms = dbmod.fetch_all(db, "ppc_search_terms", client["id"], filters={"channel": channel})
    ppc_spend = dbmod.fetch_all(db, "ppc_spend", client["id"], filters={"channel": channel})
    outputs = _load_outputs(db, run_id)
    drafts = draft_directives(results["inventory_sim_results"], results["ad_efficiency_results"],
                              results["elasticity_results"], results["margin_results"],
                              search_terms=search_terms, brand_terms=resolve_brand_terms(client),
                              recovery=outputs.get("recovery"), inv_econ=outputs.get("invecon"),
                              anomaly_rows=(outputs.get("anomaly") or {}).get("rows"),
                              channel=channel, ad_allocation=outputs.get("ad_allocation"),
                              incrementality=outputs.get("incrementality"), client_id=client["id"],
                              experiments=_load_price_tests(db, client["id"]),
                              cross_price=outputs.get("cross_price"), markdown=outputs.get("markdown"),
                              replenishment=outputs.get("replenishment"), cash_orders=outputs.get("cash_orders"),
                              assortment=outputs.get("assortment"),
                              risk_share=client.get("risk_budget_share"), cash=outputs.get("cash"),
                              ppc_spend_rows=ppc_spend)

    # file each directive into the active plan's matching initiative
    initiative_by_module = {}
    active = (db.table("plans").select("id").eq("client_id", client["id"])
              .eq("status", "active").limit(1).execute().data)
    if active:
        for i in db.table("initiatives").select("id, module").eq("plan_id", active[0]["id"]).execute().data:
            initiative_by_module[i["module"]] = i["id"]
    # Scoped by CHANNEL, not run_id: every sweep opens a new model_runs row, so
    # the old .eq("run_id", run_id) never matched anything and the same finding
    # was re-drafted every Monday, ready to be issued — and counted — twice.
    db.table("directives").delete().eq("client_id", client["id"]).eq("channel", channel) \
        .eq("status", "draft").execute()
    if not drafts:
        return []

    # A finding already live as issued/approved is not re-drafted: the client
    # has it, and a second row would double-count it on the ledger. The partial
    # unique index enforces this too; filtering here keeps the insert from
    # failing wholesale on one collision.
    live = {r["dedupe_key"] for r in
            db.table("directives").select("dedupe_key").eq("client_id", client["id"])
            .eq("channel", channel).in_("status", ["issued", "approved"]).execute().data
            if r.get("dedupe_key")}
    rows, seen = [], set()
    for d in drafts:
        key = d["dedupe_key"]
        if key in live or key in seen:
            continue
        seen.add(key)
        rows.append({
            "client_id": client["id"],
            "run_id": run_id,
            "channel": channel,
            "module": d["module"],
            "kind": d["kind"],
            "dedupe_key": key,
            # the drafting score is not a column; it rides in evidence so the
            # issue pass can break ties on it
            "evidence": {**(d["evidence"] or {}), "score": round(float(d.get("score") or 0), 4)},
            "mandate": d["mandate"],
            "action_text": d["action_text"],
            "expected_impact_usd": d["expected_impact_usd"],
            "initiative_id": initiative_by_module.get(d["module"]),
        })
    if not rows:
        return []
    return db.table("directives").insert(rows).execute().data


def _refresh_value(db, client: dict, run_id: str) -> dict:
    """Recompute the value ledger and its chart-pack slice after measurements
    change. Without this the desk keeps showing the pre-measurement number
    until the next run."""
    directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
    v = valuemod.compute(client, directives, _fetch_claims(db, client["id"]),
                         _fetch_invoices(db, client["id"]))
    _save_output(db, run_id, client["id"], "value", v)
    packs = (db.table("chart_packs").select("payload").eq("run_id", run_id).limit(1).execute().data)
    if packs:
        payload = {**packs[0]["payload"], "value": chart_pack.value_section(v)}
        dbmod.chunked_upsert(db, "chart_packs",
                             [{"run_id": run_id, "client_id": client["id"], "payload": payload}],
                             on_conflict="run_id")
    return v


def _measure_for_run(db, client: dict, run_id: str, channel: str, apply: bool = True) -> list[dict]:
    """Measure every approved directive against the client's own later exports.

    Runs on the same data the models just read, so a sweep's measurements land
    on the same run's value ledger. Returns the verdicts for the digest."""
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .eq("channel", channel).in_("status", list(measurement.MEASURABLE_STATUSES))
                  .is_("measured_at", "null").execute().data)
    if not directives:
        return []
    data = _load_data(db, client["id"], channel)
    margins = db.table("margin_results").select("*").eq("run_id", run_id).execute().data
    ads_rows = db.table("ad_efficiency_results").select("*").eq("run_id", run_id).execute().data
    claims = _fetch_claims(db, client["id"])

    verdicts = measurement.measure(directives, data, margins, ads_rows, claims,
                                   inv_econ=_load_outputs(db, run_id).get("invecon"),
                                   switchbacks=_load_switchbacks(db, client["id"]),
                                   experiments=_load_experiments(db, run_id))
    if not apply:
        return verdicts
    by_id = {d["id"]: d for d in directives}
    for v in verdicts:
        patch = measurement.to_patch(v, run_id)
        if patch is None:
            continue
        evidence = {**(by_id[v["directive_id"]].get("evidence") or {})}
        if v.get("evidence_after"):
            evidence["after"] = v["evidence_after"]
        patch["evidence"] = evidence
        db.table("directives").update(patch).eq("id", v["directive_id"]).execute()
    return verdicts


def cmd_replay(args):
    """Replay every measured directive and score the promises against outcomes.

    The backtest above the measurement pass: not "did this move work" but "is the
    number we put on these moves calibrated". On a client with no measured history
    yet it reports pending, which is the honest answer and the reason the harness
    exists before the history does."""
    from . import replay as replaymod

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    channel = args.channel or channels.client_channel(client) or "amazon"
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .eq("channel", channel).order("created_at").execute().data)
    if not directives:
        print("No directives on file for this client — nothing to replay.")
        return

    if args.rescore:
        # score what the ledger already banked, without re-measuring
        card = replaymod.score(directives)
    else:
        run = _latest_run(db, client["id"], args.run)
        data = _load_data(db, client["id"], channel)
        margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
        ads_rows = (db.table("ad_efficiency_results").select("*")
                    .eq("run_id", run["id"]).execute().data)
        claims = _fetch_claims(db, client["id"])
        card = replaymod.replay(directives, data, margins, ads_rows, claims,
                               inv_econ=_load_outputs(db, run["id"]).get("invecon"),
                               switchbacks=_load_switchbacks(db, client["id"]),
                               experiments=_load_experiments(db, run["id"]))
    print(replaymod.render(card))


def cmd_directives(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], args.run)
    inserted = _draft_for_run(db, client, run["id"], _run_channel(client, run))
    if not inserted:
        print("No directives drafted — clean run.")
        return

    state = "draft (review, then rerun with --issue)"
    if args.issue:
        # terms.html §6 sells a veto: a directive is only ever "issued" through
        # issue_drafts, which emails the client first and opens the window only
        # for the moves that email reached. Without a mail key nothing can be
        # sent, so nothing is issued: the drafts stay drafts, and saying so out
        # loud beats a portal row nobody was told about.
        if not email_configured():
            print("not notified — window not opened: RESEND_API_KEY is not set, so the drafts stay drafts.")
        else:
            res = issue.issue_drafts(db, client, _run_channel(client, run), PORTAL_URL, send=True)
            if res["issued"] and res["notified"]:
                state = "issued and notified (veto window open)"
            elif res["issued"]:
                state = "issued but NOT notified — no veto window opened, so none of them can auto-approve"
            if res["held"]:
                state += f"; {res['held']} draft(s) held for the next issue"

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


# Only a directive that was actually authorised can bank dollars by hand. An
# 'issued' one has no mandate behind it yet, a 'draft' was never shown to
# anyone, and a 'declined' one was vetoed — measuring any of those puts money
# on the ledger for work the client never agreed to. (measurement.py has its
# own, narrower list for what the sweep measures automatically.)
HAND_MEASURABLE_STATUSES = ("approved", "done", "closed")


def cmd_measure(args):
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)

    if args.auto:
        # What the sweep would bank, on demand — the way this gets developed
        # and audited without waiting for Monday.
        total = 0.0
        for channel in channels.channels_for(client.get("platform")):
            run = _latest_run(db, client["id"], None, channel=channel, required=False)
            if not run:
                print(f"{channels.label(channel)}: no succeeded run yet.")
                continue
            verdicts = _measure_for_run(db, client, run["id"], channel, apply=not args.dry_run)
            print(f"\n{channels.label(channel)} — {len(verdicts)} directive(s) due measurement")
            for v in verdicts:
                usd = v["measured_impact_usd"]
                money = f"${usd:>10,.2f}" if usd is not None else f"{'—':>11}"
                print(f"  {money}  {v['verdict']:<12} {str(v['kind'] or ''):<20} [{v['attribution']}]")
                print(f"              {v['measurement_notes']}")
                if v["verdict"] == "measured":
                    total += float(usd or 0)
            if verdicts and not args.dry_run:
                _refresh_value(db, client, run["id"])
        print(f"\n{'Would bank' if args.dry_run else 'Banked'} ${total:,.2f}.")
        return

    if not args.directive or args.impact is None:
        sys.exit("Pass --directive and --impact to record one by hand, or --auto to measure from the exports.")

    candidates = (db.table("directives").select("id, status, action_text, measured_at, measurement_notes")
                  .eq("client_id", client["id"]).execute().data)
    rows = [r for r in candidates if r["id"].startswith(args.directive.lower())]
    if len(rows) != 1:
        sys.exit(f"Directive prefix {args.directive!r} matched {len(rows)} row(s) — need exactly 1.")
    row = rows[0]
    if row["status"] not in HAND_MEASURABLE_STATUSES and not args.force:
        sys.exit(f"Directive {row['id'][:8]} is {row['status']!r}, not one of {HAND_MEASURABLE_STATUSES}. "
                 f"Approve it first, or pass --force if this really happened out of band.")
    if row.get("measured_at") and not args.remeasure:
        sys.exit(f"Directive {row['id'][:8]} was already measured on {str(row['measured_at'])[:10]}. "
                 f"Pass --remeasure to correct it; the old note is kept.")

    # The override is stamped into the record, not hidden: a number banked
    # outside the normal lifecycle has to be visible in the audit column.
    notes = [n for n in (row.get("measurement_notes"), args.notes) if n]
    if args.force and row["status"] not in HAND_MEASURABLE_STATUSES:
        notes.append(f"Recorded by hand with --force while {row['status']!r}.")
    if row.get("measured_at"):
        notes.append(f"Remeasured on {_now()[:10]}.")

    patch = {
        "measured_impact_usd": args.impact,
        "measured_at": _now(),
        "status": "done",
        "attribution": "direct",   # a founder-recorded number, not an engine measurement
    }
    if notes:
        patch["measurement_notes"] = " ".join(notes)
    db.table("directives").update(patch).eq("id", row["id"]).execute()
    print(f"Recorded ${args.impact:,.0f} on {row['id'][:8]} ({row['action_text'][:60]}…)")


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
    v = valuemod.compute(client, directives, _fetch_claims(db, client["id"]),
                         _fetch_invoices(db, client["id"]))
    print(f"Value ledger — {client['company_name'] or client['contact_email']} (as of {v['as_of']})")
    print(f"  engagement since {v['engagement_start']} · {v['months_elapsed']} month(s) · "
          f"{v['billed_months']} billed at ${float(v['monthly_fee']):,.0f}")
    print(f"  measured on directives  ${float(v['measured']):>10,.0f}  ({v['measured_count']})")
    if v["measured_by_attribution"]:
        tiers = "  ".join(f"{k} ${val:,.0f}" for k, val in sorted(v["measured_by_attribution"].items()))
        print(f"  {'':<24} {tiers}")
    print(f"  recovered from Amazon   ${float(v['recovered']):>10,.0f}  ({v['recovered_count']})")
    if float(v["recovered_unattributed"] or 0):
        # Amazon's own reconciliation. The client's record, not our result.
        print(f"  {'':<24} ${float(v['recovered_unattributed']):,.0f} more reimbursed without a claim from us — "
              f"shown, not banked")
    print(f"  value delivered         ${float(v['value_total']):>10,.0f}")
    print(f"  fees to date            ${float(v['fees_paid']):>10,.0f}  [{v['fees_basis']}]")
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

    if args.action == "plan" and getattr(args, "design", "fixed") == "randomized":
        from .directives import _fee_history
        from .models.price_experiment import design as design_experiment

        if not args.sku or not args.start:
            sys.exit("a randomized plan needs --sku and --start YYYY-MM-DD")
        run = _latest_run(db, client["id"], None)
        margins = [m for m in db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
                   if m.get("sku") == args.sku]
        if not margins:
            sys.exit(f"No margin row for {args.sku} on the latest run — a randomised test needs the unit economics.")
        latest = max(margins, key=lambda m: str(m["period_start"]))
        fit = latest_elasticity(
            db.table("elasticity_results").select("*").eq("run_id", run["id"]).execute().data, args.sku)
        d = design_experiment(client["id"], args.sku, args.start, latest, fit, _fee_history(args.sku, margins))
        if d.get("status") != "ok":
            sys.exit(f"Cannot design the test: {d.get('status')} — {d.get('basis', '')}")
        test = db.table("price_tests").insert({
            "client_id": client["id"], "sku": args.sku, "asin": latest.get("asin"),
            "baseline_price": d["p0"], "test_price": d["p0"], "start_date": d["start_date"],
            "end_date": d["end_date"], "design": d,
        }).execute().data[0]
        print(f"Planned {test['id'][:8]}: randomised test on {args.sku} around ${d['p0']:.2f}, "
              f"{d['n_blocks']} blocks of {d['block_days']} days ({d['allocation']}; seed {d['seed']}):")
        for b in d["blocks"]:
            print(f"  {b['start']}..{b['end']}  ${b['price']:.2f}  ({d['arms'][b['arm']]:+.1%})")
        cost = d.get("expected_test_cost")
        if cost:
            print(f"Expected {cost['p50']:+,.0f} against holding (90% range {cost['p5']:+,.0f} to {cost['p95']:+,.0f}).")
        print("Set each block's price on its first day; `start` when it begins, `analyze` when it ends.")
        return

    if args.action == "analyze":
        from .models import daily
        from .models.price_experiment import analyze

        if not args.test:
            sys.exit("analyze needs --test <id prefix>")
        test = _find_test(db, client["id"], args.test)
        if not test.get("design"):
            sys.exit(f"Test {test['id'][:8]} is a fixed-price test; only a randomised design can be analysed.")
        run = _latest_run(db, client["id"], None)
        data = _load_data(db, client["id"], _run_channel(client, run))
        series = daily.daily_sku_series(data["settlement_transactions"], test["sku"],
                                        test["design"]["start_date"], test["design"]["end_date"])
        fit = latest_elasticity(
            db.table("elasticity_results").select("*").eq("run_id", run["id"]).execute().data, test["sku"])
        if fit and (fit.get("details") or {}).get("source") == "experiment":
            fit = None
        result = analyze({**test["design"], "sku": test["sku"]}, series, fit)
        note = (result["details"].get("bias_sentence") if result["status"] == "ok"
                else f"{result['status']}: {result['details'].get('basis', '')}")
        db.table("price_tests").update({"analysis": result, "outcome_notes": note}).eq("id", test["id"]).execute()
        if result["status"] == "ok":
            print(f"ε = {result['elasticity']:.2f} (95% {result['details']['ci95'][0]:.2f} to "
                  f"{result['details']['ci95'][1]:.2f}; permutation p {result['details']['p_permutation']}).")
            print(note or "")
            print("The next `hubricon run` fits on it, unshrunk.")
        else:
            print(note)
        return

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


def cmd_adtest(args):
    """Plan and analyse an ON/OFF switchback on one campaign — the experiment
    that identifies ad incrementality, which no monthly export can."""
    from datetime import date

    from .models import daily
    from .models.incrementality import analyze_switchback, design_switchback

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    tests = _load_switchbacks(db, client["id"])

    if args.action == "list":
        if not tests:
            print("No ad tests yet — `hubricon adtest <client> plan --campaign ... --start YYYY-MM-DD`")
            return
        for t in tests:
            r = t.get("result") or {}
            print(f"  {t['campaign']:<32} {t['start_date']}..{t['end_date']}  "
                  + (f"ι {r['incrementality']:.2f} ({r['ci90'][0]:.2f}–{r['ci90'][1]:.2f})" if r.get("status") == "ok"
                     else r.get("status", "planned")))
        return

    if not args.campaign:
        sys.exit(f"{args.action} needs --campaign")
    run = _latest_run(db, client["id"], None)
    key = f"ad_switchback:{args.campaign}"

    if args.action == "plan":
        start = args.start or (date.today() + timedelta(days=1)).isoformat()
        schedule = design_switchback(client["id"], args.campaign, start)
        _save_output(db, run["id"], client["id"], key, schedule)
        print(f"Planned {schedule['n_blocks']} blocks of {schedule['block_days']} days on “{args.campaign}” "
              f"from {start} to {schedule['end_date']} (seed {schedule['seed']}):")
        for b in schedule["blocks"]:
            print(f"  {b['start']}..{b['end']}  {b['arm'].upper()}")
        print("Pause the campaign on every OFF block; the daily settlement file is what the analysis reads.")
        return

    if args.action == "analyze":
        test = next((t for t in tests if t.get("campaign") == args.campaign), None)
        if test is None:
            sys.exit(f"No planned test on “{args.campaign}” — plan it first.")
        channel = _run_channel(client, run)
        data = _load_data(db, client["id"], channel)
        totals = daily.daily_totals(data["settlement_transactions"], test["start_date"], test["end_date"])
        result = analyze_switchback(test, totals, data["ppc_spend"])
        _save_output(db, run["id"], client["id"], key, {**test, "result": result})
        if result["status"] == "ok":
            print(f"ι = {result['incrementality']:.2f} (90% range {result['ci90'][0]:.2f}–{result['ci90'][1]:.2f}, "
                  f"permutation p {result['p_permutation']:.3f}) — {result['reading']}. "
                  f"The next `hubricon run` corrects the break-even.")
        else:
            print(f"{result['status']}: {(result.get('details') or {}).get('basis', '')}")
        return
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
    (db.table("plans").update({"status": "superseded"}).eq("client_id", client["id"])
     .in_("status", ["draft", "active"]).execute())
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


def draft_plan_for_run(db, client: dict, run_id: str) -> dict | None:
    """Draft the 90-day plan from the audit, ready for the kickoff call.

    welcome.html promises the plan is "drafted straight from" the Teardown
    within 24 hours and *presented* on the call — so it is written as a draft,
    invisible to the client's desk (which reads status='active'), and the
    founder commits it live. Nothing drafted one automatically before this, so
    a client who booked the kickoff arrived at a plan placeholder."""
    margins = db.table("margin_results").select("*").eq("run_id", run_id).execute().data
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .in_("status", ["draft", "issued", "approved", "done"]).execute().data)
    proposal = propose_plan(margins, directives)
    if proposal is None:
        return None
    existing = (db.table("plans").select("id").eq("client_id", client["id"])
                .in_("status", ["draft", "active"]).limit(1).execute().data)
    if existing:
        return None     # never overwrite a plan someone is already working from
    b, t = proposal["baseline"], proposal["targets"]
    try:
        plan = db.table("plans").insert({
            "client_id": client["id"], "label": proposal["label"], "status": "draft",
            "starts_on": proposal["starts_on"], "ends_on": proposal["ends_on"],
            "baseline_net": b["net"], "baseline_revenue": b["revenue"],
            "baseline_margin_pct": b["margin_pct"],
            "target_net": t["net"], "target_revenue": t["revenue"], "target_margin_pct": t["margin_pct"],
        }).execute().data[0]
    except Exception as err:
        print(f"  plan not drafted: {err}")
        return None
    for sort, i in enumerate(proposal["initiatives"]):
        db.table("initiatives").insert({
            "client_id": client["id"], "plan_id": plan["id"], "title": i["title"],
            "thesis": i["thesis"], "module": i["module"],
            "expected_impact_usd": i["expected_impact_usd"], "sort": sort,
        }).execute()
    print(f"  90-day plan drafted: {proposal['label']}, "
          f"${t['net']:,.0f} net target — commit it on the kickoff call.")
    return plan


def cmd_mandate(args):
    """Record what the client authorised at kickoff.

    welcome.html: "you decide which fixes we make without asking, and exactly
    where your veto sits." Until this existed the mandate was a constant in
    Python, which is not the same as something a client agreed to."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    name = client["company_name"] or client["contact_email"]

    if args.show:
        current = issue.load_mandate(db, client["id"])
        stored = {r["module"] for r in
                  (db.table("mandates").select("module").eq("client_id", client["id"]).execute().data or [])}
        print(f"Standing mandate — {name}")
        for module, m in current.items():
            source = "agreed" if module in stored else "Terms default"
            bound = f" · bound {m['bound']:.0%}" if m.get("bound") is not None else ""
            print(f"  {module:<12} {'without asking' if m['standing'] else 'needs your yes':<16}"
                  f"{bound}  veto {m['veto_hours']}h  [{source}]"
                  + (f"\n  {'':<12} {m['bound_note']}" if m.get("bound_note") else ""))
        return

    row = {"client_id": client["id"], "module": args.module, "standing": args.standing,
           "veto_hours": args.veto_hours, "agreed_note": args.note}
    if args.bound is not None:
        row["bound"] = args.bound
    if args.bound_note:
        row["bound_note"] = args.bound_note
    db.table("mandates").upsert(row, on_conflict="client_id,module").execute()
    print(f"{name}: {args.module} is now "
          + (f"inside the standing mandate (veto window {args.veto_hours}h)"
             if args.standing else "explicit — nothing happens without a yes")
          + (f", bound {args.bound}" if args.bound is not None else "") + ".")


def cmd_execute(args):
    """Record that an approved directive was actually carried out.

    welcome.html promises "Week 1 — first fixes go live in your account", and
    nothing anywhere recorded that they had. The client sees this in their desk
    log, and the sweep escalates anything approved and still not executed."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    rows = [r for r in db.table("directives").select("id, status, action_text, executed_at, kind, evidence")
            .eq("client_id", client["id"]).execute().data
            if r["id"].startswith(args.directive.lower())]
    if len(rows) != 1:
        sys.exit(f"Directive prefix {args.directive!r} matched {len(rows)} row(s) — need exactly 1.")
    row = rows[0]
    if row["status"] != "approved":
        sys.exit(f"Directive {row['id'][:8]} is {row['status']!r}. Only an approved directive is "
                 f"ours to execute — that is what the mandate means.")
    db.table("directives").update({
        "executed_at": _now(),
        "executed_by": args.by or os.environ.get("EXECUTION_EMAIL", "hagen.simmons@hubricon.com"),
        "execution_ref": args.ref,
    }).eq("id", row["id"]).execute()
    print(f"Executed {row['id'][:8]} ({row['action_text'][:60]}…)"
          + (f" — ref {args.ref}" if args.ref else ""))
    if row.get("kind") == "price_experiment":
        # the schedule becomes a running price test, so the daily Buy Box watch
        # and the analysis pass both see it
        ev = row.get("evidence") or {}
        design = ev.get("design") or {}
        db.table("price_tests").insert({
            "client_id": client["id"], "sku": ev.get("sku"), "baseline_price": ev.get("p0"),
            "test_price": ev.get("p0"), "start_date": design.get("start_date"), "end_date": design.get("end_date"),
            "status": "running", "design": design, "directive_id": row["id"],
        }).execute()
        print(f"Randomised test on {ev.get('sku')} is running {design.get('start_date')}..{design.get('end_date')}; "
              f"set each block's price on its first day.")


def cmd_watch(args):
    """The daily reading on any live price test.

    index.html, welcome.html and terms.html §6 all promise Buy Box share (or
    Shopify conversion) is watched DAILY through a price step. The only reading
    that ever existed was one hand-typed number read once a week, so this makes
    the promise true through an enforced daily touch — and says loudly when a
    day was missed."""
    db = dbmod.connect()
    today = date.today()
    clients = ([dbmod.resolve_client(db, args.client)] if args.client
               else db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data)
    missed, watched = [], 0
    for client in clients:
        name = client["company_name"] or client["contact_email"]
        live = (db.table("price_tests").select("*").eq("client_id", client["id"])
                .eq("status", "running").execute().data)
        for t in live:
            if args.buybox is not None or args.conversion is not None:
                db.table("price_test_watch").upsert({
                    "client_id": client["id"], "price_test_id": t["id"],
                    "observed_on": today.isoformat(), "buy_box_share": args.buybox,
                    "conversion_rate": args.conversion, "note": args.note,
                }, on_conflict="price_test_id,observed_on").execute()
                watched += 1
                print(f"{name} · {t['sku']}: recorded for {today}.")
                continue
            seen = (db.table("price_test_watch").select("observed_on")
                    .eq("price_test_id", t["id"]).eq("observed_on", today.isoformat())
                    .limit(1).execute().data)
            if seen:
                watched += 1
            else:
                missed.append(f"{name} · {t['sku']} (${t['baseline_price']} → ${t['test_price']})")

    if missed:
        print(f"{len(missed)} live price test(s) have no reading for {today}:")
        for m in missed:
            print(f"  - {m}")
        print("\nRecord them: hubricon watch <client> --buybox <pct>")
        if args.alert and (founder := os.environ.get("FOUNDER_EMAIL")) and email_configured():
            send_email(founder, f"Buy Box reading missing on {len(missed)} live test(s)",
                       "The site promises Buy Box share is watched daily through a price step.\n\n"
                       + "\n".join(f"  - {m}" for m in missed)
                       + "\n\nRecord them with: hubricon watch <client> --buybox <pct>\n")
    else:
        print(f"{watched} live price test(s), all read for {today}." if watched
              else "No live price tests.")


# Every table a client's export contains. Ordered so the zip reads like the
# service does: what you sent us, what we computed, what we decided, what it
# earned.
EXPORT_TABLES = (
    "uploads", "sku_economics", "asin_traffic", "ppc_search_terms", "ppc_spend",
    "inventory_levels", "settlement_transactions", "cogs_inputs",
    "fba_reimbursements", "fba_returns", "inventory_ledger", "inventory_health",
    "margin_results", "elasticity_results", "inventory_sim_results", "ad_efficiency_results",
    "cash_horizon_results", "recovery_claims", "model_runs", "model_outputs", "chart_packs",
    "directives", "price_tests", "alerts", "briefings", "plans", "initiatives",
    "invoices", "mandates", "consents",
)


def cmd_export(args):
    """Everything we hold on a client, as one zip.

    "Your data and your ledger export free, any time" appears eleven times
    across six surfaces — including Terms §11, Privacy §6 and the portal footer
    — and until now there was no export command, endpoint or button anywhere.
    Raw uploads included: the promise says "raw files, tables, results, this
    ledger", not a summary."""
    import csv
    import io
    import zipfile
    from pathlib import Path

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    name = client["company_name"] or client["contact_email"]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "client"
    out = Path(args.out or f"{slug}-hubricon-export-{date.today().isoformat()}.zip")

    def rows_to_csv(rows: list[dict]) -> str:
        if not rows:
            return ""
        cols = sorted({k for r in rows for k in r})
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: (json.dumps(r[c]) if isinstance(r.get(c), (dict, list)) else r.get(c))
                        for c in cols})
        return buf.getvalue()

    manifest = [f"Hubricon export — {name}", f"Generated {datetime.now(timezone.utc).isoformat()}", ""]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for table in EXPORT_TABLES:
            try:
                rows = dbmod.fetch_all(db, table, client["id"])
            except Exception as err:
                manifest.append(f"  {table}: unavailable ({str(err)[:80]})")
                continue
            if not rows:
                manifest.append(f"  {table}: empty")
                continue
            z.writestr(f"tables/{table}.csv", rows_to_csv(rows))
            manifest.append(f"  tables/{table}.csv — {len(rows)} row(s)")

        # The ledger, as its own file, because it is the thing most often asked for.
        directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
        ledger = valuemod.compute(client, directives, _fetch_claims(db, client["id"]),
                                  _fetch_invoices(db, client["id"]))
        z.writestr("ledger.json", json.dumps(ledger, indent=2, default=str))
        manifest.append(f"  ledger.json — ${float(ledger['value_total']):,.0f} measured against "
                        f"${float(ledger['fees_paid']):,.0f} in fees [{ledger['fees_basis']}]")

        if not args.no_files:
            uploads = db.table("uploads").select("*").eq("client_id", client["id"]).execute().data
            for u in uploads:
                if not u.get("storage_path") or u["storage_path"] == "pending":
                    continue
                try:
                    blob = storage.download(db, u["storage_path"])
                except Exception as err:
                    manifest.append(f"  raw/{u.get('original_filename')}: unavailable ({str(err)[:60]})")
                    continue
                z.writestr(f"raw/{u['id'][:8]}-{u.get('original_filename') or 'upload.csv'}", blob)
            manifest.append(f"  raw/ — {len(uploads)} uploaded file(s) exactly as you sent them")

        for path_field, label in (("report_path", "reports"), ("video_path", "videos")):
            for b in db.table("briefings").select("*").eq("client_id", client["id"]).execute().data:
                target = b.get(path_field)
                if not target:
                    continue
                try:
                    z.writestr(f"{label}/{target.rsplit('/', 1)[-1]}", storage.download(db, target))
                except Exception:
                    pass

        z.writestr("MANIFEST.txt", "\n".join(manifest) + "\n")
    print("\n".join(manifest))
    print(f"\nWrote {out} ({out.stat().st_size / 1_000_000:.1f} MB). It is theirs, free, any time.")


def cmd_request(args):
    """Track a deletion, access or correction request against its promised clock.

    privacy.html makes four dated commitments — deletion within 30 days, breach
    notice within 72 hours, a DSAR answer within 7 days, and 14 days' notice of
    a terms change — with no code behind any of them. A promise with a deadline
    and no timer is a promise kept by luck."""
    db = dbmod.connect()
    if args.action == "open":
        client = dbmod.resolve_client(db, args.client) if args.client else None
        row = db.table("data_requests").insert({
            "client_id": client["id"] if client else None,
            "requester_email": args.email or (client or {}).get("contact_email"),
            "kind": args.kind, "note": args.note,
            "due_at": (datetime.now(timezone.utc)
                       + timedelta(days=DATA_REQUEST_DAYS[args.kind])).isoformat(),
        }).execute().data[0]
        print(f"{args.kind} request {row['id'][:8]} opened — due {str(row['due_at'])[:10]} "
              f"({DATA_REQUEST_DAYS[args.kind]} days, per the privacy policy).")
        return

    if args.action == "close":
        rows = [r for r in db.table("data_requests").select("*").is_("closed_at", "null").execute().data
                if r["id"].startswith(args.id.lower())]
        if len(rows) != 1:
            sys.exit(f"Prefix {args.id!r} matched {len(rows)} open request(s) — need exactly 1.")
        db.table("data_requests").update({"closed_at": _now(), "outcome": args.outcome}).eq(
            "id", rows[0]["id"]).execute()
        print(f"Closed {rows[0]['id'][:8]}.")
        return

    open_rows = db.table("data_requests").select("*").is_("closed_at", "null").order("due_at").execute().data
    if not open_rows:
        print("No open data requests.")
        return
    now = datetime.now(timezone.utc)
    for r in open_rows:
        due = datetime.fromisoformat(str(r["due_at"]))
        left = (due - now).days
        flag = "OVERDUE" if left < 0 else f"{left}d left"
        print(f"  {r['id'][:8]}  {r['kind']:<12} {r.get('requester_email') or '—':<32} {flag}")


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
                      ledger_measured, len(directives), issue_number=issue_count + 1,
                      channel=_run_channel(client, run))

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
        inv_econ=outputs.get("invecon"), data_quality=outputs.get("data_quality"),
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


# privacy.html's four dated commitments, in one place so a policy edit is a
# constant change rather than a hunt.
DATA_REQUEST_DAYS = {
    "deletion": 30,       # privacy.html §6: "deletion on request, within thirty days"
    # §7: "it lands with the founder, and you get an answer within seven days".
    # A data-subject request opened by hand answers in seven. The client's own
    # "Request your export" button in Hubricon writes the same kind with a
    # tighter clock — one working day, terms §11 — because that export is the
    # hedge the site sells against a one-person shop. Each row carries its own
    # due date, and the promise audit reads the row, so the two never collide.
    "access": 7,
    "correction": 7,
    "breach_notice": 3,   # §5: "within seventy-two hours of confirming it"
    "terms_notice": 14,   # terms.html §14: "clients get fourteen days' notice by email"
}

ISSUE_INTERVAL_DAYS = 14      # welcome.html: "a short video after, every two weeks"


def _next_issue_number(db, client_id: str) -> int:
    """Atomic where the RPC exists; count-then-add-one only as a fallback, so a
    database that has not taken the migration still publishes."""
    try:
        return int(db.rpc("next_issue_number", {"p_client_id": client_id}).execute().data)
    except Exception:
        return (db.table("briefings").select("id", count="exact", head=True)
                .eq("client_id", client_id).execute().count or 0) + 1


def _issue_due(db, client: dict, today: date) -> tuple[bool, str]:
    """Is this client's next issue due?

    The cadence is anchored to THEIR retainer start, not a global fortnightly
    cron, so "every two weeks" means fourteen days from their own day one."""
    last = (db.table("briefings").select("created_at, issue_number")
            .eq("client_id", client["id"]).order("created_at", desc=True).limit(1).execute().data)
    if not last:
        return False, "no first issue yet — the teardown publishes that"
    since = (today - date.fromisoformat(str(last[0]["created_at"])[:10])).days
    if since < ISSUE_INTERVAL_DAYS:
        return False, f"issue No. {last[0]['issue_number']:03d} was {since}d ago"
    return True, f"{since}d since issue No. {last[0]['issue_number']:03d}"


def _publish_issue(db, client: dict, channel: str, send: bool, today: date) -> dict | None:
    """Publish the next issue from the latest run: letter, report, video, email.

    The models are not re-run — Monday's sweep already did that — so this reads
    the newest succeeded run and re-cuts it as an issue."""
    from pathlib import Path
    from . import video as videomod
    from .briefing import build_beats, build_memo, period_deltas
    from .report.html_report import generate

    run = _latest_run(db, client["id"], None, channel=channel, required=False)
    if not run:
        return None
    issue_no = _next_issue_number(db, client["id"])
    company = client["company_name"] or client["contact_email"]
    first = (client.get("contact_name") or "").split(" ")[0]

    margins = db.table("margin_results").select("*").eq("run_id", run["id"]).execute().data
    elasticity = db.table("elasticity_results").select("*").eq("run_id", run["id"]).execute().data
    directives = (db.table("directives").select("*").eq("client_id", client["id"])
                  .eq("channel", channel).order("created_at", desc=True).limit(40).execute().data)
    alerts = (db.table("alerts").select("*").eq("client_id", client["id"])
              .order("created_at", desc=True).limit(10).execute().data)
    ledger = valuemod.compute(client, directives, _fetch_claims(db, client["id"]),
                              _fetch_invoices(db, client["id"]))
    deltas = period_deltas(margins)

    memo = build_memo(company, first, deltas, directives, alerts, elasticity,
                      float(ledger["measured"] or 0), int(ledger["measured_count"] or 0),
                      issue_number=issue_no, channel=channel,
                      ledger_found=float(ledger["identified_unbanked"] or 0),
                      fees_billed=float(ledger["fees_billed"] or 0))
    if narrate.available():
        try:
            outputs = _load_outputs(db, run["id"])
            facts = narrate.build_facts(
                company, first, deltas, directives, alerts,
                float(ledger["measured"] or 0), int(ledger["measured_count"] or 0),
                issue_number=issue_no, health=outputs.get("health"), value=outputs.get("value"),
                recovery=outputs.get("recovery"),
                forecast_rows=(outputs.get("forecast") or {}).get("rows"),
                risk=outputs.get("risk"),
                anomaly_summary=summarize_anomalies((outputs.get("anomaly") or {}).get("rows") or []),
                inv_econ=outputs.get("invecon"), data_quality=outputs.get("data_quality"))
            result = narrate.narrate(facts)
            if result.get("text"):
                memo = result["text"]
        except Exception as err:
            print(f"  narration skipped: {err}")

    report_path = None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            local = generate(db, client, run["id"], out_dir=tmp)
            report_path = f"reports/{client['id']}/issue-{issue_no:03d}.html"
            db.storage.from_(storage.BUCKET).upload(
                report_path, Path(local).read_bytes(),
                {"content-type": "text/html", "upsert": "true"})
        except Exception as err:
            print(f"  report skipped: {err}")
            report_path = None

        # The video never blocks the letter: terms.html §2 owes them a written
        # report inside 24 hours, and a TTS outage must not hold that hostage.
        video_path = None
        beats = build_beats(company, first, deltas, directives, alerts, elasticity,
                            float(ledger["measured"] or 0), int(ledger["measured_count"] or 0),
                            ledger_found=float(ledger["identified_unbanked"] or 0),
                            fees_billed=float(ledger["fees_billed"] or 0))
        made = videomod.render(company, issue_no, beats, Path(tmp) / f"issue-{issue_no:03d}.mp4")
        if made:
            video_path = f"reports/{client['id']}/issue-{issue_no:03d}.mp4"
            db.storage.from_(storage.BUCKET).upload(
                video_path, made.read_bytes(),
                {"content-type": "video/mp4", "upsert": "true"})

    headline = f"Profit Brief No. {issue_no:03d}"
    if deltas and deltas.get("net_delta") is not None:
        headline += f" — net profit {'up' if deltas['net_delta'] >= 0 else 'down'} ${abs(deltas['net_delta']):,.0f}"
    row = {"client_id": client["id"], "run_id": run["id"], "memo": memo, "issue_number": issue_no,
           "report_path": report_path, "video_path": video_path, "title": "Profit Brief",
           "headline": headline, "tldr": (memo.split("\n\n")[2][:280] if memo.count("\n\n") > 2 else None)}
    try:
        inserted = db.table("briefings").insert(row).execute().data[0]
    except Exception as err:
        print(f"  Profit Brief No. {issue_no:03d} not published: {err}")
        return None

    # The price of the free month is asked for here — on the first Issue after
    # the ledger has earned the asking, once, as one more paragraph in a
    # letter the client already opens (referral.py).
    try:
        ask = referral.ask_if_due(db, client, ledger, _fetch_claims(db, client["id"]), send)
    except Exception as err:
        print(f"  consent ask skipped: {err}")
        ask = []
    proven = float(ledger["value_total"] or 0)
    found = float(ledger["identified_unbanked"] or 0)
    sent = _send_client_email(db, client, "issue_ready", inserted["id"],
                              _issue_subject(issue_no, headline, proven, found),
                              _issue_email_blocks(issue_no, proven, found, bool(video_path)) + ask, send)
    if sent and ask:
        referral.mark_asked(db, client)
        print("  the consent and referral ask rode this issue")
    parts = [p for p, on in (("letter", memo), ("report", report_path), ("video", video_path)) if on]
    print(f"  Profit Brief No. {issue_no:03d} published ({' + '.join(parts)})"
          + (" and emailed" if sent else ""))
    if not video_path:
        # The site promises a three-minute video with every brief. Shipping the
        # letter alone is the right fallback, but it is still a promise
        # outstanding and has to be said out loud rather than absorbed.
        print(f"  NOT KEPT: Profit Brief No. {issue_no:03d} went out without the video the site promises. "
              f"Record one: hubricon brief {client['contact_email']} --video <loom url>")
    return {"issue_number": issue_no, "video": bool(video_path), "emailed": sent}


def _issue_subject(issue_no: int, headline: str, proven: float, found: float) -> str:
    """The subject line is the Record, not the period's net profit: what has
    been proven and what has been found since day one. The briefings row keeps
    `headline` (net profit up/down) for the portal; the inbox gets the number
    the invoice is judged on. Before the Record has anything on it, the subject
    falls back to the headline's tail, or to plain 'is in Hubricon'."""
    if proven + found > 0:
        return f"Profit Brief No. {issue_no:03d} — ${proven:,.0f} proven, ${found:,.0f} found on your Record"
    tail = headline.split("—")[-1].strip() if "—" in headline else ""
    return (f"Profit Brief No. {issue_no:03d} — {tail}" if tail
            else f"Profit Brief No. {issue_no:03d} is in Hubricon")


def _issue_email_blocks(issue_no: int, proven: float, found: float, has_video: bool) -> list[dict]:
    return [
        {"p": f"Your Profit Brief is ready — ${proven:,.0f} proven on your Record since day one, "
              f"${found:,.0f} found and filed."},
        {"p": ("It's a short video, with the written letter and the full report "
               "underneath it." if has_video else
               "The written letter and the full report are both in Hubricon.")},
        {"button": "Open Hubricon", "url": PORTAL_URL},
        {"p": "Anything waiting for your yes is right below the brief, under 'Before it goes live'. "
              "Reply to this email if you'd rather just tell me."},
    ]


# Letters whose body already IS the three Profit Record numbers.
RECORD_FOOTER_EXEMPT = frozenset({"guarantee_cleared", "guarantee_short", "month_waived"})


def _send_client_email(db, client: dict, kind: str, ref_id: str, subject: str,
                       blocks: list[dict], send: bool) -> bool:
    """Send a recurring client email exactly once.

    client_touches keys on (client_id, kind) and so can only fire a kind once
    per client for all time; recurring mail is logged in client_emails against
    the thing it is about."""
    if not send or not email_configured() or not client.get("contact_email"):
        return False
    try:
        already = (db.table("client_emails").select("id").eq("client_id", client["id"])
                   .eq("kind", kind).eq("ref_id", str(ref_id)).limit(1).execute().data)
        if already:
            return False
    except Exception:
        pass    # log table missing (migration not applied): better to send than to go silent
    from .notify import letter
    if kind not in RECORD_FOOTER_EXEMPT:
        # Every client email closes on the Profit Record — the same three
        # numbers as the strip in Hubricon. The billing letters already carry
        # them as their subject; the footer never blocks a send.
        try:
            directives = db.table("directives").select("*").eq("client_id", client["id"]).execute().data
            ledger = valuemod.compute(client, directives, _fetch_claims(db, client["id"]),
                                      _fetch_invoices(db, client["id"]))
            blocks = list(blocks) + [{"p": valuemod.record_line(ledger)}]
        except Exception as err:
            print(f"  Profit Record footer skipped ({err})")
    text, html = letter(client.get("contact_name"), blocks)
    ok = send_email(client["contact_email"], subject, text, html=html,
                    sender=os.environ.get("EMAIL_FROM", "Hagen Simmons <hagen.simmons@hubricon.com>"),
                    reply_to=os.environ.get("EMAIL_REPLY_TO",
                                            os.environ.get("EMAIL_FROM", "hagen.simmons@hubricon.com")))
    if ok:
        try:
            db.table("client_emails").insert({
                "client_id": client["id"], "kind": kind, "ref_id": str(ref_id), "subject": subject,
            }).execute()
        except Exception as err:
            print(f"  email log write failed ({err}) — the mail went out")
    return ok


def cmd_issue(args):
    """Publish the issue for every client whose fortnight is up.

    Runs daily; each client's clock is their own, so nobody waits for a global
    cadence to come round."""
    db = dbmod.connect()
    today = date.today()
    clients = ([dbmod.resolve_client(db, args.client)] if args.client
               else db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data)
    published = 0
    for client in clients:
        name = client["company_name"] or client["contact_email"]
        if onboarding.is_internal(client["contact_email"], client.get("contact_name")) and not args.client:
            continue
        due, why = _issue_due(db, client, today)
        if not due and not args.force:
            print(f"{name}: not due — {why}")
            continue
        print(f"{name}: {why}")
        if args.dry_run:
            print("  [dry] would publish the next issue")
            continue
        for channel in channels.channels_for(client.get("platform")):
            if _publish_issue(db, client, channel, send=args.send, today=today):
                published += 1
    print(f"\n{published} issue(s) published.")


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

    issue = _next_issue_number(db, client["id"])

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
    print(f"Profit Brief No. {issue:03d} ({' + '.join(parts)}) published to the portal for "
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
    if getattr(args, "buffer", None) is not None:
        patch["min_cash_buffer_usd"] = args.buffer
    if getattr(args, "risk_share", None) is not None:
        if not 0.05 <= args.risk_share <= 0.30:
            sys.exit("--risk-share must sit between 0.05 and 0.30: the share of a month's net one move may put at risk.")
        patch["risk_budget_share"] = args.risk_share
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
    floor = float(client.get("min_cash_buffer_usd") or 0)
    print(f"  p(dip below ${floor:,.0f} in {cash['horizon_days']}d): {float(cash['p_ruin']):.1%}"
          + (" (buffer client-stated)" if floor else "")
          + f"; risk budget {float(client.get('risk_budget_share') or 0.15):.0%} of monthly net per move")
    print(f"  5th-percentile low: ${float(cash['min_p5']):,.0f} around "
          f"{(today + timedelta(days=cash['min_p5_day'])).strftime('%b %d')}")
    for w in cash["details"]["wires"][:6]:
        print(f"  wire {(today + timedelta(days=w['day'])).strftime('%b %d')}: "
              f"${w['amount']:,.0f} — {w['sku']}")


def cmd_benchmark(args):
    """Where the client sits against the consenting book, as percentiles."""
    from .models import benchmark

    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    out = benchmark.run(db, client["id"])
    if out["status"] != "ok":
        print(f"{out['status']}: {out['basis']}")
        return
    print(f"{client['company_name'] or client['contact_email']} against {out['n_clients']} consenting clients:")
    for ratio, r in out["ratios"].items():
        if r.get("status") != "ok":
            print(f"  {ratio:<18} {r['status']}")
            continue
        print(f"  {ratio:<18} {float(r['value']):8.3f}  percentile {float(r['percentile']):5.0%} "
              f"({float(r['percentile_p5']):.0%}–{float(r['percentile_p95']):.0%}), book median {float(r['book_median']):.3f} — {r['reading']}")


def cmd_stress(args):
    """The 'what would break you' table from the latest run."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    run = _latest_run(db, client["id"], None)
    st = _load_outputs(db, run["id"]).get("stress")
    if not st or st.get("status") != "ok":
        sys.exit("No stress table on the latest run — `hubricon run` with cash inputs on file first.")
    print(f"What would break {client['company_name'] or client['contact_email']} — 90 days, {st['basis']}")
    for r in st["scenarios"]:
        print(f"  {r['label']:<48} p(ruin) {float(r['p_ruin']):6.1%}  trough p5 ${float(r['trough_p5'] or 0):>10,.0f}"
              f"  Δp(ruin) {float(r['p_ruin_delta']):+.1%}")


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


def _sweep_channel(db, client: dict, channel: str, label: str, send_alerts: bool,
                   issue_drafts: bool = False) -> dict:
    """One channel's run -> draft -> alert pass. Returns the digest facts the
    client-level summary adds up."""
    out = {"ran": False, "drafts": 0, "alerts": 0, "emailed": False, "issued": 0,
           "auto_approved": 0, "lapsed": 0, "measured": 0, "measured_usd": 0.0}

    def has_rows(table: str) -> bool:
        return bool(db.table(table).select("id").eq("client_id", client["id"])
                    .eq("channel", channel).limit(1).execute().data)

    if not (has_rows("sku_economics") or has_rows("asin_traffic")):
        return out  # nothing on this channel yet — no empty run to explain

    # the previous run ON THIS CHANNEL, for crossed/worsened comparison —
    # a Shopify stockout must not be measured against Amazon's last picture
    recent_runs = (db.table("model_runs").select("id, params").eq("client_id", client["id"])
                   .eq("status", "succeeded").order("started_at", desc=True).limit(10).execute().data)
    prev_runs = [r for r in recent_runs if _run_channel(client, r) == channel]
    prev_inventory = (
        db.table("inventory_sim_results").select("*").eq("run_id", prev_runs[0]["id"]).execute().data
        if prev_runs else []
    )
    prev_health = _load_outputs(db, prev_runs[0]["id"] if prev_runs else None).get("health")

    # Close any veto window that expired since last week BEFORE drafting, so a
    # directive is never deleted and re-drafted out from under a client who was
    # about to answer it.
    closed = issue.close_veto_windows(db, client, channel)
    out["auto_approved"] = closed["auto_approved"]
    out["lapsed"] = closed["lapsed"]

    run_id = _run_models(db, client, set(ALL_MODELS), 20000, 42, channel)
    out["ran"] = True
    out["drafts"] = len(_draft_for_run(db, client, run_id, channel))

    # welcome.html promises the first fixes go live in week one. Nothing
    # tracked whether they did, so a slip only surfaced when a client noticed.
    late = issue.overdue_executions(db, client, channel)
    out["overdue"] = [f"{d['action_text'][:70]} ({d['days']}d since approval)" for d in late]

    if issue_drafts:
        # terms.html §6: stated with its expected dollars BEFORE it goes live.
        res = issue.issue_drafts(db, client, channel, PORTAL_URL, send=send_alerts)
        out["issued"] = res["issued"]
        out["issue_notified"] = res["notified"]
        out["held_back"] = res["held"]
        if res["issued"] and not res["notified"]:
            print(f"  {res['issued']} directive(s) issued but NOT notified — no veto window opened, "
                  f"so none of them can auto-approve.")

    # Measure what was approved before, from the exports that just landed, then
    # recompute the ledger so this sweep's own findings are in it.
    verdicts = _measure_for_run(db, client, run_id, channel)
    out["measured"] = sum(1 for v in verdicts if v["verdict"] == "measured")
    out["measured_usd"] = round(sum(float(v["measured_impact_usd"] or 0)
                                    for v in verdicts if v["verdict"] == "measured"), 2)
    for v in verdicts:
        if v["verdict"] != "not_yet":
            print(f"  {v['verdict']:<12} {str(v['kind'] or ''):<20} {v['measurement_notes'][:90]}")
    if out["measured"]:
        _refresh_value(db, client, run_id)

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
                                  health=outputs.get("health"), previous_health=prev_health,
                                  channel=channel), recent)
    out["alerts"] = len(fresh)
    if not fresh:
        return out

    emailed = False
    if send_alerts and email_configured() and client.get("contact_email"):
        try:
            ledger = valuemod.compute(client, db.table("directives").select("*").eq("client_id", client["id"]).execute().data,
                                      _fetch_claims(db, client["id"]), _fetch_invoices(db, client["id"]))
            record = valuemod.record_line(ledger)
        except Exception as err:
            print(f"  Profit Record footer skipped ({err})")
            record = None
        text, html = alert_email_body(label, fresh, client.get("contact_name"), PORTAL_URL,
                                      record_line=record)
        urgent = sum(1 for a in fresh if a.get("severity") == "critical")
        subject = (f"{urgent} urgent item on {label}" if urgent == 1 else
                   f"{urgent} urgent items on {label}" if urgent else
                   f"This week's watch on {label}")
        emailed = send_email(
            client["contact_email"], subject, text, html=html,
            sender=os.environ.get("EMAIL_FROM", "Hagen Simmons <hagen.simmons@hubricon.com>"),
            # welcome.html: "reply to any Hubricon email and it lands with the
            # person who builds your models". It did not, for the only email a
            # client got regularly.
            reply_to=os.environ.get("EMAIL_REPLY_TO",
                                    os.environ.get("EMAIL_FROM", "hagen.simmons@hubricon.com")),
        )
    out["emailed"] = emailed
    db.table("alerts").insert([
        {**a, "client_id": client["id"], "run_id": run_id,
         "emailed_at": _now() if emailed else None}
        for a in fresh
    ]).execute()
    for a in fresh:
        print(f"  ALERT [{a['severity']}] {a['message'][:90]}")
    return out


def _sweep_client(db, client: dict, send_alerts: bool, issue_drafts: bool = False) -> dict:
    """Ingest -> run -> draft -> alert for one client. Returns digest facts.

    Uploads are parsed once — a file belongs to a client, and its parser
    already stamps the channel — then the run step repeats per channel the
    client sells on, so a brand on both platforms gets two honest reads
    instead of one blended average."""
    summary = {"client": client["company_name"] or client["contact_email"],
               "parsed": 0, "failed": 0, "ran": False, "drafts": 0, "alerts": 0, "emailed": False,
               "issued": 0, "auto_approved": 0, "lapsed": 0, "measured": 0, "measured_usd": 0.0}
    summary["parsed"], summary["failed"] = _ingest_client(db, client)

    running = channels.channels_for(client.get("platform"))
    for channel in running:
        if len(running) > 1:
            print(f"  -- {channels.label(channel)}")
        got = _sweep_channel(db, client, channel, summary["client"], send_alerts, issue_drafts)
        summary["ran"] = summary["ran"] or got["ran"]
        summary["emailed"] = summary["emailed"] or got["emailed"]
        for k in ("drafts", "alerts", "issued", "auto_approved", "lapsed", "measured", "measured_usd"):
            summary[k] += got.get(k, 0)
        summary.setdefault("overdue", []).extend(got.get("overdue", []))
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
            digests.append(_sweep_client(db, client, send_alerts=args.alert,
                                         issue_drafts=args.issue))
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
            if d.get("issued") or d.get("auto_approved") or d.get("lapsed"):
                lines.append(f"      decisions: {d['issued']} issued"
                             + (f", {d['auto_approved']} auto-approved on a closed veto window"
                                if d["auto_approved"] else "")
                             + (f", {d['lapsed']} lapsed unanswered" if d["lapsed"] else ""))
            if d.get("measured"):
                lines.append(f"      ledger: {d['measured']} directive(s) measured, "
                             f"${d['measured_usd']:,.0f} banked from your clients' own exports")
            for late in d.get("overdue", []):
                lines.append(f"      OVERDUE — approved and not yet executed: {late}")
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


def cmd_platform(args):
    """Which store(s) a client runs. Everything downstream reads this: which
    exports the intake admits, which channel a run reads, and whether the
    client is ever told about Amazon fees."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    patch = {"platform": args.platform}
    if args.shopify_domain:
        patch["shopify_domain"] = args.shopify_domain.strip().lower()
    db.table("clients").update(patch).eq("id", client["id"]).execute()
    name = client["company_name"] or client["contact_email"]
    print(f"{name} sells on {channels.both_label(args.platform)}.")
    if patch.get("shopify_domain"):
        print(f"  storefront: {patch['shopify_domain']}")
    print(f"  next run reads: {', '.join(channels.label(c) for c in channels.channels_for(args.platform))}")


def cmd_retainer(args):
    """When the retainer actually started.

    terms.html §3: "the retainer starts on the day you say yes after the
    Teardown." Nothing recorded that date, so the free-month clock ran from
    provisioning — from the booking, before the Teardown existed. This is the
    best evidence there is, and it outranks the date the Stripe webhook infers
    from a first invoice."""
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    name = client["company_name"] or client["contact_email"]

    if args.show:
        v = valuemod.engagement_start(client, date.today())
        print(f"{name}: retainer clock runs from {v[0].isoformat()} ({v[1]})")
        if not client.get("retainer_started_at"):
            print("  no agreed start date on file — the ledger reports its fee basis as unknown "
                  "and treats them as in their free month.")
        return

    started = date.fromisoformat(args.started) if args.started else date.today()
    db.table("clients").update({
        "retainer_started_at": datetime.combine(started, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
        "retainer_source": args.source,
    }).eq("id", client["id"]).execute()
    free = int(client.get("free_months") if client.get("free_months") is not None else 1)
    print(f"{name}: retainer starts {started.isoformat()} ({args.source}).")
    print(f"  free month{'s' if free != 1 else ''} run to "
          f"{(started + timedelta(days=30 * free)).isoformat()}; the guarantee is checked then.")


def cmd_downsell(args):
    """Move a client onto the recovery-only plan, or back onto the retainer.

    A plan is a contract, so the switch is a founder's command rather than a
    keyword the triage reads: the prospect replies RECOVERY, a person confirms
    it, and this records it. From the next pass the client is billed a share of
    what Amazon actually paid on our claims, at month end, and nothing else."""
    from . import billing
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    name = client["company_name"] or client["contact_email"]
    if args.retainer:
        db.table("clients").update({"plan": "retainer"}).eq("id", client["id"]).execute()
        print(f"{name}: back on the retainer. The day-30 gate (or the rolling gate) applies from the next pass; "
              f"record the yes with `hubricon retainer {args.client}` if the clock should restart.")
        return
    share = float(args.share) if args.share is not None else billing.RECOVERY_SHARE
    if not 0 < share <= 0.5:
        sys.exit("--share must be a fraction between 0 and 0.5 (0.25 = a quarter of what lands)")
    db.table("clients").update({"plan": "recovery", "recovery_share": share}).eq("id", client["id"]).execute()
    print(f"{name}: recovery-only at {share * 100:.0f}% of reimbursements Amazon pays on claims we file, "
          f"invoiced at month end (minimum ${billing.RECOVERY_MIN_INVOICE_USD:,.0f}, smaller amounts roll forward). "
          f"No retainer, no day-30 subscription. Claims: `hubricon recover {args.client} list|file|paid`.")


def cmd_casestudy(args):
    """index.html §3b: one client's case study, told in full, or nothing.

    Prints the section as it would read and every reason it may not ship.
    --publish writes it only when there are no reasons left; public_case_study()
    then serves it and re-checks consent on every read. --unpublish takes it down."""
    from . import case_study
    db = dbmod.connect()
    client = dbmod.resolve_client(db, args.client)
    name = client["company_name"] or client["contact_email"]
    if args.unpublish:
        case_study.unpublish(db, client["id"])
        print(f"{name}: case study unpublished. The section is gone on the next page load.")
        return
    run = case_study.publish if args.publish else case_study.build
    row, problems = run(db, client["id"], allow_no_miss=args.allow_no_miss)
    print(case_study.render_text(row))
    if problems:
        print("\nNot publishable yet:")
        for p in problems:
            print(f"  - {p}")
        if args.publish:
            sys.exit(1)
    elif args.publish:
        print(f"\n{name}: published. hubricon.com shows it on the next page load.")
    else:
        print("\nEvery rule passes. Run again with --publish to put it on hubricon.com.")


def cmd_all(args):
    cmd_ingest(args)
    cmd_run(args)
    args.run = None
    cmd_report(args)


def cmd_operator(args):
    from . import operator

    operator.run(send=args.send, dry=args.dry_run, digest=args.digest)


def cmd_proof(args):
    """Verified results: what the ledgers proved, and the words that let a card publish."""
    db = dbmod.connect()
    if args.action == "set":
        if not args.client:
            sys.exit("usage: hubricon proof set <client> --industry <word> [--revenue-band <band>]")
        c = dbmod.resolve_client(db, args.client)
        try:
            patch = proof.set_profile(db, c["id"], args.industry, args.revenue_band)
        except ValueError as err:
            sys.exit(str(err))
        print(f"{c['company_name'] or c['contact_email']}: {patch or 'nothing changed'}")
        return
    if args.action == "line":
        print(proof.line(db) or "(no published result yet — the copy carries no proof line)")
        return
    if args.action == "cards":
        cards = proof.cards(db)
        print(json.dumps(cards, indent=2) if cards else "[]  (nothing consented and published yet)")
        return
    rows = (db.table("results").select("*, clients(company_name, contact_email, industry)")
            .order("created_at", desc=True).execute().data)
    if not rows:
        print("No verified result yet. The operator writes one the first time a ledger proves a dollar.")
        return
    for r in rows:
        c = r.get("clients") or {}
        who = c.get("company_name") or c.get("contact_email") or r["client_id"][:8]
        print(f"  {who:<28} {proof.describe(r)}"
              + ("" if c.get("industry") else "   ← no industry word; `hubricon proof set`"))
    print(f"\nProof line the copy carries now: {proof.line(db) or '(none)'}")


def cmd_loop(_args):
    """Every arrow of the loop as a conversion from the one before it."""
    db = dbmod.connect()
    print(loopmod.table(db.rpc("pmf_scoreboard", {}).execute().data or {}))


def cmd_calibrate(args):
    """What consenting clients' real accounts say the cold engine's guesses should be."""
    db = dbmod.connect()
    if args.action == "show":
        rows = db.table("calibration").select("*").order("key").execute().data
        if not rows:
            print("Nothing calibrated yet — `hubricon calibrate` runs it; the sweep runs it weekly.")
        for r in rows:
            v = f"{float(r['value']):.4g}" if r.get("value") is not None else "—"
            print(f"  {r['key']:<44} {v:>10}  {r['method']} · {r['n_clients']} client(s), {r['n_obs']} obs")
        return
    rows = calibration.compute(db)
    live = sum(1 for r in rows if r["value"] is not None)
    print(f"\n{live} of {len(rows)} calibration row(s) carry a value; the rest say why not.")


def cmd_partner(args):
    """Referral partners: the people who already hold a list of sellers."""
    db = dbmod.connect()
    if args.action == "add":
        if not (args.code and args.name):
            sys.exit("usage: hubricon partner add <code> --name <name> [--email x] [--kind bookkeeper|prep|lender|agency|other] [--terms ...]")
        row = referral.add_partner(db, args.code, args.name, args.email, args.kind, args.terms)
        print(f"{row['name']} ({row['code']}): their link is {referral.link(row['code'])}")
        return
    if args.action == "email":
        from . import outreach
        rows = db.table("partners").select("*").eq("code", args.code or "").limit(1).execute().data
        if not rows or not args.seller:
            sys.exit("usage: hubricon partner email <code> <seller_id>")
        p = rows[0]
        facts = outreach.seller_facts(db, args.seller)
        m = outreach.partner_email(facts, p["name"], p.get("terms") or "a referral month on anything that renews")
        print(f"To: {m.get('to') or p.get('contact_email') or ''}\nSubject: {m.get('subject')}\n\n{m.get('body')}")
        print(f"\nTheir link, for the clients they introduce: {referral.link(p['code'])}")
        return
    rows = db.table("partners").select("*").order("created_at").execute().data
    if not rows:
        print("No partners yet — `hubricon partner add <code> --name <name>`.")
    for p in rows:
        print(f"  {p['code']:<12} {p['name']:<30} {p['kind']:<10} {referral.link(p['code'])}"
              + (f"   {p['terms']}" if p.get("terms") else ""))


def cmd_scoreboard(_args):
    import json

    db = dbmod.connect()
    print(json.dumps(db.rpc("pmf_scoreboard", {}).execute().data, indent=2, default=str))


def promise_rows(db, one_client: str | None = None) -> list[tuple]:
    """Which promises the machine can keep right now.

    Every line on the site is now backed by a job, and a job with a missing
    secret is a promise that fails quietly. Read-only. Shared by
    `hubricon promises` and the operator's daily digest, so a gap reaches the
    founder without anyone remembering to look."""
    from . import billing, issue as issuemod, tts, video

    rows = []

    def add(promise, where, ok, detail):
        rows.append((promise, where, ok, detail))

    # -- the deliverables ----------------------------------------------------
    can_video, why = video.available()
    add("A video with every issue", "index, welcome, terms §2", can_video,
        f"speech via {tts.provider()}" if can_video else why)

    mail = email_configured()
    add("A brief every two weeks", "welcome, index", mail,
        "published daily by the issue job, emailed through Resend" if mail
        else "RESEND_API_KEY missing — briefs publish to Hubricon but no email goes out")
    add("Corrections stated before they go live", "terms §6", mail,
        "the veto notice needs email; without it nothing auto-approves, by design"
        if not mail else "sweep --issue notifies, then opens the window")

    stripe_ok = billing.stripe_configured() and bool(os.environ.get("STRIPE_PRICE_ID"))
    add("No invoice unless we found more than we cost", "terms §3, 8 surfaces", stripe_ok,
        "the day-30 pass creates the subscription" if stripe_ok
        else "STRIPE_SECRET_KEY / STRIPE_PRICE_ID missing — a client who clears the bar is "
             "flagged in the digest instead of billed. Nobody is ever wrongly billed.")

    add("Free data + Profit Record export, any time", "terms §11, privacy §6, Hubricon", True,
        "hubricon export <client>")
    add("An invoice the Profit Record hasn't covered is void", "terms §3, index, welcome", stripe_ok,
        "every new invoice is judged by the day-30 bar; one the ledger has not covered is voided" if stripe_ok
        else "STRIPE_SECRET_KEY missing — an uncovered invoice is flagged in the digest instead of voided")
    add("Recovery-only clients pay only on money that landed", "terms §4", True,
        "the invoice amount is derived from paid claims we filed; nothing landed, no invoice")

    # -- the clocks ----------------------------------------------------------
    try:
        overdue = [r for r in db.table("data_requests").select("kind, due_at")
                   .is_("closed_at", "null").execute().data
                   if datetime.fromisoformat(str(r["due_at"])) < datetime.now(timezone.utc)]
        add("Deletion in 30d · DSAR in 7d · breach in 72h", "privacy §5–7", not overdue,
            "no open request is past its deadline" if not overdue
            else f"{len(overdue)} request(s) PAST the deadline the privacy policy states")
    except Exception as err:
        add("Deletion in 30d · DSAR in 7d · breach in 72h", "privacy §5–7", False,
            f"data_requests unreadable: {str(err)[:60]}")

    # -- per client ----------------------------------------------------------
    clients = ([dbmod.resolve_client(db, one_client)] if one_client
               else db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data)
    for c in clients:
        if onboarding.is_internal(c["contact_email"], c.get("contact_name")) and not one_client:
            continue
        name = c["company_name"] or c["contact_email"]
        add(f"{name}: the retainer clock", "terms §3", bool(c.get("retainer_started_at")),
            f"runs from {str(c['retainer_started_at'])[:10]} ({c.get('retainer_source')})"
            if c.get("retainer_started_at")
            else "no agreed start date — billing will not start. `hubricon retainer <client>`")

        late = []
        for channel in channels.channels_for(c.get("platform")):
            late += issuemod.overdue_executions(db, c, channel)
        add(f"{name}: first fixes live in week one", "welcome", not late,
            "nothing approved is waiting" if not late
            else f"{len(late)} approved directive(s) not executed, oldest {late[0]['days']}d")

        landed = c.get("exports_landed_at")
        if landed:
            first = c.get("first_issue_at")
            waited = speed.hours(landed, first or datetime.now(timezone.utc))
            within = waited is not None and waited <= speed.SLA_HOURS
            add(f"{name}: the Teardown inside {speed.SLA_HOURS} hours of the exports", "welcome, index, terms §2",
                within,
                f"Issue 001 landed {waited}h after the exports" if first
                else f"exports landed {waited}h ago and Issue 001 has not published — `hubricon operator`")

        live = (db.table("price_tests").select("id, sku").eq("client_id", c["id"])
                .eq("status", "running").execute().data)
        if live:
            today = date.today().isoformat()
            unread = [t for t in live if not db.table("price_test_watch").select("id")
                      .eq("price_test_id", t["id"]).eq("observed_on", today).limit(1).execute().data]
            add(f"{name}: Buy Box watched daily", "index, terms §6", not unread,
                "all live tests read today" if not unread
                else f"{len(unread)} live test(s) unread today — `hubricon watch`")

    return rows


def cmd_promises(args):
    db = dbmod.connect()
    rows = promise_rows(db, args.client)
    width = max(len(r[0]) for r in rows)
    kept = sum(1 for r in rows if r[2])
    print(f"Promises the machine can keep right now: {kept}/{len(rows)}\n")
    for promise, where, ok, detail in rows:
        print(f"  {'OK  ' if ok else 'GAP '} {promise:<{width}}  {where}")
        print(f"  {'':<4} {'':<{width}}  {detail}")
    if kept < len(rows):
        print("\nA GAP is a promise on the site that nothing is currently keeping. "
              "None of them bill a client wrongly; they under-deliver quietly, which is why "
              "this command exists.")


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


def _teardown_row(t: dict) -> str:
    seller = t.get("seller") or {}
    brand = (seller.get("brand") or seller.get("seller_name") or t["prospect_key"])[:22]
    finding = t.get("finding") or {}
    hi, lo = t.get("dollars_high"), t.get("dollars_low")
    money = f"${float(lo or 0):,.0f}-${float(hi or 0):,.0f}/mo" if hi else "per-unit only"
    state = "READY" if t.get("ready") else (t.get("blocker") or "")
    return (f"  {t['id'][:8]}  {brand:<22} {finding.get('kind', '?'):<20} {money:>19}  "
            f"{state}")


def cmd_teardown(args):
    """The cold engine: a defensible finding about a stranger, as a page and an email."""
    from .cold import compliance, page as coldpage, priors, run as cold, settings

    action = getattr(args, "action", None) or "today"
    db = dbmod.connect()

    if action == "ratecard":
        if getattr(args, "json", False):
            import json as _json
            print(_json.dumps(priors.ratecard_dict(), indent=1))
            return
        warning = priors.stale()
        in_force = priors.card_for()
        print(f"  surcharge {priors.FUEL_SURCHARGE:.1%} from {priors.FUEL_SURCHARGE_FROM}")
        print(f"  status    {warning or f'inside the {in_force.name} window'}\n")
        for card in priors.CARDS:
            print(f"{card.source}\n  in force  {card.effective} to {card.through}\n")
            for name, table in (("small standard", card.small), ("large standard", card.large)):
                print(f"{name}   (upper edge)      <$10    $10-50     >$50")
                for edge, fees in table:
                    print(f"    {edge:>3} oz{'':<18}" + "".join(f"{f:>9.2f}" for f in fees))
                print()
            print("Large standard above 3 lb: "
                  + " / ".join(f"${b:,.2f}" for b in card.over_3lb_base)
                  + f" plus ${priors.LARGE_STANDARD_OVER_3LB_PER_4OZ:.2f} per 4 oz over 3 lb.\n")
        print("Verify against Seller Central -> Fulfilment by Amazon fees -> US, and edit\n"
              "engine/src/hubricon_engine/cold/priors.py if a figure has moved. Every dollar\n"
              "the cold engine claims comes from this table.")
        print(f"\nShopify / carrier card: {priors.CARRIER_SOURCE}. "
              f"{'loaded' if priors.CARRIER_GROUND_USD else 'EMPTY, so Shopify prospects are never sent.'}")
        return

    if action == "add":
        from .cold import intake
        from .harvest import shopify as shopify_harvest

        # stdin only on an explicit "-". Sniffing for a pipe means that running
        # the command with no arguments — which is how anyone discovers what it
        # wants — hangs forever with no output, waiting on a terminal nobody is
        # typing into.
        text = "" if args.ref == "-" else (args.ref or "")
        if args.file:
            text += "\n" + open(args.file).read()
        if args.ref == "-":
            text += "\n" + sys.stdin.read()
        if args.email:
            text += f",{args.email}"
        if args.first_name:
            text += f",{args.first_name}"
        leads, bad = intake.parse(text)
        if not leads:
            print("Nothing to add. A lead is a domain, or an Amazon seller id — with an\n"
                  "address and a first name if you found them, which is the whole point.\n\n"
                  "  hubricon teardown add holtzleather.com\n"
                  "  hubricon teardown add holtzleather.com --email nora@holtzleather.com "
                  "--first-name Nora\n"
                  "  hubricon teardown add --file leads.csv    one per line: domain, email, name\n"
                  "  pbpaste | hubricon teardown add -         straight from the clipboard")
            for line in bad:
                print(f"  could not read: {line}")
            return
        print(f"{len(leads)} lead(s) to read."
              + (f" {len(bad)} line(s) skipped." if bad else ""))
        for line in bad:
            print(f"  skipped: {line}")
        amazon = [lead for lead in leads if lead.is_amazon]
        stores = [lead for lead in leads if not lead.is_amazon]
        keys = []
        if stores:
            # Through Chrome: a store answers a plain client with 429 and a
            # browser with its JSON, the same lesson Amazon taught.
            fetcher = shopify_harvest.store_fetcher()
            for lead in stores:
                try:
                    key, note = intake.add_shopify(db, fetcher, lead)
                except Exception as err:
                    key, note = None, f"failed: {err}"
                print(f"  {lead.handle:<34} {note}")
                if key:
                    keys.append(key)
        if amazon:
            from .harvest.fetch import Fetcher

            fetcher = Fetcher()
            for lead in amazon:
                try:
                    key, note = intake.add_amazon(db, fetcher, lead, log=lambda *_a: None)
                except Exception as err:
                    key, note = None, f"failed: {err}"
                print(f"  {lead.ident:<34} {note}")
                if key:
                    keys.append(key)
        if not keys:
            print("\nNothing readable was found at those addresses.")
            return
        print(f"\nModelling {len(keys)}...")
        summary = cold.build(db, limit=len(keys), only=keys, force=True)
        if summary.get("stale"):
            return
        print(f"  {summary['built']} produced a teardown, "
              f"{summary['no_finding']} produced nothing that cleared the bar, "
              f"{summary['blocked']} are not contactable")
        for reason, n in sorted(summary["reasons"].items(), key=lambda kv: -kv[1])[:5]:
            print(f"      {n:>3}  {reason}")
        rows = cold.queue(db, "draft", 50)
        mine = [t for t in rows if t["prospect_key"] in set(keys)]
        if mine:
            print()
            for t in mine:
                print(_teardown_row(t))
        print("\nNext: hubricon teardown review")
        return

    if action == "send":
        from . import instantly
        from .cold import dispatch

        rehearse = args.dry_run or settings.dry_run()
        if settings.dry_run() and not args.dry_run:
            print("COLD_DRY_RUN is on, so nothing leaves. That is the safety, not a fault.\n"
                  "  hubricon teardown send --dry-run           rehearse: who would go\n"
                  "  COLD_DRY_RUN=false hubricon teardown send  actually dispatch\n")
        api = instantly.Instantly() if instantly.configured() else None
        n, notes = dispatch.push(db, api, dry=rehearse, limit=args.limit)
        for note in notes:
            print(f"  {note}")
        waiting = len(dispatch.approved(db))
        print(f"\n{n} teardown(s) {'would go' if rehearse else 'dispatched'}; "
              f"{waiting} approved and waiting.")
        if api is None:
            print("No INSTANTLY_API_KEY here. The hourly operator holds it and dispatches on "
                  "its own pass, so approving is enough.")
        return

    if action == "suppress":
        if not args.who:
            print("Give an email or a domain: hubricon teardown suppress hello@acme.com "
                  "--reason 'asked us to stop'")
            return
        who = args.who.strip().lower()
        field = "email" if "@" in who else "domain"
        compliance.suppress(db, reason=args.reason or "manual", **{field: who})
        print(f"Suppressed {field} {who}. Nothing will be sent to it again, by any lane.")
        return

    if action == "stats":
        s = cold.stats(db)
        print("COLD ENGINE\n")
        print(f"  modelled              {s['modelled']} prospect(s)")
        thin = s["no_price"] + s["no_weight"]
        print(f"  no listing on file    {s['no_price']}")
        print(f"  listing, no weight    {s['no_weight']}")
        if thin:
            print(f"      -> {thin} of {s['modelled']} are thin data, not a silent engine. "
                  f"Fix with: hubricon harvest listings")
        print(f"  judged on real data   {s['judged']}")
        print(f"    produced a finding  {s['selected']}"
              + (f"   ({1 - s['silent_rate']:.0%})" if s["silent_rate"] is not None else ""))
        if s["silent_rate"] is not None:
            if s["silent_rate"] < 0.25:
                verdict = ("SUSPICIOUS - a gate that refuses almost nothing is not a gate. "
                           "Check COLD_MIN_CONFIDENCE.")
            elif s["silent_rate"] <= 0.85:
                verdict = "healthy"
            else:
                verdict = ("expected on snapshot-only data: four of five detectors need a "
                           "weight near a band edge")
            print(f"    stayed silent       {s['silent_rate']:.0%}   {verdict}")
        for reason, n in list(s["why_silent"].items())[:6]:
            print(f"        {n:>3}  {reason}")
        queue = ", ".join(f"{k} {v}" for k, v in sorted(s["by_status"].items()))
        print(f"\n  queue                 {queue or 'empty'}")
        if s["approval_rate"] is not None:
            bar = "PASSES" if s["approval_rate"] >= 0.90 else "the Phase 2 gate wants 45 of 50"
            print(f"  you kept              {s['kept']} of {s['reviewed']} reviewed "
                  f"({s['approval_rate']:.0%})   {bar}")
        if s["events"]:
            print("  pages                 " + ", ".join(f"{k} {v}" for k, v in
                                                         sorted(s["events"].items())))
        return

    if action in ("show", "open", "approve", "reject", "sent", "name"):
        t = cold.resolve(db, args.ref)
        if not t:
            print(f"No teardown matches {args.ref!r}. Try `hubricon teardown queue`.")
            return
        if action == "show":
            seller = t["seller"]
            print(f"{seller.get('brand') or t['prospect_key']}   [{t['status']}]   {t['id'][:8]}")
            print(f"  page      {t['url']}")
            print(f"  expires   {str(t['expires_at'])[:10]}")
            print(f"  finding   {(t['finding'] or {}).get('kind')}   "
                  f"confidence {(t['finding'] or {}).get('confidence')}")
            for r in (t["run"].get("rejected") or []):
                print(f"      also found {r['kind']}: {r['reason']}")
            print(f"\nTo:      {t['seller'].get('email')}")
            print(f"Subject: {t['subject']}\n")
            print(t["body"])
            print("\n--- send this by hand, from your own mailbox, after editing it. ---")
            print(f"Then: hubricon teardown sent {t['id'][:8]}")
            return
        if action == "open":
            path = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"teardown-{t['id'][:8]}.html")
            with open(path, "w") as fh:
                fh.write(t["html"])
            subprocess.run(["open", path], check=False)
            print(f"Opened {path}\n(this is byte-for-byte the page the prospect sees at {t['url']})")
            return
        if action == "name":
            ok, why = cold.name_owner(db, t["id"], first_name=args.first_name,
                                      last_name=args.last_name, email=args.email)
            print(why if ok else f"Not saved: {why}")
            if ok:
                print(f"  hubricon teardown show {t['id'][:8]}")
            return
        if action == "approve":
            cold.decide(db, t["id"], "approved", args.note)
            print(f"Approved. The page is live at {t['url']}\n"
                  f"Send the email, then: hubricon teardown sent {t['id'][:8]}")
            return
        if action == "reject":
            cold.decide(db, t["id"], "rejected", args.note)
            print("Rejected." + (f" Noted: {args.note}" if args.note else
                                 " Pass --note next time; the note is how the gate gets fixed."))
            return
        ok, why = cold.mark_sent(db, t["id"], sending_domain=args.domain)
        print(("Sent: " if ok else "NOT recorded: ") + why)
        return

    if action == "review":
        rows = [r for r in cold.queue(db, "draft", args.limit) if r["ready"] or args.all]
        if not rows:
            print("Nothing waiting that is ready to send. `hubricon teardown` shows what is\n"
                  "blocked and why; --all walks the blocked ones too.")
            return
        print(f"{len(rows)} waiting. For each: [s]end it, [n]o, [o]pen the page, [q]uit.\n")
        kept = 0
        for i, t in enumerate(rows, 1):
            full = cold.resolve(db, t["id"])
            seller = full["seller"]
            print("=" * 78)
            print(f"{i}/{len(rows)}  {seller.get('brand') or full['prospect_key']}   "
                  f"{seller.get('email') or 'NO ADDRESS'}   {full['url']}")
            if full["blocker"]:
                print(f"BLOCKED: {full['blocker']}")
            print("=" * 78)
            print(f"Subject: {full['subject']}\n")
            print(full["body"])
            while True:
                choice = input("\n[s]end / [n]o / [o]pen / [q]uit > ").strip().lower()[:1]
                if choice == "o":
                    path = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                                        f"teardown-{full['id'][:8]}.html")
                    with open(path, "w") as fh:
                        fh.write(full["html"])
                    subprocess.run(["open", path], check=False)
                    continue
                break
            if choice == "q":
                break
            if choice == "s":
                cold.decide(db, full["id"], "approved")
                kept += 1
                print(f"  approved. Send it, then: hubricon teardown sent {full['id'][:8]}")
            else:
                note = input("  why not? (this is how the gate gets fixed) > ").strip()
                cold.decide(db, full["id"], "rejected", note)
        print(f"\nKept {kept}. `hubricon teardown stats` shows the running rate; the Phase 2 "
              f"gate is 45 of 50 unedited.")
        return

    if action in ("today", "build"):
        if action == "today":
            print("Building whatever is buildable, then showing you what is waiting.\n")
        summary = cold.build(db, limit=args.limit, force=args.force, only=args.seller)
        if summary.get("stale"):
            return
        print(f"Looked at {summary['looked']} prospect(s):")
        print(f"  {summary['built']:>4}  produced a teardown")
        print(f"  {summary['no_finding']:>4}  produced nothing that cleared the bar")
        print(f"  {summary['blocked']:>4}  are not contactable (suppressed, off-ICP, jurisdiction)")
        print(f"  {summary['skipped']:>4}  already have a recent teardown")
        if summary["reasons"]:
            print("\n  why the silent ones were silent:")
            for reason, n in sorted(summary["reasons"].items(), key=lambda kv: -kv[1])[:8]:
                print(f"      {n:>3}  {reason}")
        if summary["next"]:
            print("\n  what would unblock them:")
            for n, command, why in summary["next"]:
                print(f"      {n:>3}  {command:<28} {why}")
        print(f"\n  spend this run  ${summary['spent_usd']:.4f} "
              f"(budget ${settings.daily_budget_usd():,.2f}/day)")
        if action == "build":
            print("\nNext: hubricon teardown review")
            return

    rows = cold.queue(db, "draft", getattr(args, "limit", 25))
    if not rows:
        print("\nNothing is waiting for review.")
        return
    ready = [r for r in rows if r["ready"]]
    blocked = [r for r in rows if not r["ready"]]
    print(f"\nWAITING FOR YOU — {len(ready)} ready to send, {len(blocked)} need something "
          f"first.\n")
    for t in ready:
        print(_teardown_row(t))
    if not ready:
        print("  (none — every teardown below needs an owner's name or a real address)")
    if blocked:
        print("\n  Built, but not sendable yet. Ten minutes each on the brand's About page,\n"
              "  LinkedIn, or the state business registry turns one of these into a send:\n")
        for t in blocked[:12]:
            print(_teardown_row(t))
    print("\n  hubricon teardown review          read the ready ones and decide, one at a time")
    print("  hubricon teardown show <id>       one of them in full")
    print("  hubricon teardown open <id>       the page as the prospect sees it")


def cmd_source(args):
    """Shopify lead sourcing: discovery, qualification, contact, and the two sinks.

    Runs on the Mac, like the harvest. Nothing here sends an email: `push`
    writes to a holding-pen list the operator's enrolment cannot match, and
    `promote` lands rows at `candidate`, where the auto-push does not look.
    """
    from .sourcing import run as sourcing

    if args.action == "install":
        print(sourcing.install_launchd())
        return

    db = dbmod.connect()
    calibration.load(db)      # learned curves and ratios, when any exist
    if args.action == "status":
        print(sourcing.status_text(db))
        return
    if args.action == "calibrate":
        if not args.file:
            sys.exit("hubricon source calibrate needs --file: a csv of domain,good "
                     "(good = 1 for a store you judge in-ICP). Label a hundred by hand; "
                     "an uncalibrated scorer produces confident garbage.")
        print(sourcing.calibrate(db, args.file))
        return

    api = None
    if args.action in ("push", "all") and not args.dry_run:
        from .instantly import Instantly, configured as instantly_configured

        api = Instantly() if instantly_configured() else None
        if api is None:
            print("  INSTANTLY_API_KEY is not set on this machine — the push is a rehearsal. "
                  "The hourly operator holds the key.")

    if args.action == "sheet":
        sourcing.sheet(db, dry=args.dry_run)
        return
    if args.action == "push":
        sourcing.push(db, api, dry=args.dry_run, limit=args.limit or 200)
        return

    from .sourcing.fetch import dual_fetcher

    fetcher = dual_fetcher()
    if args.action == "discover":
        search = _search_fetcher() if args.source in ("search", "both") else None
        sourcing.discover(db, fetcher, limit=args.limit or sourcing.DISCOVER_LIMIT,
                          source=args.source, search_fetcher=search)
    elif args.action == "qualify":
        sourcing.qualify(db, fetcher, limit=args.limit or sourcing.QUALIFY_LIMIT)
    elif args.action == "contact":
        sourcing.contact(db, fetcher, limit=args.limit or sourcing.CONTACT_LIMIT,
                         search_fetcher=_search_fetcher())
    elif args.action == "promote":
        from .harvest import shopify as shopify_harvest

        sourcing.promote(db, shopify_harvest.store_fetcher(),
                         limit=args.limit or sourcing.PROMOTE_LIMIT)
    elif args.action == "all":
        sourcing.run_all(db, fetcher, api, dry=args.dry_run, limit=args.limit, source=args.source)
    print()
    print(sourcing.status_text(db))


def _search_fetcher():
    """Plain HTTP for Bing: a search engine does not want a browser, and Chrome
    wraps its results in a viewer (harvest/shopify.py's archive lesson)."""
    from .harvest import shopify as shopify_harvest

    return shopify_harvest.archive_fetcher()


def cmd_harvest(args):
    """Free leads from public pages; runs on the founder's Mac (Amazon captchas datacenters)."""
    from .harvest import run as harvest

    if args.action == "install":
        print(harvest.install_launchd())
        return
    db = dbmod.connect()
    calibration.load(db)      # learned curves and ratios, when any exist
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
    elif args.action == "shopify":
        from pathlib import Path

        from .harvest import shopify

        # Its own fetcher: through Chrome like the Amazon one (a plain client
        # gets 429 from every store), but paced for hosts that are a different
        # company each time rather than one counterparty counting requests.
        store_fetcher = shopify.store_fetcher()
        metas = None
        if args.source == "archive":
            # Free, and mostly Shopify's own dev stores. Its own plain-HTTP
            # fetcher: web.archive.org is not Shopify and answers a browser
            # with its JSON viewer instead of the bytes.
            handles = shopify.load_handles(cdx_file=Path(args.cdx_file) if args.cdx_file else None)
        else:
            handles, metas = shopify.discover(shopify.archive_fetcher(), store_fetcher)
        shopify.crawl(db, store_fetcher, handles, limit=args.limit or shopify.LIMIT, metas=metas)
    elif args.action == "profiles":
        from pathlib import Path

        harvest.profiles(db, fetcher, limit=args.limit or harvest.PROFILES_LIMIT,
                         ids_file=Path(args.ids_file) if getattr(args, "ids_file", None) else None)
    elif args.action == "requalify":
        harvest.requalify(db, fetcher, limit=args.limit or harvest.REQUALIFY_LIMIT)
    elif args.action == "listings":
        harvest.listings(db, fetcher, limit=args.limit or harvest.LISTINGS_LIMIT)
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
    p.add_argument("--channel", choices=list(channels.CHANNELS),
                   help="which platform to read (default: every channel the client sells on)")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("platform", help="set which store(s) a client runs")
    p.add_argument("client")
    p.add_argument("platform", choices=list(channels.PLATFORMS))
    p.add_argument("--shopify-domain", help="the store's myshopify domain")
    p.set_defaults(fn=cmd_platform)

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
    p.add_argument("--directive", help="directive id prefix")
    p.add_argument("--impact", type=float, help="measured impact in USD")
    p.add_argument("--auto", action="store_true",
                   help="measure every approved directive from the client's own later exports")
    p.add_argument("--dry-run", action="store_true", help="with --auto: print the verdicts, bank nothing")
    p.add_argument("--notes", help="how the measurement was made")
    p.add_argument("--force", action="store_true",
                   help="bank a directive that was never approved (stamped into the notes)")
    p.add_argument("--remeasure", action="store_true",
                   help="correct an already-measured directive (the old note is kept)")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("replay", help="score past promises against measured outcomes")
    p.add_argument("client")
    p.add_argument("--channel")
    p.add_argument("--run", help="run id to take margins and ad curves from")
    p.add_argument("--rescore", action="store_true",
                   help="score what the ledger already banked instead of re-measuring")
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("retainer", help="record when the retainer started (the client's yes)")
    p.add_argument("client")
    p.add_argument("--started", help="YYYY-MM-DD (default: today)")
    p.add_argument("--source", default="client_yes",
                   choices=["client_yes", "first_invoice", "teardown_delivered", "manual"])
    p.add_argument("--show", action="store_true", help="print the clock without changing it")
    p.set_defaults(fn=cmd_retainer)

    p = sub.add_parser("downsell", help="the smaller door: recovery-only at a share of what Amazon pays back, or --retainer")
    p.add_argument("client")
    p.add_argument("--share", type=float, help="fraction of recovered dollars, default RECOVERY_SHARE (0.25)")
    p.add_argument("--retainer", action="store_true", help="move the client back onto the flat retainer")
    p.set_defaults(fn=cmd_downsell)

    p = sub.add_parser("casestudy", help="index.html §3b: one real client's case study, previewed, published or taken down")
    p.add_argument("client")
    p.add_argument("--publish", action="store_true", help="publish when every rule passes; otherwise print why and exit 1")
    p.add_argument("--unpublish", action="store_true", help="take the section off the site")
    p.add_argument("--allow-no-miss", action="store_true",
                   help="publish a Record with no recorded miss, only when that really is the whole Record")
    p.set_defaults(fn=cmd_casestudy)

    p = sub.add_parser("promises", help="which promises the machine can keep right now, and which it cannot")
    p.add_argument("--client", help="just this client")
    p.set_defaults(fn=cmd_promises)

    p = sub.add_parser("export", help="everything we hold on a client, as one zip (Terms §11)")
    p.add_argument("client")
    p.add_argument("--out", help="output path (default: <slug>-hubricon-export-<date>.zip)")
    p.add_argument("--no-files", action="store_true", help="tables and ledger only, skip raw uploads")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("request", help="track a deletion / access / correction request against its clock")
    p.add_argument("action", choices=["open", "close", "list"], nargs="?", default="list")
    p.add_argument("--client")
    p.add_argument("--email", help="requester, when they are not a client")
    p.add_argument("--kind", choices=sorted(DATA_REQUEST_DAYS), default="access")
    p.add_argument("--note")
    p.add_argument("--id", help="request id prefix, for close")
    p.add_argument("--outcome")
    p.set_defaults(fn=cmd_request)

    p = sub.add_parser("mandate", help="record what the client authorised at kickoff")
    p.add_argument("client")
    p.add_argument("--module", choices=["pricing", "advertising", "inventory", "margin", "recovery", "general"])
    p.add_argument("--standing", action="store_true", help="we may do this without asking")
    p.add_argument("--explicit", dest="standing", action="store_false", help="nothing happens without a yes")
    p.add_argument("--bound", type=float, help="numeric bound, e.g. 0.05 for a 5%% price step")
    p.add_argument("--bound-note", help="the bound in the client's own words")
    p.add_argument("--veto-hours", type=int, default=72)
    p.add_argument("--note", help="what was agreed, and when")
    p.add_argument("--show", action="store_true", help="print the mandate without changing it")
    p.set_defaults(fn=cmd_mandate, standing=False)

    p = sub.add_parser("execute", help="record that an approved directive was carried out")
    p.add_argument("client")
    p.add_argument("--directive", required=True, help="directive id prefix")
    p.add_argument("--ref", help="the change reference in Seller Central / Shopify")
    p.add_argument("--by", help="who made the change (defaults to EXECUTION_EMAIL)")
    p.set_defaults(fn=cmd_execute)

    p = sub.add_parser("watch", help="the daily Buy Box / conversion reading on live price tests")
    p.add_argument("--client", help="just this client")
    p.add_argument("--buybox", type=float, help="Buy Box share, percent")
    p.add_argument("--conversion", type=float, help="Shopify conversion rate, percent")
    p.add_argument("--note")
    p.add_argument("--alert", action="store_true", help="email the founder about missed readings")
    p.set_defaults(fn=cmd_watch)

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

    p = sub.add_parser("issue", help="publish the fortnightly briefing (letter + report + video) and email it")
    p.add_argument("--client", help="just this client")
    p.add_argument("--send", action="store_true", help="actually email the client")
    p.add_argument("--dry-run", action="store_true", help="say who is due, publish nothing")
    p.add_argument("--force", action="store_true", help="publish even if the fortnight is not up")
    p.set_defaults(fn=cmd_issue)

    p = sub.add_parser("brief", help="publish an Issue (video and/or letter, optional full report) to the portal")
    p.add_argument("client")
    p.add_argument("--video", help="Loom share URL or video id")
    p.add_argument("--memo-file", help="path to the edited letter (markdown/plain text)")
    p.add_argument("--report", help="path to the full written report HTML to attach")
    p.add_argument("--tldr", help="3-4 sentence summary shown under the video")
    p.add_argument("--headline", help="one headline stat, e.g. '+$9,200 vs July'")
    p.add_argument("--title", help="brief title (default 'Profit Brief No. N')")
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
    p.add_argument("--buffer", type=float, help="minimum cash buffer (USD): the cone counts a path as ruined below it")
    p.add_argument("--risk-share", dest="risk_share", type=float,
                   help="share of a month's net one move may put at risk before it needs an explicit yes (0.05–0.30)")
    p.set_defaults(fn=cmd_cash)

    p = sub.add_parser("benchmark", help="where the client sits against the consenting book, as percentiles")
    p.add_argument("client")
    p.set_defaults(fn=cmd_benchmark)

    p = sub.add_parser("stress", help="what would break the account: fee rise, suppression, dearer clicks, late supplier, held payout")
    p.add_argument("client")
    p.set_defaults(fn=cmd_stress)

    p = sub.add_parser("console", help="render the internal briefing console for Loom screen-share")
    p.add_argument("client")
    p.set_defaults(fn=cmd_console)

    p = sub.add_parser("sweep", help="always-on pass over every active client: ingest, run, draft, alert")
    p.add_argument("--client", help="sweep just this client")
    p.add_argument("--alert", action="store_true", help="send alert/digest emails (needs RESEND_API_KEY)")
    p.add_argument("--issue", action="store_true",
                   help="promote the top drafts to issued and tell the client before anything goes live "
                        "(terms.html §6). Opt-in: run without it first and read what WOULD be issued.")
    p.set_defaults(fn=cmd_sweep)

    p = sub.add_parser("operator", help="hourly funnel pass: outbound, bookings, nudges, teardowns, digest")
    p.add_argument("--send", action="store_true", help="actually send emails and Instantly replies")
    p.add_argument("--dry-run", action="store_true", help="read everything, change nothing")
    p.add_argument("--digest", action="store_true", help="email the founder the digest (with --send)")
    p.set_defaults(fn=cmd_operator)

    sub.add_parser("scoreboard", help="print the PMF scoreboard").set_defaults(fn=cmd_scoreboard)

    sub.add_parser("loop", help="the loop stage by stage: every arrow as a conversion").set_defaults(fn=cmd_loop)

    p = sub.add_parser("proof", help="verified results: list them, set a client's industry word, print the proof line")
    p.add_argument("action", nargs="?", default="list", choices=["list", "set", "line", "cards"])
    p.add_argument("client", nargs="?")
    p.add_argument("--industry", help="one of: " + ", ".join(proof.INDUSTRIES))
    p.add_argument("--revenue-band", dest="revenue_band", help="e.g. '$1M–$5M'")
    p.set_defaults(fn=cmd_proof)

    p = sub.add_parser("calibrate", help="learn the cold engine's guesses from consenting clients' real accounts")
    p.add_argument("action", nargs="?", default="run", choices=["run", "show"])
    p.set_defaults(fn=cmd_calibrate)

    p = sub.add_parser("partner", help="referral partners: add, list, draft the intro email")
    p.add_argument("action", nargs="?", default="list", choices=["add", "list", "email"])
    p.add_argument("code", nargs="?")
    p.add_argument("seller", nargs="?")
    p.add_argument("--name")
    p.add_argument("--email")
    p.add_argument("--kind", default="other", choices=["bookkeeper", "prep", "lender", "agency", "other"])
    p.add_argument("--terms")
    p.set_defaults(fn=cmd_partner)

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

    p = sub.add_parser("teardown", help="the cold engine: build, review and send unsolicited "
                                        "Profit Teardowns from public pages")
    p.add_argument("action", nargs="?",
                   choices=["today", "build", "queue", "review", "show", "open", "approve",
                            "reject", "sent", "name", "add", "send", "stats", "ratecard",
                            "suppress"],
                   default="today",
                   help="default 'today': build what is buildable, then show what is waiting")
    p.add_argument("ref", nargs="?", help="a teardown id prefix, seller id, or brand name")
    p.add_argument("who", nargs="?", help="for suppress: an email address or a domain")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--seller", help="build one prospect by seller id")
    p.add_argument("--force", action="store_true", help="rebuild even if a recent draft exists")
    p.add_argument("--note", help="why you rejected it, in your words")
    p.add_argument("--domain", help="the sending domain, for the per-domain daily cap")
    p.add_argument("--reason", help="for suppress: why")
    p.add_argument("--all", action="store_true",
                   help="review: walk the blocked ones too, not only the ready ones")
    p.add_argument("--first-name", help="name: the owner you just found")
    p.add_argument("--last-name", help="name: their surname, if you have it")
    p.add_argument("--email", help="name/add: their real address")
    p.add_argument("--file", help="add: a file of leads — domain, email, first name per line")
    p.add_argument("--dry-run", action="store_true", help="send: rehearse, change nothing")
    p.add_argument("--json", action="store_true",
                   help="ratecard: print every published figure as JSON (this is /ratecard.json)")
    p.set_defaults(fn=cmd_teardown)

    p = sub.add_parser("source", help="Shopify lead sourcing: Tranco+DNS discovery -> "
                                      "qualification -> a named contact -> Google Sheet + Instantly")
    p.add_argument("action", choices=["discover", "qualify", "contact", "sheet", "push",
                                      "promote", "all", "status", "calibrate", "install"])
    p.add_argument("--limit", type=int, help="rows this pass should work on")
    p.add_argument("--source", choices=["tranco", "search", "both"], default="tranco",
                   help="discover: where domains come from (default: the Tranco top-1M plus a DNS pass)")
    p.add_argument("--file", help="calibrate: csv of domain,good — a hundred stores you judged by hand")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="sheet/push: report, write nothing to Google or Instantly")
    p.set_defaults(fn=cmd_source)

    p = sub.add_parser("harvest", help="free leads: Amazon Best Sellers / archived seller profiles / "
                                       "Shopify stores → brand sites → Instantly list")
    p.add_argument("action", choices=["crawl", "enrich", "push", "all", "status", "report", "install",
                                      "wayback", "shopify", "requalify", "prune", "listings", "profiles"])
    p.add_argument("--categories", nargs="*", help="Best Sellers slugs (default: three, rotating by day)")
    p.add_argument("--ids-file", dest="ids_file",
                   help="profiles: saved seller-id list (default ~/.hubricon/harvest/seller-ids.txt)")
    p.add_argument("--within-oz", dest="within_oz", type=float, default=1.0,
                   help="report: ounces above a lighter FBA weight band that count as a cliff (default 1)")
    p.add_argument("--max-products", dest="max_products", type=int, help="product pages per run (default 150)")
    p.add_argument("--limit", type=int, help="rows to enrich / push this run")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="push/prune: report, don't touch Instantly")
    p.add_argument("--workers", type=int, help="wayback: parallel fetchers against web.archive.org (default 3)")
    p.add_argument("--cdx-file", dest="cdx_file", help="wayback/shopify: saved CDX listing (default "
                                                       "~/.hubricon/harvest/wayback-sellers.cdx, shopify-stores.cdx)")
    p.add_argument("--source", choices=["search", "archive"], default="search",
                   help="shopify: where stores come from (default: category searches of Shopify's own marketplace)")
    p.set_defaults(fn=cmd_harvest)

    p = sub.add_parser("adtest", help="plan and analyse an ON/OFF switchback on a campaign (ad incrementality)")
    p.add_argument("client")
    p.add_argument("action", choices=["plan", "analyze", "list"])
    p.add_argument("--campaign")
    p.add_argument("--start", help="first day YYYY-MM-DD (default: tomorrow)")
    p.set_defaults(fn=cmd_adtest)

    p = sub.add_parser("pricetest", help="plan and track a price test (the wedge program)")
    p.add_argument("client")
    p.add_argument("action", choices=["plan", "start", "track", "complete", "abort", "list", "analyze"])
    p.add_argument("--sku")
    p.add_argument("--to", type=float, help="test price (fixed design)")
    p.add_argument("--design", choices=["fixed", "randomized"], default="fixed",
                   help="randomized: six 7-day blocks around the current price, drawn by the engine")
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
        simulations=20000, seed=42, run=None, out=None, channel=None,
    )

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
