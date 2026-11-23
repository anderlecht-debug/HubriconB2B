"""The Shopify app's scheduled jobs, one CLI: `python -m hubricon_engine.shopify_run
ingest|shadow|meter`. .github/workflows/shopify.yml runs them.

  ingest  nightly. For each installed store: pull orders (last 60 days),
          products and stock through the Bulk Operations API (shopify_api),
          upsert the same rows a CSV upload would write, and compute the free
          look-back (lookback.run), written to the private intake bucket under
          shopify/<shop>/lookback.json.
  shadow  weekly (Monday). For each store: grade last week's sealed calls
          against what happened (shadow.grade, which seals the measured
          entries), then make and seal this week's (shadow.run). The calls are
          kept in the intake bucket under shopify/<shop>/shadow/<week>.json so
          the next run can grade them; before grading, each stored call is
          checked against its sealed leaf's evidence digest, so a call edited
          after sealing is refused, not graded.
  meter   monthly. For each live store: the months of measured dollars on the
          client's directives, through hwm.run (the high-water-mark fee rule),
          and the latest month's statement through usage.send. Dry run unless
          --send. hwm and usage are imported lazily.

Stores come from shopify_shops (status 'active', or every one with --all) or
from --shop with SHOPIFY_ACCESS_TOKEN. The token is decrypted with
SHOPIFY_TOKEN_KEY exactly as lib/shopify.js encrypts it (AES-256-GCM, the shop
domain as AAD). The data tables key on a clients row: a store's client is the
shop row's client_id when it has one, else --client; a store with neither is
skipped and named.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from . import ledger, lookback, mandate, meter_gate, shadow, shopify_api
from . import seal as sealmod

SHOPS = "shopify_shops"
BUCKET = "intake"
NEVER_BILLED_MODULES = {shadow.MODULE, ledger.MODULE}


# ── stores and tokens ────────────────────────────────────────────────────────

def decrypt_token(blob: str, raw_key: str, shop: str = "") -> str:
    """lib/shopify.js decryptToken: "v1:" + base64url(iv[12] | tag[16] | ciphertext)."""
    from cryptography.hazmat.primitives.ciphers.aead import (
        AESGCM,  # lazy: only the live job needs it
    )
    if not isinstance(blob, str) or not blob.startswith("v1:"):
        raise ValueError("unknown token format")
    key = bytes.fromhex(raw_key) if len(raw_key) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw_key) \
        else base64.b64decode(raw_key)
    if len(key) != 32:
        raise ValueError("SHOPIFY_TOKEN_KEY must be 32 bytes")
    body = blob[3:]
    buf = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    iv, tag, ct = buf[:12], buf[12:28], buf[28:]
    return AESGCM(key).decrypt(iv, ct + tag, shop.encode()).decode()


def stores(db, args, env=os.environ) -> list[dict]:
    """[{shop, token, client_id, row}] to run, each resolvable or skipped by name."""
    if args.shop:
        token = env.get("SHOPIFY_ACCESS_TOKEN")
        if not token:
            sys.exit("--shop needs SHOPIFY_ACCESS_TOKEN in the environment")
        row = {}
        if db is not None:
            rows = db.table(SHOPS).select("*").eq("shop_domain", args.shop).execute().data or []
            row = rows[0] if rows else {}
        return [{"shop": args.shop, "token": token, "client_id": row.get("client_id") or args.client, "row": row}]
    q = db.table(SHOPS).select("*")
    rows = q.execute().data or []
    if not getattr(args, "all", False):
        rows = [r for r in rows if r.get("status") == "active"]
    out = []
    for r in rows:
        try:
            token = decrypt_token(r.get("token_enc"), env.get("SHOPIFY_TOKEN_KEY", ""), r["shop_domain"])
        except Exception as err:
            print(f"  skip {r['shop_domain']}: token not readable ({type(err).__name__})", file=sys.stderr)
            continue
        out.append({"shop": r["shop_domain"], "token": token, "client_id": r.get("client_id") or args.client, "row": r})
    return out


def _put(db, path: str, payload) -> None:
    db.storage.from_(BUCKET).upload(path, json.dumps(payload, default=str).encode(),
                                    {"content-type": "application/json", "upsert": "true"})


def _get(db, path: str):
    try:
        return json.loads(db.storage.from_(BUCKET).download(path))
    except Exception:
        return None


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ── ingest ───────────────────────────────────────────────────────────────────

def ingest_store(db, store: dict, today: date, days: int, pulled: dict | None = None) -> dict:
    from . import db as dbmod
    pulled = pulled or shopify_api.pull(shopify_api.http_transport(store["shop"], store["token"]),
                                        shopify_api.http_downloader(), today=today, days=days)
    written = shopify_api.ingest(pulled, store["client_id"])
    for table, rows, on_conflict in written:
        if rows:
            dbmod.chunked_upsert(db, table, rows, on_conflict)
    tables = {t: rows for t, rows, _ in written}
    tz = (pulled.get("shop") or {}).get("timezone") or "UTC"
    tables["sku_economics"] = shopify_api.weekly_economics(
        pulled["orders"], store["client_id"], date.fromisoformat(pulled["since"]), today - timedelta(days=1), tz)
    look = lookback.run(tables, today=today, window_days=days, last_sold=shopify_api.last_sold(pulled["orders"], tz))
    _put(db, f"shopify/{store['shop']}/lookback.json", look)
    led = ledger_store(db, store, today, tables, pulled)
    return {"rows": {t: len(r) for t, r, _ in written}, "lookback": look, "ledger": led}


def _ours(db, client_id: str) -> set:
    """(variant_id, price) of every step Hubricon executed, so the ledger leaves them out."""
    try:
        rows = db.table("directives").select("evidence, executed_by").eq("client_id", client_id).execute().data or []
    except Exception:
        return set()
    return {((r.get("evidence") or {}).get("variant_id"), float((r.get("evidence") or {}).get("p_new")))
            for r in rows if r.get("executed_by") == mandate.EXECUTED_BY
            and (r.get("evidence") or {}).get("variant_id") and (r.get("evidence") or {}).get("p_new") is not None}


def ledger_store(db, store: dict, today: date, tables: dict, pulled: dict) -> dict:
    """Snapshot tonight's variants, seal every move seen since the last
    snapshot as observed-not-ours, grade the ledger, and keep it for the app."""
    base = f"shopify/{store['shop']}"
    cid = store["client_id"]
    cur = ledger.snapshot(pulled.get("products") or [], today)
    prev = _get(db, f"{base}/snapshot.json")
    found = ledger.detect(prev, cur, cid, ours=_ours(db, cid))
    sealed = ledger.seal(db, cid, found) if found else {"status": sealmod.NOTHING}
    kept = _get(db, f"{base}/ledger_entries.json") or []
    have = {e["id"] for e in kept}
    entries = kept + [e for e in found if e["id"] not in have and e["id"] in (sealed.get("short") or {})]
    grades = ledger.grade(entries, tables, today, db=db, client_id=cid)
    _put(db, f"{base}/ledger_entries.json", entries)
    _put(db, f"{base}/ledger.json", ledger.summary(entries, grades))
    _put(db, f"{base}/snapshot.json", cur)
    return {"seen": len(found), "seal": sealed.get("status"), "entries": len(entries)}


def cmd_ingest(db, args) -> int:
    today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
    failures = 0
    for s in stores(db, args):
        if not s["client_id"]:
            print(f"  skip {s['shop']}: no client_id on its shopify_shops row and no --client", file=sys.stderr)
            continue
        try:
            out = ingest_store(db, s, today, args.days)
            print(f"  ingested {s['shop']}: {out['rows']}; look-back {len(out['lookback']['items'])} item(s)")
        except Exception as err:
            failures += 1
            print(f"  FAILED {s['shop']}: {type(err).__name__}: {str(err)[:200]}", file=sys.stderr)
    return 1 if failures else 0


# ── shadow ───────────────────────────────────────────────────────────────────

def untampered(db, client_id: str, calls: list[dict]) -> tuple[list[dict], list[str]]:
    """Stored calls whose evidence still hashes to what was sealed."""
    rows = db.table(sealmod.TABLE).select("*").eq("client_id", client_id).execute().data or []
    sealed = {r["entry_key"]: r for r in rows}
    ok, bad = [], []
    for c in calls:
        row = sealed.get(sealmod.called_key(c["id"]))
        doc = (row or {}).get("document") or {}
        if row and doc.get("evidence_sha256") == sealmod.digest(sealmod.promise_evidence(c.get("evidence"))):
            ok.append(c)
        else:
            bad.append(c["id"])
    return ok, bad


def shadow_store(db, store: dict, today: date, days: int, pulled: dict | None = None) -> dict:
    pulled = pulled or shopify_api.pull(shopify_api.http_transport(store["shop"], store["token"]),
                                        shopify_api.http_downloader(), today=today, days=days)
    tz = (pulled.get("shop") or {}).get("timezone") or "UTC"
    cid = store["client_id"]
    week = _monday(today)
    tables = {t: rows for t, rows, _ in shopify_api.ingest(pulled, cid)}
    econ = shopify_api.weekly_economics(pulled["orders"], cid, date.fromisoformat(pulled["since"]),
                                        week - timedelta(days=1), tz)
    out = {"graded": None, "refused": []}
    last = _get(db, f"shopify/{store['shop']}/shadow/{(week - timedelta(days=7)).isoformat()}.json")
    if last:
        calls, out["refused"] = untampered(db, cid, last)
        out["graded"] = shadow.grade(calls, econ, tables.get("cogs_inputs"), db=db, client_id=cid)
        _put(db, f"shopify/{store['shop']}/shadow/{(week - timedelta(days=7)).isoformat()}.grade.json", out["graded"])
        summary = _get(db, f"shopify/{store['shop']}/shadow/summary.json") or {"weeks": []}
        summary["weeks"] = [w for w in summary["weeks"] if w["week_start"] != (week - timedelta(days=7)).isoformat()]
        summary["weeks"].append({"week_start": (week - timedelta(days=7)).isoformat(), "n_graded": out["graded"]["n_graded"],
                                 "hits": out["graded"]["hits"], "gap_units": out["graded"]["gap_units"]})
        n = sum(w["n_graded"] for w in summary["weeks"])
        summary.update({"label": "sealed call", "n_graded": n, "hits": sum(w["hits"] for w in summary["weeks"]),
                        "hit_rate": round(sum(w["hits"] for w in summary["weeks"]) / n, 4) if n else None,
                        "target_hit_rate": out["graded"]["target_hit_rate"]})
        _put(db, f"shopify/{store['shop']}/shadow/summary.json", summary)
    data = {**tables, "sku_economics": econ}
    made = shadow.run(db, data, cid, week)
    if made["seal"]["status"] in (sealmod.SEALED, sealmod.ALREADY, sealmod.PARTIAL):
        _put(db, f"shopify/{store['shop']}/shadow/{week.isoformat()}.json", made["calls"])
    out.update({"calls": len(made["calls"]), "seal": made["seal"]["status"]})
    out["mandate"] = mandate_store(db, store, today, data, pulled)
    return out


def mandate_store(db, store: dict, today: date, data: dict, pulled: dict, transport=None) -> dict:
    """Sort this week's drafted moves by the brand's limits; carry out the ones
    inside them once shadow mode is over; keep the rest for the brand's tap."""
    from .directives import draft_directives
    from .lookback import _safe, complete
    from .models import elasticity, margin, shopify_findings
    row = store.get("row") or {}
    limits = mandate.load(db, store["shop"])
    full = complete(data)
    margins = _safe(margin.run, full, default=[])
    fits = _safe(elasticity.run, full, default=[])
    drafts = _safe(draft_directives, [], [], fits, margins, channel="shopify", client_id=store["client_id"],
                   shopify_findings=_safe(shopify_findings.run, full), default=[]) or []
    sorted_ = mandate.sort(drafts, limits, installed_at=row.get("installed_at"), today=today, scopes=row.get("scopes"))
    done = []
    if sorted_[mandate.EXECUTE]:
        transport = transport or shopify_api.http_transport(store["shop"], store["token"])
        done = mandate.execute(db, store["client_id"], sorted_[mandate.EXECUTE], limits,
                               mandate.variant_index(pulled.get("products") or []), transport,
                               installed_at=row.get("installed_at"), today=today, scopes=row.get("scopes"))
    if any(r["status"] == "executed" for r in done) and row.get("mode") != "live":
        db.table(SHOPS).update({"mode": "live"}).eq("shop_domain", store["shop"]).execute()
    tap = [{"sku": (d.get("evidence") or {}).get("sku"), "kind": d.get("kind"), "text": d.get("action_text"),
            "expected_usd": d.get("expected_impact_usd"), "why": d["mandate_why"]}
           for d in sorted_[mandate.AWAITING_TAP]]
    _put(db, f"shopify/{store['shop']}/awaiting_tap.json", {"label": "awaiting your tap", "moves": tap})
    return {"executed": sum(r["status"] == "executed" for r in done), "results": done,
            "awaiting_tap": len(tap), "shadow": len(sorted_[mandate.SHADOW]),
            "in_shadow": mandate.in_shadow(row.get("installed_at"), limits, today)}


