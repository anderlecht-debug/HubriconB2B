"""The Shopify app's scheduled jobs, one CLI: `python -m hubricon_engine.shopify_run
ingest|shadow|meter`. .github/workflows/shopify.yml runs them.

  ingest  nightly. For each installed store: pull orders (last 60 days),
          products and stock through the Bulk Operations API (shopify_api),
          upsert the same rows a CSV upload would write, and compute the free
          look-back (lookback.run), written to the private intake bucket under
          shopify/<shop>/lookback.json.
  shadow  weekly (Monday). For each store: grade the last full week's sealed
          calls against what happened (shadow.grade, which seals the measured
          entries), then make and seal NEXT week's (shadow.run), so each call
          is sealed before its week begins. The calls are kept, written once
          and never overwritten, in the intake bucket under
          shopify/<shop>/shadow/<week>.json so
          the next run can grade them; before grading, each stored call is
          rebuilt into its called document and checked against the sealed
          leaf, so a call edited after sealing is refused, not graded.
  meter   monthly. For each live store: the months of measured dollars on the
          client's directives and the brand's disputes, through hwm.run (the
          high-water-mark fee rule). Only the month that has just closed is
          billed, once (key shop|month|line item): its net fee plus any drift
          in months already billed, read back from shopify_fee_months, where
          each month's billed amount, refund due and peak are persisted. Dry
          run unless --send. hwm and usage are imported lazily.

Stores come from shopify_shops (status 'active', or every one with --all) or
from --shop with SHOPIFY_ACCESS_TOKEN. The token is decrypted with
SHOPIFY_TOKEN_KEY exactly as lib/shopify.js encrypts it (AES-256-GCM, the shop
domain as AAD). The data tables key on a clients row: a store's client is the
shop row's client_id (or --client, for one --shop run); a store without one is
skipped and named. --client is accepted only together with --shop. --client is accepted only together with --shop.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from . import ledger, lookback, mandate, meter_gate, shadow, shopify_api
from . import seal as sealmod

SHOPS = "shopify_shops"
BUCKET = "intake"
NEVER_BILLED_MODULES = {shadow.MODULE, ledger.MODULE}


# ── stores and tokens ────────────────────────────────────────────────────────

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_B64 = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


def token_key(raw: str) -> bytes:
    """SHOPIFY_TOKEN_KEY as 32 bytes, read exactly as lib/shopify.js tokenKey
    reads it: 64 hex characters, or base64 in either alphabet (standard or
    url-safe, padded or not). Anything else is refused, not half-decoded."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("SHOPIFY_TOKEN_KEY is not set")
    if _HEX64.match(raw):
        key = bytes.fromhex(raw)
    else:
        std = raw.replace("-", "+").replace("_", "/").rstrip("=")
        std += "=" * (-len(std) % 4)
        if not _B64.match(std) or len(std) % 4:
            raise ValueError("SHOPIFY_TOKEN_KEY is neither hex nor base64")
        try:
            key = base64.b64decode(std, validate=True)
        except (binascii.Error, ValueError) as err:
            raise ValueError("SHOPIFY_TOKEN_KEY is neither hex nor base64") from err
    if len(key) != 32:
        raise ValueError("SHOPIFY_TOKEN_KEY must be 32 bytes")
    return key


def decrypt_token(blob: str, raw_key: str, shop: str = "") -> str:
    """lib/shopify.js decryptToken: "v1:" + base64url(iv[12] | tag[16] | ciphertext)."""
    from cryptography.hazmat.primitives.ciphers.aead import (
        AESGCM,  # lazy: only the live job needs it
    )
    if not isinstance(blob, str) or not blob.startswith("v1:"):
        raise ValueError("unknown token format")
    key = token_key(raw_key)
    body = blob[3:]
    buf = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    iv, tag, ct = buf[:12], buf[12:28], buf[28:]
    return AESGCM(key).decrypt(iv, ct + tag, shop.encode()).decode()


