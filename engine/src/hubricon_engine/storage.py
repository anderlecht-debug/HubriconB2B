"""Where files live: the private Supabase Storage buckets.

`intake` holds what clients send us (and their reports, under reports/).
`exports` holds the zips the machine builds when a client asks for everything
we hold (terms §11): private, no storage policies, reachable only by the
service role and by a signed link that expires. Migration
20261001000005_exit_and_export.sql creates it; until it is applied every
upload here fails, and the caller falls back to the founder running
`hubricon export` by hand.
"""

from datetime import datetime, timedelta, timezone

from supabase import Client

BUCKET = "intake"
EXPORTS_BUCKET = "exports"
# How long the emailed download link works. The email says so, with the date.
EXPORT_LINK_DAYS = 7


def download(db: Client, storage_path: str) -> bytes:
    return db.storage.from_(BUCKET).download(storage_path)


def publish_export(db: Client, client_id: str, ref: str, blob: bytes, filename: str,
                   days: int = EXPORT_LINK_DAYS) -> dict:
    """Put one export zip in the private bucket and sign a link to it.

    Returns {"path", "url", "expires_at"}. Raises on any failure (the bucket
    missing, the upload refused, a link that did not come back), so the caller
    never emails a link that does not work. The link downloads the file under
    `filename`, not under its storage path."""
    path = f"{client_id}/{ref}.zip"
    bucket = db.storage.from_(EXPORTS_BUCKET)
    bucket.upload(path, blob, {"content-type": "application/zip", "upsert": "true"})
    signed = bucket.create_signed_url(path, int(days * 86400), {"download": filename}) or {}
    url = signed.get("signedURL") or signed.get("signedUrl")
    if not url:
        raise RuntimeError(f"no signed link came back for {EXPORTS_BUCKET}/{path}")
    return {"path": path, "url": url, "expires_at": datetime.now(timezone.utc) + timedelta(days=days)}


def exports_ready(db: Client) -> tuple[bool, str]:
    """Can the machine store an export? Read-only: lists the bucket's root.
    Used by `hubricon promises`; never raises."""
    try:
        db.storage.from_(EXPORTS_BUCKET).list("", {"limit": 1})
        return True, f"the private '{EXPORTS_BUCKET}' bucket is reachable"
    except Exception as err:
        return False, (f"the '{EXPORTS_BUCKET}' bucket is not reachable ({str(err)[:60]}); apply "
                       "supabase/migrations/20261001000005_exit_and_export.sql")
