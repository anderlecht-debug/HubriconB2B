"""The one file a planning session reads (docs/content/FILM_LINE.md): everything a shot plan needs,
condensed, so the session doesn't read the spec, the skill, the style registry and a word-by-word
timing (about 100k tokens) to make decisions that need about 20k.

    hubricon-content plan-brief <slug>   → videos/<slug>/plan-brief.md

It holds:
- the rules (the shot-plan skill);
- the plan fields the v3 stage honours;
- the styles, one line each;
- the figures the voice says, one line each;
- the beats, sentence by sentence, each with its start, its figures and the legal cuts at its end.
Costs no tokens.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

SKILL = CONTENT_DIR.parent / ".claude" / "skills" / "shot-plan" / "SKILL.md"

PARAMS = """\
## The plan fields the v3 stage honours (times are seconds from the shot's first frame)

| Kind | Field | Meaning |
|---|---|---|
| document | `lines`, `line`, `source` | The page's lines (verbatim from a real source, or "Typeset from …" in `source`); `line` is the one the camera reads. |
| document | `visits: [{text, at, mark}]`, `opening: "page"\\|"tight"` | Camera waypoints on phrases printed on the page (`mark: true` swipes the highlighter); open on the whole page or tight. |
| table | `rows`, `columns`, `row`, `cell`, `type_values` | A typeset table; `type_values: true` types each cell on its word. |
| number | `value` (`{{key}}`), `sub`, `estimate` | One hero figure and a context line. |
| pair | `left`/`right` `{value, label, at}`, `gap`, `gap_at`, `question` | Two figures to compare; `gap` is the line under them. |
| formula | `terms: [{text, at}]`, `ops`, `caption` | A sum drawn term by term on its words. |
| timeline | `layout: "dates"\\|"bars"\\|"share"\\|"ledger"\\|"step"`, `events: [{date, label, at}]`, `heading` | Only `dates` is a line in time; `bars` are quantities to scale; `step` is prices or weights on either side of an edge. |
| chart | `chart: {"scene": …}`, `params.builds` | A case-study chart (`staircase`, `staircases`, `aging`, `waterfall`, `montecarlo`, `catalogue`); `builds` = seconds when something new lands. |
| quote, kinetic | `text` / `lines`, `attribution` | Words land on their onsets. |
| still | `enter: "dive"`, `exit: "surface"`, `focus: [x, y]`, `motion` | A full-frame picture; dive in from a print on the desk, surface back to one. |
| archive | `focus`, `params.trim`, `params.treat: "object"` | A print or a museum object on the desk. |
| number, pair, formula, kinetic, timeline | `params.print: {want, at, caption}` | A companion picture on the desk beside the type: give it whenever the type would stand alone. |
| any | `style: "callback"`, `params.callback: "<shot id>"` | Draw an earlier shot again; it continues that shot's layout. |
"""


def _sentences(words: list[dict]) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?…][\"'’”)]*$", w["word"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build(slug: str) -> Path:
    from . import shots
    d = scriptmod.video_dir(slug)
    timing, _ = shots.load_timing(d)
    facts = scriptmod.load_facts(slug)
    reg = shots.registry()
    cuts = sorted(float(c["t"]) for c in timing.get("cutpoints", []))
    spoken = {}
    for r in shots.spoken_reveals(timing):
        spoken.setdefault(round(float(r["t"]), 2), []).append(r["key"])
    lines = [f"# Plan brief: {slug}", "",
             f"Narration {float(timing['duration']):.1f} s. Write `videos/{slug}/shots.json` as "
             '`{"slug": …, "mode": "history"|"explainer", "fps": 30, "shots": [...]}`, then run '
             f"`content/.venv/bin/hubricon-content shots-fill {slug}` and `… shots-validate {slug}` and fix "
             "until it prints clean. Screen-mix shares are advisory. Do not read any other file: everything is here.", ""]
    skill = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    skill = re.sub(r"^---.*?---\s*", "", skill, flags=re.S)
    lines += ["## The rules (the shot-plan skill)", "", skill.strip(), "", PARAMS, "## Styles (name: kinds · room · seconds)", ""]
    for name, st in sorted(reg["styles"].items()):
        if st.get("deferred"):
            continue
        lines.append(f"- `{name}`: {', '.join(st.get('kinds', []))} · {st.get('room', '?')} · {st.get('seconds', '')}")
    lines += ["", "## The figures the voice says ({{key}} = value: label)", ""]
    said = sorted({k for ks in spoken.values() for k in ks})
    for k in said:
        f = facts.get(k, {})
        lines.append(f"- `{{{{{k}}}}}` = {f.get('value', '')}: {f.get('label', '')}")
    plan_p = d / "shots.json"
    if plan_p.exists():
        return _with_shots(d, slug, lines, json.loads(plan_p.read_text(encoding="utf-8")), timing, spoken)
    lines += ["", "## The beats, sentence by sentence", "",
              "Each sentence: `[start] text` then its figures `{{key}}@t`, then `cut:` the legal cut at its end (if any).", ""]
    for seg in timing["segments"]:
        if seg["kind"] == "card":
            lines.append(f"### Chapter card at {float(seg['start']):.2f}–{float(seg['end']):.2f} s: {seg.get('title', '')} (a fixed 2.5 s card; style `chapter`)")
            continue
        if seg["kind"] != "beat":
            continue
        visual = re.sub(r"\s+", " ", str(seg.get("visual") or "")).strip()
        lines.append(f"### Beat {seg.get('index', '?')} ({float(seg['start']):.2f}–{float(seg['end']):.2f} s)" + (f". VISUAL: {visual}" if visual else ""))
        for sent in _sentences(seg.get("words", [])):
            a, b = float(sent[0]["start"]), float(sent[-1]["end"])
            figs = [f"{{{{{k}}}}}@{t:.2f}" for t, ks in spoken.items() if a - 0.05 <= t <= b + 0.05 for k in ks]
            near = [c for c in cuts if b - 0.05 <= c <= b + 1.5]
            text = " ".join(w["word"] for w in sent)
            lines.append(f"- [{a:.2f}] {text}" + (f"  {' '.join(figs)}" if figs else "") + (f"  cut: {near[0]:.2f}" if near else ""))
        lines.append("")
    out = d / "plan-brief.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


DECISIONS = """\
## What you return

