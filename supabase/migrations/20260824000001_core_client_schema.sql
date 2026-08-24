-- Core multi-tenant schema: one row per Hubricon client, data silos keyed by client_id.

create table public.clients (
  id uuid primary key default gen_random_uuid(),
  company_name text,
  contact_name text,
  contact_email text unique,
  amazon_seller_id text unique,
  stripe_customer_id text unique,
  status text not null default 'pending'
    check (status in ('pending', 'active', 'past_due', 'churned')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Maps Supabase Auth users to the client workspace(s) they may read.
create table public.client_users (
  user_id uuid not null references auth.users (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  primary key (user_id, client_id)
);

create table public.orders (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  amazon_order_id text not null,
  purchase_date timestamptz,
  order_status text,
  order_total numeric(12, 2),
  currency text not null default 'USD',
  raw jsonb,
  ingested_at timestamptz not null default now(),
  unique (client_id, amazon_order_id)
);

create table public.inventory_levels (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  snapshot_date date not null default current_date,
  sku text not null,
  asin text,
  fnsku text,
  fulfillable_quantity integer,
  inbound_quantity integer,
  reserved_quantity integer,
  raw jsonb,
  ingested_at timestamptz not null default now(),
  unique (client_id, sku, snapshot_date)
);

create table public.ppc_spend (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  report_date date not null,
  campaign_id text not null,
  campaign_name text,
  spend numeric(12, 2),
  sales numeric(12, 2),
  clicks integer,
  impressions integer,
  raw jsonb,
  ingested_at timestamptz not null default now(),
  unique (client_id, campaign_id, report_date)
);

create index orders_client_date_idx on public.orders (client_id, purchase_date);
create index inventory_client_date_idx on public.inventory_levels (client_id, snapshot_date);
create index ppc_client_date_idx on public.ppc_spend (client_id, report_date);

-- keep clients.updated_at fresh
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger clients_set_updated_at
  before update on public.clients
  for each row execute function public.set_updated_at();
