"""The review draft of a long film and its review sheets, made on this machine for no tokens
(docs/content/FILM_LINE.md).

    hubricon-content draft <slug> [--remix]      → media/draft.mp4
    hubricon-content review-sheets <slug>        → qa/sheets/<section>-NN.jpg

The draft is assemble.run_d's join and mix encoded on the GPU (h264_nvenc), with x264 when there is
no GPU, so a 30-minute film is a draft in minutes. Its length is checked against the narration plus
the end card's hold: a clip that would not open ends a concat early, silently. The sheets show three
frames of every shot (15%, 50%, 85%) with its id, time, kind and words, six shots a sheet: the one
look a person (or one cheap review pass) takes at a film.
"""
from __future__ import annotations

import json
import subprocess
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import grade
from . import script as scriptmod


def _encode(cmd_head: list[str], out: Path, tail: list[str]) -> None:
    gpu = ["-c:v", "h264_nvenc", "-preset", "p6", "-rc", "vbr", "-cq", "18", "-b:v", "0", "-profile:v", "high"]
    cpu = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-profile:v", "high"]
    for enc in (gpu, cpu):
        r = subprocess.run([*cmd_head, *enc, *grade.spec()["color"], *tail, str(out)], timeout=3 * 3600)
        if r.returncode == 0:
            return
    raise RuntimeError("the draft could not be encoded")


def draft(slug: str, remix: bool = False) -> dict:
    from . import audio, shots, subtitles
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    missing = [s["id"] for s in plan["shots"] if not (d / "shots" / f"{s['id']}.mp4").exists()]
    if missing:
        return {"status": "blocked", "reason": f"{len(missing)} shot(s) have no clip: run render-shots", "missing": missing[:20]}
    manifest = d / "shots" / "concat-draft.txt"
    manifest.write_text("".join(f"file '{(d / 'shots' / (s['id'] + '.mp4')).resolve()}'\n" for s in plan["shots"]), encoding="utf-8")
    mix = d / "media" / "mix.wav"
    if remix or not mix.exists():
        mix = audio.mix(slug)
    subtitles.write_srt(slug)
    out = d / "media" / "draft.mp4"
    _encode(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest), "-i", str(mix),
             "-map", "0:v", "-map", "1:a", "-r", "30"], out, ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"])
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    want = float(timing["duration"]) + shots.end_tail(plan)
    got = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout.strip() or 0)
    if abs(got - want) > 1.0:
        return {"status": "failed", "reason": f"the draft runs {got:.1f} s; the narration and the end card's hold run {want:.1f} s"}
    return {"status": "ok", "draft": str(out), "shots": len(plan["shots"]), "seconds": round(got, 1)}


def review_sheets(slug: str, per_sheet: int = 6) -> dict:
    from PIL import Image, ImageDraw, ImageFont
    from . import shots
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shots.load_timing(d)
    words = shots.spoken(timing)
    out = d / "qa" / "sheets"
    (out / "f").mkdir(parents=True, exist_ok=True)
    tw, th = 400, 225

    def frames(s):
        dur = float(s["end"]) - float(s["start"])
        res = []
        for k, f in enumerate((0.15, 0.5, 0.85)):
            p = out / "f" / f"{s['id']}-{k}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * f:.2f}", "-i", str(d / "shots" / f"{s['id']}.mp4"),
                            "-frames:v", "1", "-vf", f"scale={tw}:{th}", "-q:v", "3", str(p)])
            res.append(p)
        return res

    with ThreadPoolExecutor(8) as ex:
        fr = list(ex.map(frames, plan["shots"]))
    fonts = "/usr/share/fonts/TTF/"
    font, bold = ImageFont.truetype(fonts + "DejaVuSans.ttf", 15), ImageFont.truetype(fonts + "DejaVuSans-Bold.ttf", 17)
    groups: dict[str, list] = {}
    for s, f in zip(plan["shots"], fr):
        groups.setdefault(s["id"][0], []).append((s, f))
    made = []
    for sec, items in groups.items():
        for n in range(0, len(items), per_sheet):
            chunk = items[n:n + per_sheet]
            sheet = Image.new("RGB", (3 * tw + 340, len(chunk) * (th + 8)), (24, 24, 24))
            dr = ImageDraw.Draw(sheet)
            for i, (s, f) in enumerate(chunk):
                y = i * (th + 8)
                for k, p in enumerate(f):
                    if p.exists():
                        sheet.paste(Image.open(p), (k * tw, y))
                x, dur = 3 * tw + 10, float(s["end"]) - float(s["start"])
                m, sec_ = divmod(float(s["start"]), 60)
                dr.text((x, y + 4), f"{s['id']}  {int(m)}:{sec_:04.1f}  {dur:.1f}s", font=bold, fill=(255, 220, 120))
                dr.text((x, y + 26), f"{s.get('kind')} · {s.get('style')}", font=font, fill=(200, 200, 200))
                said = " ".join(w["word"] for w in shots.words_in(words, s["start"], s["end"]))
                dr.multiline_text((x, y + 48), "\n".join(textwrap.fill(said, 38).split("\n")[:9]), font=font, fill=(235, 235, 235), spacing=2)
            p = out / f"{sec}-{n // per_sheet + 1:02d}.jpg"
            sheet.save(p, quality=85)
            made.append(str(p))
    return {"status": "ok", "sheets": len(made), "dir": str(out)}
