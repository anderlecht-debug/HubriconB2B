"""One clip per shot (VISUAL_SPEC.md §8.3): `hubricon-content render-shots <slug>`.

Each shot of a picked plan becomes content/videos/<slug>/shots/<id>.mp4, exactly
its frame count at 30 fps, by one of three renderers:

- the film stage (content/film/shots.mjs), for every paper kind, the house
  charts, and world stills and textures, where a still's move is drawn by
  Chrome frame by frame (no ffmpeg zoompan steps);
- ffmpeg (footage.py), for world footage, graded and grained;
- Manim (scenes/), for the engine's own charts, restyled on the site's tokens.

A clip is named by a cache key, the sha256 of the shot's resolved job, its
assets, tokens.json, grade.json, styles.json and this renderer's version, so a
one-line change re-renders one clip, not a film. Every figure on screen is
filled from facts.json here, never typed in a plan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import footage, grade, shots, tokens
from . import script as scriptmod
from .state import CONTENT_DIR

VERSION = "2026-10-05.1"
FPS = 30
REPO = CONTENT_DIR.parent
RENDER_MJS = CONTENT_DIR / "film" / "render.mjs"
GRADED = CONTENT_DIR / ".cache" / "graded"
MANIM_SCENES = {"waterfall": "Waterfall", "cash_cone": "CashCone", "paths": "Paths", "elasticity": "Elasticity",
                "newsvendor": "Newsvendor", "sample_size": "SampleSize"}
STAGE_CHARTS = {"staircase", "montecarlo", "aging"}
# The end card's words are the site's own (the style reel's end scene, content/film/scenes.mjs).
END = {"headline": "More profit than our bill every month, or you don't pay.", "primary": "Book your call",
       "secondary": "or learn the method, free, at hubricon.com/learn"}
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


def frames_of(shot: dict) -> int:
    return round(float(shot["end"]) * FPS) - round(float(shot["start"]) * FPS)


def fill(obj, values: dict):
    """Every {{key}} in the plan's text, from facts.json; an unknown key is an error, never a guess."""
    if isinstance(obj, str):
        def one(m):
            if m.group(1) not in values:
                raise KeyError(f"no figure {{{{{m.group(1)}}}}} in facts.json")
            return str(values[m.group(1)])
        return PLACEHOLDER.sub(one, obj)
    if isinstance(obj, list):
        return [fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: fill(v, values) for k, v in obj.items()}
    return obj


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_url(path: Path) -> str:
    """A file under the repo as the stage's local server serves it."""
    return "/" + str(Path(path).resolve().relative_to(REPO.resolve()))


def graded_still(file: str | Path, mono: bool | None = None, placeholder: bool = False) -> dict:
    """The still with the world grade, cached by its source's sha256. A labelled placeholder
    card (no picture exists yet) is shown as it is: it is not a picture to grade."""
    src = Path(file)
    if placeholder:
        w, h = _size(src)
        return {"url": stage_url(src), "w": w, "h": h, "sha256": sha(src)}
    look = hashlib.sha256(grade.GRADE_JSON.read_bytes()).hexdigest()[:8]   # a new grade re-grades the still
    key = sha(src)[:20] + f"-{look}" + ("-mono" if mono else "")
    out = GRADED / f"{key}.jpg"
    if not out.exists():
        grade.still(src, out, mono=mono)
    w, h = _size(out)
    return {"url": stage_url(out), "w": w, "h": h, "sha256": sha(src)}


def _size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def _balanced(text: str) -> list[str]:
    """A thesis line in at most two lines of near-equal length, broken between words."""
    words = text.split()
    if len(" ".join(words)) <= 26 or len(words) < 4:
        return [" ".join(words)]
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


