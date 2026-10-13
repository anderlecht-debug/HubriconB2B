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


def auto_pick(slug: str, repick: bool = False) -> dict:
    """Every picture shot takes its best passed candidate. Scored by the relevance model (relevance.py), a
    candidate below its THRESHOLD is not taken and the rest are ordered by relevance with the source's rank
    a little; a shot whose best stays below LOW is listed for the one capped visual-pick reply. Unscored
    (no model on this machine), the source's rank alone orders them, as before."""
    from . import relevance
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    used = _used(plan)
    picked, left, low = [], [], []
    for s in plan["shots"]:
        if s.get("kind") not in PICTURE or (s.get("asset") and not repick):
            continue
        if repick and s.get("asset"):
            for a in (s["asset"] if isinstance(s["asset"], list) else [s["asset"]]):
                used.discard(a.get("id"))
        rec_p = d / "sources" / f"{s['id']}.json"
        rec = json.loads(rec_p.read_text(encoding="utf-8")) if rec_p.exists() else {}
        ok = [c for c in rec.get("candidates", []) if c.get("passed_filters") and c.get("id") not in used]
        ok.sort(key=lambda c: (c.get("rank", 99), c.get("sheet_index", 99)))
        scored = any("relevance" in c for c in ok)
        if scored:
            ok = [c for _, c in sorted(((relevance.blend(c, i), c) for i, c in enumerate(ok)
                                        if c.get("relevance", -1.0) >= relevance.THRESHOLD), key=lambda x: -x[0])]
            if not ok or ok[0]["relevance"] < relevance.LOW:
                low.append(s["id"])
        need = 3 if s["kind"] == "stack" else 1
        if len(ok) < need:
            left.append(s["id"])
            continue
        nums = [int(c["sheet_index"]) for c in ok[:need]]
        why = (f"auto-pick: relevance {ok[0]['relevance']:+.3f}, the best of {len(ok)} that show the sentence" if scored
               else "auto-pick: the filters' top passed candidate")
        try:
            pk.pick(slug, s["id"], nums, reason=why)
        except SystemExit as e:
            left.append(f"{s['id']} ({e})")
            continue
        except Exception as e:     # noqa: BLE001: a library refusing a download (a 429) costs one shot its new pick, never the run
            left.append(f"{s['id']} (kept its picture: {type(e).__name__} {str(e)[:60]})")
            continue
        used.update(c["id"] for c in ok[:need])
        picked.append(s["id"])
    return {"status": "ok", "picked": len(picked), "left_for_pick_step": left, "low": low}


PICK_SYSTEM = ("You choose pictures for a documentary film. You answer with exactly one JSON object, as the "
               "prompt's last paragraph describes, and nothing before or after it.")
SHEET_PX = 800          # a contact sheet's width as the model sees it (about 1,100–1,400 tokens a sheet)


