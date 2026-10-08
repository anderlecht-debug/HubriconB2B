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


# ── the whole line as one resumable command (FILM_LINE.md) ───────────────────────────────────────

def autofix(slug: str) -> dict:
    """The validator's problems that have a known mechanical fix, fixed by code (the fixes made by hand
    on G02, 2026-10-07): a style's missing landing word, a thesis card longer than its 12 words or a
    then-and-now with no pictures (the film's own words on a typed card), a clipping style without
    its clipping, a pan too short to pan (a push)."""
    import re
    from . import shots as shotmod
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shotmod.load_timing(d)
    problems = shotmod.validate(plan, timing, scriptmod.load_facts(slug))
    by = {s["id"]: s for s in plan["shots"]}
    fixed = []
    longest = lambda s: max([w.strip(".,;:!?\"'’”()") for w in (s.get("says") or "").split()] or [None], key=lambda w: len(w or ""))
    card = lambda lines: {"lines": [x for x in lines if x], "line": 1, "source": "As this film states it"}
    for p in problems:
        m = re.match(r"(s\d+[a-z]?): (.*)", p)
        if not m or m.group(1) not in by:
            continue
        s, msg = by[m.group(1)], m.group(2)
        if msg.endswith("lands on a word: set `on`") or "is not spoken inside the shot" in msg:
            s["on"] = longest(s)
        elif msg.startswith("a thesis line is"):
            s.update({"kind": "document", "style": "doc-highlight", "room": "paper", "params": card((s.get("params") or {}).get("lines") or [s.get("says")])})
            s["on"] = longest(s)
        elif msg == "doc-clipping sets params.clipping":
            s["style"] = "doc-highlight"
        elif "still-pan runs" in msg:
            s["style"] = "still-push"
        elif s.get("kind") == "split" and not s.get("asset") and "split" in msg:
            p_ = s.get("params") or {}
            s.update({"kind": "document", "style": "doc-highlight", "room": "paper", "params": card([p_.get("then"), p_.get("now")])})
            s["on"] = longest(s)
        else:
            continue
        fixed.append(m.group(1))
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"fixed": sorted(set(fixed))}


def _cli(*args, env: dict | None = None, timeout: int = 6 * 3600) -> tuple[int, str]:
    import os, subprocess, sys
    from .state import CONTENT_DIR
    e = {**os.environ, "FILM_LOOK": "v3", "PYTHONWARNINGS": "ignore", **(env or {})}
    r = subprocess.run([sys.executable, "-m", "hubricon_content.cli", *args], cwd=str(CONTENT_DIR), env=e,
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "")[-4000:] + (r.stderr or "")[-2000:]


