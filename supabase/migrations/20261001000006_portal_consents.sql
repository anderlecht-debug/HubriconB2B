-- The portal's own two calls (2026-10-01): a permission withdrawn in one click,
-- and what the portal needs that row-level security does not give it.
--
-- terms.html §9 and §10 name four permissions, each a separate yes asked on a
-- private page: anonymised results, a testimonial, calibration and the network.
-- The /say page (api/consent.js) is where they are given. Withdrawing one took
-- a reply to an email; a permission that takes a letter to withdraw is not
-- freely given. The portal reads `consents` under "members read own consents"
-- and now writes through one function:
--
--   set_my_consent(p_client_id, p_kind, p_granted)
--       Only for a member of that workspace (client_users), only for the kinds
--       the terms name. Withdrawing is always allowed, for those four and for
--       `named_results` (the /say page's optional "name my brand", which the
--       terms do not name, so the portal can take it away but never give it).
--       Giving is allowed only where the question was already asked (a row
--       exists): it is the portal's one-click undo, never a new ask. Returns the
--       row as it now stands.
--
--   my_portal(p_client_id)
--       The time of the client's call (the latest booking that is not a
--       kickoff, as engine lifecycle.call_at reads it), so a client who has not
--       said yes yet reads "Your call is ..." rather than anything that assumes
--       a yes, and the kinds set_my_consent accepts. `bookings` has no client
--       policy and gets none: this returns one timestamp of the caller's own.
--       Its presence is how the portal knows this migration is applied; without
--       it the portal says "Reply to any email from us to change this."
--
-- What a withdrawal does downstream is already in code: public_results() and
-- the case-study reads re-check `granted` on every read, so a withdrawn
-- publication disappears at once; fleet.py and `hubricon book` read the network
-- consent each pass, and calibration reads its own. Nothing else changes.
-- Safe to apply before or after the portal that calls it. Not applied by the
-- commit that adds it.

create or replace function public.set_my_consent(p_client_id uuid, p_kind text, p_granted boolean)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_row public.consents%rowtype;
begin
  if (select auth.uid()) is null
     or not exists (select 1 from public.client_users u
                     where u.user_id = (select auth.uid()) and u.client_id = p_client_id) then
    raise exception 'not a member of this workspace' using errcode = '42501';
  end if;
  if p_granted is null then
    raise exception 'a permission is a yes or a no' using errcode = '22023';
  end if;
  if not (p_kind in ('anonymised_results', 'testimonial', 'calibration', 'network')
          or (p_kind = 'named_results' and p_granted is false)) then
    raise exception 'the terms do not name that permission' using errcode = '22023';
  end if;

  if p_granted is false then
    insert into public.consents (client_id, kind, granted, answered_at)
    values (p_client_id, p_kind, false, now())
    on conflict (client_id, kind) do update
       set granted = false, answered_at = now()
    returning * into v_row;
  else
    update public.consents k
       set granted = true, answered_at = now()
     where k.client_id = p_client_id and k.kind = p_kind
    returning * into v_row;
    if not found then
      raise exception 'a permission is given on the page we send you, not here' using errcode = '22023';
    end if;
  end if;

  return jsonb_build_object('kind', v_row.kind, 'granted', v_row.granted, 'answered_at', v_row.answered_at);
end;
$$;

revoke execute on function public.set_my_consent(uuid, text, boolean) from public, anon;
grant execute on function public.set_my_consent(uuid, text, boolean) to authenticated, service_role;

create or replace function public.my_portal(p_client_id uuid)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select case
    when (select auth.uid()) is not null
     and exists (select 1 from public.client_users u
                  where u.user_id = (select auth.uid()) and u.client_id = p_client_id)
    then jsonb_build_object(
      'call_at', (select b.starts_at
                    from public.bookings b
                   where b.client_id = p_client_id
                     and b.starts_at is not null
                     and coalesce(b.event_type, '') !~* 'kick\s*-?\s*off'
                   order by b.created_at desc
                   limit 1),
      'consent_kinds', jsonb_build_array('anonymised_results', 'testimonial', 'calibration', 'network'),
      'withdraw_only', jsonb_build_array('named_results'))
  end;
$$;

revoke execute on function public.my_portal(uuid) from public, anon;
grant execute on function public.my_portal(uuid) to authenticated, service_role;
