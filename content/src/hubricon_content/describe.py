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


ARCHIVAL = {"loc": "Library of Congress", "smithsonian": "Smithsonian Institution", "commons": "Wikimedia Commons",
            "archive": "Internet Archive", "nara": "National Archives"}


def credits(plan: dict) -> str:
    """Every picture's credit, from the picks' own provenance only (VISUAL_SPEC.md §11)."""
    stock, archival, ai = {}, [], False
    for s in plan.get("shots", []):
        for a in (s["asset"] if isinstance(s.get("asset"), list) else [s.get("asset")]):
            if not a:
                continue
            src = str(a.get("source") or str(a.get("id", "")).split(":")[0])
            if src in ("pexels", "pixabay"):
                stock.setdefault(src, set()).add(a.get("author") or "")
            elif src in ARCHIVAL:
                line = f"{a.get('title') or 'Photograph'}, {ARCHIVAL[src]}" + (f" ({a['licence']})" if a.get("licence") else "")
                if line not in archival:
                    archival.append(line)
            elif s.get("kind") == "texture" or src == "higgsfield":
                ai = True
    out = []
    if stock:
        out.append("Footage: " + " and ".join({"pexels": "Pexels (pexels.com)", "pixabay": "Pixabay (pixabay.com)"}[k] for k in sorted(stock)) +
                   ". Filmed by " + ", ".join(sorted({n for v in stock.values() for n in v if n})) + ".")
    if archival:
        out.append("Archival: " + "; ".join(archival) + ".")
    if ai:
        out.append("Some illustrations are AI-generated, and say so on screen.")
    return "\n".join(out)


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
    if (d / "shots.json").exists():
        cr = credits(json.loads((d / "shots.json").read_text(encoding="utf-8")))
        if cr:
            desc += "\n\n" + cr
    (d / "description.md").write_text(desc + "\n", encoding="utf-8")
    pinned = links[1]   # "every piece points to /learn" (HUBRICON_SPEC.md, the content engine)
    (d / "pinned-comment.md").write_text(pinned + "\n", encoding="utf-8")
    return {"status": "ok", "description": "description.md", "chapters": len(timing.get("chapters", []))}
