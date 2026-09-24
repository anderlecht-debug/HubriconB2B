-- Randomised price experiments (engine/models/price_experiment.py).
-- `design` is the block schedule the engine drew (arms, prices, seed, blocks);
-- `analysis` is what the settlement file said once the blocks had run. Both are
-- jsonb because their shape belongs to the engine, and a fixed-price test
-- carries neither.
alter table public.price_tests
  add column if not exists design jsonb,
  add column if not exists analysis jsonb,
  add column if not exists directive_id uuid references public.directives (id) on delete set null;
