-- One link, one job. privacy.html §5 and /your-data say upload links are
-- single-purpose; until now they were not. Upload links (/intake) and consent
-- links (/say) were rows of the same table resolved by the same function, so an
-- upload link opened the consent page and the other way round, and rotating a
-- client's upload link (a fresh welcome, `new-client.mjs`) also killed a live
-- consent link.
--
-- Each token now carries its purpose. It is set from the label at insert, so no
-- caller changes: referral.py mints consent links with the label 'consent link';
-- everything else is an upload link. The pages resolve a token only for their
-- own purpose (validate_token_for), the old resolver answers for upload links
-- only, and revoking a client's upload links leaves their consent link alone.

alter table private.intake_tokens
  add column if not exists purpose text not null default 'upload'
  check (purpose in ('upload', 'consent'));

update private.intake_tokens set purpose = 'consent'
 where purpose = 'upload' and label ilike 'consent%';

create or replace function private.intake_token_purpose()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.label ilike 'consent%' then
    new.purpose := 'consent';
  end if;
  return new;
end;
$$;

drop trigger if exists intake_token_purpose on private.intake_tokens;
create trigger intake_token_purpose before insert on private.intake_tokens
  for each row execute function private.intake_token_purpose();

-- Resolves a live token for one purpose only.
create or replace function public.validate_token_for(p_token_hash text, p_purpose text)
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
     and t.purpose = p_purpose
     and t.revoked_at is null
     and t.expires_at > now()
  returning t.client_id, c.company_name;
end;
$$;

revoke execute on function public.validate_token_for(text, text) from public, anon, authenticated;
grant execute on function public.validate_token_for(text, text) to service_role;

-- The old resolver now answers for upload links only, so a caller not yet
-- moved to validate_token_for can never open the consent page with one.
create or replace function public.validate_intake_token(p_token_hash text)
returns table (client_id uuid, company_name text)
language plpgsql
security definer
set search_path = ''
as $$
begin
  return query select * from public.validate_token_for(p_token_hash, 'upload');
end;
$$;

-- Rotating a client's upload link no longer revokes their consent link.
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
     and purpose = 'upload'
     and revoked_at is null;
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;
