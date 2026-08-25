"""Hubricon COGS template -> cogs_inputs. Columns match cogs-template.csv."""

import pandas as pd

from .headers import clean_int, clean_money, clean_str, dedupe_last, map_columns

SPEC = {
    "sku": {"synonyms": ["sku"], "required": True, "cleaner": clean_str},
    "asin": {"synonyms": ["asin"], "cleaner": clean_str},
    "product_name": {"synonyms": ["productname"], "cleaner": clean_str},
    "unit_cost_usd": {"synonyms": ["unitcostusd", "unitcost"], "required": True, "cleaner": clean_money},
    "inbound_freight_per_unit_usd": {
        "synonyms": ["inboundfreightperunitusd", "freightperunit"],
        "cleaner": clean_money,
    },
    "packaging_per_unit_usd": {"synonyms": ["packagingperunitusd", "packagingperunit"], "cleaner": clean_money},
    "other_cost_per_unit_usd": {"synonyms": ["othercostperunitusd", "otherperunit"], "cleaner": clean_money},
    "supplier_lead_time_days": {"synonyms": ["supplierleadtimedays", "leadtimedays"], "cleaner": clean_int},
    "notes": {"synonyms": ["notes"], "cleaner": clean_str},
}

EXAMPLE_SKUS = {"EXAMPLE-001"}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["sku"] or record["sku"] in EXAMPLE_SKUS:
            continue
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("sku",))
    return "cogs_inputs", rows, "client_id,sku"
