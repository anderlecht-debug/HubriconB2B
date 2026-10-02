"""The YouTube description, number-guarded like everything else."""

import json

from hubricon_engine.narrate import render as render_facts, validate as number_guard

from . import script as scriptmod
from .qa import disclosure_for

SITE = "https://www.hubricon.com"


def _ts(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def data_line(u: dict) -> str:
    """Where the film's numbers come from, as its own unit says, with the label its proof carries."""
    models = set(u.get("models") or [])
    if "store_study" in models:
        return ("Every number on screen is Hubricon's engine on a real retailer's published orders: Online Retail II, "
                "UCI Machine Learning Repository, CC BY 4.0 (Chen, D., 2012, https://doi.org/10.24432/C5CG6D). "
                "Modeled on published data · Not a client · Not a result.")
    if "case_study" in models:
        return ("Every number on screen is modeled from one real listing's public page and Amazon's published fee cards. "
                "Modeled from public data · Not a client · Not a result.")
    return ("Every number on screen comes from a real model run on a labelled demo catalogue (Tarnhollow, demo data). "
            "Nothing is illustrative.")


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
    # Every link carries the film's source code, so a booked call can be traced to the film that
    # earned it (the site keeps ?src= for 90 days and /apply carries it into the booking). The
    # call first, the free courses second: the spec's soft close. No /method, no Teardown (killed).
    code = f"yt-{str(u.get('id') or slug).lower()}"
    links = [f"Book the call: {SITE}/apply?src={code}",
             f"Not ready yet? Every course is free, every lesson open: {SITE}/learn?src={code}"]
    desc = (f"{text}\n\n" + (f"Chapters\n0:00 Hook\n{chapters}\n\n" if chapters else "") +
            "\n".join(links) + "\n\n" + disclosure_for(u.get("voice")) + "\n\n" + data_line(u) + "\n\n" +
            "Tags: " + ", ".join(("amazon fba", "shopify", "ecommerce finance", "unit economics", "profit margin", "cash flow",
                                  "inventory", "pricing", "hubricon")))
    (d / "description.md").write_text(desc + "\n", encoding="utf-8")
    pinned = links[1]   # "every piece points to /learn" (HUBRICON_SPEC.md, the content engine)
    (d / "pinned-comment.md").write_text(pinned + "\n", encoding="utf-8")
    return {"status": "ok", "description": "description.md", "chapters": len(timing.get("chapters", []))}
