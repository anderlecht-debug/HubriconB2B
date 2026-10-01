"""Hubricon COGS template -> cogs_inputs. Columns match cogs-template.csv.

One sheet for both platforms (2026-10-01). `sku` leads: the Variant SKU on
Shopify, the seller SKU on Amazon, the key every other export joins on.
`listing_id` is optional: the ASIN on Amazon, the product handle on
Shopify. It lands in the cogs_inputs column still called `asin` (the bridge
models/common.sku_asin_bridge reads), and a sheet made from the old
template, whose second column was `asin`, parses exactly as before.

fulfillment_per_unit_usd (2026-09-04) is pick, pack and postage per unit,
or a 3PL's per-unit fee — a landed cost no platform report itemises. It is
counted once (models/margin.py): on every Shopify sale, and on an Amazon
sale only when Amazon charged no FBA fulfilment fee on it, so a seller on
both platforms fills it in for the 3PL and it never lands on top of FBA."""

import pandas as pd

from .headers import clean_int, clean_money, clean_str, dedupe_last, map_columns

SPEC = {
    # every sku name is one lib/call.js COST_FILE also reads (lib/call.test.mjs)
    "sku": {"synonyms": ["sku", "variantsku", "sellersku", "msku", "merchantsku"], "required": True,
            "cleaner": clean_str},
    "asin": {"synonyms": ["listingid", "asin", "producthandle", "handle"], "cleaner": clean_str},
    "product_name": {"synonyms": ["productname"], "cleaner": clean_str},
    "unit_cost_usd": {"synonyms": ["unitcostusd", "unitcost"], "required": True, "cleaner": clean_money},
    "inbound_freight_per_unit_usd": {
        "synonyms": ["inboundfreightperunitusd", "freightperunit"],
        "cleaner": clean_money,
    },
    "packaging_per_unit_usd": {"synonyms": ["packagingperunitusd", "packagingperunit"], "cleaner": clean_money},
    "other_cost_per_unit_usd": {"synonyms": ["othercostperunitusd", "otherperunit"], "cleaner": clean_money},
    "fulfillment_per_unit_usd": {
        "synonyms": ["fulfillmentperunitusd", "fulfillmentperunit", "pickpackpostageperunit",
                     "shippingperunitusd", "shippingperunit"],
        "cleaner": clean_money,
    },
    "supplier_lead_time_days": {"synonyms": ["supplierleadtimedays", "leadtimedays"], "cleaner": clean_int},
    # supplier terms (2026-09-23), all optional: a blank column is priced as
    # absent by models/replenishment.py, never guessed
    "supplier": {"synonyms": ["supplier", "vendor", "suppliername"], "cleaner": clean_str},
    "moq_units": {"synonyms": ["moqunits", "moq", "minimumorderquantity", "minorderunits"], "cleaner": clean_int},
    "case_pack_units": {"synonyms": ["casepackunits", "casepack", "unitspercase"], "cleaner": clean_int},
    "price_break_qty": {"synonyms": ["pricebreakqty", "pricebreakunits", "volumebreakqty"], "cleaner": clean_int},
    "price_break_unit_cost_usd": {"synonyms": ["pricebreakunitcostusd", "pricebreakunitcost", "unitcostatbreak"],
                                  "cleaner": clean_money},
    "air_freight_per_unit_usd": {"synonyms": ["airfreightperunitusd", "airfreightperunit"], "cleaner": clean_money},
    "air_lead_time_days": {"synonyms": ["airleadtimedays", "airleadtime"], "cleaner": clean_int},
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
