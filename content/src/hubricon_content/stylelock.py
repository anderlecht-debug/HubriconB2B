"""After the first video passes QA: freeze what was actually used (bible §7)."""

import json
from datetime import date
from pathlib import Path

from . import script as scriptmod
from .audio import BED_DB, BED_DUCK_DB, ROOM_TONE_DB, TICK_DB, WHOOSH_DB
from .scenes.base import STYLE
from .state import CONTENT_DIR
from .tts import ELEVEN_MODEL, ELEVEN_SETTINGS, KOKORO_VOICE

LOCK_JSON = CONTENT_DIR / "assets" / "style-lock.json"
LOCK_MD = CONTENT_DIR.parent / "docs" / "content" / "STYLE-LOCK.md"


def write(slug: str, q: dict) -> Path:
    d = scriptmod.video_dir(slug)
    mixmeta = json.loads((d / "media" / "mix.json").read_text(encoding="utf-8")) if (d / "media" / "mix.json").exists() else {}
    textures = CONTENT_DIR / "assets" / "textures" / "manifest.json"
    lock = {
        "locked_on": date.today().isoformat(), "locked_from": slug,
        "style": STYLE,
        "sound": {"room_tone_db": ROOM_TONE_DB, "bed_db": BED_DB, "bed_duck_db": BED_DUCK_DB, "tick_db": TICK_DB,
                  "whoosh_db": WHOOSH_DB, "target_lufs": -16, "bed_source": mixmeta.get("bed_source")},
        "narration": {"founder_model": ELEVEN_MODEL, "founder_settings": ELEVEN_SETTINGS, "placeholder_voice": KOKORO_VOICE,
                      "per_paragraph": True},
        "edit": {"fps": 30, "resolution": "1920x1080", "grain": "noise=alls=7:allf=t+u", "cuts": "hard", "chapter_card_s": 1.1,
                 "subtitles": "burned, JetBrains Mono, 42 chars/line"},
        "textures": json.loads(textures.read_text(encoding="utf-8")) if textures.exists() else "procedural glow (no Higgsfield set cached yet)",
    }
    LOCK_JSON.write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8")
    md = ["# Style lock", "", f"Frozen on {lock['locked_on']} from `{slug}` after it passed QA. Every later video reuses these values;",
          "change them only by a deliberate edit here and in `content/assets/style-lock.json`.", "",
          "## Palette", ""] + [f"- {k}: `{v}`" for k, v in STYLE["palette"].items()] + \
         ["", "## Type", ""] + [f"- {k}: {v}" for k, v in STYLE["type"].items()] + \
         ["", "## Charts", ""] + [f"- {k}: {v}" for k, v in STYLE["chart"].items()] + \
         ["", "## Sound", ""] + [f"- {k}: {v}" for k, v in lock["sound"].items()] + \
         ["", "## Narration", ""] + [f"- {k}: {v}" for k, v in lock["narration"].items()] + \
         ["", "## Edit", ""] + [f"- {k}: {v}" for k, v in lock["edit"].items()] + \
         ["", "## Textures", "", f"- {lock['textures'] if isinstance(lock['textures'], str) else 'cached Higgsfield set, see content/assets/textures/manifest.json'}", ""]
    LOCK_MD.write_text("\n".join(md), encoding="utf-8")
    q["style_locked"] = True
    return LOCK_JSON
