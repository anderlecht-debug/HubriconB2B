"""The brand's own limits on what Hubricon may do unasked, and the price steps
that run inside them.

BUILD_PLAN M6: "Price steps within the merchant's limits." The brand sets its
limits once, in the app (api/shopify/app.js writes shopify_mandates):

  max_price_step_pct   the largest single price step that may run unasked,
                       in percent of the live price (at most 5: terms.html §6)
  price_moves_enabled  off by default: nothing is priced until the brand says so
  reorder_needs_tap    on by default; the app cannot place a purchase order in
                       any case, so a reorder always waits for the brand's tap
  shadow_weeks         weeks of shadow mode after install (default 4), during
                       which every call is sealed and nothing executes

sort() splits the engine's drafted moves (directives.draft_directives) three
ways and says why for each one:

  execute       a price step inside every limit, after shadow mode, with the
                write_products scope granted
  awaiting_tap  anything outside the limits: a larger step, a step the
                downside guard sent to the explicit mandate, any reorder, any
                kind the app has no way to carry out
  shadow        inside the limits, but shadow mode has not ended: it stays a
                sealed call (shadow.py), never a write

execute() carries out the `execute` list. For each move, in this order:

  1. Check it again against the limits (sort() may be stale).
  2. Check the variant's live price is still the price the move was sized on.
     If the brand or anyone else moved it since, the move is refused: the
     promise was made about a price that no longer exists.
  3. Seal the move with seal.seal_called. A move that is not on the chain
     after this step is never written to the store.
  4. Write the price with productVariantsBulkUpdate (an injected transport, as
     usage.py and shopify_api.py take; tests pass a double).
  5. Record it as a directives row (status 'done', executed_at, the Shopify
     reference) so measurement.measure grades it like every price step. A
     write Shopify refused is recorded 'closed' with the reason, so the
     sealed call has an honest answer on the Record.

Nothing here runs without a transport, and the transport needs a token granted
write_products, which lib/shopify.js asks for only when the brand opts in
(WRITE_SCOPES; the default install stays read-only).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from . import seal as sealmod
from .models.common import num

TABLE = "shopify_mandates"
DEFAULT_MAX_STEP_PCT = 5.0
TERMS_MAX_STEP_PCT = 5.0          # terms.html §6: the standing mandate's ceiling
DEFAULT_SHADOW_WEEKS = 4
WRITE_SCOPE = "write_products"
PRICE_KINDS = {"price_step"}      # the kinds this module can execute: one variant, one new price
REORDER_WORDS = ("reorder", "order_set", "expedite", "purchase")
LIVE_PRICE_TOLERANCE = 0.005      # half a cent: the live price must still be the one the move was sized on
NAMESPACE = uuid.UUID("0b8f0f55-5b0e-4c0e-8f3c-6c1d2e3f4a5b")
EXECUTED_BY = "hubricon:brand_limits"

EXECUTE, AWAITING_TAP, SHADOW = "execute", "awaiting_tap", "shadow"

MUTATION = """mutation HubriconPriceStep($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price }
    userErrors { field message }
  }
}"""


# ── the limits ───────────────────────────────────────────────────────────────

def settings(row: dict | None) -> dict:
    """The shop's mandate row with every default filled in, and the step cap
    clamped to what the terms allow (a row can only narrow it)."""
    row = row or {}
    pct = row.get("max_price_step_pct")
    pct = DEFAULT_MAX_STEP_PCT if pct is None else float(pct)
    return {
        "max_price_step_pct": max(0.0, min(pct, TERMS_MAX_STEP_PCT)),
        "price_moves_enabled": bool(row.get("price_moves_enabled", False)),
        "reorder_needs_tap": bool(row.get("reorder_needs_tap", True)),
        "shadow_weeks": int(row.get("shadow_weeks") or DEFAULT_SHADOW_WEEKS),
    }


def load(db, shop: str) -> dict:
    rows = db.table(TABLE).select("*").eq("shop_domain", shop).execute().data or []
    return settings(rows[0] if rows else None)


def _day(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def shadow_ends(installed_at, limits: dict) -> date | None:
    start = _day(installed_at)
    return None if start is None else start + timedelta(weeks=limits["shadow_weeks"])


def in_shadow(installed_at, limits: dict, today: date) -> bool:
    """True until shadow_weeks have passed since install. An unknown install
    date is shadow: the bias is toward doing nothing."""
    end = shadow_ends(installed_at, limits)
    return end is None or today < end


def has_write(scopes) -> bool:
    return WRITE_SCOPE in {s.strip() for s in str(scopes or "").split(",")}


def step_pct(move: dict) -> float | None:
    ev = move.get("evidence") or {}
    p0, p1 = ev.get("p0"), ev.get("p_new")
    if not p0 or p1 is None:
        return None
    return abs(float(p1) / float(p0) - 1.0) * 100.0


def _is_reorder(kind: str) -> bool:
    return any(w in (kind or "") for w in REORDER_WORDS)


def verdict(move: dict, limits: dict, *, shadow: bool, write: bool) -> tuple[str, str]:
    """(where the move goes, why), for one drafted move."""
    kind = str(move.get("kind") or "")
    if _is_reorder(kind):
        return AWAITING_TAP, ("a reorder always waits for your tap" if limits["reorder_needs_tap"]
                              else "the app cannot place a purchase order, so a reorder waits for your tap")
    if kind not in PRICE_KINDS:
        return AWAITING_TAP, f"{kind or 'this move'} is not a price step, the only move the app may run unasked"
    if move.get("mandate") != "standing":
        return AWAITING_TAP, move.get("mandate_reason") or "the engine marked it as needing your explicit yes"
    if not limits["price_moves_enabled"]:
        return AWAITING_TAP, "price moves are off in your limits"
    pct = step_pct(move)
    if pct is None or move.get("expected_impact_usd") is None:
        return AWAITING_TAP, "the step has no sized price or no stated expected dollars"
    p0 = float((move.get("evidence") or {})["p0"])
    slack = 0.005 / p0 * 100.0 if p0 else 0.0          # the cent rounding directives.py also allows
    if pct > limits["max_price_step_pct"] + slack + 1e-9:
        return AWAITING_TAP, f"a {pct:.1f}% step is larger than your {limits['max_price_step_pct']:g}% limit"
    if shadow:
        return SHADOW, "inside your limits, but shadow mode has not ended: sealed, not executed"
    if not write:
        return AWAITING_TAP, "inside your limits, but the app has not been granted write access to prices"
    return EXECUTE, f"a {pct:.1f}% step, inside your {limits['max_price_step_pct']:g}% limit"


def sort(drafts: list[dict], limits: dict, *, installed_at, today: date, scopes=None) -> dict:
    """{execute, awaiting_tap, shadow}: each a list of the drafts, each draft
    carrying `mandate_verdict` and `mandate_why`. Pure."""
    shadow = in_shadow(installed_at, limits, today)
    write = has_write(scopes)
    out = {EXECUTE: [], AWAITING_TAP: [], SHADOW: []}
    for d in drafts:
        where, why = verdict(d, limits, shadow=shadow, write=write)
        out[where].append({**d, "mandate_verdict": where, "mandate_why": why})
    return out


# ── carrying out a step ──────────────────────────────────────────────────────

def variant_index(product_lines: list[dict]) -> dict[str, dict]:
    """{sku: {variant_id, product_id, price}} from the Bulk Operations product
    lines shopify_api.pull returns (a variant line carries __parentId)."""
    out = {}
    for line in product_lines or []:
        if "ProductVariant/" not in str(line.get("id")) or not line.get("sku"):
            continue
        out[str(line["sku"])] = {"variant_id": line["id"], "product_id": line.get("__parentId"),
                                 "price": None if line.get("price") is None else float(line["price"])}
    return out


def move_id(client_id: str, move: dict, today: date) -> str:
    """One id per move per day, so a re-run the same day never seals or writes twice."""
    subject = move.get("dedupe_key") or (move.get("evidence") or {}).get("sku")
    return str(uuid.uuid5(NAMESPACE, f"{client_id}|{today.isoformat()}|{subject}"))


def _directive(move: dict, client_id: str, variant: dict, today: date, now: str) -> dict:
    ev = move.get("evidence") or {}
    return {
        "id": move_id(client_id, move, today),
        "client_id": client_id,
        "channel": "shopify",
        "module": "pricing",
        "kind": move.get("kind"),
        "status": "issued",
        "mandate": "standing",
        "issued_at": now,
        "expected_impact_usd": move.get("expected_impact_usd"),
        "action_text": move.get("action_text"),
        "dedupe_key": move.get("dedupe_key"),
        "evidence": {**ev, "variant_id": variant["variant_id"], "product_id": variant["product_id"],
                     "brand_limit_pct": move.get("brand_limit_pct"), "executed": True,
                     "executed_under": "brand_limits"},
    }


def _write(transport, variant: dict, price: float) -> tuple[bool, str]:
    try:
        resp = transport(MUTATION, {"productId": variant["product_id"],
                                    "variants": [{"id": variant["variant_id"], "price": f"{price:.2f}"}]})
    except Exception as err:      # a failed write is a recorded failure, never a crash
        return False, f"{type(err).__name__}: {str(err)[:200]}"
    body = (resp or {}).get("data", resp) or {}
    out = body.get("productVariantsBulkUpdate") or {}
    errors = out.get("userErrors") or (resp or {}).get("errors") or []
    if errors:
        return False, "; ".join(str(e.get("message", e)) for e in errors)[:300]
    got = next((v for v in out.get("productVariants") or [] if v.get("id") == variant["variant_id"]), None)
    if not got or abs(float(got.get("price") or 0) - price) > LIVE_PRICE_TOLERANCE:
        return False, "Shopify did not return the new price"
    return True, got["id"]


def execute(db, client_id: str, moves: list[dict], limits: dict, variants: dict[str, dict], transport,
            *, installed_at, today: date, scopes, now=None) -> list[dict]:
    """Carry out the moves inside the limits. One result per move:
    {id, sku, status: executed | refused | failed, why, seal}. Writes nothing
    for a move that is refused or that the Seal did not take."""
    now = sealmod.stamp(now or datetime.now(UTC))
    shadow, write = in_shadow(installed_at, limits, today), has_write(scopes)
    results = []
    for move in moves:
        sku = (move.get("evidence") or {}).get("sku")
        res = {"sku": sku, "id": move_id(client_id, move, today)}
        where, why = verdict(move, limits, shadow=shadow, write=write)
        if where != EXECUTE:
            results.append({**res, "status": "refused", "why": why})
            continue
        variant = variants.get(str(sku))
        ev = move["evidence"]
        if not variant or not variant.get("product_id"):
            results.append({**res, "status": "refused", "why": "no live variant for this SKU"})
            continue
        if variant["price"] is None or abs(variant["price"] - float(ev["p0"])) > LIVE_PRICE_TOLERANCE:
            results.append({**res, "status": "refused",
                            "why": f"the live price is {variant['price']}, not the {ev['p0']} the move was sized on"})
            continue
        d = _directive({**move, "brand_limit_pct": limits["max_price_step_pct"]}, client_id, variant, today, now)
        sealed = sealmod.seal_called(db, client_id, [d], sealed_at=now)
        if d["id"] not in (sealed.get("short") or {}):
            results.append({**res, "status": "refused", "why": f"not sealed ({sealed.get('status')}): "
                            f"{sealed.get('reason') or 'no seal'}; nothing written", "seal": sealed.get("status")})
            continue
        price = round(float(ev["p_new"]), 2)
        ok, ref = _write(transport, variant, price)
        row = {**d, "status": "done" if ok else "closed",
               "executed_at": now if ok else None,
               "executed_by": EXECUTED_BY if ok else None,
               "execution_ref": ref if ok else None,
               "measurement_notes": None if ok else f"The price write failed and nothing changed: {ref}"}
        db.table("directives").upsert(row, on_conflict="id").execute()
        results.append({**res, "status": "executed" if ok else "failed", "why": ref,
                        "seal": sealed["short"][d["id"]], "price_from": num(ev["p0"]), "price_to": price})
    return results
