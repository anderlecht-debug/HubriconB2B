"""Sound assets: a fixed library, each file with its licence in a manifest.

The tick, the whoosh, the music bed and the world ambience on file were made with
ElevenLabs during the founder's paid subscription, which licenses them for
commercial use for good; they stay. Nothing new is generated (the founder's call,
2026-10-06: no ElevenLabs). A new sound comes from Freesound under its CC0 licence
or from Pixabay under the Pixabay Content License, added with `hubricon-content
ambience-add`, which records where it came from and refuses any other licence. A
missing tick or whoosh falls back to the procedural one (audio.py), and a subject
with no ambience on file plays room tone alone.
"""

import json
import re
import shutil
from datetime import date
from pathlib import Path

from .state import CONTENT_DIR

SFX = CONTENT_DIR / "assets" / "sfx"
MUSIC = CONTENT_DIR / "assets" / "music"
AMBIENCE = SFX / "ambience"
# The licences a sound may carry. ElevenLabs only for files made during the paid subscription,
# which ended new generation on 2026-10-06; ambience-add accepts the free ones alone.
PAID_ELEVENLABS = "ElevenLabs, generated during a paid subscription: licensed for commercial use"
FREE_LICENCES = {"cc0": "Creative Commons CC0 (Freesound)", "pixabay": "Pixabay Content License"}
_STRIP = re.compile(r"\b(daylight|wide|close|up|static|medium|detail|slow|aerial|shot|footage|4k|hd|overcast)\b", re.I)


def ensure(force: bool = False) -> dict:
    """The tick, the whoosh and the bed on file. Nothing is generated: a missing one is None
    and audio.py uses its procedural stand-in."""
    out = {name: (SFX / f"{name}.mp3") if (SFX / f"{name}.mp3").exists() else None for name in ("tick", "whoosh")}
    bed = MUSIC / "bed-elevenlabs.mp3"
    out["bed"] = bed if bed.exists() else None
    out["notes"] = [f"{k}: not on file; the procedural stand-in plays" for k, v in out.items() if v is None]
    return out


def subject_of(query: str) -> str:
    """The concrete nouns of a footage query, which is what the ambience should sound like."""
    words = _STRIP.sub(" ", query).split()
    return " ".join(words[:4]).lower() or "room"


def _name(subject: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60] or "room"


def _manifest() -> dict:
    p = AMBIENCE / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _licensed(entry: dict) -> bool:
    return entry.get("licence") in (PAID_ELEVENLABS, *FREE_LICENCES.values())


def ambience(subject: str) -> Path | None:
    """The library's bed of a place's own sound (a port, a warehouse) for this subject: the clip
    filed under its name, else the licensed clip whose subject shares the most words with it (at
    least two). None when nothing on file fits; the film then has room tone alone there."""
    entries = _manifest()
    name = _name(subject)
    if name in entries and _licensed(entries[name]) and (AMBIENCE / f"{name}.mp3").exists():
        return AMBIENCE / f"{name}.mp3"
    want = set(subject.lower().split())
    best, best_n = None, 1
    for k, e in entries.items():
        f = AMBIENCE / e.get("file", f"{k}.mp3")
        n = len(want & set(str(e.get("subject", k.replace("-", " "))).lower().split()))
        if n > best_n and _licensed(e) and f.exists():
            best, best_n = f, n
    return best


def ambience_add(file: str, subject: str, source: str, url: str, author: str = "") -> dict:
    """File a free clip in the ambience library: `source` is "freesound" (CC0 only) or
    "pixabay" (Pixabay Content License). The licence, the page it came from and its author
    go in the manifest beside it."""
    src = source.lower()
    licence = FREE_LICENCES["cc0"] if src == "freesound" else FREE_LICENCES["pixabay"] if src == "pixabay" else None
    if licence is None:
        raise SystemExit("a new sound comes from Freesound (CC0 only) or Pixabay; nothing else is accepted")
    if not url.startswith(("https://freesound.org/", "https://pixabay.com/")):
        raise SystemExit("give the clip's page on freesound.org or pixabay.com, so its licence can be checked")
    f = Path(file)
    if not f.exists():
        raise SystemExit(f"{f} does not exist")
    AMBIENCE.mkdir(parents=True, exist_ok=True)
    name = _name(subject)
    dest = AMBIENCE / f"{name}{f.suffix.lower()}"
    shutil.copyfile(f, dest)
    entries = _manifest()
    entries[name] = {"subject": subject, "file": dest.name, "source": src, "url": url, "author": author,
                     "licence": licence, "added": date.today().isoformat()}
    (AMBIENCE / "manifest.json").write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "name": name, "file": str(dest), "licence": licence}
