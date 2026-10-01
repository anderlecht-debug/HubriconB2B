-- The network: every consenting account makes every account safer (2026-09-25).
--
-- A platform-wide change (an Amazon fee) that shows up in several accounts at
-- once is declared by engine/src/hubricon_engine/fleet.py and announced to
-- every client it applies to, sooner and with fewer false alarms than one
-- account's own sweep can manage. terms.html §10 says we never use one client's
-- data to advise another, so this needs a consent of its own, asked on the same
-- private /say page as the others, opt-in and withdrawable. Four things:
--
--   consents.kind 'network'        the consent. Only clients who granted it
--                                  (and have not withdrawn it) are read as
--                                  sources, by fleet.py and by `hubricon book`.
--   alerts.module 'network'        the alert a recipient reads in the portal.
--   public.platform_changes        each detected change: fee type, direction,
--                                  window, how many accounts agree, the pooled
--                                  ratio and its band, p and q, status. An
--                                  aggregate across accounts; never a figure
--                                  of any one of them, never a name, SKU or
--                                  ASIN. Service role only.
--   alerts.platform_change_id      one change is announced once per client:
--                                  the unique index makes a second announcement
--                                  an error rather than a habit.
--
-- The portal needs nothing new: the alert row it already reads under "members
-- read own alerts" carries the words. Additive; nothing existing changes
-- meaning. Not applied by the commit that adds it.

-- 1. The consent.
alter table public.consents drop constraint if exists consents_kind_check;
alter table public.consents add constraint consents_kind_check
  check (kind in ('testimonial', 'anonymised_results', 'named_results', 'calibration', 'network'));

-- 2. The alert module.
alter table public.alerts drop constraint if exists alerts_module_check;
alter table public.alerts add constraint alerts_module_check
  check (module in ('inventory', 'pricing', 'advertising', 'margin', 'system', 'cash', 'recovery', 'anomaly',
                    'network'));

-- 3. What the network declared, and what it is watching.
--
-- status:  declared         at least min_accounts agree inside the window and
--                           the agreement clears the fleet's false-discovery
--                           level; announced
--          not_significant  enough accounts agree, but that many could agree
--                           by coincidence; recorded, no size, nobody told
--          insufficient_accounts
--                           below the floor; the engine prints it and writes
--                           no row, and a row that ever says it carries no
--                           number
create table if not exists public.platform_changes (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('amazon', 'shopify')),
  kind text not null,                   -- the fee type, e.g. fba_fee_per_unit
  label text not null,                  -- the fee type in words
  direction text not null check (direction in ('up', 'down')),
  onset date not null,                  -- the agreeing accounts' median onset
  window_start date not null,
  window_end date not null,
  n_accounts integer not null check (n_accounts >= 0),     -- accounts that agree (N >= min_accounts)
  n_eligible integer not null check (n_eligible >= 0),     -- consenting accounts carrying the fee type
  min_accounts integer not null,
  pooled_ratio numeric,                 -- median of the agreeing accounts' after/before ratios
  ratio_low numeric,                    -- 90% band from resampling those accounts
  ratio_high numeric,
  p_value numeric,                      -- P(that many agree by coincidence), Poisson-binomial
  q_value numeric,                      -- Benjamini–Hochberg across the pass's (fee type, direction) tests
  fdr_q numeric not null,
  n_tests integer not null,
  alpha_account numeric not null,       -- each account's own false-alarm bar
  status text not null
    check (status in ('declared', 'not_significant', 'insufficient_accounts')),
  basis text,
  first_declared_at timestamptz,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  -- a size is stated only for a change that was declared
  constraint platform_changes_size_only_when_declared
    check (status = 'declared' or (pooled_ratio is null and ratio_low is null and ratio_high is null)),
  -- below the floor, no number at all
  constraint platform_changes_refusal_carries_no_number
    check (status <> 'insufficient_accounts' or (p_value is null and q_value is null)),
  constraint platform_changes_floor
    check (status = 'insufficient_accounts' or n_accounts >= min_accounts)
);
alter table public.platform_changes enable row level security;   -- service role only
create index if not exists platform_changes_lookup_idx
  on public.platform_changes (platform, kind, direction, onset desc);

-- 4. One announcement per client per change.
alter table public.alerts
  add column if not exists platform_change_id uuid references public.platform_changes (id) on delete set null;
create unique index if not exists alerts_one_per_platform_change
  on public.alerts (client_id, platform_change_id) where platform_change_id is not null;
