-- Harvest: seller-level size signal and provenance.
--   ratings_12mo / ratings_lifetime  the seller-feedback counts on the public
--                                    profile page; ~1 order in 500 leaves one,
--                                    so the 12-month count tracks the whole
--                                    account (Gorilla Grip 8,703; a $3M brand ~300)
--   source                           'bestsellers' (live crawl) or 'wayback'
--                                    (archived seller profile, no Amazon request)
alter table public.harvest_sellers
  add column if not exists ratings_12mo integer,
  add column if not exists ratings_lifetime integer,
  add column if not exists source text not null default 'bestsellers'
    check (source in ('bestsellers', 'wayback'));
create index if not exists harvest_sellers_source_idx on public.harvest_sellers (source);
