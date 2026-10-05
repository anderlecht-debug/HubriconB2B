"""The script file: doctrine §12 parsed, validated and rendered.

The number guard is `hubricon_engine.narrate.validate`, applied to every line a
viewer will hear or read (VO, hooks, title, thumbnail, CTA). Scaffolding lines
(`PILLAR: 4`, `[1:15]`, `RUNTIME: 5–7 min`) legitimately carry digits and are
never checked as prose.
"""

import json
import re
from pathlib import Path

from hubricon_engine.narrate import PLACEHOLDER, render as render_facts, validate as number_guard

from .state import CONTENT_DIR

VIDEOS = CONTENT_DIR / "videos"
BANNED = ["in today's video", "let's dive in", "game-changer", "game changer", "secret", "hack",
          "crazy", "insane", "simply", "just", "obviously", "of course", "the truth is", "imagine"]
# The house visuals (HUBRICON_SPEC.md: the staircase, the Monte Carlo band, the aging cliff) are
# drawn by the site's own /assets/charts.mjs (content/film/render.mjs); the rest are Manim scenes.
HOUSE_SCENES = {"staircase", "montecarlo", "aging"}
CHART_SCENES = {"waterfall", "cash_cone", "elasticity", "newsvendor", "paths", "sample_size"} | HOUSE_SCENES
ALL_SCENES = CHART_SCENES | {"kinetic", "chapter_card", "screenshot", "number", "formula"}
HEADER_KEYS = ["TITLE", "THUMBNAIL", "PILLAR", "TIER", "AWARENESS STAGE", "CTA", "SPIKY CLAIM",
               "MISCONCEPTION", "RUNTIME"]
BEAT_RE = re.compile(r"^\[(\d+):(\d\d)\]\s*(.*)$")
FIELD_RE = re.compile(r"^\s+(VO|VISUAL|DATA SOURCE|CLIP|TEMPLATE|CTA):\s*(.*)$")
HOOK_RE = re.compile(r"^([123])\.\s+(.*)$")
STAMP_RE = re.compile(r"(\d+):(\d\d)")
WPM = 150
# F: the home page's one film. D: the long documentary films, 20 to 50 minutes (VISUAL_SPEC.md §7.1).
WORDS = {"A": (650, 950), "B": (1100, 2200), "F": (280, 520), "D": (3000, 7500)}


def scene_of(visual: str) -> str | None:
    """The scene a VISUAL line names: its leading token (`paths: the top tenth lit`),
    else the first scene name found anywhere in it."""
    vis = (visual or "").lower().strip()
    head = re.split(r"[:,;(]", vis, maxsplit=1)[0].strip().replace(" ", "_")
    if head in ALL_SCENES:
        return head
    for name in ("cash_cone", "sample_size", "chapter_card", "waterfall", "elasticity", "newsvendor", "screenshot", "kinetic", "paths",
                 "staircase", "montecarlo", "aging", "number", "formula"):
        if re.search(r"\b" + name + r"\b", vis):
            return name
    return None


def video_dir(slug: str) -> Path:
    return VIDEOS / slug


def load_facts(slug: str) -> dict:
    p = video_dir(slug) / "facts.json"
    if not p.exists():
        raise SystemExit(f"{p} missing — run `hubricon-content facts {slug}` first")
    return json.loads(p.read_text(encoding="utf-8"))


