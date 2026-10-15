"""The films' one look, in Python: colours and type from content/assets/tokens.json,
which content/film/tokens.mjs writes from the site's own /assets/hubricon.css
(VISUAL_SPEC.md §3.1). No module in this package keeps a colour of its own.

Type is Inter. Every size a film sets is at or above Inter's display range
(32 px), where the site's variable font draws its Display cut, so Manim, the
thumbnail and the subtitles use the static Inter Display files beside it in
content/assets/fonts/ and match the film stage letter for letter.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path

from .state import CONTENT_DIR

TOKENS = CONTENT_DIR / "assets" / "tokens.json"
FONTS = CONTENT_DIR / "assets" / "fonts"
WRITER = CONTENT_DIR / "film" / "tokens.mjs"
FONT_FILES = {(True, 400): "InterDisplay-Regular.ttf", (True, 600): "InterDisplay-SemiBold.ttf",
              (False, 400): "Inter-Regular.ttf", (False, 600): "Inter-SemiBold.ttf"}


def refresh() -> bool:
    """Rewrite tokens.json from the CSS; run before every render. Without node the
    committed file stands. True when node ran."""
    try:
        subprocess.run(["node", str(WRITER)], check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    load.cache_clear()
    return True


@functools.lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(TOKENS.read_text(encoding="utf-8"))


def stage() -> dict:
    """The film stage's measures from content/film/film.css, in px and em:
    pad_px, heading_px, caption_px, number_px, the corner's label and mark …"""
    return load()["stage"]


def colour(name: str) -> str:
    """'#rrggbb' for a token name: paper, paper_2, ink, ink_2 … blue, night …"""
    return load()["colour"][name]


def rgb(name: str) -> tuple[int, int, int]:
    h = colour(name)
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def rgba(css: str) -> tuple[int, int, int, float]:
    """'rgb(11 95 255 / 0.07)' → (11, 95, 255, 0.07)."""
    m = re.fullmatch(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)\s*(?:[/,]\s*([\d.]+))?\s*\)", css.strip())
    if not m:
        raise ValueError(f"not an rgb() colour: {css}")
    return int(m[1]), int(m[2]), int(m[3]), float(m[4] or 1)


def ass(name: str, alpha: float = 1.0) -> str:
    """An ASS subtitle colour, &HAABBGGRR, where AA is transparency (00 opaque)."""
    r, g, b = rgb(name)
    return f"&H{round((1 - alpha) * 255):02X}{b:02X}{g:02X}{r:02X}"


def family(display: bool = True) -> str:
    f = load()["font"]
    return f["display"] if display else f["family"]


def font_file(weight: int = 600, display: bool = True) -> Path:
    return FONTS / FONT_FILES[(display, 400 if weight < 500 else 600)]


def register_fonts() -> None:
    """Make Inter and Inter Display known to Pango (Manim) in this process."""
    import manimpango
    for f in sorted(FONTS.glob("Inter*.ttf")):
        manimpango.register_font(str(f))
