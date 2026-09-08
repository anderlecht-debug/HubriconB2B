-- Proof: the verified results a client's own ledger produces, made publishable.
--
-- The site carried "Sample · demo data" on every artifact and the cold email
-- said "the track record isn't [built]". Both were true, and both stayed true
-- after a client cleared the guarantee, because nothing turned a measured
-- dollar into a sentence a stranger could read. This table is that turn: one
-- row per verified event (a reimbursement Amazon paid on a claim we filed, a
-- directive measured `direct`, the day-30 gate clearing, the ledger crossing
-- 3x or 5x the fee), written by the operator from `value.compute`, never by
-- hand and never by a model.
--
-- Nothing here is public until two things are both true: the client granted
-- `anonymised_results` consent (terms.html §9) and the row is marked
-- published. The RPC re-checks consent on every read, so a revocation hides
-- every row instantly rather than on the next pass.

alter table public.clients
  add column industry text,          -- a category word for the result card ("kitchen")
  add column revenue_band text;      -- the gate's own answer ("$1M–$5M")

create table public.results (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  kind text not null
    check (kind in ('first_recovered', 'gate_cleared', 'roi_3x', 'roi_5x', 'direct_measured')),
  source_ref text not null default '',       -- the claim, directive or month it came from
  amount_usd numeric(12, 2) not null,
  mechanism text,                            -- what produced it: claim type, directive module
  how_we_know text not null
    check (how_we_know in ('direct', 'isolated', 'attributable', 'recovered', 'gate')),
  platform text,
  industry text,
  revenue_band text,
  published boolean not null default false,
  published_at timestamptz,
  created_at timestamptz not null default now(),
  unique (client_id, kind, source_ref)
);
alter table public.results enable row level security;   -- service role only
create index results_client_idx on public.results (client_id, created_at desc);
create index results_published_idx on public.results (published, published_at desc);

-- The one aperture. One card per brand — its largest verified amount, since a
-- ledger only grows — so a reader can count brands without a client id ever
-- leaving the database. Anonymised by construction: no company, no name, no
-- SKU, amounts rounded DOWN to the nearest hundred (terms §9: "figures
-- rounded"). It is the first function in this schema anon may execute; it
-- returns nothing that identifies anyone and nothing that was not consented to.
create or replace function public.public_results()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with eligible as (
    select r.*
      from public.results r
      join public.clients c on c.id = r.client_id
     where r.published
       and r.industry is not null
       and r.amount_usd >= 100
       and c.contact_email not like '%@hubricon.internal'
       and c.contact_email not like '%@hubricon.com'
       and c.contact_email not like '%@gethubricon.com'
       and exists (select 1 from public.consents k
                    where k.client_id = r.client_id
                      and k.kind = 'anonymised_results'
                      and k.granted is true)
  ),
  per_brand as (
    select distinct on (client_id) *
      from eligible
     order by client_id, amount_usd desc, published_at desc
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'industry',      industry,
           'revenue_band',  revenue_band,
           'platform',      platform,
           'kind',          kind,
           'amount_usd',    floor(amount_usd / 100) * 100,
           'mechanism',     mechanism,
           'how_we_know',   how_we_know,
           'month',         to_char(created_at, 'YYYY-MM')
         ) order by published_at desc), '[]'::jsonb)
    from per_brand;
$$;

revoke execute on function public.public_results() from public;
grant execute on function public.public_results() to anon, authenticated, service_role;
