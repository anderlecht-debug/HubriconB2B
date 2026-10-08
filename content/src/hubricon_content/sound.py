"""The sound design rules of a long film, as code (docs/content/SOUND_DESIGN.md). audio.mix calls
these; each rule names the practice it comes from and the number it holds to.

- Voice first (Walter Murch: dialogue is the spine). The narration gets a full chain. Breaths and
  mouth noise between words are pulled down. A real voice gets no added room.
- Carve, don't bury. Under speech the music loses the band the voice lives in (250 Hz–5 kHz)
  hard, and its lows and highs only a little, so it stays full and the words stay clear.
- Contrast before impact (Gary Rydstrom: the loudest thing is the silence before it). The bed dips
  for a quarter second before each hero figure lands.
- No machine-gun repetition (Ben Burtt: a sound repeated identically reads as a machine). Every
  tick and paper sound varies slightly in pitch and level.
- Two and a half at once (Murch's Law of Two-and-a-Half). Transient effects that pile up are
  thinned by priority.
- Sound leads picture (the J-cut): see audio._ambience.
- Measure it (the mix's own numbers, read by film-qa): voice over music under speech, effects a
  minute, the longest stretch with nothing designed, loudness range.
"""
from __future__ import annotations

import numpy as np

SR = 48000
CHUNK = SR * 30        # long filters run on 30 s at a time: double precision without a film-length double copy

# Murch's voice: rumble cut, gentle noise reduction, de-ess, mud cut, presence, air, a leveling
# compressor then a peak one, a limiter. Values are gentle on purpose: a chain is heard when it's wrong.
VOICE_CHAIN = ",".join([
    "highpass=f=80",
    "afftdn=nr=10:nf=-40:tn=1",
    "deesser=i=0.35:m=0.5:f=0.5",
    "equalizer=f=300:t=q:w=1.1:g=-2.5",
    "equalizer=f=4200:t=q:w=1.0:g=2",
    "highshelf=f=10000:g=1.5",
    "acompressor=threshold=-24dB:ratio=3:attack=6:release=90:makeup=4",
    "acompressor=threshold=-9dB:ratio=6:attack=1:release=40",
    "alimiter=limit=0.95:level=disabled",
])

BREATH_DB = -9.0          # a breath or a lip noise between words, pulled down, never cut to silence
BREATH_MIN_GAP = 0.18     # gaps shorter than this are the voice itself
VOICE_BAND = (250.0, 5000.0)
CARVE_MID_DB = -12.0      # the voice's band of the music, under speech
CARVE_REST_DB = -4.0      # the music's lows and highs, under speech
PREDIP_DB = -7.0          # the bed just before a hero figure lands
PREDIP_S, RECOVER_S = 0.25, 0.6
VARY_SEMITONES, VARY_DB = 1.2, 2.0
MIN_GAP_S = 0.35          # two transient effects closer than this are one too many
PRIORITY = {"riser": 5, "sub": 4, "tick": 3, "room": 2, "paper": 1}


def breath_gate(vo: np.ndarray, words: list[dict], offset: float = 0.0) -> np.ndarray:
    """The narration with every gap between words of BREATH_MIN_GAP or more pulled down by BREATH_DB,
    on 20 ms ramps, so a breath stays human and never pumps."""
    g = np.ones(len(vo), dtype=np.float32)
    r = int(0.02 * SR)
    lo = 10 ** (BREATH_DB / 20)
    for a, b in zip(words, words[1:]):
        s, e = float(a["end"]) + offset + 0.03, float(b["start"]) + offset - 0.03
        if e - s < BREATH_MIN_GAP:
            continue
        i, j = int(s * SR), int(e * SR)
        if j - i <= 2 * r or i < 0 or j > len(g):
            continue
        g[i:i + r] = np.minimum(g[i:i + r], np.linspace(1, lo, r))
        g[i + r:j - r] = lo
        g[j - r:j] = np.minimum(g[j - r:j], np.linspace(lo, 1, r))
    return vo * g


