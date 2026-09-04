-- The bridge from 20260904000002 is retired: main now carries the
-- channel-aware parsers, so the narrow keys have no reader left and they
-- forbid the thing the Shopify route exists to allow — one client holding the
-- same SKU on Amazon and on Shopify. Dropped with no upload in flight and no
-- client yet on both platforms.
drop index if exists public.asin_traffic_compat_item_period_key;
drop index if exists public.sku_economics_compat_sku_period_key;
drop index if exists public.inventory_levels_compat_sku_snapshot_key;
