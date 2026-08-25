"""FBA Inventory export -> inventory_levels. Amazon splits inbound across
working/shipped/receiving columns; they are summed when present."""

import pandas as pd

from .headers import clean_int, clean_str, dedupe_last, map_columns

SPEC = {
    "sku": {"synonyms": ["sku", "sellersku", "msku", "merchantsku"], "required": True, "cleaner": clean_str},
    "fnsku": {"synonyms": ["fnsku"], "cleaner": clean_str},
    "asin": {"synonyms": ["asin"], "cleaner": clean_str},
    "fulfillable_quantity": {
        "synonyms": ["available", "availablequantity", "fulfillablequantity", "afnfulfillablequantity"],
        "cleaner": clean_int,
    },
    "inbound_total": {"synonyms": ["inbound", "inboundquantity", "totalinbound"], "cleaner": clean_int},
    "inbound_working": {"synonyms": ["afninboundworkingquantity", "inboundworking"], "cleaner": clean_int},
    "inbound_shipped": {"synonyms": ["afninboundshippedquantity", "inboundshipped"], "cleaner": clean_int},
    "inbound_receiving": {"synonyms": ["afninboundreceivingquantity", "inboundreceiving"], "cleaner": clean_int},
    "reserved_quantity": {"synonyms": ["reserved", "reservedquantity", "afnreservedquantity"], "cleaner": clean_int},
}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["sku"]:
            continue
        parts = [record[k] for k in ("inbound_working", "inbound_shipped", "inbound_receiving") if record[k] is not None]
        inbound = record["inbound_total"] if record["inbound_total"] is not None else (sum(parts) if parts else None)
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "snapshot_date": upload["period_start"],
                "sku": record["sku"],
                "fnsku": record["fnsku"],
                "asin": record["asin"],
                "fulfillable_quantity": record["fulfillable_quantity"],
                "inbound_quantity": inbound,
                "reserved_quantity": record["reserved_quantity"],
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("sku",))
    return "inventory_levels", rows, "client_id,sku,snapshot_date"
