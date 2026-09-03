-- The scoreboard counted a disqualified prospect as contacted.
--
-- 'contacted' was count(*) where status <> 'queued', so every row we threw out
-- for being an agency, a competitor or a wrong address was reported as someone
-- we had emailed. On 2026-09-03 that read "56 contacted" on a funnel that had
-- never sent a single email. A metric that moves when you delete bad leads is
-- worse than no metric.
--
-- Also adds by_source, so the manual channels (founder lane, partner emails,
-- the data post) can be compared against the automated one without a new table.

alter table public.prospects drop constraint if exists prospects_source_check;
alter table public.prospects add constraint prospects_source_check
  check (source in ('instantly_list', 'supersearch', 'inbound', 'manual',
                    'founder', 'partner', 'post', 'teardown', 'spn', 'referral', 'forum'));

create or replace function public.pmf_scoreboard()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with real_clients as (
    select * from public.clients
    where contact_email not like '%@hubricon.internal'
      and contact_email not like '%@hubricon.com'
      and contact_email not like '%@gethubricon.com'
  ),
  paid as (
    select * from real_clients where status in ('active', 'past_due') and stripe_customer_id is not null
  ),
  renewed as (
    -- past the free month(s) and still active: the first real retention signal
    select * from paid
    where status = 'active'
      and now() > created_at + make_interval(months => coalesce(free_months, 1) + 1)
  )
  select jsonb_build_object(
    'prospects_total',    (select count(*) from public.prospects),
    -- Never emailed: 'queued' has not gone out yet and 'dq' never will.
    'contacted',          (select count(*) from public.prospects where status not in ('queued', 'dq')),
    'disqualified',       (select count(*) from public.prospects where status = 'dq'),
    'replied',            (select count(*) from public.prospects where last_reply_at is not null),
    'interested',         (select count(*) from public.prospects
                            where status in ('interested', 'wants_teardown', 'booked', 'client')),
    'unsubscribed',       (select count(*) from public.prospects where status = 'unsubscribed'),
    'bookings',           (select count(*) from public.bookings where not is_test),
    'bookings_qualified', (select count(*) from public.bookings where not is_test and qualified),
    'clients_onboarding', (select count(*) from real_clients where status = 'pending'),
    'teardowns_delivered',(select count(*) from public.briefings b
                            join real_clients c on c.id = b.client_id
                            where b.issue_number = 1),
    'paid',               (select count(*) from paid),
    'renewed',            (select count(*) from renewed),
    'churned',            (select count(*) from real_clients where status = 'churned'),
    'pmf_bar_renewed',    3,
    'pmf_reached',        (select count(*) from renewed) >= 3,
    'by_source',          (select coalesce(jsonb_object_agg(source, counts), '{}'::jsonb) from (
                             select coalesce(source, 'unknown') as source,
                                    jsonb_build_object(
                                      'total',      count(*),
                                      'contacted',  count(*) filter (where status not in ('queued', 'dq')),
                                      'dq',         count(*) filter (where status = 'dq'),
                                      'replied',    count(*) filter (where last_reply_at is not null),
                                      'interested', count(*) filter (where status in
                                                     ('interested', 'wants_teardown', 'booked', 'client')),
                                      'client',     count(*) filter (where status = 'client')
                                    ) as counts
                             from public.prospects group by coalesce(source, 'unknown')
                           ) s),
    'as_of',              now()
  );
$$;

revoke execute on function public.pmf_scoreboard() from public, anon, authenticated;
grant execute on function public.pmf_scoreboard() to service_role;
