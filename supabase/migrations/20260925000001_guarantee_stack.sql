-- The guarantee, rebuilt as a stack (2026-09-25).
--
-- Three promises the site now makes need facts the schema did not hold:
--
--   invoices.refunded_usd          money given back on an invoice. The rolling
--                                  gate now refunds a paid month the Record
--                                  stopped covering (it used to credit the next
--                                  invoice, which is worth nothing to a client
--                                  who leaves), and the exit true-up refunds what
--                                  was billed beyond the Record. The ledger
--                                  counts every invoice net of it.
--   clients.exit_trued_up_at       the true-up ran, once, when Managed Profit
--   clients.exit_refund_usd        ended, and what it refunded.
--   clients.late_teardown_month_at a Teardown later than 24 hours from the files
--                                  added a free month (free_months + 1), once.
--
-- Additive only; every column defaults to "nothing happened".

alter table public.invoices
  add column if not exists refunded_usd numeric(12, 2) not null default 0;

alter table public.clients
  add column if not exists exit_trued_up_at timestamptz,
  add column if not exists exit_refund_usd numeric(12, 2),
  add column if not exists late_teardown_month_at timestamptz;

comment on column public.invoices.gate_note is
  'voided | refunded | voided at exit (''credited'' only on decisions before 2026-09-25)';
