-- Unit economics: what one more account costs (2026-09-25).
--
-- Hubricon is one founder serving every account for a flat fee, so whether it
-- scales is arithmetic: what an account-month costs in compute, in third-party
-- usage and above all in the founder's minutes, and whether that falls as the
-- engine automates more. None of it was recorded; model_runs' started_at and
-- finished_at were the only unit of cost on file.
--
--   usage_events   One row per measured quantity of a cost driver: Anthropic
--                  tokens as the API reports them, ElevenLabs characters,
--                  Resend emails, engine seconds per account and per scheduled
--                  job. Written by engine/src/hubricon_engine/meter.py, never
--                  fatally: a failed write is dropped and the brief, the email
--                  or the sweep goes on. Quantities only (no recipient, no
--                  text), so a deleted client's rows stay, unattributed.
--   founder_time   The founder's minutes. `hubricon log <client|prospect|all>
--                  <minutes> <what>`, plus rows written only where the data
--                  already says he spent the time: a booked call at its
--                  scheduled length, the kickoff. `ref` makes each of those
--                  once. These are work notes about a client, so they go when
--                  the client does.
--   cost_config    Every price, plan fee and rate the report multiplies by,
--                  and the founder's shadow rate and working week. Seeded with
--                  placeholders, each labelled so, and never overwritten by a
--                  re-run. Editing a value makes it the founder's figure (the
--                  trigger sets basis), which is what the report then says.
--
-- Internal throughout: RLS on, no policies, service role only.

create table public.usage_events (
  id bigint generated always as identity primary key,
  occurred_at timestamptz not null default now(),
  client_id uuid references public.clients (id) on delete set null,
  prospect_id uuid references public.prospects (id) on delete set null,
  service text not null,                 -- anthropic | elevenlabs | resend | engine
  unit text not null,                    -- input_tokens | output_tokens | cache_write_tokens | cache_read_tokens
                                         -- | characters | emails | seconds
  quantity numeric(16, 3) not null check (quantity >= 0),
  item text,                             -- the model, the voice model, or the scheduled command
  component text,                        -- the code path: narrate | triage | tts | email | issue | sweep | teardown | job ...
  job text,                              -- the command it ran inside: operator | sweep | issue | watch | calibrate ...
  runner text,                           -- github_actions | local
  detail jsonb not null default '{}'::jsonb
);
alter table public.usage_events enable row level security;   -- service role only
create index usage_events_occurred_idx on public.usage_events (occurred_at);
create index usage_events_client_idx on public.usage_events (client_id, occurred_at)
  where client_id is not null;

create table public.founder_time (
  id uuid primary key default gen_random_uuid(),
  occurred_on date not null default ((now() at time zone 'America/Chicago')::date),
  client_id uuid references public.clients (id) on delete cascade,
  prospect_id uuid references public.prospects (id) on delete cascade,
  minutes numeric(8, 1) not null check (minutes >= 0 and minutes <= 1440),
  what text not null,
  source text not null default 'logged' check (source in ('logged', 'booking', 'kickoff')),
  -- logged: typed by the founder. scheduled: a booking's own length.
  -- stated: the length the site states (the 20-minute call, the 45-minute kickoff).
  basis text not null default 'logged' check (basis in ('logged', 'scheduled', 'stated')),
  ref text unique,                       -- automatic rows only: booking:<id> | kickoff:<client id>
  created_at timestamptz not null default now(),
  check (client_id is null or prospect_id is null)   -- neither = work for all accounts
);
alter table public.founder_time enable row level security;   -- service role only
create index founder_time_occurred_idx on public.founder_time (occurred_on);
create index founder_time_client_idx on public.founder_time (client_id) where client_id is not null;

create table public.cost_config (
  key text primary key,
  value numeric not null check (value >= 0),
  unit text not null,
  basis text not null default 'placeholder' check (basis in ('placeholder', 'site', 'founder')),
  note text,
  updated_at timestamptz not null default now()
);
alter table public.cost_config enable row level security;   -- service role only

create or replace function public.cost_config_touched()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- A value edited in the dashboard is the founder's figure from then on,
  -- unless the same edit changed the basis too.
  if new.value is distinct from old.value and new.basis is not distinct from old.basis then
    new.basis := 'founder';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger cost_config_touched
  before update on public.cost_config
  for each row execute function public.cost_config_touched();

-- Placeholders, not facts: list prices nobody has checked against a bill, and
-- the two lengths the site states. engine/src/hubricon_engine/economics.py
-- DEFAULTS is the same table; a test holds them in step.
insert into public.cost_config (key, value, unit, basis, note) values
  ('founder.hourly_rate_usd', 150, 'usd/hour', 'placeholder', 'the shadow price of one founder hour in cost to serve; set your own'),
  ('founder.working_hours_per_week', 50, 'hours/week', 'placeholder', 'the working week the capacity figure is computed in'),
  ('founder.booked_call_minutes', 20, 'minutes', 'site', 'a booked call whose event names no length: the 20-minute call apply.html offers'),
  ('founder.kickoff_minutes', 45, 'minutes', 'site', 'the Kickoff: 45 minutes on welcome.html and method.html'),
  ('fixed.supabase', 25, 'usd/month', 'placeholder', 'Supabase Pro list price, unverified; use the invoice'),
  ('fixed.vercel', 20, 'usd/month', 'placeholder', 'Vercel Pro, one seat, unverified'),
  ('fixed.github', 4, 'usd/month', 'placeholder', 'GitHub Pro, unverified; 0 on the free plan'),
  ('fixed.google_workspace', 7, 'usd/month', 'placeholder', 'Workspace Business Starter, one user, unverified'),
  ('fixed.calendly', 12, 'usd/month', 'placeholder', 'Calendly Standard billed monthly, unverified'),
  ('fixed.instantly', 37, 'usd/month', 'placeholder', 'Instantly Growth billed monthly, unverified'),
  ('fixed.elevenlabs', 22, 'usd/month', 'placeholder', 'ElevenLabs Creator, unverified'),
  ('fixed.resend', 0, 'usd/month', 'placeholder', 'Resend free tier, unverified'),
  ('rate.github_actions.usd_per_minute', 0.008, 'usd/minute', 'placeholder', 'a hosted Linux runner on a private repo, unverified; 0 if the repo is public'),
  ('rate.github_actions.included_minutes', 2000, 'minutes/month', 'placeholder', 'runner minutes the plan includes before any are billed, unverified'),
  ('rate.github_actions.setup_seconds_per_job', 60, 'seconds/job', 'placeholder', 'checkout and dependency install before hubricon starts, which the engine cannot see'),
  ('rate.anthropic.claude-fable-5-1.input_usd_per_mtok', 10, 'usd/1M tokens', 'placeholder', 'list price in mid-2026, unverified'),
  ('rate.anthropic.claude-fable-5-1.output_usd_per_mtok', 50, 'usd/1M tokens', 'placeholder', 'list price in mid-2026, unverified'),
  ('rate.anthropic.claude-opus-5.input_usd_per_mtok', 5, 'usd/1M tokens', 'placeholder', 'list price in mid-2026, unverified'),
  ('rate.anthropic.claude-opus-5.output_usd_per_mtok', 25, 'usd/1M tokens', 'placeholder', 'list price in mid-2026, unverified'),
  ('rate.anthropic.claude-opus-4-8.input_usd_per_mtok', 5, 'usd/1M tokens', 'placeholder', 'list price in mid-2026, unverified'),
  ('rate.anthropic.claude-opus-4-8.output_usd_per_mtok', 25, 'usd/1M tokens', 'placeholder', 'list price in mid-2026, unverified'),
  ('rate.anthropic.cache_write_multiplier', 1.25, 'x input rate', 'placeholder', 'a cache write, as a multiple of the input rate, unverified'),
  ('rate.anthropic.cache_read_multiplier', 0.1, 'x input rate', 'placeholder', 'a cache read, as a multiple of the input rate, unverified'),
  ('rate.elevenlabs.usd_per_1k_characters', 0.3, 'usd/1k characters', 'placeholder', 'characters past the plan quota, unverified'),
  ('rate.elevenlabs.included_characters', 100000, 'characters/month', 'placeholder', 'the plan quota, unverified'),
  ('rate.resend.usd_per_email', 0.0009, 'usd/email', 'placeholder', 'emails past the plan quota, unverified'),
  ('rate.resend.included_emails', 3000, 'emails/month', 'placeholder', 'the plan quota, unverified'),
  ('rate.stripe.invoicing_pct', 0.004, 'share of a paid invoice', 'placeholder', 'Stripe Invoicing, unverified'),
  ('rate.stripe.ach_pct', 0.008, 'share of a paid invoice', 'placeholder', 'ACH Direct Debit, unverified'),
  ('rate.stripe.ach_cap_usd', 5, 'usd/payment', 'placeholder', 'the ACH fee cap, unverified')
on conflict (key) do nothing;
