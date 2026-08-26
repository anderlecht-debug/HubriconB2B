-- The always-on layer: alerts produced by scheduled sweeps, shown in the
-- client portal and optionally emailed. Factual model outputs only
-- (stockout risk, margin flips, Buy Box suppression) — directives stay
-- operator-gated.

create table public.alerts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  run_id uuid references public.model_runs (id) on delete set null,
  severity text not null check (severity in ('info', 'warning', 'critical')),
  module text not null
    check (module in ('inventory', 'pricing', 'advertising', 'margin', 'system')),
  message text not null,
  emailed_at timestamptz,
  created_at timestamptz not null default now()
);
alter table public.alerts enable row level security;

create policy "members read own alerts"
  on public.alerts for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index alerts_client_created_idx on public.alerts (client_id, created_at desc);
