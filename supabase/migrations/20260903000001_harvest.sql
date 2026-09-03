-- Harvest: private-label Amazon sellers found on public pages (Best Sellers
-- lists → product pages → the seller profile Amazon requires every
-- professional seller to publish, with business name and address), then the
-- brand's own website for a published contact address. Feeds the Instantly
-- list "Hubricon harvest (auto)", which the operator enrolls into the
-- campaign. Internal: RLS on, no policies, service role only.

create table public.harvest_sellers (
  seller_id text primary key,
  seller_name text,
  brand text,
  brands jsonb not null default '[]'::jsonb,
  business_name text,
  address text,
  city text,
  state text,
  country text,
  asins jsonb not null default '[]'::jsonb,
  top_bsr integer,
  top_category text,
  reviews_max integer,
  est_monthly_units numeric,
  est_monthly_revenue numeric,
  website text,
  email text,
  email_confidence text check (email_confidence in ('published', 'pattern')),
  first_name text,
  last_name text,
  person_source text,
  status text not null default 'candidate'
    check (status in ('candidate', 'enriched', 'pushed', 'no_website', 'no_email',
                      'skip_reseller', 'skip_non_us', 'skip_amazon', 'skip_size', 'skip_internal')),
  instantly_lead_id text,
  pushed_at timestamptz,
  notes text,
  first_seen timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.harvest_sellers enable row level security;
create index harvest_sellers_status_idx on public.harvest_sellers (status);
create index harvest_sellers_email_idx on public.harvest_sellers (email);

-- Every product page read, with the public weight/dimensions/rank/price.
-- Doubles as the dataset behind the fee-cliff report (see GROWTH.md).
create table public.harvest_products (
  asin text primary key,
  seller_id text,
  brand text,
  title text,
  category text,
  bsr integer,
  price numeric,
  reviews integer,
  weight_oz numeric,
  dims text,
  fulfilled_by_amazon boolean,
  est_monthly_units numeric,
  est_monthly_revenue numeric,
  seen_at timestamptz not null default now()
);
alter table public.harvest_products enable row level security;
create index harvest_products_seller_idx on public.harvest_products (seller_id);