def parse(text: str) -> dict:
    header, hooks, beats, tail = {}, {}, [], {}
    section = "header"
    cur = None
    field = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if section == "header":
            m = re.match(r"^([A-Z ]+):\s*(.*)$", line)
            if m and m.group(1).strip() in HEADER_KEYS:
                header[m.group(1).strip()] = m.group(2).strip()
                continue
            if line.startswith("HOOKS"):
                section = "hooks"
                continue
        if section == "hooks":
            m = HOOK_RE.match(line)
            if m:
                hooks[int(m.group(1))] = m.group(2).strip()
                continue
            if line.strip() and hooks and not line.startswith("SCRIPT") and cur is None:
                hooks[max(hooks)] += " " + line.strip()
                continue
            if line.startswith("SCRIPT"):
                section = "script"
                continue
        if section == "script":
            m = BEAT_RE.match(line)
            if m:
                cur = {"at": int(m.group(1)) * 60 + int(m.group(2)), "name": m.group(3).strip(),
                       "VO": "", "VISUAL": "", "DATA SOURCE": "", "CLIP": "", "TEMPLATE": "", "CTA": ""}
                beats.append(cur)
                field = None
                continue
            if line.startswith("RE-HOOK AUDIT:") or line.startswith("DERIVED ASSETS:"):
                k, v = line.split(":", 1)
                tail[k.strip()] = v.strip()
                section = "tail"
                cur, field = None, None
                continue
            f = FIELD_RE.match(line)
            if f and cur is not None:
                field = f.group(1)
                cur[field] = f.group(2).strip()
                continue
            if cur is not None and field and line.strip():
                cur[field] = (cur[field] + " " + line.strip()).strip()
                continue
        if section == "tail" and line.strip():
            k = list(tail)[-1] if tail else None
            if ":" in line and line.split(":", 1)[0].strip() in ("RE-HOOK AUDIT", "DERIVED ASSETS"):
                k2, v = line.split(":", 1)
                tail[k2.strip()] = v.strip()
            elif k:
                tail[k] += " " + line.strip()
    return {"header": header, "hooks": hooks, "beats": beats, "tail": tail}


def spoken(script: dict) -> str:
    return "\n".join(b["VO"] for b in script["beats"] if b["VO"])


def word_count(text: str, facts: dict) -> int:
    return len(re.findall(r"[A-Za-z0-9$%'’.,-]+", render_facts(text, facts) if facts else text))


def _banned(text: str) -> list[str]:
    low = text.lower()
    hits = []
    for phrase in BANNED:
        pat = r"\b" + re.escape(phrase) + r"\b" if " " not in phrase else re.escape(phrase)
        if re.search(pat, low):
            hits.append(phrase)
    return hits


