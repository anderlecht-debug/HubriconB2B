"""Payments > Transaction View date-range export -> settlement_transactions.
One line per settlement event with Amazon's fee decomposition. Timestamps
keep the wall-clock Amazon prints ("Jul 1, 2026 3:12:44 AM PDT" ->
2026-07-01T03:12:44, zone dropped, not converted); txn_date is the date
part the models key on. The channel leads the row_key hash (2026-09-04) so
a Shopify Payments line can never collide with an Amazon settlement line
for the same client."""

import pandas as pd

from .headers import as_int, clean_int, clean_money, clean_str, dedupe_last, map_columns, row_key, to_iso_datetime

SPEC = {
    "txn_datetime": {"synonyms": ["datetime", "date", "posteddate", "postedate"], "required": True, "cleaner": clean_str},
    "settlement_id": {"synonyms": ["settlementid"], "cleaner": clean_str},
    "txn_type": {"synonyms": ["type", "transactiontype"], "required": True, "cleaner": clean_str},
    "order_id": {"synonyms": ["orderid", "amazonorderid"], "cleaner": clean_str},
    "sku": {"synonyms": ["sku", "msku", "sellersku"], "cleaner": clean_str},
    "description": {"synonyms": ["description"], "cleaner": clean_str},
    "quantity": {"synonyms": ["quantity", "qty"], "cleaner": clean_int},
    "marketplace": {"synonyms": ["marketplace"], "cleaner": clean_str},
    "account_type": {"synonyms": ["accounttype"], "cleaner": clean_str},
    "fulfillment": {"synonyms": ["fulfillment", "fulfilment"], "cleaner": clean_str},
    "product_sales": {"synonyms": ["productsales"], "cleaner": clean_money},
    "product_sales_tax": {"synonyms": ["productsalestax"], "cleaner": clean_money},
    "shipping_credits": {"synonyms": ["shippingcredits"], "cleaner": clean_money},
    "shipping_credits_tax": {"synonyms": ["shippingcreditstax"], "cleaner": clean_money},
    "gift_wrap_credits": {"synonyms": ["giftwrapcredits"], "cleaner": clean_money},
    "gift_wrap_credits_tax": {"synonyms": ["giftwrapcreditstax"], "cleaner": clean_money},
    "regulatory_fee": {"synonyms": ["regulatoryfee"], "cleaner": clean_money},
    "tax_on_regulatory_fee": {"synonyms": ["taxonregulatoryfee"], "cleaner": clean_money},
    "promotional_rebates": {"synonyms": ["promotionalrebates"], "cleaner": clean_money},
    "promotional_rebates_tax": {"synonyms": ["promotionalrebatestax"], "cleaner": clean_money},
    "marketplace_withheld_tax": {"synonyms": ["marketplacewithheldtax"], "cleaner": clean_money},
    "selling_fees": {"synonyms": ["sellingfees"], "cleaner": clean_money},
    "fba_fees": {"synonyms": ["fbafees"], "cleaner": clean_money},
    "other_transaction_fees": {"synonyms": ["othertransactionfees"], "cleaner": clean_money},
    "other": {"synonyms": ["other"], "cleaner": clean_money},
    "total": {"synonyms": ["total"], "required": True, "cleaner": clean_money},
}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        txn_datetime = to_iso_datetime(record["txn_datetime"])
        if not txn_datetime or not record["txn_type"] or record["total"] is None:
            continue
        quantity = as_int(record["quantity"])
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": "amazon",
                "row_key": row_key(
                    "amazon", txn_datetime, record["settlement_id"], record["txn_type"], record["order_id"],
                    record["sku"], record["description"], quantity, record["total"],
                ),
                "txn_datetime": txn_datetime,
                "txn_date": txn_datetime[:10],
                "quantity": quantity,
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("row_key",))
    return "settlement_transactions", rows, "client_id,row_key"
