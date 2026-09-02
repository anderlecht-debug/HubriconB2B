-- The funnel: prospects (cold outreach through Instantly), their replies,
-- Calendly bookings parsed from the founder's inbox, and an event log the
-- operator reads and writes. Everything here is internal — RLS is enabled
-- with no policies, so only the service role (the engine, the GitHub
-- operator) and the project owner (the cloud routine, through the
-- Supabase connector) can touch it. Clients never see any of this.

create table public.prospects (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  first_name text,
  last_name text,
  company_name text,
  website text,
  source text not null default 'instantly_list'
    check (source in ('instantly_list', 'supersearch', 'inbound', 'manual')),
  instantly_lead_id text,
  instantly_campaign_id text,
  status text not null default 'queued'
    check (status in ('queued', 'contacted', 'replied', 'interested', 'wants_teardown',
                      'booked', 'client', 'not_now', 'not_interested', 'unsubscribed',
                      'bounced', 'dq')),
  client_id uuid references public.clients (id) on delete set null,
  fit_notes text,
  follow_up_at date,
  last_reply_at timestamptz,
  last_event_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.prospects enable row level security;
create index prospects_status_idx on public.prospects (status);
create trigger prospects_set_updated_at
  before update on public.prospects
  for each row execute function public.set_updated_at();

-- One row per email in or out of a prospect thread. Inbound rows arrive
-- from Instantly's unibox with reply_status 'pending_review'; triage
-- (rules, Claude in the Action, or the cloud routine) writes a category
-- and a draft, flips it to 'approved', and the next operator run sends it
-- through Instantly from the same mailbox that started the thread.
create table public.prospect_messages (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references public.prospects (id) on delete cascade,
  direction text not null check (direction in ('in', 'out')),
  instantly_email_id text unique,
  instantly_thread_id text,
  eaccount text,
  subject text,
  body text,
  category text
    check (category is null or category in ('interested', 'wants_teardown', 'question', 'not_now',
                                            'not_interested', 'unsubscribe', 'ooo', 'bounce', 'other')),
  triaged_by text check (triaged_by is null or triaged_by in ('rules', 'claude', 'routine')),
  draft_reply text,
  reply_status text not null default 'none'
    check (reply_status in ('none', 'pending_review', 'approved', 'sent', 'skipped', 'failed')),
  received_at timestamptz,
  sent_at timestamptz,
  created_at timestamptz not null default now()
);
alter table public.prospect_messages enable row level security;
create index prospect_messages_review_idx on public.prospect_messages (reply_status)
  where reply_status in ('pending_review', 'approved');
create index prospect_messages_prospect_idx on public.prospect_messages (prospect_id, created_at desc);

-- Calendly bookings, parsed from "New Event" notification emails by the
-- cloud routine. source_message_id is the Gmail message id, which makes
-- re-reading the inbox idempotent. The operator provisions qualified,
-- non-test bookings into clients and sends the welcome email.
create table public.bookings (
  id uuid primary key default gen_random_uuid(),
  source_message_id text not null unique,
  event_type text,
  invitee_name text,
  invitee_email text not null,
  starts_at timestamptz,
  answers jsonb not null default '{}'::jsonb,
  is_test boolean not null default false,
  qualified boolean,
  dq_reason text,
  client_id uuid references public.clients (id) on delete set null,
  provisioned_at timestamptz,
  welcome_sent_at timestamptz,
  created_at timestamptz not null default now()
);
alter table public.bookings enable row level security;
create index bookings_unprovisioned_idx on public.bookings (created_at)
  where provisioned_at is null;

-- Append-only log every operator pass writes to; the digest and the
-- scoreboard read it. processed_at lets one component leave work for
-- another (the routine parses, the Action sends).
create table public.funnel_events (
  id bigint generated always as identity primary key,
  kind text not null,
  prospect_id uuid references public.prospects (id) on delete set null,
  client_id uuid references public.clients (id) on delete set null,
  booking_id uuid references public.bookings (id) on delete set null,
  payload jsonb not null default '{}'::jsonb,
  note text,
  occurred_at timestamptz not null default now(),
  processed_at timestamptz
);
alter table public.funnel_events enable row level security;
create index funnel_events_kind_idx on public.funnel_events (kind, occurred_at desc);

-- Small key/value store for cursors and ids the operator must remember
-- between runs (the Instantly campaign id, the last unibox timestamp…).
create table public.operator_state (
  key text primary key,
  value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.operator_state enable row level security;

-- Onboarding emails the operator has already sent per client, so a nudge
-- goes out once, not hourly.
create table public.client_touches (
  client_id uuid not null references public.clients (id) on delete cascade,
  kind text not null check (kind in ('welcome', 'nudge', 'files', 'teardown_ready')),
  sent_at timestamptz not null default now(),
  primary key (client_id, kind)
);
alter table public.client_touches enable row level security;

-- The product-market-fit scoreboard. Internal addresses and the dry-run
-- workspace are excluded so the founder's own test bookings never count.
create or replace function public.pmf_scoreboard()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with real_clients as (
    select * from public.clients
    where contact_email not like '%@hubricon.internal'
      and contact_email not like '%@hubricon.com'
      and contact_email not like '%@gethubricon.com'
  ),
  paid as (
    select * from real_clients where status in ('active', 'past_due') and stripe_customer_id is not null
  ),
  renewed as (
    -- past the free month(s) and still active: the first real retention signal
    select * from paid
    where status = 'active'
      and now() > created_at + make_interval(months => coalesce(free_months, 1) + 1)
  )
  select jsonb_build_object(
    'prospects_total',    (select count(*) from public.prospects),
    'contacted',          (select count(*) from public.prospects where status <> 'queued'),
    'replied',            (select count(*) from public.prospects where last_reply_at is not null),
    'interested',         (select count(*) from public.prospects
                            where status in ('interested', 'wants_teardown', 'booked', 'client')),
    'unsubscribed',       (select count(*) from public.prospects where status = 'unsubscribed'),
    'bookings',           (select count(*) from public.bookings where not is_test),
    'bookings_qualified', (select count(*) from public.bookings where not is_test and qualified),
    'clients_onboarding', (select count(*) from real_clients where status = 'pending'),
    'teardowns_delivered',(select count(*) from public.briefings b
                            join real_clients c on c.id = b.client_id
                            where b.issue_number = 1),
    'paid',               (select count(*) from paid),
    'renewed',            (select count(*) from renewed),
    'churned',            (select count(*) from real_clients where status = 'churned'),
    'pmf_bar_renewed',    3,
    'pmf_reached',        (select count(*) from renewed) >= 3,
    'as_of',              now()
  );
$$;

revoke execute on function public.pmf_scoreboard() from public, anon, authenticated;
grant execute on function public.pmf_scoreboard() to service_role;
