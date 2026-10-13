"""The film teaches, the worksheet practises (docs/content/LEARNING_DESIGN.md, transfer): a one-page sheet
per film, from its own script, for no tokens.

    hubricon-content worksheet <slug>    → videos/<slug>/worksheet.md

It holds the film's takeaways (its KEEP lines), the step to do this week (its TRY beat, a step a sentence)
and the figures that step uses, each with its source; a demo figure says it is demo data. Publishing it on
the matching /learn lesson is a site change, for the founder's go.
"""
from __future__ import annotations

import re

from . import script as scriptmod

TRY_NAMES = re.compile(r"THIS WEEK|WHAT YOU CAN DO|TRY IT", re.I)   # a script from before TRY lines
LEAD_IN = re.compile(r"^(so|now|here'?s|here is|okay|right)\b.{0,40}[.!]$", re.I)
FOLLOWS = re.compile(r"^(if|either way|otherwise|or|unless|and if|then)\b", re.I)


def build(slug: str) -> dict:
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    raw = scriptmod.parse((d / "script.md").read_text(encoding="utf-8"))
    sc = scriptmod.render(raw, facts)
    tries = [b for b in raw["beats"] if b.get("TRY", "").lower().startswith("y")] or \
            [b for b in raw["beats"] if TRY_NAMES.search(b["name"])]
    if not tries:
        return {"status": "skipped", "reason": "the script has no TRY beat"}
    title = sc["header"].get("TITLE", slug)
    keeps = [b["KEEP"] for b in sc["beats"] if b.get("KEEP")]
    lines = [f"# {title}", "", "*A worksheet for the film. Figures marked demo come from the Tarnhollow demo "
             "catalogue: demo data, not a client and not a result.*", ""]
    if keeps:
        lines += ["## What to keep", "", *[f"- {k}" for k in keeps], ""]
    lines += ["## Try it this week", ""]
    used = []
    for b in tries:
        text = scriptmod.render_facts(b["VO"], facts)
        steps = []
        for sent in (x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if x.strip()):
            if not steps and LEAD_IN.match(sent):
                continue                                  # "So here's this week." introduces, it is not a step
            if steps and FOLLOWS.match(sent):
                steps[-1] += " " + sent                   # "If not, …" belongs to the check before it
            else:
                steps.append(sent)
        lines += [f"{i}. {s}" for i, s in enumerate(steps, 1)] + [""]
        used += [k for k in re.findall(r"\{\{\s*(\w+)\s*\}\}", b["VO"]) if k not in used]
    if used:
        lines += ["## The numbers in it", "", "| Figure | What it is | Source |", "|---|---|---|"]
        for k in used:
            f = facts.get(k, {})
            src = str(f.get("source", ""))
            demo = " (demo data)" if "demo" in src.lower() else ""
            lines.append(f"| {f.get('value', '')}{demo} | {f.get('label', '')} | {src} |")
        lines.append("")
    lines += ["The free course that goes further: hubricon.com/learn"]
    out = d / "worksheet.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pdf_path = pdf(d, "\n".join(lines))
    return {"status": "ok", "worksheet": str(out), "pdf": str(pdf_path) if pdf_path else None, "steps": sum(1 for l in lines if re.match(r"^\d+\. ", l)), "figures": len(used)}


def _css() -> str:
    """The sheet's type, its colours from the one design system (content/assets/tokens.json)."""
    from . import tokens
    rgb = lambda k: "rgb({},{},{})".format(*tokens.rgb(k))
    ink, ink3, rule = rgb("ink"), rgb("ink_3"), rgb("rule_2")
    return (
        "@page { size: Letter; margin: 0.55in 0.65in; }"
        f"body {{ font: 400 10pt/1.38 'Inter', system-ui, sans-serif; color: {ink}; }}"
        "h1 { font: 700 17pt/1.18 'Inter', sans-serif; letter-spacing: -0.01em; margin: 0 0 6pt; }"
        f"h2 {{ font: 600 10.5pt/1.3 'Inter', sans-serif; margin: 12pt 0 5pt; text-transform: uppercase; letter-spacing: 0.06em; color: {ink3}; }}"
        f"em {{ color: {ink3}; font-size: 9.5pt; }}"
        "ol, ul { padding-left: 16pt; margin: 0; } li { margin: 0 0 3.5pt; }"
        "table { border-collapse: collapse; width: 100%; font-size: 8.5pt; }"
        f"th, td {{ border-bottom: 1px solid {rule}; padding: 4pt 6pt; text-align: left; vertical-align: top; }}"
        "td { word-break: break-word; }")


def _chrome():
    import glob
    from pathlib import Path
    found = sorted(glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")))
    return found[-1] if found else None


def pdf(d, md: str):
    """The worksheet as a one-page PDF, ready for /learn: the markdown set in the site's type, printed by the
    same Chromium that renders the films. None when no Chromium is on the machine."""
    import subprocess
    import markdown
    chrome = _chrome()
    if not chrome:
        return None
    from .state import CONTENT_DIR
    fonts = CONTENT_DIR / "assets" / "fonts"
    face = "".join(f"@font-face {{ font-family: 'Inter'; src: url('file://{f}'); font-weight: {w}; }}"
                   for f, w in ((next(fonts.glob('*Inter*Regular*'), None), 400), (next(fonts.glob('*Inter*SemiBold*'), None), 600),
                                (next(fonts.glob('*Inter*Bold*'), None), 700)) if f)
    html = d / "worksheet.html"
    html.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{face}{_css()}</style></head><body>"
                    f"{markdown.markdown(md, extensions=['tables'])}</body></html>", encoding="utf-8")
    out = d / "worksheet.pdf"
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", f"file://{html}"], capture_output=True, timeout=120)
    return out if out.exists() else None
