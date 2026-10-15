"""A script written elsewhere becomes a film (docs/content/SCRIPT_KIT.md).

    hubricon-content script-in <file> [--slug S] [--dry]

The founder drafts a script wherever he likes, in the kit's format: the script.md template with
every figure as a {{key}}, and a FACTS block at the end giving each key its value, label and
source. This takes it in, for no tokens:

1. splits off the FACTS block into the film's history.json (every figure needs a source);
2. writes the script as videos/<slug>/script.md;
3. builds facts.json (the engine's demo figures plus the film's own) and runs the script check;
4. adds the film to the queue as approved (his script is his approval), waiting on his takes.

Nothing is written unless the script checks clean: the problems come back as a list, to fix
wherever it was drafted. Once his takes are in (content/film/record.mjs), the runner's shell runs
the whole film line as code (FILM_LINE.md).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import script as scriptmod
from . import state

FACTS_HEAD = re.compile(r"^\s*(?:#+\s*)?FACTS\s*:?\s*$", re.M)
KEY = re.compile(r"^[a-z][a-z0-9_]*$")
SERIES_GREATS = re.compile(r"greats of commerce", re.I)
STOP = {"a", "an", "the", "of", "and", "for", "to", "in", "on", "its", "it", "his", "her", "here's", "what", "how", "why", "that", "this"}


def split(text: str) -> tuple[str, dict, list[str]]:
    """The script, its FACTS (key → {value, label, source}) and the problems with them."""
    m = FACTS_HEAD.search(text)
    if not m:
        return text.strip() + "\n", {}, []
    script, block = text[:m.start()].rstrip() + "\n", text[m.end():]
    facts, problems = {}, []
    for line in block.splitlines():
        line = line.strip()
        if not line or set(line) <= set("|-: ") or line.startswith("#"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if [c.lower() for c in cells[:2]] == ["key", "value"]:
            continue                      # a table's header row
        key = cells[0].strip("{} `")
        if len(cells) < 4 or not all(cells[:4]):
            problems.append(f"FACTS: `{line[:80]}` needs four parts: key | value | label | source")
            continue
        if not KEY.match(key):
            problems.append(f"FACTS: `{key}` is not a key (lower case, digits and _ only)")
            continue
        facts[key] = {"value": cells[1], "label": cells[2], "source": " | ".join(cells[3:])}
    return script, facts, problems


def header(script: str) -> dict:
    out = {}
    for line in script.splitlines():
        if line.strip() == "SCRIPT":
            break
        m = re.match(r"^([A-Z][A-Z ]+):\s*(.*)$", line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _slugify(title: str, n: int = 4, keep: bool = False) -> str:
    """A slug from a title (its first n words that carry meaning), or from SHORT kept as written."""
    words = [w for w in re.sub(r"\{\{[^}]*\}\}", " ", title).lower().replace("'", "").split()]
    words = [re.sub(r"[^a-z0-9]", "", w) for w in words]
    words = [w for w in words if w and (keep or w not in STOP)]
    return "-".join(words[:n]) or "film"


def name(head: dict, q: dict, slug: str | None = None) -> tuple[str, str]:
    """The film's unit id and slug: a Greats of Commerce film is G<n>, greats-<nn>-…; any other F<n>."""
    ids = [u["id"] for u in q["units"]]
    greats = SERIES_GREATS.search(head.get("SERIES", "")) or (slug or "").startswith("greats-")
    prefix = "G" if greats else "F"
    n = 1 + max((int(i[1:]) for i in ids if re.fullmatch(rf"{prefix}\d+", i)), default=0)
    if not slug:
        short = head.get("SHORT")
        slug = (f"greats-{n:02d}-" if greats else "") + (_slugify(short, 6, keep=True) if short else _slugify(head.get("TITLE", "")))
    return f"{prefix}{n:02d}", slug


