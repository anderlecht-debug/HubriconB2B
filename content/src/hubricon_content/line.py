"""The film line's picture steps that need no model (docs/content/FILM_LINE.md).

    hubricon-content auto-pick <slug>     → every picture shot takes its best passed candidate
    hubricon-content auto-prints <slug>   → every companion print the plan asks for, from its query

The sourcing filters already rank candidates by licence, light, faces, resolution, relevance and
the grade, so the top passed one is the pick. Code makes that choice, and a model never sees it.
What's left (no passed candidate, a then-and-now pair) is listed for the budgeted `pick` step.
No picture is used twice in a film.
"""
from __future__ import annotations

import json

from . import pick as pk
from . import script as scriptmod

PICTURE = {"still", "texture", "footage", "archive", "stack"}


def _used(plan: dict) -> set:
    out = set()
    for s in plan["shots"]:
        a = s.get("asset")
        for x in (a if isinstance(a, list) else [a] if a else []):
            if isinstance(x, dict) and x.get("id"):
                out.add(x["id"])
        pr = (s.get("params") or {}).get("print") or {}
        if isinstance(pr.get("asset"), dict):
            out.add(pr["asset"].get("id"))
    return out


def auto_pick(slug: str) -> dict:
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    used = _used(plan)
    picked, left = [], []
    for s in plan["shots"]:
        if s.get("kind") not in PICTURE or s.get("asset"):
            continue
        rec_p = d / "sources" / f"{s['id']}.json"
        rec = json.loads(rec_p.read_text(encoding="utf-8")) if rec_p.exists() else {}
        ok = [c for c in rec.get("candidates", []) if c.get("passed_filters") and c.get("id") not in used]
        ok.sort(key=lambda c: (c.get("rank", 99), c.get("sheet_index", 99)))
        need = 3 if s["kind"] == "stack" else 1
        if len(ok) < need:
            left.append(s["id"])
            continue
        nums = [int(c["sheet_index"]) for c in ok[:need]]
        try:
            pk.pick(slug, s["id"], nums, reason="auto-pick: the filters' top passed candidate")
        except SystemExit as e:
            left.append(f"{s['id']} ({e})")
            continue
        used.update(c["id"] for c in ok[:need])
        picked.append(s["id"])
    return {"status": "ok", "picked": len(picked), "left_for_pick_step": left}


def auto_prints(slug: str) -> dict:
    from . import shots as shotmod
    from . import sources
    from .sources import filters, net as netmod
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    used, net, reg = _used(plan), netmod.default(), shotmod.registry()
    done, dropped = [], []
    for s in plan["shots"]:
        pr = (s.get("params") or {}).get("print")
        if not isinstance(pr, dict) or isinstance(pr.get("asset"), dict):
            continue
        w = pr.get("want") or {}
        query = (w.get("query") or [None])[0] if isinstance(w.get("query"), list) else w.get("query")
        if not query:
            s["params"].pop("print")
            dropped.append(f"{s['id']} (no query)")
            continue
        ctx = filters.context({**s, "kind": "archive", "style": "archive-print", "specific": None}, reg)
        found = None
        for src in w.get("sources") or ["smithsonian", "commons"]:
            try:
                cands = sources.search(src, query, kind="image", n=20, net=net)
            except Exception:   # noqa: BLE001: a library down drops one print, never the film
                continue
            for c in cands:
                if c.get("id") in used:
                    continue
                c["query"] = query
                filters.precheck(c, ctx, {})
                filters.metadata(c, ctx)
                # a print stands at most 720 x 828 px on the desk: the full-frame size floors don't apply
                why = [r for r in c.get("rejected_because", []) if "long edge" not in r and "enlarged" not in r]
                w_, h_ = int(c.get("width") or 0), int(c.get("height") or 0)
                if why or not (w_ and h_) or min(720 / w_, 828 / h_) > 1.5:
                    continue
                c["rejected_because"] = []
                filters.finish(c)
                found = c
                break
            if found:
                break
        if not found:
            s["params"].pop("print")
            dropped.append(f"{s['id']} ({query})")
            continue
        a = pk.asset_of(found, net)
        for k in ("want",):
            pr.pop(k, None)
        pr["asset"] = a
        used.add(a["id"])
        done.append(s["id"])
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "prints": len(done), "dropped": dropped}


MERGE_MAX, MERGE_MAX_OPEN = 14.0, 8.0   # a held picture or card, at most (the style ceiling; the first minute is quicker)


def resolve_gaps(slug: str) -> dict:
    """Picture shots that found no picture, for no tokens. A neighbour takes the time: a held still or
    a type shot beside it, up to MERGE_MAX. Footage is never stretched past its clip. Only a shot no
    neighbour can take becomes the film's own words on a typed card."""
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    sh = plan["shots"]
    absorbed, carded = [], []
    i = 0
    while i < len(sh):
        s = sh[i]
        if s.get("kind") not in PICTURE or s.get("asset"):
            i += 1
            continue
        L = float(s["end"]) - float(s["start"])
        prev = sh[i - 1] if i else None
        nxt = sh[i + 1] if i + 1 < len(sh) else None
        can = lambda o: o and o.get("kind") not in ("chapter", "footage", "end") and (o.get("asset") or o.get("kind") not in PICTURE) \
            and float(o["end"]) - float(o["start"]) + L <= (MERGE_MAX_OPEN if float(s["start"]) < 60 else MERGE_MAX)
        if can(prev):
            prev["end"] = s["end"]
            absorbed.append(s["id"]); sh.pop(i)
            continue
        if can(nxt):
            nxt["start"] = s["start"]
            absorbed.append(s["id"]); sh.pop(i)
            continue
        said = [w.strip(".,;:!?\"'’”()") for w in (s.get("says") or "").split()]
        s.update({"kind": "document", "style": "doc-highlight", "room": "paper", "on": max(said, key=len) if said else None,
                  "params": {"lines": [s.get("says") or ""], "line": 1, "source": "As this film states it"},
                  "intent": "the film's own words, no picture found"})
        for k in ("query", "sources", "fallback", "specific", "focus", "motion"):
            s.pop(k, None)
        carded.append(s["id"])
        i += 1
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "absorbed": absorbed, "carded": carded, "shots": len(sh)}
