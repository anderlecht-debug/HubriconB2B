-- The Seal: every promise on the Profit Record, fingerprinted before the move
-- goes live, and every measurement chained after it.
--
-- "We write the expected dollars down before a move goes live" was true and
-- could not be checked: the promise lived in a directives row Hubricon could
-- edit, so a client, a buyer's diligence team or a lender had our word for it.
-- This table turns the claim into arithmetic anyone can redo.
--
-- One row per entry, and two entries per move:
--
--   called    written by issue.issue_drafts when the move is issued, BEFORE
--             the email that states it goes out: the move, its target, the
--             expected dollars, the promised band, the mandate, and a SHA-256
--             of the evidence the number came from.
--   measured  written when the measurement pass banks or closes the move:
--             measured dollars, how we know, and the leaf of the called entry
--             it answers.
--
-- Each row carries the entry's canonical document (RFC 8785 JSON, built by
-- engine/src/hubricon_engine/seal.py), its leaf = sha256(document), and its
-- place in two hash chains:
--
--   the client's own   seq, prev_head, head
--   one across clients global_seq, global_prev_head, global_head
--
-- where head_n = sha256(head_{n-1} || leaf_n) over the raw 32-byte digests and
-- head_0 is 64 zeros. The engine computes all of it. The database re-checks
-- the arithmetic (the two CHECKs on head), refuses a row that does not extend
-- both chains (record_seals_extend), and refuses every update and delete
-- (record_seals_append_only): once written, a row can only be read. The one
-- exception is below.
--
-- Deleting a client (privacy §5) sets client_id to null through the foreign
-- key, and the trigger then drops that row's document and directive id. Their
-- words go; the fingerprint stays, so every other client's global chain still
-- verifies. Nothing else may change a row.
--
-- public_record_seal() joins public_results() and public_case_study() as a
-- function anon may execute: the global head, how many entries it covers, and
-- when the last was sealed. A hash reveals nothing, and any capture of it (a Wayback
-- snapshot, an OpenTimestamps proof — neither is wired up yet) pins every
-- entry beneath it.
--
-- Not applied by the engine; apply by hand. Until it is, moves are issued and
-- emailed unsealed, and `hubricon promises` says so. After it is,
-- `hubricon seal sync` seals the moves issued before it, labelled late.

create table public.record_seals (
  global_seq bigint primary key check (global_seq > 0),
  -- set null, not cascade: see the privacy note above
  client_id uuid references public.clients (id) on delete set null,
  seq integer not null check (seq > 0),
  entry text not null check (entry in ('called', 'measured')),
  -- called:<directive id> or measured:<directive id>:<measured_at>. One of
  -- each, so re-running a sweep can never seal the same thing twice.
  entry_key text not null unique,
  -- No foreign key: a seal must outlive any edit to the row it sealed, and
  -- verification reads the directive by this id to compare.
  directive_id uuid,
  document jsonb,
  leaf text not null check (leaf ~ '^[0-9a-f]{64}$'),
  prev_head text not null check (prev_head ~ '^[0-9a-f]{64}$'),
  head text not null check (head ~ '^[0-9a-f]{64}$'),
  global_prev_head text not null check (global_prev_head ~ '^[0-9a-f]{64}$'),
  global_head text not null check (global_head ~ '^[0-9a-f]{64}$'),
  sealed_at timestamptz not null,
  unique (client_id, seq),
  constraint record_seals_head_is_the_chain
    check (head = encode(sha256(decode(prev_head, 'hex') || decode(leaf, 'hex')), 'hex')),
  constraint record_seals_global_head_is_the_chain
    check (global_head = encode(sha256(decode(global_prev_head, 'hex') || decode(leaf, 'hex')), 'hex')),
  -- a live row names its client and carries its words; only a deleted
  -- client's rows are bare
  constraint record_seals_document_belongs
    check ((document is null and client_id is null)
           or (document is not null and client_id is not null
               and document ->> 'entry' = entry
               and document ->> 'client_id' = client_id::text
               and document ->> 'directive_id' = directive_id::text))
);
alter table public.record_seals enable row level security;