class Job:
    """A shot, resolved: what the renderer draws and everything that names its clip."""

    def __init__(self, shot: dict, plan: dict, timing: dict, facts: dict, d: Path):
        reg = shots.registry()
        self.shot, self.d = shot, d
        by_id = {s["id"]: s for s in plan["shots"]}
        src = by_id[shot["params"]["callback"]] if shot.get("style") == "callback" else shot
        self.kind, self.style = src.get("kind"), src.get("style")
        if shot.get("style") == "breath" and shot.get("room") == "paper":
            prev = plan["shots"][max(0, plan["shots"].index(shot) - 1)]
            src, self.kind, self.style = prev, prev.get("kind"), prev.get("style")
        values = {k: v.get("value", "") for k, v in facts.items()}
        start, self.frames = float(shot["start"]), frames_of(shot)
        self.seconds = self.frames / FPS
        words = shots.spoken(timing)
        on_abs = shots.resolve_on(shot, words)
        reveals = [{"key": r["key"], "t": round(float(r["t"]) - start, 3), "value": values.get(r["key"], "")}
                   for r in shot.get("reveals", [])]
        brand = facts.get("demo_brand", {}).get("value")
        self.room = shot.get("room")
        self.job = {
            "id": shot["id"], "kind": self.kind, "style": self.style, "seconds": self.seconds, "frames": self.frames,
            "render": reg["styles"].get(self.style, {}).get("render", {}), "drift_to": reg["drift"]["to"],
            "on": None if on_abs is None else round(on_abs - start, 3), "reveals": reveals, "says": shot.get("says", ""),
            "label": shot.get("label"), "demo_label": f"{brand} demo data" if brand else "demo data",
            "params": fill(src.get("params") or {}, values), "focus": shot.get("focus") or src.get("focus"),
            "motion": shot.get("motion") or src.get("motion"), "overlay": fill(shot.get("overlay") or {}, values),
            "chart": src.get("chart"),
        }
        self.assets: list[str] = []
        self._defaults(shot, timing, facts, words, start)

    def _defaults(self, shot, timing, facts, words, start):
        j, p = self.job, self.job["params"]
        key = next((r["key"] for r in j["reveals"]), None)
        if self.kind == "number":
            k = re.fullmatch(r"\{\{\s*([a-z0-9_]+)\s*\}\}", shot.get("on") or "")
            k = k.group(1) if k else key
            fact = facts.get(k, {})
            p.setdefault("value", fact.get("value", ""))
            p.setdefault("sub", fact.get("label", ""))
            p.setdefault("estimate", "estimate" in str(fact.get("source", "")).lower())
        if self.kind == "pair":
            rv = j["reveals"]
            for side, r in zip(("left", "right"), rv[:2]):
                p.setdefault(side, {})
                p[side].setdefault("value", r["value"])
                p[side].setdefault("label", facts.get(r["key"], {}).get("label", ""))
                p[side].setdefault("at", r["t"])
        if self.kind == "kinetic":
            lines = _balanced(j["says"])
            p.setdefault("lines", lines)
            if len(lines) == 2:
                first = len(lines[0].split())
                inside = shots.words_in(words, float(shot["start"]), float(shot["end"]))
                p.setdefault("at", [0.0, round(inside[first]["start"] - start, 3) if len(inside) > first else 0.9])
        if self.kind == "chapter":
            card = next((c for c in timing["segments"] if c["kind"] == "card" and abs(float(c["start"]) - start) < 0.05), None)
            p.setdefault("title", (card or {}).get("title", ""))
        if self.kind == "end":
            for k, v in END.items():
                p.setdefault(k, v)

    @property
    def renderer(self) -> str:
        if self.kind == "footage":
            return "footage"
        if self.kind == "chart":
            scene = (self.job.get("chart") or {}).get("scene")
            if scene in MANIM_SCENES:
                return "manim"
            if scene in STAGE_CHARTS:
                return "stage"
            raise ValueError(f"{self.shot['id']}: no renderer draws the chart scene {scene!r}")
        return "stage"

    def resolve_assets(self):
        """Grade the stills and record every source file's sha256 for the cache key."""
        a = self.shot.get("asset")
        if self.kind in ("still", "texture", "archive", "split") and isinstance(a, dict):
            g = graded_still(a["file"], mono=True if self.kind in ("archive", "split") else None,
                             placeholder=str(a.get("id", "")).startswith("placeholder:"))
            self.job["asset"] = {**{k: a.get(k) for k in ("credit", "place", "date", "title")}, **g}
            self.assets.append(g["sha256"])
        if self.kind == "stack" and isinstance(a, list):
            self.job["assets"] = []
            for x in a:
                g = graded_still(x["file"], mono=True)
                self.job["assets"].append({**{k: x.get(k) for k in ("credit", "place", "date", "at")}, **g})
                self.assets.append(g["sha256"])
        if self.kind == "footage" and isinstance(a, dict):
            self.assets.append(sha(Path(a["file"])))
        if self.kind == "split":
            right = (self.shot.get("params") or {}).get("right") or {}
            if right.get("file"):
                self.assets.append(sha(Path(right["file"])))

    def key(self) -> str:
        look = "".join((CONTENT_DIR / p).read_text(encoding="utf-8") for p in
                       ("assets/tokens.json", "assets/grade.json", "film/styles.json", "film/shots.css", "film/shots.mjs"))
        blob = json.dumps({"job": self.job, "assets": self.assets, "renderer": self.renderer, "room": self.room,
                           "asset": self.shot.get("asset"), "version": VERSION}, sort_keys=True, default=str)
        return hashlib.sha256((blob + look).encode()).hexdigest()