def validate(script: dict, facts: dict, tier: str, pillar: int, cta_rules: dict) -> list[str]:
    problems = []
    h = script["header"]
    for k in ("TITLE", "THUMBNAIL", "CTA", "SPIKY CLAIM", "MISCONCEPTION", "TIER", "PILLAR"):
        if not h.get(k):
            problems.append(f"header field {k} missing")
    # number guard on everything a viewer hears or reads
    prose = {"TITLE": h.get("TITLE", ""), "THUMBNAIL": h.get("THUMBNAIL", ""), "CTA": h.get("CTA", "")}
    for i, hook in script["hooks"].items():
        prose[f"hook {i}"] = hook
    for b in script["beats"]:
        prose[f"VO at {b['at'] // 60}:{b['at'] % 60:02d}"] = b["VO"]
        if b["CTA"]:
            prose[f"CTA at {b['at'] // 60}:{b['at'] % 60:02d}"] = b["CTA"]
    for where, text in prose.items():
        if not text:
            continue
        for p in number_guard(text, facts):
            if p != "empty draft":
                problems.append(f"{where}: {p}")
        for phrase in _banned(text):
            problems.append(f"{where}: banned phrase “{phrase}”")
    if len(script["hooks"]) != 3:
        problems.append(f"{len(script['hooks'])} hooks; need three")
    for i, hook in script["hooks"].items():
        n = word_count(hook, facts)
        if n > 45:
            problems.append(f"hook {i} is {n} words; limit 45")
        first = re.split(r"(?<=[.!?])\s", hook, maxsplit=1)[0]
        if not PLACEHOLDER.search(first):
            problems.append(f"hook {i}: first sentence has no {{{{key}}}} figure")
    if not script["beats"]:
        problems.append("no beats parsed; check the [m:ss] headers")
    clips = sum(1 for b in script["beats"] if b["CLIP"].lower().startswith("y"))
    if clips < 3:
        problems.append(f"{clips} CLIP markers; need at least three")
    long_film = tier.upper() == "D"
    if long_film:   # a long film's VISUAL is the shot plan's brief: it names VISUAL_SPEC.md §14 styles
        from .shots import registry
        styles = set(registry()["styles"])
    for b in script["beats"]:
        vis = b["VISUAL"].lower()
        if b["VO"] and not b["VISUAL"]:
            problems.append(f"beat {b['name']} has no VISUAL")
        if long_film:
            named = {w for w in re.findall(r"[a-z][a-z-]+[a-z]", vis) if w in styles}
            if b["VISUAL"] and not named:
                problems.append(f"beat {b['name']}: a long film's VISUAL names at least one style from VISUAL_SPEC.md §14")
            if named & {"chart-build", "counterfactual", "range-band", "callback"} and not b["DATA SOURCE"]:
                problems.append(f"beat {b['name']} draws a chart without DATA SOURCE")
            continue
        scene = scene_of(vis)
        if scene in CHART_SCENES:
            if not b["DATA SOURCE"]:
                problems.append(f"beat {b['name']} draws {scene} without DATA SOURCE")
            elif not any(w in b["DATA SOURCE"].lower() for w in ("demo", "modeled from public data", "published")):
                problems.append(f"beat {b['name']}: DATA SOURCE must say the run is demo data, the public-data case study, or a published card")
        elif b["VISUAL"] and scene is None and "screenshot" not in vis:
            problems.append(f"beat {b['name']}: VISUAL names no scene ({', '.join(sorted(ALL_SCENES))})")
    ctas = [b for b in script["beats"] if b["CTA"]]
    if len(ctas) != 1:
        problems.append(f"{len(ctas)} beats carry a CTA; exactly one (the honest limit) may")
    # HUBRICON_SPEC.md ("Content engine"): every piece points to /learn and closes on one calm
    # line; the home page's film (pillar 0) points to the call first. The Teardown is gone.
    cta_text = (h.get("CTA", "") + " " + " ".join(b["CTA"] for b in ctas)).lower()
    said = spoken(script).lower()
    if "/learn" not in cta_text:
        problems.append("the CTA must point to /learn (HUBRICON_SPEC.md: every piece points to /learn)")
    if pillar == 0 and "call" not in cta_text:
        problems.append("the home page's film points to the call first, then /learn")
    if "teardown" in cta_text or "teardown" in said:
        problems.append("the Teardown is killed (HUBRICON_SPEC.md); no script mentions it")
    if pillar in (3, 4, 5):
        for word in ("managed profit", "/apply", "capital position"):
            if word in cta_text or word in said:
                problems.append(f"pillar {pillar} must not mention “{word}”: the soft close names no product")
    # re-hook cadence: beat starts plus the audit's stamps
    stamps = sorted({b["at"] for b in script["beats"]} | {
        int(m.group(1)) * 60 + int(m.group(2)) for m in STAMP_RE.finditer(script["tail"].get("RE-HOOK AUDIT", ""))})
    for a, b in zip(stamps, stamps[1:]):
        if b - a > 40:
            problems.append(f"re-hook gap of {b - a}s between {a // 60}:{a % 60:02d} and {b // 60}:{b % 60:02d}")
    n = word_count(spoken(script), facts)
    lo, hi = WORDS.get(tier.upper(), (650, 2200))
    if not lo <= n <= hi:
        problems.append(f"{n} spoken words; tier {tier} wants {lo}–{hi}")
    return problems


def render(script: dict, facts: dict) -> dict:
    """The same structure with every placeholder replaced — what the voice reads."""
    out = json.loads(json.dumps(script))
    out["header"] = {k: render_facts(v, facts) for k, v in out["header"].items()}
    out["hooks"] = {int(k): render_facts(v, facts) for k, v in out["hooks"].items()}
    for b in out["beats"]:
        for f in ("VO", "CTA", "VISUAL"):
            b[f] = render_facts(b[f], facts)
    return out


def estimate_seconds(script: dict, facts: dict) -> int:
    return round(word_count(spoken(script), facts) / WPM * 60)


def keys_used(script: dict) -> list[str]:
    text = "\n".join([*script["header"].values(), *script["hooks"].values(), spoken(script)])
    return sorted(set(PLACEHOLDER.findall(text)))
