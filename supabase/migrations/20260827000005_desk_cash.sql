-- Second aperture through the engine wall: the latest run's cash-horizon
-- cone for the caller's own workspace. Deliverable-shaped output only —
-- percentile paths, ruin probability, the wire schedule — same posture as
-- desk_metrics(); raw model tables stay service-role only.

create or replace function public.desk_cash()
returns table (
  horizon_days integer,
  n_paths integer,
  starting_cash numeric,
  monthly_fixed_costs numeric,
  p_ruin numeric,
  min_p5 numeric,
  min_p5_day integer,
  details jsonb,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  with latest as (
    select distinct on (client_id) id, client_id
    from public.model_runs
    where status = 'succeeded'
    order by client_id, started_at desc
  )
  select c.horizon_days, c.n_paths, c.starting_cash, c.monthly_fixed_costs,
         c.p_ruin, c.min_p5, c.min_p5_day, c.details, c.created_at
  from public.cash_horizon_results c
  join latest l on l.id = c.run_id and l.client_id = c.client_id
  where c.client_id in (
    select client_id from public.client_users
    where user_id = (select auth.uid())
  );
$$;

revoke execute on function public.desk_cash() from public, anon;
grant execute on function public.desk_cash() to authenticated, service_role;
