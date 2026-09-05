"""Shopify inventory export -> inventory_levels (channel shopify).

The products export carries `Variant Inventory Qty` only for a store with a
single location. Shopify's own CSV guide says so: "the Inventory quantity
column is used only for stores that have a single location". A brand with
its own shelf plus a 3PL — the common shape at this size — exports that
column blank, and its stock would silently never arrive. Products >
Inventory > Export is the export that does carry it: one row per variant
per location, with the four states Shopify tracks.

  Available    sellable right now                      -> fulfillable_quantity
  Incoming     on a transfer, not landed yet           -> inbound_quantity
  Committed    promised to orders not yet fulfilled  ┐
  Unavailable  damaged, QC hold, safety stock, other ┘ -> reserved_quantity

A SKU's row is the sum across its locations: the models ask how many units
the brand can ship, not which shelf they sit on. `raw` keeps the
per-location split so any number here can be traced back to a location.

Not every export shape prints Available. When it is absent but On hand is
present, Available is derived from Shopify's own identity — on hand =
available + committed + unavailable — rather than passing On hand off as
sellable stock, which would overstate what can ship. A variant whose every
state is blank writes no row at all: absent stock is not zero stock, and a
row of nulls would make the coverage score read 'inventory on file' while
the newsvendor has nothing to run on (the same rule the products export
follows for a blank Cost per item).
"""

import pandas as pd

from .headers import as_int, clean_int, clean_str, dedupe_last, map_columns
from .shopify_products import product_name

SPEC = {
    "handle": {"synonyms": ["handle"], "cleaner": clean_str},
    "title": {"synonyms": ["title"], "cleaner": clean_str},
    "option1_value": {"synonyms": ["option1value"], "cleaner": clean_str},
    "option2_value": {"synonyms": ["option2value"], "cleaner": clean_str},
    "option3_value": {"synonyms": ["option3value"], "cleaner": clean_str},
    "sku": {"synonyms": ["sku", "variantsku"], "required": True, "cleaner": clean_str},
    "location": {"synonyms": ["location", "locationname"], "cleaner": clean_str},
    "available": {"synonyms": ["available"], "cleaner": clean_int},
    "on_hand": {"synonyms": ["onhand"], "cleaner": clean_int},
    "committed": {"synonyms": ["committed"], "cleaner": clean_int},
    "unavailable": {"synonyms": ["unavailable"], "cleaner": clean_int},
    "incoming": {"synonyms": ["incoming"], "cleaner": clean_int},
}
STATES = ("available", "on_hand", "committed", "unavailable", "incoming")
CHANNEL = "shopify"


def _add(total: int | None, value: int | None) -> int | None:
    """Sum across locations that keeps 'never stated' distinct from zero."""
    if value is None:
        return total
    return value if total is None else total + value


def _sellable(states: dict[str, int | None]) -> int | None:
    """Units that can ship. Available when the export prints it; otherwise
    on hand less what is committed or held back, which is the same number by
    Shopify's own definition of on hand."""
    if states["available"] is not None:
        return states["available"]
    if states["on_hand"] is None:
        return None
    held = (states["committed"] or 0) + (states["unavailable"] or 0)
    return max(0, states["on_hand"] - held)


def _reserved(states: dict[str, int | None]) -> int | None:
    """On hand but not sellable: promised to an order, or held back."""
    if states["committed"] is None and states["unavailable"] is None:
        return None
    return (states["committed"] or 0) + (states["unavailable"] or 0)


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    variants: dict[str, dict] = {}
    for record in mapped.to_dict(orient="records"):
        sku = record["sku"]
        if not sku:
            continue  # a location header line, or a variant nothing can join on
        variant = variants.setdefault(
            sku, {"handle": None, "title": None, "options": (None, None, None),
                  "states": {k: None for k in STATES}, "locations": []},
        )
        # The naming columns repeat on a variant's every location line; take
        # the first one that states anything.
        for field in ("handle", "title"):
            if variant[field] is None and record[field]:
                variant[field] = record[field]
        options = (record["option1_value"], record["option2_value"], record["option3_value"])
        if variant["options"] == (None, None, None) and any(options):
            variant["options"] = options
        # as_int: pandas promotes an int column that also holds blanks to
        # float on the way through map_columns, and these land in an integer
        # column and in a JSON payload.
        counted = {s: as_int(record[s]) for s in STATES}
        for state in STATES:
            variant["states"][state] = _add(variant["states"][state], counted[state])
        variant["locations"].append({"location": record["location"], **counted})

    rows = []
    for sku, variant in variants.items():
        states = variant["states"]
        if all(states[s] is None for s in STATES):
            continue  # nothing stated anywhere: no snapshot to record
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": CHANNEL,
                "snapshot_date": upload["period_start"],
                "sku": sku,
                "asin": variant["handle"],  # the handle bridges sku -> product page
                "fnsku": None,
                "fulfillable_quantity": _sellable(states),
                "inbound_quantity": states["incoming"],
                "reserved_quantity": _reserved(states),
                "raw": {
                    "product_name": product_name(variant["title"], variant["options"]),
                    "on_hand": states["on_hand"],
                    "locations": variant["locations"],
                },
            }
        )
    return "inventory_levels", dedupe_last(rows, ("sku",)), "client_id,channel,sku,snapshot_date"