-- The client reads their own Record's seals. Nobody writes here but the
-- service role, and the triggers below hold even the service role to append.
create policy "members read own seals"
  on public.record_seals for select to authenticated
  using (client_id in (select client_id from public.client_users where user_id = (select auth.uid())));

create index record_seals_directive_idx on public.record_seals (directive_id);

comment on table public.record_seals is
  'The Seal (engine seal.py): one row per called or measured entry on a client''s Profit Record, hash-chained per client and globally. Append-only; verify with `hubricon seal verify`.';

-- A new row must extend both chains: its prev_head is the head of the entry
-- before it, in the client's chain and in the global one. With the unique
-- keys above, two writers racing for the same number cannot both land, and a
-- gap or a fork cannot land at all.
create or replace function public.record_seals_extend()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_prev text;
begin
  if new.client_id is null or new.document is null then
    raise exception 'record_seals: a new entry needs its client and its document';
  end if;
  if new.seq = 1 then
    v_prev := repeat('0', 64);
  else
    select s.head into v_prev
      from public.record_seals s
     where s.client_id = new.client_id and s.seq = new.seq - 1;
  end if;
  if v_prev is distinct from new.prev_head then
    raise exception 'record_seals: entry % does not extend the chain of client %', new.seq, new.client_id;
  end if;
  if new.global_seq = 1 then
    v_prev := repeat('0', 64);
  else
    select s.global_head into v_prev
      from public.record_seals s
     where s.global_seq = new.global_seq - 1;
  end if;
  if v_prev is distinct from new.global_prev_head then
    raise exception 'record_seals: global entry % does not extend the global chain', new.global_seq;
  end if;
  return new;
end;
$$;

create trigger record_seals_extend
  before insert on public.record_seals
  for each row execute function public.record_seals_extend();

-- Append-only, for the service role too. The single permitted change is the
-- foreign key's own: a deleted client's rows lose their words and keep their
-- place, and every chain column must be exactly what it was. "Deleted" is
-- checked, not assumed: setting client_id to null by hand while the client
-- still exists is refused like any other edit, so an entry cannot be orphaned
-- to free its number for a replacement.
create or replace function public.record_seals_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    if old.client_id is not null and new.client_id is null
       and not exists (select 1 from public.clients c where c.id = old.client_id)
       and new.global_seq = old.global_seq and new.seq = old.seq
       and new.entry = old.entry and new.entry_key = old.entry_key
       and new.leaf = old.leaf
       and new.prev_head = old.prev_head and new.head = old.head
       and new.global_prev_head = old.global_prev_head and new.global_head = old.global_head
       and new.sealed_at = old.sealed_at then
      new.document := null;
      new.directive_id := null;
      return new;
    end if;
  end if;
  raise exception 'record_seals is append-only: % refused', tg_op;
end;
$$;

create trigger record_seals_append_only
  before update or delete on public.record_seals
  for each row execute function public.record_seals_append_only();

create trigger record_seals_no_truncate
  before truncate on public.record_seals
  for each statement execute function public.record_seals_append_only();

-- The public head, for the site and for any external anchor added later. All
-- three figures come from the same row, so the count is always the head's own
-- position. Nothing here names a client or a promise.
create or replace function public.public_record_seal()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(
    (select jsonb_build_object('head', s.global_head,
                               'entries', s.global_seq,
                               'last_sealed_at', s.sealed_at)
       from public.record_seals s
      order by s.global_seq desc
      limit 1),
    jsonb_build_object('head', repeat('0', 64), 'entries', 0, 'last_sealed_at', null)
  );
$$;

revoke execute on function public.public_record_seal() from public;
grant execute on function public.public_record_seal() to anon, authenticated, service_role;
