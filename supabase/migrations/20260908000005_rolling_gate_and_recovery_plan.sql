-- The rolling honesty gate, and the recovery-only plan.
--
-- Day 30 was the only month the guarantee covered. terms.html §3 now says our
-- invoices never run ahead of the ledger: every invoice Stripe raises is judged
-- against what the ledger has measured or identified since the retainer began,
-- and one that is not covered is voided (or credited, if already paid). The
-- decision is written on the invoice row so it is taken exactly once.
--
-- The recovery-only plan is the smaller door for the founder who will not
-- commit to $6,000 a month: no fee, a share of the reimbursements Amazon
-- actually paid on claims we filed, invoiced in arrears, nothing else. It is
-- a plan on the client row, not a second product: the same intake, the same
-- ledger, the same proof and the same ask.

alter table public.invoices
  add column gate_decision text check (gate_decision in ('covered', 'waived')),
  add column gate_decided_at timestamptz,
  add column gate_value numeric(12, 2),      -- measured + identified at the decision
  add column gate_fees numeric(12, 2),       -- billed through this invoice, at the decision
  add column gate_note text;                 -- 'voided' | 'credited', and why

alter table public.clients
  add column plan text not null default 'retainer' check (plan in ('retainer', 'recovery')),
  add column recovery_share numeric(5, 4) not null default 0.25;

create table public.recovery_invoices (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  period_start date not null,
  period_end date not null,
  recovered_usd numeric(12, 2) not null,     -- what Amazon paid on our claims in the period
  share numeric(5, 4) not null,
  amount_usd numeric(12, 2) not null,        -- recovered × share, what was invoiced
  n_claims integer not null default 0,
  stripe_invoice_id text unique,
  hosted_invoice_url text,
  created_at timestamptz not null default now(),
  unique (client_id, period_start, period_end)
);
alter table public.recovery_invoices enable row level security;

create policy "members read own recovery invoices"
  on public.recovery_invoices for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

-- Each paid claim is invoiced once, and says which invoice carried it.
alter table public.recovery_claims
  add column recovery_invoice_id uuid references public.recovery_invoices (id) on delete set null;

alter table public.client_touches drop constraint if exists client_touches_kind_check;
alter table public.client_touches add constraint client_touches_kind_check
  check (kind in ('welcome', 'nudge', 'files', 'teardown_ready', 'consent_ask', 'referral_credit', 'downsell'));