def visual_pick(slug: str, low: list[str]) -> dict:
    """The shots whose best picture is doubtful, in one capped reply: each shot's contact sheet, its words and
    its candidates' scores in; a sheet number (or none) per shot out. As many sheets as the step's budget
    holds go, the most doubtful first; the rest keep their auto-pick (FILM_PROCESS.md 2.7)."""
    import io
    from PIL import Image
    from . import ai_step
    d = scriptmod.video_dir(slug)
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    by = {s["id"]: s for s in plan["shots"]}
    cap = int(ai_step.budgets()["steps"]["pick"]["tokens"])
    room = cap * 0.75 - 1500                       # the prompt, the answer, a margin under the cap
    def best(sid):
        rec = json.loads((d / "sources" / f"{sid}.json").read_text(encoding="utf-8"))
        return max((c.get("relevance", -1.0) for c in rec.get("candidates", []) if c.get("passed_filters")), default=-1.0)
    images, lines, sent = [], [], []
    for sid in sorted(low, key=best):
        sheet = d / "sources" / f"{sid}.jpg"
        if not sheet.exists():
            continue
        im = Image.open(sheet).convert("RGB")
        im.thumbnail((SHEET_PX, 4000))
        cost = im.width * im.height / 750
        if cost > room:
            break
        room -= cost
        b = io.BytesIO()
        im.save(b, "JPEG", quality=82)
        images.append(b.getvalue())
        sent.append(sid)
        s = by[sid]
        rec = json.loads((d / "sources" / f"{sid}.json").read_text(encoding="utf-8"))
        cands = "; ".join(f"#{c['sheet_index']} {c.get('relevance', 0):+.2f}" for c in rec.get("candidates", []) if c.get("passed_filters"))
        lines.append(f"Picture {len(sent)}: shot {sid}. Spoken: \"{(s.get('says') or '')[:220]}\" Passed candidates (sheet number, "
                     f"relevance): {cands}.")
    if not sent:
        return {"status": "skipped", "reason": "no contact sheet fits the budget", "reviewed": 0}
    prompt = ("Each picture above is a contact sheet of candidate pictures for one shot of a documentary about retail "
              "history and pricing; each candidate is numbered under its picture, and crossed-out ones failed the filters.\n"
              + "\n".join(lines) + "\n\nFor each shot choose the passed candidate that best shows what is spoken, as a "
              "viewer would expect to see it (period and subject right; never a modern building for a historic store). "
              'If none fits, choose null. Reply with one JSON object: {"shots": {"<shot id>": <sheet number or null>, ...}}.')
    saved = d / "qa" / "visual-pick.json"
    old = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else {}
    if sorted(old.get("sent", [])) == sorted(sent) and old.get("answer") is not None:
        r, ans = {"status": "reused", "weighted_tokens": 0}, old["answer"]         # asked once: never paid for twice
    else:
        r = ai_step.reply(slug, "pick", PICK_SYSTEM, prompt, images=images)
        ans = (ai_step.json_reply(r.get("result")) or {}).get("shots") or {}
        saved.parent.mkdir(exist_ok=True)
        saved.write_text(json.dumps({"sent": sent, "answer": ans, "weighted_tokens": r.get("weighted_tokens")}, indent=1) + "\n",
                         encoding="utf-8")
    chose, none = [], []
    for sid in sent:
        n = ans.get(sid)
        if isinstance(n, int):
            try:
                pk.pick(slug, sid, [n], reason="visual-pick: chosen from its contact sheet in one capped reply")
                chose.append(sid)
            except SystemExit:
                pass
            except Exception:    # noqa: BLE001: a library refusing the download (a 429) keeps the shot's picture
                pass
        elif sid in ans:
            none.append(sid)
    if none:      # no candidate shows the sentence: resolve-gaps absorbs the shot or sets the film's own words
        plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
        for s in plan["shots"]:
            if s["id"] in none:
                s.pop("asset", None)
        (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": r.get("status"), "reviewed": len(sent), "chosen": chose, "none_fit": none,
            "weighted_tokens": r.get("weighted_tokens")}


PRINT_POOL = 6          # acceptable print candidates gathered per shot before the best is chosen


def _best_print(s: dict, pool: list[dict], net) -> dict | None:
    """The companion print that best shows the shot's words (relevance.py), from the acceptable ones; the
    first acceptable one when the model is not on this machine; none when every one shows something else."""
    if not pool:
        return None
    try:
        from . import relevance, sources
        files = []
        for c in pool:
            try:
                files.append((c, relevance._picture(sources.fetch_preview(c, net))))
            except Exception:    # noqa: BLE001: a preview that won't download is not a candidate
                continue
        files = [(c, f) for c, f in files if f]
        if not files:
            return pool[0]
        text = relevance.text_of({**s, "query": [((s.get("params") or {}).get("print") or {}).get("want", {}).get("query") or ""]})
        ranked = sorted(zip(relevance.scores(text, [f for _, f in files]), range(len(files))), key=lambda x: -(x[0] + relevance.RANK_WEIGHT / (1 + x[1])))
        sc, i = ranked[0]
        if sc < relevance.THRESHOLD:
            return None
        files[i][0]["relevance"] = round(sc, 4)
        return files[i][0]
    except ImportError:
        return pool[0]


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
        found, pool = None, []
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
                pool.append(c)
                if len(pool) >= PRINT_POOL:
                    break
            if len(pool) >= PRINT_POOL:
                break
        found = _best_print(s, pool, net)
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

