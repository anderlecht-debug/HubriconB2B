-- Monthly video briefings: the founder's personalized Loom walkthrough of a
-- client's numbers. Loom has no API, so the video id is pasted in via the
-- CLI once per client per month; the portal embeds the newest row.

create table public.briefings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  run_id uuid references public.model_runs (id) on delete set null,
  title text,
  video_id text not null,
  tldr text,
  headline text,
  created_at timestamptz not null default now()
);
alter table public.briefings enable row level security;

create policy "members read own briefings"
  on public.briefings for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index briefings_client_created_idx on public.briefings (client_id, created_at desc);
