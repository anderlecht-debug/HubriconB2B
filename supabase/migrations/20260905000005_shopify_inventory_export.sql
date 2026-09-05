-- The Shopify inventory export becomes an intake report type.
--
-- Shopify's product CSV carries Variant Inventory Qty only for a store with
-- a single location ("the Inventory quantity column is used only for stores
-- that have a single location" — Shopify's own CSV guide). A brand with its
-- own shelf plus a 3PL exports that column blank, so until now its stock
-- silently never arrived and the inventory models ran on nothing. Products >
-- Inventory > Export is the export that does carry it, one row per variant
-- per location; engine/src/hubricon_engine/ingest/shopify_inventory.py sums
-- the locations into the same inventory_levels row the products export
-- writes for a single-location store.

alter table public.uploads drop constraint if exists uploads_report_type_check;
alter table public.uploads add constraint uploads_report_type_check
  check (report_type in ('business_report', 'sku_economics', 'ppc_search_terms',
                         'ppc_campaign', 'fba_inventory', 'cogs',
                         'fba_reimbursements', 'fba_returns', 'inventory_ledger',
                         'inventory_health', 'transactions',
                         'shopify_orders', 'shopify_products', 'shopify_inventory',
                         'shopify_payouts',
                         'meta_ads', 'google_ads_campaign', 'google_ads_search_terms'));
