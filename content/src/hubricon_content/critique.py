"""Doctrine §14, the mechanical half. The judgment items are left for Claude
(the `critique` skill) and merged into the same file."""

import json
import re

from hubricon_engine.narrate import PLACEHOLDER

from . import script as scriptmod
from .state import CALENDAR

ITEMS = {
    1: "Does the viewer commit to a wrong answer before hearing the right one?",
    2: "Is there a concrete number in the first sentence?",
    3: "Is the title's promise fully delivered?",
    4: "Does any notation appear before its intuition?",
    5: "Is there exactly one idea, and exactly one CTA?",
    6: "Does the CTA match the awareness stage in §8?",
    7: "Is there one claim a competent operator could dispute?",
    8: "Is there any gap over 40 seconds without a re-hook?",
    9: "Does every number name its model run?",
    10: "Is any step of the method withheld?",
    11: "Does the close state a real limitation rather than pitch?",
    12: "Any banned phrase present?",
    13: "Are CLIP markers placed, with at least three usable?",
    14: "Would a $30M founder outside Amazon still get something from this? (pillars 1–2 exempt)",
}


def mechanical(slug: str, tier: str, pillar: int) -> dict:
    facts = scriptmod.load_facts(slug)
    text = (scriptmod.video_dir(slug) / "script.md").read_text(encoding="utf-8")
    sc = scriptmod.parse(text)
    cal = json.loads(CALENDAR.read_text(encoding="utf-8"))
    problems = scriptmod.validate(sc, facts, tier, pillar, cal["cta_by_pillar"])
    items = {n: {"n": n, "question": q, "pass": None, "note": "judged by the critique skill"} for n, q in ITEMS.items()}

    hook = sc["hooks"].get(1, "") or next(iter(sc["hooks"].values()), "")
    first = re.split(r"(?<=[.!?])\s", hook, maxsplit=1)[0] if hook else ""
    items[2].update(pass_=bool(PLACEHOLDER.search(first)), note="first sentence carries a {{key}} figure" if PLACEHOLDER.search(first) else "no figure in the first sentence")
    ctas = [b for b in sc["beats"] if b["CTA"]]
    items[5].update(pass_=len(ctas) == 1, note=f"{len(ctas)} CTA beat(s); one idea is judged by the skill")
    cta_problems = [p for p in problems if "CTA" in p or "pillar" in p]
    items[6].update(pass_=not cta_problems, note="; ".join(cta_problems) or "CTA matches §8 for this pillar")
    gaps = [p for p in problems if p.startswith("re-hook gap")]
    items[8].update(pass_=not gaps, note="; ".join(gaps) or "no gap over 40 s")
    ds = [p for p in problems if "DATA SOURCE" in p]
    unknown = [p for p in problems if "unknown placeholder" in p]
    items[9].update(pass_=not ds and not unknown, note="; ".join(ds + unknown) or "every chart beat names its run; every key exists")
    banned = [p for p in problems if "banned phrase" in p]
    items[12].update(pass_=not banned, note="; ".join(banned) or "none")
    clips = sum(1 for b in sc["beats"] if b["CLIP"].lower().startswith("y"))
    items[13].update(pass_=clips >= 3, note=f"{clips} CLIP markers")
    if pillar in (1, 2):
        items[14].update(pass_=True, note="exempt (pillar 1–2)")
    for it in items.values():
        if "pass_" in it:
            it["pass"] = it.pop("pass_")
    out = {"slug": slug, "pass": None, "validator_problems": problems,
           "items": [items[n] for n in sorted(items)]}
    return out


def merged_pass(c: dict) -> bool:
    return not c.get("validator_problems") and all(i.get("pass") is True for i in c["items"])
