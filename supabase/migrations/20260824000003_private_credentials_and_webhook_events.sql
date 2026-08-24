-- Sensitive material lives in a private schema PostgREST never exposes.
-- SP-API refresh tokens are stored in Supabase Vault; this table only
-- holds the Vault secret id per client.

create schema if not exists private;
revoke all on schema private from anon, authenticated;

create table private.amazon_credentials (
  client_id uuid primary key references public.clients (id) on delete cascade,
  lwa_refresh_token_secret_id uuid,
  authorized_at timestamptz,
  updated_at timestamptz not null default now()
);
alter table private.amazon_credentials enable row level security;

-- Stripe webhook idempotency ledger: event ids we've already processed.
create table private.stripe_events (
  event_id text primary key,
  event_type text not null,
  received_at timestamptz not null default now()
);
alter table private.stripe_events enable row level security;
