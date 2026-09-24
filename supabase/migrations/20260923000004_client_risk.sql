-- The client's own risk tolerance, stated rather than assumed (engine iteration 25).
-- risk_budget_share: the share of a SKU's (or a campaign set's) trailing monthly
-- net that one move's worst realistic case may put at risk before it needs an
-- explicit yes; every step, reallocation and markdown is sized against it.
-- min_cash_buffer_usd: the balance below which the cash cone counts a path as
-- ruined, in place of zero.
alter table public.clients
  add column if not exists risk_budget_share numeric(4, 3) not null default 0.150
    check (risk_budget_share between 0.05 and 0.30),
  add column if not exists min_cash_buffer_usd numeric(12, 2) not null default 0;
