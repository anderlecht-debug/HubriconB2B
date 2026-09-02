-- Bleed reports: the five Amazon exports that show money leaking out of an
-- FBA account — reimbursements Amazon has paid (so the engine can find the
-- ones it has not), customer returns and their dispositions, the inventory
-- ledger of lost/found/damaged/disposed units, the inventory-age snapshot
-- behind aged-inventory surcharges, and the Payments transaction detail
-- with every fee line. Row-level exports carry no natural key of their
-- own, so each row stores row_key = sha1 of its natural-key fields
-- (computed by the engine's parser) and upserts on (client_id, row_key).
--
-- Engine-lockdown posture (see 20260827000003): RLS enabled, NO policies —
-- only the service role (the engine) reads or writes these tables. Clients
-- see findings through deliverables, never raw rows.

-- The intake registry enumerates report types; admit the five new ones.
alter table public.uploads drop constraint uploads_report_type_check;
alter table public.uploads add constraint uploads_report_type_check
  check (report_type in ('business_report', 'sku_economics', 'ppc_search_terms',
                         'ppc_campaign', 'fba_inventory', 'cogs',
                         'fba_reimbursements', 'fba_returns', 'inventory_ledger',
                         'inventory_health', 'transactions'));

-- Reimbursements report (Reports > Fulfillment > Payments > Reimbursements).
create table public.fba_reimbursements (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  row_key text not null,  -- sha1(reimbursement_id|sku|reason|approval_date)
  approval_date date,
  reimbursement_id text not null,
  case_id text,
  amazon_order_id text,
  reason text not null,
  sku text not null,  -- fnsku when the export leaves sku blank
  fnsku text,
  asin text,
  product_name text,
  condition text,
  currency text not null default 'USD',
  amount_per_unit numeric(12, 2),
  amount_total numeric(12, 2),
  quantity_reimbursed_cash integer,
  quantity_reimbursed_inventory integer,
  quantity_reimbursed_total integer,
  original_reimbursement_id text,
  original_reimbursement_type text,
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, row_key)
);

-- FBA customer returns (Reports > Fulfillment > Customer Concessions).
-- One line per returned unit (LPN) with what Amazon did with it.
create table public.fba_returns (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  row_key text not null,  -- sha1(order_id|sku|return_date|license_plate_number|fulfillment_center_id)
  return_date date not null,
  order_id text,
  sku text not null,
  asin text,
  fnsku text,
  product_name text,
  quantity integer not null,
  fulfillment_center_id text,
  detailed_disposition text,  -- SELLABLE | DAMAGED | CUSTOMER_DAMAGED | CARRIER_DAMAGED | DEFECTIVE | EXPIRED ...
  reason text,
  status text,  -- 'Unit returned to inventory' | 'Reimbursed' ...
  license_plate_number text,
  customer_comments text,
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, row_key)
);

-- Inventory Ledger detail (Reports > Fulfillment > Inventory > Inventory
-- Ledger) and the older Inventory Adjustments export, which the parser folds
-- into the same shape with event_type = 'Adjustments'.
create table public.inventory_ledger (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  row_key text not null,  -- sha1(event_date|event_type|reference_id|sku|fnsku|fulfillment_center|reason|disposition|quantity)
  event_date date not null,
  event_type text not null,  -- Adjustments | Receipts | Shipments | CustomerReturns | VendorReturns | WhseTransfers ...
  reference_id text,
  fnsku text,
  asin text,
  sku text not null,
  title text,
  fulfillment_center text,
  quantity integer not null,  -- signed
  disposition text,
  -- Amazon adjustment codes: M misplaced, F found, D damaged, E customer
  -- damaged, P disposed, 5/6 lost/found in transit, X/N unrecoverable ...
  reason text,
  country text,
  reconciled_qty integer,
  unreconciled_qty integer,
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, row_key)
);

-- Inventory Age / Manage Inventory Health snapshot, keyed on the upload's
-- snapshot date like inventory_levels. The seven estimated-ais-* buckets are
-- summed into estimated_aged_surcharge (null when the export has none).
create table public.inventory_health (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  snapshot_date date not null,
  sku text not null,
  fnsku text,
  asin text,
  product_name text,
  condition text,
  available integer,
  pending_removal integer,
  inv_age_0_to_90 integer,
  inv_age_91_to_180 integer,
  inv_age_181_to_270 integer,
  inv_age_271_to_365 integer,
  inv_age_365_plus integer,
  units_shipped_t7 integer,
  units_shipped_t30 integer,
  units_shipped_t60 integer,
  units_shipped_t90 integer,
  sell_through numeric(8, 4),
  days_of_supply integer,
  estimated_excess_quantity integer,
  item_volume numeric(12, 4),  -- cu ft per unit
  storage_volume numeric(12, 4),  -- cu ft total
  estimated_storage_cost_next_month numeric(12, 2),
  estimated_aged_surcharge numeric(12, 2),
  recommended_action text,
  low_inventory_level_fee_applied boolean,
  your_price numeric(12, 2),
  sales_price numeric(12, 2),
  currency text not null default 'USD',
  healthy_inventory_level integer,
  storage_type text,
  weeks_of_cover_t30 numeric(8, 4),
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, sku, snapshot_date)
);

-- Payments > Transaction View date-range export: one line per settlement
-- event. txn_datetime keeps the wall-clock timestamp exactly as Amazon
-- prints it (zone name dropped, not converted); txn_date is its date part
-- and is what the models key on.
create table public.settlement_transactions (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  row_key text not null,  -- sha1(txn_datetime|settlement_id|txn_type|order_id|sku|description|quantity|total)
  txn_date date not null,
  txn_datetime timestamp not null,
  settlement_id text,
  txn_type text not null,  -- Order | Refund | Adjustment | Service Fee | FBA Inventory Fee | Transfer | Liquidations ...
  order_id text,
  sku text,
  description text,
  quantity integer,
  marketplace text,
  account_type text,
  fulfillment text,
  product_sales numeric(12, 2),
  product_sales_tax numeric(12, 2),
  shipping_credits numeric(12, 2),
  shipping_credits_tax numeric(12, 2),
  gift_wrap_credits numeric(12, 2),
  gift_wrap_credits_tax numeric(12, 2),
  regulatory_fee numeric(12, 2),
  tax_on_regulatory_fee numeric(12, 2),
  promotional_rebates numeric(12, 2),
  promotional_rebates_tax numeric(12, 2),
  marketplace_withheld_tax numeric(12, 2),
  selling_fees numeric(12, 2),
  fba_fees numeric(12, 2),
  other_transaction_fees numeric(12, 2),
  other numeric(12, 2),
  total numeric(12, 2) not null,
  raw jsonb,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, row_key)
);

-- RLS on, no policies: service role only (engine-lockdown posture).
alter table public.fba_reimbursements enable row level security;
alter table public.fba_returns enable row level security;
alter table public.inventory_ledger enable row level security;
alter table public.inventory_health enable row level security;
alter table public.settlement_transactions enable row level security;

create index fba_reimbursements_client_date_idx on public.fba_reimbursements (client_id, approval_date);
create index fba_returns_client_date_idx on public.fba_returns (client_id, return_date);
create index inventory_ledger_client_date_idx on public.inventory_ledger (client_id, event_date);
create index inventory_health_client_date_idx on public.inventory_health (client_id, snapshot_date);
create index settlement_transactions_client_date_idx on public.settlement_transactions (client_id, txn_date);
