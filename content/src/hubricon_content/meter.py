"""What one film cost to make (VISUAL_SPEC.md §13.4), counted where it is spent.

A film is made on the founder's machine, so its meter is a ledger beside it,
content/videos/<slug>/meter.json, not the engine's database meter: API
requests by source (sourcing writes sources/requests.json) and the Higgsfield
credits the texture step reports. Narration and sound cost nothing to make: the
founder reads the films himself and the sound library is on file. Quantities only; a price is a separate question. Never
fatal: a failed write is dropped, and the work never waits on it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import script as scriptmod


def count(slug: str, service: str, unit: str, quantity: float, note: str | None = None, **extra) -> None:
    try:
        p = scriptmod.video_dir(slug) / "meter.json"
        rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        rows.append({"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "service": service, "unit": unit,
                     "quantity": quantity, **({"note": note} if note else {}), **extra})
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


def summary(slug: str) -> dict:
    """What the film has cost so far: AI tokens by step (cost-weighted, against each step's budget),
    and every other service's quantities."""
    p = scriptmod.video_dir(slug) / "meter.json"
    rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    ai, other = {}, {}
    for r in rows:
        if r.get("service") == "claude":
            a = ai.setdefault(r.get("step", "?"), {"runs": 0, "weighted": 0.0, "stopped": 0, "seconds": 0.0})
            a["runs"] += 1
            a["weighted"] += float(r.get("quantity", 0))
            a["stopped"] += 1 if r.get("stopped") else 0
            a["seconds"] += float(r.get("seconds", 0))
        else:
            k = f"{r.get('service')} ({r.get('unit')})"
            other[k] = other.get(k, 0) + float(r.get("quantity", 0))
    return {"slug": slug, "ai_weighted_tokens": round(sum(a["weighted"] for a in ai.values())),
            "ai_by_step": {k: {**v, "weighted": round(v["weighted"])} for k, v in ai.items()}, "other": other}
