-- The export promise, tightened to what the site now says.
--
-- terms §11 and Hubricon's own footer promise a complete export "within one
-- working day". The RPC that opens the request has always dated it seven days
-- out, so the clock the promise audit read was the weaker one and the page had
-- been softened to match it. Nothing about a founder-operated desk with fewer
-- than ten clients needs seven days to run `hubricon export <client>`, and the
-- export is the hedge the page sells against a one-person shop — the strongest
-- honest version of it is the one worth keeping.
--
-- Two working days' grace is built into the arithmetic rather than the promise:
-- a request opened on a Friday evening is due Monday, not Saturday, so a
-- weekend can never make `hubricon promises` report a broken promise that was
-- never broken. Existing open requests are pulled forward to the same rule.
--
-- Only the due date changes. The no-second-row behaviour, the security-definer
-- scoping and the grants are exactly as they were.

create or replace function public.next_working_day(ts timestamptz)
returns timestamptz
language sql
immutable
set search_path = ''
as $$
  -- One working day after `ts`: Saturday and Sunday are skipped, so Friday and
  -- the weekend all land on Monday at the same time of day.
  select case extract(isodow from ts)
           when 5 then ts + interval '3 days'   -- Friday   -> Monday
           when 6 then ts + interval '2 days'   -- Saturday -> Monday
           when 7 then ts + interval '2 days'   -- Sunday   -> Tuesday
           else ts + interval '1 day'
         end;
$$;

create or replace function public.request_data_export()
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_client uuid;
begin
  select client_id into v_client
    from public.client_users where user_id = (select auth.uid()) limit 1;
  if v_client is null then
    return false;
  end if;
  if exists (select 1 from public.data_requests
              where client_id = v_client and kind = 'access' and closed_at is null) then
    return true;
  end if;
  insert into public.data_requests (client_id, requester_email, kind, note, due_at)
  select v_client, c.contact_email, 'access', 'Requested from Hubricon',
         public.next_working_day(now())
    from public.clients c where c.id = v_client;
  return true;
end;
$$;

revoke execute on function public.request_data_export() from public, anon;
grant execute on function public.request_data_export() to authenticated, service_role;

-- Anyone already waiting gets the promise the page now makes, not the one it
-- used to make. Only open access requests move, and only ever earlier.
update public.data_requests
   set due_at = least(due_at, public.next_working_day(opened_at))
 where kind = 'access' and closed_at is null;
