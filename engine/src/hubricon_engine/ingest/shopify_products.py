"""Shopify Products export -> cogs_inputs (unit cost only) and
inventory_levels (channel shopify): one export, two tables.

Shopify Admin > Products > Export prints one line per variant. The
product-level columns (Title, Vendor, Type, Tags, the Option names) appear
on a product's first line only and are forward-filled by Handle; image-only
lines (a Handle and an Image Src, no Variant SKU) and variants without a
SKU are skipped — the SKU is what everything else joins on, and an image
line is not a variant.

The export is the snapshot the store keeps: Variant Inventory Qty is
on-hand at the moment of export, so the upload is snapshot-scoped and
period_start is the snapshot date. asin holds the product Handle, which
bridges a Shopify SKU to its product page the way an ASIN does.

THE VARIANT'S OWN NUMBERS (2026-10-01). Variant Price, Variant Compare At
Price and Variant Grams are parsed and kept on every row this export writes,
as raw["_variant"] = {price, compare_at_price, grams, handle, product_name,
status, snapshot_date}: the two prices are what models/shopify_findings.py
reads for "sells below its own compare-at" (the opener that booked the call,
carried past the yes), and the grams for the parcel-weight observation. No
column was added for them, so no migration: raw is the row's own record of
what the export said. A variant that states neither a cost nor a quantity
writes no row at all, so its compare-at is not kept either.

Shopify prints Variant Inventory Qty only for a store with ONE location; a
multi-location store exports the column blank and sends its stock through
the inventory export instead (shopify_inventory). A variant with no stated
quantity therefore writes no inventory row — a row of nulls would make the
Health Score's coverage read 'inventory on file' while the newsvendor has
nothing to run on, and a variant that is genuinely out of stock exports 0,
not a blank.

Cost per item is Shopify's own unit-cost field. A variant that states one
lands in cogs_inputs as unit_cost_usd, and ONLY that column plus the
identity columns: PostgREST upsert sets the columns provided, so a richer
COGS-template row already on file keeps its freight, packaging, fulfilment
and lead time. A variant without a cost writes no cogs row at all — a
blank must never overwrite a stated number (decided 2026-09-04).
"""

import pandas as pd

from .headers import IngestError, as_int, clean_int, clean_money, clean_str, dedupe_last, map_columns

SPEC = {
    "handle": {"synonyms": ["handle"], "required": True, "cleaner": clean_str},
    "title": {"synonyms": ["title"], "cleaner": clean_str},
    "vendor": {"synonyms": ["vendor"], "cleaner": clean_str},
    "product_type": {"synonyms": ["type", "producttype"], "cleaner": clean_str},
    "option1_value": {"synonyms": ["option1value"], "cleaner": clean_str},
    "option2_value": {"synonyms": ["option2value"], "cleaner": clean_str},
    "option3_value": {"synonyms": ["option3value"], "cleaner": clean_str},
    "sku": {"synonyms": ["variantsku", "sku"], "required": True, "cleaner": clean_str},
    "grams": {"synonyms": ["variantgrams"], "cleaner": clean_money},
    "inventory_qty": {"synonyms": ["variantinventoryqty", "variantinventoryquantity"], "cleaner": clean_int},
    "price": {"synonyms": ["variantprice"], "cleaner": clean_money},
    "compare_at_price": {"synonyms": ["variantcompareatprice", "compareatprice"], "cleaner": clean_money},
    "cost": {"synonyms": ["costperitem", "variantcost", "cost"], "cleaner": clean_money},
    "image_src": {"synonyms": ["imagesrc"], "cleaner": clean_str},
    "status": {"synonyms": ["status"], "cleaner": clean_str},
}
# Printed on a product's first line only, so forward-filled by Handle. Status
# is the product's (active, draft, archived), not the variant's.
PRODUCT_FIELDS = ("title", "vendor", "product_type", "status")
VARIANT_KEY = "_variant"   # where raw keeps the parsed variant numbers
DEFAULT_OPTION_VALUE = "Default Title"  # Shopify's placeholder on a single-variant product
CHANNEL = "shopify"


def product_name(title: str | None, options: tuple[str | None, ...]) -> str | None:
    values = [v for v in options if v and v != DEFAULT_OPTION_VALUE]
    if not title:
        return " / ".join(values) or None
    return f"{title} — {' / '.join(values)}" if values else title


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    products: dict[str, dict] = {}
    cogs_rows: list[dict] = []
    inventory_rows: list[dict] = []
    variants = 0
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        handle = record["handle"]
        if not handle:
            continue
        product = products.setdefault(handle, {k: None for k in PRODUCT_FIELDS})
        for k in PRODUCT_FIELDS:
            if product[k] is None and record[k] is not None:
                product[k] = record[k]
        if not record["sku"]:
            continue  # image-only line, or a variant nothing can join on
        variants += 1
        name = product_name(product["title"],
                            (record["option1_value"], record["option2_value"], record["option3_value"]))
        source = {**source, VARIANT_KEY: {
            "price": record["price"], "compare_at_price": record["compare_at_price"], "grams": record["grams"],
            "handle": handle, "product_name": name, "status": (product["status"] or "").lower() or None,
            "snapshot_date": upload["period_start"],
        }}
        if record["cost"] is not None:
            cogs_rows.append(
                {
                    "client_id": upload["client_id"],
                    "upload_id": upload["id"],
                    "sku": record["sku"],
                    "asin": handle,
                    "product_name": name,
                    "unit_cost_usd": record["cost"],
                    "raw": source,
                }
            )
        if record["inventory_qty"] is None:
            continue  # see the note on Variant Inventory Qty above
        inventory_rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": CHANNEL,
                "snapshot_date": upload["period_start"],
                "sku": record["sku"],
                "asin": handle,
                "fnsku": None,
                "fulfillable_quantity": as_int(record["inventory_qty"]),
                "inbound_quantity": None,
                "reserved_quantity": None,
                "raw": source,
            }
        )
    if variants and not cogs_rows and not inventory_rows:
        # The file parsed and held variants, but stated neither a cost nor a
        # quantity. "No usable data rows" would be true and useless; this says
        # which two things to go and do.
        raise IngestError(
            "The products export states no Cost per item and no Variant Inventory Qty. Fill in Cost per "
            "item in Shopify before exporting, and — if the store has more than one location, which is "
            "why the quantity column is blank — send Products > Inventory > Export as well."
        )
    return [
        ("cogs_inputs", dedupe_last(cogs_rows, ("sku",)), "client_id,sku"),
        ("inventory_levels", dedupe_last(inventory_rows, ("sku",)), "client_id,channel,sku,snapshot_date"),
    ]
