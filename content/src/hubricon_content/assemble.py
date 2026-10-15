"""The master: scene clips in timeline order, grain over everything, subtitles
burned in, the mixed audio underneath. Hard cuts between segments (bible §6:
whip pan or hard cut, never a dissolve)."""

import json
import subprocess
from pathlib import Path

from . import audio, subtitles
from . import script as scriptmod

# Paper's grain (VISUAL_SPEC §3.2): every A/B frame is paper. Tier D grains each clip by its room.
GRAIN = "noise=alls=2:allf=t+u"


def run_d(u: dict) -> dict:
    """Tier D (VISUAL_SPEC.md §8.5–8.6): the shot clips joined in plan order, re-encoded
    once at the master's settings, the mix underneath, nothing burned in, and the
    narration's own words written to media/captions.srt for YouTube's caption track."""
    from . import grade
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    clips = [d / "shots" / f"{s['id']}.mp4" for s in plan["shots"]]
    missing = [c.name for c in clips if not c.exists()]
    if missing:
        return {"status": "failed", "reason": f"missing shot clips ({len(missing)}): {', '.join(missing[:5])}; run render-shots first"}
    manifest = d / "shots" / "concat.txt"
    manifest.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    mix = audio.mix(slug)
    srt = subtitles.write_srt(slug)
    out = d / "media" / "master.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-i", str(mix),
                    "-map", "0:v", "-map", "1:a", "-r", "30", *grade.encode_args("master"),
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True, timeout=4 * 3600)
    return {"status": "ok", "master": str(out.relative_to(d.parents[1])), "shots": len(clips), "captions": srt.name}


def run(u: dict, q: dict, force: bool = False) -> dict:
    if str(u.get("tier", "")).upper() == "D":
        return run_d(u)
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
    vf = f"{GRAIN},{subtitles.ass_filter(subs)}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-i", str(mix),
           "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=3600)
    return {"status": "ok", "master": str(out.relative_to(d.parents[1])), "segments": len(clips)}