def _grain(room: str) -> str:
    return grade.spec()["grain"]["paper" if room == "paper" else "world"]


def _clip_ok(path: Path, frames: int) -> bool:
    return path.exists() and footage.probe(path)["frames"] == frames


def _manim(job: Job, out: Path):
    """An engine chart as a shot: the Manim scene renders the shot's own time span."""
    from .render_scenes import ENTRY
    s = job.shot
    seg = {"start": float(s["start"]), "end": float(s["start"]) + job.seconds, "index": int(re.sub(r"\D", "", s["id"]) or 0),
           "reveals": {r["key"]: {"t": float(s["start"]) + r["t"], "value": r["value"]} for r in job.job["reveals"]},
           "vo": s.get("says", ""), "proof": s.get("label") == "proof", "kind": "beat",
           "title": (job.job["params"] or {}).get("heading", "")}
    with tempfile.TemporaryDirectory(prefix="hubricon-manim-") as tmp:
        env = {**os.environ, "HC_CONTEXT": json.dumps({"dir": str(job.d), "segment": seg}), "PYTHONWARNINGS": "ignore"}
        cmd = [str(CONTENT_DIR / ".venv" / "bin" / "manim"), "render", "-r", "1920,1080", "--fps", str(FPS), "--disable_caching",
               "--media_dir", tmp, "-o", "clip.mp4", "-v", "WARNING", "--progress_bar", "none", str(ENTRY),
               MANIM_SCENES[job.job["chart"]["scene"]]]
        res = subprocess.run(cmd, cwd=str(CONTENT_DIR), env=env, capture_output=True, text=True, timeout=3600)
        if res.returncode != 0:
            raise RuntimeError(f"manim failed on {s['id']}:\n{res.stderr[-1500:]}")
        raw = next(Path(tmp).rglob("clip.mp4"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", f"{_grain('paper')},format=yuv420p,tpad=stop_mode=clone:stop_duration=0.5",
                        "-frames:v", str(job.frames), "-r", str(FPS), "-an", *grade.encode_args(), str(out)], check=True, timeout=1800)


def _split_composite(job: Job, stage_clip: Path, rect: dict, out: Path):
    """Then and now (W11): the present-day footage plays inside the stage's right panel."""
    right = job.shot["params"]["right"]
    at = float(job.shot.get("params", {}).get("right_at", job.job["on"] if job.job["on"] is not None else job.job["render"]["right_at_s"]))
    n = max(1, job.frames - round(at * FPS))
    with tempfile.TemporaryDirectory(prefix="hubricon-split-") as tmp:
        clip = Path(tmp) / "right.mp4"
        footage.render(Path(right["file"]), clip, n, start=float(right.get("in", 0.0)), focus=right.get("focus", (0.5, 0.5)))
        w, h, x, y = (round(rect[k]) for k in ("w", "h", "x", "y"))
        fc = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setpts=PTS+{at:.3f}/TB[r];"
              f"[0:v][r]overlay={x}:{y}:eof_action=pass:repeatlast=0,format=yuv420p")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(stage_clip), "-i", str(clip), "-filter_complex", fc,
                        "-frames:v", str(job.frames), "-an", *grade.encode_args(), str(out)], check=True, timeout=1800)