The shots below were drafted by code: their cuts are legal and fixed, a figure stays on screen 3 s,
and each says what is spoken under it. Decide each shot. Write ONE file,
`content/videos/{slug}/decisions.json`, in a single write:

    {{"mode": "history", "shots": {{"s001": {{"kind": …, "style": …, "on": …, "params": {{…}}, "query": ["…"], "sources": ["…"],
      "fallback": "…", "specific": "…", "intent": "…"}}, "s002": {{…}}, …}}}}

- Give only the fields you set; a field you leave keeps the draft's value.
- Keep `intent` to eight words or fewer.
- A paper shot (it holds a figure) stays paper: choose its kind, style and params (values as `{{{{key}}}}`, never typed).
  Give it `params.print` with a `want` ({{"query": "…", "sources": ["smithsonian", "commons"]}}) when a true picture
  fits the sentence.
- A world shot: choose still, footage or archive, with `query` (the sentence's concrete nouns), `sources` and
  `fallback`, and `specific` when the sentence names a real company, person, place or event.
- Follow each beat's VISUAL brief where it names a picture.
- Do not run commands and do not read other files. Reply with the number of shots decided.
"""


def _with_shots(d, slug, lines, plan, timing, spoken):
    from . import shots as shotmod
    words = shotmod.spoken(timing)
    lines += ["", DECISIONS.format(slug=slug), "## The shots, drafted by code", ""]
    beat = None
    for s in plan["shots"]:
        if s.get("beat") != beat:
            beat = s.get("beat")
            v = s.get("visual") or ""
            lines.append(f"### Beat {beat}" + (f". VISUAL: {v}" if v else ""))
        said = " ".join(w["word"] for w in shotmod.words_in(words, s["start"], s["end"]))
        figs = [f"{{{{{k}}}}}@{t:.2f}" for t, ks in spoken.items() if s["start"] - 0.05 <= t < s["end"] for k in ks]
        lines.append(f"- {s['id']} [{s['start']:.2f}–{s['end']:.2f}] {s['room']} {s['kind']}/{s['style']}"
                     + (f" {' '.join(figs)}" if figs else "") + f" | {said}")
    out = d / "plan-brief.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
