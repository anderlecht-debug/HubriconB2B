-- The Private Desk: client objectives on the masthead, briefings become
-- numbered Issues (letter and/or video, optionally carrying the full
-- written report), and members may download their own report files.

alter table public.clients add column goals text;

alter table public.briefings alter column video_id drop not null;
alter table public.briefings add column memo text;
alter table public.briefings add column issue_number integer;
alter table public.briefings add column report_path text;

-- Members may read report files under reports/{their client_id}/ in the
-- intake bucket. Uploads there are service-role only (the brief command).
create policy "members read own report files"
  on storage.objects for select to authenticated
  using (
    bucket_id = 'intake'
    and (storage.foldername(name))[1] = 'reports'
    and (storage.foldername(name))[2] in (
      select client_id::text from public.client_users where user_id = (select auth.uid())
    )
  );
