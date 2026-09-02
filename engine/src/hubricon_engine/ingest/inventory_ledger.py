"""Inventory Ledger detail report -> inventory_ledger. Also accepts the older
Inventory Adjustments export, which has no Event Type column: those rows are
Adjustments by definition, reference_id comes from transaction-item-id and
unreconciled_qty from 'unreconciled'. Both layouts hash to the same row_key
for the same event, so a client can send either without double counting."""

import pandas as pd

from .headers import as_int, clean_int, clean_str, dedupe_last, map_columns, row_key, to_iso_date

SPEC = {
    "event_date": {"synonyms": ["date", "adjusteddate", "eventdate", "transactiondate"], "required": True, "cleaner": clean_str},
    "event_type": {"synonyms": ["eventtype", "transactiontype"], "cleaner": clean_str},
    "reference_id": {"synonyms": ["referenceid", "transactionitemid", "referencenumber"], "cleaner": clean_str},
    "fnsku": {"synonyms": ["fnsku"], "cleaner": clean_str},
    "asin": {"synonyms": ["asin"], "cleaner": clean_str},
    "sku": {"synonyms": ["msku", "sku", "sellersku", "merchantsku"], "cleaner": clean_str},
    "title": {"synonyms": ["title", "productname", "itemname"], "cleaner": clean_str},
    "fulfillment_center": {
        "synonyms": ["fulfillmentcenter", "fulfillmentcenterid", "warehouse", "fc"],
        "cleaner": clean_str,
    },
    "quantity": {"synonyms": ["quantity", "qty"], "required": True, "cleaner": clean_int},
    "disposition": {"synonyms": ["disposition"], "cleaner": clean_str},
    "reason": {"synonyms": ["reason"], "cleaner": clean_str},
    "country": {"synonyms": ["country"], "cleaner": clean_str},
    "reconciled_qty": {"synonyms": ["reconciledquantity", "reconciled"], "cleaner": clean_int},
    "unreconciled_qty": {"synonyms": ["unreconciledquantity", "unreconciled"], "cleaner": clean_int},
}
DEFAULT_EVENT_TYPE = "Adjustments"
INT_FIELDS = ("reconciled_qty", "unreconciled_qty")


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        sku = record["sku"] or record["fnsku"]
        event_date = to_iso_date(record["event_date"])
        quantity = as_int(record["quantity"])
        if not event_date or not sku or quantity is None:
            continue
        event_type = record["event_type"] or DEFAULT_EVENT_TYPE
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "row_key": row_key(
                    event_date, event_type, record["reference_id"], sku, record["fnsku"],
                    record["fulfillment_center"], record["reason"], record["disposition"], quantity,
                ),
                "event_date": event_date,
                "event_type": event_type,
                "sku": sku,
                "quantity": quantity,
                **{k: as_int(record[k]) for k in INT_FIELDS},
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("row_key",))
    return "inventory_ledger", rows, "client_id,row_key"
