"""A film's shot plan, split by what each side does best (docs/content/FILM_LINE.md).

    hubricon-content plan-skeleton <slug>             → shots.json drafted by code, and plan-brief.md for the model
    hubricon-content plan-apply <slug> <decisions>    → the model's decisions merged into shots.json

Code drafts the mechanics, for no tokens. Sentences are grouped into shots of about 7 s (5 s in
the first minute) that end on legal cuts. A shot holding a figure runs at least 3 s past it. A
shot is on paper when it holds a figure and in the world when it doesn't, and chapter cards are
fixed.

The model only judges. For each shot it returns a few fields (kind, style, on, params,
query/sources/fallback, specific, intent), a few thousand output tokens instead of a whole JSON
plan. Asked to write the whole plan, a model on G02 wrote a script that cut 6,899 shots.
"""
from __future__ import annotations

import json
import re

from . import script as scriptmod

WAIT_OK, WAIT_WEIGHT, WAIT_HORIZON = 0.6, 1.5, 4.0   # a figure within 0.6 s of its cut is on the word

DECIDED = ("kind", "style", "on", "params", "query", "sources", "fallback", "specific", "intent", "label", "overlay", "chart", "room")


def draft(slug: str) -> dict:
    """Shots cut by code at legal cuts, never within the 3 s hold after a figure lands. Each cut is
    the legal one nearest the target length inside the floor and ceiling; chapter cards are fixed."""
    from . import shots as shotmod
    d = scriptmod.video_dir(slug)
    timing, _ = shotmod.load_timing(d)
    cad = shotmod.registry()["cadence"]
    hold = float(cad.get("hold_after_number_s", 3.0))
    cuts = sorted(float(c["t"]) for c in timing["cutpoints"])
    reveals = sorted((float(r["t"]), r["key"]) for r in shotmod.spoken_reveals(timing))
    duration = float(timing["duration"])
    cards = [(float(c["start"]), float(c["end"])) for c in timing["segments"] if c["kind"] == "card"]
    beats = [(float(c["start"]), float(c["end"]), i, re.sub(r"\s+", " ", str(c.get("visual") or "")).strip())
             for i, c in enumerate(timing["segments"]) if c["kind"] == "beat"]
    beat_at = lambda t: next(((i, v) for a, b, i, v in beats if a - 0.05 <= t < b), (beats[-1][2], beats[-1][3]) if beats else (0, ""))
    holds_ok = lambda c: not any(c - hold + 0.034 < t < c for t, _ in reveals)
    # cut on the word: a cut that leaves the next shot waiting on bare paper for its figure costs, so the
    # shot holding a figure opens just before the figure is said (G02: 28 of 79 type shots waited 1.5 s or more)
    rt = [t for t, _ in reveals]

    def wait_cost(c):
        nxt = next((t for t in rt if t > c), None)
        return WAIT_WEIGHT * max(0.0, nxt - c - WAIT_OK) if nxt is not None and nxt - c < WAIT_HORIZON else 0.0

    score = lambda c, aim: abs(c - aim) + wait_cost(c)

    keeps = _keeps(timing, cuts)
    shots, start = [], 0.0
    while start < duration - 0.05:
        keep = next(((a, b, text) for a, b, text in keeps if abs(a - start) < 0.05), None)
        if keep:      # the chapter's takeaway, set as it is said: fixed, the decision leaves it
            i, _ = beat_at(keep[0])
            shots.append({"start": keep[0], "end": keep[1], "beat": i, "room": "paper", "kind": "kinetic", "style": "kinetic-thesis",
                          "on": None, "params": {"lines": [keep[2]]}, "intent": "the chapter's takeaway", "fixed": True})
            start = keep[1]
            continue
        card = next(((a, b) for a, b in cards if abs(a - start) < 0.05), None)
        if card:
            i, _ = beat_at(card[0])
            shots.append({"start": card[0], "end": card[1], "beat": i, "room": "paper", "kind": "chapter", "style": "chapter",
                          "on": None, "params": {}, "intent": "the chapter card"})
            start = card[1]
            continue
        wall = min([a for a, _ in cards if a > start + 0.05] + [a for a, _, _ in keeps if a > start + 0.05] + [duration])
        target, ceil = (5.0, 7.5) if start < 60 else (6.5, 8.0)
        lo, hi = start + 3.5, start + ceil
        inside = [c for c in cuts if lo <= c <= min(hi, wall) and holds_ok(c)]
        if wall <= hi and (wall - start >= 3.0 or not shots):
            end = wall if not inside or abs(wall - (start + target)) < 1.5 else min(inside, key=lambda c: score(c, start + target))
        elif inside:
            end = min(inside, key=lambda c: score(c, start + target))
        else:   # no legal cut in range keeps the holds: the first one after the ceiling that does, else the wall
            end = next((c for c in cuts if c > hi and c <= wall and holds_ok(c)), wall)
        if wall - end < 3.0 and wall - end > 0.05:   # never leave a sliver before a card or the end
            end = wall
        i, v = beat_at(start)
        shots.append(_shot(start, end, i, [k for t, k in reveals if start - 0.05 <= t < end - 0.05], v))
        start = end
    for n, sh in enumerate(shots, 1):
        sh["id"] = f"s{n:03d}"
        sh["start"], sh["end"] = round(sh["start"], 3), round(sh["end"], 3)
    shots[-1]["end"] = round(duration, 3)
    plan = {"slug": slug, "mode": "history", "fps": 30, "shots": [{"id": sh.pop("id"), **sh} for sh in shots]}
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return plan


