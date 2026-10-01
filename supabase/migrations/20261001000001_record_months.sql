-- The Record, month by month (engine/src/hubricon_engine/monthly.py).
--
-- HUBRICON_SPEC.md, "The mechanics": each month closes on a fixed date, the
-- attribution runs once on the closed month, and that one number decides the
-- month's invoice. One row per client, retainer month and channel, written by the
-- weekly sweep a week after the month ends. The row stands: only a dispute may
-- change it afterwards, and a dispute only ever takes dollars off.

create table if not exists public.record_months (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients (id) on delete cascade,
  channel text not null default 'amazon',
  month_index integer not null check (month_index >= 0),
  month_start date not null,
  month_end date not null,
  free boolean not null default false,
  attributed_usd numeric(12, 2) not null,
  fee_usd numeric(12, 2) not null,
  clears boolean not null,
  moves jsonb not null default '[]'::jsonb,
  disputed_usd numeric(12, 2) not null default 0 check (disputed_usd >= 0),
  dispute_notes text,
  measured_at timestamptz not null default now(),
  unique (client_id, month_index, channel)
);
alter table public.record_months enable row level security;

create policy "members read own record months"
  on public.record_months for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index if not exists record_months_client_idx on public.record_months (client_id, month_index);

create or replace function public.record_months_stand() returns trigger
language plpgsql set search_path = public as $$
begin
  if (new.client_id, new.channel, new.month_index, new.month_start, new.month_end, new.free,
      new.attributed_usd, new.fee_usd, new.clears, new.moves, new.measured_at)
     is distinct from
     (old.client_id, old.channel, old.month_index, old.month_start, old.month_end, old.free,
      old.attributed_usd, old.fee_usd, old.clears, old.moves, old.measured_at) then
    raise exception 'a measured month stands: only a dispute may change it';
  end if;
  if new.disputed_usd < old.disputed_usd then
    raise exception 'a dispute only ever takes dollars off a month';
  end if;
  return new;
end $$;

drop trigger if exists record_months_stand on public.record_months;
create trigger record_months_stand before update on public.record_months
  for each row execute function public.record_months_stand();

-- Which month an invoice billed, as the gate decided it.
alter table public.invoices add column if not exists gate_month_index integer;
