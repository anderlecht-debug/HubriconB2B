"""Speech for the generated briefing video.

index.html, welcome.html, terms.html §2 and portal.html all promise a recorded
walkthrough with every issue. `operator.py` hard-coded `video_id: None`, so the
promise depended on the founder remembering to record a Loom.

One provider interface, two implementations, because the choice has a privacy
consequence rather than just a quality one: the narration carries the client's
real dollar figures, so a hosted voice sends those numbers to a third party and
that vendor belongs in privacy.html's subprocessor table. `local` keeps the
numbers in the building at the cost of a flatter voice.

    HUBRICON_TTS=elevenlabs   (default when ELEVENLABS_API_KEY is set)
    HUBRICON_TTS=local        macOS `say` / `espeak-ng`, no vendor
    HUBRICON_TTS=off          no audio; the issue still publishes its letter
"""

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from . import meter

ELEVEN_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVEN_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
TIMEOUT = 120


class TTSUnavailable(RuntimeError):
    """No usable voice. The caller publishes the letter and skips the video."""


def provider() -> str:
    explicit = (os.environ.get("HUBRICON_TTS") or "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    return "local" if _local_binary() else "off"


def available() -> bool:
    return provider() != "off"


def _local_binary() -> str | None:
    return shutil.which("say") or shutil.which("espeak-ng") or shutil.which("espeak")


def _elevenlabs(text: str, out: Path) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise TTSUnavailable("ELEVENLABS_API_KEY is not set")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}",
        data=json.dumps({"text": text, "model_id": ELEVEN_MODEL,
                         "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode(),
        headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            out.write_bytes(res.read())
        # Billed by the character on a voiced request; a refused one costs nothing.
        meter.characters(meter.ELEVENLABS, len(text), "tts", item=ELEVEN_MODEL)
    except urllib.error.HTTPError as err:
        raise TTSUnavailable(f"ElevenLabs HTTP {err.code}: {err.read().decode(errors='replace')[:200]}")
    except (urllib.error.URLError, TimeoutError) as err:
        raise TTSUnavailable(f"ElevenLabs unreachable: {err}")


def _local(text: str, out: Path) -> None:
    binary = _local_binary()
    if not binary:
        raise TTSUnavailable("no local speech binary (say / espeak-ng)")
    aiff = out.with_suffix(".aiff")
    try:
        if binary.endswith("say"):
            subprocess.run([binary, "-o", str(aiff), "--data-format=LEF32@22050", text],
                           check=True, capture_output=True, timeout=TIMEOUT)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), str(out)],
                           check=True, capture_output=True, timeout=TIMEOUT)
            aiff.unlink(missing_ok=True)
        else:
            subprocess.run([binary, "-w", str(out.with_suffix(".wav")), text],
                           check=True, capture_output=True, timeout=TIMEOUT)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-i", str(out.with_suffix(".wav")), str(out)],
                           check=True, capture_output=True, timeout=TIMEOUT)
            out.with_suffix(".wav").unlink(missing_ok=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as err:
        raise TTSUnavailable(f"local speech failed: {err}")


def speak(text: str, out: Path) -> Path:
    """Render one beat's speech to an audio file at `out` (mp3)."""
    kind = provider()
    if kind == "off":
        raise TTSUnavailable("speech is switched off (HUBRICON_TTS=off)")
    out.parent.mkdir(parents=True, exist_ok=True)
    (_elevenlabs if kind == "elevenlabs" else _local)(text, out)
    if not out.exists() or out.stat().st_size == 0:
        raise TTSUnavailable(f"{kind} produced no audio")
    return out
