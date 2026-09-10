-- The 60-second Teardown (/teardown): one row per run a visitor chose to keep
-- by leaving an email, and a prospect source that marks where they came from.
-- The page computes everything in the browser off /ratecard.json; the API
-- route (api/quick.js) only prefills from harvest_products, computes the
-- category benchmark, and records the capture. The capture creates a prospect
-- at `wants_teardown`, which the hourly operator already turns into a
-- provisioned client with the private upload page emailed — that is the deep
-- follow-up, and no new job was needed for it.
-- Internal: RLS on, no policies, service role only.

create table public.tool_runs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  email text,
  first_name text,
  platform text not null default 'amazon' check (platform in ('amazon', 'shopify')),
  asin text,
  inputs jsonb not null default '{}'::jsonb,
  summary jsonb not null default '{}'::jsonb,
  prospect_id uuid references public.prospects (id) on delete set null,
  referer text,
  ua text
);
alter table public.tool_runs enable row level security;
create index tool_runs_email_idx on public.tool_runs (email);
create index tool_runs_created_idx on public.tool_runs (created_at desc);

alter table public.prospects drop constraint prospects_source_check;
alter table public.prospects add constraint prospects_source_check
  check (source in ('instantly_list', 'supersearch', 'inbound', 'manual', 'founder', 'partner',
                    'post', 'teardown', 'spn', 'referral', 'forum', 'tool'));
