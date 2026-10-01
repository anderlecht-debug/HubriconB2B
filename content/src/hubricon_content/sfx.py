"""Sound assets from ElevenLabs, generated once and cached with their prompts.

The synthesised drone and the sine tick were the cheapest tell in a first
render. With a key on file, the tick, the whoosh and a restrained bed come from
ElevenLabs' sound-effects and music endpoints; each is generated once, written
under content/assets with a manifest, and reused by every video so the series
sounds like one series. A failed call leaves the procedural fallback in place
and says so.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .state import CONTENT_DIR

SFX = CONTENT_DIR / "assets" / "sfx"
MUSIC = CONTENT_DIR / "assets" / "music"
SFX_SPECS = {
    "tick": {"text": "a single very short, soft, dry wooden click, like a fingertip tapping a desk once; close-miked, no reverb, no tail",
             "duration_seconds": 0.5, "prompt_influence": 0.7},
    "whoosh": {"text": "a low, brief, airy cinematic whoosh for a chapter cut; restrained, felt more than heard, no cartoon sweep",
               "duration_seconds": 0.9, "prompt_influence": 0.6},
}
BED_PROMPT = ("Sparse, restrained ambient underscore for a serious financial documentary: a soft felt piano playing slow "
              "single notes, a low sustained cello drone, wide reverb, no drums, no melody hook, no build, 62 bpm, "
              "minor key, calm and expensive. Seamlessly loopable.")
BED_MS = 120000


def _post(url: str, body: dict, timeout: int = 300) -> bytes:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def ensure(force: bool = False) -> dict:
    """Generate whatever is missing. Returns {name: path|None, notes}."""
    SFX.mkdir(parents=True, exist_ok=True); MUSIC.mkdir(parents=True, exist_ok=True)
    out, notes = {}, []
    manifest_p = SFX / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    for name, spec in SFX_SPECS.items():
        p = SFX / f"{name}.mp3"
        if p.exists() and not force:
            out[name] = p; continue
        try:
            p.write_bytes(_post("https://api.elevenlabs.io/v1/sound-generation", spec))
            manifest[name] = {**spec, "source": "elevenlabs sound-generation"}
            out[name] = p
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, TimeoutError) as err:
            detail = err.read().decode(errors="replace")[:200] if hasattr(err, "read") else str(err)
            notes.append(f"{name}: {detail}"); out[name] = None
    bed = MUSIC / "bed-elevenlabs.mp3"
    if bed.exists() and not force:
        out["bed"] = bed
    else:
        try:
            bed.write_bytes(_post("https://api.elevenlabs.io/v1/music", {"prompt": BED_PROMPT, "music_length_ms": BED_MS}, timeout=600))
            manifest["bed"] = {"prompt": BED_PROMPT, "music_length_ms": BED_MS, "source": "elevenlabs music"}
            out["bed"] = bed
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, TimeoutError) as err:
            detail = err.read().decode(errors="replace")[:300] if hasattr(err, "read") else str(err)
            notes.append(f"bed: {detail}"); out["bed"] = None
    manifest_p.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    out["notes"] = notes
    return out
