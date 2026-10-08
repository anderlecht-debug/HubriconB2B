"""Sound design, the layer a first attempt always forgets (bible §4).

Five layers, all built in numpy from the timeline and rendered once through
ffmpeg for the loudness pass: narration with a light compressor and a tiny
room; room tone under everything; a soft tick where each data point lands; a
low whoosh on chapter cuts; and a music bed ducked under the voice. The tick,
whoosh and bed come from the sound library (sfx.py: made with ElevenLabs during
the paid subscription, licensed for commercial use; new sounds only from Freesound
CC0 or Pixabay); a missing one is synthesised here, and the style lock records
which was used.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from . import script as scriptmod
from . import shots as shots_mod
from . import sound
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
    return np.frombuffer(res.stdout, dtype=np.float32).copy()   # writable


def _smooth(x: np.ndarray, k: int) -> np.ndarray:
    """np.convolve(x, ones(k)/k, "same") by a running sum (O(n), accumulated in double), returned as
    float32: a 30-minute film mixes in seconds, without index arrays the size of the film."""
    from scipy.ndimage import uniform_filter1d
    return uniform_filter1d(np.asarray(x, dtype=np.float32), size=max(1, int(k)), mode="constant", output=np.float32)


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
    air = _smooth(rng.normal(0, 1, n), 400) * 0.15
    return ((tone * lfo + air) / 2.2).astype(np.float32)


def _room(seconds: float, rng) -> np.ndarray:
    n = int(SR * seconds)
    brown = np.cumsum(rng.standard_normal(n, dtype=np.float32), dtype=np.float64)
    brown -= _smooth(brown, 2000)
    brown /= np.abs(brown).max() + 1e-9
    return brown.astype(np.float32)


def _reverb(x: np.ndarray, rng) -> np.ndarray:
    n = int(SR * 0.11)
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / (SR * 0.03))
    ir[0] = 1.0
    ir /= np.abs(ir).sum() / 1.15
    from scipy.signal import oaconvolve
    wet = oaconvolve(x, ir.astype(np.float32), mode="full")[: len(x)]
    return (0.88 * x + 0.12 * wet).astype(np.float32)


def _place(track: np.ndarray, clip: np.ndarray, at: float, gain: float) -> None:
    i = int(at * SR)
    j = min(len(track), i + len(clip))
    if i < len(track):
        track[i:j] += clip[: j - i] * gain


AMBIENCE_DB = -40.0       # VISUAL_SPEC.md §9, under footage; an observational hold up to -36
AMBIENCE_OBSERVE_DB = -36.0
AMBIENCE_FADE = 0.4
AMBIENCE_LEAD, AMBIENCE_TAIL = 0.5, 0.35   # the J-cut and the L-cut: a place is heard before it is seen

# A long film's score (VISUAL_SPEC.md §9, with the 2026-10-06 additions): the shot plan, not
# events.json, says where each figure lands, where the picture changes room and where a
# thesis line stands alone.
SUB_DB = -24.0            # a low hit under a hero figure, felt more than heard
ROOM_WHOOSH_DB = -32.0    # where the picture moves between paper and the world
RISER_DB = -30.0          # a short rise into each chapter card
CARD_SWELL_DB = 8.0       # the bed comes up while the card holds (no voice there)
# A long film's bed is levelled by its average (RMS), not its peaks: a sparse piano cue's peaks sit
# some 15–20 dB above its body, so peak-levelled at −32 dB and ducked −20 it measured 35 dB under the
# voice, which is no music at all (G01 draft, 2026-10-06). Levelled by RMS and ducked 10 dB, it sits
# about 25 dB under the voice and comes up to −24 dB under a chapter card: felt, never in the way.
BED_DUCK_DB_D = -10.0
HERO = {"number-land", "number-pair", "counterfactual", "callback", "range-band", "unit-grid"}
# The bed family (§9): one licensed cue, a different passage and key per chapter, so a
# 30-minute film never hears the same two minutes looped.
FAMILY = [(0.0, 1.0), (0.37, 0.944), (0.71, 0.891), (0.18, 0.944), (0.55, 1.0), (0.86, 0.891)]
FAMILY_XFADE = 2.5


def _sub(rng) -> np.ndarray:
    """A short low hit: a sine falling from 62 to 38 Hz, with a soft transient."""
    n = int(SR * 0.75)
    t = np.arange(n) / SR
    f = 38 + 24 * np.exp(-t * 7)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5.5)
    click = np.convolve(rng.normal(0, 1, n), np.ones(60) / 60, mode="same") * np.exp(-t * 60) * 0.25
    x = body + click
    return x / (np.abs(x).max() + 1e-9)


FOLEY_DB = -30.0          # a page or print landing on the desk
SUBDROP_DB = -24.0        # under a chapter card
FOLEY_LEAD = 0.1          # sound leads picture by three frames (a J-cut), so the cut is heard first
PAPER_KINDS = {"document", "table", "receipt", "archive", "stack", "split"}


def _paper(rng) -> np.ndarray:
    """A sheet or print sliding onto the desk: a short band of air, 0.35 s, its body around 1–4 kHz."""
    n = int(SR * 0.35)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    body = _smooth(noise, 6) - _smooth(noise, 48)              # a crude band-pass: no low rumble, no hiss
    env = (1 - np.exp(-t * 60)) * np.exp(-t * 9)
    x = body * env
    return x / (np.abs(x).max() + 1e-9)


def _subdrop(rng) -> np.ndarray:
    """A low fall under a chapter card: a sine from 80 to 35 Hz over 0.9 s."""
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    f = 35 + 45 * np.exp(-t * 4)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2) * (1 - np.exp(-t * 80))
    return x / (np.abs(x).max() + 1e-9)


def _riser(rng, seconds: float = 1.8) -> np.ndarray:
    """Air that brightens and grows into a cut: noise through a one-pole low-pass opening 250 Hz → 5 kHz."""
    n = int(SR * seconds)
    noise = rng.normal(0, 1, n)
    cut = 250 * (20 ** (np.arange(n) / n))
    a = np.exp(-2 * np.pi * cut / SR)
    out, y = np.empty(n), 0.0
    for i in range(n):
        y = a[i] * y + (1 - a[i]) * noise[i]
        out[i] = y
    env = (np.arange(n) / n) ** 2.2
    x = out * env
    return x / (np.abs(x).max() + 1e-9)


def _family(bed: np.ndarray, n: int, bounds: list[float]) -> np.ndarray:
    """The bed as a family of cues, one per chapter, crossfading over FAMILY_XFADE at each boundary.
    `bed` is the cue itself (minutes), not the cue tiled to the film's length."""
    out = np.zeros(n, dtype=np.float32)
    k = int(FAMILY_XFADE * SR)
    edges = [0.0] + [b for b in bounds if 0 < b * SR < n] + [n / SR]
    for i, (a, b) in enumerate(zip(edges, edges[1:])):
        offset, ratio = FAMILY[i % len(FAMILY)]
        # a lower key by resampling (slower and darker, as a family member should be)
        src = np.interp(np.arange(0, len(bed), ratio), np.arange(len(bed)), bed).astype(np.float32)
        src = np.roll(src, -int(offset * len(src)))
        i0, i1 = max(0, int(a * SR) - k // 2), min(n, int(b * SR) + k // 2)
        cue = np.tile(src, int(np.ceil((i1 - i0) / len(src))) + 1)[: i1 - i0]
        fade = np.ones(i1 - i0, dtype=np.float32)
        if i0 > 0:
            fade[:k] = np.linspace(0, 1, k)
        if i1 < n:
            fade[-k:] = np.linspace(1, 0, k)
        out[i0:i1] += cue * fade
    return out


def score_events(plan: dict, timing: dict) -> dict:
    """Where a long film's score acts, from its shot plan: a tick on every figure as it lands, a
    low hit under each hero figure, a soft whoosh where the room changes (not at chapter cards,
    which keep their own), a riser into each card, and the bed's drop before each thesis line."""
    shots = plan.get("shots", [])
    cards = [(float(c["start"]), float(c["end"])) for c in timing["segments"] if c["kind"] == "card"]
    ticks, subs, rooms, drops = [], [], [], []
    for s in shots:
        if s.get("room") == "paper":
            for r in s.get("reveals", []):
                t = float(r["t"])
                if not ticks or t - ticks[-1] > 0.25:
                    ticks.append(t)
            if s.get("style") in HERO and s.get("reveals"):
                on = str(s.get("on") or "")
                hit = next((float(r["t"]) for r in s["reveals"] if f"{{{{{r['key']}}}}}" == on), float(s["reveals"][-1]["t"]))
                subs.append(hit)
        if s.get("style") == "kinetic-thesis":
            drops.append(float(s["start"]))
    near_card = lambda t: any(abs(t - a) < 0.5 or abs(t - b) < 0.5 for a, b in cards)
    for a, b in zip(shots, shots[1:]):
        if a.get("room") != b.get("room") and not near_card(float(b["start"])):
            rooms.append(float(b["start"]))
    return {"ticks": ticks, "subs": subs, "rooms": rooms, "drops": drops,
            "risers": [a for a, _ in cards], "cards": cards,
            "paper": [float(s["start"]) for s in shots if s.get("kind") in PAPER_KINDS and s.get("room") == "paper"]}


def _ambience(d: Path, n: int) -> tuple[np.ndarray, list[str]]:
    """Each footage shot's own place sound, faded in and out over 0.4 s at its cuts."""
    track = np.zeros(n, dtype=np.float32)
    plan_p = d / "shots.json"
    if not plan_p.exists():
        return track, []
    from . import sfx
    used = []
    for s in json.loads(plan_p.read_text(encoding="utf-8")).get("shots", []):
        if s.get("room") != "world" or s.get("kind") != "footage" or not s.get("query"):
            continue
        subject = (s.get("params") or {}).get("ambience") or sfx.subject_of(s["query"][0])
        f = sfx.ambience(subject)
        if f is None:
            continue
        clip = _decode(f)
        peak = np.abs(clip).max()
        if peak <= 0:
            continue
        a, b = float(s["start"]), float(s["end"])
        length = int((b - a + AMBIENCE_LEAD + AMBIENCE_TAIL) * SR)
        clip = np.tile(clip / peak, int(np.ceil(length / len(clip))))[:length]
        fade = np.ones(length)
        ki, ko = int(AMBIENCE_LEAD * SR), int(AMBIENCE_TAIL * SR)
        fade[:ki] = np.linspace(0, 1, ki)
        fade[-ko:] = np.linspace(1, 0, ko)
        gain = _db(AMBIENCE_OBSERVE_DB if s.get("style") == "footage-observe" else AMBIENCE_DB)
        _place(track, clip * fade, max(0.0, a - AMBIENCE_LEAD), gain)
        used.append(subject)
    return track, sorted(set(used))


def mix(slug: str) -> Path:
    d = scriptmod.video_dir(slug)
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    events = json.loads((d / "events.json").read_text(encoding="utf-8")) if (d / "events.json").exists() else []
    plan_p = d / "shots.json"
    plan = json.loads(plan_p.read_text(encoding="utf-8")) if plan_p.exists() else None
    tail = shots_mod.end_tail(plan) if plan else 0.0
    total = timing["duration"] + tail + 0.5
    n = int(total * SR)
    rng = np.random.default_rng(7)
    (d / "media").mkdir(exist_ok=True)

    vo = np.zeros(n, dtype=np.float32)   # float32 throughout: 24 bits is 144 dB of range, and half the memory
    for seg in timing["segments"]:
        if seg["kind"] != "beat":
            continue
        clip = _decode(d / seg["audio"])
        _place(vo, clip, seg["vo_start"], 1.0)
    vo = sound.breath_gate(vo, [w for seg in timing["segments"] if seg["kind"] == "beat" for w in seg.get("words", [])])
    if not (d / "takes").exists():      # the placeholder is dry; a real voice keeps its own room, none added
        vo = _reverb(vo, rng)
    # the voice chain (sound.VOICE_CHAIN) before the loudness pass
    vo_path = d / "media" / "vo.wav"
    sf.write(str(vo_path), vo.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vo_path), "-af",
                    sound.VOICE_CHAIN,
                    "-ar", str(SR), str(d / "media" / "vo-proc.wav")], check=True, timeout=600)
    vo = _decode(d / "media" / "vo-proc.wav")
    vo = np.pad(vo, (0, max(0, n - len(vo))))[:n]

    # envelope of the voice, for ducking
    win = int(SR * 0.05)
    env = _smooth(np.abs(vo), win)
    speaking = _smooth(env > 0.01, int(SR * 0.35))
    del env
    speaking = np.clip(speaking * 1.5, 0, 1)

    bed_file = next(iter(sorted(list(ASSETS.glob("music/*.wav")) + list(ASSETS.glob("music/*.mp3")))), None)
    if bed_file:
        cue = _decode(bed_file)
        bed = np.tile(cue, int(np.ceil(n / max(1, len(cue)))))[:n]
        bed_source = bed_file.name
    else:
        bed = cue = _bed(total, rng)[:n]
        bed_source = "procedural drone (provisional)"
    score = score_events(plan, timing) if plan else None
    if score:
        th = sound.thin({"tick": score["ticks"], "sub": score["subs"], "room": score["rooms"], "paper": score["paper"],
                         "riser": score["risers"]})
        score.update({"ticks": th["tick"], "subs": th["sub"], "rooms": th["room"], "paper": th["paper"]})
    if score:
        del bed
        bed = _family(cue, n, [float(c["at"]) for c in timing["chapters"]])
        bed_source += f" · a family of {len(timing['chapters']) + 1} cues"
    if score:
        bed = bed / (np.sqrt(np.mean(bed ** 2)) + 1e-9)
        bed = sound.carve(bed, speaking)          # under speech: the voice's band cut hard, the rest a little
        bed_gain = np.full(n, _db(BED_DB), dtype=np.float32)
    else:
        bed = bed / (np.abs(bed).max() + 1e-9)
        bed_gain = _db(BED_DB) * (1 - speaking * (1 - _db(BED_DUCK_DB)))
    if score:
        lift = np.ones(n, dtype=np.float32)
        for a, b in score["cards"]:      # the card holds with no voice: the bed comes up
            i0, i1, r = int(a * SR), int(b * SR), int(0.4 * SR)
            ramp = np.ones(max(0, i1 - i0)) * _db(CARD_SWELL_DB)
            if len(ramp) > 2 * r:
                ramp[:r] = np.linspace(1, _db(CARD_SWELL_DB), r)
                ramp[-r:] = np.linspace(_db(CARD_SWELL_DB), 1, r)
            lift[i0:i1] = ramp[: max(0, min(n, i1) - i0)]
        for t in score["drops"]:         # silence under the thesis line's first words, then back
            i0, i1 = int(max(0.0, t - 0.35) * SR), int((t + 0.05) * SR)   # 0.4 s: a breath, not a hole
            back = int(1.5 * SR)
            lift[i0:i1] = 0.0
            lift[i1:i1 + back] = np.linspace(0, 1, len(lift[i1:i1 + back]))
        if tail:   # the end card holds with no voice: the bed comes up, then fades out to the film's last frame
            i0, r = int(float(timing["duration"]) * SR), int(0.6 * SR)
            hold = np.ones(max(0, n - i0)) * _db(CARD_SWELL_DB)
            hold[: min(r, len(hold))] = np.linspace(1, _db(CARD_SWELL_DB), len(hold[:r]))
            lift[i0:] = hold
        bed_gain *= lift
        del lift
        bed_gain *= sound.predips(n, score["subs"])
    room = _room(total, rng)[:n]
    if score:   # a long film's room tone is levelled by its body, like the bed: the floor never falls to silence
        room = room / (np.sqrt(np.mean(room ** 2)) + 1e-9)
    room *= np.float32(_db(ROOM_TONE_DB))

    fx = np.zeros(n, dtype=np.float32)
    fx_side = np.zeros(n, dtype=np.float32)   # panned effects (sound.py: mid/side)
    tick_file, whoosh_file = ASSETS / "sfx" / "tick.mp3", ASSETS / "sfx" / "whoosh.mp3"
    tick = _decode(tick_file) if tick_file.exists() else _tick(rng)
    whoosh = _decode(whoosh_file) if whoosh_file.exists() else _whoosh(rng)
    for clip in (tick, whoosh):
        peak = np.abs(clip).max()
        if peak > 0:
            clip /= peak
    sfx_source = "sound library (ElevenLabs, paid-subscription licence)" if tick_file.exists() and whoosh_file.exists() else "procedural (provisional)"
    for e in events:
        if e.get("kind") == "data":
            _place(fx, tick, float(e["t"]), _db(TICK_DB))
    for ch in timing["chapters"]:
        _place(fx, whoosh, max(0.0, float(ch["at"]) - 0.08), _db(WHOOSH_DB))
    if score:
        sub, riser = _sub(rng), _riser(rng)
        for k, t in enumerate(score["ticks"]):
            c, g = sound.vary(tick, rng)
            _place(fx, c, t, _db(TICK_DB) * g)
            _place(fx_side, c, t, _db(TICK_DB) * g * (sound.PAN_TICK if k % 2 else -sound.PAN_TICK))
        for t in score["subs"]:
            _place(fx, sub, max(0.0, t - 0.02), _db(SUB_DB))
        for t in score["rooms"]:
            _place(fx, whoosh, max(0.0, t - 0.15), _db(ROOM_WHOOSH_DB))
        for t in score["risers"]:
            _place(fx, riser, max(0.0, t - len(riser) / SR), _db(RISER_DB))
        paper, sub_drop = _paper(rng), _subdrop(rng)
        for t in score["paper"]:
            c, g = sound.vary(paper, rng)
            _place(fx, c, max(0.0, t - FOLEY_LEAD), _db(FOLEY_DB) * g)
            _place(fx_side, c, max(0.0, t - FOLEY_LEAD), _db(FOLEY_DB) * g * rng.uniform(-sound.PAN_PAPER, sound.PAN_PAPER))
        for t in score["risers"]:
            _place(fx, sub_drop, max(0.0, t - FOLEY_LEAD), _db(SUBDROP_DB))

    amb, amb_subjects = _ambience(d, n)
    music = bed * bed_gain
    del bed, bed_gain
    mid = vo + music
    mid += room
    mid += fx
    mid += amb
    # the stereo field (sound.py): the voice centre, the music, the place and the room around it
    side = sound.widen(music, sound.WIDTH_BED) + sound.widen(amb, sound.WIDTH_AMB) + sound.widen(room, sound.WIDTH_ROOM) + fx_side
    out = np.stack([mid + side, mid - side], axis=1)
    side_db = sound.side_under_mid_db(mid, side)
    del side
    measured = sound.metrics(vo, music + amb, {k: score[k] for k in ("ticks", "subs", "rooms", "paper", "risers")},
                             speaking, float(timing["duration"])) if score else {}
    if score:
        measured["side_under_mid_db"] = side_db
    if tail:   # everything fades out over the tail's last 2.5 s, to silence on the last frame
        f = int(min(2.5, tail) * SR)
        end = int((float(timing["duration"]) + tail) * SR)
        out[end - f:end] *= (np.linspace(1, 0, f) ** 1.5)[:, None]
        out[end:] = 0.0
    peak = np.abs(out).max()
    if peak > 0.98:
        out = out / peak * 0.98
    raw = d / "media" / "mix-raw.wav"
    sf.write(str(raw), out.astype(np.float32, copy=False), SR)
    final = d / "media" / "mix.wav"
    # the ceiling sits 0.5 dB under the spec's -1.5 dBTP: the AAC encode adds about 0.3 dB of
    # inter-sample peak (G01's draft measured -1.2 from a -1.5 mix)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-16:TP=-2.0:LRA=11", "-ar", str(SR), str(final)], check=True, timeout=600)
    (d / "media" / "mix.json").write_text(json.dumps({
        "sample_rate": SR, "room_tone_db": ROOM_TONE_DB, "bed_db": BED_DB, "bed_duck_db": BED_DUCK_DB,
        "tick_db": TICK_DB, "whoosh_db": WHOOSH_DB, "bed_source": bed_source, "sfx_source": sfx_source,
        "ticks": sum(1 for e in events if e.get("kind") == "data"),
        "whooshes": len(timing["chapters"]), "target_lufs": -16, "ambience": amb_subjects,
        **({"score": {k: len(v) for k, v in score.items() if k != "cards"}, "sub_db": SUB_DB, "room_whoosh_db": ROOM_WHOOSH_DB,
            "riser_db": RISER_DB, "card_swell_db": CARD_SWELL_DB, "bed_levelled_by": "rms",
            "bed_duck_db_long_film": BED_DUCK_DB_D, "carve_db": [sound.CARVE_MID_DB, sound.CARVE_REST_DB],
            "measured": measured} if score else {})}, indent=1) + "\n", encoding="utf-8")
    return final