def _keeps(timing: dict, cuts: list[float]) -> list[tuple[float, float, str]]:
    """Each beat's KEEP sentence as a fixed span from the legal cut before its first word to the one after its last."""
    import re as _re
    norm = lambda w: _re.sub(r"[^a-z0-9]", "", w.lower())
    out = []
    for seg in timing["segments"]:
        if seg.get("kind") != "beat" or not seg.get("keep"):
            continue
        want = [norm(w) for w in seg["keep"].split() if norm(w)]
        ws = seg.get("words") or []
        got = [norm(w["word"]) for w in ws]
        for i in range(len(got) - len(want) + 1):
            if got[i:i + len(want)] == want:
                a = max((c for c in cuts if c <= ws[i]["start"] + 0.01), default=ws[i]["start"])
                b = min((c for c in cuts if c >= ws[i + len(want) - 1]["end"] - 0.01), default=seg["end"])
                out.append((round(a, 3), round(b, 3), seg["keep"]))
                break
    return out


def _shot(a, b, beat, keys, visual):
    if keys:
        kind, style = ("number", "number-land") if len(keys) == 1 else ("pair", "number-pair") if len(keys) == 2 else ("timeline", "timeline")
        params = {"value": f"{{{{{keys[0]}}}}}"} if kind == "number" else (
            {"left": {"value": f"{{{{{keys[0]}}}}}"}, "right": {"value": f"{{{{{keys[1]}}}}}"}} if kind == "pair" else
            {"layout": "ledger", "events": [{"date": "", "label": f"{{{{{k}}}}}"} for k in keys]})
        return {"start": a, "end": b, "beat": beat, "room": "paper", "kind": kind, "style": style, "on": f"{{{{{keys[0]}}}}}",
                "params": params, "intent": "", "visual": visual}
    return {"start": a, "end": b, "beat": beat, "room": "world", "kind": "still", "style": "still-push", "on": None, "params": {},
            "intent": "", "visual": visual}


def apply(slug: str, decisions: dict, also: tuple = ()) -> dict:
    """Merge the model's decisions ({"mode": …, "shots": {id: {field: value}}}) into the drafted plan.
    `also` admits more fields (a fix pass may move `start` and `end`)."""
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    by = {s["id"]: s for s in plan["shots"]}
    if decisions.get("mode") in ("history", "explainer"):
        plan["mode"] = decisions["mode"]
    unknown, set_ = [], 0
    for sid, fields in (decisions.get("shots") or {}).items():
        s = by.get(sid)
        if s is None:
            unknown.append(sid)
            continue
        if s.get("fixed"):            # code's (a chapter's takeaway): the decision leaves it
            continue
        for k, v in (fields or {}).items():
            if k == "params" and isinstance(v, dict) and isinstance(s.get("params"), dict):
                # merged, never replaced: a decision that sets a layout keeps the figures the draft put there
                s["params"] = {pk: pv for pk, pv in {**s["params"], **v}.items() if pv is not None}
            elif k in DECIDED or k in also:
                s[k] = v
                set_ += 1
    # what follows from a decision is code's: the room from the style, and a landing word where the
    # style needs one and the model gave none (the sentence's longest word, a noun more often than not)
    from . import shots as shotmod
    styles = shotmod.registry()["styles"]
    timing, _ = shotmod.load_timing(d)
    words = shotmod.spoken(timing)
    for s in plan["shots"]:
        s.pop("visual", None)
        st = styles.get(s.get("style"), {})
        if st.get("room") in ("paper", "world"):
            s["room"] = st["room"]
        if st.get("on") == "required" and not s.get("on"):
            said = [w["word"].strip(".,;:!?\"'’”()") for w in shotmod.words_in(words, s["start"], s["end"])]
            s["on"] = max(said, key=len) if said else None
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "shots": len(plan["shots"]), "fields_set": set_, "unknown_ids": unknown}
