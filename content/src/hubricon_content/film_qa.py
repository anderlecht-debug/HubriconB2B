"""Film QA with no AI in the loop (docs/content/FILM_LINE.md): every check five critic agents ran
by eye on G01, as code, so a film a day is checked for nothing.

    hubricon-content film-qa <slug> [--no-media]

1. The plan: shots.validate (screen-mix shares are advisory, not problems).
2. The clips: one per shot, of the shot's length.
3. The stage: content/film/v3/qa.mjs over every paper shot (figures before their words, bare
   openings, labels over lit pictures, text under prints, title-safe, overlaps).
4. The draft (media/draft.mp4), when there is one: its length against the narration plus the end
   card's hold, loudness and true peak, black and frozen stretches.

Writes videos/<slug>/qa/film-qa.json and prints a punch list; the status is "clean" or "problems".
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

ADVISORY = re.compile(r"of the runtime|at most$")
LUFS, TRUE_PEAK = (-17.0, -15.0), -1.5
# the mix's own numbers (sound.metrics, docs/content/SOUND_DESIGN.md)
SOUND = {"voice_over_music_db": 15.0, "effects_per_minute": (2.0, 14.0), "longest_undesigned_s": 60.0, "lra": (2.0, 12.0)}


def _ffprobe_seconds(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def export_jobs(slug: str) -> Path:
    """Every shot as the stage draws it (render_shots.Job), into qa/jobs.json."""
    os.environ.setdefault("FILM_LOOK", "v3")
    from . import render_shots, shots, tokens
    d = scriptmod.video_dir(slug)
    tokens.refresh()
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shots.load_timing(d)
    facts = scriptmod.load_facts(slug)
    jobs = []
    for s in plan["shots"]:
        job = render_shots.Job(s, plan, timing, facts, d)
        job.resolve_assets()
        jobs.append(job.job)
    out = d / "qa" / "jobs.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    return out


def media(d: Path, plan: dict, timing: dict) -> list[dict]:
    from . import shots
    m = d / "media" / "draft.mp4"
    if not m.exists():
        return []
    out = []
    want = float(timing["duration"]) + shots.end_tail(plan)
    got = _ffprobe_seconds(m)
    if abs(got - want) > 1.0:
        out.append({"check": "draft-length", "msg": f"the draft runs {got:.1f} s; the narration and the end card's hold run {want:.1f} s"})
    log = subprocess.run(["ffmpeg", "-nostats", "-i", str(m), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summary = log[log.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    if i and not (LUFS[0] <= float(i.group(1)) <= LUFS[1]):
        out.append({"check": "loudness", "msg": f"{i.group(1)} LUFS integrated; the spec is {LUFS[0]} to {LUFS[1]}"})
    if tp and float(tp.group(1)) > TRUE_PEAK:
        out.append({"check": "true-peak", "msg": f"true peak {tp.group(1)} dBTP; the spec is at most {TRUE_PEAK}"})
    lra = re.search(r"LRA:\s+([\d.]+) LU", summary)
    if lra and not (SOUND["lra"][0] <= float(lra.group(1)) <= SOUND["lra"][1]):
        out.append({"check": "sound", "msg": f"loudness range {lra.group(1)} LU; a documentary breathes within {SOUND['lra'][0]}–{SOUND['lra'][1]}"})
    mj = d / "media" / "mix.json"
    meas = (json.loads(mj.read_text(encoding="utf-8")).get("measured") or {}) if mj.exists() else {}
    if meas.get("voice_over_music_db") is not None and meas["voice_over_music_db"] < SOUND["voice_over_music_db"]:
        out.append({"check": "sound", "msg": f"the voice sits {meas['voice_over_music_db']} dB over the music under speech; at least {SOUND['voice_over_music_db']}"})
    epm = meas.get("effects_per_minute")
    if epm is not None and not (SOUND["effects_per_minute"][0] <= epm <= SOUND["effects_per_minute"][1]):
        out.append({"check": "sound", "msg": f"{epm} designed effects a minute; {SOUND['effects_per_minute'][0]}–{SOUND['effects_per_minute'][1]} keeps attention without fatigue"})
    if meas.get("longest_undesigned_s", 0) > SOUND["longest_undesigned_s"]:
        out.append({"check": "sound", "msg": f"{meas['longest_undesigned_s']} s with nothing designed under the voice; at most {SOUND['longest_undesigned_s']}"})
    log = subprocess.run(["ffmpeg", "-nostats", "-i", str(m), "-an", "-vf",
                          "fps=10,scale=320:-2,blackdetect=d=0.5:pix_th=0.06,freezedetect=n=0.003:d=4", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log):
        out.append({"check": "black", "t": float(a), "msg": f"black from {float(a):.1f} to {float(b):.1f} s"})
    for a in re.findall(r"freeze_start: ([\d.]+)", log):
        if float(a) < want - 6:                      # the end card's hold is a still frame by design
            out.append({"check": "freeze", "t": float(a), "msg": f"a frozen picture from {float(a):.1f} s (4 s or more)"})
    return out


def run(slug: str, check_media: bool = True) -> dict:
    from . import shots
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shots.load_timing(d)
    facts = scriptmod.load_facts(slug)
    problems, advisory = [], []
    for p in shots.validate(plan, timing, facts):
        (advisory if ADVISORY.search(p) else problems).append({"check": "plan", "msg": p})
    for s in plan["shots"]:
        c = d / "shots" / f"{s['id']}.mp4"
        if not c.exists():
            problems.append({"shot": s["id"], "check": "clip", "msg": "no clip: run render-shots"})
            continue
        want = float(s["end"]) - float(s["start"]) + (shots.end_tail(plan) if s is plan["shots"][-1] else 0.0)
        got = _ffprobe_seconds(c)
        if abs(got - want) > 0.1:
            problems.append({"shot": s["id"], "check": "clip", "msg": f"clip runs {got:.2f} s; the shot is {want:.2f} s"})
    jobs = export_jobs(slug)
    env = {**os.environ, "FILM_LOOK": "v3"}
    proc = subprocess.run(["node", str(CONTENT_DIR / "film" / "v3" / "qa.mjs"), str(jobs)], capture_output=True, text=True,
                          env=env, cwd=str(CONTENT_DIR.parent), timeout=3 * 3600)
    for line in proc.stdout.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not row.get("summary"):
            problems.append(row)
    if proc.returncode != 0:
        problems.append({"check": "stage", "msg": f"qa.mjs failed: {proc.stderr.strip()[-300:]}"})
    if check_media:
        problems += media(d, plan, timing)
    by = {}
    for p in problems:
        by[p["check"]] = by.get(p["check"], 0) + 1
    res = {"slug": slug, "status": "clean" if not problems else "problems", "problems": len(problems), "by_check": by,
           "advisory": [a["msg"] for a in advisory]}
    (d / "qa").mkdir(exist_ok=True)
    (d / "qa" / "film-qa.json").write_text(json.dumps({**res, "list": problems}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**res, "list": problems}
