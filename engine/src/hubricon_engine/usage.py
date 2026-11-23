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
    appUsageRecord { id price { amount } }
    userErrors { field message }
  }
}"""

# Words Shopify uses when a charge would pass the merchant's capped amount.
CAP_ERROR_MARKERS = ("capped amount", "balance remaining", "exceeds the balance", "exceeds balance")


def idempotency_key(statement: dict, subscription_line_item_id: str | None = None) -> str:
    """sha256(shop|month|line item): one key per month per subscription line,
    whatever the statement's numbers. A retry, or a re-run on numbers that have
    since changed, sends the same key, so Shopify returns the record it already
    made and the month is charged once. A later correction is never a second
    record for the month: it rides on the next month's statement as an
    adjustment (shopify_run.cmd_meter)."""
    line = subscription_line_item_id or statement.get("subscription_line_item_id") or ""
    raw = f"{statement['shop']}|{statement['month']}|{line}"
    return hashlib.sha256(raw.encode()).hexdigest()[:IDEMPOTENCY_KEY_MAX]


def _owed(statement: dict) -> float:
    """What the month settles: `charge` (the meter's net of the month and any
    adjustment) when given, else the statement's net fee."""
    for k in ("charge", "net", "fee"):
        if statement.get(k) is not None:
            return float(statement[k])
    return 0.0


def amount(statement: dict) -> float:
    """What this record charges: never below zero."""
    return round(max(0.0, _owed(statement)), 2)


def description(statement: dict) -> str:
    parts = [f"Hubricon {statement['month']}: share of new proven profit"]
    if statement.get("capped"):
        parts.append("capped")
    if float(statement.get("refunds") or 0) > 0:
        parts.append(f"after ${float(statement['refunds']):,.2f} refunded for disputes")
    adj = float(statement.get("adjustment") or 0)
    if abs(adj) >= 0.005:
        parts.append(f"{'+' if adj > 0 else '-'}${abs(adj):,.2f} adjustment for earlier months")
    return ", ".join(parts)[:DESCRIPTION_MAX]


def payload(statement: dict, subscription_line_item_id: str) -> dict:
    """The mutation text and its variables, ready for the Admin GraphQL API."""
    return {
        "query": MUTATION,
        "variables": {
            "subscriptionLineItemId": subscription_line_item_id,
            "price": {"amount": f"{amount(statement):.2f}", "currencyCode": CURRENCY},
            "description": description(statement),
            "idempotencyKey": idempotency_key(statement, subscription_line_item_id),
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
    due_back = round(max(0.0, -_owed(statement)), 2)
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
        rec = body["appUsageRecord"]
        out["status"], out["record_id"] = "sent", rec["id"]
        # The record Shopify holds (on a repeated key, the one it made first).
        price = (rec.get("price") or {}).get("amount")
        if price is not None:
            out["amount"] = round(float(price), 2)
    return out
