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
    lines = [f"# {title}", "", "*A one-page worksheet for the film. Figures marked demo come from the Tarnhollow demo "
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
    return {"status": "ok", "worksheet": str(out), "steps": sum(1 for l in lines if re.match(r"^\d+\. ", l)), "figures": len(used)}
