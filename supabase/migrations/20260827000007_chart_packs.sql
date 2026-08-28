-- The chart pack: model output re-cut as deliverable-shaped chart data,
-- one JSONB per run, drawn by the Desk. This is the doctrine-compliant
-- path for "show clients the math": raw model tables stay service-role
-- only; the pack carries exactly the series, bands, and thresholds the
-- Chart Book specifies — computed by the engine, never by the client.

create table public.chart_packs (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique (run_id)
);
alter table public.chart_packs enable row level security;

create policy "members read own chart packs"
  on public.chart_packs for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index chart_packs_client_idx on public.chart_packs (client_id, created_at desc);
