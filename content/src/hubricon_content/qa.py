"""Production bible §11, the half a program can judge. The other half (faces,
texture-as-subject, chart annotation, legibility) is the critique skill reading
the frames this step extracts."""

import json
import re
import subprocess
from pathlib import Path

from . import subtitles
from . import script as scriptmod

DISCLOSURE = "Narration is an AI clone of Hagen Simmons's voice, used with his permission; the analysis is his."
TIER_RANGE = {"A": (270, 460), "B": (450, 900)}


def _ffprobe_duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True, timeout=60)
    return float(r.stdout.strip())


def _filter_log(p: Path, af: str | None = None, vf: str | None = None) -> str:
    cmd = ["ffmpeg", "-nostats", "-i", str(p)]
    if af:
        cmd += ["-af", af]
    if vf:
        cmd += ["-vf", vf, "-an"]
    else:
        cmd += ["-vn"]
    cmd += ["-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    return r.stderr


def lufs(p: Path) -> float | None:
    log = _filter_log(p, af="ebur128=framelog=verbose")
    m = re.findall(r"I:\s*(-?[\d.]+) LUFS", log)
    return float(m[-1]) if m else None


def max_hold(p: Path, threshold_s: float = 6.0) -> tuple[float, int]:
    log = _filter_log(p, vf=f"freezedetect=n=0.002:d={threshold_s}")
    durs = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", log)]
    return (max(durs) if durs else 0.0), len(durs)


def cut_stats(p: Path) -> dict:
    log = _filter_log(p, vf="select='gt(scene,0.28)',showinfo")
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", log)]
    if len(times) < 2:
        return {"cuts": len(times), "mean_interval": None, "max_interval": None}
    gaps = [b - a for a, b in zip(times, times[1:])]
    return {"cuts": len(times), "mean_interval": round(sum(gaps) / len(gaps), 2), "max_interval": round(max(gaps), 2)}


def silences(p: Path) -> int:
    log = _filter_log(p, af="silencedetect=n=-55dB:d=1.0")
    return len(re.findall(r"silence_start", log))


def frames(p: Path, out: Path, every_s: int = 10) -> int:
    out.mkdir(exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf", f"fps=1/{every_s},scale=960:-1",
                    str(out / "f-%03d.png")], check=True, timeout=1800)
    return len(list(out.glob("*.png")))


def transcript_match(slug: str, master: Path) -> float | None:
    """Share of scripted words the transcriber heard, a mispronunciation net."""
    try:
        from .tts import align
    except Exception:
        return None
    d = scriptmod.video_dir(slug)
    wav = d / "media" / "master-audio.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(master), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True, timeout=600)
    try:
        heard = [re.sub(r"[^a-z0-9]", "", w["word"].lower()) for w in align(wav)]
    except Exception:
        return None
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    said = [re.sub(r"[^a-z0-9]", "", w["word"].lower()) for s in timing["segments"] if s["kind"] == "beat" for w in s["words"]]
    said = [w for w in said if w]
    if not said:
        return None
    heard_set = set(heard)
    return round(sum(1 for w in said if w in heard_set) / len(said), 3)


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    master = d / "media" / "master.mp4"
    if not master.exists():
        return {"status": "failed", "reason": "no master.mp4; run assemble first"}
    dur = _ffprobe_duration(master)
    lo, hi = TIER_RANGE.get(u.get("tier", "A"), (200, 900))
    loud = lufs(master)
    hold, holds = max_hold(master)
    cuts = cut_stats(master)
    sil = silences(master)
    cov = round(subtitles.coverage(slug), 3)
    nframes = frames(master, d / "frames")
    desc = (d / "description.md").read_text(encoding="utf-8") if (d / "description.md").exists() else ""
    tm = transcript_match(slug, master)
    checks = {
        "duration_in_range": lo <= dur <= hi,
        "loudness_within_1_lu": loud is not None and abs(loud + 16) <= 1.0,
        "no_hold_over_6s": holds == 0,
        "room_tone_present": sil == 0,
        "subtitle_coverage_ge_90": cov >= 0.9,
        "disclosure_in_description": DISCLOSURE in desc if desc else None,
        "transcript_match_ge_85": (tm is None) or tm >= 0.85,
        "cut_cadence_2_to_6s": cuts["mean_interval"] is None or 1.0 <= cuts["mean_interval"] <= 6.5,
    }
    hard = [k for k, v in checks.items() if v is False and k != "disclosure_in_description"]
    out = {"slug": slug, "pass": not hard, "failed": hard, "duration_s": round(dur, 1), "tier_range": [lo, hi], "lufs": loud,
           "max_hold_s": hold, "holds_over_6s": holds, "cuts": cuts, "silences": sil, "subtitle_coverage": cov,
           "transcript_match": tm, "frames": nframes, "checks": checks, "voice": u.get("voice")}
    (d / "qa.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return {"status": "ok" if out["pass"] else "failed", **{k: out[k] for k in ("pass", "failed", "duration_s", "lufs", "max_hold_s", "subtitle_coverage", "transcript_match")}}
