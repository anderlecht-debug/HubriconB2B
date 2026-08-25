"""CSV ingest: one parser module per Amazon report type.

Each parser exposes parse(df, upload) -> (table, rows, on_conflict), where
rows are ready for chunked_upsert and on_conflict matches the table's
natural-key unique constraint.
"""

from . import (
    business_report,
    cogs,
    fba_inventory,
    ppc_campaign,
    ppc_search_terms,
    sku_economics,
)

PARSERS = {
    "business_report": business_report,
    "sku_economics": sku_economics,
    "ppc_search_terms": ppc_search_terms,
    "ppc_campaign": ppc_campaign,
    "fba_inventory": fba_inventory,
    "cogs": cogs,
}
