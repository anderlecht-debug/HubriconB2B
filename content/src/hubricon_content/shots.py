"""The shot plan of a long film, and what `shots-validate` holds it to.

`content/videos/<slug>/shots.json` (VISUAL_SPEC.md §7.3) names every shot of a
tier-D film: its time on the narration, its room (paper or world), its kind,
its style from the library (§14), and, after the pick, its asset. The plan is
written by the `shot-plan` skill and checked here against §4 (cadence), §5
(screen time), §7.4 (the eight rules) and §14.8 (variety). Every number the
checks use lives in content/film/styles.json.
"""

from __future__ import annotations

import functools
import json
import re
import statistics
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

STYLES_JSON = CONTENT_DIR / "film" / "styles.json"
USAGE = CONTENT_DIR / "assets" / "usage.json"
PROOF_LABEL = "Modeled from public data · Not a client · Not a result"
TOL = 1 / 30 + 1e-3            # one frame
REVEAL_TOL = 0.05
USAGE_WINDOW = 10              # an asset is not used again within the next ten films (§6.7)
# Licences an asset may carry (§6.3): the source's own licence, or a public-domain mark.
LICENCES = {"pexels", "pixabay", "no known restrictions", "no restrictions", "cc0", "public domain", "cc by", "higgsfield"}   # "no restrictions": the founder's call, 2026-10-07
MOTIONS = {"still-push": {"push", "pull"}, "still-pan": {"pan-left", "pan-right", "pan-up", "pan-down"},
           "still-reveal": {"reveal"}, "still-depth": {"depth"}, "texture": {"push", "drift"}}
OPENERS = {"chapter", "document", "number", "pair", "table", "quote"}   # a change of texture (§4)


def licence_ok(licence: str) -> bool:
    """§6.3's accept list: Pexels, Pixabay, no known restrictions, CC0, public domain,
    CC BY. Share-alike, non-commercial, no-derivatives, fair use and unknown are refused."""
    x = str(licence).lower().replace("_", " ")
    if re.search(r"\b(by-?sa|sa|nc|nd|non-?commercial|no-?deriv\w*|share-?alike|fair use|unknown)\b", x):
        return False
    return any(k in x for k in LICENCES)


@functools.lru_cache(maxsize=1)
def registry() -> dict:
    return json.loads(STYLES_JSON.read_text(encoding="utf-8"))


def end_tail(plan: dict, reg: dict | None = None) -> float:
    """Seconds the end card holds after the narration's last word (styles.json end.tail_s), when the
    film ends on one; the film then runs the narration plus this tail."""
    last = (plan.get("shots") or [{}])[-1]
    if last.get("kind") != "end":
        return 0.0
    return float(((reg or registry())["styles"].get("end") or {}).get("tail_s", 0.0))


def names(name: str, text: str) -> bool:
    """Whether a record names `name` (§6.2): the phrase itself; every word of it in any order, as a
    catalogue writes a person ("WOOD, ROBERT E."); or the given names as initials before the
    surname ("R.E. Wood", "R. E. Wood"). A company's name still needs every one of its words."""
    t = str(text).lower()
    if not name or name.lower() in t:
        return bool(name)
    toks = re.findall(r"[a-z0-9]+", name.lower())
    if toks and set(toks) <= set(re.findall(r"[a-z0-9]+", t)):
        return True
    if len(toks) >= 2:
        *given, last = toks
        initials = r"\.?\s*".join(re.escape(g[0]) for g in given)
        return re.search(rf"\b{initials}\.?\s*{re.escape(last)}\b", t) is not None
    return False


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9$%]", "", w.lower())


def load_timing(d: Path) -> tuple[dict | None, str]:
    """The real timing when narration exists, else the 150-wpm estimate."""
    for name, note in (("timing.json", ""), ("timing.estimate.json", " (on estimated timing: no voice yet)")):
        if (d / name).exists():
            return json.loads((d / name).read_text(encoding="utf-8")), note
    return None, ""


