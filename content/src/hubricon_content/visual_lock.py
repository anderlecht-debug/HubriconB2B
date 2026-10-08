"""The long films' look, frozen once the founder approves the visual trial
(VISUAL_SPEC.md §12, phase 5). Until then nothing long renders for publishing;
after, a film renders only on the look he approved.

`hubricon-content visual-lock` is his call, once: it fingerprints the files the
look lives in and the AI preamble, writes content/assets/visual-lock.json and
sets the queue's `visual_locked`. The 2026-10-01 style lock of the short films
(content/film/lock.mjs) stays as it is.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

from .state import CONTENT_DIR

REPO = CONTENT_DIR.parent
LOCK = CONTENT_DIR / "assets" / "visual-lock.json"
LOOK = ["assets/hubricon.css", "content/assets/tokens.json", "content/assets/grade.json", "content/film/styles.json",
        "content/film/film.css", "content/film/shots.css", "content/film/shots.mjs", "content/film/scenes.mjs",
        "content/src/hubricon_content/scenes/base.py", "content/src/hubricon_content/scenes/charts.py"]


def fingerprints() -> dict:
    from .sourcing import PREAMBLE
    out = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in LOOK}
    out["ai-preamble"] = hashlib.sha256(PREAMBLE.encode()).hexdigest()
    return out


def lock(q: dict, note: str = "") -> dict:
    doc = {"locked_on": date.today().isoformat(), "from": "content/videos/visual-trial", "note": note, "files": fingerprints()}
    LOCK.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    q["visual_locked"] = True
    return doc


def drift() -> list[str] | None:
    """The look's files that moved since the lock, or None when there is no lock yet."""
    if not LOCK.exists():
        return None
    locked, now = json.loads(LOCK.read_text(encoding="utf-8"))["files"], fingerprints()
    return [k for k in now if locked.get(k) != now[k]]