def render(u: dict, q: dict | None = None, force: bool = False, only: set[str] | None = None,
           workers: int | None = None) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    tokens.refresh()
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, note = shots.load_timing(d)
    if timing is None:
        return {"status": "failed", "reason": "no timing"}
    if timing.get("estimated"):
        return {"status": "blocked", "reason": "the timing is the 150-wpm estimate; render-shots needs the narration's own timing"}
    facts = scriptmod.load_facts(slug)
    if slug != "visual-trial":   # a film renders on the look the founder approved, or not at all
        from . import visual_lock
        moved = visual_lock.drift()
        if moved is None:
            return {"status": "blocked", "reason": "the long films' look is not locked yet: the founder watches the visual trial, then `hubricon-content visual-lock`"}
        if moved:
            return {"status": "blocked", "reason": f"the look moved since the founder locked it: {', '.join(moved)}; re-run the trial and re-lock deliberately"}
    out_dir = d / "shots"
    out_dir.mkdir(exist_ok=True)
    workers = workers or max(1, min(4, (os.cpu_count() or 4) // 4))
    stage, others, done, skipped = [], [], [], []
    for s in plan["shots"]:
        if only and s["id"] not in only:
            continue
        job = Job(s, plan, timing, facts, d)
        job.resolve_assets()
        clip, side = out_dir / f"{s['id']}.mp4", out_dir / f"{s['id']}.json"
        k = job.key()
        if not force and side.exists() and json.loads(side.read_text()).get("key") == k and _clip_ok(clip, job.frames):
            skipped.append(s["id"])
            continue
        (stage if job.renderer == "stage" else others).append((job, clip, side, k))
    if stage:
        jobs = []
        for job, clip, side, k in stage:
            target = clip.with_suffix(".stage.mp4") if job.kind == "split" else clip
            jobs.append({**job.job, "out": str(target), "vf": _grain(job.room), "encode": grade.encode_args()})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(jobs, f)
            jobs_file = f.name
        try:
            res = subprocess.run(["node", str(RENDER_MJS), "--shots", jobs_file, "--workers", str(workers)], cwd=str(REPO),
                                 capture_output=True, text=True, timeout=6 * 3600)
        finally:
            os.unlink(jobs_file)
        if res.returncode != 0:
            raise RuntimeError(f"the stage failed:\n{res.stderr[-2000:]}")
        rects = json.loads(res.stdout.strip().splitlines()[-1])
        for job, clip, side, k in stage:
            if job.kind == "split":
                tmp = clip.with_suffix(".stage.mp4")
                _split_composite(job, tmp, rects[job.shot["id"]]["rect"], clip)
                tmp.unlink()
            others.append((job, clip, side, k))   # verified below with the rest
    for job, clip, side, k in others:
        if job.renderer == "footage":
            a = job.shot["asset"]
            footage.render(Path(a["file"]), clip, job.frames, start=float(a.get("in", 0.0)), focus=job.job["focus"] or (0.5, 0.5))
        elif job.renderer == "manim":
            _manim(job, clip)
        if not _clip_ok(clip, job.frames):
            raise RuntimeError(f"{clip.name}: not {job.frames} frames")
        side.write_text(json.dumps({"key": k, "frames": job.frames, "renderer": job.renderer, "version": VERSION}) + "\n")
        done.append(job.shot["id"])
    return {"status": "ok", "rendered": len(done), "cached": len(skipped), "workers": workers}


def run(u: dict, q: dict, force: bool = False) -> dict:
    return render(u, q, force=force)
