"""CSV ingest: one parser module per report type, Amazon's and Shopify's.

Each parser exposes parse(df, upload) -> (table, rows, on_conflict), where
rows are ready for chunked_upsert and on_conflict matches the table's
natural-key unique constraint. Since 2026-09-04 a parser may instead return
a list of such triples when one export feeds two tables (the Shopify
products export is both the unit-cost sheet and the stock snapshot);
parse_all normalises either shape so the CLI never has to care.

Every row a parser writes to one of the six channel tables carries
``channel`` ('amazon' or 'shopify'); the Shopify-side parsers are the ones
registered after the bleed reports.
"""

import pandas as pd

from . import (
    business_report,
    cogs,
    fba_inventory,
    fba_reimbursements,
    fba_returns,
    google_ads_campaign,
    google_ads_search_terms,
    inventory_health,
    inventory_ledger,
    meta_ads,
    ppc_campaign,
    ppc_search_terms,
    shopify_inventory,
    shopify_orders,
    shopify_payouts,
    shopify_products,
    sku_economics,
    transactions,
)

PARSERS = {
    "business_report": business_report,
    "sku_economics": sku_economics,
    "ppc_search_terms": ppc_search_terms,
    "ppc_campaign": ppc_campaign,
    "fba_inventory": fba_inventory,
    "cogs": cogs,
    # bleed reports: where money leaks out of an FBA account
    "fba_reimbursements": fba_reimbursements,
    "fba_returns": fba_returns,
    "inventory_ledger": inventory_ledger,
    "inventory_health": inventory_health,
    "transactions": transactions,
    # the Shopify route: the store's own exports and the two ad platforms a
    # Shopify brand actually buys
    "shopify_orders": shopify_orders,
    "shopify_products": shopify_products,
    "shopify_inventory": shopify_inventory,
    "shopify_payouts": shopify_payouts,
    "meta_ads": meta_ads,
    "google_ads_campaign": google_ads_campaign,
    "google_ads_search_terms": google_ads_search_terms,
}


def parse_all(report_type: str, df: pd.DataFrame, upload: dict) -> list[tuple[str, list[dict], str]]:
    """Run the parser for report_type and return its output as a list of
    (table, rows, on_conflict) triples whether it produced one or several."""
    result = PARSERS[report_type].parse(df, upload)
    if isinstance(result, tuple) and len(result) == 3 and isinstance(result[0], str):
        return [result]
    return list(result)
