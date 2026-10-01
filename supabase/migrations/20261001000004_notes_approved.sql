-- The founder approves every note (engine/src/hubricon_engine/approval.py).
--
-- HUBRICON_SPEC.md, "Customer experience" 4: the human layer is a short weekly
-- note, drafted by the system from the graded numbers and approved by the
-- founder, never written from scratch. Until now nothing was approved: the
-- fortnightly Profit Brief published and emailed itself, and a quiet Monday
-- sent the client nothing.
--
-- 1. weekly_notes: the Monday note, one per client per week, held as a draft
--    until `hubricon approve` sends it. A client reads only their own notes
--    that were actually sent; drafts and discarded notes are the founder's.
-- 2. briefings.status: Profit Brief No. 002 on is drafted ('draft') and only
--    becomes visible in the portal when approved ('published'). Every existing
--    row, and every row written without a status (Issue 001, the first full
--    read, which publishes itself; `hubricon brief`), is published.
--
-- Safe before or after the code: without this, the code publishes and sends as
-- it did before and the founder's digest says the approval gate is off.

create table if not exists public.weekly_notes (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  week_of date not null,                       -- the Monday the note belongs to
  facts jsonb not null default '{}'::jsonb,    -- every line, verbatim, and the Record figure it was drafted on
  body_text text,
  body_html text,
  status text not null default 'draft' check (status in ('draft', 'sent', 'discarded')),
  created_at timestamptz not null default now(),
  approved_at timestamptz,
  sent_at timestamptz,
  unique (client_id, week_of)
);
alter table public.weekly_notes enable row level security;

drop policy if exists "members read own sent notes" on public.weekly_notes;
create policy "members read own sent notes"
  on public.weekly_notes for select to authenticated
  using (status = 'sent'
         and client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index if not exists weekly_notes_status_idx on public.weekly_notes (status, created_at);

alter table public.briefings add column if not exists status text not null default 'published';
alter table public.briefings drop constraint if exists briefings_status_check;
alter table public.briefings add constraint briefings_status_check check (status in ('draft', 'published'));
alter table public.briefings add column if not exists approved_at timestamptz;
-- What a draft's email says (subject, blocks, footer) and the Record figure it
-- was drafted on, so approval sends exactly what was shown and refuses a draft
-- whose figure has since moved.
alter table public.briefings add column if not exists facts jsonb;

drop policy if exists "members read own briefings" on public.briefings;
drop policy if exists "members read own published briefings" on public.briefings;
create policy "members read own published briefings"
  on public.briefings for select to authenticated
  using (status = 'published'
         and client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index if not exists briefings_status_idx on public.briefings (status, created_at);
