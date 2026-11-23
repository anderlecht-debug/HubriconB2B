-- Milestone 2 of the Shopify app (BUILD_PLAN M6): the brand's own limits on
-- what Hubricon may do unasked, and the fee-approval question.
--
-- shopify_mandates: one row per store, written by api/shopify/app.js (the
-- brand's settings form) with the service role, read by the engine
-- (mandate.py). A move outside these limits is never executed: it waits for
-- the brand's tap. The defaults act on nothing: price moves are off until the
-- brand turns them on, and a reorder always waits for a tap.
--
-- Deleting the store's shopify_shops row (shop/redact) deletes this row too.

create table if not exists public.shopify_mandates (
  shop_domain text primary key
    references public.shopify_shops (shop_domain) on delete cascade,
  -- The largest single price step, in percent of the current price, that may
  -- run unasked. terms.html §6's standing mandate is five percent; the brand
  -- can only narrow it here.
  max_price_step_pct numeric not null default 5
    check (max_price_step_pct > 0 and max_price_step_pct <= 5),
  price_moves_enabled boolean not null default false,
  reorder_needs_tap boolean not null default true,
  -- Weeks of shadow mode (sealed calls, nothing executed) after install before
  -- any move inside the limits may run. Operator-set; the form does not show it.
  shadow_weeks integer not null default 4 check (shadow_weeks >= 1),
  updated_at timestamptz not null default now()
);

alter table public.shopify_mandates enable row level security;
revoke all on public.shopify_mandates from anon, authenticated;

create trigger shopify_mandates_touch before update on public.shopify_mandates
  for each row execute function public.shopify_shops_touch();

-- The fee-approval question (meter_gate.py). When a store's first proven
-- dollar is banked it is asked, once, whether it approves the fee on it. Its
-- answer feeds the pre-registered kill counter the operator digest prints.
--   none      no proven dollar yet, nothing asked
--   ask       a proven dollar is banked; the question is open
--   approved  the brand said yes
--   declined  the brand said no (or did not answer in the window: meter_gate)
alter table public.shopify_shops
  add column if not exists fee_question text not null default 'none'
    check (fee_question in ('none', 'ask', 'approved', 'declined')),
  add column if not exists fee_question_at timestamptz,
  add column if not exists fee_answered_at timestamptz,
  add column if not exists first_proven_usd numeric,
  add column if not exists client_id uuid references public.clients (id) on delete set null;
