"""`hubricon-content`: one subcommand per pipeline step, each idempotent.

Imports are lazy so `next`, `status` and the review commands work even when a
media dependency is missing on the machine that runs them.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from . import state
from .state import CONTENT_DIR

MAIN_ENV = CONTENT_DIR.parent.parent / "HubriconB2B" / ".env"


def _load_env() -> None:
    """Secrets from the main checkout's .env, values never printed."""
    for candidate in (CONTENT_DIR.parent / ".env", MAIN_ENV):
        if candidate.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(candidate, override=False)
            except Exception:
                pass
            break


def _q():
    return state.load()


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _status_files(q: dict) -> None:
    state.STATE_MD.write_text(state.render_state(q), encoding="utf-8")
    from . import review
    review.build(q)


def cmd_init(a):
    if state.QUEUE.exists() and not a.force:
        raise SystemExit("queue.json exists; pass --force to reseed (this discards progress)")
    q = state.seed()
    state.save(q)
    _status_files(q)
    print(f"seeded {len(q['units'])} units → {state.QUEUE}")


def cmd_demo(a):
    from . import demo
    m = demo.generate()
    print(f"{m['brand']}: {len(m['files'])} files, revenue ${m['annual_revenue']:,.0f} — demo data")


def cmd_facts(a):
    from . import facts
    p = facts.write(a.slug, force=a.force)
    n = len(json.loads(p.read_text(encoding="utf-8")))
    print(f"{p} ({n} facts)")


def _unit_for(q, slug):
    return state.unit(q, slug)


