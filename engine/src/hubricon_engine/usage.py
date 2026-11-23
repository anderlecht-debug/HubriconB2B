"""A month's statement, sent to Shopify as one usage record.

hwm.py decides what a month costs. This module only says it to Shopify: the
appUsageRecordCreate mutation on the merchant's usage-based subscription line,
priced at the statement's net fee. Shopify enforces the merchant's capped
amount itself; when it refuses because that cap is reached, the month is
recorded "capped" and nothing is owed (hwm.py's rule: the excess is never a debt).

No network here. `send` takes a transport, a callable (query, variables) ->
the GraphQL response as a dict, so tests pass a double and the app passes the
authenticated Admin API client.

Refunds: a usage record cannot be negative. When a month's refunds exceed its
fee, no record is sent and the result says how much is due back to the brand;
the operator issues it (Shopify refunds app charges from the Partner Dashboard).
"""

import hashlib
import json

CURRENCY = "USD"
IDEMPOTENCY_KEY_MAX = 255    # Shopify's limit on appUsageRecordCreate's idempotencyKey
DESCRIPTION_MAX = 255        # kept short; the full statement lives on the Record

MUTATION = """mutation appUsageRecordCreate(
  $subscriptionLineItemId: ID!
  $price: MoneyInput!
  $description: String!
  $idempotencyKey: String
) {
  appUsageRecordCreate(
    subscriptionLineItemId: $subscriptionLineItemId
    price: $price
    description: $description
    idempotencyKey: $idempotencyKey
  ) {
    appUsageRecord { id }
    userErrors { field message }
  }
}"""

# Words Shopify uses when a charge would pass the merchant's capped amount.
CAP_ERROR_MARKERS = ("capped amount", "balance remaining", "exceeds the balance", "exceeds balance")


def digest(statement: dict) -> str:
    """sha256 of the statement's own numbers, canonical JSON, so the same
    statement always gives the same key and a changed one never reuses it."""
    body = json.dumps(statement, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def idempotency_key(statement: dict) -> str:
    """sha256(shop|month|statement digest): a retry of the same month sends the
    same key, so Shopify charges it once however many times we try."""
    raw = f"{statement['shop']}|{statement['month']}|{digest(statement)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:IDEMPOTENCY_KEY_MAX]


def amount(statement: dict) -> float:
    """What this record charges: the net fee, never below zero."""
    return round(max(0.0, float(statement.get("net", statement.get("fee", 0.0)))), 2)


def description(statement: dict) -> str:
    parts = [f"Hubricon {statement['month']}: share of new proven profit"]
    if statement.get("capped"):
        parts.append("capped")
    if float(statement.get("refunds") or 0) > 0:
        parts.append(f"after ${float(statement['refunds']):,.2f} refunded for disputes")
    return ", ".join(parts)[:DESCRIPTION_MAX]


def payload(statement: dict, subscription_line_item_id: str) -> dict:
    """The mutation text and its variables, ready for the Admin GraphQL API."""
    return {
        "query": MUTATION,
        "variables": {
            "subscriptionLineItemId": subscription_line_item_id,
            "price": {"amount": f"{amount(statement):.2f}", "currencyCode": CURRENCY},
            "description": description(statement),
            "idempotencyKey": idempotency_key(statement),
        },
    }


def _is_cap_error(message: str) -> bool:
    m = (message or "").lower()
    return any(k in m for k in CAP_ERROR_MARKERS)


def send(statement: dict, transport, subscription_line_item_id: str | None = None) -> dict:
    """Send one month. Returns {"status", "record_id", "amount", "refund_due",
    "errors", "payload"}; status is one of:

      sent             Shopify created the usage record
      nothing_to_bill  the net fee is zero (no record is sent)
      capped           Shopify refused: the merchant's capped amount is reached
      error            anything else; nothing was charged, retry is safe
    """
    line = subscription_line_item_id or statement.get("subscription_line_item_id")
    due_back = round(max(0.0, -float(statement.get("net", 0.0))), 2)
    out = {"status": None, "record_id": None, "amount": amount(statement),
           "refund_due": due_back, "errors": [], "payload": None}
    if out["amount"] <= 0:
        out["status"] = "nothing_to_bill"
        return out
    if not line:
        raise ValueError("a subscription line item id is required to send a usage record")
    p = payload(statement, line)
    out["payload"] = p
    try:
        res = transport(p["query"], p["variables"]) or {}
    except Exception as err:   # the transport's own failure: nothing was charged
        out["status"], out["errors"] = "error", [str(err)]
        return out

    top = res.get("errors") or []
    body = ((res.get("data") or {}).get("appUsageRecordCreate") or {})
    user = body.get("userErrors") or []
    messages = [str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in top + user]
    if any(_is_cap_error(msg) for msg in messages):
        out["status"], out["errors"] = "capped", messages
    elif messages or not (body.get("appUsageRecord") or {}).get("id"):
        out["status"], out["errors"] = "error", messages or ["no usage record returned"]
    else:
        out["status"], out["record_id"] = "sent", body["appUsageRecord"]["id"]
    return out
