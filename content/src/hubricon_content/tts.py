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
ELEVEN_FORMAT = "mp3_44100_128"


def eleven_settings() -> dict:
    """Narration settings: steady, not flat. Stability under 0.40 wanders; over
    0.55 flattens into a read. Style stays low so the clone never performs."""
    f = lambda k, d: float(os.environ.get(k, d))
    return {"stability": f("ELEVENLABS_STABILITY", 0.45), "similarity_boost": f("ELEVENLABS_SIMILARITY", 0.85),
            "style": f("ELEVENLABS_STYLE", 0.08), "use_speaker_boost": True}


ELEVEN_SETTINGS = eleven_settings()
# The placeholder voice exists to prove the chain, not to be heard. It renders only
# when asked for explicitly, so a founder never reviews a video in a voice that
# is not his.
ALLOW_PLACEHOLDER = os.environ.get("CONTENT_ALLOW_PLACEHOLDER") == "1"
KOKORO_DIR = CONTENT_DIR / ".cache" / "kokoro"
KOKORO_VOICE = "am_michael"
WHISPER_MODEL = os.environ.get("CONTENT_WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("CONTENT_WHISPER_DEVICE", "cpu")   # the box has a GPU but no CUDA runtime libraries
WORD_RE = re.compile(r"[A-Za-z0-9$%'’.,-]+")


def provider() -> tuple[str, str]:
    """(name, reason)."""
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
        return "founder", "ElevenLabs clone of the founder's voice"
    if ALLOW_PLACEHOLDER and (KOKORO_DIR / "kokoro-v1.0.onnx").exists() and (KOKORO_DIR / "voices-v1.0.bin").exists():
        return "placeholder", "Kokoro offline placeholder; never ships"
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "none", ("The founder's voice clone is not configured. Record per docs/content/VOICE-RECORDING.md, run "
                        "`hubricon-content voice-clone --name \"Hagen Simmons\" <wav files>`, and set ELEVENLABS_VOICE_ID in "
                        "/home/lp9/Hubricon/HubriconB2B/.env. Nothing renders in another voice unless CONTENT_ALLOW_PLACEHOLDER=1.")
    return "none", "Narration needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in /home/lp9/Hubricon/HubriconB2B/.env (the founder's clone)."


def _eleven(text: str, out_mp3: Path, previous_text: str | None = None, next_text: str | None = None,
            voice: str | None = None) -> list[dict]:
    """One paragraph, with character timing. previous_text/next_text carry the
    surrounding narration so prosody stays continuous across paragraphs even
    though each is generated on its own (and can be re-rolled alone)."""
    key = os.environ["ELEVENLABS_API_KEY"]
    voice = voice or os.environ["ELEVENLABS_VOICE_ID"]
    body = {"text": text, "model_id": ELEVEN_MODEL, "voice_settings": eleven_settings()}
    if previous_text:
        body["previous_text"] = previous_text[-600:]
    if next_text:
        body["next_text"] = next_text[:600]
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format={ELEVEN_FORMAT}",
        data=json.dumps(body).encode(), headers={"xi-api-key": key, "content-type": "application/json"})
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


def snap_words(text: str, heard: list[dict]) -> list[dict]:
    """The script's own words carrying the transcriber's timing.

    A transcriber spells numbers its own way ("$969 ,579", "10th"), so subtitles
    and reveal lookups must never show its text. Align the script's tokens to the
    heard tokens with a sequence matcher; tokens it did not match take
    interpolated times from their neighbours."""
    import difflib
    said = text.split()
    if not said:
        return heard
    if not heard:
        return [{"word": w, "start": 0.0, "end": 0.0} for w in said]
    norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
    a = [norm(w) for w in said]
    b = [norm(w["word"]) for w in heard]
    times = [None] * len(said)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif tag == "replace" and j2 > j1:
            span = (heard[j1]["start"], heard[j2 - 1]["end"])
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = (span[0] + (span[1] - span[0]) * k / n, span[0] + (span[1] - span[0]) * (k + 1) / n)
    last_end = 0.0
    for i, t in enumerate(times):
        if t is None:
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), heard[-1]["end"])
            times[i] = (last_end, min(nxt, last_end + max(0.05, nxt - last_end) * 0.5))
        last_end = times[i][1]
    return [{"word": w, "start": round(t[0], 3), "end": round(t[1], 3)} for w, t in zip(said, times)]


def _placeholder(text: str, out_wav: Path) -> list[dict]:
    import soundfile as sf
    samples, rate = _kokoro_model().create(text, voice=KOKORO_VOICE, speed=1.0, lang="en-us")
    sf.write(str(out_wav), samples, rate)
    return snap_words(text, align(out_wav))


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
    texts = [speakable(b["VO"]) for b in sc["beats"]]
    for i, b in enumerate(sc["beats"], start=1):
        text = texts[i - 1]
        if not text:
            continue
        ext = "mp3" if name == "founder" else "wav"
        audio = d / "audio" / f"vo-{i:02d}.{ext}"
        meta = d / "alignment" / f"vo-{i:02d}.json"
        if audio.exists() and meta.exists() and not force:
            done.append(i); continue
        prev_text = next((t for t in reversed(texts[: i - 1]) if t), None)
        next_text = next((t for t in texts[i:] if t), None)
        words = _eleven(text, audio, prev_text, next_text) if name == "founder" else _placeholder(text, audio)
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


# ── the founder's voice: clone and preview ─────────────────────────────────

def voice_clone(name: str, files: list[Path], description: str = "") -> str:
    """Instant Voice Clone from the founder's own recordings. Returns the voice id.
    Run only by the founder, on his own audio (docs/content/VOICE-RECORDING.md)."""
    import mimetypes, uuid
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    boundary = f"----hubricon{uuid.uuid4().hex}"
    parts = []
    def field(k, v):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    field("name", name)
    field("description", description or "Hubricon founder narration clone, used with permission")
    field("labels", json.dumps({"use_case": "narration", "owner": "founder"}))
    field("remove_background_noise", "false")
    for f in files:
        f = Path(f)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{f.name}\"\r\nContent-Type: {ctype}\r\n\r\n".encode() + f.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices/add", data=b"".join(parts),
                                 headers={"xi-api-key": key, "content-type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=600) as res:
        return json.loads(res.read())["voice_id"]


def voice_preview(slug: str, text: str | None = None, voice: str | None = None) -> Path:
    """The hook and the first chapter of a parked script in the configured voice,
    so the founder hears the clone with the pipeline's exact settings before
    anything renders."""
    from . import script as scriptmod
    out_dir = CONTENT_DIR / "voice-previews"
    out_dir.mkdir(exist_ok=True)
    if text is None:
        d = scriptmod.video_dir(slug)
        facts = scriptmod.load_facts(slug)
        sc = scriptmod.render(scriptmod.parse((d / "script.md").read_text(encoding="utf-8")), facts)
        chapter = next((b for b in sc["beats"] if b["name"].upper().startswith("CHAPTER")), sc["beats"][min(2, len(sc["beats"]) - 1)])
        text = speakable(sc["hooks"].get(1, "")) + " " + speakable(chapter["VO"])
    label = "founder" if (voice or os.environ.get("ELEVENLABS_VOICE_ID")) else "unset"
    out = out_dir / f"{slug}-{label}.mp3"
    _eleven(text[:4000], out, voice=voice)
    return out
