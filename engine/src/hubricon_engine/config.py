"""Environment loading: same two secrets the Vercel functions use."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]


def load() -> dict[str, str]:
    load_dotenv(REPO_ROOT / ".env")
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Set {', '.join(missing)} (env or {REPO_ROOT / '.env'}) before running.")
    return {
        "supabase_url": os.environ["SUPABASE_URL"],
        "service_role_key": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    }
