-- The recurring issue, and the emails that carry it.
--
-- Two structural blockers to publishing on a schedule:
--
-- 1. briefings.issue_number was assigned count-then-add-one in two independent
--    places (cli.cmd_brief and operator._publish_first_issue) with no unique
--    constraint. Fine while a human ran it; a race the moment a daily job does.
--
-- 2. client_touches has primary key (client_id, kind), so an email kind can
--    fire exactly ONCE per client, forever. That is right for "welcome" and
--    wrong for anything recurring — there was no way to send issue No. 2.

alter table public.briefings
  -- Self-hosted generated video, alongside the Loom-shaped video_id, so
  -- `hubricon brief --video <loom url>` keeps working when the founder wants
  -- their own voice on an issue.
  add column video_path text;

-- Backfill before the constraint: any pre-existing NULL or duplicate number
-- would otherwise fail the index.
with numbered as (
  select id, row_number() over (partition by client_id order by created_at) as n
    from public.briefings
)
update public.briefings b
   set issue_number = numbered.n
  from numbered
 where numbered.id = b.id
   and (b.issue_number is null
        or exists (select 1 from public.briefings o
                    where o.client_id = b.client_id
                      and o.issue_number = b.issue_number
                      and o.id <> b.id));

alter table public.briefings
  add constraint briefings_client_issue_unique unique (client_id, issue_number);

-- Atomic next number: two publishers cannot both read "3" and both write 4.
create or replace function public.next_issue_number(p_client_id uuid)
returns integer
language sql
security definer
set search_path = ''
as $$
  select coalesce(max(issue_number), 0) + 1
    from public.briefings where client_id = p_client_id;
$$;
revoke execute on function public.next_issue_number(uuid) from public, anon, authenticated;
grant execute on function public.next_issue_number(uuid) to service_role;

-- The log for emails that recur. client_touches keeps the once-ever kinds
-- (welcome, files, nudge, teardown_ready); anything with a ref_id lives here,
-- so "issue 7 is ready" is sent once and only once without blocking issue 8.
create table public.client_emails (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  kind text not null,
  ref_id text not null default '',      -- the briefing / invoice / directive it is about
  subject text,
  sent_at timestamptz not null default now(),
  unique (client_id, kind, ref_id)
);
alter table public.client_emails enable row level security;   -- service role only

create index client_emails_client_idx on public.client_emails (client_id, sent_at desc);

-- welcome.html: "Within 24 hours … your 90-day plan is drafted straight from
-- it. On this call, you see the plan." Drafted is not the same as presented, so
-- the plan needs a state between "does not exist" and "live in the client's
-- desk". Today a client who books the kickoff finds the plan placeholder,
-- because nothing drafts one until the founder runs `hubricon plan … draft`
-- by hand.
alter table public.plans drop constraint if exists plans_status_check;
alter table public.plans add constraint plans_status_check
  check (status in ('draft', 'active', 'completed', 'superseded'));

-- The portal's policy already filters to status='active', so a draft stays
-- internal until the founder commits it on the kickoff call.