def spoken(timing: dict) -> list[dict]:
    return [w for s in timing["segments"] if s["kind"] == "beat" for w in s.get("words", [])]


def spoken_reveals(timing: dict) -> list[dict]:
    """Every spoken figure with its second: each mention (`spoken`), or, in a timing
    written before 2026-10-04, the last mention of each key (`reveals`)."""
    out = []
    for s in timing["segments"]:
        if s["kind"] != "beat":
            continue
        if "spoken" in s:
            out += [{"key": r["key"], "t": float(r["t"])} for r in s["spoken"]]
        else:
            out += [{"key": k, "t": float(r["t"])} for k, r in s.get("reveals", {}).items()]
    return out


def words_in(words: list[dict], start: float, end: float) -> list[dict]:
    """The words a shot carries: those whose middle falls inside it."""
    return [w for w in words if start <= (w["start"] + w["end"]) / 2 < end]


def group_of(shot: dict, reg: dict) -> str:
    st = reg["styles"].get(shot.get("style"), {})
    g = st.get("group", "by-kind")
    if g == "by-kind":
        g = reg["group_of_kind"].get(shot.get("kind"), "numbers")
    if g == "stock" and shot.get("sources") and set(shot["sources"]) <= set(reg["sources"]["archival"]):
        g = "archival"   # archival film plays as footage
    return g


def resolve_on(shot: dict, words: list[dict]) -> float | None:
    """The time of the word or {{key}} a style's main event lands on, or None."""
    on = shot.get("on")
    if on is None:
        return None
    m = re.fullmatch(r"\{\{\s*([a-z0-9_]+)\s*\}\}", on)
    if m:
        hit = [r for r in shot.get("reveals", []) if r.get("key") == m.group(1)]
        return float(hit[0]["t"]) if hit else None
    target = [_norm(t) for t in on.split() if _norm(t)]
    inside = words_in(words, shot["start"], shot["end"])
    norm = [_norm(w["word"]) for w in inside]
    for i in range(len(norm) - len(target) + 1):
        if norm[i:i + len(target)] == target:
            return inside[i]["start"]
    return None


def _cliche(query: str, cliches: list[str]) -> str | None:
    q = query.lower()
    return next((c for c in cliches if re.search(rf"\b{re.escape(c)}\b", q)), None)


def _runs(shots: list[dict], key) -> list[tuple[list[dict], object]]:
    runs = []
    for s in shots:
        k = key(s)
        if runs and runs[-1][1] == k:
            runs[-1][0].append(s)
        else:
            runs.append(([s], k))
    return runs


# What each paper kind draws, as the stage reads it (film/v3/kinds): any one of the field sets will do. Without
# one the stage shows the bare desk for the whole shot (G02, 2026-10-07: 25 shots, a timeline up to 16 s, after a
# decision's params replaced the drafted ones). A number or pair falls back to its spoken figure; kinetic type to its words.
CONTENT = {"timeline": [("events",)], "pair": [("left", "right"), ("reveals",)], "number": [("value",), ("reveals",)],
           "formula": [("terms",)], "quote": [("text",)]}


def draws(s: dict) -> bool:
    """The shot has something to draw (a callback draws its target's)."""
    alts = CONTENT.get(s.get("kind"))
    p = s.get("params") if isinstance(s.get("params"), dict) else {}
    return not alts or s.get("style") == "callback" or any(all(p.get(f) or s.get(f) for f in alt) for alt in alts)


