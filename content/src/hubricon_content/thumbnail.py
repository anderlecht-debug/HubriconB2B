"""One real number and one chart fragment. No face, no arrows, no shock."""

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import script as scriptmod
from .state import CONTENT_DIR

FONTS = CONTENT_DIR / "assets" / "fonts"
NAVY = (5, 10, 31); AMBER = (255, 192, 0); INK = (244, 246, 252); INK_60 = (154, 160, 180)


def _font(size: int, mono: bool = False):
    if mono:
        for p in ("/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf", "/usr/share/fonts/TTF/JetBrainsMono-Medium.ttf"):
            if Path(p).exists():
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()
    f = next(iter(FONTS.glob("Fraunces[[]*")), None) or next(iter(FONTS.glob("Fraunces*.ttf")), None)
    font = ImageFont.truetype(str(f), size) if f else ImageFont.load_default()
    try:
        font.set_variation_by_axes([144, 700, 0, 0])   # opsz, wght, SOFT, WONK
    except Exception:
        pass
    return font


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    sc = scriptmod.parse((d / "script.md").read_text(encoding="utf-8"))
    concept = sc["header"].get("THUMBNAIL", "")
    keys = re.findall(r"\{\{\s*([a-z0-9_]+)\s*\}\}", concept) or scriptmod.keys_used(sc)[:1]
    key = keys[0] if keys else None
    value = facts[key]["value"] if key and key in facts else ""
    label = facts[key]["label"] if key and key in facts else ""
    img = Image.new("RGB", (1280, 720), NAVY)
    draw = ImageDraw.Draw(img)
    frame_files = sorted((d / "frames").glob("*.png")) if (d / "frames").exists() else []
    if frame_files:
        pick = frame_files[min(len(frame_files) - 1, max(1, len(frame_files) // 3))]
        fr = Image.open(pick).convert("RGB")
        fr = fr.resize((1280, int(1280 * fr.height / fr.width)))
        crop = fr.crop((fr.width // 3, 0, fr.width, fr.height))
        crop = crop.resize((int(crop.width * 0.72), int(crop.height * 0.72)))
        img.paste(crop, (1280 - crop.width - 24, (720 - crop.height) // 2))
        shade = Image.new("RGBA", img.size, (5, 10, 31, 0))
        sd = ImageDraw.Draw(shade)
        for x in range(0, 700, 4):
            sd.rectangle([x, 0, x + 4, 720], fill=(5, 10, 31, int(230 * (1 - x / 700))))
        img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
        draw = ImageDraw.Draw(img)
    size = 168 if len(value) <= 6 else 128 if len(value) <= 9 else 96
    draw.text((64, 220), value, font=_font(size), fill=AMBER)
    words, lines, cur = label.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 30 and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    y = 220 + size + 28
    for ln in lines[:3]:
        draw.text((68, y), ln, font=_font(34, mono=True), fill=INK); y += 44
    draw.text((68, 660), "Tarnhollow · demo data", font=_font(20, mono=True), fill=INK_60)
    draw.rectangle([64, 200, 120, 206], fill=AMBER)
    out = d / "thumbnail.png"
    img.save(out, optimize=True)
    return {"status": "ok", "thumbnail": out.name, "key": key}
