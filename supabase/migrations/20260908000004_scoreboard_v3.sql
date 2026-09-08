-- The scoreboard, continued past "paid".
--
-- Two things were wrong with the old one. `renewed` ran from created_at, the
-- provisioning date, while everything else — the free-month clock, the ledger's
-- denominator, the day-30 pass — runs from retainer_started_at; so the PMF bar
-- and the billing code disagreed about who had renewed. And the funnel stopped
-- at paid: nothing counted a consent, a testimonial, a referral, or how long a
-- client waited for Issue 001. Those are the arrows of the loop this business
-- is meant to be, and a loop nobody measures is a line.

alter table public.teardown_events drop constraint if exists teardown_events_kind_check;
alter table public.teardown_events add constraint teardown_events_kind_check
  check (kind in ('delivered', 'open', 'click', 'page_view', 'cta_click', 'video_watch',
                  'reply', 'booked', 'bounce', 'complaint', 'unsubscribe'));

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
    -- Past the free month(s) on the SAME clock billing uses, and billing has
    -- actually started: the first real retention signal.
    select * from paid
    where status = 'active'
      and stripe_subscription_id is not null
      and retainer_started_at is not null
      and now() > retainer_started_at + make_interval(months => coalesce(free_months, 1))
  ),
  speed as (
    select extract(epoch from (first_issue_at - exports_landed_at)) / 3600.0 as hours
      from real_clients
     where first_issue_at is not null and exports_landed_at is not null
  ),
  value_speed as (
    select extract(epoch from (first_value_at - exports_landed_at)) / 86400.0 as days
      from real_clients
     where first_value_at is not null and exports_landed_at is not null
  )
  select jsonb_build_object(
    'prospects_total',    (select count(*) from public.prospects),
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
    -- the loop past paid
    'asks_sent',          (select count(*) from public.client_touches t
                            join real_clients c on c.id = t.client_id where t.kind = 'consent_ask'),
    'consent_granted',    (select count(distinct k.client_id) from public.consents k
                            join real_clients c on c.id = k.client_id where k.granted is true),
    'testimonials',       (select count(*) from public.consents k
                            join real_clients c on c.id = k.client_id
                            where k.kind = 'testimonial' and k.granted is true
                              and coalesce(k.testimonial, '') <> ''),
    'results_published',  (select count(*) from public.results r
                            join real_clients c on c.id = r.client_id where r.published),
    'referral_links',     (select count(*) from real_clients where referral_code is not null),
    'referral_booked',    (select count(*) from public.bookings where not is_test and ref_code is not null),
    'referral_paid',      (select count(*) from paid where referred_by_client_id is not null),
    'partner_booked',     (select count(*) from real_clients where referred_by_partner_id is not null),
    'partner_paid',       (select count(*) from paid where referred_by_partner_id is not null),
    'median_hours_to_first_issue',
                          (select percentile_cont(0.5) within group (order by hours) from speed),
    'median_days_to_first_value',
                          (select percentile_cont(0.5) within group (order by days) from value_speed),
    -- the cold teardown lane, joined to what came back
    'teardowns_sent',     (select count(*) from public.teardowns where status = 'sent'),
    'teardowns_replied',  (select count(distinct teardown_id) from public.teardown_events where kind = 'reply'),
    'teardowns_booked',   (select count(distinct teardown_id) from public.teardown_events where kind = 'booked'),
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
