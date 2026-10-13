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
               "MISCONCEPTION", "RUNTIME", "FORM",
               # packaging first: three titles and three thumbnail concepts, the chosen ones among them
               "TITLE 1", "TITLE 2", "TITLE 3", "THUMBNAIL 1", "THUMBNAIL 2", "THUMBNAIL 3"]
BEAT_RE = re.compile(r"^\[(\d+):(\d\d)\]\s*(.*)$")
FIELD_RE = re.compile(r"^\s+(VO|VISUAL|DATA SOURCE|CLIP|TEMPLATE|CTA|KEEP|TRY|BREATHE|MONTAGE):\s*(.*)$")
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
            m = re.match(r"^([A-Z][A-Z0-9 ]*):\s*(.*)$", line)
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
                       "VO": "", "VISUAL": "", "DATA SOURCE": "", "CLIP": "", "TEMPLATE": "", "CTA": "", "KEEP": "", "TRY": "", "BREATHE": "", "MONTAGE": ""}
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
    # an unknown key stays a placeholder here, so the number guard can name it instead of a crash
    filled = PLACEHOLDER.sub(lambda m: str(facts[m.group(1)]["value"]) if m.group(1) in facts else m.group(0), text) if facts else text
    return len(re.findall(r"[A-Za-z0-9$%'’.,-]+", filled))


def _banned(text: str) -> list[str]:
    low = text.lower()
    hits = []
    for phrase in BANNED:
        pat = r"\b" + re.escape(phrase) + r"\b" if " " not in phrase else re.escape(phrase)
        if re.search(pat, low):
            hits.append(phrase)
    return hits


# How people learn from a narrated film (docs/content/LEARNING_DESIGN.md), checked on a long film's script.
CHAPTER_WORDS = (225, 900)    # 1.5 to 6 minutes at 150 words a minute (Guo et al. 2014: engagement falls past ~6)
KEEP_WORDS = 12               # the takeaway is set as a kinetic-thesis card, 12 words at most
RECALL_MIN = 2                # the last chapter brings back at least this many of the film's earlier figures


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9{}_ ]+", "", re.sub(r"\s+", " ", text.lower())).strip()


THUMB_TEXT_WORDS = 4          # a thumbnail carries at most four words; a {{key}} figure is one


def thumbnail_concept(line: str) -> dict:
    """A concept line, "<the stakes, as a picture> | TEXT: <at most four words> [| PICTURE: <shot id or words>]"."""
    m = re.search(r"(?:^|[|·])\s*TEXT:\s*(.*?)\s*(?:[|·]\s*PICTURE:\s*(.*?)\s*)?$", line or "")
    if not m:
        return {"visual": (line or "").strip(" |·"), "text": "", "picture": None}
    return {"visual": line[:m.start()].strip(" |·"), "text": m.group(1).strip(), "picture": (m.group(2) or "").strip() or None}


def _same(a: str, b: str) -> bool:
    return _norm(a) == _norm(b)


def packaging(script: dict) -> list[str]:
    """Packaging first: three titles and three thumbnail concepts, the chosen TITLE and THUMBNAIL among them."""
    h, problems = script["header"], []
    titles = [h.get(f"TITLE {i}", "") for i in (1, 2, 3)]
    thumbs = [h.get(f"THUMBNAIL {i}", "") for i in (1, 2, 3)]
    for i, t in enumerate(titles, 1):
        if not t:
            problems.append(f"header field TITLE {i} missing: three title candidates, the chosen TITLE one of them")
    for i, t in enumerate(thumbs, 1):
        if not t:
            problems.append(f"header field THUMBNAIL {i} missing: three thumbnail concepts, the chosen THUMBNAIL one of them")
            continue
        c = thumbnail_concept(t)
        n = len(re.sub(r"\{\{\s*\w+\s*\}\}", "X", c["text"]).split())
        if not c["visual"] or not c["text"]:
            problems.append(f"THUMBNAIL {i}: write the stakes as a picture, then `| TEXT: <at most {THUMB_TEXT_WORDS} words>`")
        elif n > THUMB_TEXT_WORDS:
            problems.append(f"THUMBNAIL {i}: its text is {n} words; {THUMB_TEXT_WORDS} at most")
    if all(titles) and h.get("TITLE") and not any(_same(h["TITLE"], t) for t in titles):
        problems.append("TITLE must be one of TITLE 1–3, word for word")
    if all(thumbs) and h.get("THUMBNAIL") and not any(_same(h["THUMBNAIL"], t) for t in thumbs):
        problems.append("THUMBNAIL must be one of THUMBNAIL 1–3, word for word")
    return problems


