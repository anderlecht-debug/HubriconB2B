from supabase import Client

BUCKET = "intake"


def download(db: Client, storage_path: str) -> bytes:
    return db.storage.from_(BUCKET).download(storage_path)
