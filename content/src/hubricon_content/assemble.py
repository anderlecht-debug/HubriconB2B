"""The master: scene clips in timeline order, grain over everything, subtitles
burned in, the mixed audio underneath. Hard cuts between segments (bible §6:
whip pan or hard cut, never a dissolve)."""

import json
import subprocess
from pathlib import Path

from . import audio, subtitles
from . import script as scriptmod

GRAIN = "noise=alls=5:allf=t+u"


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    clips = []
    for k, seg in enumerate(timing["segments"]):
        p = d / "scenes" / f"seg-{k:02d}.mp4"
        if not p.exists():
            return {"status": "failed", "reason": f"missing scene clip {p.name}; run render-scenes first"}
        clips.append(p)
    manifest = d / "scenes" / "concat.txt"
    manifest.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    mix = audio.mix(slug)
    subs = subtitles.write(slug)
    out = d / "media" / "master.mp4"
    vf = f"{GRAIN},ass={subs.as_posix()}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-i", str(mix),
           "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=3600)
    return {"status": "ok", "master": str(out.relative_to(d.parents[1])), "segments": len(clips)}