def chapters(script: dict) -> list[dict]:
    """The film's chapters: the open, then each run of beats after a CHAPTER card."""
    out, cur = [], {"name": "the open", "beats": []}
    for b in script["beats"]:
        if b["name"].upper().startswith("CHAPTER"):
            out.append(cur)
            cur = {"name": re.sub(r"^CHAPTER\s*\d*\s*[—-]?\s*", "", b["name"], flags=re.I).strip() or b["name"], "beats": []}
        else:
            cur["beats"].append(b)
    out.append(cur)
    return [c for c in out if c["beats"]]


CTA_AFTER_TRY_S = 30                        # the one CTA follows the step to try (the doctrine, 2026-10-13)
FORMS = ("teardown", "method", "story")   # a week's films vary their shape (the queue keeps two alike apart)
CASE_FIGURES = 3                            # a teardown chapter carries one case: at least 3 figures from one source


def form_of(script: dict) -> str:
    return str(script["header"].get("FORM", "")).strip().lower()


def _case(source: str) -> str:
    """A figure's case: the document it comes from (a link's site and first path part, else its words)."""
    m = re.search(r"https?://([^/\s]+)(/[^/\s?#]*)?", source or "")
    return (m.group(1) + (m.group(2) or "")).lower() if m else re.sub(r"\s+", " ", (source or "").lower())[:60]


def learning(script: dict, facts: dict | None = None) -> list[str]:
    """The learning rules a long film's script is held to, by its FORM (LEARNING_DESIGN.md):

    - every form: chapters of 1.5–6 minutes, a step to try, a recall at the end;
    - method: a guess before each chapter's answer, and a takeaway per chapter;
    - teardown: a takeaway per chapter, and one chapter carried by a single sourced case;
    - story: one takeaway for the film."""
    problems, ch = [], chapters(script)
    form = form_of(script)
    if form not in FORMS:
        problems.append(f"FORM must be one of {', '.join(FORMS)} (the week's films vary their shape)")
    for c in ch[1:]:                                   # the open is the hook, not a lesson
        vo = " ".join(b["VO"] for b in c["beats"])
        n = len(vo.split())
        if not CHAPTER_WORDS[0] <= n <= CHAPTER_WORDS[1]:
            problems.append(f"chapter {c['name']}: {n} words (about {n / 150:.1f} min); a chapter runs "
                            f"{CHAPTER_WORDS[0]}–{CHAPTER_WORDS[1]} words, 1.5 to 6 minutes: split a long one at its steps")
        if form == "method" and "?" not in vo:
            problems.append(f"chapter {c['name']}: asks the viewer nothing; put a question before its answer "
                            "(a guess first makes the answer stick)")
        keeps = [b for b in c["beats"] if b.get("KEEP")]
        if form != "story" and len(keeps) != 1:
            problems.append(f"chapter {c['name']}: {len(keeps)} KEEP lines; one, on its last beat, the sentence the viewer keeps")
        for b in keeps:
            k = b["KEEP"]
            if len(k.split()) > KEEP_WORDS:
                problems.append(f"beat {b['name']}: KEEP is {len(k.split())} words; {KEEP_WORDS} at most")
            if _norm(k) not in _norm(b["VO"]):
                problems.append(f"beat {b['name']}: KEEP must be said word for word in the beat's VO (it is shown as it is spoken)")
    for b in script["beats"]:
        if b.get("BREATHE", "").lower().startswith("y") and b.get("MONTAGE", "").lower().startswith("y"):
            problems.append(f"beat {b['name']}: BREATHE and MONTAGE can't share a beat")
        if b.get("KEEP") and (b.get("BREATHE", "").lower().startswith("y") or b.get("MONTAGE", "").lower().startswith("y")):
            problems.append(f"beat {b['name']}: a KEEP line is set as its own card; give BREATHE or MONTAGE to another beat")
    beats = script["beats"]
    tries = [i for i, b in enumerate(beats) if b.get("TRY", "").lower().startswith("y")]
    ctas = [b for b in beats if b.get("CTA")]
    if tries and len(ctas) == 1:
        t = tries[-1]
        end = beats[t + 1]["at"] if t + 1 < len(beats) else beats[t]["at"]
        if not beats[t]["at"] <= ctas[0]["at"] <= end + CTA_AFTER_TRY_S:
            problems.append(f"the CTA (at {ctas[0]['at'] // 60}:{ctas[0]['at'] % 60:02d}) must come within {CTA_AFTER_TRY_S} s after "
                            f"the TRY beat ends: the viewer is pointed onward while the step is fresh")
    if form == "story" and not any(b.get("KEEP") for b in script["beats"]):
        problems.append("a story film needs one KEEP line: the sentence the viewer keeps from the whole film")
    if form == "teardown" and facts is not None:
        demo = lambda k: "demo" in str((facts.get(k) or {}).get("source", "")).lower()
        def one_case(c):
            keys = {k for b in c["beats"] for k in PLACEHOLDER.findall(b["VO"]) if k in facts and not demo(k)}
            cases = {_case(facts[k].get("source", "")) for k in keys}
            return len(keys) >= CASE_FIGURES and len(cases) == 1
        if not any(one_case(c) for c in ch[1:]):
            problems.append(f"a teardown needs one chapter carried by a single real case: at least {CASE_FIGURES} of its figures "
                            "from one sourced case study (not demo data)")
    if not any(b.get("TRY", "").lower().startswith("y") for b in script["beats"]):
        problems.append("no TRY beat: mark the beat that gives the viewer the step to do this week with `TRY: yes`")
    if len(ch) > 2:
        earlier = {k for c in ch[:-1] for b in c["beats"] for k in PLACEHOLDER.findall(b["VO"])}
        last = {k for b in ch[-1]["beats"] for k in PLACEHOLDER.findall(b["VO"])}
        if len(last & earlier) < RECALL_MIN:
            problems.append(f"the last chapter brings back {len(last & earlier)} of the film's earlier figures; "
                            f"at least {RECALL_MIN}, so the ending is a recall")
    return problems


