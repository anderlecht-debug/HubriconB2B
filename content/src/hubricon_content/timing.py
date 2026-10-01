"""The timeline: where every beat, chapter card, reveal and clip sits.

Built from the word alignment, so an on-screen number can land the instant it
is spoken (bible §6). Segments are what the scenes render: one per beat, plus
a chapter card before each beat whose name starts with CHAPTER.
"""

import json
import re
import subprocess
from pathlib import Path

from hubricon_engine.narrate import PLACEHOLDER

from . import script as scriptmod

BEAT_PAD = 0.55        # a breath between beats
CARD_SECONDS = 1.1     # chapter card held about a second (bible §6)
FADE_IN = 0.3


def duration(path: Path) -> float:
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True, timeout=30)
    return float(res.stdout.strip())


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def _find(words: list[dict], value: str, start_at: int = 0) -> tuple[int, float | None]:
    """First word index at or after start_at where the rendered value begins."""
    target = [_norm(t) for t in scriptmod.WORD_RE_TOKENS.findall(value)] if hasattr(scriptmod, "WORD_RE_TOKENS") else [_norm(t) for t in re.findall(r"[A-Za-z0-9$%'’.,-]+", value)]
    target = [t for t in target if t]
    if not target:
        return start_at, None
    norm = [_norm(w["word"]) for w in words]
    for i in range(start_at, len(words)):
        if norm[i] == target[0] or (len(target[0]) > 3 and norm[i].startswith(target[0][:4])):
            return i, words[i]["start"]
    # a number the aligner spelt differently: fall back to proportional position
    return start_at, None


def build(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    raw = scriptmod.parse((d / "script.md").read_text(encoding="utf-8"))
    rendered = scriptmod.render(raw, facts)
    segments, t = [], 0.0
    chapters, clips = [], []
    for i, (b, rb) in enumerate(zip(raw["beats"], rendered["beats"]), start=1):
        meta = d / "alignment" / f"vo-{i:02d}.json"
        audio = next(iter((d / "audio").glob(f"vo-{i:02d}.*")), None)
        if not meta.exists() or audio is None:
            continue
        al = json.loads(meta.read_text(encoding="utf-8"))
        words = al["words"]
        dur = duration(audio)
        if b["name"].upper().startswith("CHAPTER"):
            segments.append({"kind": "card", "name": b["name"], "start": round(t, 3), "end": round(t + CARD_SECONDS, 3),
                             "title": re.sub(r"^CHAPTER\s*\d*\s*[—-]?\s*", "", b["name"], flags=re.I).strip() or b["name"]})
            chapters.append({"at": round(t, 3), "title": segments[-1]["title"]})
            t += CARD_SECONDS
        start = t
        vo_start = start + FADE_IN
        reveals, cursor = {}, 0
        for m in PLACEHOLDER.finditer(b["VO"]):
            key = m.group(1)
            value = facts.get(key, {}).get("value", "")
            idx, at = _find(words, value, cursor)
            if at is None:
                # proportional fallback: position of the placeholder in the text
                frac = m.start() / max(1, len(b["VO"]))
                at = words[min(len(words) - 1, int(frac * len(words)))]["start"] if words else 0.0
            reveals[key] = {"t": round(vo_start + at, 3), "value": value, "word_index": idx}
            cursor = idx + 1
        end = vo_start + dur + BEAT_PAD
        seg = {"kind": "beat", "index": i, "name": b["name"], "script_at": b["at"], "start": round(start, 3),
               "vo_start": round(vo_start, 3), "end": round(end, 3), "audio": str(audio.relative_to(d)),
               "visual": b["VISUAL"], "data_source": b["DATA SOURCE"], "clip": b["CLIP"].lower().startswith("y"),
               "vo": rb["VO"], "reveals": reveals,
               "words": [{"word": w["word"], "start": round(vo_start + w["start"], 3), "end": round(vo_start + w["end"], 3)} for w in words]}
        segments.append(seg)
        if seg["clip"]:
            clips.append({"index": i, "start": seg["start"], "end": min(seg["end"], seg["start"] + 45.0), "name": b["name"]})
        t = end
    out = {"slug": slug, "duration": round(t, 3), "segments": segments, "chapters": chapters, "clips": clips,
           "voice": u.get("voice"), "fps": 30, "width": 1920, "height": 1080}
    (d / "timing.json").write_text(json.dumps(out, indent=None, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "duration": out["duration"], "segments": len(segments), "clips": len(clips), "chapters": len(chapters)}


run = build
