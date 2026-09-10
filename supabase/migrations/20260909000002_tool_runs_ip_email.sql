-- The 60-second Teardown's capture, hardened: the connection address as a
-- salted hash (never raw) for a per-day limit that survives a cold start,
-- and the record of the result email Resend sent.
alter table public.tool_runs
  add column ip_hash text,
  add column email_sent_at timestamptz,
  add column email_id text;
create index tool_runs_ip_idx on public.tool_runs (ip_hash, created_at desc);
