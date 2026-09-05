-- When the retainer actually started, and what was actually billed.
--
-- Two facts the ledger was inventing:
--
-- 1. The free-month clock ran from clients.created_at, which onboarding sets at
--    PROVISIONING — when a prospect books a call or replies TEARDOWN, before the
--    Teardown exists and before anyone said yes. terms.html §3 says the retainer
--    starts "on the day you say yes after the Teardown". The clock could expire
--    before the engagement began.
--
-- 2. fees_paid was months_elapsed x $6,000, assumed. A prospect who never
--    converted still accrued $6,000 a month in the denominator of their own ROI
--    multiple, and their desk told them they were "under three times".

alter table public.clients
  add column retainer_started_at timestamptz,
  -- Best evidence first: client_yes (recorded when they said it) beats
  -- first_invoice beats teardown_delivered beats the provisioning date.
  add column retainer_source text
    check (retainer_source in ('client_yes', 'first_invoice', 'teardown_delivered', 'manual'));

-- What Stripe says we billed, mirrored locally so the ledger's denominator is
-- observed rather than assumed, and so the client can audit it.
create table public.invoices (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references public.clients (id) on delete cascade,
  stripe_invoice_id text not null unique,
  stripe_customer_id text,
  number text,
  status text not null,                       -- draft|open|paid|void|uncollectible
  currency text not null default 'usd',
  amount_due numeric(12, 2),
  amount_paid numeric(12, 2) not null default 0,
  period_start date,
  period_end date,
  issued_at timestamptz,
  paid_at timestamptz,
  voided_at timestamptz,
  hosted_invoice_url text,
  raw jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.invoices enable row level security;

-- Clients read their own invoices. It is their money, and it is the denominator
-- of the guarantee we make them — letting them audit it is the same doctrine
-- that puts the chart pack in front of them instead of a summary.
create policy "members read own invoices"
  on public.invoices for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index invoices_client_status_idx on public.invoices (client_id, status);

create trigger invoices_set_updated_at
  before update on public.invoices
  for each row execute function public.set_updated_at();
