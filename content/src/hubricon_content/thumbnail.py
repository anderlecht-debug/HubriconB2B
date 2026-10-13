"""A film's three thumbnail concepts, rendered, so all three can go to YouTube's test (FILM_PROCESS.md 2.11).

Two kinds:
- the figure: one real number, its label, and one chart fragment, on the films' one look (VISUAL_SPEC.md
  §3.1: paper ground, the number in Inter Display, blue only when it is money, the demo label boxed);
- the stakes picture: one of the film's own pictures (already licensed and credited in its description) or
  a frame of one of its stage scenes, full bleed, with at most four words.
No face added, no arrows, no shock. The chosen concept (THUMBNAIL) is also thumbnail.png."""

import json
import re
import subprocess
from pathlib import Path

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


LIGHT, DESK = (242, 238, 230), (14, 13, 12)     # the v3 film's text and desk (film/v3/base.css)


def figure_v3(facts: dict, key: str, text: str) -> Image.Image:
    """The figure kind on the film's own look: the figure, then the concept's other words (four at most in
    all), on the dark desk; a demo figure carries its demo label."""
    f = facts.get(key, {})
    value = str(f.get("value", ""))
    rest = re.sub(r"\{\{\s*\w+\s*\}\}", " ", text or "").split()
    img = Image.new("RGB", (1280, 720), DESK)
    glow = Image.new("RGB", (1280, 720), (40, 36, 30))
    mask = Image.new("L", (1280, 720), 0)
    ImageDraw.Draw(mask).ellipse([-200, -260, 1100, 760], fill=150)
    from PIL import ImageFilter
    img = Image.composite(glow, img, mask.filter(ImageFilter.GaussianBlur(160)))
    draw = ImageDraw.Draw(img)
    stage = tokens.stage()
    size = 200 if len(value) <= 6 else 150 if len(value) <= 10 else 112
    _tracked(draw, (64, 330), value, _font(size, 700), tokens.rgb("blue") if "$" in value else LIGHT, stage["number_track_em"])
    if rest:
        _tracked(draw, (68, 330 + 130), " ".join(rest), _font(96, 600), LIGHT, stage["number_track_em"])
    if "demo" in str(f.get("source", "")).lower():
        brand = facts.get("demo_brand", {}).get("value") or "demo"
        t = f"{brand} demo data".upper()
        fl = _font(20)
        w = fl.getlength(t) + 0.06 * 20 * len(t)
        draw.rounded_rectangle([64, 640, 64 + w + 28, 676], radius=5, outline=(119, 114, 106), width=1)
        _tracked(draw, (78, 665), t, fl, (185, 179, 169), stage["label_track_em"])
    return img


def figure(d, facts: dict, key: str | None) -> Image.Image:
    """The pre-packaging formula: one real number, its label and a chart fragment."""
    value = facts[key]["value"] if key and key in facts else ""
    label = facts[key]["label"] if key and key in facts else ""
    brand = facts.get("demo_brand", {}).get("value") if key and "demo" in str(facts.get(key, {}).get("source", "")).lower() else None
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
    return img


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (t or "").lower())}


def stakes_shot(plan: dict, c: dict) -> dict | None:
    """The shot whose picture the stakes concept names: PICTURE as a shot id, else the world shot whose
    query, words and picture title share the most words with the concept (the relevance model, when it
    is installed, ranks instead)."""
    shots = plan.get("shots", [])
    if c.get("picture"):
        hit = next((s for s in shots if s["id"] == c["picture"]), None)
        if hit:
            return hit
    pool = [s for s in shots if s.get("room") == "world" and (s.get("asset") or {}).get("file")]
    if not pool:
        return None
    want = _words(f"{c.get('visual', '')} {c.get('picture') or ''}")
    try:
        from . import relevance
        ranked = relevance.rank_assets(f"{c.get('visual', '')} {c.get('picture') or ''}", pool)
        if ranked:
            return ranked[0]
    except Exception:
        pass
    have = lambda s: _words(" ".join(s.get("query") or []) + " " + (s.get("says") or "") + " " + str((s.get("asset") or {}).get("title", "")))
    return max(pool, key=lambda s: len(want & have(s)))


def _frame(path, at: float) -> Image.Image:
    out = path.parent / f".thumb-frame-{path.stem}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(path), "-frames:v", "1", str(out)], check=True, timeout=300)
    im = Image.open(out).convert("RGB")
    im.load()
    out.unlink()
    return im


