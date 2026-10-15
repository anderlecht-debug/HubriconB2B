"""QA for a long film (VISUAL_SPEC.md §10), by program, before the eye.

Reads the master, the plan and each shot's own clip. Thresholds live in
THRESHOLDS and are written into qa.json, so the `critique render` skill and the
founder can cite them. Then qa/contact.jpg: one frame per shot at its middle,
ten across, with the shot's id, style and source under it, and a larger sheet
of the first minute; the final review shows both at the top of REVIEW.md.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from . import grade, shots, tokens
from . import script as scriptmod
from .qa import TIER_RANGE, disclosure_for, lufs, transcript_match, _ffprobe_duration, _filter_log
from .state import CONTENT_DIR

THRESHOLDS = {"duration_s": TIER_RANGE["D"], "lufs": [-17.0, -15.0], "true_peak_dbtp": -1.5, "freeze_s": 4.0,
              "freeze_noise": 0.003, "world_luma": [128, 148], "blue_hue": [212, 228], "blue_sat": 0.6,
              "blue_world_share": 0.005, "paper_corner_tolerance": 3, "phash_min_distance": 10,
              "face_area": 0.01, "black_s": 0.5, "silence_s": 2.0, "transcript_match": 0.85}
YUNET = CONTENT_DIR / "assets" / "models" / "face_detection_yunet_2023mar.onnx"


def _frame(clip: Path, at: float, w: int = 480, h: int = 270) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, at):.3f}", "-i", str(clip), "-frames:v", "1",
                          "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=120).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3) if len(raw) == w * h * 3 else np.zeros((h, w, 3), np.uint8)


def blue_share(rgb: np.ndarray) -> float:
    """Share of pixels in the saturated money blue (§10): hue 212–228°, saturation over 0.6."""
    x = rgb.astype(np.float32) / 255.0
    mx, mn = x.max(axis=2), x.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    d = np.maximum(mx - mn, 1e-6)
    hue = np.where(mx == b, 60 * ((r - g) / d + 4), np.where(mx == g, 60 * ((b - r) / d + 2), 60 * (((g - b) / d) % 6)))
    lo, hi = THRESHOLDS["blue_hue"]
    return float(((hue >= lo) & (hue <= hi) & (sat > THRESHOLDS["blue_sat"]) & (mx > 0.2)).mean())


def faces(rgb: np.ndarray) -> float:
    """The largest face's share of the frame (YuNet), 0 when none."""
    import cv2
    h, w = rgb.shape[:2]
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.8)
    _, found = det.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if found is None:
        return 0.0
    return float(max(f[2] * f[3] for f in found) / (w * h))


def phash(rgb: np.ndarray):
    import imagehash
    from PIL import Image
    return imagehash.phash(Image.fromarray(rgb))


def contact(d: Path, plan: dict, out: Path, across: int = 10, first_minute: bool = False) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    pick = [s for s in plan["shots"] if not first_minute or float(s["start"]) < 60]
    W, H, pad, cap = (384, 216, 8, 26) if not first_minute else (640, 360, 10, 30)
    across = across if not first_minute else 4
    rows = max(1, (len(pick) + across - 1) // across)
    sheet = Image.new("RGB", (across * (W + pad) + pad, rows * (H + cap + pad) + pad), tokens.rgb("paper_2"))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(tokens.font_file(400, display=False)), 15 if not first_minute else 20)
    for i, s in enumerate(pick):
        clip = d / "shots" / f"{s['id']}.mp4"
        rgb = _frame(clip, (float(s["end"]) - float(s["start"])) / 2, W, H)
        x, y = pad + (i % across) * (W + pad), pad + (i // across) * (H + cap + pad)
        sheet.paste(Image.fromarray(rgb), (x, y))
        a = s.get("asset")
        src = (a[0] if isinstance(a, list) else a or {}).get("id", "paper") if a else "paper"
        draw.text((x, y + H + 5), f"{s['id']} {s['style']} · {str(src)[:24]}", font=font, fill=tokens.rgb("ink_2"))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)
    return out


