"""Render one Manim clip per timeline segment, each exactly its segment's length."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

ENTRY = Path(__file__).resolve().parent / "scenes" / "entry.py"
SCENE_BY_KEYWORD = [("cash_cone", "CashCone"), ("waterfall", "Waterfall"), ("elasticity", "Elasticity"),
                    ("newsvendor", "Newsvendor"), ("paths", "Paths"), ("sample_size", "SampleSize"),
                    ("screenshot", "Screenshot"), ("chapter_card", "ChapterCard"), ("kinetic", "Kinetic")]


def scene_for(seg: dict) -> str:
    if seg["kind"] == "card":
        return "ChapterCard"
    from .script import scene_of
    name = scene_of(seg.get("visual") or "")
    return dict(SCENE_BY_KEYWORD).get(name, "Kinetic")


def render_segment(d: Path, seg: dict, index: int, vertical: bool = False, force: bool = False) -> Path:
    out_dir = d / "scenes"
    out_dir.mkdir(exist_ok=True)
    name = f"{'vert' if vertical else 'seg'}-{index:02d}"
    target = out_dir / f"{name}.mp4"
    if target.exists() and not force:
        return target
    ctx = {"dir": str(d), "segment": {**seg, "index": seg.get("index", index)}, "vertical": vertical}
    env = {**os.environ, "HC_CONTEXT": json.dumps(ctx), "PYTHONWARNINGS": "ignore"}
    media = d / ".manim"
    size = "1080,1920" if vertical else "1920,1080"
    cmd = [str(CONTENT_DIR / ".venv" / "bin" / "manim"), "render", "-r", size, "--fps", "30", "--disable_caching",
           "--media_dir", str(media), "-o", f"{name}.mp4", "-v", "WARNING", "--progress_bar", "none",
           str(ENTRY), scene_for(seg)]
    res = subprocess.run(cmd, cwd=str(CONTENT_DIR), env=env, capture_output=True, text=True, timeout=1800)
    if res.returncode != 0:
        raise RuntimeError(f"manim failed on segment {index} ({scene_for(seg)}):\n{res.stderr[-2000:]}")
    produced = next(iter(media.rglob(f"{name}.mp4")), None)
    if produced is None:
        raise RuntimeError(f"manim produced no file for segment {index}")
    shutil.move(str(produced), str(target))
    return target


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    if not q.get("style_locked") and not (u["id"].startswith("V01") or u["id"].startswith("SMOKE")):
        return {"status": "blocked", "reason": "style not locked yet; V01 must pass QA and `hubricon-content style-lock` first"}
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    if force and (d / "events.json").exists():
        (d / "events.json").unlink()
    done = []
    for k, seg in enumerate(timing["segments"]):
        done.append(render_segment(d, seg, k, force=force).name)
    return {"status": "ok", "segments": len(done), "scenes": sorted(set(scene_for(s) for s in timing["segments"]))}
