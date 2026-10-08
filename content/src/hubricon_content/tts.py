"""Narration, one beat at a time, with word timing.

Every film is narrated in the founder's own recorded voice (the founder's call,
2026-10-06: no ElevenLabs, no clone). He reads each beat at the teleprompter
(`content/film/record.mjs`), which keeps one take per beat as takes/b<N>.wav;
`takes_to_vo` copies them to audio/vo-NN.wav and times the script's own words on
faster-whisper, run on this PC, so subtitles and reveals follow his reading.

The only other voice is Kokoro, an offline open-weights placeholder aligned the
same way. It exists so the chain can be proven before his takes exist, renders
only when asked for (CONTENT_ALLOW_PLACEHOLDER=1), and never publishes.
"""

import json
import os
import re
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

# The placeholder voice exists to prove the chain, not to be heard. It renders only
# when asked for explicitly, so a founder never reviews a video in a voice that
# is not his.
ALLOW_PLACEHOLDER = os.environ.get("CONTENT_ALLOW_PLACEHOLDER") == "1"
KOKORO_DIR = CONTENT_DIR / ".cache" / "kokoro"
KOKORO_VOICE = "am_michael"
WHISPER_MODEL = os.environ.get("CONTENT_WHISPER_MODEL", "small")


def _cuda_ready() -> bool:
    """Load the CUDA libraries the `voice` extra installs (nvidia-cublas-cu12,
    nvidia-cudnn-cu12) so faster-whisper finds them on the GPU; the system has
    none of its own. False when they or the GPU are missing."""
    import ctypes
    import glob
    try:
        import ctranslate2
        import nvidia
        base = Path(nvidia.__path__[0])
        for pat in ("cublas/lib/libcublasLt.so.*", "cublas/lib/libcublas.so.*", "cudnn/lib/libcudnn*.so.*"):
            for f in sorted(glob.glob(str(base / pat))):
                ctypes.CDLL(f, mode=ctypes.RTLD_GLOBAL)
        return ctranslate2.get_cuda_device_count() > 0
    except (ImportError, OSError, AttributeError):
        return False


WHISPER_DEVICE = os.environ.get("CONTENT_WHISPER_DEVICE")   # unset: the GPU when _cuda_ready(), else the CPU
WORD_RE = re.compile(r"[A-Za-z0-9$%'’.,-]+")


def _beat_texts(slug: str) -> tuple[list[str], list[dict]]:
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    sc = scriptmod.render(scriptmod.parse((d / "script.md").read_text(encoding="utf-8")), facts)
    return [speakable(b["VO"]) for b in sc["beats"]], sc["beats"]


def missing_takes(slug: str) -> list[str]:
    """The beats the founder has not read yet (takes/b<N>.wav), in order."""
    d = scriptmod.video_dir(slug)
    texts, _ = _beat_texts(slug)
    return [f"b{i}" for i, t in enumerate(texts, start=1) if t and not (d / "takes" / f"b{i}.wav").exists()]


def provider(slug: str | None = None) -> tuple[str, str]:
    """(name, reason): "own" when every beat has his take, "placeholder" when the offline
    proof voice is asked for, else "none" with what to record."""
    if slug and not missing_takes(slug):
        return "own", "the founder's own recorded takes"
    if ALLOW_PLACEHOLDER and (KOKORO_DIR / "kokoro-v1.0.onnx").exists() and (KOKORO_DIR / "voices-v1.0.bin").exists():
        return "placeholder", "Kokoro offline placeholder; never ships"
    what = f"`node content/film/record.mjs {slug}`" if slug else "`node content/film/record.mjs <slug>`"
    return "none", (f"the founder's own takes: read the script at the teleprompter, {what} "
                    "(docs/content/VOICE-RECORDING.md)")


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
        dev = device or WHISPER_DEVICE or ("cuda" if _cuda_ready() else "cpu")
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
    """The narration step: the founder's takes when every beat is read, else the
    opt-in placeholder, else blocked on his reading."""
    slug = u["slug"]
    name, why = provider(slug)
    if name == "own":
        return takes_to_vo(u, q, force=force)
    if name == "none":
        return {"status": "blocked", "reason": why}
    d = scriptmod.video_dir(slug)
    texts, beats = _beat_texts(slug)
    (d / "audio").mkdir(exist_ok=True)
    (d / "alignment").mkdir(exist_ok=True)
    done = []
    for i, b in enumerate(beats, start=1):
        text = texts[i - 1]
        if not text:
            continue
        audio, meta = d / "audio" / f"vo-{i:02d}.wav", d / "alignment" / f"vo-{i:02d}.json"
        if audio.exists() and meta.exists() and not force:
            done.append(i); continue
        words = _placeholder(text, audio)
        meta.write_text(json.dumps({"beat": i, "name": b["name"], "text": text, "provider": name, "words": words},
                                   indent=None, ensure_ascii=False) + "\n", encoding="utf-8")
        done.append(i)
    u["voice"] = name
    u["publishable"] = False
    return {"status": "ok", "voice": name, "beats": len(done), "why": why}


def takes_to_vo(u: dict, q: dict, force: bool = False) -> dict:
    """The founder's own reading, as the film's narration.

    `record.mjs` keeps one take per beat as takes/b<N>.wav; each becomes
    audio/vo-NN.wav with alignment/vo-NN.json (the script's own words on
    faster-whisper's timing), so everything after `tts` is one path whichever
    voice reads (VISUAL_SPEC.md §7.2). Takes are copied, never altered."""
    import shutil
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    sc = scriptmod.render(scriptmod.parse((d / "script.md").read_text(encoding="utf-8")), facts)
    texts = [speakable(b["VO"]) for b in sc["beats"]]
    wanted = [i for i, t in enumerate(texts, start=1) if t]
    missing = [f"b{i}" for i in wanted if not (d / "takes" / f"b{i}.wav").exists()]
    if missing:
        return {"status": "blocked", "reason": f"no take for {', '.join(missing)}: read them with "
                                               f"`node content/film/record.mjs {slug}`"}
    (d / "audio").mkdir(exist_ok=True)
    (d / "alignment").mkdir(exist_ok=True)
    for i in wanted:
        take, audio = d / "takes" / f"b{i}.wav", d / "audio" / f"vo-{i:02d}.wav"
        meta = d / "alignment" / f"vo-{i:02d}.json"
        if audio.exists() and meta.exists() and not force and json.loads(meta.read_text(encoding="utf-8")).get("provider") == "own":
            continue
        for other in (d / "audio").glob(f"vo-{i:02d}.*"):   # an earlier read of this beat (placeholder, or mp3) steps aside
            if other.suffix != ".wav":
                other.unlink()
        shutil.copyfile(take, audio)
        words = snap_words(texts[i - 1], align(audio))
        meta.write_text(json.dumps({"beat": i, "name": sc["beats"][i - 1]["name"], "text": texts[i - 1], "provider": "own",
                                    "words": words}, ensure_ascii=False) + "\n", encoding="utf-8")
    u["voice"] = "own"
    u["publishable"] = False   # set again only by approve-final
    return {"status": "ok", "voice": "own", "beats": len(wanted)}
