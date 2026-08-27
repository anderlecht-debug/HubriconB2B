-- Cash-flow horizon (CF-VaR): the engine simulates the client's daily cash
-- position over the next 90 days — Amazon's 14-day payout cycle in, fixed
-- costs and supplier PO wires out — and stores the percentile cone plus the
-- probability the account dips below zero. Inputs the client states (cash
-- on hand, monthly fixed costs) live on the client row; results follow the
-- engine-lockdown posture: RLS enabled, no policies, service role only.

alter table public.clients
  add column cash_on_hand numeric(12, 2),
  add column cash_as_of date,
  add column monthly_fixed_costs numeric(12, 2);

create table public.cash_horizon_results (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  horizon_days integer not null,
  n_paths integer not null,
  starting_cash numeric(12, 2) not null,
  monthly_fixed_costs numeric(12, 2) not null,
  p_ruin numeric(8, 4) not null,
  min_p5 numeric(12, 2),
  min_p5_day integer,
  min_median numeric(12, 2),
  details jsonb,
  created_at timestamptz not null default now(),
  unique (run_id)
);
alter table public.cash_horizon_results enable row level security;

create index cash_horizon_client_idx on public.cash_horizon_results (client_id, created_at desc);
