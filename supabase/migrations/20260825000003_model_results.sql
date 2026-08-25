-- Output tables for the analytics engine. One model_runs row per
-- `hubricon run`; each model writes results keyed by (run_id, item) so
-- past runs stay comparable and a bad run can be discarded wholesale.

create table public.model_runs (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  status text not null default 'running'
    check (status in ('running', 'succeeded', 'failed')),
  engine_version text,
  git_sha text,
  params jsonb,
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table public.inventory_sim_results (
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  sku text not null,
  daily_velocity_mean numeric(12, 4),
  daily_velocity_std numeric(12, 4),
  lead_time_days integer,
  on_hand_units integer,
  inbound_units integer,
  stockout_probability numeric(6, 4),
  days_of_cover numeric(8, 1),
  reorder_point integer,
  reorder_qty integer,
  safety_stock integer,
  simulations integer,
  details jsonb,
  primary key (run_id, sku)
);

create table public.elasticity_results (
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  level text not null check (level in ('sku', 'asin')),
  item_id text not null,
  status text not null
    check (status in ('ok', 'insufficient_price_variation', 'insufficient_data')),
  elasticity numeric(10, 4),
  std_err numeric(10, 4),
  r_squared numeric(6, 4),
  n_periods integer,
  price_cv numeric(8, 4),
  details jsonb,
  primary key (run_id, level, item_id)
);

create table public.ad_efficiency_results (
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  campaign_name text not null,
  status text not null check (status in ('ok', 'insufficient_data')),
  curve_model text,
  curve_params jsonb,
  current_spend numeric(12, 2),
  current_sales numeric(12, 2),
  marginal_roas numeric(10, 4),
  breakeven_spend numeric(12, 2),
  recommended_spend numeric(12, 2),
  bleed_terms jsonb,
  details jsonb,
  primary key (run_id, campaign_name)
);

create table public.margin_results (
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  sku text not null,
  asin text,
  period_start date not null,
  period_end date not null,
  units integer,
  revenue numeric(12, 2),
  amazon_fees numeric(12, 2),
  cogs numeric(12, 2),
  ad_spend_allocated numeric(12, 2),
  net_margin numeric(12, 2),
  net_margin_pct numeric(8, 4),
  forecast jsonb,
  primary key (run_id, sku, period_start)
);

alter table public.model_runs enable row level security;
alter table public.inventory_sim_results enable row level security;
alter table public.elasticity_results enable row level security;
alter table public.ad_efficiency_results enable row level security;
alter table public.margin_results enable row level security;

create policy "members read own model runs"
  on public.model_runs for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own inventory sims"
  on public.inventory_sim_results for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own elasticities"
  on public.elasticity_results for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own ad efficiency"
  on public.ad_efficiency_results for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create policy "members read own margins"
  on public.margin_results for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index model_runs_client_idx on public.model_runs (client_id, started_at desc);