def bands(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The voice's band of a track, and the rest of it."""
    from scipy.signal import butter, sosfilt
    sos = butter(4, VOICE_BAND, btype="bandpass", fs=SR, output="sos")
    # one pass (a phase shift in the music is inaudible), filtered in double a chunk at a time, kept as float32
    mid, zi = np.empty(len(x), dtype=np.float32), np.zeros((sos.shape[0], 2))
    for i in range(0, len(x), CHUNK):
        mid[i:i + CHUNK], zi = sosfilt(sos, x[i:i + CHUNK], zi=zi)
    return mid, x - mid


def carve(bed: np.ndarray, speaking: np.ndarray) -> np.ndarray:
    """The music under speech: its voice band cut by CARVE_MID_DB, the rest by CARVE_REST_DB."""
    mid, rest = bands(bed)
    gm = 1 - speaking * (1 - 10 ** (CARVE_MID_DB / 20))
    gr = 1 - speaking * (1 - 10 ** (CARVE_REST_DB / 20))
    return mid * gm + rest * gr


def predips(n: int, hits: list[float]) -> np.ndarray:
    """A gain curve for the bed: down PREDIP_DB over the PREDIP_S before each hit, back over RECOVER_S."""
    g = np.ones(n, dtype=np.float32)
    lo = 10 ** (PREDIP_DB / 20)
    for t in hits:
        i0, i1, i2 = int(max(0.0, t - PREDIP_S) * SR), int(t * SR), int((t + RECOVER_S) * SR)
        if i1 >= n:
            continue
        g[i0:i1] = np.minimum(g[i0:i1], np.linspace(1, lo, i1 - i0))
        k = min(n, i2) - i1
        g[i1:i1 + k] = np.minimum(g[i1:i1 + k], np.linspace(lo, 1, i2 - i1)[:k])
    return g


def vary(clip: np.ndarray, rng) -> tuple[np.ndarray, float]:
    """One instance of a sound: pitched up to VARY_SEMITONES either way, and a gain within VARY_DB."""
    from scipy.signal import resample
    ratio = 2 ** (rng.uniform(-VARY_SEMITONES, VARY_SEMITONES) / 12)
    out = resample(clip, max(8, int(len(clip) / ratio)))
    return out, 10 ** (rng.uniform(-VARY_DB, VARY_DB) / 20)


def thin(events: dict[str, list[float]]) -> dict[str, list[float]]:
    """Murch's two and a half: of transient effects within MIN_GAP_S of each other, keep the most
    important (riser > sub > tick > room > paper). A sub and a tick on one figure are one designed hit."""
    flat = sorted(((t, k) for k, ts in events.items() for t in ts), key=lambda x: (x[0], -PRIORITY.get(x[1], 0)))
    kept: list[tuple[float, str]] = []
    for t, k in flat:
        clash = [(i, kt) for i, kt in enumerate(kept) if abs(kt[0] - t) < MIN_GAP_S and {kt[1], k} != {"sub", "tick"}]
        if not clash:
            kept.append((t, k))
        elif all(PRIORITY.get(k, 0) > PRIORITY.get(kt[1], 0) for _, kt in clash):
            for i, _ in sorted(clash, reverse=True):
                kept.pop(i)
            kept.append((t, k))
    out: dict[str, list[float]] = {k: [] for k in events}
    for t, k in kept:
        out[k].append(t)
    return out


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)) if len(x) else -120.0


def metrics(vo: np.ndarray, music: np.ndarray, events: dict[str, list[float]], speaking: np.ndarray, seconds: float) -> dict:
    """The mix's own numbers for film-qa."""
    sp = speaking > 0.5
    ratio = _rms_db(vo[sp]) - _rms_db(music[sp]) if sp.any() else None
    ts = sorted(t for k, v in events.items() for t in v)
    gaps = [b - a for a, b in zip([0.0] + ts, ts + [seconds])]
    return {"voice_over_music_db": None if ratio is None else round(ratio, 1),
            "effects_per_minute": round(len(ts) / max(seconds / 60, 1e-9), 1),
            "longest_undesigned_s": round(max(gaps) if gaps else seconds, 1)}


# ── the stereo field: the voice dead centre, the world around it (mid/side, mono-safe) ───────────
# A side signal is the track through a chain of all-pass filters (same spectrum, scattered phase).
# Left = mid + side, right = mid - side, so folded to mono (a phone's speaker) the side cancels
# exactly and the mix is the mono mix: width that costs nothing in mono.
WIDTH_BED, WIDTH_AMB, WIDTH_ROOM = 0.45, 0.6, 0.7
PAN_TICK, PAN_PAPER = 0.15, 0.3
_ALLPASS = (0.62, -0.41, 0.77, -0.23)


def widen(x: np.ndarray, width: float) -> np.ndarray:
    """The side signal for a track: decorrelated by first-order all-passes, scaled by `width`."""
    from scipy.signal import lfilter
    y = np.array(x, dtype=np.float32)
    for a in _ALLPASS:
        zi = np.zeros(1)
        for i in range(0, len(y), CHUNK):
            y[i:i + CHUNK], zi = lfilter([a, 1.0], [1.0, a], y[i:i + CHUNK], zi=zi)
    y *= np.float32(width)
    return y


def side_under_mid_db(mid: np.ndarray, side: np.ndarray) -> float:
    """How far the side sits under the mid: folded to mono, the mix loses 10·log10(1 + side²/mid²) dB."""
    m, s = float(np.dot(mid, mid)), float(np.dot(side, side))
    return round(10 * np.log10(max(m, 1e-12) / max(s, 1e-12)), 1)
