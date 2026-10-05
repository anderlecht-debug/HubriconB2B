-- The journey's stages (engine/src/hubricon_engine/lifecycle.py).
--
-- Until now every booking became a `pending` client and the machine had no way
-- to know whether anyone had said yes or no on the call. The yes was already
-- recordable (`retainer_started_at`, source 'client_yes', by `hubricon retainer`);
-- this adds the no, so a prospect who declines is sent nothing more unasked, and
-- the client emails the stages need.
--
-- Safe to apply before or after the code: the code reads 'declined' only where
-- it can be written, and a client_touches insert of an unknown kind fails loud
-- in the operator's warnings rather than sending twice.

alter table public.clients drop constraint if exists clients_status_check;
alter table public.clients add constraint clients_status_check
  check (status in ('pending', 'active', 'past_due', 'churned', 'declined'));

alter table public.clients add column if not exists declined_at timestamptz;

alter table public.client_touches drop constraint if exists client_touches_kind_check;
alter table public.client_touches add constraint client_touches_kind_check
  check (kind in ('welcome', 'nudge', 'files', 'teardown_ready', 'consent_ask', 'referral_credit', 'downsell',
                  'recovery_welcome',
                  -- 2026-10-01, the journey:
                  'call_prep',    -- on booking: what the call is and what to have ready
                  'agreed'));     -- on the yes: the Proving Month's dates and what happens next
