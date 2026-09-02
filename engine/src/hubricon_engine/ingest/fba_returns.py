"""FBA customer returns report -> fba_returns. Each line is one returned
unit (an LPN) with Amazon's disposition: SELLABLE went back on the shelf;
anything else is a unit the seller may still be owed for."""

import pandas as pd

from .headers import as_int, clean_int, clean_str, dedupe_last, map_columns, row_key, to_iso_date

SPEC = {
    "return_date": {"synonyms": ["returndate", "date"], "required": True, "cleaner": clean_str},
    "order_id": {"synonyms": ["orderid", "amazonorderid"], "cleaner": clean_str},
    "sku": {"synonyms": ["sku", "msku", "sellersku", "merchantsku"], "cleaner": clean_str},
    "asin": {"synonyms": ["asin"], "cleaner": clean_str},
    "fnsku": {"synonyms": ["fnsku"], "cleaner": clean_str},
    "product_name": {"synonyms": ["productname", "title", "itemname"], "cleaner": clean_str},
    "quantity": {"synonyms": ["quantity", "qty", "returnedquantity"], "required": True, "cleaner": clean_int},
    "fulfillment_center_id": {
        "synonyms": ["fulfillmentcenterid", "fulfillmentcenter", "fc", "warehouse"],
        "cleaner": clean_str,
    },
    "detailed_disposition": {"synonyms": ["detaileddisposition", "disposition"], "cleaner": clean_str},
    "reason": {"synonyms": ["reason", "returnreason"], "cleaner": clean_str},
    "status": {"synonyms": ["status"], "cleaner": clean_str},
    "license_plate_number": {"synonyms": ["licenseplatenumber", "lpn"], "cleaner": clean_str},
    "customer_comments": {"synonyms": ["customercomments", "customercomment", "comments"], "cleaner": clean_str},
}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        sku = record["sku"] or record["fnsku"]
        return_date = to_iso_date(record["return_date"])
        quantity = as_int(record["quantity"])
        if not return_date or not sku or quantity is None:
            continue
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "row_key": row_key(
                    record["order_id"], sku, return_date,
                    record["license_plate_number"], record["fulfillment_center_id"],
                ),
                "return_date": return_date,
                "sku": sku,
                "quantity": quantity,
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("row_key",))
    return "fba_returns", rows, "client_id,row_key"
