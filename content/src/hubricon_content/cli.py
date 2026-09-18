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


def cmd_next(a):
    q = _q()
    item = state.next_item(q)
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


def cmd_template(a):
    from . import playbook_template
    p = playbook_template.build()
    print(p)


def cmd_render_lessons(a):
    from . import lessons
    print(lessons.render_all())


def cmd_style_lock(a):
    from . import stylelock
    q = _q()
    p = stylelock.write(a.slug, q)
    state.save(q)
    print(p)


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
    for name, module in (("tts", "tts"), ("timing", "timing"), ("render-scenes", "render_scenes"), ("assemble", "assemble"),
                         ("qa", "qa"), ("thumbnail", "thumbnail"), ("describe", "describe"), ("shorts", "shorts"),
                         ("upload", "upload")):
        p = sub.add_parser(name); p.add_argument("slug"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=_step(module))
    sub.add_parser("template").set_defaults(fn=cmd_template)
    sub.add_parser("render-lessons").set_defaults(fn=cmd_render_lessons)
    p = sub.add_parser("style-lock"); p.add_argument("slug"); p.set_defaults(fn=cmd_style_lock)
    sub.add_parser("youtube-auth").set_defaults(fn=cmd_youtube_auth)
    sub.add_parser("next").set_defaults(fn=cmd_next)
    p = sub.add_parser("status"); p.add_argument("--md", action="store_true"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("mark"); p.add_argument("unit"); p.add_argument("step"); p.add_argument("outcome", choices=["done", "failed", "blocked", "awaiting"]); p.add_argument("note", nargs="?", default=""); p.set_defaults(fn=cmd_mark)
    p = sub.add_parser("unblock"); p.add_argument("unit"); p.add_argument("--note", default=""); p.set_defaults(fn=cmd_unblock)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