def cmd_shadow(db, args) -> int:
    today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
    failures = 0
    for s in stores(db, args):
        if not s["client_id"]:
            print(f"  skip {s['shop']}: no client_id", file=sys.stderr)
            continue
        try:
            out = shadow_store(db, s, today, args.days)
            g = out["graded"]
            print(f"  shadow {s['shop']}: {out['calls']} call(s) sealed ({out['seal']})"
                  + (f"; last week {g['hits']}/{g['n_graded']} inside the 90% range, gap {g['gap_units']} units"
                     if g else "; nothing to grade yet")
                  + (f"; {len(out['refused'])} stored call(s) did not match their seal" if out["refused"] else ""))
        except Exception as err:
            failures += 1
            print(f"  FAILED {s['shop']}: {type(err).__name__}: {str(err)[:200]}", file=sys.stderr)
    return 1 if failures else 0


# ── meter ────────────────────────────────────────────────────────────────────

def months_of(directives: list[dict], disputed: set[str] | None = None) -> list[dict]:
    """hwm.run's input from a client's measured directives (never a shadow call)."""
    by: dict[str, list[dict]] = defaultdict(list)
    for d in directives:
        # Shadow calls were never made; ledger entries were never ours. Neither is ever billed.
        if (d.get("module") in NEVER_BILLED_MODULES or d.get("mandate") == ledger.MANDATE
                or d.get("measured_impact_usd") is None or not d.get("measured_at")):
            continue
        month = str(d["measured_at"])[:7]
        by[month].append({"id": str(d["id"]), "usd": float(d["measured_impact_usd"]),
                          "grade": d.get("attribution") or "none", "month": month})
    return [{"month": m, "dollars": by[m], "disputed": sorted(disputed or ())} for m in sorted(by)]


