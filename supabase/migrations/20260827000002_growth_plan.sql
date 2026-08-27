-- The Growth Plan: the client's own 90-day operating plan becomes the
-- product's spine. Targets are budget-vs-actual, initiatives are the
-- carried roadmap, and every directive files into the initiative it
-- executes — approving a directive is executing the plan.

create table public.plans (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  label text not null,
  starts_on date not null,
  ends_on date not null,
  baseline_net numeric(12, 2),
  baseline_revenue numeric(12, 2),
  baseline_margin_pct numeric(8, 4),
  target_net numeric(12, 2),
  target_revenue numeric(12, 2),
  target_margin_pct numeric(8, 4),
  status text not null default 'active'
    check (status in ('active', 'completed', 'superseded')),
  created_at timestamptz not null default now()
);
alter table public.plans enable row level security;

create policy "members read own plans"
  on public.plans for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create table public.initiatives (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  plan_id uuid not null references public.plans (id) on delete cascade,
  title text not null,
  thesis text,
  module text not null
    check (module in ('inventory', 'pricing', 'advertising', 'margin', 'general')),
  expected_impact_usd numeric(12, 2),
  status text not null default 'active'
    check (status in ('planned', 'active', 'done', 'dropped')),
  sort integer not null default 0,
  created_at timestamptz not null default now()
);
alter table public.initiatives enable row level security;

create policy "members read own initiatives"
  on public.initiatives for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

alter table public.directives
  add column initiative_id uuid references public.initiatives (id) on delete set null;

create index plans_client_status_idx on public.plans (client_id, status);
create index initiatives_plan_idx on public.initiatives (plan_id, sort);
