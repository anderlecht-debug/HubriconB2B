"""The world grade (VISUAL_SPEC.md §3.2): one grade and one grain over every
world asset, so a stock clip, a 1930s photograph and an engine chart read as
one film.

Four stages, in order, with the numbers in content/assets/grade.json:

1. Conform: cover 1920×1080 around the picked focus, 30 fps, square pixels.
2. Normalize: measure the window's mean luma and saturation, then shift
   brightness so the graded picture lands at 138 ± 10 (of 255) and scale
   saturation into the band. An asset that needs more than ±0.12 brightness
   is too far from the look to grade honestly, and is rejected.
3. Grade: soft contrast, lifted shadows, a slight cool shift, blues and cyans
   pulled down, so the only saturated blue on screen is money.
4. Grain: stronger on world clips than on paper.

Black-and-white archival photographs skip the colour stages and stay
monochrome; nothing is ever colourized.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path

from .state import CONTENT_DIR

GRADE_JSON = CONTENT_DIR / "assets" / "grade.json"


@functools.lru_cache(maxsize=1)
def spec() -> dict:
    return json.loads(GRADE_JSON.read_text(encoding="utf-8"))


class Rejected(ValueError):
    """The asset is too far from the look to grade honestly."""


def conform(focus: tuple[float, float] = (0.5, 0.5)) -> str:
    """Scale to cover the frame, then crop around the focus point."""
    c = spec()["conform"]
    w, h = c["width"], c["height"]
    fx, fy = (min(1.0, max(0.0, float(v))) for v in focus)
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h}:(iw-{w})*{fx:.4f}:(ih-{h})*{fy:.4f},setsar=1,fps={c['fps']}")


def measure(path: Path, chain: str = "", start: float | None = None, duration: float | None = None,
            image: bool = False) -> dict:
    """Mean luma (YAVG) and saturation (SATAVG), 0–255 scale, over a window, on a small copy."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if image:
        cmd += ["-loop", "1", "-t", "1"]
    if start is not None and not image:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration is not None and not image:
        cmd += ["-t", f"{duration:.3f}"]
    # Two frames a second are taken *before* the chain, so the conform and the grade run on the
    # frames that are measured, not on thirty a second that are thrown away (a footage preview
    # took minutes of 1080p grading per candidate); the chain's own frame rate is dropped here.
    chain = re.sub(r"(^|,)fps=[\d.]+(?=,|$)", "", chain).strip(",")
    vf = ",".join(x for x in ("fps=2", chain, "scale=480:270:flags=bilinear", "format=yuv420p", "signalstats",
                              "metadata=print:file=-") if x)
    cmd += ["-vf", vf, "-an", "-f", "null", "-"]
    # an archival file's own metadata (EXIF in Latin-1) is printed too; only the numbers matter
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600).stdout
    y = [float(v) for v in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", out)]
    s = [float(v) for v in re.findall(r"lavfi\.signalstats\.SATAVG=([\d.]+)", out)]
    if not y:
        raise RuntimeError(f"could not measure {path}")
    return {"yavg": sum(y) / len(y), "satavg": sum(s) / len(s) if s else 0.0}


def is_mono(path: Path, image: bool = False) -> bool:
    """A source with no colour to speak of (an archival black-and-white photograph)."""
    return measure(path, image=image)["satavg"] < 3.0


BORDER_MAX = 0.15         # never trim more than this share of a side


@functools.lru_cache(maxsize=512)
def border_box(path: Path) -> tuple[float, float, float, float] | None:
    """The print inside a scan, as fractions (x, y, w, h): uniform white or black edges (a card
    mount, a glass negative's rebate, a scanner's bed) trimmed, never more than BORDER_MAX a side.
    None when there is no border to speak of. Framing, not retouching: nothing inside is touched."""
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(path).convert("L")
        im.thumbnail((800, 800))
        a = np.asarray(im, dtype=np.float32)
    except Exception:
        return None
    h, w = a.shape

    def edge(lines) -> int:
        """How many lines from this side are mount or rebate. A line is border when most of it is
        near-pure white or black (a print sits a little crooked in its mount and a negative's edge
        is ragged); the border is the deepest such line, provided most lines before it are border
        too (a scanner's grey strip may come first) and the picture begins right after it."""
        frac = [max(float((ln > 225).mean()), float((ln < 50).mean())) for ln in lines]
        deep = [i for i, f in enumerate(frac) if f >= 0.85]
        for k in reversed(deep):
            inside = frac[k + 1:k + 4]
            if sum(f >= 0.85 for f in frac[:k + 1]) >= 0.7 * (k + 1) and inside and sum(inside) / len(inside) < 0.6:
                return k + 1
        return 0
    cap_h, cap_w = int(h * BORDER_MAX), int(w * BORDER_MAX)
    top, bottom = min(edge(a[:cap_h]), cap_h), min(edge(a[::-1][:cap_h]), cap_h)
    left, right = min(edge(a.T[:cap_w]), cap_w), min(edge(a.T[::-1][:cap_w]), cap_w)
    if max(top, bottom) < h * 0.01 and max(left, right) < w * 0.01:
        return None
    pad = max(2, round(0.012 * max(h, w)))   # inside the edge, so a ragged or crooked one does not survive
    x0, y0 = (left + pad) / w, (top + pad) / h
    x1, y1 = 1 - (right + pad) / w, 1 - (bottom + pad) / h
    return (round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4))