def cmd_meter(db, args) -> int:
    from . import hwm, usage  # lazy: built beside this module
    from .db import fetch_all
    failures = 0
    for s in stores(db, args):
        row = s["row"] or {}
        if row.get("mode", "shadow") != "live" and not args.include_shadow:
            print(f"  {s['shop']}: shadow mode, nothing is metered")
            continue
        if not s["client_id"]:
            print(f"  skip {s['shop']}: no client_id", file=sys.stderr)
            continue
        months = months_of(fetch_all(db, "directives", s["client_id"]))
        if not months:
            print(f"  {s['shop']}: no measured dollars, nothing to bill")
            continue
        statements = hwm.run(s["shop"], months, cap_usd=float(row.get("cap_usd") or hwm.DEFAULT_CAP_USD))
        latest = statements[-1]
        _put(db, f"shopify/{s['shop']}/fee.json", {"label": "proven", "statements": statements})
        if meter_gate.mark_ask(db, s["shop"], row, statements):
            print(f"  {s['shop']}: first proven dollar banked; the fee question is now open")
        if not args.send:
            print(f"  {s['shop']}: dry run, {latest.get('month')} statement {json.dumps(latest, default=str)[:300]}")
            continue
        res = usage.send(latest, shopify_api.http_transport(s["shop"], s["token"]), row.get("usage_line_item_id"))
        print(f"  {s['shop']}: {res['status']} {res.get('amount')}")
        failures += res["status"] == "error"
    return 1 if failures else 0


# ── the command line ─────────────────────────────────────────────────────────

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m hubricon_engine.shopify_run")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("ingest", "shadow", "meter"):
        s = sub.add_parser(name)
        s.add_argument("--shop", help="one store's myshopify domain (token from SHOPIFY_ACCESS_TOKEN)")
        s.add_argument("--client", help="the clients.id its rows belong to, when the shop row has none")
        s.add_argument("--all", action="store_true", help="every installed store, not only active ones")
        s.add_argument("--today", help="run as of this date (YYYY-MM-DD)")
        s.add_argument("--days", type=int, default=shopify_api.DEFAULT_DAYS)
        if name == "meter":
            s.add_argument("--send", action="store_true", help="send the usage record (default: dry run)")
            s.add_argument("--include-shadow", action="store_true")
    return p


COMMANDS = {"ingest": cmd_ingest, "shadow": cmd_shadow, "meter": cmd_meter}


def main(argv=None, db=None) -> int:
    args = parser().parse_args(argv)
    if db is None:
        from . import db as dbmod
        db = dbmod.connect()
    return COMMANDS[args.cmd](db, args)


if __name__ == "__main__":
    sys.exit(main())
