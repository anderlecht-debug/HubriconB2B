"""One real number and one chart fragment. No face, no arrows, no shock.

On the films' one look (VISUAL_SPEC.md §3.1): paper ground, the number in
Inter Display (blue only when it is money), its label in ink, and the demo
label boxed as the film stage boxes it, all from content/assets/tokens.json."""

import json
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import script as scriptmod
from . import tokens

# How long after a chart's last build beat the fragment is taken: enough for the
# line to have finished drawing, far short of anything the hold cuts away to.
BUILD_SETTLE_S = 0.8
# How far the fragment's left edge dissolves into the paper.
FADE_PX = 300


def _font(size: int, weight: int = 600):
    return ImageFont.truetype(str(tokens.font_file(weight, display=True)), size, layout_engine=ImageFont.Layout.RAQM)


def _tracked(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, track_em: float):
    """Draw text with CSS letter-spacing: each glyph at its kerned advance plus the tracking."""
    x, y = xy
    for i, c in enumerate(text):
        draw.text((x + font.getlength(text[:i]) + track_em * font.size * i, y), c, font=font, fill=fill, anchor="ls")


def chart_frame(d):
    """A frame of the film's own chart, taken just after its last build beat landed.

    The fragment used to be a frame picked by its place in the film, which on V04
    was a kinetic card, so the thumbnail cropped through a sentence and read as
    broken type (2026-10-05). events.json records every landing the scenes made
    and which kind it was, and a `data` landing is a chart drawing itself, so the
    picture at one is a chart and nothing else."""
    ev, master = d / "events.json", d / "media" / "master.mp4"
    if not ev.exists() or not master.exists():
        return None
    data = [e for e in json.loads(ev.read_text(encoding="utf-8")) if e.get("kind") == "data"]
    if not data:
        return None
    at_s = float(data[-1]["t"]) + BUILD_SETTLE_S
    out = d / ".thumbnail-frame.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at_s:.3f}", "-i", str(master),
                    "-frames:v", "1", str(out)], check=True, timeout=300)
    fr = Image.open(out).convert("RGB")
    fr.load()
    out.unlink()
    return fr


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
    fr = chart_frame(d)
    if fr is not None:
        fr = fr.resize((1280, int(1280 * fr.height / fr.width)))
        # below the heading and above the burned subtitles: a fragment that cuts
        # through a word reads as broken type, so the crop takes the plot alone
        crop = fr.crop((fr.width // 3, int(fr.height * 0.26), fr.width, int(fr.height * 0.80)))
        crop = crop.resize((int(crop.width * 0.72), int(crop.height * 0.72)))
        img.paste(crop, (1280 - crop.width - 24, (720 - crop.height) // 2))
        # The fragment fades into the paper under the number, never a box or a
        # shadow, and the fade starts where the fragment does: measured from the
        # left of the picture it left the crop's own edge at full strength, a hard
        # vertical cut through whatever word the plot ended on.
        left = 1280 - crop.width - 24
        shade = Image.new("RGBA", img.size, (*paper, 0))
        sd = ImageDraw.Draw(shade)
        for x in range(left, left + FADE_PX, 2):
            sd.rectangle([x, 0, x + 2, 720], fill=(*paper, int(255 * (1 - (x - left) / FADE_PX))))
        img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)
    size = 168 if len(value) <= 6 else 128 if len(value) <= 9 else 96
    baseline = 220 + size
    _tracked(draw, (64, baseline), value, _font(size), tokens.rgb("blue") if "$" in value else ink, stage["number_track_em"])
    def wrap(text: str) -> list[str]:
        out, cur = [], ""
        for w in text.split():
            if len(cur) + len(w) + 1 > 30 and cur:
                out.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        return out + ([cur] if cur else [])

    # the longest leading clause that fits, as scenes.base.fit_clause cuts a chart
    # caption: a label stopped mid-phrase by the line count loses the words that
    # say what the figure is of
    parts = label.split(", ")
    for i in range(len(parts), 0, -1):
        lines = wrap(", ".join(parts[:i]))
        if len(lines) <= 3:
            break
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
