-- The testimonial ask and the referral month.
--
-- terms.html §9 prices the free month in a testimonial and anonymised results.
-- The day-30 pass inserted two unanswered `consents` rows and nothing ever
-- asked, collected, or read them back. This gives the ask a surface (the
-- tokenised /say page), a place to keep the answer, and a way for the client
-- who says yes to send the next client: a personal link that rides the
-- booking, and a month credited to them when that client clears its own gate.

alter table public.consents
  add column testimonial text,
  add column testimonial_named_ok boolean;
alter table public.consents drop constraint if exists consents_kind_check;
alter table public.consents add constraint consents_kind_check
  check (kind in ('testimonial', 'anonymised_results', 'named_results', 'calibration'));

create table public.partners (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  contact_email text,
  kind text not null default 'other'
    check (kind in ('bookkeeper', 'prep', 'lender', 'agency', 'other')),
  terms text,                                -- what was agreed, in words
  created_at timestamptz not null default now()
);
alter table public.partners enable row level security;   -- service role only

alter table public.clients
  add column referral_code text unique,
  add column referred_by_client_id uuid references public.clients (id) on delete set null,
  add column referred_by_partner_id uuid references public.partners (id) on delete set null,
  add column referral_credit_applied_at timestamptz;   -- the credit THIS client earned its referrer

alter table public.prospects
  add column referrer_client_id uuid references public.clients (id) on delete set null,
  add column partner_id uuid references public.partners (id) on delete set null;

alter table public.bookings
  add column ref_code text;

alter table public.client_touches drop constraint if exists client_touches_kind_check;
alter table public.client_touches add constraint client_touches_kind_check
  check (kind in ('welcome', 'nudge', 'files', 'teardown_ready', 'consent_ask', 'referral_credit'));

create index clients_referral_code_idx on public.clients (referral_code) where referral_code is not null;