def trim(path: Path) -> str:
    """The crop filter that keeps only the print (empty when there is no border)."""
    b = border_box(Path(path))
    return f"crop=iw*{b[2]}:ih*{b[3]}:iw*{b[0]}:ih*{b[1]}" if b else ""


def plan(path: Path, *, image: bool = False, focus=(0.5, 0.5), start: float | None = None,
         duration: float | None = None, mono: bool | None = None, room: str = "world", crop: bool = True,
         grain: bool = True, strict: bool = True) -> dict:
    """The exact filter chain for one asset, after measuring it; raises Rejected
    when it cannot reach the look. Returns {"filter", "brightness", "saturation",
    "yavg", "mono"}; "yavg" is the measured result of the whole chain."""
    g, n = spec(), spec()["normalize"]
    mono = is_mono(path, image) if mono is None else mono
    head = ",".join(x for x in ((trim(path) if image else ""), conform(focus) if crop else "") if x)
    base = g["mono"]["grade"] if mono else g["grade"]
    raw = measure(path, head, start, duration, image)
    if raw["yavg"] < n["reject_below_yavg"]:
        raise Rejected(f"mean luma {raw['yavg']:.0f} is night or low-key; the world is high-key (§6.1)")
    sat = 1.0
    if not mono and raw["satavg"] > 0:
        lo, hi = n["saturation_band"]
        smin, smax = n["saturation_scale_limits"]
        if raw["satavg"] > hi:
            sat = max(smin, hi / raw["satavg"])
        elif raw["satavg"] < lo:
            sat = min(smax, lo / raw["satavg"])

    def chain(b: float) -> str:
        parts = [head] if head else []
        parts.append("format=gray" if mono else "")
        parts.append(f"eq=brightness={b:.4f}:saturation={sat:.4f}" if not mono else f"eq=brightness={b:.4f}")
        parts.append(base)   # empty for mono: §3.2 skips the grade stage
        return ",".join(p for p in parts if p)

    b = 0.0
    for _ in range(3):   # the grade is close to linear in brightness; two corrections land it
        got = measure(path, chain(b), start, duration, image)["yavg"]
        miss = n["target_yavg"] - got
        if abs(miss) <= n["tolerance"] * 0.5:
            break
        b += miss / 255.0
    # judged on the shift it converged to, not a step on the way there (rounding allowed)
    clamped = abs(b) > n["max_brightness_shift"] + 0.005
    if clamped and strict:
        raise Rejected(f"needs a brightness shift of {b:+.2f}; more than ±{n['max_brightness_shift']} is not an honest grade")
    if clamped:
        # At render time the asset has passed sourcing on its preview; the full file's window may
        # need a hair more. It gets the most an honest grade allows, never more, and says so.
        b = max(-n["max_brightness_shift"], min(n["max_brightness_shift"], b))
    final = measure(path, chain(b), start, duration, image)["yavg"]
    if strict and abs(final - n["target_yavg"]) > n["tolerance"]:
        raise Rejected(f"lands at mean luma {final:.0f}, outside {n['target_yavg']} ± {n['tolerance']}")
    noise = (g["grain"]["paper" if room == "paper" else "world"] + ",") if grain else ""
    tail = "format=yuv420p" if not mono else "format=gray,format=yuv420p"
    return {"filter": f"{chain(b)},{noise}{tail}", "brightness": round(b, 4), "saturation": round(sat, 4),
            "yavg": round(final, 1), "mono": mono, **({"clamped": True} if clamped else {})}


def still(src: Path, out: Path, mono: bool | None = None) -> dict:
    """A graded still for the film stage: colour and grain from the grade, kept at
    up to 3840 px wide so the stage's moves (to 1.35 on a pull-back) stay sharp.
    The stage crops and moves it; this only gives it the look. Its grain is added
    per frame when the shot is encoded, so it moves like film grain does."""
    w = spec()["conform"]["still_max_width"]
    p = plan(src, image=True, mono=mono, crop=False, grain=False, strict=False)
    vf = f"scale='min({w},iw)':-2:flags=lanczos,{p['filter']}"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", vf, "-frames:v", "1", "-q:v", "2", str(out)],
                   check=True, timeout=300)
    return {**p, "file": str(out)}


def encode_args(kind: str = "intermediate") -> list[str]:
    """Encoder arguments for a per-shot clip (NVENC when this machine has it) or the master."""
    g = spec()
    if kind == "master":
        return g["master"] + g["color"]
    return ["-c:v", g["intermediate"]["codec"], *g["intermediate"]["args"], *g["color"]] if nvenc() else \
        [*g["intermediate"]["fallback"], *g["color"]]


@functools.lru_cache(maxsize=1)
def nvenc() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x144:d=0.1", "-c:v", "h264_nvenc",
                            "-f", "null", "-"], capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