def stakes(d, plan: dict, c: dict, facts: dict) -> tuple[Image.Image, dict]:
    """The stakes kind: a picture of what is at stake, full bleed, darkened toward its words, at most four."""
    from . import footage
    s = stakes_shot(plan, c)
    prov = {}
    clip = d / "shots" / f"{(s or {}).get('id')}.mp4"
    if s and clip.exists():
        # the picture exactly as the film shows it: the shot's own clip, mid-move, in the film's look
        pic = _frame(clip, 0.5 * footage.probe(clip)["duration"])
        a = s.get("asset") or {}
        prov = {"shot": s["id"], "asset": a.get("id"), "credit": a.get("credit") or a.get("author"), "licence": a.get("licence"),
                **({} if a else {"scene": "a frame of the film's own stage scene"})}
    elif s and s.get("room") == "world" and (s.get("asset") or {}).get("file"):
        a = s["asset"]
        src = Path(a["file"])
        if src.suffix.lower() in (".mp4", ".mov", ".webm"):
            pic = _frame(src, float(a.get("in", 0.0)) + 1.0)
        else:      # the still as the film shows it: the world grade (a raw scan on white reads as a grey haze)
            from .render_shots import REPO, graded_still
            pic = Image.open(REPO / graded_still(src)["url"].lstrip("/")).convert("RGB")
        prov = {"shot": s["id"], "asset": a.get("id"), "credit": a.get("credit") or a.get("author"), "licence": a.get("licence")}
    elif s and (d / "shots" / f"{s['id']}.mp4").exists():
        clip = d / "shots" / f"{s['id']}.mp4"
        pic = _frame(clip, 0.7 * footage.probe(clip)["duration"])      # the scene once its figures have landed
        prov = {"shot": s["id"], "scene": "a frame of the film's own stage scene"}
    else:
        pic = Image.new("RGB", (1280, 720), tokens.rgb("ink"))
        prov = {"shot": None, "note": "no picture in the film fits; ink ground"}
    pic.thumbnail((4000, 4000))
    k = max(1280 / pic.width, 720 / pic.height)
    pic = pic.resize((max(1280, round(pic.width * k)), max(720, round(pic.height * k))), Image.LANCZOS)
    fx, fy = ((s or {}).get("params") or {}).get("focus") or (0.5, 0.45)
    x0 = int(min(max(0, fx * pic.width - 640), pic.width - 1280))
    y0 = int(min(max(0, fy * pic.height - 360), pic.height - 720))
    img = pic.crop((x0, y0, x0 + 1280, y0 + 720)).convert("RGBA")
    ink = tokens.rgb("ink")
    shade = Image.new("RGBA", img.size, (*ink, 0))
    sd = ImageDraw.Draw(shade)
    for x in range(0, 1280, 4):     # darkened toward the words, so they read without a box
        sd.rectangle([x, 0, x + 4, 720], fill=(*ink, int(205 * max(0.0, 1 - x / 900) ** 1.3)))
    img = Image.alpha_composite(img, shade).convert("RGB")
    draw = ImageDraw.Draw(img)
    text = scriptmod.render_facts(c.get("text", ""), facts)
    money = "$" in text
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + len(w) + 1 > 14:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines = (lines + [cur])[:2] if cur else lines[:2]
    size = 132 if max((len(l) for l in lines), default=0) <= 10 else 104
    y = 720 - 96 - (len(lines) - 1) * int(size * 1.02)
    stage = tokens.stage()
    for ln in lines:
        _tracked(draw, (64, y), ln, _font(size, 700), tokens.rgb("blue") if money and "$" in ln else LIGHT, stage["number_track_em"])
        y += int(size * 1.02)
    return img, prov


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    sc = scriptmod.parse((d / "script.md").read_text(encoding="utf-8"))
    h = sc["header"]
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8")) if (d / "shots.json").exists() else {"shots": []}
    lines = [h[f"THUMBNAIL {i}"] for i in (1, 2, 3) if h.get(f"THUMBNAIL {i}")] or [h.get("THUMBNAIL", "")]
    (d / "media").mkdir(exist_ok=True)
    made = []
    for i, line in enumerate(lines, 1):
        c = scriptmod.thumbnail_concept(line)
        keys = re.findall(r"\{\{\s*([a-z0-9_]+)\s*\}\}", f"{c['text']} {c['visual']}")
        if c["picture"] is None and keys:
            img, kind, prov = figure_v3(facts, keys[0], c["text"]), "figure", {"key": keys[0]}
        elif c["picture"] is None and not c["text"] and not keys:     # a pre-packaging concept: the old formula
            k = (scriptmod.keys_used(sc)[:1] or [None])[0]
            img, kind, prov = figure(d, facts, k), "figure", {"key": k}
        else:
            img, prov = stakes(d, plan, c, facts)
            kind = "stakes"
        out = d / "media" / f"thumb-{i}.png"
        img.save(out, optimize=True)
        made.append({"n": i, "concept": line, "kind": kind, "file": str(out.relative_to(d)), **prov})
    chosen = next((m for m in made if scriptmod._norm(m["concept"]) == scriptmod._norm(h.get("THUMBNAIL", ""))), made[0])
    (d / "thumbnail.png").write_bytes((d / chosen["file"]).read_bytes())
    (d / "media" / "thumbnails.json").write_text(json.dumps({"chosen": chosen["n"], "thumbnails": made}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "thumbnail": "thumbnail.png", "chosen": chosen["n"], "rendered": [m["file"] for m in made]}
