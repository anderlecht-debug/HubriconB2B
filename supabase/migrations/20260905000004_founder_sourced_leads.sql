-- Leads the founder found by hand.
--
-- The crawl finds companies; a person finds the owner's *name*, which is the
-- one thing the crawl cannot do and the constraint the cold lane kept hitting.
-- So a row can now arrive from `hubricon teardown add` rather than only from a
-- category crawl, and it says so — the provenance is a GDPR record as much as a
-- diagnostic (COLD_ENGINE.md §2.3).
alter table public.harvest_sellers drop constraint if exists harvest_sellers_source_check;
alter table public.harvest_sellers
  add constraint harvest_sellers_source_check
  check (source in ('bestsellers', 'wayback', 'shopify', 'founder'));
