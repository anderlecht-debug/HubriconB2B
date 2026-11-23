-- The Shopify app's installs (BUILD_PLAN M1). One row per store, written only by
-- the Vercel functions in api/shopify/* with the service role. The offline token
-- is stored encrypted (AES-256-GCM, SHOPIFY_TOKEN_KEY, never in the database).
--
-- shop/redact deletes the row. Any later table holding a store's data references
-- shopify_shops (shop_domain) ON DELETE CASCADE, so that one delete erases it all.

create table if not exists public.shopify_shops (
  shop_domain text primary key check (shop_domain ~ '^[a-z0-9][a-z0-9-]*\.myshopify\.com$'),
  token_enc text,
  scopes text,
  status text not null default 'pending_billing'
    check (status in ('pending_billing', 'active', 'frozen', 'uninstalled')),
  installed_at timestamptz not null default now(),
  uninstalled_at timestamptz,
  usage_line_item_id text,
  cap_usd numeric not null default 500 check (cap_usd > 0),
  -- terms §10: one store's data never advises another without this yes.
  network_consent boolean not null default false,
  -- The high-water mark of cumulative proven profit, and what has been billed on it.
  peak_usd numeric not null default 0,
  billed_usd numeric not null default 0 check (billed_usd >= 0),
  mode text not null default 'shadow' check (mode in ('shadow', 'live')),
  updated_at timestamptz not null default now()
);

-- RLS on and no policy: anon and authenticated read and write nothing; only the
-- service role (which bypasses RLS) touches the table.
alter table public.shopify_shops enable row level security;
revoke all on public.shopify_shops from anon, authenticated;

create or replace function public.shopify_shops_touch() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

create trigger shopify_shops_touch before update on public.shopify_shops
  for each row execute function public.shopify_shops_touch();
