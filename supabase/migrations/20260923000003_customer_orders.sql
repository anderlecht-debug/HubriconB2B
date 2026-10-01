-- One row per Shopify order with a hashed customer key (engine/ingest/shopify_orders.py):
-- the SHA-256 of the lower-cased email salted with the client id. The email is
-- never stored. models/clv.py fits repeat-purchase behaviour on it.
create table if not exists public.customer_orders (
  id bigint generated always as identity primary key,
  client_id uuid not null references public.clients (id) on delete cascade,
  channel text not null default 'shopify',
  customer_key text not null,
  order_name text not null,
  order_date date not null,
  revenue numeric(12, 2),
  units integer,
  upload_id uuid references public.uploads (id) on delete set null,
  ingested_at timestamptz not null default now(),
  unique (client_id, channel, order_name)
);
alter table public.customer_orders enable row level security;
create policy "members read own customer orders"
  on public.customer_orders for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));
create index customer_orders_client_customer_idx on public.customer_orders (client_id, customer_key, order_date);
