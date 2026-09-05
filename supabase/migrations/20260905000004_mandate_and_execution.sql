-- The standing mandate, and proof that the work was actually done.
--
-- welcome.html §Step 2: "Then we set your standing mandate. That's where you
-- decide which fixes we make without asking, and exactly where your veto sits."
-- terms.html §6 states the default bounds. Neither was ever stored, so the
-- "mandate" a directive claimed to be inside was a constant in Python rather
-- than something this client agreed to.
--
-- And welcome.html promises "Week 1 — first fixes go live in your account",
-- with nothing anywhere recording that they had.

create table public.mandates (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  module text not null
    check (module in ('pricing', 'advertising', 'inventory', 'margin', 'recovery', 'general')),
  -- What we may do without asking, in this module.
  standing boolean not null default false,
  -- The bound, in the module's own units: 0.05 = five percent per cycle for
  -- pricing. NULL means "no numeric bound, the module's default applies".
  bound numeric(12, 4),
  bound_note text,
  -- How long the client gets to say no before a standing item goes ahead.
  veto_hours integer not null default 72 check (veto_hours >= 24),
  agreed_at timestamptz not null default now(),
  agreed_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (client_id, module)
);
alter table public.mandates enable row level security;

-- The client reads what they agreed to. They cannot edit it here — a mandate
-- changes on a call, not in a form.
create policy "members read own mandate"
  on public.mandates for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create trigger mandates_set_updated_at
  before update on public.mandates
  for each row execute function public.set_updated_at();

-- The daily Buy Box reading. index.html, welcome.html and terms.html §6 all
-- promise Buy Box share (or Shopify conversion) is "watched daily" during a
-- price test; the only reading that ever existed was a single hand-typed
-- number on the price_test row, read once a week by the sweep.
create table public.price_test_watch (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  price_test_id uuid not null references public.price_tests (id) on delete cascade,
  observed_on date not null,
  buy_box_share numeric(6, 2),
  conversion_rate numeric(8, 4),
  note text,
  created_at timestamptz not null default now(),
  unique (price_test_id, observed_on)
);
alter table public.price_test_watch enable row level security;

create policy "members read own price test watch"
  on public.price_test_watch for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index price_test_watch_test_idx on public.price_test_watch (price_test_id, observed_on desc);

-- Day 30: the guarantee, enforced by the code that writes the invoice.
--
-- Eight surfaces including terms.html §3 promise "if we don't find you more
-- than we cost, you walk away owing nothing". Nothing created an invoice at
-- all (scripts/stripe-setup.mjs only PRINTS the call for a human to run), so
-- the promise was kept by remembering. Billing now starts in the same pass
-- that checks the ledger, and only when it clears.
alter table public.clients
  add column stripe_subscription_id text unique,
  add column billing_decided_at timestamptz,
  add column billing_decision text
    check (billing_decision in ('cleared', 'short', 'waived'));

-- The stated price of the free month: terms.html §9 and welcome.html both say
-- it is a testimonial plus permission to publish anonymised results. It was
-- the one commitment on either side that nothing tracked.
create table public.consents (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  kind text not null check (kind in ('testimonial', 'anonymised_results', 'named_results')),
  granted boolean,
  asked_at timestamptz not null default now(),
  answered_at timestamptz,
  note text,
  unique (client_id, kind)
);
alter table public.consents enable row level security;

create policy "members read own consents"
  on public.consents for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

-- The four dated commitments in privacy.html and terms.html that had no code
-- behind them: deletion within 30 days, a DSAR answer within 7, breach notice
-- within 72 hours, and 14 days' notice of a terms change. A promise with a
-- deadline and no timer is a promise kept by luck.
create table public.data_requests (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references public.clients (id) on delete set null,
  requester_email text,
  kind text not null
    check (kind in ('deletion', 'access', 'correction', 'breach_notice', 'terms_notice')),
  note text,
  opened_at timestamptz not null default now(),
  due_at timestamptz not null,
  closed_at timestamptz,
  outcome text
);
alter table public.data_requests enable row level security;   -- service role only

create index data_requests_open_idx on public.data_requests (due_at) where closed_at is null;

-- The desk's "request your export" control. An RPC rather than a table insert
-- policy, so the client cannot set their own due date, kind or client_id —
-- the same shape as respond_to_directive, which is the only other client write
-- in the system. Re-requesting while one is open is a no-op rather than a
-- second row, because a client clicking twice is not two requests.
create or replace function public.request_data_export()
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_client uuid;
begin
  select client_id into v_client
    from public.client_users where user_id = (select auth.uid()) limit 1;
  if v_client is null then
    return false;
  end if;
  if exists (select 1 from public.data_requests
              where client_id = v_client and kind = 'access' and closed_at is null) then
    return true;
  end if;
  insert into public.data_requests (client_id, requester_email, kind, note, due_at)
  select v_client, c.contact_email, 'access', 'Requested from the desk', now() + interval '7 days'
    from public.clients c where c.id = v_client;
  return true;
end;
$$;

revoke execute on function public.request_data_export() from public, anon;
grant execute on function public.request_data_export() to authenticated, service_role;
