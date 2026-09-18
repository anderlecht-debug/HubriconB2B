"""The founder's inbox: `content/REVIEW.md` and the email that points at it.

A unit that reaches a gate is parked here with everything needed to judge it in
one read — the rendered script with each figure's key beside it, the shot list,
the hooks, the thumbnail concept — and the two commands that move it on.
"""

import json
import os
from pathlib import Path

from hubricon_engine.narrate import PLACEHOLDER

from . import script as scriptmod
from . import state
from .state import CONTENT_DIR

REVIEW_MD = CONTENT_DIR / "REVIEW.md"


def _render_with_keys(text: str, facts: dict) -> str:
    return PLACEHOLDER.sub(lambda m: f"{facts[m.group(1)]['value']} ⟨{m.group(1)}⟩" if m.group(1) in facts else m.group(0), text)


def script_block(u: dict) -> str:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    facts = json.loads((d / "facts.json").read_text(encoding="utf-8"))
    sc = scriptmod.parse((d / "script.md").read_text(encoding="utf-8"))
    h = sc["header"]
    secs = scriptmod.estimate_seconds(sc, facts)
    out = [f"## {u['id']} · day {u.get('day')} · tier {u.get('tier')} · pillar {u.get('pillar')} — script gate", "",
           f"**Title:** {_render_with_keys(h.get('TITLE', ''), facts)}  ",
           f"**Thumbnail:** {_render_with_keys(h.get('THUMBNAIL', ''), facts)}  ",
           f"**Spiky claim:** {h.get('SPIKY CLAIM', '')}  ",
           f"**Misconception:** {h.get('MISCONCEPTION', '')}  ",
           f"**CTA:** {_render_with_keys(h.get('CTA', ''), facts)}  ",
           f"**Estimated runtime:** about {secs // 60} min {secs % 60:02d} s · **voice:** {u.get('voice') or 'placeholder until the clone exists'}", "",
           "### Hooks (the first is the one that ships unless you say otherwise)", ""]
    for i in sorted(sc["hooks"]):
        out.append(f"{i}. {_render_with_keys(sc['hooks'][i], facts)}")
    out += ["", "### Script", ""]
    for b in sc["beats"]:
        out.append(f"**[{b['at'] // 60}:{b['at'] % 60:02d}] {b['name']}**  ")
        out.append(_render_with_keys(b["VO"], facts) + "  ")
        if b["CTA"]:
            out.append(f"*CTA:* {_render_with_keys(b['CTA'], facts)}  ")
        out.append("")
    out += ["### Shot list", "", "| at | scene | data source |", "|---|---|---|"]
    for b in sc["beats"]:
        out.append(f"| {b['at'] // 60}:{b['at'] % 60:02d} | {b['VISUAL']} | {b['DATA SOURCE']} |")
    notes = u.get("review_notes") or []
    if notes:
        out += ["", "### Your earlier notes", ""] + [f"- {n['note']}" for n in notes]
    out += ["", "### Decide", "", "```",
            f"hubricon-content approve {slug}",
            f"hubricon-content reject  {slug} --note \"what to change\"",
            "```", f"Edit `content/videos/{slug}/script.md` first if you prefer; it is re-validated on approve.", ""]
    return "\n".join(out)


def final_block(u: dict) -> str:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    qa = {}
    if (d / "qa.json").exists():
        qa = json.loads((d / "qa.json").read_text(encoding="utf-8"))
    out = [f"## {u['id']} · {u['title']} — final gate", "",
           f"- Master: `content/videos/{slug}/media/master.mp4`",
           f"- Thumbnail: `content/videos/{slug}/thumbnail.png`",
           f"- Description: `content/videos/{slug}/description.md`",
           f"- Shorts: `content/videos/{slug}/shorts/`",
           f"- Voice: {u.get('voice')} · publishable once approved: {u.get('voice') == 'founder'}",
           f"- QA: {json.dumps({k: v for k, v in qa.items() if k in ('pass', 'duration_s', 'lufs', 'max_hold_s', 'subtitle_coverage')})}", "",
           "```", f"hubricon-content approve-final {slug}", f"hubricon-content reject-final {slug} --note \"what to change\"", "```", ""]
    return "\n".join(out)


def build(q: dict) -> str:
    blocks = []
    for u in q["units"]:
        if u["kind"] != "video":
            continue
        if u["steps"].get("review") == "awaiting":
            blocks.append(script_block(u))
        elif u["steps"].get("approve_final") == "awaiting":
            blocks.append(final_block(u))
    head = ["# Review inbox", "", f"Updated {state.now()}. Everything here is parked until you decide. "
            "Nothing renders before a script is approved; nothing uploads before the final sign-off.", ""]
    body = blocks or ["Nothing waiting for you.", ""]
    text = "\n".join(head + body)
    REVIEW_MD.write_text(text, encoding="utf-8")
    return text


def notify(q: dict, u: dict, block: str) -> bool:
    to = os.environ.get("CONTENT_REVIEW_EMAIL") or os.environ.get("EMAIL_REPLY_TO")
    if not to or not os.environ.get("RESEND_API_KEY"):
        return False
    try:
        from hubricon_engine.notify import send_email
    except Exception:
        return False
    subject = f"[Hubricon content] review: {u['id']} · {u['title']}"
    text = block + "\n\nFull inbox: content/REVIEW.md on the content branch."
    return bool(send_email(to, subject, text))


def enter(q: dict, ref: str, final: bool = False) -> dict:
    u = state.unit(q, ref)
    gate = "approve_final" if final else "review"
    state.mark(q, u["id"], gate, "awaiting")
    build(q)
    block = final_block(u) if final else script_block(u)
    sent = notify(q, u, block)
    state.log(u, gate, "parked for the founder" + (" (emailed)" if sent else ""))
    return {"unit": u["id"], "gate": gate, "status": "awaiting", "emailed": sent}
