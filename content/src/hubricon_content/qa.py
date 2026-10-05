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
# The founder records the films himself first (HUBRICON_SPEC.md: "record in my own voice now"; the
# clone comes later). A unit's "voice" says which: "own" is his recorded takes (content/film/
# record.mjs), "founder" is the ElevenLabs clone of his voice (tts.py), anything else a placeholder
# that never publishes. The description says which it is, and never claims a clone that isn't one.
OWN_VOICE = "Narrated by Hagen Simmons, in his own voice."
# "library": an ElevenLabs library voice the founder chose (content/assets/voice.json, 2026-10-04).
# It is never presented as his voice; the description says what it is.
LIBRARY_VOICE = "Narrated by an AI voice from ElevenLabs' voice library; written and analysed by Hagen Simmons."
PUBLISHABLE_VOICES = ("own", "founder", "library")


def disclosure_for(voice: str | None) -> str:
    if voice == "own":
        return OWN_VOICE
    if voice == "founder":
        return DISCLOSURE
    if voice == "library":
        return LIBRARY_VOICE
    return "Narration is a placeholder voice. This cut is not for publishing."
TIER_RANGE = {"A": (270, 460), "B": (450, 900), "D": (1200, 3000)}   # D: VISUAL_SPEC.md §7.1
# The cadence, from VISUAL_SPEC.md §4 (its §0 retires the bible's two-to-four seconds
# and its §1.4 names the three thresholds that used to contradict each other): a shot
# runs three to fourteen seconds, a chart build may run to thirty, and nothing on
# screen is ever frozen longer than four.
SHOT_MIN_S, SHOT_MAX_S, BUILD_MAX_S, FROZEN_MAX_S = 3.0, 14.0, 30.0, 4.0
# How hard a picture has to change to count as a cut. Measured on V01's master
# 2026-10-05: a chart cutting to a chapter card scores 0.083 and 0.073, the segment
# joins 0.028 to 0.053, and the busiest moment inside a shot (a path landing, the slow
# push) 0.023. Ink on paper never approaches the 0.28 that suits footage, which is why
# the old check read zero cuts in a film that has nine. Tier D carries the world room,
# where motion scores high and the shot plan is validated against §4 in its own right.
CUT_SCORE = {"D": 0.28}
CUT_SCORE_PAPER = 0.025


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
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=3600)
    return r.stderr


def lufs(p: Path) -> float | None:
    log = _filter_log(p, af="ebur128=framelog=verbose")
    m = re.findall(r"I:\s*(-?[\d.]+) LUFS", log)
    return float(m[-1]) if m else None


def max_hold(p: Path, threshold_s: float = FROZEN_MAX_S) -> tuple[float, int]:
    log = _filter_log(p, vf=f"freezedetect=n=0.002:d={threshold_s}")
    durs = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", log)]
    return (max(durs) if durs else 0.0), len(durs)


def frozen(d: Path, master: Path, threshold_s: float = FROZEN_MAX_S) -> tuple[float, int]:
    """The longest stretch of unchanging picture, read off the clips the master is
    cut from rather than the master itself: the burned-in subtitles change underneath
    a still picture and blind freezedetect on the master, which is how a card held
    for most of a minute passed this check (V01's QA, 2026-10-05)."""
    worst, runs = 0.0, 0
    clips = sorted((d / "scenes").glob("seg-*.mp4")) + sorted((d / "shots").glob("*.mp4"))
    if not clips:
        hold, n = max_hold(master, threshold_s)   # no clips kept: the master is all there is to read
        return round(hold, 2), n
    for clip in clips:
        hold, n = max_hold(clip, threshold_s)
        worst, runs = max(worst, hold), runs + n
    return round(worst, 2), runs


def cut_stats(p: Path, score: float = CUT_SCORE_PAPER) -> dict:
    log = _filter_log(p, vf=f"select='gt(scene,{score})',showinfo")
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", log)]
    if len(times) < 2:
        return {"cuts": len(times), "mean_interval": None, "max_interval": None, "score": score}
    gaps = [b - a for a, b in zip(times, times[1:])]
    return {"cuts": len(times), "mean_interval": round(sum(gaps) / len(gaps), 2),
            "max_interval": round(max(gaps), 2), "score": score}


def cadence_holds(cuts: dict) -> bool:
    """§4: a film this long is cut, its shots average inside the shot range, and no
    stretch between cuts runs past a chart build's thirty seconds. A film the
    detector finds no cuts in fails: it is one long shot, not a film without cuts."""
    if cuts["cuts"] < 2 or cuts["mean_interval"] is None:
        return False
    return SHOT_MIN_S <= cuts["mean_interval"] <= SHOT_MAX_S and cuts["max_interval"] <= BUILD_MAX_S


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
    if str(u.get("tier", "")).upper() == "D":
        from . import qa_d   # VISUAL_SPEC.md §10
        return qa_d.run(u)
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    master = d / "media" / "master.mp4"
    if not master.exists():
        return {"status": "failed", "reason": "no master.mp4; run assemble first"}
    dur = _ffprobe_duration(master)
    lo, hi = TIER_RANGE.get(u.get("tier", "A"), (200, 900))
    loud = lufs(master)
    hold, holds = max_hold(master)
    froze, freezes = frozen(d, master)
    cuts = cut_stats(master, CUT_SCORE.get(str(u.get("tier") or "").upper(), CUT_SCORE_PAPER))
    sil = silences(master)
    cov = round(subtitles.coverage(slug), 3)
    nframes = frames(master, d / "frames")
    desc = (d / "description.md").read_text(encoding="utf-8") if (d / "description.md").exists() else ""
    tm = transcript_match(slug, master)
    checks = {
        "duration_in_range": lo <= dur <= hi,
        "loudness_within_1_lu": loud is not None and abs(loud + 16) <= 1.0,
        "no_frozen_picture_over_4s": freezes == 0,
        "room_tone_present": sil == 0,
        "subtitle_coverage_ge_90": cov >= 0.9,
        "disclosure_in_description": disclosure_for(u.get("voice")) in desc if desc else None,
        "transcript_match_ge_85": (tm is None) or tm >= 0.85,
        "cut_cadence_spec_4": cadence_holds(cuts),
    }
    hard = [k for k, v in checks.items() if v is False and k != "disclosure_in_description"]
    out = {"slug": slug, "pass": not hard, "failed": hard, "duration_s": round(dur, 1), "tier_range": [lo, hi], "lufs": loud,
           "max_hold_s": hold, "holds_over_4s": holds, "frozen_s": froze, "frozen_runs": freezes,
           "cuts": cuts, "silences": sil, "subtitle_coverage": cov,
           "transcript_match": tm, "frames": nframes, "checks": checks, "voice": u.get("voice")}
    (d / "qa.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return {"status": "ok" if out["pass"] else "failed", **{k: out[k] for k in ("pass", "failed", "duration_s", "lufs", "max_hold_s", "subtitle_coverage", "transcript_match")}}