def validate(script: dict, facts: dict, tier: str, pillar: int, cta_rules: dict) -> list[str]:
    problems = []
    h = script["header"]
    for k in ("TITLE", "THUMBNAIL", "CTA", "SPIKY CLAIM", "MISCONCEPTION", "TIER", "PILLAR"):
        if not h.get(k):
            problems.append(f"header field {k} missing")
    # number guard on everything a viewer hears or reads
    seen = lambda line: " ".join(v for k, v in thumbnail_concept(line).items() if k != "picture" and v)   # a PICTURE shot id is not shown
    prose = {"TITLE": h.get("TITLE", ""), "THUMBNAIL": seen(h.get("THUMBNAIL", "")), "CTA": h.get("CTA", "")}
    prose.update({k: (seen(h[k]) if k.startswith("THUMBNAIL") else h[k])
                  for k in ("TITLE 1", "TITLE 2", "TITLE 3", "THUMBNAIL 1", "THUMBNAIL 2", "THUMBNAIL 3") if h.get(k)})
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
        problems.append(f"{len(ctas)} beats carry a CTA; exactly one may")
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
    rehook = not (tier.upper() == "D" and form_of(script) in ("teardown", "story"))   # the 40 s re-hook is a method film's rule
    for a, b in zip(stamps, stamps[1:]) if rehook else []:
        if b - a > 40:
            problems.append(f"re-hook gap of {b - a}s between {a // 60}:{a % 60:02d} and {b // 60}:{b % 60:02d}")
    n = word_count(spoken(script), facts)
    lo, hi = WORDS.get(tier.upper(), (650, 2200))
    if not lo <= n <= hi:
        problems.append(f"{n} spoken words; tier {tier} wants {lo}–{hi}")
    if tier.upper() == "D":
        problems += packaging(script) + learning(script, facts)
    return problems


def render(script: dict, facts: dict) -> dict:
    """The same structure with every placeholder replaced — what the voice reads."""
    out = json.loads(json.dumps(script))
    out["header"] = {k: render_facts(v, facts) for k, v in out["header"].items()}
    out["hooks"] = {int(k): render_facts(v, facts) for k, v in out["hooks"].items()}
    for b in out["beats"]:
        for f in ("VO", "CTA", "VISUAL", "KEEP"):
            b[f] = render_facts(b.get(f, ""), facts)
    return out


def estimate_seconds(script: dict, facts: dict) -> int:
    return round(word_count(spoken(script), facts) / WPM * 60)


def keys_used(script: dict) -> list[str]:
    text = "\n".join([*script["header"].values(), *script["hooks"].values(), spoken(script)])
    return sorted(set(PLACEHOLDER.findall(text)))