def stores(db, args, env=os.environ) -> list[dict]:
    """[{shop, token, client_id, row}] to run, each resolvable or skipped by name.

    --client names one store's client and is accepted only with --shop: a run
    over every store takes each store's own shopify_shops.client_id, so one
    tenant's rows can never be written under another's."""
    if getattr(args, "client", None) and not args.shop:
        sys.exit("--client is only accepted together with --shop")
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
        out.append({"shop": r["shop_domain"], "token": token, "client_id": r.get("client_id"), "row": r})
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
            print(f"  skip {s['shop']}: no client_id on its shopify_shops row", file=sys.stderr)
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
    """Stored calls that rebuild, field for field, into the document that was
    sealed: the whole called document (expected dollars, band, text, target,
    issue time and evidence), not only the evidence digest. A call edited in
    the bucket after sealing is refused, never graded."""
    rows = db.table(sealmod.TABLE).select("*").eq("client_id", client_id).execute().data or []
    sealed = {r["entry_key"]: r for r in rows}
    ok, bad = [], []
    for c in calls:
        row = sealed.get(sealmod.called_key(c.get("id")))
        doc = (row or {}).get("document") or {}
        try:
            rebuilt = sealmod.called_document(c, client_id, doc.get("sealed_at"), doc.get("sealed"))
            same = bool(row) and sealmod.leaf_of(sealmod.as_stored(rebuilt)) == row.get("leaf") == sealmod.leaf_of(doc)
        except Exception:
            same = False
        (ok.append(c) if same else bad.append(c.get("id")))
    return ok, bad


def shadow_store(db, store: dict, today: date, days: int, pulled: dict | None = None, now=None) -> dict:
    """Grade the last full week's sealed calls, then make and seal the calls
    for the NEXT week (the Monday after today), so every call is sealed before
    the week it predicts begins, in any store's time zone. A week's stored
    calls are written once: a re-run adds only calls not yet stored and never
    rewrites one, so the bucket always matches the seal."""
    pulled = pulled or shopify_api.pull(shopify_api.http_transport(store["shop"], store["token"]),
                                        shopify_api.http_downloader(), today=today, days=days)
    tz = (pulled.get("shop") or {}).get("timezone") or "UTC"
    cid = store["client_id"]
    this_week = _monday(today)
    week = this_week + timedelta(days=7)          # the week the new calls predict
    graded_week = this_week - timedelta(days=7)   # the last week that has fully happened
    base = f"shopify/{store['shop']}/shadow"
    tables = {t: rows for t, rows, _ in shopify_api.ingest(pulled, cid)}
    econ = shopify_api.weekly_economics(pulled["orders"], cid, date.fromisoformat(pulled["since"]),
                                        this_week - timedelta(days=1), tz)
    out = {"graded": None, "refused": [], "week_start": week.isoformat()}
    last = _get(db, f"{base}/{graded_week.isoformat()}.json")
    if last:
        calls, out["refused"] = untampered(db, cid, last)
        out["graded"] = shadow.grade(calls, econ, tables.get("cogs_inputs"), db=db, client_id=cid)
        _put(db, f"{base}/{graded_week.isoformat()}.grade.json", out["graded"])
        summary = _get(db, f"{base}/summary.json") or {"weeks": []}
        summary["weeks"] = [w for w in summary["weeks"] if w["week_start"] != graded_week.isoformat()]
        summary["weeks"].append({"week_start": graded_week.isoformat(), "n_graded": out["graded"]["n_graded"],
                                 "hits": out["graded"]["hits"], "gap_units": out["graded"]["gap_units"]})
        n = sum(w["n_graded"] for w in summary["weeks"])
        summary.update({"label": "sealed call", "n_graded": n, "hits": sum(w["hits"] for w in summary["weeks"]),
                        "hit_rate": round(sum(w["hits"] for w in summary["weeks"]) / n, 4) if n else None,
                        "target_hit_rate": out["graded"]["target_hit_rate"]})
        _put(db, f"{base}/summary.json", summary)
    data = {**tables, "sku_economics": econ}
    now = now or datetime.now(UTC)
    if now.date() >= week - timedelta(days=1):
        # Within a day of the week's start (the earliest time zone's Monday), a
        # call could be sealed after its week began: none is made.
        out.update({"calls": 0, "seal": "too_late"})
        out["mandate"] = mandate_store(db, store, today, data, pulled)
        return out
    made = shadow.run(db, data, cid, week, issued_at=now)
    path = f"{base}/{week.isoformat()}.json"
    kept = _get(db, path) or []
    have = {c["id"] for c in kept}
    marks = made["seal"].get("short") or {}
    new = [c for c in made["calls"] if c["id"] not in have and c["id"] in marks]
    if new:
        # Stored calls are kept exactly as they were sealed; only calls not yet
        # stored are added (a call whose seal predates this run and differs from
        # it is refused at grading by `untampered`, never trusted).
        _put(db, path, kept + new)
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

