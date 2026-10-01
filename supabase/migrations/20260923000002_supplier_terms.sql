-- Supplier terms on the cost sheet (engine/models/replenishment.py). All
-- optional: a blank column means the decision it feeds is not priced.
alter table public.cogs_inputs
  add column if not exists supplier text,
  add column if not exists moq_units integer,
  add column if not exists case_pack_units integer,
  add column if not exists price_break_qty integer,
  add column if not exists price_break_unit_cost_usd numeric(12, 4),
  add column if not exists air_freight_per_unit_usd numeric(12, 4),
  add column if not exists air_lead_time_days integer;
