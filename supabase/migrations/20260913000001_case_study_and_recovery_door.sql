-- The home page's two new jobs, and what each needs from the schema.
--
-- 1. Recovery Only gets a door on the site. The application no longer books a
--    call below $3M; an Amazon seller there can ask for Recovery Only on the
--    below-the-bar screen (api/gate.js). The operator's first email to them is
--    `recovery_welcome`, not the full-Teardown `files` email, and it suppresses
--    the day-14 downsell, which would otherwise offer them the door they came in by.
--
-- 2. One case study, told in full, or nothing (index.html §3b). A row here is
--    written only by `hubricon casestudy <client> --publish`, from the client's
--    real Profit Record, their own before-state and their own quote. It reaches
--    the page only through public_case_study(), which re-checks consent on every
--    read exactly as public_results() does: a revoked testimonial or publication
--    consent hides the case study at once, and a revoked named_results consent
--    hides the brand name while the anonymised story stands.

alter table public.client_touches drop constraint if exists client_touches_kind_check;
alter table public.client_touches add constraint client_touches_kind_check
  check (kind in ('welcome', 'nudge', 'files', 'teardown_ready', 'consent_ask', 'referral_credit', 'downsell',
                  'recovery_welcome'));

-- The founder's before-state, in their own words, written on the consent page
-- beside the testimonial it frames. It lives on the testimonial row.
alter table public.consents add column if not exists before_text text;

create table public.case_studies (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null unique references public.clients (id) on delete cascade,
  brand_name text,                 -- set only when named_results was granted at publish time
  industry text,
  platform text,
  before_text text not null,       -- consents.before_text, verbatim
  quote text not null,             -- consents.testimonial, verbatim, 30 words or fewer
  numbers jsonb not null default '[]'::jsonb,   -- [{label, amount_usd, method}], from value.compute
  record jsonb not null default '[]'::jsonb,    -- the client's own Record rows, identifiers masked, the miss included
  proving_month_closed_on date not null,
  published boolean not null default false,
  published_at timestamptz,
  drafted_at timestamptz not null default now()
);
alter table public.case_studies enable row level security;   -- service role only

create or replace function public.public_case_study()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
           'brand',     case when exists (select 1 from public.consents k
                                           where k.client_id = s.client_id
                                             and k.kind = 'named_results' and k.granted is true)
                             then s.brand_name end,
           'industry',  s.industry,
           'platform',  s.platform,
           'before',    s.before_text,
           'quote',     s.quote,
           'numbers',   s.numbers,
           'record',    s.record,
           'closed_on', s.proving_month_closed_on)
    from public.case_studies s
    join public.clients c on c.id = s.client_id
   where s.published
     and c.contact_email not like '%@hubricon.internal'
     and c.contact_email not like '%@hubricon.com'
     and c.contact_email not like '%@gethubricon.com'
     and exists (select 1 from public.consents k
                  where k.client_id = s.client_id and k.kind = 'testimonial' and k.granted is true)
     and exists (select 1 from public.consents k
                  where k.client_id = s.client_id
                    and k.kind in ('named_results', 'anonymised_results') and k.granted is true)
   order by s.published_at desc
   limit 1;
$$;

revoke execute on function public.public_case_study() from public;
grant execute on function public.public_case_study() to anon, authenticated, service_role;
