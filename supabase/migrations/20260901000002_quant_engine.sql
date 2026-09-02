-- The quantitative engine's second wave: recovery, anomaly, forecast,
-- risk, inventory economics, the Health Score and the value ledger.
--
-- Posture is unchanged from the engine lockdown: every raw model payload
-- is service-role only (RLS on, no policies). The Desk reads only the
-- chart pack and the desk_* RPCs, which carry deliverable-shaped numbers.

-- One JSONB payload per (run, model). The new models are dict-shaped and
-- evolve quickly; a typed table per model would mean a migration per
-- tweak. Payloads are versioned by run_id and git_sha on model_runs.
create table public.model_outputs (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.model_runs (id) on delete cascade,
  client_id uuid not null references public.clients (id) on delete cascade,
  model text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique (run_id, model)
);
alter table public.model_outputs enable row level security;
create index model_outputs_client_idx on public.model_outputs (client_id, model, created_at desc);

-- Reimbursement claims have a life of their own across runs: detected by
-- the sweep, filed by the operator, paid or denied by Amazon. Money lands
-- on the value ledger only when a claim is marked paid with the amount
-- Amazon actually sent.
create table public.recovery_claims (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  claim_key text not null,
  claim_type text not null,
  sku text,
  fnsku text,
  asin text,
  order_id text,
  event_date date,
  units integer,
  unit_value numeric(12, 2),
  value numeric(12, 2),
  value_basis text,
  p_approve numeric(6, 4),
  expected_value numeric(12, 2),
  eligible_from date,
  deadline date,
  status text not null default 'detected'
    check (status in ('detected', 'filed', 'paid', 'denied', 'expired', 'dismissed')),
  case_id text,
  filed_at timestamptz,
  paid_amount numeric(12, 2),
  paid_at timestamptz,
  denied_at timestamptz,
  notes text,
  evidence jsonb,
  first_seen_run_id uuid references public.model_runs (id) on delete set null,
  last_seen_run_id uuid references public.model_runs (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (client_id, claim_key)
);
alter table public.recovery_claims enable row level security;
create index recovery_claims_client_status_idx on public.recovery_claims (client_id, status, deadline);
create trigger recovery_claims_set_updated_at
  before update on public.recovery_claims
  for each row execute function public.set_updated_at();

-- The value ledger's price side: flat monthly fee after the free month.
alter table public.clients
  add column monthly_fee_usd numeric(12, 2) not null default 6000,
  add column free_months integer not null default 1;

-- New alert and directive modules. (The cash-horizon alert already emits
-- module 'cash', which the original check would have rejected.)
alter table public.alerts drop constraint alerts_module_check;
alter table public.alerts add constraint alerts_module_check
  check (module in ('inventory', 'pricing', 'advertising', 'margin', 'system', 'cash', 'recovery', 'anomaly'));

alter table public.directives drop constraint directives_module_check;
alter table public.directives add constraint directives_module_check
  check (module in ('inventory', 'pricing', 'advertising', 'margin', 'general', 'recovery'));

alter table public.initiatives drop constraint initiatives_module_check;
alter table public.initiatives add constraint initiatives_module_check
  check (module in ('inventory', 'pricing', 'advertising', 'margin', 'general', 'recovery'));
