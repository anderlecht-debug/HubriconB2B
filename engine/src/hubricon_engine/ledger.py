"""The ledger of anyone's moves: what the brand, its agency or anyone else did
to the store, seen in the data, sealed when seen, and graded where it can be.

BUILD_PLAN "What the agency gets: free sealed grading of its own moves (item
5)." Hubricon's own moves are sealed before they run (mandate.py, shadow.py).
Everybody else's moves are not announced to us, so they are detected: each
nightly ingest keeps a snapshot of every variant (price, stock, its product's
status) and compares it with the last one.

  observed_price_change   a variant's price moved between two snapshots, and
                          not by a step Hubricon executed
  observed_archive        a product left ACTIVE (archived, drafted or deleted)
  observed_receipt        a variant's stock rose by at least RECEIPT_MIN_UNITS
                          and RECEIPT_SHARE of what it held: a delivery landed
                          (sales only ever lower stock)

Each is sealed on the client's Record chain the night it is detected, through
seal.seal_called, as a directive-shaped entry (module "ledger", mandate
"observed", status "observed", evidence.executed False, evidence.ours False),
so the chain shows plainly it was seen, not called. The seal fixes WHEN we saw
it: a grade written later cannot pretend the move was chosen after the fact.

Grading. A price change is graded once MIN_AFTER_DAYS of orders have run at
the new price, with the look-back's own price-change measurement
(lookback._price_change: the SKU's fitted demand curve, or the two readings
its own numbers allow when none fits). Archives and receipts are listed, not
graded: there is no honest counterfactual for them in a store's own rows.

What a grade is NOT. A move someone else chose, when they chose, is not
randomised: its before/after carries whatever else changed that month. Every
grade says so (GRADE_LABEL). None of these dollars is ever Hubricon's: no
ledger entry is ever a directives row, so it can never reach the meter
(shopify_run.months_of skips them by name as well, and hwm.grade_of refuses
the label). Never billed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from . import seal as sealmod
from .lookback import _price_change, _safe, complete
from .models import elasticity, margin, shopify_findings
from .models.common import num

MODULE = "ledger"
MANDATE = "observed"
LABEL = "observed, not ours"
GRADE_LABEL = "observed, not ours: not randomised, a before/after on your own orders, never billed"
ATTRIBUTION = "observed_not_randomised"
PRICE_TOLERANCE = 0.005          # half a cent
RECEIPT_MIN_UNITS = 20
RECEIPT_SHARE = 0.5
MIN_AFTER_DAYS = 14              # measurement.MIN_AFTER_DAYS: a shorter window proves nothing
ACTIVE = "ACTIVE"
NAMESPACE = uuid.UUID("8e3b1d2a-7c55-4f0e-9a61-3b2c4d5e6f70")
KINDS = ("observed_price_change", "observed_archive", "observed_receipt")


# ── snapshots ────────────────────────────────────────────────────────────────

def snapshot(product_lines: list[dict], day: date) -> dict:
    """{day, variants: {variant_id: {sku, product_id, title, product_status,
    price, inventory}}} from the Bulk Operations product lines."""
    products = {l["id"]: l for l in product_lines or [] if "/Product/" in str(l.get("id"))}
    variants = {}
    for l in product_lines or []:
        if "ProductVariant/" not in str(l.get("id")):
            continue
        p = products.get(l.get("__parentId")) or {}
        variants[l["id"]] = {
            "sku": l.get("sku") or None, "product_id": l.get("__parentId"), "title": p.get("title"),
            "product_status": (p.get("status") or "").upper() or None,
            "price": None if l.get("price") is None else float(l["price"]),
            "inventory": None if l.get("inventoryQuantity") is None else int(l["inventoryQuantity"]),
        }
    return {"day": day.isoformat(), "variants": variants}


def entry_id(client_id: str, kind: str, subject: str, day: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{client_id}|{kind}|{subject}|{day}"))


def _entry(client_id, kind, subject, text, evidence, prev_day, day, detected_at) -> dict:
    return {
        "id": entry_id(client_id, kind, subject, day),
        "client_id": client_id,
        "channel": "shopify",
        "module": MODULE,
        "kind": kind,
        "status": "observed",
        "mandate": MANDATE,
        "issued_at": detected_at,
        "expected_impact_usd": None,
        "label": LABEL,
        "action_text": f"Observed, not ours: {text}",
        "dedupe_key": f"{MODULE}:{kind}:{subject}:{day}",
        "evidence": {**evidence, "executed": False, "ours": False, "seen_between": [prev_day, day]},
    }


def detect(prev: dict | None, cur: dict, client_id: str, ours: set | None = None, detected_at=None) -> list[dict]:
    """Moves between two snapshots. `ours` is {(variant_id, new price)} that
    Hubricon itself executed in between; those are left out. Pure."""
    if not prev:
        return []
    detected_at = sealmod.stamp(detected_at or datetime.now(UTC))
    ours = {(v, round(float(p), 2)) for v, p in (ours or set())}
    a, b, d0, d1 = prev["variants"], cur["variants"], prev["day"], cur["day"]
    out = []
    for vid, now in sorted(b.items()):
        was = a.get(vid)
        if not was:
            continue
        name = now.get("sku") or vid
        if (was["price"] is not None and now["price"] is not None
                and abs(now["price"] - was["price"]) > PRICE_TOLERANCE
                and (vid, round(now["price"], 2)) not in ours):
            pct = (now["price"] / was["price"] - 1) if was["price"] else None
            out.append(_entry(client_id, "observed_price_change", vid,
                              f"{name} moved ${was['price']:,.2f} → ${now['price']:,.2f} between {d0} and {d1}.",
                              {"sku": now.get("sku"), "variant_id": vid, "price_from": was["price"],
                               "price_to": now["price"], "step_pct": None if pct is None else num(pct * 100, 2)},
                              d0, d1, detected_at))
        if was["inventory"] is not None and now["inventory"] is not None:
            rise = now["inventory"] - was["inventory"]
            if rise >= RECEIPT_MIN_UNITS and rise >= RECEIPT_SHARE * max(was["inventory"], 1):
                out.append(_entry(client_id, "observed_receipt", vid,
                                  f"{name} stock rose {was['inventory']:,} → {now['inventory']:,} between {d0} and {d1}.",
                                  {"sku": now.get("sku"), "variant_id": vid, "units_from": was["inventory"],
                                   "units_to": now["inventory"], "units_received": rise}, d0, d1, detected_at))
    seen = set()
    for vid, was in sorted(a.items()):
        pid = was.get("product_id")
        if pid in seen or was.get("product_status") != ACTIVE:
            continue
        seen.add(pid)
        now_status = next((v.get("product_status") for v in b.values() if v.get("product_id") == pid), "REMOVED")
        if now_status != ACTIVE:
            skus = sorted({v["sku"] for v in a.values() if v.get("product_id") == pid and v.get("sku")})
            out.append(_entry(client_id, "observed_archive", pid,
                              f"{was.get('title') or pid} went from active to {now_status.lower()} between {d0} and {d1}.",
                              {"sku": skus[0] if len(skus) == 1 else None, "skus": skus, "product_id": pid,
                               "status_from": ACTIVE, "status_to": now_status}, d0, d1, detected_at))
    return out


def seal(db, client_id: str, entries: list[dict], sealed_at=None) -> dict:
    """Seal each entry the night it is seen. Never raises (seal.seal_called)."""
    return sealmod.seal_called(db, client_id, entries, sealed_at=sealed_at)


# ── grading ──────────────────────────────────────────────────────────────────

def grade_one(entry: dict, data: dict, today: date) -> dict:
    """One entry's grade: {id, kind, sku, graded, usd, usd_low, usd_high,
    label, basis}. Only price changes with MIN_AFTER_DAYS behind them are
    graded; everything else says why not."""
    ev = entry["evidence"]
    base = {"id": entry["id"], "kind": entry["kind"], "sku": ev.get("sku"), "label": GRADE_LABEL,
            "billed": False, "randomised": False, "graded": False, "usd": None, "usd_low": None, "usd_high": None}
    if entry["kind"] != "observed_price_change":
        return {**base, "basis": "listed, not graded: a store's own rows hold no honest counterfactual for it"}
    start, end = (date.fromisoformat(x) for x in ev["seen_between"])
    if (today - end).days < MIN_AFTER_DAYS:
        return {**base, "basis": f"not graded yet: under {MIN_AFTER_DAYS} days at the new price"}
    data = complete(data)
    sku = ev.get("sku")
    hist = shopify_findings.history(data).get(sku) or []
    econ = {str(r["period_start"])[:10]: r for r in data["sku_economics"] if r.get("sku") == sku}
    before = [h for h in hist if str(econ[h["day"].isoformat()]["period_end"])[:10] < start.isoformat()]
    after = [h for h in hist if h["day"] >= end]
    if not before or not after:
        return {**base, "basis": "not graded: no sales on one side of the change"}
    margins = _safe(margin.run, data, default=[])
    fits = _safe(elasticity.run, data, default=[])
    fit = next((f for f in fits if f.get("level") == "sku" and f.get("item_id") == sku
                and f.get("status") == "ok" and f.get("elasticity") is not None), None)
    item = _price_change(sku, before, after, econ, margins, fit)
    if item["usd"] is None:
        return {**base, "basis": item["basis"]}
    return {**base, "graded": True, "usd": item["usd"], "usd_low": item["usd_low"], "usd_high": item["usd_high"],
            "basis": item["basis"], "price_from": item["price_from"], "price_to": item["price_to"],
            "days_after": item["days_after"]}


def grade(entries: list[dict], data: dict, today: date, db=None, client_id: str | None = None,
          measured_at=None) -> list[dict]:
    """Grade every entry; with a database, seal each graded one's measured entry
    beside its observed one, labelled observed and not randomised."""
    grades = [grade_one(e, data, today) for e in entries]
    if db is not None and client_id:
        when = sealmod.stamp(measured_at or datetime.now(UTC))
        by_id = {e["id"]: e for e in entries}
        measured = [{**by_id[g["id"]], "status": "measured", "attribution": ATTRIBUTION,
                     "measured_impact_usd": g["usd"], "measured_at": when,
                     "evidence": {**by_id[g["id"]]["evidence"],
                                  "after": {k: g[k] for k in ("usd", "usd_low", "usd_high", "label", "basis")}}}
                    for g in grades if g["graded"]]
        if measured:
            sealmod.seal_measured(db, client_id, measured, sealed_at=when)
    return grades


def summary(entries: list[dict], grades: list[dict]) -> dict:
    """The app page's ledger block."""
    by = {g["id"]: g for g in grades}
    return {"label": LABEL, "grade_label": GRADE_LABEL,
            "note": ("Moves we saw in your store that Hubricon did not make, sealed the night we saw them. "
                     "Not randomised and never billed."),
            "entries": [{"id": e["id"], "kind": e["kind"], "text": e["action_text"],
                         "seen_between": e["evidence"]["seen_between"], "grade": by.get(e["id"])}
                        for e in entries]}