def _workers() -> int:
    """Render workers by free memory: each Chrome worker and its grading take about 3 GB at peak."""
    try:
        avail = int(next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable")).split()[1]) / 1e6
    except Exception:   # noqa: BLE001
        return 2
    return max(1, min(4, int(avail // 3)))


def _clean(slug: str) -> list[str]:
    import re
    from . import shots as shotmod
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shotmod.load_timing(d)
    return [p for p in shotmod.validate(plan, timing, scriptmod.load_facts(slug)) if not re.search(r"of the runtime|at most$", p)]


STEPS = ["voice", "skeleton", "decide", "fill", "source", "pictures", "render", "qa", "draft", "cost"]


def run_line(slug: str, start: str | None = None, until: str | None = None, placeholder: bool = False) -> dict:
    """Every step of a film in order, each recorded in line.json, so a stopped run resumes where it left
    off. Steps with no AI run for nothing; the two that use a model (decide, and fix when needed) run
    under their budgets. Stops with a reason when a step can't go on (no voice yet, a budget spent)."""
    from datetime import datetime, timezone
    from . import ai_step, plan_brief, plan_skeleton
    d = scriptmod.video_dir(slug)
    state_p = d / "line.json"
    st = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {"done": {}}
    order = STEPS[STEPS.index(start):] if start else STEPS
    if until:
        order = order[:order.index(until) + 1]
    log = []

    def done(step, note=""):
        st["done"][step] = {"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "note": note}
        state_p.write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        log.append(f"{step}: {note or 'done'}")

    def stop(step, why):
        log.append(f"{step}: STOPPED, {why}")
        return {"status": "stopped", "at": step, "reason": why, "log": log}

    for step in order:
        if step in st["done"] and not start:
            continue
        if step == "voice":
            if not (d / "timing.json").exists():
                if not placeholder:
                    return stop(step, "no timing yet: record the takes (record.mjs, then takes-to-vo), or pass --placeholder")
                for cmd in ("tts", "timing"):
                    rc, out = _cli(cmd, slug, env={"CONTENT_ALLOW_PLACEHOLDER": "1"})
                    if rc:
                        return stop(step, f"{cmd} failed: {out[-300:]}")
            done(step)
        elif step == "skeleton":
            plan = plan_skeleton.draft(slug)
            plan_brief.build(slug)
            done(step, f"{len(plan['shots'])} shots drafted")
        elif step == "decide":
            r = ai_step.run(slug, "plan", f"Read content/videos/{slug}/plan-brief.md and do exactly what its section 'What you return' "
                            f"says: decide every shot listed and write content/videos/{slug}/decisions.json in one write. "
                            "Reply with the number of shots decided.", extra=ai_step.STEP_ARGS)
            if not (d / "decisions.json").exists():
                return stop(step, f"no decisions written ({r.get('status')}: {r.get('reason') or ''})")
            plan_skeleton.apply(slug, json.loads((d / "decisions.json").read_text(encoding="utf-8")))
            done(step, f"{r.get('weighted_tokens')} weighted tokens")
        elif step == "fill":
            _cli("shots-fill", slug)
            for _ in range(3):
                autofix(slug)
                _cli("shots-fill", slug)
            left = _clean(slug)
            if left:
                r = ai_step.run(slug, "fix", f"Fix these problems in content/videos/{slug}/shots.json by editing that file (one write), "
                                "then stop. Keep every shot's start and end unless a problem names its length. Problems:\n- " + "\n- ".join(left[:80]),
                                extra=ai_step.STEP_ARGS)
                _cli("shots-fill", slug)
                left = _clean(slug)
                if left:
                    return stop(step, f"{len(left)} plan problem(s) remain: {left[:5]}")
            done(step, "the plan validates")
        elif step == "source":
            rc, out = _cli("source", slug)
            if rc:
                return stop(step, f"sourcing failed: {out[-300:]}")
            done(step)
        elif step == "pictures":
            a = auto_pick(slug)
            p = auto_prints(slug)
            g = resolve_gaps(slug)
            _cli("shots-fill", slug)
            for _ in range(2):
                autofix(slug)
                _cli("shots-fill", slug)
            done(step, f"{a['picked']} picked, {p['prints']} prints, {len(g['absorbed'])} absorbed, {len(g['carded'])} carded")
        elif step == "render":
            rc, out = _cli("render-shots", slug, "--workers", str(_workers()), env={"CONTENT_ALLOW_PLACEHOLDER": "1"})
            if rc:
                return stop(step, f"render failed: {out[-300:]}")
            done(step)
        elif step == "qa":
            rc, out = _cli("film-qa", slug, "--no-media")
            done(step, out.strip().splitlines()[-1] if out.strip() else "")
        elif step == "draft":
            rc, out = _cli("draft", slug, "--remix", env={"CONTENT_ALLOW_PLACEHOLDER": "1"})
            if rc:
                return stop(step, f"draft failed: {out[-300:]}")
            _cli("review-sheets", slug)
            done(step)
        elif step == "cost":
            from . import meter
            m = meter.summary(slug)
            done(step, f"{m['ai_weighted_tokens']:,} weighted tokens")
    return {"status": "ok", "log": log}