def run(u: dict) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    master = d / "media" / "master.mp4"
    if not master.exists():
        return {"status": "failed", "reason": "no master.mp4; run assemble first"}
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shots.load_timing(d)
    facts = scriptmod.load_facts(slug)
    usage = json.loads(shots.USAGE.read_text(encoding="utf-8")) if shots.USAGE.exists() else {}
    T, problems = THRESHOLDS, []
    dur = _ffprobe_duration(master)
    loud = lufs(master)
    peak_log = _filter_log(master, af="ebur128=peak=true")
    peaks = [float(x) for x in re.findall(r"Peak:\s*(-?[\d.]+) dBFS", peak_log)]
    freeze = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", _filter_log(master, vf=f"freezedetect=n={T['freeze_noise']}:d={T['freeze_s']}"))]
    black = re.findall(r"black_start", _filter_log(master, vf=f"blackdetect=d={T['black_s']}:pix_th=0.05"))
    silence = [(float(a), float(b)) for a, b in re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)",
                                                           _filter_log(master, af=f"silencedetect=n=-55dB:d={T['silence_s']}"))]
    cards = [(float(c["start"]), float(c["end"])) for c in timing["segments"] if c["kind"] == "card"]
    silence = [x for x in silence if not any(a - 1 <= x[0] <= b + 1 for a, b in cards)]
    per_shot, hashes = {}, []
    for s in plan["shots"]:
        clip = d / "shots" / f"{s['id']}.mp4"
        mid = _frame(clip, (float(s["end"]) - float(s["start"])) / 2)
        row = {"blue": round(blue_share(mid), 4)}
        if s.get("room") == "world":
            row["luma"] = round(grade.measure(clip)["yavg"], 1)
            row["face"] = round(max(faces(_frame(clip, t)) for t in np.arange(0.2, float(s["end"]) - float(s["start"]), 2.0)), 4)
            hashes.append((s["id"], phash(mid)))
            lo, hi = T["world_luma"]
            if not lo <= row["luma"] <= hi:
                problems.append(f"{s['id']}: world luma {row['luma']}, outside {lo}–{hi}")
            if row["blue"] > T["blue_world_share"]:
                problems.append(f"{s['id']}: {row['blue']:.1%} saturated blue in a world frame; blue is money's")
            named = s.get("specific") and str((s.get("asset") or {}).get("source", "")) in ("loc", "smithsonian", "commons", "archive", "nara")
            if row["face"] > T["face_area"] and not named:
                problems.append(f"{s['id']}: a face over {T['face_area']:.0%} of the frame in a stock or AI shot")
        else:
            corners = [mid[2:8, 2:8], mid[2:8, -8:-2]]
            paper = np.array(tokens.rgb("paper"))
            if s.get("kind") not in ("chapter",) and max(np.abs(c.astype(int) - paper).max() for c in corners) > T["paper_corner_tolerance"] + 4:
                problems.append(f"{s['id']}: the paper corner is not the paper token")
            money = any("$" in str(facts.get(r["key"], {}).get("value", "")) for r in s.get("reveals", []))
            if row["blue"] > 0.0005 and not money and s.get("kind") not in ("chart",):
                problems.append(f"{s['id']}: blue on a paper shot that reveals no money")
        per_shot[s["id"]] = row
    for i, (a, ha) in enumerate(hashes):
        for b, hb in hashes[i + 1:]:
            if ha - hb < T["phash_min_distance"]:
                problems.append(f"{a} and {b}: the same picture twice (phash distance {ha - hb})")
    problems += [f"provenance: {p}" for p in shots.validate(plan, timing, facts, picked=True, usage=usage)
                 if any(w in p for w in ("provenance", "licence", "asset", "filters", "already in this film", "last 10 films"))]
    tm = transcript_match(slug, master)
    desc = (d / "description.md").read_text(encoding="utf-8") if (d / "description.md").exists() else ""
    checks = {
        "duration_in_range": T["duration_s"][0] <= dur <= T["duration_s"][1],
        "loudness_within_1_lu": loud is not None and T["lufs"][0] <= loud <= T["lufs"][1],
        "true_peak": not peaks or max(peaks) <= T["true_peak_dbtp"],
        "nothing_frozen_over_4s": not freeze,
        "no_black": not black,
        "no_silence_outside_chapter_cards": not silence,
        "transcript_match_ge_85": (tm is None) or tm >= T["transcript_match"],
        "picture_checks": not problems,
        "disclosure_in_description": disclosure_for(u.get("voice")) in desc if desc else None,
    }
    sheet = contact(d, plan, d / "qa" / "contact.jpg")
    first = contact(d, plan, d / "qa" / "first-minute.jpg", first_minute=True)
    hard = [k for k, v in checks.items() if v is False and k != "disclosure_in_description"]
    out = {"slug": slug, "tier": "D", "pass": not hard, "failed": hard, "thresholds": T, "duration_s": round(dur, 1), "lufs": loud,
           "true_peak": max(peaks) if peaks else None, "freezes": freeze, "silences": silence, "transcript_match": tm,
           "problems": problems, "shots": per_shot, "checks": checks, "voice": u.get("voice"),
           "contact": str(sheet.relative_to(d)), "first_minute": str(first.relative_to(d))}
    (d / "qa.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return {"status": "ok" if out["pass"] else "failed", **{k: out[k] for k in ("pass", "failed", "duration_s", "lufs", "transcript_match")},
            "problems": problems[:12]}
