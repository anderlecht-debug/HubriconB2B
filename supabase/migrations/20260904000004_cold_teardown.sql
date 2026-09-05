-- The cold engine: an unsolicited Profit Teardown built from public pages.
--
-- COLD_ENGINE.md §3 specifies a `prospects` table. This repo already has one —
-- the funnel's, keyed on the email address of somebody who replied to a cold
-- campaign — and a second table with the same name would be a permanent source
-- of confusion. The cold engine's prospect is a harvested company, which is
-- `harvest_sellers`, keyed on seller_id (the myshopify handle on the Shopify
-- side). So every table here carries `prospect_key` referencing that, and the
-- columns §3 asks for that harvest_sellers lacked (jurisdiction, contact
-- provenance, suppression reason) are added to it below.
--
-- Internal throughout: RLS on, no policies, service role only. A prospect is
-- not a client and must never be visible in the portal.

-- -- the prospect side ------------------------------------------------------------

alter table public.harvest_sellers
  add column if not exists jurisdiction text,          -- resolved country; drives the GDPR path
  add column if not exists contact_source text,        -- where the address came from, for the record
  add column if not exists suppressed_reason text;

-- Every read of a product page, kept rather than overwritten.
--
-- harvest_products holds one row per ASIN and the crawl updates it in place, so
-- the price and rank it saw last week are gone. That is the whole reason the
-- price-history detectors in COLD_ENGINE.md §2 need a paid provider. The crawl
-- already passes the same best-selling listings twice a day; keeping what it
-- saw turns those passes into the price and rank series Keepa would have sold
-- us, for nothing, about a fortnight from the first run.
create table if not exists public.harvest_product_observations (
  id bigint generated always as identity primary key,
  asin text not null,
  platform text not null default 'amazon' check (platform in ('amazon', 'shopify')),
  seller_id text,
  price numeric(12, 2),
  bsr integer,
  reviews integer,
  weight_oz numeric(10, 3),
  in_stock boolean,
  seen_on date not null default (now() at time zone 'utc')::date,
  seen_at timestamptz not null default now(),
  unique (asin, seen_on)                               -- one row a day; re-reads update it
);
alter table public.harvest_product_observations enable row level security;
create index if not exists harvest_obs_asin_idx
  on public.harvest_product_observations (asin, seen_on desc);
create index if not exists harvest_obs_seller_idx
  on public.harvest_product_observations (seller_id);

-- -- the model run ----------------------------------------------------------------

create table if not exists public.cold_runs (
  id uuid primary key default gen_random_uuid(),
  prospect_key text not null references public.harvest_sellers (seller_id) on delete cascade,
  findings jsonb not null default '[]'::jsonb,         -- everything detected, with its reason
  selected_finding jsonb,                              -- null when nothing cleared the bar
  rejected jsonb not null default '[]'::jsonb,         -- why each other finding lost
  confidence numeric(5, 4),
  dollars_low numeric(12, 2),
  dollars_high numeric(12, 2),
  engine_version text not null,
  snapshot jsonb,                                      -- the normalised inputs, for reproduction
  cost_usd numeric(10, 4) not null default 0,
  created_at timestamptz not null default now()
);
alter table public.cold_runs enable row level security;
create index if not exists cold_runs_prospect_idx on public.cold_runs (prospect_key, created_at desc);

-- -- the artefact -----------------------------------------------------------------

create table if not exists public.teardowns (
  id uuid primary key default gen_random_uuid(),
  prospect_key text not null references public.harvest_sellers (seller_id) on delete cascade,
  cold_run_id uuid not null references public.cold_runs (id) on delete cascade,
  token text not null unique,                          -- url-safe, served at /t/<token>
  html text not null,                                  -- rendered once; the founder reviews this
  subject text,
  body text,                                           -- the email, for the founder to send
  script text,                                         -- the 90-second narration (Phase 5)
  status text not null default 'draft'
    check (status in ('draft', 'approved', 'rejected', 'sent', 'expired')),
  review_note text,                                    -- why the founder said no, in his words
  reviewed_at timestamptz,
  published_at timestamptz,
  expires_at timestamptz not null,
  video_path text,
  created_at timestamptz not null default now()
);
alter table public.teardowns enable row level security;
create index if not exists teardowns_status_idx on public.teardowns (status, created_at desc);
create index if not exists teardowns_prospect_idx on public.teardowns (prospect_key);

-- -- sending, and the record that makes the frequency rules real -------------------

create table if not exists public.outreach_sends (
  id uuid primary key default gen_random_uuid(),
  prospect_key text not null references public.harvest_sellers (seller_id) on delete cascade,
  teardown_id uuid references public.teardowns (id) on delete set null,
  channel text not null default 'email' check (channel in ('email', 'linkedin')),
  sending_domain text,
  template_id text not null,
  subject text,
  recipient_email text,
  jurisdiction text,
  basis text,                                          -- the GDPR record: why this person, on what basis
  provider_message_id text,
  sent_at timestamptz not null default now()
);
alter table public.outreach_sends enable row level security;
create index if not exists outreach_sends_prospect_idx on public.outreach_sends (prospect_key, sent_at desc);
create index if not exists outreach_sends_domain_idx on public.outreach_sends (sending_domain, sent_at desc);

create table if not exists public.teardown_events (
  id bigint generated always as identity primary key,
  teardown_id uuid references public.teardowns (id) on delete cascade,
  send_id uuid references public.outreach_sends (id) on delete cascade,
  kind text not null check (kind in ('delivered', 'open', 'click', 'page_view', 'cta_click',
                                     'video_watch', 'reply', 'bounce', 'complaint', 'unsubscribe')),
  detail jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);
alter table public.teardown_events enable row level security;
create index if not exists teardown_events_teardown_idx on public.teardown_events (teardown_id, kind);

-- Checked on every send, with no bypass path (COLD_ENGINE.md §2.3).
create table if not exists public.suppressions (
  id uuid primary key default gen_random_uuid(),
  email text,
  domain text,
  reason text not null,
  created_at timestamptz not null default now()
);
alter table public.suppressions enable row level security;
create unique index if not exists suppressions_email_idx
  on public.suppressions (lower(email)) where email is not null;
create unique index if not exists suppressions_domain_idx
  on public.suppressions (lower(domain)) where domain is not null;
