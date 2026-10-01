-- /learn: the readers. One email registers you for a course (HUBRICON_SPEC.md,
-- "Education hub"); everything inside the course is open. This is the list the
-- spec says the courses build, and nothing else is kept about a reader.
--
-- One row per address per course. api/learn.js writes it with the service role;
-- RLS is on with no policies, so no browser key can read or write it.
--
-- unsubscribe_token is per row; following any of an address's tokens marks every
-- row for that address unsubscribed. A sign-up for a new course still gets that
-- course's link (they asked for it); the occasional "a new course is out" note goes
-- only to addresses with no unsubscribed row.

create table public.learners (
  id uuid primary key default gen_random_uuid(),
  email text not null check (email = lower(email) and length(email) <= 200),
  course text not null,
  source text,
  ip_hash text,
  unsubscribe_token text not null default replace(gen_random_uuid()::text, '-', ''),
  unsubscribed_at timestamptz,
  email_sent_at timestamptz,
  email_id text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (email, course)
);
alter table public.learners enable row level security;
create index learners_ip_idx on public.learners (ip_hash, created_at desc);
create unique index learners_token_idx on public.learners (unsubscribe_token);
create index learners_email_idx on public.learners (email);
