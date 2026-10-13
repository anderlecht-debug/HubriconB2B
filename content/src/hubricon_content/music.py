"""The music library: licensed cues, each tagged by mood, tempo and key, chosen per chapter by mood.

    hubricon-content music-tag <file> --mood calm --licence "…" --source "…"   → <file>.json beside it
    hubricon-content music-list

A cue is any audio file in content/assets/music/ with a sidecar (<name>.json):

- mood: one of MOODS;
- tempo (BPM) and key (for example "D minor"): read by code (librosa);
- licence, source, title, made_on.

The mood is a person's call; code can't hear it. The decision reply gives each chapter a mood, one line per
chapter. pick() takes a cue of that mood:

- never one already used in the film;
- never one another film used in the past 7 days (the usage ledger);
- else nothing, and that chapter keeps the bed's family variation, as before.

No tokens.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .state import CONTENT_DIR

MUSIC = CONTENT_DIR / "assets" / "music"
LEDGER = CONTENT_DIR / ".cache" / "music-usage.json"
MOODS = ("calm", "tension", "lift", "resolve", "montage")
AUDIO = (".mp3", ".wav", ".flac", ".m4a", ".ogg")
WEEK = 7
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl-Kessler key profiles
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def cues(folder: Path | None = None) -> list[dict]:
    """Every tagged cue on file (an audio file with a sidecar), with its path."""
    folder = folder or MUSIC
    out = []
    for f in sorted(folder.glob("*")):
        side = f.with_suffix(".json")
        if f.suffix.lower() in AUDIO and side.exists():
            out.append({**json.loads(side.read_text(encoding="utf-8")), "file": str(f), "name": f.stem})
    return out


def detect(path: Path) -> dict:
    """Tempo (BPM) and key, by code: librosa's beat tracker, and the chroma matched to the key profiles."""
    import librosa
    import numpy as np
    y, sr = librosa.load(str(path), sr=22050, mono=True, duration=180)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    best = max(((float(np.corrcoef(np.roll(prof, k), chroma)[0, 1]), f"{_NOTES[k]} {mode}")
                for prof, mode in ((_MAJOR, "major"), (_MINOR, "minor")) for k in range(12)))
    return {"tempo": round(float(np.atleast_1d(tempo)[0]), 1), "key": best[1], "key_confidence": round(best[0], 3)}


def tag(path: str | Path, mood: str, licence: str, source: str, title: str | None = None) -> dict:
    """Write a cue's sidecar: the mood a person gave it, its tempo and key read by code, its licence."""
    p = Path(path)
    if mood not in MOODS:
        raise SystemExit(f"mood must be one of {', '.join(MOODS)}")
    if not licence.strip():
        raise SystemExit("a cue needs its licence: nothing unlicensed goes in a film")
    side = {"mood": mood, **detect(p), "licence": licence, "source": source, "title": title or p.stem,
            "made_on": date.today().isoformat()}
    p.with_suffix(".json").write_text(json.dumps(side, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return side


def _ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}


def pick(slug: str, moods: list[str | None], today: date | None = None, library: list[dict] | None = None,
         record: bool = True) -> list[dict | None]:
    """A cue per chapter, by mood: none twice in a film, none another film used in the past week. A chapter
    with no mood or no free cue of its mood gets None (it keeps the bed's family variation)."""
    today = today or date.today()
    library = cues() if library is None else library
    led = _ledger()
    taken_elsewhere = {name for name, uses in led.items()
                       for u in uses if u["film"] != slug and date.fromisoformat(u["on"]) > today - timedelta(days=WEEK)}
    used, out = set(), []
    for mood in moods:
        free = [c for c in library if c["mood"] == mood and c["name"] not in used and c["name"] not in taken_elsewhere]
        c = free[0] if free else None
        if c:
            used.add(c["name"])
        out.append(c)
    if record and any(out):
        for c in filter(None, out):
            uses = [u for u in led.get(c["name"], []) if u["film"] != slug]
            led[c["name"]] = uses + [{"film": slug, "on": today.isoformat()}]
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(led, indent=1) + "\n", encoding="utf-8")
    return out
