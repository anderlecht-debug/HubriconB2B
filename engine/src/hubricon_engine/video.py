"""The generated briefing video.

Promised in six places — index.html ("Teardown on video in 24 hours"),
welcome.html ("Your Profit Teardown, on video"), terms.html §2 as a
contractual deliverable, portal.html, the triage fact sheet and the cold copy.
Delivered by nobody: operator.py published Issue 001 with `video_id: None` and
the digest merely *suggested* the founder record a Loom.

One slide per beat, spoken from the same beat's `speech`, so the picture and
the voice cannot drift. Same navy/amber palette and inline-SVG discipline as
console.py and the report package, because every surface a client sees should
look like one instrument.

Nothing here is allowed to block the written deliverable: `render` returns None
on any failure and the caller publishes the letter and the report regardless.
"""

import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path

from . import tts
from .console import AMBER, EDGE, INK, INK_35, INK_60, NAVY_DEEP, PANEL
from .harvest.fetch import chrome_binary

WIDTH, HEIGHT = 1280, 720
MIN_SLIDE_SECONDS = 3.5     # a beat with almost no words still needs reading time
PAD_SECONDS = 0.6           # a breath between beats
TIMEOUT = 180


class VideoUnavailable(RuntimeError):
    """No Chrome, no ffmpeg, or no voice. The issue ships without a video."""


def _tool(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise VideoUnavailable(f"{name} is not on PATH")
    return found


def available() -> tuple[bool, str]:
    """Whether a video can be produced here, and why not when it cannot."""
    if not tts.available():
        return False, "no speech provider (set ELEVENLABS_API_KEY or HUBRICON_TTS=local)"
    if not chrome_binary():
        return False, "no Chrome/Chromium binary for slide capture"
    if not shutil.which("ffmpeg"):
        return False, "ffmpeg is not on PATH"
    return True, "ready"


# ── slides ───────────────────────────────────────────────────────────────────

def slide_html(company: str, issue_number: int, beat: dict, index: int, total: int) -> str:
    """One beat as a full-bleed slide. Deliberately sparse: it is read at a
    glance while the voice carries the argument."""
    points = ""
    if beat["points"]:
        rows = "".join(
            f'<div class="row"><span class="k">{escape(str(k))}</span>'
            f'<span class="v">{escape(str(v))}</span></div>'
            for k, v in beat["points"]
        )
        points = f'<div class="points">{rows}</div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{width:{WIDTH}px;height:{HEIGHT}px;background:{NAVY_DEEP};color:{INK};
       font-family:Georgia,'Times New Roman',serif;padding:64px 72px;
       display:flex;flex-direction:column;justify-content:space-between}}
  .top{{display:flex;justify-content:space-between;align-items:baseline;
       font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:{INK_35}}}
  .brand{{color:{AMBER}}}
  h1{{font-size:46px;line-height:1.15;font-weight:normal;margin:28px 0 22px}}
  .speech{{font-size:23px;line-height:1.5;color:{INK_60};max-width:900px}}
  .points{{margin-top:26px;border-top:1px solid {EDGE}}}
  .row{{display:flex;justify-content:space-between;gap:32px;padding:13px 0;
       border-bottom:1px solid {EDGE};background:{PANEL}}}
  .k{{font-size:19px;color:{INK_60}}}
  .v{{font-size:22px;color:{AMBER};font-variant-numeric:tabular-nums;text-align:right}}
  .foot{{display:flex;justify-content:space-between;font-size:14px;color:{INK_35}}}
</style></head><body>
  <div class="top"><span class="brand">Hubricon</span>
    <span>{escape(company)} · Profit Brief No. {issue_number:03d}</span></div>
  <div><h1>{escape(beat['heading'])}</h1>
    <p class="speech">{escape(beat['speech'])}</p>{points}</div>
  <div class="foot"><span>{escape(company)}</span><span>{index} / {total}</span></div>
</body></html>"""


def _capture(html: str, out: Path, chrome: str) -> None:
    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           f"--window-size={WIDTH},{HEIGHT}", f"--screenshot={out}",
           "--virtual-time-budget=2000", page.as_uri()]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=TIMEOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        raise VideoUnavailable(f"slide capture failed: {err}")
    if not out.exists():
        raise VideoUnavailable("Chrome produced no screenshot")


def _duration(path: Path) -> float:
    """Seconds of audio, from ffprobe; a failure falls back to the floor rather
    than desynchronising the whole video."""
    probe = shutil.which("ffprobe")
    if not probe:
        return MIN_SLIDE_SECONDS
    try:
        res = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)],
                             check=True, capture_output=True, timeout=30)
        return max(MIN_SLIDE_SECONDS, float(res.stdout.decode().strip()) + PAD_SECONDS)
    except Exception:
        return MIN_SLIDE_SECONDS


def render(company: str, issue_number: int, beats: list[dict], out_path: Path) -> Path | None:
    """Produce the .mp4, or return None with a printed reason.

    Never raises into the caller: welcome.html promises the letter and the
    report inside 24 hours, and a TTS outage must not hold those hostage."""
    ok, why = available()
    if not ok:
        print(f"  video skipped: {why}")
        return None
    chrome = chrome_binary()
    try:
        ffmpeg = _tool("ffmpeg")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            segments = []
            for i, beat in enumerate(beats, start=1):
                audio = tts.speak(beat["speech"], work / f"beat-{i:02d}.mp3")
                shot = work / f"beat-{i:02d}.png"
                _capture(slide_html(company, issue_number, beat, i, len(beats)), shot, chrome)
                segments.append((shot, audio, _duration(audio)))

            # One clip per beat, each still held for exactly its own narration.
            clips = []
            for i, (shot, audio, seconds) in enumerate(segments, start=1):
                clip = work / f"clip-{i:02d}.mp4"
                subprocess.run(
                    [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-i", str(shot),
                     "-i", str(audio), "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-b:a", "128k", "-t", f"{seconds:.2f}", "-shortest", str(clip)],
                    check=True, capture_output=True, timeout=TIMEOUT)
                clips.append(clip)

            manifest = work / "clips.txt"
            manifest.write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(manifest), "-c", "copy", str(out_path)],
                check=True, capture_output=True, timeout=TIMEOUT)
        return out_path if out_path.exists() and out_path.stat().st_size else None
    except (VideoUnavailable, tts.TTSUnavailable) as err:
        print(f"  video skipped: {err}")
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        detail = getattr(err, "stderr", b"") or b""
        print(f"  video failed: {err} {detail.decode(errors='replace')[:200]}")
        return None
