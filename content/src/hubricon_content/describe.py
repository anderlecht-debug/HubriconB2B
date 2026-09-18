"""The YouTube description, number-guarded like everything else."""

import json

from hubricon_engine.narrate import render as render_facts, validate as number_guard

from . import script as scriptmod
from .qa import DISCLOSURE

SITE = "https://www.hubricon.com"


def _ts(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def run(u: dict, q: dict, force: bool = False) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = scriptmod.load_facts(slug)
    sc = scriptmod.parse((d / "script.md").read_text(encoding="utf-8"))
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8")) if (d / "timing.json").exists() else {"chapters": []}
    h = sc["header"]
    hook = sc["hooks"].get(1, "")
    limit = next((b for b in reversed(sc["beats"]) if b["VO"]), None)
    body = [h.get("TITLE", ""), "", hook, "",
            (h.get("SPIKY CLAIM", "") + " " + (limit["VO"].split(". ")[0] + "." if limit else "")).strip(), ""]
    problems = number_guard("\n".join(body), facts)
    if problems:
        return {"status": "failed", "reason": "description failed the number guard: " + "; ".join(problems)}
    text = render_facts("\n".join(body), facts)
    chapters = "\n".join(f"{_ts(c['at'])} {c['title']}" for c in timing.get("chapters", []))
    pillar = u.get("pillar")
    links = [f"Every formula, in the open: {SITE}/method"]
    if pillar in (1, 2, 3, 5):
        links.insert(0, f"Free training and the Reimbursement Playbook template: {SITE}/learn")
    if pillar in (1, 2):
        links.append(f"The free Profit Teardown: {SITE}/apply")
    desc = (f"{text}\n\n" + (f"Chapters\n0:00 Hook\n{chapters}\n\n" if chapters else "") +
            "\n".join(links) + "\n\n" + DISCLOSURE + "\n\n" +
            "Every number on screen comes from a real model run on a labelled demo catalogue (Tarnhollow, demo data). "
            "Nothing is illustrative.\n\n"
            "Tags: " + ", ".join(t for t in ("amazon fba", "ecommerce finance", "unit economics", "profit margin", "cash flow",
                                            "inventory", "pricing", "monte carlo", "hubricon") if True))
    (d / "description.md").write_text(desc + "\n", encoding="utf-8")
    pinned = links[0]
    (d / "pinned-comment.md").write_text(pinned + "\n", encoding="utf-8")
    return {"status": "ok", "description": "description.md", "chapters": len(timing.get("chapters", []))}
