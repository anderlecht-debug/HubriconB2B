-- Speed to value, measured; and the calibration table the cold engine reads.
--
-- welcome.html promises the written Teardown inside 24 hours of the exports
-- landing. Nothing recorded when they landed or when Issue 001 went out, so
-- the promise could only be checked by reading two tables and doing the
-- subtraction by hand. Three set-once timestamps make it a number the digest
-- can carry and the promise check can fail.

alter table public.clients
  add column exports_landed_at timestamptz,   -- first pass that found typed data
  add column first_issue_at timestamptz,      -- Issue 001 published
  add column first_value_at timestamptz;      -- first measured or recovered dollar

-- What consenting clients' real accounts say the cold engine's guesses should
-- be. Every row carries how many clients and observations stand behind it;
-- `method = 'insufficient'` with a null value is a row that says "not yet"
-- rather than a number nobody should trust. Written only by `hubricon
-- calibrate`, from clients who granted the separate `calibration` consent.
create table public.calibration (
  key text primary key,                       -- e.g. amazon.referral_rate.home & kitchen
  value numeric,
  low numeric,
  high numeric,
  n_clients integer not null default 0,
  n_obs integer not null default 0,
  method text not null,
  note text,
  computed_at timestamptz not null default now()
);
alter table public.calibration enable row level security;   -- service role only
