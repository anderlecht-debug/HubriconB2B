-- REVIEW_M1 #1 and #4: what each month billed, and the brand's disputes.
--
-- shopify_fee_months: one row per store per month the meter settled
-- (engine shopify_run.cmd_meter). A month is billed once, under the
-- idempotency key sha256(shop|month|line item); a later change to a billed
-- month's numbers is settled on the next month's statement as an adjustment,
-- read back from these rows. Written only by the engine with the service role.
--
-- shopify_disputes: a dollar the brand disputes, keyed by the directive whose
-- measured dollar it is. hwm strikes it in the month it was disputed and
-- refunds only the fee that was actually collected on it.
--
-- Both reference shopify_shops ON DELETE CASCADE, so shop/redact's delete of
-- the store's row erases them.

create table if not exists public.shopify_fee_months (
  shop_domain text not null
    references public.shopify_shops (shop_domain) on delete cascade,
  month text not null check (month ~ '^[0-9]{4}-[0-9]{2}$'),
  -- sent: a usage record exists. nothing_to_bill / refund_due: settled with no
  -- record. capped: Shopify refused at the merchant's capped amount (forgiven,
  -- collected nothing). error: nothing charged; a re-run may retry the month.
  status text not null
    check (status in ('sent', 'nothing_to_bill', 'refund_due', 'capped', 'error')),
  fee_usd numeric(12, 2) not null default 0,
  net_usd numeric(12, 2) not null default 0,
  adjustment_usd numeric(12, 2) not null default 0,
  charge_usd numeric(12, 2) not null default 0,
  billed_usd numeric(12, 2) not null default 0 check (billed_usd >= 0),
  refund_due_usd numeric(12, 2) not null default 0 check (refund_due_usd >= 0),
  -- The high-water mark after this month, as it stood when the month was billed.
  peak_usd numeric(12, 2) not null default 0,
  record_id text,
  idempotency_key text,
  errors jsonb,
  updated_at timestamptz not null default now(),
  primary key (shop_domain, month)
);

alter table public.shopify_fee_months enable row level security;
revoke all on public.shopify_fee_months from anon, authenticated;

create trigger shopify_fee_months_touch before update on public.shopify_fee_months
  for each row execute function public.shopify_shops_touch();

create table if not exists public.shopify_disputes (
  shop_domain text not null
    references public.shopify_shops (shop_domain) on delete cascade,
  directive_id text not null,
  disputed_at timestamptz not null default now(),
  note text,
  primary key (shop_domain, directive_id)
);

alter table public.shopify_disputes enable row level security;
revoke all on public.shopify_disputes from anon, authenticated;