def validate(plan: dict, timing: dict, facts: dict, picked: bool = False, usage: dict | None = None) -> list[str]:
    reg = registry()
    cad, var = reg["cadence"], reg["variety"]
    problems: list[str] = []
    p = problems.append
    shots = plan.get("shots") or []
    mode = plan.get("mode")
    if mode not in reg["shares"]:
        p(f"mode {mode!r}: choose explainer or history (§5)")
    if not shots:
        return problems + ["no shots"]
    ids = [s.get("id") for s in shots]
    if len(set(ids)) != len(ids):
        p("shot ids repeat")
    by_id = {s.get("id"): s for s in shots}
    words, duration = spoken(timing), float(timing["duration"])
    cuts = [c["t"] for c in timing.get("cutpoints", [])]
    styles = reg["styles"]

    # ── 8. every shot a known style, allowed for its room and kind; every `on` found ──
    for s in shots:
        sid, st = s.get("id"), styles.get(s.get("style"))
        if not draws(s):
            p(f"{sid}: a {s['kind']} with no {' or '.join('/'.join(a) for a in CONTENT[s['kind']])}: it draws an empty desk")
        if st is None:
            p(f"{sid}: style {s.get('style')!r} is not in the library (§14)")
            continue
        if st.get("deferred"):
            p(f"{sid}: {s['style']} is {st['deferred']}")
        room = s.get("room")
        if room not in ("paper", "world") or (st["room"] != "either" and room != st["room"]):
            p(f"{sid}: {s['style']} belongs in the {st['room']} room, not {room!r}")
        if s.get("kind") not in st["kinds"] or s.get("kind") not in reg["kinds"].get(room, []):
            p(f"{sid}: {s['style']} renders as {'/'.join(st['kinds'])}, not {s.get('kind')!r} in {room!r}")
        if st["on"] == "required" and not s.get("on"):
            p(f"{sid}: {s['style']} lands on a word: set `on`")
        if st["on"] == "none" and s.get("on"):
            p(f"{sid}: {s['style']} has no `on` event")
        if s.get("on") and resolve_on(s, words) is None:
            p(f"{sid}: `on` {s['on']!r} is not spoken inside the shot")
        if st.get("needs_chart") and not (isinstance(s.get("chart"), dict) and s["chart"].get("scene")):
            p(f"{sid}: {s['style']} needs `chart` with its `scene`")
        if st.get("params", {}).get("clipping") and not s.get("params", {}).get("clipping"):
            p(f"{sid}: doc-clipping sets params.clipping")
        if st.get("needs_callback"):
            back = by_id.get(s.get("params", {}).get("callback"))
            if not back or ids.index(back["id"]) >= ids.index(sid) or back.get("kind") != s.get("kind"):
                p(f"{sid}: a callback names an earlier shot of the same kind in params.callback")
        if st.get("illustration") and not s.get("overlay", {}).get("illustration"):
            p(f"{sid}: an AI image carries overlay.illustration (§3.3, §7.4 rule 7)")
        if st.get("silent") and words_in(words, s["start"], s["end"]):
            p(f"{sid}: a breath has no narration under it (§14.5, C2)")
        if st.get("max_words") and len(s.get("says", "").split()) > st["max_words"]:
            p(f"{sid}: a thesis line is {st['max_words']} words at most")
        if not s.get("intent"):
            p(f"{sid}: write the intent, one line")

    shots = sorted(shots, key=lambda s: float(s.get("start", 0)))

    # ── 1. the shots cover the narration exactly, cut only where a cut is legal ──
    if abs(float(shots[0]["start"])) > TOL:
        p(f"{shots[0]['id']}: the film starts at 0.000, not {shots[0]['start']}")
    if abs(float(shots[-1]["end"]) - duration) > TOL:
        p(f"{shots[-1]['id']}: the last shot ends at {duration:.3f}, the narration's end, not {shots[-1]['end']}")
    for a, b in zip(shots, shots[1:]):
        if abs(float(a["end"]) - float(b["start"])) > TOL:
            p(f"{a['id']} → {b['id']}: {'gap' if b['start'] > a['end'] else 'overlap'} of {abs(b['start'] - a['end']):.3f} s")
        if cuts and min(abs(float(a["end"]) - c) for c in cuts) > TOL:
            p(f"{a['id']} → {b['id']}: the cut at {a['end']:.3f} is not a legal cut (a sentence end, a pause or a beat)")
    for s in shots:
        heard = " ".join(_norm(w["word"]) for w in words_in(words, s["start"], s["end"]))
        if heard != " ".join(_norm(w) for w in s.get("says", "").split() if _norm(w)):
            p(f"{s['id']}: `says` is not the narration under the shot")

    # ── 2. cadence (§4) and screen time (§5) ──
    length = {s["id"]: float(s["end"]) - float(s["start"]) for s in shots}
    for s in shots:
        L, st = length[s["id"]], styles.get(s.get("style"), {})
        lo, hi = st.get("seconds", [cad["min_s"], cad["max_s"]])
        if s.get("style") != "chapter" and not (lo - cad["style_length_slack_s"] - TOL <= L <= hi + cad["style_length_slack_s"] + TOL):
            p(f"{s['id']}: {L:.1f} s; {s.get('style')} runs {lo:g}–{hi:g} s")
        if s.get("style") not in ("chapter", "breath") and L < cad["min_s"] - TOL:
            p(f"{s['id']}: {L:.1f} s is under the {cad['min_s']:g} s floor")
        ceiling = cad["chart_max_s"] if s.get("kind") in ("chart", "timeline") else cad["max_s"]
        if L > ceiling + TOL:
            p(f"{s['id']}: {L:.1f} s is over the {ceiling:g} s ceiling for a {s.get('kind')}")
        if s.get("kind") in ("chart", "timeline") and L > cad["max_s"]:
            landings = sorted([float(s["start"]), float(s["end"])] + [float(r["t"]) for r in s.get("reveals", [])]
                              # builds are seconds from the shot's start (a plan before 2026-10-06 wrote film seconds)
                              + [float(t) if float(t) >= float(s["start"]) else float(s["start"]) + float(t)
                                 for t in s.get("params", {}).get("builds", [])]
                              + ([resolve_on(s, words)] if resolve_on(s, words) is not None else []))
            if max(b - a for a, b in zip(landings, landings[1:])) > cad["chart_landing_every_s"] + TOL:
                p(f"{s['id']}: a long chart needs something new every {cad['chart_landing_every_s']:g} s (reveals or params.builds)")
        for r in s.get("reveals", []):
            held = float(s["end"]) - float(r["t"])
            # a figure still on paper in the shots that follow keeps being held across the cut
            k = shots.index(s) + 1
            while held < cad["hold_after_number_s"] - TOL and k < len(shots) and shots[k].get("room") == "paper" \
                    and "{{" + r["key"] + "}}" in json.dumps(shots[k].get("params") or {}).replace(" ", ""):
                held += length[shots[k]["id"]]
                k += 1
            if held < cad["hold_after_number_s"] - TOL:
                p(f"{s['id']}: {{{{{r['key']}}}}} is on screen {held:.1f} s; hold a number {cad['hold_after_number_s']:g} s")
        src = str((s.get("params") or {}).get("source") or "")
        if re.search(r"[\w./-]+\.(json|xlsx|csv|py|mjs)\b", src):
            p(f"{s['id']}: its source line names a repository file ({src[:60]}…); name the public source")
        if s.get("style") == "bars-recall" and s.get("reveals"):
            p(f"{s['id']}: a recall draws figures already said; {', '.join(r['key'] for r in s['reveals'])} lands here")
        if float(s["start"]) >= cad["open_s"] and s.get("room") == "world" and s.get("kind") == "footage" \
                and L < 6 - TOL and s.get("style") not in ("footage-insert", "footage-process", "breath"):
            p(f"{s['id']}: after the first minute only inserts and process shots are footage under 6 s")
    # A chapter card is the timing's card segment, 2.5 s on tier D (§4), shot for shot.
    cards = [(float(c["start"]), float(c["end"])) for c in timing["segments"] if c["kind"] == "card"]
    chapter_shots = [(float(s["start"]), float(s["end"])) for s in shots if s.get("style") == "chapter"]
    for a, b in cards:
        if not any(abs(a - x) <= TOL and abs(b - y) <= TOL for x, y in chapter_shots):
            p(f"{a:.1f}–{b:.1f} s: the timing's chapter card needs a `chapter` shot exactly over it")
    for x, y in chapter_shots:
        if not any(abs(a - x) <= TOL and abs(b - y) <= TOL for a, b in cards):
            p(f"{x:.1f}–{y:.1f} s: a `chapter` shot sits only on a chapter card of the timing")

    def held(s):
        """A paper shot in the first minute may run past 8 s only as far as the first
        legal cut after its last figure's 3-second hold: a number must be readable."""
        if not s.get("reveals") or not cuts:
            return False
        need = max(float(r["t"]) for r in s["reveals"]) + cad["hold_after_number_s"]
        first = min((c for c in cuts if c >= need - TOL), default=None)
        return first is not None and float(s["end"]) <= first + TOL
    opening = [length[s["id"]] for s in shots if float(s["start"]) < cad["open_s"] and not held(s)]
    if opening and statistics.median(opening) > cad["open_median_s"] + TOL:
        p(f"the first minute's median shot is {statistics.median(opening):.1f} s; keep it at {cad['open_median_s']:g} s or under")
    for s in shots:
        if float(s["start"]) < cad["open_s"] and length[s["id"]] > cad["open_max_s"] + TOL and not held(s):
            p(f"{s['id']}: {length[s['id']]:.1f} s inside the first minute; nothing there runs over {cad['open_max_s']:g} s")
    for run, room in _runs(shots, lambda s: s.get("room")):
        span = float(run[-1]["end"]) - float(run[0]["start"])
        limit = cad["world_run_s"] if room == "world" else cad["paper_run_s"]
        if span > limit + TOL:
            p(f"{run[0]['id']}–{run[-1]['id']}: {span:.0f} s in the {room} room; {limit:g} s at most")
    for run, kind in _runs(shots, lambda s: s.get("kind")):
        if len(run) > cad["same_kind_run"]:
            p(f"{run[0]['id']}–{run[-1]['id']}: {len(run)} {kind} shots in a row; {cad['same_kind_run']} at most")
    events, run_start, prev_room = [0.0], 0.0, None
    for s in shots:
        if s.get("room") != prev_room:
            if prev_room is not None and float(s["start"]) - run_start >= 60:
                events.append(float(s["start"]))
            run_start, prev_room = float(s["start"]), s.get("room")
        if s.get("kind") in OPENERS:
            events.append(float(s["start"]))
    events.append(duration)
    events.sort()
    for a, b in zip(events, events[1:]):
        if b - a > cad["texture_change_s"] + TOL:
            p(f"{a:.0f}–{b:.0f} s: {b - a:.0f} s without a change of texture (a chapter, document or number); {cad['texture_change_s']:g} s at most")
    if mode in reg["shares"]:
        totals: dict[str, float] = {}
        for s in shots:
            totals[group_of(s, reg)] = totals.get(group_of(s, reg), 0.0) + length[s["id"]]
        for g, (lo, hi) in reg["shares"][mode].items():
            share = totals.get(g, 0.0) / duration
            if not (lo - 0.005 <= share <= hi + 0.005):
                p(f"{g}: {share:.0%} of the runtime; a {mode} film keeps it within {lo:.0%}–{hi:.0%} (§5)")

    # ── 3. every spoken figure revealed on paper at its second; none in the world ──
    def holder(t):
        return next((s for s in shots if float(s["start"]) - 1e-6 <= t < float(s["end"])), None)
    for r in spoken_reveals(timing):
        s = holder(r["t"])
        if s is None:
            continue
        if s.get("room") != "paper":
            p(f"{s['id']}: {{{{{r['key']}}}}} is spoken at {r['t']:.2f} s under a world shot; figures live on paper")
        elif not any(x.get("key") == r["key"] and abs(float(x["t"]) - r["t"]) <= REVEAL_TOL for x in s.get("reveals", [])):
            p(f"{s['id']}: reveal {{{{{r['key']}}}}} at {r['t']:.2f} s, the second it is spoken")
    said = {(r["key"], round(r["t"], 2)) for r in spoken_reveals(timing)}
    for s in shots:
        for x in s.get("reveals", []):
            if not any(x.get("key") == k and abs(float(x["t"]) - t) <= REVEAL_TOL for k, t in said):
                p(f"{s['id']}: reveals {{{{{x.get('key')}}}}} at {x.get('t')}, which the narration does not say then")
        if s.get("room") == "world":
            if s.get("reveals"):
                p(f"{s['id']}: a world shot carries no reveal")
            ov = s.get("overlay") or {}
            for k, v in ov.items():
                if isinstance(v, str) and re.search(r"\d", v) and not (k == "place" and re.search(r"\b1[6-9]\d\d|20\d\d\b", v)):
                    p(f"{s['id']}: a figure in the world room ({k}: {v!r}); only a provenance date may appear")

    # ── 4. a named company, person, place or event is shown only by its own evidence ──
    arch = set(reg["sources"]["archival"])
    for s in shots:
        name = s.get("specific")
        if not name:
            continue
        sourced = s.get("room") == "world" or s.get("kind") in ("archive", "stack", "split")
        if sourced and (s.get("kind") == "texture" or not s.get("sources") or not set(s["sources"]) <= arch):
            p(f"{s['id']}: names {name!r}; only archival sources may show it, never stock or AI (§6.2)")
        if picked and sourced:
            assets = s.get("asset") if isinstance(s.get("asset"), list) else [s.get("asset") or {}]
            text = " ".join(str(a.get(k, "")) for a in assets for k in ("title", "description", "url", "credit", "subject"))
            if not names(name, text):
                p(f"{s['id']}: the picked asset's provenance does not name {name!r}")

    # ── 5. world shots query concrete nouns, never a cliché; 6. no asset twice ──
    cliches = reg["cliches"]
    sourced_kinds = {"footage", "still", "texture", "archive", "stack", "split"}
    for s in shots:
        if s.get("kind") not in sourced_kinds:
            continue
        if not s.get("query"):
            p(f"{s['id']}: a sourced shot needs a query of the sentence's concrete nouns")
        for q in s.get("query") or []:
            c = _cliche(q, cliches)
            if c:
                p(f"{s['id']}: query {q!r} asks for {c!r}, a banned cliché (§6.1)")
        if not s.get("sources"):
            p(f"{s['id']}: name the sources this shot may use (§6.3)")
        if not s.get("fallback"):
            p(f"{s['id']}: set the fallback (archival → stock → texture → paper:kinetic)")
    if picked:
        used = []
        prior = set()
        for film in (usage or {}).get("films", [])[-USAGE_WINDOW:]:
            if film.get("slug") != plan.get("slug"):
                prior |= set(film.get("assets", []))
        prev_motion = None
        for s in shots:
            if s.get("kind") not in sourced_kinds:
                prev_motion = None
                continue
            assets = s.get("asset") if isinstance(s.get("asset"), list) else [s.get("asset")]
            if not assets or not all(assets):
                p(f"{s['id']}: no asset picked (or take its fallback)")
                continue
            for a in assets:
                missing = [k for k in ("id", "file", "sha256", "licence", "author", "url", "retrieved") if not a.get(k)]
                if missing:
                    p(f"{s['id']}: the asset's provenance lacks {', '.join(missing)}")
                if a.get("licence") and not licence_ok(a["licence"]):
                    p(f"{s['id']}: licence {a['licence']!r} is not on the accept list (§6.3)")
                if a.get("passed_filters") is not True:
                    p(f"{s['id']}: {a.get('id')} has not passed the sourcing filters (§6.4)")
                if s.get("kind") == "texture" and not all(a.get(k) for k in ("job", "model", "prompt", "seed")):
                    p(f"{s['id']}: an AI image records its job, model, prompt and seed")
                if s.get("kind") == "footage" and a.get("in") is not None and a.get("out") is not None \
                        and float(a["out"]) - float(a["in"]) < 0.8 * length[s["id"]] - TOL:
                    p(f"{s['id']}: the take ({float(a['out']) - float(a['in']):.1f} s) is shorter than the shot")
                if a.get("id") in used:
                    p(f"{s['id']}: {a['id']} is already in this film (§6.7)")
                if a.get("id") in prior:
                    p(f"{s['id']}: {a['id']} was used in the last {USAGE_WINDOW} films (§6.7)")
                used.append(a.get("id"))
            if s.get("kind") in ("still", "texture"):
                f = s.get("focus")
                if not (isinstance(f, list) and len(f) == 2 and all(0 <= float(v) <= 1 for v in f)):
                    p(f"{s['id']}: set focus as [x, y] between 0 and 1")
                allowed = MOTIONS.get(s.get("style"), set())
                if allowed and s.get("motion") not in allowed:
                    p(f"{s['id']}: {s.get('style')} moves by {', '.join(sorted(allowed))}")
                if s.get("motion") and s.get("motion") == prev_motion:
                    p(f"{s['id']}: two {s['motion']} moves back to back (§3.4)")
                prev_motion = s.get("motion")
            else:
                prev_motion = None

    # ── 7. labels: the proof label on a case-study figure, "demo data" on demo figures ──
    for s in shots:
        for r in s.get("reveals", []):
            src = str(facts.get(r.get("key"), {}).get("source", ""))
            if re.search(r"public-data case study", src, re.I) and s.get("label") != "proof":
                p(f"{s['id']}: {{{{{r['key']}}}}} is a case-study figure: label \"proof\" ({PROOF_LABEL})")
            elif re.search(r"demo", src, re.I) and s.get("label") != "demo":
                p(f"{s['id']}: {{{{{r['key']}}}}} is a demo figure: label \"demo\"")

    # ── 8, continued: variety (§14.8) ──
    by_style: dict[str, float] = {}
    for s in shots:
        by_style[s.get("style")] = by_style.get(s.get("style"), 0.0) + length[s["id"]]
    for style, secs in by_style.items():
        cap = var["chart_build_share"] if style == "chart-build" else var["texture_share"] if style == "texture" else var["max_style_share"]
        if secs / duration > cap + 0.005:
            p(f"{style}: {secs / duration:.0%} of the runtime; {cap:.0%} at most")
    # A process sequence (W8) is one shot in three parts, so it counts once toward a run.
    unit = lambda s: (s.get("style"), s.get("params", {}).get("group")) if s.get("style") == "footage-process" else s.get("style")
    for run, _ in _runs(shots, unit):
        style = run[0].get("style")
        if style == "footage-process":
            continue
        if len(run) > var["same_style_run"]:
            p(f"{run[0]['id']}–{run[-1]['id']}: {style} {len(run)} times running; never three")
        cap = styles.get(style, {}).get("max_run")
        if cap and len(run) > cap:
            p(f"{run[0]['id']}–{run[-1]['id']}: {style} at most {cap} in a row")
    if duration >= var["window_s"]:
        starts = sorted({float(s["start"]) for s in shots if float(s["start"]) + var["window_s"] <= duration} | {duration - var["window_s"]})
        for w0 in starts:
            seen = {s.get("style") for s in shots if float(s["end"]) > w0 and float(s["start"]) < w0 + var["window_s"]}
            if len(seen) < var["min_styles"]:
                p(f"{w0:.0f}–{w0 + var['window_s']:.0f} s: {len(seen)} styles; any 20 minutes uses at least {var['min_styles']}")
                break
    for style, st in styles.items():
        if st.get("every_s"):
            times = [float(s["start"]) for s in shots if s.get("style") == style]
            for a, b in zip(times, times[1:]):
                if b - a < st["every_s"] - TOL:
                    p(f"{style}: two within {b - a:.0f} s; one every {st['every_s']} s at most")
        if st.get("per_chapter"):
            count = 0
            for s in shots:
                if s.get("style") == "chapter":
                    count = 0
                elif s.get("style") == style:
                    count += 1
                    if count > st["per_chapter"]:
                        p(f"{s['id']}: {style} at most {st['per_chapter']} per chapter")
        if st.get("group_of"):
            groups: dict[str, list[dict]] = {}
            for s in shots:
                if s.get("style") == style:
                    groups.setdefault(s.get("params", {}).get("group", ""), []).append(s)
            for g, members in groups.items():
                order = [m.get("params", {}).get("step") for m in members]
                adjacent = [ids.index(m["id"]) for m in members]
                if not g or order != st["steps"] or adjacent != list(range(adjacent[0], adjacent[0] + len(adjacent))):
                    p(f"{style} group {g or '(unnamed)'}: three shots in a row, {' → '.join(st['steps'])}")
    return problems


