-- Tokenized CSV intake: each client gets a secret upload link, no Supabase
-- Auth in v1. Raw tokens never touch the database — callers hash with
-- sha256 first, so a leaked table dump can't be replayed as upload links.

create table private.intake_tokens (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  token_hash text not null unique,
  label text,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '90 days',
  revoked_at timestamptz,
  last_used_at timestamptz
);
alter table private.intake_tokens enable row level security;

-- Registry of files clients upload. A row is created (status 'pending')
-- before the browser PUTs the file to Storage via a signed upload URL.
create table public.uploads (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  report_type text not null
    check (report_type in ('business_report', 'sku_economics', 'ppc_search_terms',
                           'ppc_campaign', 'fba_inventory', 'cogs')),
  -- period-scoped reports carry the export's date range; fba_inventory uses
  -- period_start as the snapshot date; cogs leaves both null
  period_start date,
  period_end date,
  storage_path text not null,
  original_filename text,
  content_type text,
  declared_size_bytes bigint,
  status text not null default 'pending'
    check (status in ('pending', 'uploaded', 'parsed', 'failed')),
  parse_error text,
  row_count integer,
  uploaded_at timestamptz,
  parsed_at timestamptz,
  created_at timestamptz not null default now()
);
alter table public.uploads enable row level security;

create policy "members read own uploads"
  on public.uploads for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index uploads_client_status_idx on public.uploads (client_id, status);

-- Private bucket with no storage policies: only the service role and
-- holders of a path-scoped signed upload URL can touch objects.
insert into storage.buckets (id, name, public, file_size_limit)
values ('intake', 'intake', false, 52428800)
on conflict (id) do update set file_size_limit = excluded.file_size_limit;

-- Mints an intake token for a client (caller supplies the sha256 hex hash).
create or replace function public.create_intake_token(
  p_client_id uuid,
  p_token_hash text,
  p_label text default null,
  p_expires_at timestamptz default now() + interval '90 days'
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid;
begin
  insert into private.intake_tokens (client_id, token_hash, label, expires_at)
  values (p_client_id, p_token_hash, p_label, p_expires_at)
  returning id into v_id;
  return v_id;
end;
$$;

revoke execute on function public.create_intake_token(uuid, text, text, timestamptz) from public, anon, authenticated;
grant execute on function public.create_intake_token(uuid, text, text, timestamptz) to service_role;

-- Resolves a live token to its client (no rows for unknown, revoked, or
-- expired tokens) and touches last_used_at.
create or replace function public.validate_intake_token(p_token_hash text)
returns table (client_id uuid, company_name text)
language plpgsql
security definer
set search_path = ''
as $$
begin
  return query
  update private.intake_tokens t
     set last_used_at = now()
    from public.clients c
   where c.id = t.client_id
     and t.token_hash = p_token_hash
     and t.revoked_at is null
     and t.expires_at > now()
  returning t.client_id, c.company_name;
end;
$$;

revoke execute on function public.validate_intake_token(text) from public, anon, authenticated;
grant execute on function public.validate_intake_token(text) to service_role;

-- Revokes every live token for a client; returns how many were revoked.
create or replace function public.revoke_intake_tokens(p_client_id uuid)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count integer;
begin
  update private.intake_tokens
     set revoked_at = now()
   where client_id = p_client_id
     and revoked_at is null;
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

revoke execute on function public.revoke_intake_tokens(uuid) from public, anon, authenticated;
grant execute on function public.revoke_intake_tokens(uuid) to service_role;
