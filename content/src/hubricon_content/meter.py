"""What one film cost to make (VISUAL_SPEC.md §13.4), counted where it is spent.

A film is made on the founder's machine, so its meter is a ledger beside it,
content/videos/<slug>/meter.json, not the engine's database meter: ElevenLabs
characters sent for narration, sound effects generated, API requests by
source (sourcing writes sources/requests.json), Higgsfield credits the
texture step reports. Quantities only; a price is a separate question. Never
fatal: a failed write is dropped, and the work never waits on it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import script as scriptmod


def count(slug: str, service: str, unit: str, quantity: float, note: str | None = None) -> None:
    try:
        p = scriptmod.video_dir(slug) / "meter.json"
        rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        rows.append({"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "service": service, "unit": unit,
                     "quantity": quantity, **({"note": note} if note else {})})
        p.write_text(json.dumps(rows, indent=0) + "\n", encoding="utf-8")
    except Exception:
        pass


def summary(slug: str) -> dict:
    """Totals by service and unit, with the sourcing requests folded in."""
    d = scriptmod.video_dir(slug)
    out: dict = {}
    p = d / "meter.json"
    for r in json.loads(p.read_text(encoding="utf-8")) if p.exists() else []:
        key = f"{r['service']}:{r['unit']}"
        out[key] = out.get(key, 0) + r["quantity"]
    req = d / "sources" / "requests.json"
    if req.exists():
        for src, n in json.loads(req.read_text(encoding="utf-8")).items():
            if isinstance(n, (int, float)):
                out[f"{src}:requests"] = out.get(f"{src}:requests", 0) + n
    return out
