"""Subtitles from the word timeline. Shorts and tier A/B burn them in (most of
that audience watches muted on a phone), as ASS so ffmpeg's libass draws them
in Inter Display from content/assets/fonts: ink with a thin paper outline,
never boxed (PREMIUM-STANDARD.md), readable over paper and the high-key world grade. Long-form (tier D) burns nothing and uploads an exact
caption track instead, `captions.srt` (VISUAL_SPEC.md §8.6)."""

import json
from pathlib import Path

from . import script as scriptmod
from . import tokens

MAX_CHARS = 38
MAX_LINES = 2
SRT_CHARS = 42          # §8.6: at most 42 characters a line, two lines
FONTS_DIR = tokens.FONTS


def ass_filter(path: Path) -> str:
    """The ffmpeg filter that burns `path`, with the repo's fonts and no system fallback."""
    return f"ass={path.as_posix()}:fontsdir={FONTS_DIR.as_posix()}"


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
    size = 56 if vertical else 44
    margin_v = 420 if vertical else 104
    font = f"{tokens.family(display=True)} SemiBold"   # libass needs the face's own name; "bold" finds Inter Regular
    ink, paper, clear = tokens.ass("ink"), tokens.ass("paper"), tokens.ass("paper", 0.0)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{size},{ink},{ink},{paper},{clear},0,0,0,0,100,100,-0.6,0,1,2.5,0,2,140,140,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{_ts(c['start'])},{_ts(c['end'])},Sub,,0,0,0,,{c['text']}" for c in _cues(words)]
    out = d / ("subs-vertical.ass" if vertical else "subs.ass")
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def _srt_ts(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _srt_cues(words: list[dict]) -> list[dict]:
    """Sentence-aware cues: a cue ends at a sentence's end, a pause, or two full lines."""
    cues, cur = [], []
    for w in words:
        text = " ".join(x["word"] for x in cur + [w])
        if cur and (len(text) > SRT_CHARS * MAX_LINES or w["start"] - cur[-1]["end"] > 0.9):
            cues.append(cur)
            cur = []
        cur.append(w)
        if w["word"].rstrip("”’\"'").endswith((".", "?", "!")) and len(" ".join(x["word"] for x in cur)) > 12:
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    out = []
    for c in cues:
        lines, line = [], ""
        for x in (w["word"] for w in c):
            if line and len(line) + 1 + len(x) > SRT_CHARS:
                lines.append(line)
                line = x
            else:
                line = (line + " " + x).strip()
        lines.append(line)
        out.append({"start": c[0]["start"], "end": c[-1]["end"] + 0.15, "lines": lines[:MAX_LINES]})
    for a, b in zip(out, out[1:]):   # never overlap the next cue
        a["end"] = min(a["end"], b["start"])
    return out


def write_srt(slug: str) -> Path:
    """media/captions.srt: the narration's own words at their spoken times, for
    the YouTube caption track (tier D)."""
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    words = [w for s in timing["segments"] if s["kind"] == "beat" for w in s["words"]]
    cues = _srt_cues(words)
    out = d / "media" / "captions.srt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(f"{i}\n{_srt_ts(c['start'])} --> {_srt_ts(c['end'])}\n" + "\n".join(c["lines"]) + "\n\n"
                           for i, c in enumerate(cues, 1)), encoding="utf-8")
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
