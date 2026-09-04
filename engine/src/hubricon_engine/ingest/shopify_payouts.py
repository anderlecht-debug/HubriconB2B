"""Shopify Payments transactions export -> settlement_transactions (channel
shopify). Shopify Admin > Finances > Payouts > Transactions > Export: one
line per charge, refund, adjustment or chargeback with the fee Shopify
took and the net that reached the payout.

Conventions match the Amazon settlement rows the models already read:
fees are stored negative (Shopify prints them positive), a charge's
Amount is product_sales and every other type's Amount is `other`, total is
the Net that moved, and settlement_id is the Payout Date so a payout
reconciles the way an Amazon settlement id does. Timestamps keep the
wall-clock Shopify prints ("2026-07-20 10:15:22 -0400" -> 2026-07-20T10:15:22,
offset dropped, not converted). The channel leads the row_key hash so a
Shopify line can never collide with an Amazon line for the same client.
"""

import pandas as pd

from .headers import clean_money, clean_str, dedupe_last, map_columns, row_key, to_iso_date, to_iso_datetime

SPEC = {
    "txn_datetime": {"synonyms": ["transactiondate", "date", "datetime"], "required": True, "cleaner": clean_str},
    "txn_type": {"synonyms": ["type", "transactiontype"], "required": True, "cleaner": clean_str},
    "order_id": {"synonyms": ["order", "ordername", "orderid"], "cleaner": clean_str},
    "payout_date": {"synonyms": ["payoutdate"], "cleaner": clean_str},
    "payout_status": {"synonyms": ["payoutstatus"], "cleaner": clean_str},
    "amount": {"synonyms": ["amount"], "cleaner": clean_money},
    "fee": {"synonyms": ["fee", "fees"], "cleaner": clean_money},
    "net": {"synonyms": ["net"], "required": True, "cleaner": clean_money},
    "payment_method": {"synonyms": ["paymentmethodname", "paymentmethod"], "cleaner": clean_str},
    "currency": {"synonyms": ["currency"], "cleaner": clean_str},
}
CHANNEL = "shopify"


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        txn_datetime = to_iso_datetime(record["txn_datetime"])
        txn_type = record["txn_type"]
        if not txn_datetime or not txn_type or record["net"] is None:
            continue
        payout_date = to_iso_date(record["payout_date"])
        is_charge = txn_type.strip().lower() == "charge"
        fee = record["fee"]
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": CHANNEL,
                "row_key": row_key(
                    CHANNEL, txn_datetime, payout_date, txn_type, record["order_id"],
                    record["amount"], fee, record["net"],
                ),
                "txn_datetime": txn_datetime,
                "txn_date": txn_datetime[:10],
                "settlement_id": payout_date,
                "txn_type": txn_type,
                "order_id": record["order_id"],
                "sku": None,
                "description": " · ".join(p for p in (txn_type, record["payment_method"]) if p),
                "quantity": None,
                "marketplace": CHANNEL,
                "product_sales": record["amount"] if is_charge else None,
                "other": None if is_charge else record["amount"],
                "selling_fees": None if fee is None else (-abs(fee) or 0.0),
                "total": record["net"],
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("row_key",))
    return "settlement_transactions", rows, "client_id,row_key"