def script_in(path: str | Path, slug: str | None = None, dry: bool = False) -> dict:
    from . import facts as factsmod
    text = Path(path).read_text(encoding="utf-8")
    script, history, problems = split(text)
    bad = {re.sub(r"^FACTS: `([^ |`]+).*", r"\1", p).strip("{} ") for p in problems}   # keys with a broken FACTS line
    head = header(script)
    for f in ("TITLE", "TIER", "PILLAR"):
        if not head.get(f):
            problems.append(f"the header needs `{f}:`")
    if "SCRIPT" not in [l.strip() for l in script.splitlines()]:
        problems.append("no `SCRIPT` line: the beats follow a line that reads SCRIPT")
    q = state.load()
    uid, slug = name(head, q, slug or head.get("SLUG"))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        problems.append(f"`{slug}` is not a slug (lower case, digits and hyphens)")
    if any(u.get("slug") == slug for u in q["units"]):
        problems.append(f"a film called {slug} is already in the queue: give it another SLUG")
    used = set(re.findall(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}", script))
    if not all(head.get(f) for f in ("TITLE", "TIER", "PILLAR")):
        return {"status": "refused", "slug": slug, "problems": problems}     # nothing further can be checked

    # the engine's demo figures (no history) tell which keys the script may use without a FACTS line
    base = factsmod.build_facts(factsmod.cached_run(), factsmod.load_data())
    missing = sorted(k for k in used if k not in history and k not in base and k not in bad)
    problems += [f"`{{{{{k}}}}}` is in the script but not in FACTS" for k in missing]
    tier, pillar = head["TIER"].strip().upper()[:1], int(re.sub(r"\D", "", head["PILLAR"]) or 0)
    cal = json.loads(state.CALENDAR.read_text(encoding="utf-8"))
    facts = dict(base)
    facts.update({k: {"value": f["value"], "label": f["label"], "source": f["source"]} for k, f in history.items()})
    problems += scriptmod.validate(scriptmod.parse(script), facts, tier, pillar, cal["cta_by_pillar"])
    if problems:
        return {"status": "refused", "slug": slug, "problems": problems}
    if dry:
        return {"status": "clean", "unit": uid, "slug": slug, "facts": len(history), "keys_used": len(used)}

    d = scriptmod.video_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / "script.md").write_text(script, encoding="utf-8")
    (d / "history.json").write_text(json.dumps(history, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    factsmod.write(slug)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = f"node content/film/record.mjs {slug}"
    reason = f"the founder's own takes: read the script at the teleprompter, {record} (docs/content/VOICE-RECORDING.md)"
    unit = {"id": uid, "phase": 3, "kind": "video", "day": None, "title": head["TITLE"], "pillar": pillar, "tier": tier,
            "slug": slug, "models": [], "status": "blocked", "blocked_on": reason, "requires_done": None, "voice": "own",
            "publishable": False, "review_notes": [], "attempts": {}}
    steps = state.VIDEO_STEPS_D if tier == "D" else state.VIDEO_STEPS
    unit["steps"] = {s: "todo" for s in steps}
    unit["steps"].update({"facts": "done", "script": "done", "critique": "done", "review": "approved",
                          "tts": "blocked", "upload": "blocked"})
    note = f"taken in from {Path(path).name}: the founder's script, checked clean ({len(history)} sourced figures)"
    unit["log"] = [{"at": now, "step": "script", "note": note}, {"at": now, "step": "tts", "note": f"blocked {reason}"}]
    q["units"].append(unit)
    state.save(q)
    return {"status": "ok", "unit": uid, "slug": slug, "facts": len(history), "next": f"record your takes: {record}"}


REFERENCE = state.CONTENT_DIR.parent / "docs" / "content" / "SCRIPT_REFERENCE.md"


def reference() -> Path:
    """docs/content/SCRIPT_REFERENCE.md, generated: the names a script may use (the visual styles, the
    chart scenes, the demo's figure keys), so a drafting tool outside this machine writes ones that exist."""
    from . import facts as factsmod
    from . import shots
    reg = shots.registry()
    lines = ["# Script reference (generated by `hubricon-content script-reference`; do not edit)", "",
             "The names a script may use, for the kit (SCRIPT_KIT.md). Give this file to your drafting tool with the kit.", "",
             "## Visual styles (a long film's every VISUAL names at least one)", "", "| Style | Kinds | Room |", "|---|---|---|"]
    for name, st in sorted(reg["styles"].items()):
        if not st.get("deferred"):
            lines.append(f"| `{name}` | {', '.join(st.get('kinds', []))} | {st.get('room', '')} |")
    lines += ["", "## Chart scenes (a VISUAL that draws one needs a DATA SOURCE line)", "",
              ", ".join(f"`{s}`" for s in sorted(scriptmod.CHART_SCENES)), "",
              "## The demo's figures (Tarnhollow demo data): keys a script may use without a FACTS line", "",
              "| Key | Value | What it is |", "|---|---|---|"]
    base = factsmod.build_facts(factsmod.cached_run(), factsmod.load_data())
    for k in sorted(base):
        f = base[k]
        lines.append(f"| `{k}` | {str(f.get('value', '')).replace('|', '/')} | {str(f.get('label', '')).replace('|', '/')} |")
    REFERENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REFERENCE
