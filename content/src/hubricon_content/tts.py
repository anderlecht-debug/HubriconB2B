"""Narration, one beat at a time, with word timing.

Two providers. The founder's ElevenLabs clone is the only voice that may ship;
it returns character alignment with the audio, so subtitles and reveal times
need no transcription. The placeholder is Kokoro, an offline open-weights voice
whose output is aligned by faster-whisper; it exists so the whole chain can be
proven and reviewed before the clone exists, and a unit narrated by it is never
publishable.
"""

import base64
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

ELEVEN_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVEN_SETTINGS = {"stability": 0.40, "similarity_boost": 0.80, "style": 0.15, "use_speaker_boost": True}
KOKORO_DIR = CONTENT_DIR / ".cache" / "kokoro"
KOKORO_VOICE = "am_michael"
WHISPER_MODEL = os.environ.get("CONTENT_WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("CONTENT_WHISPER_DEVICE", "cpu")   # the box has a GPU but no CUDA runtime libraries
WORD_RE = re.compile(r"[A-Za-z0-9$%'’.,-]+")


def provider() -> tuple[str, str]:
    """(name, reason)."""
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
        return "founder", "ElevenLabs clone of the founder's voice"
    if (KOKORO_DIR / "kokoro-v1.0.onnx").exists() and (KOKORO_DIR / "voices-v1.0.bin").exists():
        return "placeholder", "Kokoro offline placeholder; never ships"
    return "none", ("Narration needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env for the founder's clone, "
                    "or the Kokoro model files in content/.cache/kokoro for the placeholder.")


def _eleven(text: str, out_mp3: Path) -> list[dict]:
    key, voice = os.environ["ELEVENLABS_API_KEY"], os.environ["ELEVENLABS_VOICE_ID"]
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
        data=json.dumps({"text": text, "model_id": ELEVEN_MODEL, "voice_settings": ELEVEN_SETTINGS}).encode(),
        headers={"xi-api-key": key, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as res:
        payload = json.loads(res.read())
    out_mp3.write_bytes(base64.b64decode(payload["audio_base64"]))
    al = payload["alignment"]
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, t0, t1 = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": t0, "end": t1}); cur, t0 = "", None
            continue
        if not cur:
            t0 = s
        cur += ch; t1 = e
    if cur:
        words.append({"word": cur, "start": t0, "end": t1})
    return words


_kokoro = None
_whisper = None


def _kokoro_model():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"), str(KOKORO_DIR / "voices-v1.0.bin"))
    return _kokoro


def _whisper_model(device: str | None = None):
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        dev = device or WHISPER_DEVICE
        _whisper = WhisperModel(WHISPER_MODEL, device=dev, compute_type="int8_float16" if dev == "cuda" else "int8",
                                cpu_threads=8)
    return _whisper


def align(wav: Path) -> list[dict]:
    """Word timestamps for any audio file, via faster-whisper. A CUDA failure
    (no runtime libraries on this box) falls back to the CPU once."""
    global _whisper
    try:
        segments, _ = _whisper_model().transcribe(str(wav), word_timestamps=True, language="en", beam_size=3)
        return [{"word": w.word.strip(), "start": float(w.start), "end": float(w.end)}
                for s in segments for w in (s.words or [])]
    except RuntimeError:
        _whisper = None
        segments, _ = _whisper_model("cpu").transcribe(str(wav), word_timestamps=True, language="en", beam_size=3)
        return [{"word": w.word.strip(), "start": float(w.start), "end": float(w.end)}
                for s in segments for w in (s.words or [])]


def _placeholder(text: str, out_wav: Path) -> list[dict]:
    import soundfile as sf
    samples, rate = _kokoro_model().create(text, voice=KOKORO_VOICE, speed=1.0, lang="en-us")
    sf.write(str(out_wav), samples, rate)
    return align(out_wav)


def speakable(text: str) -> str:
    """Punctuation is timing for a voice model; ellipses read as dead air, so a
    pause is a comma or a line break, never three dots."""
    t = text.replace("…", ",").replace("...", ",").replace(" - ", ", ").replace("—", ",")
    return re.sub(r"\s+", " ", t).strip()


def run(u: dict, q: dict, force: bool = False) -> dict:
    name, why = provider()
    if name == "none":
        return {"status": "blocked", "reason": why}
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    sc = scriptmod.render(scriptmod.parse((d / "script.md").read_text(encoding="utf-8")), facts)
    (d / "audio").mkdir(exist_ok=True)
    (d / "alignment").mkdir(exist_ok=True)
    done = []
    for i, b in enumerate(sc["beats"], start=1):
        text = speakable(b["VO"])
        if not text:
            continue
        ext = "mp3" if name == "founder" else "wav"
        audio = d / "audio" / f"vo-{i:02d}.{ext}"
        meta = d / "alignment" / f"vo-{i:02d}.json"
        if audio.exists() and meta.exists() and not force:
            done.append(i); continue
        words = _eleven(text, audio) if name == "founder" else _placeholder(text, audio)
        meta.write_text(json.dumps({"beat": i, "name": b["name"], "text": text, "provider": name, "words": words},
                                   indent=None, ensure_ascii=False) + "\n", encoding="utf-8")
        if name == "founder":   # keep every take; a consistent library is part of the series feel
            takes = d / "audio" / "takes"; takes.mkdir(exist_ok=True)
            n = len(list(takes.glob(f"vo-{i:02d}-*.mp3"))) + 1
            (takes / f"vo-{i:02d}-{n:02d}.mp3").write_bytes(audio.read_bytes())
        done.append(i)
    u["voice"] = name
    if name != "founder":
        u["publishable"] = False
    return {"status": "ok", "voice": name, "beats": len(done), "why": why}
