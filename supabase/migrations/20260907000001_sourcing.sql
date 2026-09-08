-- Shopify lead sourcing: the funnel in front of harvest_sellers.
--
-- `harvest_sellers` stays the prospect table of record — the cold engine reads
-- it, the teardown queue keys on it, and `outreach_sends` references it. What
-- it is not is a place to keep a hundred thousand domains that might be a
-- store. Discovery is millions of rows wide and about 2% of them survive
-- qualification (LEAD_SOURCING.md §0), so the funnel gets its own table and
-- only what earns a contact is promoted across.
--
-- The promotion writes status 'candidate' on purpose: harvest/run.py::push
-- selects `enriched` rows and pushes them into the auto-enrolled Instantly
-- list, and the hourly operator runs with COLD_DRY_RUN=false. A promoted row
-- at `enriched` would be cold-emailed with nobody having approved it, which
-- is the one thing this build was told not to do.
--
-- Service role only, like every other internal engine table: RLS on, no
-- policies. Nothing here is ever read by a browser.

create table if not exists public.sourcing_prospects (
  domain              text primary key,
  myshopify_handle    text,
  brand               text,

  -- discovery
  tranco_rank         integer,
  is_shopify          boolean not null default false,
  detected_via        text check (detected_via in ('dns', 'http', 'search')),

  -- qualification, all of it computed from /products.json and the homepage
  products            integer,
  asp                 numeric(12,2),
  median_price        numeric(12,2),
  discount_share      numeric(6,3),
  compare_at_share    numeric(6,3),
  velocity_days       numeric(10,1),
  -- The widest step between two adjacent prices in the catalogue. Not a
  -- finding: an AOV gap cannot be priced off a published rate card, and
  -- cold/findings.py refuses anything it cannot price. It is a hook for a
  -- human, so it lives on the sheet rather than in a teardown.
  ladder_gap_ratio    numeric(8,2),
  stack               jsonb not null default '{}'::jsonb,
  plus_signals        boolean,
  est_annual          numeric(14,2),
  score               numeric(8,2),
  score_parts         jsonb not null default '{}'::jsonb,

  -- contact. `email_confidence` carries the whole sending policy: 'published'
  -- means the address was found on a page the brand controls and may be
  -- written to; 'pattern' means it was constructed and may not, because
  -- Shopify merchants run Google Workspace catch-all and there is no paid
  -- verification in this build to tell a real mailbox from one.
  first_name          text,
  last_name           text,
  email               text,
  email_confidence    text check (email_confidence in ('published', 'pattern')),
  role_inbox          boolean not null default false,
  contact_source      text,
  linkedin_url        text,
  business_name       text,
  address             text,
  city                text,
  state               text,
  -- What the store says about where it is. The engine is US-only and the cold
  -- engine suppresses EU/UK/EEA/CH, so this is the cheapest disqualifier there
  -- is and `qualify` asks it first.
  country             text,
  currency            text,

  status              text not null default 'discovered'
    check (status in ('discovered', 'not_shopify', 'qualified', 'disqualified',
                      'contacted_found', 'no_contact', 'promoted', 'sheet_only')),
  note                text,
  first_seen          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

alter table public.sourcing_prospects enable row level security;

create index if not exists sourcing_prospects_status_idx on public.sourcing_prospects (status);
create index if not exists sourcing_prospects_score_idx on public.sourcing_prospects (score desc);
create index if not exists sourcing_prospects_rank_idx on public.sourcing_prospects (tranco_rank);

-- Where a promoted row says it came from. Written idempotently because the
-- constraint has been replaced twice already (wayback, then founder).
alter table public.harvest_sellers drop constraint if exists harvest_sellers_source_check;
alter table public.harvest_sellers
  add constraint harvest_sellers_source_check
  check (source in ('bestsellers', 'wayback', 'shopify', 'founder', 'sourcing'));

-- The anchor price, kept beside the price. `permanent_discount` needs the pair
-- and nothing else in the schema holds a compare-at; Amazon rows leave it null,
-- which is what the detector reads as "no claim available here".
alter table public.harvest_products add column if not exists compare_at_price numeric(12,2);