def validate_unit(u: dict, picked: bool = False) -> tuple[list[str], str]:
    d = scriptmod.video_dir(u["slug"])
    if not (d / "shots.json").exists():
        return ["no shots.json: invoke the shot-plan skill"], ""
    timing, note = load_timing(d)
    if timing is None:
        return ["no timing: run `hubricon-content timing <slug>` (or `--estimate` before narration)"], ""
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    facts = scriptmod.load_facts(u["slug"])
    usage = json.loads(USAGE.read_text(encoding="utf-8")) if USAGE.exists() else {}
    return validate(plan, timing, facts, picked=picked, usage=usage), note


def fill(plan: dict, timing: dict, facts: dict, snap: float = 0.6) -> dict:
    """The plan's mechanical fields, from the timing, so the planner decides only
    what to show: each boundary snapped to the nearest legal cut (within `snap`
    seconds), the film's first and last shots pinned to the narration's ends, then
    every shot's `says`, its reveals (paper only) and its label."""
    shots = sorted(plan["shots"], key=lambda s: float(s["start"]))
    cuts = [c["t"] for c in timing.get("cutpoints", [])]
    words, duration = spoken(timing), float(timing["duration"])
    for a, b in zip(shots, shots[1:]):
        t = float(a["end"])
        near = min(cuts, key=lambda c: abs(c - t)) if cuts else t
        t = near if abs(near - t) <= snap else t
        a["end"] = b["start"] = round(t, 3)
    shots[0]["start"], shots[-1]["end"] = 0.0, round(duration, 3)
    reveals = spoken_reveals(timing)
    for s in shots:
        s["says"] = " ".join(w["word"] for w in words_in(words, s["start"], s["end"]))
        inside = [r for r in reveals if float(s["start"]) - 1e-6 <= r["t"] < float(s["end"])]
        s["reveals"] = [{"key": r["key"], "t": round(r["t"], 3)} for r in inside] if s.get("room") == "paper" else []
        sources = " ".join(str(facts.get(r["key"], {}).get("source", "")) for r in s["reveals"])
        s["label"] = ("proof" if re.search(r"public-data case study", sources, re.I)
                      else "demo" if re.search(r"demo", sources, re.I) else s.get("label"))
    plan["shots"] = shots
    return plan


def fill_unit(u: dict) -> dict:
    d = scriptmod.video_dir(u["slug"])
    timing, note = load_timing(d)
    if timing is None or not (d / "shots.json").exists():
        return {"status": "failed", "reason": "needs shots.json and a timing (or timing --estimate)"}
    plan = fill(json.loads((d / "shots.json").read_text(encoding="utf-8")), timing, scriptmod.load_facts(u["slug"]))
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "shots": len(plan["shots"]), "timing": "estimate" if note else "narration"}