FEE_MONTHS = "shopify_fee_months"
DISPUTES = "shopify_disputes"
# A month whose record was sent, or that had nothing to send, is settled: what
# it billed is known and later corrections to it ride on the next statement.
# A month Shopify refused (capped) or that failed collected nothing.
SETTLED = {"sent", "nothing_to_bill", "refund_due"}


NO_COST = "no cost on file: not billed"


def _sku(d: dict) -> str | None:
    return (d.get("evidence") or {}).get("sku")


def costed_skus(cogs_rows: list[dict]) -> set[str]:
    """SKUs whose unit cost is on file. A cost-sheet row without a unit cost
    (Shopify's unitCost blank, or freight only) is not a cost."""
    return {r["sku"] for r in cogs_rows or [] if r.get("sku") and float(r.get("unit_cost_usd") or 0) > 0}


def _billable(d: dict) -> bool:
    return not (d.get("module") in NEVER_BILLED_MODULES or d.get("mandate") == ledger.MANDATE
                or d.get("measured_impact_usd") is None or not d.get("measured_at"))


def uncosted(directives: list[dict], costed: set[str]) -> list[dict]:
    """Measured dollars on a SKU with no unit cost: never proven, never billed."""
    return [{"id": str(d["id"]), "sku": _sku(d), "usd": float(d["measured_impact_usd"]),
             "month": str(d["measured_at"])[:7], "label": NO_COST}
            for d in directives if _billable(d) and _sku(d) and _sku(d) not in costed]


def months_of(directives: list[dict], disputed=None, costed: set[str] | None = None) -> list[dict]:
    """hwm.run's input from a client's measured directives (never a shadow call).

    `costed`, when given, is the set of SKUs with a unit cost on file: a dollar
    on any other SKU is left out (profit without a cost is not proven).

    `disputed` is {directive id: month the brand disputed it} (shopify_disputes);
    each dispute is applied in its own month. A plain set of ids is applied in
    the latest month."""
    by: dict[str, list[dict]] = defaultdict(list)
    for d in directives:
        # Shadow calls were never made; ledger entries were never ours. Neither is ever billed.
        if not _billable(d) or (costed is not None and _sku(d) and _sku(d) not in costed):
            continue
        month = str(d["measured_at"])[:7]
        by[month].append({"id": str(d["id"]), "usd": float(d["measured_impact_usd"]),
                          "grade": d.get("attribution") or "none", "month": month})
    if disputed and not isinstance(disputed, dict):
        last = max(by) if by else None
        disputed = {str(i): last for i in disputed} if last else {}
    hits: dict[str, list[str]] = defaultdict(list)
    for did, month in (disputed or {}).items():
        hits[str(month)[:7]].append(str(did))
    return [{"month": m, "dollars": by.get(m, []), "disputed": sorted(hits.get(m, []))}
            for m in sorted(set(by) | set(hits))]


