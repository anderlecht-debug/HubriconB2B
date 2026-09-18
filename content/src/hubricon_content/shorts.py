"""Vertical cuts from CLIP markers: the scene re-laid at 9:16 (never a crop of
the master), the beat's own audio, burned subtitles, under forty-five seconds."""

import json
import subprocess
from pathlib import Path

from . import render_scenes, subtitles
from . import script as scriptmod
from .assemble import GRAIN


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    mix = d / "media" / "mix.wav"
    if not mix.exists():
        return {"status": "failed", "reason": "no mix.wav; run assemble first"}
    (d / "shorts").mkdir(exist_ok=True)
    subs_full = subtitles.write(slug, vertical=True)
    made = []
    for clip in timing["clips"][:4]:
        seg_index = next(k for k, s in enumerate(timing["segments"]) if s.get("index") == clip["index"])
        seg = timing["segments"][seg_index]
        v = render_scenes.render_segment(d, seg, seg_index, vertical=True, force=force)
        length = min(45.0, clip["end"] - clip["start"])
        # shift the subtitle file so the clip starts at zero
        shifted = d / "shorts" / f"subs-{clip['index']:02d}.ass"
        lines = []
        for line in subs_full.read_text(encoding="utf-8").splitlines():
            if line.startswith("Dialogue:"):
                parts = line.split(",", 3)
                def sh(ts):
                    h, m, s = ts.split(":"); t = int(h) * 3600 + int(m) * 60 + float(s) - clip["start"]
                    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}" if t >= 0 else None
                a, b = sh(parts[1]), sh(parts[2])
                if a is None or b is None or float(parts[2].split(":")[-1]) < 0:
                    continue
                lines.append(",".join([parts[0], a, b, parts[3]]))
            else:
                lines.append(line)
        shifted.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = d / "shorts" / f"{clip['index']:02d}.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(v), "-ss", f"{clip['start']:.3f}", "-t", f"{length:.3f}", "-i", str(mix),
               "-vf", f"{GRAIN},ass={shifted.as_posix()}", "-t", f"{length:.3f}", "-r", "30", "-c:v", "libx264", "-crf", "18",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)]
        subprocess.run(cmd, check=True, timeout=1800)
        made.append(out.name)
    return {"status": "ok" if len(made) >= 3 else "failed", "shorts": made,
            **({} if len(made) >= 3 else {"reason": f"only {len(made)} CLIP markers produced shorts; three are needed"})}
