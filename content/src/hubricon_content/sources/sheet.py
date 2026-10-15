"""Contact sheets: `content/videos/<slug>/sources/<shot>.jpg` (VISUAL_SPEC.md §7.2, §7.5).

The visual pick reads one sheet per world shot: up to nine candidates, three
frames each for footage (or the photograph), each labelled with the index it
has in `<shot>.json`, its id, size, frame rate and mean luma, so a pick can be
named without opening a file. A refused candidate stays on the sheet, washed
out and crossed through with its reason, so the eye can audit the filters.
Colours and type are the films' own (tokens.json, Inter).
"""

from __future__ import annotations

from pathlib import Path

from .. import tokens

COLS, GUTTER, PAD = 3, 24, 32
LABEL_PX, HEADER_PX = 20, 26


def _font(px: int, weight: int = 400):
    from PIL import ImageFont
    return ImageFont.truetype(str(tokens.font_file(weight, display=False)), px)


def _fit(draw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def label(c: dict) -> list[str]:
    """The two lines under a tile: index and id, then size, frame rate and luma."""
    chk = c.get("checks") or {}
    bits = [f"{c.get('width')}×{c.get('height')}" if c.get("width") else "size unknown"]
    if c["kind"] == "video":
        bits.append(f"{float(c['fps']):g} fps" if c.get("fps") else "fps ?")
        if c.get("duration"):
            bits.append(f"{float(c['duration']):.0f} s")
    if chk.get("luma") is not None:
        bits.append(f"luma {float(chk['luma']):.0f}")
    face = (chk.get("faces") or {}).get("max_area") if isinstance(chk.get("faces"), dict) else None
    if face:
        bits.append(f"face {face * 100:.1f}%")
    if chk.get("cuts"):
        bits.append(f"cuts {', '.join(f'{t:g}' for t in chk['cuts'][:3])}")
    return [f"{c.get('sheet_index', '?')}  {c['id']}", " · ".join(bits)]


def write(path: Path, header: list[str], sections: list[tuple[str | None, list[dict]]]) -> Path:
    """Draw the sheet. Each section is (title or None, candidates with a `strip` image)."""
    from PIL import Image, ImageDraw
    paper, ink, ink3, rule = tokens.rgb("paper"), tokens.rgb("ink"), tokens.rgb("ink_3"), tokens.rgb("rule_2")
    f_head, f_lab = _font(HEADER_PX, 600), _font(LABEL_PX)
    strips = {id(c): Image.open(c["strip"]).convert("RGB") for _, cs in sections for c in cs if c.get("strip")}
    cell_w = max([im.width for im in strips.values()] + [480])
    label_h = LABEL_PX * 4 + 12
    width = PAD * 2 + COLS * cell_w + (COLS - 1) * GUTTER
    height = PAD + len(header) * (HEADER_PX + 10) + 8
    plan = []
    for title, cs in sections:
        cs = [c for c in cs if id(c) in strips]
        cell_h = max([strips[id(c)].height for c in cs] + [180])
        rows = max(1, -(-len(cs) // COLS))
        plan.append((title, cs, cell_h, height))
        height += (HEADER_PX + 14 if title else 0) + rows * (cell_h + label_h + GUTTER)
    height += PAD
    sheet = Image.new("RGB", (width, height), paper)
    d = ImageDraw.Draw(sheet)
    y = PAD
    for line in header:
        d.text((PAD, y), _fit(d, line, f_head, width - 2 * PAD), font=f_head, fill=ink)
        y += HEADER_PX + 10
    for title, cs, cell_h, top in plan:
        y = top
        if title:
            d.text((PAD, y), title, font=f_head, fill=ink3)
            y += HEADER_PX + 14
        if not cs:
            d.text((PAD, y), "no candidate reached the preview check", font=f_lab, fill=ink3)
        for i, c in enumerate(cs):
            x = PAD + (i % COLS) * (cell_w + GUTTER)
            ty = y + (i // COLS) * (cell_h + label_h + GUTTER)
            im = strips[id(c)]
            sheet.paste(im, (x, ty))
            d.rectangle([x, ty, x + im.width - 1, ty + im.height - 1], outline=rule, width=1)
            refused = not c.get("passed_filters")
            if refused:
                wash = Image.new("RGB", im.size, paper)
                sheet.paste(Image.blend(im, wash, 0.6), (x, ty))
                d.line([x, ty, x + im.width - 1, ty + im.height - 1], fill=ink, width=3)
                d.line([x, ty + im.height - 1, x + im.width - 1, ty], fill=ink, width=3)
            lines = label(c) + ([f"refused: {(c.get('rejected_because') or ['no reason'])[0]}"] if refused else ["passed the filters"])
            for n, line in enumerate(lines):
                d.text((x, ty + im.height + 6 + n * (LABEL_PX + 4)), _fit(d, line, f_lab, cell_w),
                       font=f_lab, fill=ink if n != 1 else ink3)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=85)
    return path
