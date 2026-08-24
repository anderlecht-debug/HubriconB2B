-- Security-definer RPCs: the only doors into the private schema and Vault.
-- Execute is stripped from anon/authenticated; only the service role
-- (webhook, ingestion worker) may call these.

-- Returns true if the event is new, false if already processed (idempotency).
create or replace function public.record_stripe_event(p_event_id text, p_event_type text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into private.stripe_events (event_id, event_type)
  values (p_event_id, p_event_type);
  return true;
exception when unique_violation then
  return false;
end;
$$;

revoke execute on function public.record_stripe_event(text, text) from public, anon, authenticated;
grant execute on function public.record_stripe_event(text, text) to service_role;

-- Stores/rotates a client's SP-API refresh token in Vault.
create or replace function public.store_amazon_refresh_token(p_client_id uuid, p_refresh_token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_secret_id uuid;
begin
  select lwa_refresh_token_secret_id into v_secret_id
  from private.amazon_credentials
  where client_id = p_client_id;

  if v_secret_id is null then
    v_secret_id := vault.create_secret(p_refresh_token, 'amazon_lwa_refresh_' || p_client_id::text);
    insert into private.amazon_credentials (client_id, lwa_refresh_token_secret_id, authorized_at)
    values (p_client_id, v_secret_id, now())
    on conflict (client_id) do update
      set lwa_refresh_token_secret_id = excluded.lwa_refresh_token_secret_id,
          authorized_at = now(),
          updated_at = now();
  else
    perform vault.update_secret(v_secret_id, p_refresh_token);
    update private.amazon_credentials
      set authorized_at = now(), updated_at = now()
      where client_id = p_client_id;
  end if;
end;
$$;

revoke execute on function public.store_amazon_refresh_token(uuid, text) from public, anon, authenticated;
grant execute on function public.store_amazon_refresh_token(uuid, text) to service_role;

-- Hands the decrypted refresh token to the ingestion worker.
create or replace function public.get_amazon_refresh_token(p_client_id uuid)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_token text;
begin
  select ds.decrypted_secret into v_token
  from private.amazon_credentials ac
  join vault.decrypted_secrets ds on ds.id = ac.lwa_refresh_token_secret_id
  where ac.client_id = p_client_id;
  return v_token;
end;
$$;

revoke execute on function public.get_amazon_refresh_token(uuid) from public, anon, authenticated;
grant execute on function public.get_amazon_refresh_token(uuid) to service_role;
