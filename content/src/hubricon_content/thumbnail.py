"""One real number and one chart fragment. No face, no arrows, no shock.

On the films' one look (VISUAL_SPEC.md §3.1): paper ground, the number in
Inter Display (blue only when it is money), its label in ink, and the demo
label boxed as the film stage boxes it, all from content/assets/tokens.json."""

import re

from PIL import Image, ImageDraw, ImageFont

from . import script as scriptmod
from . import tokens


def _font(size: int, weight: int = 600):
    return ImageFont.truetype(str(tokens.font_file(weight, display=True)), size, layout_engine=ImageFont.Layout.RAQM)


def _tracked(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, track_em: float):
    """Draw text with CSS letter-spacing: each glyph at its kerned advance plus the tracking."""
    x, y = xy
    for i, c in enumerate(text):
        draw.text((x + font.getlength(text[:i]) + track_em * font.size * i, y), c, font=font, fill=fill, anchor="ls")


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
    brand = facts.get("demo_brand", {}).get("value")
    paper, ink, ink_3, rule_2 = tokens.rgb("paper"), tokens.rgb("ink"), tokens.rgb("ink_3"), tokens.rgb("rule_2")
    stage = tokens.stage()
    img = Image.new("RGB", (1280, 720), paper)
    frame_files = sorted((d / "frames").glob("*.png")) if (d / "frames").exists() else []
    if frame_files:
        pick = frame_files[min(len(frame_files) - 1, max(1, len(frame_files) // 3))]
        fr = Image.open(pick).convert("RGB")
        fr = fr.resize((1280, int(1280 * fr.height / fr.width)))
        crop = fr.crop((fr.width // 3, 0, fr.width, int(fr.height * 0.80)))   # clear of any burned subtitles
        crop = crop.resize((int(crop.width * 0.72), int(crop.height * 0.72)))
        img.paste(crop, (1280 - crop.width - 24, (720 - crop.height) // 2))
        # the fragment fades into the paper under the number, never a box or a shadow
        shade = Image.new("RGBA", img.size, (*paper, 0))
        sd = ImageDraw.Draw(shade)
        for x in range(0, 700, 4):
            sd.rectangle([x, 0, x + 4, 720], fill=(*paper, int(240 * (1 - x / 700))))
        img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = 168 if len(value) <= 6 else 128 if len(value) <= 9 else 96
    baseline = 220 + size
    _tracked(draw, (64, baseline), value, _font(size), tokens.rgb("blue") if "$" in value else ink, stage["number_track_em"])
    words, lines, cur = label.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 30 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    y = baseline + 64
    for ln in lines[:3]:
        _tracked(draw, (66, y), ln, _font(40), ink, stage["number_sub_track_em"])
        y += 52
    if brand:
        text = f"{brand} demo data".upper()
        f = _font(20)
        w = f.getlength(text) + 0.06 * 20 * len(text)
        draw.rounded_rectangle([64, 640, 64 + w + 28, 676], radius=5, outline=rule_2, width=1)
        _tracked(draw, (78, 665), text, f, ink_3, stage["label_track_em"])
    out = d / "thumbnail.png"
    img.save(out, optimize=True)
    return {"status": "ok", "thumbnail": out.name, "key": key}
