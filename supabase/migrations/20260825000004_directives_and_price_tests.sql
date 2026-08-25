-- The Decision Ledger: every directive Hubricon issues is recorded with an
-- expected dollar impact, approved or declined by the client in the portal,
-- and measured against baseline on a later cycle. The cumulative measured
-- impact is the retention case, rebuilt automatically.

create table public.directives (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  run_id uuid references public.model_runs (id) on delete set null,
  module text not null
    check (module in ('inventory', 'pricing', 'advertising', 'margin', 'general')),
  action_text text not null,
  expected_impact_usd numeric(12, 2),
  status text not null default 'draft'
    check (status in ('draft', 'issued', 'approved', 'declined', 'done')),
  measured_impact_usd numeric(12, 2),
  measured_at timestamptz,
  measurement_notes text,
  responded_at timestamptz,
  responded_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  issued_at timestamptz
);
alter table public.directives enable row level security;

-- Drafts are operator-private; clients see directives only once issued.
create policy "members read own issued directives"
  on public.directives for select to authenticated
  using (
    status <> 'draft'
    and client_id in (select client_id from public.client_users where user_id = (select auth.uid()))
  );

create index directives_client_status_idx on public.directives (client_id, status);

-- Price-testing program: designed tests with Buy Box share tracked through
-- them, feeding the elasticity model with deliberate price variation.
create table public.price_tests (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  sku text not null,
  asin text,
  baseline_price numeric(12, 2) not null,
  test_price numeric(12, 2) not null,
  start_date date,
  end_date date,
  buy_box_share_before numeric(6, 2),
  buy_box_share_during numeric(6, 2),
  status text not null default 'planned'
    check (status in ('planned', 'running', 'completed', 'aborted')),
  outcome_notes text,
  created_at timestamptz not null default now()
);
alter table public.price_tests enable row level security;

create policy "members read own price tests"
  on public.price_tests for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index price_tests_client_status_idx on public.price_tests (client_id, status);

-- The one write clients can perform: answering an issued directive.
-- Scoped by membership, valid only on 'issued', records who answered.
create or replace function public.respond_to_directive(p_directive_id uuid, p_approve boolean)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.directives d
     set status = case when p_approve then 'approved' else 'declined' end,
         responded_at = now(),
         responded_by = (select auth.uid())
   where d.id = p_directive_id
     and d.status = 'issued'
     and d.client_id in (
       select client_id from public.client_users where user_id = (select auth.uid())
     );
  get diagnostics v_count = row_count;
  return v_count > 0;
end;
$$;

revoke execute on function public.respond_to_directive(uuid, boolean) from public, anon;
grant execute on function public.respond_to_directive(uuid, boolean) to authenticated, service_role;
