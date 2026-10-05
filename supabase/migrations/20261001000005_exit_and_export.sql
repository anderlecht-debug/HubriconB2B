-- Leaving never means going blind (2026-10-01).
--
-- Two promises the machine now keeps itself instead of the founder by hand:
--
--   terms §11  an export a client asks for is delivered within one working day.
--              The operator builds the zip, stores it in the private `exports`
--              bucket below, and emails a seven-day signed link to the client's
--              own contact email (operator.Pass.data_requests).
--   terms §5   a refund owed when a client leaves is issued within seven days
--              of their email. `hubricon cancel` now opens a data_request of kind
--              'exit', due seven days out; the digest and `hubricon promises`
--              count it, and the operator closes it once the true-up is done and
--              the exit letter has gone.
--
-- Safe to apply before or after the code. Before it: `hubricon cancel` says the
-- exit clock could not start (a billed client is still trued up and written to;
-- a never-billed client's exit letter waits for this), and every export request
-- falls back to the founder's `hubricon export`. Additive only.

-- 1. The exit clock: one more kind of dated request.
alter table public.data_requests drop constraint if exists data_requests_kind_check;
alter table public.data_requests add constraint data_requests_kind_check
  check (kind in ('deletion', 'access', 'correction', 'breach_notice', 'terms_notice',
                  'exit'));          -- terms §5: the refund owed at the exit, issued within seven days

-- One running exit clock per client: `hubricon cancel` run twice is one exit.
create unique index if not exists data_requests_one_open_exit
  on public.data_requests (client_id) where kind = 'exit' and closed_at is null;

-- 2. Where exports wait for their download. Private, and no storage policies:
-- only the service role and the holder of a signed link (seven days) can read
-- an object. No size limit of its own, so the project's global upload limit
-- governs; an export larger than that fails to store and the request falls back
-- to `hubricon export` by hand, which the digest says.
insert into storage.buckets (id, name, public, allowed_mime_types)
values ('exports', 'exports', false, array['application/zip'])
on conflict (id) do nothing;
