-- The engine goes fully internal. Clients see deliverables — the briefing,
-- decisions, the ledger, the plan, the watch — never raw model output.
-- Dropping these policies leaves the model tables RLS-enabled with no
-- policies at all, so only the service role (the engine) can touch them.

drop policy if exists "members read own model runs" on public.model_runs;
drop policy if exists "members read own inventory sims" on public.inventory_sim_results;
drop policy if exists "members read own elasticities" on public.elasticity_results;
drop policy if exists "members read own ad efficiency" on public.ad_efficiency_results;
drop policy if exists "members read own margins" on public.margin_results;

-- The one aperture through the wall: per-period revenue and net-profit
-- totals from the latest succeeded run, scoped to the caller's own client.
-- This powers the position tiles and Growth Plan pacing without exposing
-- a single per-SKU row, fit parameter, or simulation.
create or replace function public.desk_metrics()
returns table (period_start date, revenue numeric, net_margin numeric)
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
  select m.period_start,
         sum(m.revenue)::numeric,
         sum(m.net_margin)::numeric
  from public.margin_results m
  join latest l on l.id = m.run_id and l.client_id = m.client_id
  where m.client_id in (
    select client_id from public.client_users
    where user_id = (select auth.uid())
  )
  group by m.period_start
  order by m.period_start;
$$;

revoke execute on function public.desk_metrics() from public, anon;
grant execute on function public.desk_metrics() to authenticated, service_role;