def cmd_script_validate(a):
    from . import script as sm
    q = _q(); u = _unit_for(q, a.slug)
    facts = sm.load_facts(u["slug"])
    text = (sm.video_dir(u["slug"]) / "script.md").read_text(encoding="utf-8")
    cal = json.loads(state.CALENDAR.read_text(encoding="utf-8"))
    problems = sm.validate(sm.parse(text), facts, u["tier"], u["pillar"], cal["cta_by_pillar"])
    for p in problems:
        print(f"- {p}")
    print("clean" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


def cmd_critique(a):
    from . import critique
    q = _q(); u = _unit_for(q, a.slug)
    c = critique.mechanical(u["slug"], u["tier"], u["pillar"])
    p = Path(state.CONTENT_DIR / "videos" / u["slug"] / "critique.json")
    if p.exists():
        prev = json.loads(p.read_text(encoding="utf-8"))
        for old, new in zip(prev.get("items", []), c["items"]):
            if new["pass"] is None and old.get("pass") is not None:
                new["pass"], new["note"] = old["pass"], old["note"]
    c["pass"] = critique.merged_pass(c) if all(i["pass"] is not None for i in c["items"]) else None
    p.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{p}: pass={c['pass']} problems={len(c['validator_problems'])} unjudged={sum(1 for i in c['items'] if i['pass'] is None)}")


def cmd_review(a):
    from . import review
    q = _q()
    r = review.enter(q, a.slug, final=a.final)
    state.save(q)
    _status_files(q)
    _out(r)


def _approve(a, gate):
    from . import script as sm
    q = _q(); u = _unit_for(q, a.slug)
    if gate == "review":
        facts = sm.load_facts(u["slug"])
        text = (sm.video_dir(u["slug"]) / "script.md").read_text(encoding="utf-8")
        cal = json.loads(state.CALENDAR.read_text(encoding="utf-8"))
        problems = sm.validate(sm.parse(text), facts, u["tier"], u["pillar"], cal["cta_by_pillar"])
        if problems:
            print("the script no longer passes the guard; fix these before approving:")
            for p in problems:
                print(f"- {p}")
            sys.exit(1)
    state.approve(q, u["id"], gate, a.note or "")
    state.save(q)
    _status_files(q)
    print(f"{u['id']} {gate} approved; the next tick continues")


def cmd_approve(a):
    _approve(a, "review")


def cmd_approve_final(a):
    _approve(a, "approve_final")


def _reject(a, gate):
    q = _q(); u = _unit_for(q, a.slug)
    state.reject(q, u["id"], gate, a.note)
    d = CONTENT_DIR / "videos" / u["slug"]
    d.mkdir(parents=True, exist_ok=True)
    with (d / "brief.md").open("a", encoding="utf-8") as fh:
        fh.write(f"\n## Founder note ({state.now()}, {gate})\n\n{a.note}\n")
    state.save(q)
    _status_files(q)
    print(f"{u['id']} sent back to {'the script' if gate == 'review' else 'the render'} with your note")


def cmd_reject(a):
    _reject(a, "review")


def cmd_reject_final(a):
    _reject(a, "approve_final")


def cmd_voice(a):
    """Which voice a unit carries: "own" once the founder's recorded takes are rendered in, "founder" for the clone."""
    q = _q(); u = _unit_for(q, a.slug)
    u["voice"] = a.voice
    u["publishable"] = False   # set again only by approve-final
    state.save(q)
    _status_files(q)
    print(f"{u['id']} voice: {a.voice}")


def cmd_takes_to_vo(a):
    q = _q(); u = _unit_for(q, a.slug)
    from . import tts
    res = tts.takes_to_vo(u, q, force=a.force)
    state.save(q)
    _status_files(q)
    _out(res)
    if res["status"] != "ok":
        raise SystemExit(1)


def cmd_next(a):
    q = _q()
    item = state.next_item(q)
    if not a.dry:
        state.save(q)
    _out(item)


def cmd_status(a):
    q = _q()
    state.refresh_capabilities(q)
    state.save(q)
    if a.md:
        _status_files(q)
        print(f"wrote {state.STATE_MD.name} and REVIEW.md")
    else:
        counts = {}
        for u in q["units"]:
            counts[u["status"]] = counts.get(u["status"], 0) + 1
        _out({"units": counts, "style_locked": q.get("style_locked"), "capabilities": q.get("capabilities")})


def cmd_mark(a):
    q = _q()
    u = state.mark(q, a.unit, a.step, a.outcome, a.note or "")
    state.save(q)
    _status_files(q)
    print(f"{u['id']} {a.step} → {a.outcome} (unit {u['status']})")


def cmd_unblock(a):
    q = _q(); u = state.unit(q, a.unit)
    u["status"], u["blocked_on"] = "todo", None
    for s, v in list(u.get("steps", {}).items()):
        if v == "blocked" and s != "upload":
            u["steps"][s] = "todo"
    state.log(u, "unblock", a.note or "unblocked by the founder")
    state.save(q); _status_files(q)
    print(f"{u['id']} back in the queue")


def _step(module: str, fn: str = "run"):
    def handler(a):
        import importlib
        mod = importlib.import_module(f"hubricon_content.{module}")
        q = _q(); u = _unit_for(q, a.slug)
        result = getattr(mod, fn)(u, q, force=getattr(a, "force", False))
        state.save(q)
        _out(result)
        if isinstance(result, dict) and result.get("status") in ("blocked", "failed"):
            sys.exit(2)
    return handler


def cmd_timing(a):
    from . import timing
    q = _q(); u = _unit_for(q, a.slug)
    result = timing.build(u, q, force=a.force, estimate=a.estimate)
    if not a.estimate:
        state.save(q)
    _out(result)


def cmd_pick(a):
    from . import pick
    focus = [float(x) for x in a.focus.split(",")] if a.focus else None
    if a.none:
        _out(pick.none(a.slug, a.shot, a.reason))
    elif a.texture_file:
        _out(pick.texture(a.slug, a.shot, a.texture_file, a.job, a.model, a.prompt, a.seed, a.reason, focus=focus, motion=a.motion or "drift"))
    else:
        _out(pick.pick(a.slug, a.shot, a.numbers, focus=focus, motion=a.motion, start=a.start, reason=a.reason, then=a.then, now=a.now))


def cmd_render_shots(a):
    from . import render_shots
    q = _q(); u = _unit_for(q, a.slug)
    res = render_shots.render(u, q, force=a.force, only={x for x in a.only.split(",") if x} or None, workers=a.workers)
    _out(res)
    if res.get("status") != "ok":
        sys.exit(2)


def cmd_shots_fill(a):
    from . import shots
    q = _q(); u = _unit_for(q, a.slug)
    _out(shots.fill_unit(u))


def cmd_shots_validate(a):
    from . import shots
    q = _q(); u = _unit_for(q, a.slug)
    problems, note = shots.validate_unit(u, picked=a.picked)
    for p_ in problems:
        print(f"- {p_}")
    print(f"{len(problems)} problem(s){note}" if problems else f"clean{note}")
    if problems:
        sys.exit(1)


def cmd_source(a):
    from . import sourcing
    q = _q(); u = _unit_for(q, a.slug)
    result = sourcing.run(u, q, shot=a.shot)
    for line in sourcing.summary(result):
        print(line)
    _out(result)
    if result.get("status") in ("blocked", "failed"):
        sys.exit(2)


def cmd_template(a):
    from . import playbook_template
    p = playbook_template.build()
    print(p)


def cmd_render_lessons(a):
    from . import lessons
    print(lessons.render_all())


def cmd_embed_lessons(a):
    from . import lessons
    print(lessons.embed())


def cmd_style_lock(a):
    from . import stylelock
    q = _q()
    p = stylelock.write(a.slug, q)
    state.save(q)
    print(p)


def cmd_voice_clone(a):
    from . import tts
    from pathlib import Path as P
    files = [P(f) for f in a.files]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise SystemExit("missing: " + ", ".join(missing))
    vid = tts.voice_clone(a.name, files, a.description or "")
    print(f"voice id: {vid}")
    print(f"add to /home/lp9/Hubricon/HubriconB2B/.env:  ELEVENLABS_VOICE_ID={vid}")
    print("then listen:  hubricon-content voice-preview 01-survivorship-bias")


def cmd_voice_preview(a):
    from . import tts
    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    if not (a.voice or os.environ.get("ELEVENLABS_VOICE_ID")):
        raise SystemExit("no voice: set ELEVENLABS_VOICE_ID (run voice-clone first) or pass --voice <id>")
    out = tts.voice_preview(a.slug, text=a.text, voice=a.voice)
    print(out)


def cmd_youtube_auth(a):
    from . import upload
    print(upload.authorize())


def main(argv=None) -> None:
    _load_env()
    ap = argparse.ArgumentParser(prog="hubricon-content")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_init)
    sub.add_parser("demo").set_defaults(fn=cmd_demo)
    p = sub.add_parser("facts"); p.add_argument("slug"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_facts)
    p = sub.add_parser("script-validate"); p.add_argument("slug"); p.set_defaults(fn=cmd_script_validate)
    p = sub.add_parser("critique"); p.add_argument("slug"); p.set_defaults(fn=cmd_critique)
    p = sub.add_parser("review"); p.add_argument("slug"); p.add_argument("--final", action="store_true"); p.set_defaults(fn=cmd_review)
    for name, fn in (("approve", cmd_approve), ("approve-final", cmd_approve_final)):
        p = sub.add_parser(name); p.add_argument("slug"); p.add_argument("--note", default=""); p.set_defaults(fn=fn)
    for name, fn in (("reject", cmd_reject), ("reject-final", cmd_reject_final)):
        p = sub.add_parser(name); p.add_argument("slug"); p.add_argument("--note", required=True); p.set_defaults(fn=fn)
    p = sub.add_parser("timing", help="timing.json from the narration, or --estimate: timing.estimate.json at 150 wpm")
    p.add_argument("slug"); p.add_argument("--force", action="store_true")
    p.add_argument("--estimate", action="store_true", help="plan before a voice exists; never replaces timing.json")
    p.set_defaults(fn=cmd_timing)
    p = sub.add_parser("pick", help="record a shot's picture from its contact sheet (the visual-pick skill)")
    p.add_argument("slug"); p.add_argument("shot"); p.add_argument("numbers", nargs="*", type=int)
    p.add_argument("--focus", default=None); p.add_argument("--motion", default=None); p.add_argument("--in", dest="start", type=float, default=None)
    p.add_argument("--then", type=int, default=None); p.add_argument("--now", type=int, default=None)
    p.add_argument("--none", action="store_true"); p.add_argument("--reason", default="")
    p.add_argument("--texture-file", default=None); p.add_argument("--job"); p.add_argument("--model"); p.add_argument("--prompt"); p.add_argument("--seed")
    p.set_defaults(fn=cmd_pick)
    p = sub.add_parser("render-shots", help="one clip per shot of a picked plan (VISUAL_SPEC.md §8.3)")
    p.add_argument("slug"); p.add_argument("--force", action="store_true"); p.add_argument("--only", default="")
    p.add_argument("--workers", type=int, default=None); p.set_defaults(fn=cmd_render_shots)
    p = sub.add_parser("shots-fill", help="snap shots.json to legal cuts and fill says, reveals and labels from the timing")
    p.add_argument("slug"); p.set_defaults(fn=cmd_shots_fill)
    p = sub.add_parser("shots-validate", help="check shots.json against VISUAL_SPEC.md §4, §5, §7.4 and §14.8")
    p.add_argument("slug"); p.add_argument("--picked", action="store_true", help="also check every pick (after visual-pick)")
    p.set_defaults(fn=cmd_shots_validate)
    p = sub.add_parser("source", help="candidates, filters and contact sheets for every world shot (VISUAL_SPEC.md §6)")
    p.add_argument("slug"); p.add_argument("--shot", default=None, help="one shot, e.g. s012")
    p.set_defaults(fn=cmd_source)
    for name, module in (("tts", "tts"), ("render-scenes", "render_scenes"), ("assemble", "assemble"),
                         ("qa", "qa"), ("thumbnail", "thumbnail"), ("describe", "describe"), ("shorts", "shorts"),
                         ("upload", "upload")):
        p = sub.add_parser(name); p.add_argument("slug"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=_step(module))
    sub.add_parser("template").set_defaults(fn=cmd_template)
    sub.add_parser("render-lessons").set_defaults(fn=cmd_render_lessons)
    sub.add_parser("embed-lessons").set_defaults(fn=cmd_embed_lessons)
    p = sub.add_parser("style-lock"); p.add_argument("slug"); p.set_defaults(fn=cmd_style_lock)
    sub.add_parser("youtube-auth").set_defaults(fn=cmd_youtube_auth)
    p = sub.add_parser("voice-clone", help="instant clone from the founder's own recordings"); p.add_argument("--name", required=True); p.add_argument("--description", default=""); p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_voice_clone)
    p = sub.add_parser("voice-preview", help="hear a parked script's hook and first chapter in the configured voice"); p.add_argument("slug"); p.add_argument("--text", default=None); p.add_argument("--voice", default=None); p.set_defaults(fn=cmd_voice_preview)
    p = sub.add_parser("next"); p.add_argument("--dry", action="store_true", help="report without changing the queue"); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("status"); p.add_argument("--md", action="store_true"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("voice"); p.add_argument("slug"); p.add_argument("voice", choices=["own", "founder", "library"]); p.set_defaults(fn=cmd_voice)
    p = sub.add_parser("takes-to-vo", help="the founder's own takes (record.mjs) as the unit's narration")
    p.add_argument("slug"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_takes_to_vo)
    p = sub.add_parser("mark"); p.add_argument("unit"); p.add_argument("step"); p.add_argument("outcome", choices=["done", "failed", "blocked", "awaiting"]); p.add_argument("note", nargs="?", default=""); p.set_defaults(fn=cmd_mark)
    p = sub.add_parser("unblock"); p.add_argument("unit"); p.add_argument("--note", default=""); p.set_defaults(fn=cmd_unblock)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
