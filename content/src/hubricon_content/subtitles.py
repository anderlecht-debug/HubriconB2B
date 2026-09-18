"""Burned-in subtitles from the word timeline (bible §6: always, most of the
audience watches muted on a phone). ASS so ffmpeg's libass renders them with
the brand's mono face and a safe bottom margin."""

import json
from pathlib import Path

from . import script as scriptmod

MAX_CHARS = 42
MAX_LINES = 2
FONT = "JetBrains Mono"


def _ts(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _cues(words: list[dict]) -> list[dict]:
    cues, cur, cur_start = [], [], None
    for w in words:
        text = " ".join(x["word"] for x in cur + [w])
        if cur and (len(text) > MAX_CHARS * MAX_LINES or w["start"] - cur[-1]["end"] > 0.9):
            cues.append({"start": cur_start, "end": cur[-1]["end"] + 0.15, "text": " ".join(x["word"] for x in cur)})
            cur, cur_start = [], None
        if cur_start is None:
            cur_start = w["start"]
        cur.append(w)
    if cur:
        cues.append({"start": cur_start, "end": cur[-1]["end"] + 0.15, "text": " ".join(x["word"] for x in cur)})
    for c in cues:
        if len(c["text"]) > MAX_CHARS:
            words_ = c["text"].split()
            line, lines = "", []
            for x in words_:
                if len(line) + len(x) + 1 > MAX_CHARS and line:
                    lines.append(line); line = x
                else:
                    line = (line + " " + x).strip()
            lines.append(line)
            c["text"] = "\\N".join(lines[:MAX_LINES])
    return cues


def write(slug: str, vertical: bool = False) -> Path:
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    words = [w for s in timing["segments"] if s["kind"] == "beat" for w in s["words"]]
    w, h = (1080, 1920) if vertical else (1920, 1080)
    size = 64 if vertical else 40
    margin_v = 420 if vertical else 96
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},{size},&H00F4F6FC,&H0000C0FF,&H00050A1F,&H80050A1F,0,0,0,0,100,100,0,0,1,2,0,2,120,120,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{_ts(c['start'])},{_ts(c['end'])},Sub,,0,0,0,,{c['text']}" for c in _cues(words)]
    out = d / ("subs-vertical.ass" if vertical else "subs.ass")
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def coverage(slug: str) -> float:
    """Share of narrated time under a cue."""
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    words = [w for s in timing["segments"] if s["kind"] == "beat" for w in s["words"]]
    if not words:
        return 0.0
    cues = _cues(words)
    spoken = sum(max(0.0, w["end"] - w["start"]) for w in words)
    covered = sum(sum(max(0.0, min(w["end"], c["end"]) - max(w["start"], c["start"])) for c in cues) for w in words)
    return min(1.0, covered / spoken) if spoken else 0.0