def restore_content(plan: dict) -> list[str]:
    """A paper shot with nothing to draw gets its content back from what is spoken under it: its figures
    (`reveals`) for a number, pair, timeline or formula, its words (`says`) for a quote or kinetic type."""
    from .shots import draws
    fixed = []
    for s in plan["shots"]:
        p = s.get("params") if isinstance(s.get("params"), dict) else {}
        if draws(s):
            continue
        reveals = sorted(s.get("reveals") or [], key=lambda r: r["t"])
        keys = list(dict.fromkeys(r["key"] for r in reveals))
        k = s["kind"]
        if k == "number" and keys:
            p["value"] = f"{{{{{keys[0]}}}}}"
        elif k == "pair" and len(keys) >= 2:
            p.update(left={**(p.get("left") or {}), "value": f"{{{{{keys[0]}}}}}"},
                     right={**(p.get("right") or {}), "value": f"{{{{{keys[1]}}}}}"})
        elif k == "timeline" and keys:
            p["events"] = [{"date": "", "label": f"{{{{{x}}}}}"} for x in keys]
            if p.get("layout") in (None, "dates"):
                p["layout"] = "ledger"          # a line in time needs dates; figures with none stand as a ledger
        elif k == "formula" and keys:
            p["terms"] = [{"text": f"{{{{{r['key']}}}}}", "at": round(float(r["t"]) - float(s["start"]), 2)} for r in reveals]
        elif k == "quote" and s.get("says"):
            p["text"] = s["says"]
        else:
            continue
        s["params"] = p
        fixed.append(f"{s['id']}: its {k} drawn again from what is spoken under it")
    return fixed


CONTEXT_WORDS = 9


def context_of(label: str | None) -> str | None:
    """A figure's fact label as the line set at the cut: its first clause, no parentheses, 9 words at most."""
    import re
    if not label:
        return None
    t = re.sub(r"\s*\([^)]*\)", "", str(label)).split(";")[0].strip(" ,.")
    if len(t.split()) > CONTEXT_WORDS and "," in t and len(t.split(",")[0].split()) >= 3:
        t = t.split(",")[0].strip()
    if not t or len(t.split()) > CONTEXT_WORDS or "http" in t:
        return None
    return t[0].upper() + t[1:]


def context_lines(plan: dict, facts: dict) -> list[str]:
    """A type shot opens on what its figure is, never on bare paper: a number's `sub` and a pair's labels, set
    at the cut, from the figures' fact labels (no tokens), where the plan gave none. The figure lands on its word."""
    import re
    fixed = []
    key = lambda v: (re.findall(r"\{\{\s*(\w+)\s*\}\}", str(v or "")) or [None])[0]
    for s in plan["shots"]:
        if s.get("style") == "callback" or s.get("fixed"):
            continue
        p = s.get("params") if isinstance(s.get("params"), dict) else None
        if p is None:
            continue
        if s.get("kind") == "number" and not p.get("sub"):
            k = key(p.get("value")) or next((r["key"] for r in s.get("reveals") or []), None)
            c = context_of((facts.get(k) or {}).get("label"))
            if c:
                p["sub"] = c
                fixed.append(f"{s['id']}: opens on {c!r}")
        elif s.get("kind") == "pair":
            for side in ("left", "right"):
                v = p.get(side)
                if isinstance(v, dict) and not v.get("label"):
                    c = context_of((facts.get(key(v.get("value"))) or {}).get("label"))
                    if c:
                        v["label"] = c
                        fixed.append(f"{s['id']}: its {side} figure labelled {c!r}")
    return fixed


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
    fixed = restore_content(plan) + context_lines(plan, scriptmod.load_facts(slug))
    longest = lambda s: max([w.strip(".,;:!?\"'’”()") for w in (s.get("says") or "").split()] or [None], key=lambda w: len(w or ""))
    card = lambda lines: {"lines": [x for x in lines if x], "line": 1, "source": "As this film states it"}
    for p in problems:
        m = re.match(r"(s\d+[a-z]?): (.*)", p)
        if not m or m.group(1) not in by:
            continue
        s, msg = by[m.group(1)], m.group(2)
        if s.get("fixed"):          # code's shots (a chapter's takeaway, a BREATHE hold, a MONTAGE run) are never rewritten
            continue
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


