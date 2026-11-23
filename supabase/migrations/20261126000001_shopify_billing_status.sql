-- REDTEAM_BUILD risk 2: the free look-back and shadow mode run before any
-- billing approval. Install sets status 'active' (ingest runs) and creates no
-- charge; the capped usage charge is created only when the brand says yes to
-- the fee question (api/shopify/app.js), and its Shopify approval is tracked
-- here, apart from the install's status.
--   none     no charge created (no yes yet)
--   pending  the brand said yes; the charge awaits approval on Shopify
--   active   Shopify confirms the subscription is active (api/shopify/billing.js)
-- The engine's meter bills only fee_question 'approved' with billing_status 'active'.
alter table public.shopify_shops
  add column if not exists billing_status text not null default 'none'
    check (billing_status in ('none', 'pending', 'active'));

update public.shopify_shops
   set billing_status = 'active'
 where status = 'active' and usage_line_item_id is not null and billing_status = 'none';
