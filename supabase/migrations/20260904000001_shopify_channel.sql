-- The Shopify route: a second platform on the same engine.
--
-- A client says which store(s) it runs (clients.platform); every canonical
-- data row says which channel it came from; the intake admits the Shopify
-- exports and the two ad platforms a Shopify brand actually buys; the
-- harvest holds Shopify stores beside Amazon sellers. The models stay
-- channel-blind arithmetic over the same tables — a unit is a unit and a fee
-- is a fee — and engine/src/hubricon_engine/channels.py is the one place the
-- mechanics differ (payout cycle, fee cliffs, reimbursement windows).

alter table public.clients
  add column if not exists platform text not null default 'amazon'
    check (platform in ('amazon', 'shopify', 'both')),
  add column if not exists shopify_domain text unique;

-- intake: the Shopify-side exports
alter table public.uploads drop constraint if exists uploads_report_type_check;
alter table public.uploads add constraint uploads_report_type_check
  check (report_type in ('business_report', 'sku_economics', 'ppc_search_terms',
                         'ppc_campaign', 'fba_inventory', 'cogs',
                         'fba_reimbursements', 'fba_returns', 'inventory_ledger',
                         'inventory_health', 'transactions',
                         'shopify_orders', 'shopify_products', 'shopify_payouts',
                         'meta_ads', 'google_ads_campaign', 'google_ads_search_terms'));

-- channel on the canonical tables. The three keyed on an item and a period
-- gain channel in their natural key, so a brand on both platforms can hold
-- the same SKU twice; the ad and settlement tables carry it as a descriptor
-- (campaign ids and row hashes already differ by platform).
-- The three swaps below widen a natural key rather than replacing data:
-- every existing row is channel 'amazon', so the new key is a superset of
-- the old one and no row can collide. `if not exists` on the add keeps the
-- whole migration re-runnable.
alter table public.asin_traffic
  add column if not exists channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify'));
alter table public.asin_traffic
  drop constraint if exists asin_traffic_client_id_child_asin_period_start_period_end_key;
create unique index if not exists asin_traffic_client_channel_item_period_key
  on public.asin_traffic (client_id, channel, child_asin, period_start, period_end);

alter table public.sku_economics
  add column if not exists channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify'));
alter table public.sku_economics
  drop constraint if exists sku_economics_client_id_sku_period_start_period_end_key;
create unique index if not exists sku_economics_client_channel_sku_period_key
  on public.sku_economics (client_id, channel, sku, period_start, period_end);

alter table public.inventory_levels
  add column if not exists channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify'));
alter table public.inventory_levels
  drop constraint if exists inventory_levels_client_id_sku_snapshot_date_key;
create unique index if not exists inventory_levels_client_channel_sku_snapshot_key
  on public.inventory_levels (client_id, channel, sku, snapshot_date);

alter table public.ppc_spend
  add column if not exists channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify'));
alter table public.ppc_search_terms
  add column if not exists channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify'));
alter table public.settlement_transactions
  add column if not exists channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify'));

-- A Shopify store ships from its own shelf or a 3PL: pick, pack and postage
-- per unit is a landed cost no platform report itemises, so the cost
-- template carries it. Amazon sellers leave it blank (FBA fees are in the
-- SKU Economics export).
alter table public.cogs_inputs
  add column if not exists fulfillment_per_unit_usd numeric(12, 4);

-- harvest: Shopify stores beside Amazon sellers. seller_id holds the store's
-- myshopify handle; harvest_products.asin holds <domain>/products/<handle>.
alter table public.harvest_sellers
  add column if not exists platform text not null default 'amazon'
    check (platform in ('amazon', 'shopify'));
alter table public.harvest_sellers drop constraint if exists harvest_sellers_source_check;
alter table public.harvest_sellers
  add constraint harvest_sellers_source_check
  check (source in ('bestsellers', 'wayback', 'shopify'));
create index if not exists harvest_sellers_platform_idx on public.harvest_sellers (platform);
alter table public.harvest_products
  add column if not exists platform text not null default 'amazon'
    check (platform in ('amazon', 'shopify'));
