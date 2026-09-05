-- Directives stop being prose.
--
-- Until now a directive carried a module, a sentence and a number. Nothing
-- machine-readable said WHICH sku, WHICH search terms, WHICH metric, what the
-- pre-state was, or what later export would prove it — so the only way a
-- dollar could ever be marked "measured" was the founder typing it in, and the
-- ledger that is supposed to prove the retainer's worth sat at zero.
--
-- Each directive now carries the structured subject it acts on and the
-- evidence it was computed from, so a later sweep can measure it against the
-- client's own next export. This is the measurement engine's data model.

alter table public.directives
  -- The run's platform. Denormalised from model_runs.params so a measurement
  -- pass can scope by channel without joining every run.
  add column channel text not null default 'amazon'
    check (channel in ('amazon', 'shopify')),
  -- Measurement family (measurement.FAMILIES): names how this directive is
  -- proved, not what module it belongs to.
  add column kind text,
  -- sha1(module|kind|subject): one finding, one open directive, stable across
  -- runs so the weekly sweep re-drafting the same fee creep does not re-issue it.
  add column dedupe_key text,
  -- The BEFORE half of the before/after, captured at draft time from the
  -- client's own rows. Without this the after-export has nothing to be
  -- compared against; measurement.py reads it, never re-derives it.
  add column evidence jsonb not null default '{}'::jsonb,
  -- Whether the standing mandate covers this (terms.html §6: bounded price
  -- steps and advertising corrections) or it needs an explicit yes.
  add column mandate text not null default 'explicit'
    check (mandate in ('standing', 'explicit')),
  -- Which tier of the attribution standard the measured number earned.
  add column attribution text
    check (attribution in ('direct', 'isolated', 'attributable', 'none')),
  -- terms.html §6 promises the client is told before anything goes live and
  -- may veto by reply. notified_at is the proof we told them; veto_closes_at
  -- is only ever set when that notification actually went out, because
  -- silence from someone who was never told is not consent.
  add column veto_closes_at timestamptz,
  add column notified_at timestamptz,
  add column auto_approved_at timestamptz,
  -- Founder-executed work, on the record: welcome.html promises first fixes
  -- go live in week 1, and nothing recorded that they had.
  add column executed_at timestamptz,
  add column executed_by text,
  add column execution_ref text,
  add column measured_run_id uuid references public.model_runs (id) on delete set null;

-- Two new terminal states.
--   closed — executed, but no honest measurement is possible from the client's
--            exports (an inventory reorder's avoided stockout is unobservable;
--            a diagnostic anomaly has no action to measure). Out of BOTH
--            measured and identified: we prove the work and bank nothing.
--   lapsed — an explicit-mandate directive nobody answered. Silence is not a
--            veto and it is not consent, so it gets its own state rather than
--            being quietly approved or quietly declined.
alter table public.directives drop constraint if exists directives_status_check;
alter table public.directives add constraint directives_status_check
  check (status in ('draft', 'issued', 'approved', 'declined', 'done', 'closed', 'lapsed'));

-- measured_impact_usd = 0 or negative stays reserved for "measured, and it did
-- not pay". portal.html already promises the misses stay on the record, so the
-- schema has to let a miss exist and be told apart from "not measured yet".

update public.directives d
   set channel = coalesce(r.params ->> 'channel', 'amazon')
  from public.model_runs r
 where r.id = d.run_id
   and r.params ->> 'channel' is not null;

-- The duplicate-draft fix, made structural.
--
-- _draft_for_run deleted stale drafts with .eq("run_id", run_id), but every
-- sweep opens a NEW model_runs row — so the delete never matched anything and
-- the same finding was re-drafted every Monday, ready to be issued and counted
-- twice. Scoping the delete by channel is the code half; this index is the
-- half that cannot be forgotten.
create unique index directives_open_dedupe_key
  on public.directives (client_id, channel, dedupe_key)
  where dedupe_key is not null and status in ('draft', 'issued', 'approved');

create index directives_client_kind_idx on public.directives (client_id, kind, status);

-- The operational record of a price step, linked to the directive that
-- proposed it. The price test stays operational (it tracks Buy Box share);
-- the directive is what the ledger measures, from margin_results, because
-- that is where the dollars actually are.
alter table public.price_tests
  add column directive_id uuid references public.directives (id) on delete set null;

-- terms.html §6: "a step reversed if it costs you the sale". A client who
-- reads the mail two days late had no path to that — respond_to_directive is
-- valid only on 'issued'. This one is valid on an approved directive that has
-- not yet been measured, and records the reversal as a decline so the ledger
-- never banks a step the client pulled.
create or replace function public.veto_directive(p_directive_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count integer;
begin
  update public.directives d
     set status = 'declined',
         responded_at = now(),
         responded_by = (select auth.uid()),
         measurement_notes = concat_ws(
           ' ',
           d.measurement_notes,
           'Reversed by the client on ' || to_char(now(), 'YYYY-MM-DD') || '.'
         )
   where d.id = p_directive_id
     and d.status = 'approved'
     and d.measured_at is null
     and d.client_id in (
       select client_id from public.client_users where user_id = (select auth.uid())
     );
  get diagnostics v_count = row_count;
  return v_count > 0;
end;
$$;

revoke execute on function public.veto_directive(uuid) from public, anon;
grant execute on function public.veto_directive(uuid) to authenticated, service_role;
