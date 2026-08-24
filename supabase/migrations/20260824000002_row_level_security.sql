-- Mechanical tenant isolation: RLS on every table.
-- Read-only for authenticated clients, scoped to their own client_id.
-- No insert/update/delete policies exist, so only the service role
-- (ingestion worker, Stripe webhook) can write.

alter table public.clients enable row level security;
alter table public.client_users enable row level security;
alter table public.orders enable row level security;
alter table public.inventory_levels enable row level security;
alter table public.ppc_spend enable row level security;

create policy "members read own client"
  on public.clients for select to authenticated
  using (id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "users read own memberships"
  on public.client_users for select to authenticated
  using (user_id = (select auth.uid()));

create policy "members read own orders"
  on public.orders for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own inventory"
  on public.inventory_levels for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own ppc spend"
  on public.ppc_spend for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));
