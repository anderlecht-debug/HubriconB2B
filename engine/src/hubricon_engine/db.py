"""Supabase access. The service role bypasses RLS, exactly like the webhook."""

import sys

from supabase import Client, create_client

from . import config

UPSERT_CHUNK = 500


def connect() -> Client:
    cfg = config.load()
    return create_client(cfg["supabase_url"], cfg["service_role_key"])


def resolve_client(db: Client, ident: str) -> dict:
    """Accepts a client uuid, uuid prefix, or contact email."""
    q = db.table("clients").select(
        "id, company_name, contact_email, status, contact_name, brand_terms, goals, "
        "cash_on_hand, cash_as_of, monthly_fixed_costs, created_at"
    )
    if "@" in ident:
        rows = q.eq("contact_email", ident.lower()).execute().data
    else:
        # uuid columns reject LIKE, so prefix-match client-side (roster is small)
        rows = [r for r in q.execute().data if r["id"].startswith(ident.lower())]
    if not rows:
        sys.exit(f"No client matches {ident!r} — try `hubricon clients`.")
    if len(rows) > 1:
        listing = ", ".join(f"{r['id'][:8]} ({r['company_name']})" for r in rows)
        sys.exit(f"{ident!r} is ambiguous: {listing}")
    return rows[0]


def chunked_upsert(db: Client, table: str, rows: list[dict], on_conflict: str) -> int:
    """Idempotent bulk write; input must already be deduped on the conflict key."""
    for i in range(0, len(rows), UPSERT_CHUNK):
        db.table(table).upsert(rows[i : i + UPSERT_CHUNK], on_conflict=on_conflict).execute()
    return len(rows)


def fetch_all(db: Client, table: str, client_id: str, page: int = 1000) -> list[dict]:
    """PostgREST caps responses, so page through the client's rows."""
    out: list[dict] = []
    start = 0
    while True:
        rows = (
            db.table(table)
            .select("*")
            .eq("client_id", client_id)
            .range(start, start + page - 1)
            .execute()
            .data
        )
        out.extend(rows)
        if len(rows) < page:
            return out
        start += page
