"""The usage ledger, content/assets/usage.json (VISUAL_SPEC.md §6.7).

An asset appears once in a film and not again within the next ten films, so a
long-running series never shows the same port twice in a fortnight. The ledger
keeps, per film in the order they were made, the asset ids it used and their
perceptual hashes, so the filters can catch the same clip under another id (a
Pexels clip re-uploaded to Pixabay). shots.py reads the same file with the same
shape: {"films": [{"slug": …, "assets": [ids]}]}; the hashes ride alongside.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .. import shots
from ..shots import USAGE_WINDOW

USAGE = shots.USAGE


def read(path: Path | None = None) -> dict:
    path = Path(path or USAGE)
    if not path.exists():
        return {"films": []}
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.setdefault("films", [])
    return doc


def window(slug: str, ledger: dict | None = None) -> list[dict]:
    """The films whose assets `slug` may not reuse: the last ten, itself excluded
    (the same reading as shots.validate)."""
    films = (ledger if ledger is not None else read())["films"][-USAGE_WINDOW:]
    return [f for f in films if f.get("slug") != slug]


def window_ids(slug: str, ledger: dict | None = None) -> dict[str, str]:
    """Each asset id in the window, mapped to the film that used it."""
    return {a: f["slug"] for f in window(slug, ledger) for a in f.get("assets", [])}


def window_hashes(slug: str, ledger: dict | None = None) -> dict[str, tuple[str, str]]:
    """Each hashed asset in the window: id → (phash, where), for filters.media."""
    return {a: (h, f"in {f['slug']}, inside the last ten films") for f in window(slug, ledger)
            for a, h in (f.get("phash") or {}).items() if h}


def record_film(slug: str, ids: list[str], phashes: dict[str, str] | None = None, path: Path | None = None) -> dict:
    """Record what a film used. Refuses an asset twice in the film or one inside the window;
    recording the same film again replaces its entry in place."""
    path = Path(path or USAGE)
    ledger = read(path)
    seen, twice = set(), []
    for a in ids:
        if a in seen and a not in twice:
            twice.append(a)
        seen.add(a)
    if twice:
        raise ValueError(f"{slug}: an asset appears once per film; twice: {', '.join(twice)} (§6.7)")
    clash = {a: f for a, f in window_ids(slug, ledger).items() if a in seen}
    if clash:
        raise ValueError(f"{slug}: used inside the last {USAGE_WINDOW} films: "
                         + ", ".join(f"{a} ({f})" for a, f in clash.items()) + " (§6.7)")
    entry = {"slug": slug, "assets": list(ids), "phash": {a: h for a, h in (phashes or {}).items() if a in seen},
             "recorded": date.today().isoformat()}
    films = ledger["films"]
    at = next((i for i, f in enumerate(films) if f.get("slug") == slug), None)
    if at is None:
        films.append(entry)
    else:
        films[at] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return ledger
