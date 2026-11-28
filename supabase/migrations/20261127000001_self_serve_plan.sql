-- The self-serve plan: $1,000 a month by card, paid on /start.
--
-- Until now a client row was made by the operator from a booked call, and the
-- plan was 'retainer' ($6,000 a month by ACH, a free first month, every invoice
-- held at draft for the gate) or 'recovery' (a share of reimbursements). The
-- new offer is paid on the spot: Stripe Checkout takes the card, and the
-- webhook (lib/provision.js) writes the client row the moment the payment
-- lands, with
--
--   plan                   'self_serve'
--   status                 'active'
--   monthly_fee_usd        1000
--   free_months            0
--   stripe_customer_id     the Checkout customer
--   stripe_subscription_id the card subscription Checkout created
--   retainer_started_at    the moment of payment
--   retainer_source        'first_invoice'
--
-- so the engine reads them as a paid client waiting for files. Nothing else in
-- the schema changes: the fee, the free months and both Stripe ids are columns
-- that already exist.
--
-- The plan decides what the engine may do. For 'self_serve' it never creates
-- an ACH subscription, never holds an invoice for the month gate, and never
-- voids, credits or trues up: Stripe charges the card and the client cancels
-- in Stripe's own portal (api/billing.js).

alter table public.clients drop constraint if exists clients_plan_check;
alter table public.clients add constraint clients_plan_check
  check (plan in ('retainer', 'recovery', 'self_serve'));

-- The welcome email after payment is sent once per Checkout session. The
-- dedupe row lives in client_emails (client_id, kind, ref_id), whose kind is
-- free text, so no change is needed there.
