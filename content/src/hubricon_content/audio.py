"""Sound design, the layer a first attempt always forgets (bible §4).

Five layers, all built in numpy from the timeline and rendered once through
ffmpeg for the loudness pass: narration with a light compressor and a tiny
room; room tone under everything; a soft tick where each data point lands; a
low whoosh on chapter cuts; and a music bed ducked under the voice. The tick,
whoosh and bed are synthesised here until a licensed bed or ElevenLabs sound
effects exist, and the style lock records which was used.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from . import script as scriptmod
from .state import CONTENT_DIR

SR = 48000
ROOM_TONE_DB = -48.0
BED_DB = -32.0          # bed level in the gaps
BED_DUCK_DB = -20.0     # additional reduction under narration
TICK_DB = -26.0
WHOOSH_DB = -22.0
ASSETS = CONTENT_DIR / "assets"


def _db(v: float) -> float:
    return 10 ** (v / 20)


def _decode(path: Path) -> np.ndarray:
    """Any audio → float32 mono at SR, via ffmpeg."""
    res = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, timeout=300, check=True)
    return np.frombuffer(res.stdout, dtype=np.float32)


def _tick(rng) -> np.ndarray:
    n = int(SR * 0.055)
    t = np.arange(n) / SR
    env = np.exp(-t * 90)
    return (np.sin(2 * np.pi * 1720 * t) * 0.7 + np.sin(2 * np.pi * 2580 * t) * 0.3) * env


def _whoosh(rng) -> np.ndarray:
    n = int(SR * 0.42)
    noise = rng.normal(0, 1, n)
    # band-limited by a moving average, swept by a rising envelope
    k = 24
    noise = np.convolve(noise, np.ones(k) / k, mode="same")
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 2 * (0.4 + 0.6 * t)
    return noise / (np.abs(noise).max() + 1e-9) * env


def _bed(seconds: float, rng) -> np.ndarray:
    """A slow two-note drone with a breathing LFO; deliberately featureless."""
    n = int(SR * seconds)
    t = np.arange(n) / SR
    f0 = 55.0
    tone = (np.sin(2 * np.pi * f0 * t) + 0.5 * np.sin(2 * np.pi * f0 * 1.498 * t + 0.3) +
            0.35 * np.sin(2 * np.pi * f0 * 2.01 * t) + 0.2 * np.sin(2 * np.pi * f0 * 3.0 * t))
    lfo = 0.65 + 0.35 * np.sin(2 * np.pi * t / 23.0)
    air = np.convolve(rng.normal(0, 1, n), np.ones(400) / 400, mode="same") * 0.15
    return (tone * lfo + air) / 2.2


def _room(seconds: float, rng) -> np.ndarray:
    n = int(SR * seconds)
    brown = np.cumsum(rng.normal(0, 1, n))
    brown -= np.convolve(brown, np.ones(2000) / 2000, mode="same")
    return brown / (np.abs(brown).max() + 1e-9)


def _reverb(x: np.ndarray, rng) -> np.ndarray:
    n = int(SR * 0.11)
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / (SR * 0.03))
    ir[0] = 1.0
    ir /= np.abs(ir).sum() / 1.15
    wet = np.convolve(x, ir, mode="full")[: len(x)]
    return 0.88 * x + 0.12 * wet


def _place(track: np.ndarray, clip: np.ndarray, at: float, gain: float) -> None:
    i = int(at * SR)
    j = min(len(track), i + len(clip))
    if i < len(track):
        track[i:j] += clip[: j - i] * gain


def mix(slug: str) -> Path:
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    events = json.loads((d / "events.json").read_text(encoding="utf-8")) if (d / "events.json").exists() else []
    total = timing["duration"] + 0.5
    n = int(total * SR)
    rng = np.random.default_rng(7)
    (d / "media").mkdir(exist_ok=True)

    vo = np.zeros(n, dtype=np.float64)
    for seg in timing["segments"]:
        if seg["kind"] != "beat":
            continue
        clip = _decode(d / seg["audio"]).astype(np.float64)
        _place(vo, clip, seg["vo_start"], 1.0)
    vo = _reverb(vo, rng)
    # compress the narration lightly before it goes to the loudness pass
    vo_path = d / "media" / "vo.wav"
    sf.write(str(vo_path), vo.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vo_path), "-af",
                    "acompressor=threshold=-18dB:ratio=2.5:attack=8:release=120:makeup=3,highpass=f=70",
                    "-ar", str(SR), str(d / "media" / "vo-proc.wav")], check=True, timeout=600)
    vo = _decode(d / "media" / "vo-proc.wav").astype(np.float64)
    vo = np.pad(vo, (0, max(0, n - len(vo))))[:n]

    # envelope of the voice, for ducking
    win = int(SR * 0.05)
    env = np.convolve(np.abs(vo), np.ones(win) / win, mode="same")
    speaking = np.convolve((env > 0.01).astype(float), np.ones(int(SR * 0.35)) / int(SR * 0.35), mode="same")
    speaking = np.clip(speaking * 1.5, 0, 1)

    bed_file = next(iter(sorted(list(ASSETS.glob("music/*.wav")) + list(ASSETS.glob("music/*.mp3")))), None)
    if bed_file:
        bed = _decode(bed_file).astype(np.float64)
        bed = np.tile(bed, int(np.ceil(n / max(1, len(bed)))))[:n]
        bed_source = bed_file.name
    else:
        bed = _bed(total, rng)[:n]
        bed_source = "procedural drone (provisional)"
    bed = bed / (np.abs(bed).max() + 1e-9)
    bed_gain = _db(BED_DB) * (1 - speaking * (1 - _db(BED_DUCK_DB)))
    room = _room(total, rng)[:n] * _db(ROOM_TONE_DB)

    fx = np.zeros(n)
    tick_file, whoosh_file = ASSETS / "sfx" / "tick.mp3", ASSETS / "sfx" / "whoosh.mp3"
    tick = _decode(tick_file).astype(np.float64) if tick_file.exists() else _tick(rng)
    whoosh = _decode(whoosh_file).astype(np.float64) if whoosh_file.exists() else _whoosh(rng)
    for clip in (tick, whoosh):
        peak = np.abs(clip).max()
        if peak > 0:
            clip /= peak
    sfx_source = "elevenlabs sound-generation" if tick_file.exists() and whoosh_file.exists() else "procedural (provisional)"
    for e in events:
        if e.get("kind") == "data":
            _place(fx, tick, float(e["t"]), _db(TICK_DB))
    for ch in timing["chapters"]:
        _place(fx, whoosh, max(0.0, float(ch["at"]) - 0.08), _db(WHOOSH_DB))

    out = vo + bed * bed_gain + room + fx
    peak = np.abs(out).max()
    if peak > 0.98:
        out = out / peak * 0.98
    raw = d / "media" / "mix-raw.wav"
    sf.write(str(raw), out.astype(np.float32), SR)
    final = d / "media" / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), str(final)], check=True, timeout=600)
    (d / "media" / "mix.json").write_text(json.dumps({
        "sample_rate": SR, "room_tone_db": ROOM_TONE_DB, "bed_db": BED_DB, "bed_duck_db": BED_DUCK_DB,
        "tick_db": TICK_DB, "whoosh_db": WHOOSH_DB, "bed_source": bed_source, "sfx_source": sfx_source,
        "ticks": sum(1 for e in events if e.get("kind") == "data"),
        "whooshes": len(timing["chapters"]), "target_lufs": -16}, indent=1) + "\n", encoding="utf-8")
    return final
