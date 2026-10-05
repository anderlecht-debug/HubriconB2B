"""World footage, one clip per shot (VISUAL_SPEC.md §8.2): cut `in`→`out` from
the cached source, conform, normalize, grade and grain it (grade.py), slow it
to 0.8× only when the source runs at 60 fps, strip its sound, and write exactly
the shot's frame count, so the clips concatenate frame-exact into the master.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import grade

SLOW = 0.8   # §3.4: footage plays in real time, or at 0.8× from a 60 fps source; never faster


def probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True, timeout=60)
    d = json.loads(r.stdout)
    st, fmt = (d.get("streams") or [{}])[0], d.get("format", {})
    num, _, den = str(st.get("r_frame_rate", "30/1")).partition("/")
    return {"width": int(st.get("width", 0)), "height": int(st.get("height", 0)),
            "fps": float(num) / float(den or 1), "duration": float(fmt.get("duration", 0) or 0),
            "frames": int(st["nb_frames"]) if str(st.get("nb_frames", "")).isdigit() else None}


def render(src: Path, out: Path, frames: int, start: float = 0.0, focus=(0.5, 0.5), slow: bool | None = None,
           fps: int = 30) -> dict:
    """One graded clip of exactly `frames` frames at 30 fps from `src`, starting at `start`."""
    info = probe(src)
    slow = info["fps"] >= 50 if slow is None else slow
    need = frames / fps * (SLOW if slow else 1.0)
    if info["duration"] and start + need > info["duration"] + 0.05:
        raise grade.Rejected(f"the take is {info['duration'] - start:.1f} s from its in point; the shot needs {need:.1f} s")
    g = grade.plan(src, focus=focus, start=start, duration=need)
    speed = f"setpts=PTS/{SLOW}," if slow else ""
    # a clone of the last frame covers a rounding shortfall of a frame or two, never more
    vf = f"{speed}{g['filter']},tpad=stop_mode=clone:stop_duration=0.2"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{need + 0.25:.3f}", "-i", str(src),
                    "-vf", vf, "-an", "-frames:v", str(frames), "-r", str(fps), *grade.encode_args(), str(out)],
                   check=True, timeout=1800)
    got = probe(out)["frames"]
    if got is not None and got != frames:
        raise RuntimeError(f"{out.name}: {got} frames, the shot is {frames}")
    return {"file": str(out), "frames": frames, "slowed": slow, "yavg": g["yavg"], "brightness": g["brightness"],
            "saturation": g["saturation"], "mono": g["mono"]}
