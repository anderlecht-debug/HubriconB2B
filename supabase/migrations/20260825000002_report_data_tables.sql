-- Typed tables for the CSV report exports clients upload. inventory_levels
-- and ppc_spend (built for SP-API pulls) already fit the FBA Inventory and
-- daily Campaign exports — they just gain upload provenance here.

alter table public.inventory_levels
  add column upload_id uuid references public.uploads (id) on delete set null;
alter table public.ppc_spend
  add column upload_id uuid references public.uploads (id) on delete set null;

-- Business Report "Detail Page Sales and Traffic by Child Item".
-- One export is one aggregate row per ASIN over a date range — Amazon gives
-- no time dimension inside a single file, so the time series is built from
-- multiple period-scoped uploads, keyed on (asin, period).
create table public.asin_traffic (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  period_start date not null,
  period_end date not null,
  parent_asin text,
  child_asin text not null,
  title text,
  sessions integer,
  page_views integer,
  buy_box_pct numeric(6, 2),
  units_ordered integer,
  ordered_product_sales numeric(12, 2),
  total_order_items integer,
  unit_session_pct numeric(6, 2),
  currency text not null default 'USD',
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, child_asin, period_start, period_end)
);

-- SKU Economics export: the SKU<->ASIN bridge plus Amazon fee detail,
-- available at monthly granularity.
create table public.sku_economics (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  period_start date not null,
  period_end date not null,
  sku text not null,
  asin text,
  units_sold integer,
  avg_sales_price numeric(12, 2),
  sales numeric(12, 2),
  referral_fees numeric(12, 2),
  fba_fulfillment_fees numeric(12, 2),
  storage_fees numeric(12, 2),
  other_fees numeric(12, 2),
  net_proceeds numeric(12, 2),
  currency text not null default 'USD',
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, sku, period_start, period_end)
);

-- Sponsored Products Search Term report (aggregate over the export range).
create table public.ppc_search_terms (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  period_start date not null,
  period_end date not null,
  campaign_name text not null,
  ad_group_name text not null default '',
  targeting text not null default '',
  match_type text,
  search_term text not null,
  impressions integer,
  clicks integer,
  spend numeric(12, 2),
  sales_7d numeric(12, 2),
  orders_7d integer,
  units_7d integer,
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, period_start, period_end, campaign_name, ad_group_name, targeting, search_term)
);

-- Hubricon COGS template: current per-unit costs and supplier lead times.
-- Re-uploads replace rows; history lives in the raw files in Storage.
create table public.cogs_inputs (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  sku text not null,
  asin text,
  product_name text,
  unit_cost_usd numeric(12, 4),
  inbound_freight_per_unit_usd numeric(12, 4),
  packaging_per_unit_usd numeric(12, 4),
  other_cost_per_unit_usd numeric(12, 4),
  supplier_lead_time_days integer,
  notes text,
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, sku)
);

alter table public.asin_traffic enable row level security;
alter table public.sku_economics enable row level security;
alter table public.ppc_search_terms enable row level security;
alter table public.cogs_inputs enable row level security;

create policy "members read own asin traffic"
  on public.asin_traffic for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own sku economics"
  on public.sku_economics for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own search terms"
  on public.ppc_search_terms for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own cogs"
  on public.cogs_inputs for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index asin_traffic_client_period_idx on public.asin_traffic (client_id, period_start);
create index sku_economics_client_period_idx on public.sku_economics (client_id, period_start);
create index ppc_search_terms_client_period_idx on public.ppc_search_terms (client_id, period_start);