def load_disputes(db, shop: str) -> dict[str, str]:
    """{directive id: the month it was disputed in}, from shopify_disputes."""
    try:
        rows = db.table(DISPUTES).select("*").eq("shop_domain", shop).execute().data or []
    except Exception:
        return {}
    return {str(r["directive_id"]): str(r["disputed_at"])[:7] for r in rows if r.get("disputed_at")}


def load_billed(db, shop: str) -> dict[str, dict]:
    """{month: its shopify_fee_months row}: what each month billed, refunded and
    the peak it was billed on, as the previous runs persisted them."""
    rows = db.table(FEE_MONTHS).select("*").eq("shop_domain", shop).execute().data or []
    return {r["month"]: r for r in rows}


def closed_month(today: date) -> str:
    """The calendar month that has just closed: the only month a run bills."""
    return (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def _f(row: dict | None, key: str) -> float:
    return float((row or {}).get(key) or 0)


def settle(shop: str, months: list[dict], billed: dict[str, dict], month: str, *, cap_usd: float):
    """(statements, the closed month's charge statement).

    Every month is recomputed from the Record. A settled month's share of its
    fee was collected in full; a capped or failed month collected nothing, so a
    later dispute refunds nothing for it (hwm's `collected`). The closed month
    is charged its net fee plus the drift of every settled month since it was
    billed: (what settled months owe now) - (what they billed, less refunds
    due). That is how a late dollar, a re-measure or a dispute in an already
    billed month is settled: once, on the next statement, never as a second
    record for the month it belongs to."""
    from . import hwm
    months = [m for m in months if m["month"] <= month]
    if not any(m["month"] == month for m in months):
        months.append({"month": month, "dollars": [], "disputed": []})
    for m in months:
        row = billed.get(m["month"])
        if m["month"] != month:
            m["collected"] = 1.0 if (row or {}).get("status") in SETTLED else 0.0
    statements = hwm.run(shop, months, cap_usd=cap_usd)
    by = {s["month"]: s for s in statements}
    settled = [k for k, r in billed.items() if k < month and r.get("status") in SETTLED and k in by]
    owed_before = sum(by[k]["net"] for k in settled)
    paid_before = sum(_f(billed[k], "billed_usd") - _f(billed[k], "refund_due_usd") for k in settled)
    adjustment = round(owed_before - paid_before, 2)
    cur = by[month]
    charge = round(cur["net"] + adjustment, 2)
    last = max(settled) if settled else None
    explanation = list(cur["explanation"])
    if abs(adjustment) >= 0.005:
        explanation.append(f"Adjustment for months already billed: {'+' if adjustment > 0 else '-'}"
                           f"${abs(adjustment):,.2f} (a dollar that landed late, a re-measure or a dispute "
                           f"changed what they owe; each month is billed once, so the difference is settled here).")
    if last and abs(_f(billed[last], "peak_usd") - cur["peak_before"]) >= 0.005:
        explanation.append(f"The high-water mark was ${_f(billed[last], 'peak_usd'):,.2f} when {last} was billed; "
                           f"on the Record as it stands now it is ${cur['peak_before']:,.2f}.")
    return statements, {**cur, "adjustment": adjustment, "charge": charge,
                        "peak_billed_before": _f(billed.get(last), "peak_usd") if last else 0.0,
                        "explanation": explanation}


def _persist(db, shop: str, st: dict, res: dict, line: str | None, now: datetime) -> dict:
    from . import usage
    status = res["status"]
    if status == "nothing_to_bill" and res.get("refund_due", 0) > 0:
        status = "refund_due"
    row = {"shop_domain": shop, "month": st["month"], "status": status,
           "fee_usd": st["fee"], "net_usd": st["net"], "adjustment_usd": st["adjustment"],
           "charge_usd": st["charge"],
           "billed_usd": res["amount"] if status == "sent" else 0.0,
           "refund_due_usd": res.get("refund_due") or 0.0,
           "peak_usd": st["peak_after"], "record_id": res.get("record_id"),
           "idempotency_key": usage.idempotency_key(st, line) if line else None,
           "errors": res.get("errors") or None, "updated_at": now.isoformat()}
    db.table(FEE_MONTHS).upsert(row, on_conflict="shop_domain,month").execute()
    return row


def cmd_meter(db, args) -> int:
    from . import hwm, usage  # lazy: built beside this module
    from .db import fetch_all
    today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
    month = closed_month(today)
    failures = 0
    for s in stores(db, args):
        row = s["row"] or {}
        if row.get("mode", "shadow") != "live" and not args.include_shadow:
            print(f"  {s['shop']}: shadow mode, nothing is metered")
            continue
        if not s["client_id"]:
            print(f"  skip {s['shop']}: no client_id", file=sys.stderr)
            continue
        directives = fetch_all(db, "directives", s["client_id"])
        costed = costed_skus(fetch_all(db, "cogs_inputs", s["client_id"]))
        no_cost = [u for u in uncosted(directives, costed) if u["month"] <= month]
        months = months_of(directives, load_disputes(db, s["shop"]), costed=costed)
        billed = load_billed(db, s["shop"])
        if not [m for m in months if m["month"] <= month] and not billed and not no_cost:
            print(f"  {s['shop']}: no measured dollars, nothing to bill")
            continue
        statements, st = settle(s["shop"], months, billed, month,
                                cap_usd=float(row.get("cap_usd") or hwm.DEFAULT_CAP_USD))
        # Only a brand that said yes (and approved the charge on Shopify) is
        # billed. Read before this run opens the question, so the run that
        # opens it never bills.
        ok, why = meter_gate.billable(row, datetime(today.year, today.month, today.day, tzinfo=UTC))
        st = {**st, "billed": ok, "not_billed": why,
              "explanation": st["explanation"] + [f"{u['sku']}: ${u['usd']:,.2f} measured in {u['month']}, "
                                                  f"{NO_COST}." for u in no_cost]}
        _put(db, f"shopify/{s['shop']}/fee.json", {
            "label": "proven", "month": month, "statements": statements, "closing": st,
            "not_billed_no_cost": no_cost,
            "billed": {k: {"status": r.get("status"), "billed_usd": _f(r, "billed_usd"),
                           "refund_due_usd": _f(r, "refund_due_usd"), "peak_usd": _f(r, "peak_usd")}
                       for k, r in sorted(billed.items())}})
        if meter_gate.mark_ask(db, s["shop"], row, statements):
            print(f"  {s['shop']}: first proven dollar banked; the fee question is now open")
        if not ok:
            print(f"  {s['shop']}: {month} fee {st['charge']:.2f} would be due; {why}")
            continue
        done = billed.get(month)
        if done and done.get("status") not in ("error",):
            # Billed (or refused as capped) already: never a second record for
            # the month. Anything that changed rides on next month's adjustment.
            print(f"  {s['shop']}: {month} already {done.get('status')}, nothing sent")
            continue
        if not args.send:
            print(f"  {s['shop']}: dry run, {month} charge {st['charge']:.2f} "
                  f"(net {st['net']:.2f}, adjustment {st['adjustment']:.2f})")
            continue
        line = row.get("usage_line_item_id")
        res = usage.send(st, shopify_api.http_transport(s["shop"], s["token"]), line)
        saved = _persist(db, s["shop"], st, res, line, datetime.now(UTC))
        settled = {**billed, month: saved}
        db.table(SHOPS).update({
            "peak_usd": st["peak_after"],
            "billed_usd": round(max(0.0, sum(_f(r, "billed_usd") - _f(r, "refund_due_usd")
                                             for r in settled.values() if r.get("status") in SETTLED)), 2),
        }).eq("shop_domain", s["shop"]).execute()
        print(f"  {s['shop']}: {month} {saved['status']} {res.get('amount')}"
              + (f", {res['refund_due']:.2f} due back to the brand" if res.get("refund_due") else ""))
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
