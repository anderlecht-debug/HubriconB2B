-- Brand terms per client, for cannibalization detection in search-term
-- spend. Comma-separated; when null the engine derives a default from
-- company_name.

alter table public.clients add column brand_terms text;
