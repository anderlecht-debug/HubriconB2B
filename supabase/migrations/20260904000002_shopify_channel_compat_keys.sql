-- Bridge: the pre-channel natural keys, restored alongside the channel-aware
-- ones, so BOTH the code on main and the code on shopify-route can upsert.
--
-- 20260904000001 widened three natural keys to include `channel` and dropped
-- the old constraints. Scheduled GitHub Actions run `main`, whose parsers
-- still pass the old column lists to ON CONFLICT — and an ON CONFLICT whose
-- columns match no unique index is an error, not a fallback. Nothing failed
-- only because no upload was awaiting a parse; the first client to send their
-- exports would have hit it.
--
-- These indexes are DELIBERATELY TEMPORARY. They forbid one client holding the
-- same SKU on both channels, which is exactly what the Shopify route exists to
-- allow, so drop them in the same change that merges shopify-route into main:
--
--   drop index if exists public.asin_traffic_compat_item_period_key;
--   drop index if exists public.sku_economics_compat_sku_period_key;
--   drop index if exists public.inventory_levels_compat_sku_snapshot_key;
--
-- Safe to add today: every existing row is channel 'amazon', so the narrower
-- key is already unique across the data.
create unique index if not exists asin_traffic_compat_item_period_key
  on public.asin_traffic (client_id, child_asin, period_start, period_end);
create unique index if not exists sku_economics_compat_sku_period_key
  on public.sku_economics (client_id, sku, period_start, period_end);
create unique index if not exists inventory_levels_compat_sku_snapshot_key
  on public.inventory_levels (client_id, sku, snapshot_date);