PLAN_SYSTEM = ("You plan the shots of a documentary film for Hubricon. You answer with exactly one JSON object, "
               "as the brief's section 'What you return' describes, and nothing before or after it.")
FIX_SYSTEM = ("You fix problems in a documentary film's shot plan. You answer with exactly one JSON object, "
              "as the brief's section 'What you return' describes, and nothing before or after it.")
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
            tj = d / "timing.json"
            # a timing read by the placeholder voice is a preview: his own film is timed from his takes
            stale = tj.exists() and not placeholder and json.loads(tj.read_text(encoding="utf-8")).get("voice") == "placeholder"
            if not tj.exists() or stale:
                from .state import _takes_in
                if placeholder:
                    cmds, env = ("tts", "timing"), {"CONTENT_ALLOW_PLACEHOLDER": "1"}
                elif _takes_in(slug):            # his takes are in: they become the narration and its timing
                    cmds, env = ("takes-to-vo", "timing"), None
                else:
                    return stop(step, f"no takes yet: node content/film/record.mjs {slug}")
                for cmd in cmds:
                    rc, out = _cli(cmd, slug, env=env)
                    if rc:
                        return stop(step, f"{cmd} failed: {out[-300:]}")
                if not placeholder:          # his film's line has started: its FORM counts against the week
                    from . import state
                    q = state.load()
                    u = next((x for x in q["units"] if x.get("slug") == slug), None)
                    if u:
                        state.record_line_start(q, u)
                        state.save(q)
            done(step)
        elif step == "skeleton":
            plan = plan_skeleton.draft(slug)
            plan_brief.build(slug)
            done(step, f"{len(plan['shots'])} shots drafted")
        elif step == "decide":
            # one reply, no tools: the brief holds everything, the answer is the decisions (ai_step.reply)
            r = ai_step.reply(slug, "plan", PLAN_SYSTEM, (d / "plan-brief.md").read_text(encoding="utf-8"))
            dec = ai_step.json_reply(r.get("result"))
            if not dec or not isinstance(dec.get("shots"), dict):
                (d / "decisions.raw.txt").write_text(r.get("result") or "", encoding="utf-8")
                return stop(step, f"no decisions in the reply ({r.get('status')}, {r.get('weighted_tokens')} weighted tokens; "
                                  "the reply is in decisions.raw.txt)")
            (d / "decisions.json").write_text(json.dumps(dec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            plan_skeleton.apply(slug, dec)
            done(step, f"{len(dec['shots'])} shots decided, {r.get('weighted_tokens')} weighted tokens")
        elif step == "fill":
            _cli("shots-fill", slug)
            for _ in range(3):
                autofix(slug)
                _cli("shots-fill", slug)
            left = _clean(slug)
            if left:
                # one reply with the shots the problems name: field patches back, merged by code
                r = ai_step.reply(slug, "fix", FIX_SYSTEM, plan_brief.fix_brief(slug, left[:80]))
                dec = ai_step.json_reply(r.get("result"))
                if dec and isinstance(dec.get("shots"), dict):
                    plan_skeleton.apply(slug, dec, also=("start", "end"))
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
            try:      # the relevance model scores every candidate on the GPU, for no tokens (relevance.py)
                from . import relevance
                relevance.score_film(slug)
            except ImportError:
                pass
            a = auto_pick(slug)
            p = auto_prints(slug)
            v = visual_pick(slug, a["low"]) if a.get("low") else {"reviewed": 0}
            try:
                relevance.score_film(slug)     # the picks as they stand, for film-qa
            except (ImportError, NameError):
                pass
            g = resolve_gaps(slug)
            _cli("shots-fill", slug)
            for _ in range(2):
                autofix(slug)
                _cli("shots-fill", slug)
            done(step, f"{a['picked']} picked, {v['reviewed']} reviewed by a model, {p['prints']} prints, "
                       f"{len(g['absorbed'])} absorbed, {len(g['carded'])} carded")
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
    # the queue hears what the line did, so the runner's skill never repeats a step by hand
    for q_step, line_step in (("shots", "fill"), ("source", "source"), ("pick", "pictures"), ("render_shots", "render")):
        if line_step in st["done"]:
            _cli("mark", slug, q_step, "done")
    return {"status": "ok", "log": log}
