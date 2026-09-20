"""The queue: what is done, what is next, and what a human must supply.

`content/queue.json` is the single source of truth for the unattended runner.
Every rule that keeps the pipeline honest is enforced here rather than by
convention: one unit in progress at a time, nothing renders before the founder
approves the script, nothing uploads before the final sign-off and a founder
voice, and a step that fails three times is parked as stuck instead of retried
forever.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parents[2]
QUEUE = CONTENT_DIR / "queue.json"
CALENDAR = CONTENT_DIR / "calendar.json"
STATE_MD = CONTENT_DIR / "STATE.md"

VIDEO_STEPS = ["facts", "script", "critique", "review", "tts", "timing", "scenes", "assemble",
               "qa", "thumbnail", "describe", "shorts", "approve_final", "upload"]
GATES = {"review", "approve_final"}
MAX_ATTEMPTS = 3
MAX_AWAITING = 5
FIRST_VIDEO = "V01"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load() -> dict:
    if not QUEUE.exists():
        raise SystemExit(f"{QUEUE} missing — run `hubricon-content init`")
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save(q: dict) -> None:
    q["updated_at"] = now()
    QUEUE.write_text(json.dumps(q, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def unit(q: dict, ref: str) -> dict:
    """A unit by id or by video slug."""
    for u in q["units"]:
        if u["id"] == ref or u.get("slug") == ref:
            return u
    raise SystemExit(f"no unit {ref!r} in queue.json")


def log(u: dict, step: str, note: str) -> None:
    u.setdefault("log", []).append({"at": now(), "step": step, "note": note[:400]})


# ── capabilities ───────────────────────────────────────────────────────────

def capabilities() -> dict:
    """What the environment can do right now. Values only, never secrets."""
    secrets = CONTENT_DIR / ".secrets"
    return {
        "elevenlabs_key": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "founder_voice_id": os.environ.get("ELEVENLABS_VOICE_ID") or None,
        "youtube_token": (secrets / "youtube-token.json").exists(),
        "youtube_client": (secrets / "client_secret.json").exists(),
        "textures_cached": (CONTENT_DIR / "assets" / "textures" / "manifest.json").exists(),
        "music_bed": ("licensed" if any((CONTENT_DIR / "assets" / "music").glob("*.wav"))
                      else "elevenlabs" if (CONTENT_DIR / "assets" / "music" / "bed-elevenlabs.mp3").exists() else "procedural"),
        "sfx": "elevenlabs" if (CONTENT_DIR / "assets" / "sfx" / "tick.mp3").exists() else "procedural",
    }


def refresh_capabilities(q: dict) -> None:
    caps = capabilities()
    q["capabilities"] = caps
    # A unit blocked on an input that has since arrived goes back to work.
    for u in q["units"]:
        if u.get("status") != "blocked":
            continue
        reason = (u.get("blocked_on") or "").lower()
        freed = (
            ("elevenlabs_api_key" in reason and caps["elevenlabs_key"]) or
            ("elevenlabs_voice_id" in reason and caps["founder_voice_id"]) or
            ("client_secret.json" in reason and caps["youtube_client"]) or
            ("youtube-token" in reason and caps["youtube_token"])
        )
        if freed:
            u["status"] = "todo"
            u["blocked_on"] = None
            for s, v in list(u.get("steps", {}).items()):
                if v == "blocked":
                    u["steps"][s] = "todo"
            log(u, "unblock", "input arrived; unit returned to the queue")


# ── seeding ────────────────────────────────────────────────────────────────

def _video_unit(day: dict) -> dict:
    steps = {s: "todo" for s in VIDEO_STEPS}
    steps["upload"] = "blocked"
    return {
        "id": f"V{day['day']:02d}", "phase": 2 if day["day"] == 1 else 3, "kind": "video",
        "day": day["day"], "title": day["title"], "pillar": day["pillar"], "tier": day["tier"],
        "slug": day["slug"], "models": day["models"],
        "status": "todo" if day["producible"] else "blocked",
        "blocked_on": None if day["producible"] else day.get("blocked_reason"),
        "requires_done": day.get("requires_done"),
        "voice": None, "publishable": False, "steps": steps,
        "review_notes": [], "attempts": {}, "log": [],
    }


def _checklist_unit(uid: str, phase: int, kind: str, title: str, items: list[str], order: int = 0) -> dict:
    return {"id": uid, "phase": phase, "kind": kind, "title": title, "status": "todo", "order": order,
            "checklist": [{"item": i, "done": False} for i in items],
            "attempts": {}, "blocked_on": None, "log": []}


PHASE1 = [
    ("P1-template", "Reimbursement Playbook spreadsheet template", [
        "Run `hubricon-content template` to build learn/reimbursement-playbook-template.xlsx from recovery.py's constants and the demo rows; open it with openpyxl and confirm every sheet listed in docs/content/hubricon-learn-build-prompt.md §1 exists.",
        "Run `pytest content/tests/test_template_parity.py` and make it pass (constants, reason map, and the Claims sheet's logic equal recovery.run on the demo rows).",
    ]),
    ("P1-lessons", "Reimbursement Playbook written lessons", [
        "Run `hubricon-content facts playbook` to produce content/videos/playbook/facts.json from recovery.run on the demo catalogue.",
        "Write the six lessons to content/learn/lessons/L1.md … L6.md per the plan (L1 open: what Amazon owes you and the four reports it hides in; L2 warehouse lost/damaged; L3 carrier/transit; L4 refund without return; L5 damaged returns; L6 reversals, filing wording, EV triage and the calendar). Every dollar figure is a {{key}} from facts.json; render with `hubricon-content render-lessons`.",
        "Run the critique skill in copy mode on each rendered lesson; fix until it passes.",
    ]),
    ("P1-api-learn", "api/learn.js capture and routing", [
        "Write api/learn.js by copying api/gate.js's skeleton: kind learn_capture, server-side route like apply.html fitTag (below for Under $3M or Wholesale/Arbitrage; none for Mixed/other under $3M), no prospect row, template email via lib/tool_email.js sendResend when RESEND_API_KEY is set.",
        "Write api/learn.test.mjs (node --test) covering validation, honeypot and the three routes; run `node --test api/learn.test.mjs` and pass.",
    ]),
    ("P1-course-page", "learn/reimbursement-playbook.html", [
        "Build learn/reimbursement-playbook.html: three columns (sticky lesson nav / lesson body with the template button directly under the video slot / sticky six-field form), mobile collapse, lessons 2–6 in <section hidden data-gated>, unlock on submit via localStorage, routing panel core/below/none, one CTA. Reuse the tokens, nav and footer markup from index.html and GATE_QUESTIONS from apply.html verbatim. Embed the rendered lessons from content/learn/lessons/rendered/.",
        "Run the critique skill in copy mode on the page; fix until it passes.",
    ]),
    ("P1-learn-hub", "learn/index.html", [
        "Build learn/index.html: one course card (badges New · Free), headline stating the position, under 200 words, same tokens/nav/footer as index.html, no other cards.",
        "Run the critique skill in copy mode; fix until it passes.",
    ]),
    ("P1-followup", "Recovered-amount follow-up", [
        "Add learn_followups() to engine/src/hubricon_engine/operator.py: seven days after a learn_capture with no learn_result_ask row for that email, send one email asking how much came back and for permission to publish the number and the brand; log funnel_events kind learn_result_ask; reply-to the founder. Wire it into operator.run behind the same send/dry flags as the other steps. Add a unit test with the operator's existing fixtures.",
    ]),
    ("P1-index-links", "Nav and footer links on index.html", [
        "Add `Learn` to .nav-links and `Free training` (href /learn) to the footer Product list on index.html; nothing in body copy. Record the visible word count before and after in the commit message.",
    ]),
]


def seed() -> dict:
    cal = json.loads(CALENDAR.read_text(encoding="utf-8"))
    units = [
        _checklist_unit("P0-tooling", 0, "setup", "Tooling, docs, skills, state, runner, timer", [
            "content venv on Python 3.13 with manim, elevenlabs, google client and the engine importable",
            "Fraunces fonts in content/assets/fonts and ~/.local/share/fonts",
            "docs/content holds the six governing documents; CLAUDE.md, .claude/settings.json, skills, runner, systemd units written",
            "queue.json seeded; STATE.md and REVIEW.md render",
            "demo catalogue committed and parsing through the engine; pytest content/tests passes",
        ]),
    ]
    units += [_checklist_unit(uid, 1, "learn", title, items, order=n) for n, (uid, title, items) in enumerate(PHASE1, start=1)]
    units += [_video_unit(d) for d in cal["days"]]
    q = {"version": 1, "updated_at": now(), "style_locked": False,
         "capabilities": capabilities(), "units": units}
    return q


# ── selection ──────────────────────────────────────────────────────────────

def _phase_open(q: dict, phase: int) -> bool:
    for u in q["units"]:
        if u["phase"] < phase and u["status"] not in ("done", "blocked", "stuck", "awaiting"):
            return False
    return True


def _next_step(u: dict) -> str | None:
    for s in VIDEO_STEPS:
        if u["steps"].get(s) not in ("done", "approved"):
            return s
    return None


def next_item(q: dict) -> dict:
    """The one thing to do now, or why there is nothing."""
    refresh_capabilities(q)
    awaiting = sum(1 for u in q["units"] if u["status"] == "awaiting")
    done_videos = sum(1 for u in q["units"] if u["kind"] == "video" and u["status"] == "done")
    candidates = [u for u in q["units"] if u["status"] in ("in_progress", "todo")]

    def started(x):
        if x["kind"] == "video":
            return any(v in ("done", "approved", "awaiting", "in_progress") for v in x["steps"].values())
        return any(c["done"] for c in x["checklist"])

    def priority(x):
        # an interrupted step is finished first; a unit the founder just approved
        # resumes before anything new is drafted; then the calendar order
        mid = x["kind"] == "video" and "in_progress" in x["steps"].values()
        resumed = x["kind"] == "video" and _next_step(x) in ("tts", "upload") and x["steps"].get("review") == "approved"
        return (0 if mid else 1 if resumed else 2 if x["status"] == "in_progress" else 3, x["phase"],
                x.get("order") or 0, x.get("day") or 0, x["id"])

    for u in sorted(candidates, key=priority):
        # the phase gate applies to starting a unit; one already under way finishes on its own merits
        if not started(u) and not _phase_open(q, u["phase"]):
            continue
        if u["kind"] != "video":
            for i, c in enumerate(u["checklist"]):
                if not c["done"]:
                    for other in q["units"]:
                        if other is not u and other["status"] == "in_progress":
                            other["status"] = "todo"
                    u["status"] = "in_progress"
                    return {"unit": u["id"], "kind": u["kind"], "step": f"checklist:{i}", "item": c["item"]}
            u["status"] = "done"
            continue
        if u.get("requires_done") and done_videos < u["requires_done"]:
            continue
        step = _next_step(u)
        if step is None:
            u["status"] = "done"
            continue
        if u["status"] == "todo" and awaiting >= MAX_AWAITING and u["steps"]["review"] != "approved":
            continue  # the founder's inbox is full; draft nothing more
        if step == "scenes" and not q.get("style_locked") and not u["id"].startswith(FIRST_VIDEO):
            continue  # nothing after the first video renders before the style is locked
        if step == "upload" and not u.get("publishable"):
            continue  # waits for a founder voice and the final sign-off
        if u["steps"][step] == "awaiting":
            u["status"] = "awaiting"
            continue
        for other in q["units"]:
            if other is not u and other["status"] == "in_progress":
                other["status"] = "todo"   # between steps; its step states persist
        u["status"] = "in_progress"
        u["steps"][step] = "in_progress"
        return {"unit": u["id"], "kind": "video", "step": step, "slug": u["slug"], "tier": u["tier"],
                "pillar": u["pillar"], "title": u["title"]}
    reasons = []
    if awaiting:
        reasons.append(f"{awaiting} unit(s) await the founder's review (content/REVIEW.md)")
    blocked = [u for u in q["units"] if u["status"] == "blocked"]
    if blocked:
        reasons.append(f"{len(blocked)} unit(s) blocked on founder input (content/STATE.md)")
    return {"idle": True, "reason": "; ".join(reasons) or "queue complete"}


# ── transitions ────────────────────────────────────────────────────────────

def mark(q: dict, ref: str, step: str, outcome: str, note: str = "") -> dict:
    u = unit(q, ref)
    if step.startswith("checklist:"):
        i = int(step.split(":", 1)[1])
        if outcome == "done":
            u["checklist"][i]["done"] = True
            if all(c["done"] for c in u["checklist"]):
                u["status"] = "done"
        elif outcome == "blocked":
            u["status"], u["blocked_on"] = "blocked", note
        else:
            u["attempts"][step] = u["attempts"].get(step, 0) + 1
            if u["attempts"][step] >= MAX_ATTEMPTS:
                u["status"] = "stuck"
        log(u, step, f"{outcome} {note}".strip())
        return u
    if step not in VIDEO_STEPS:
        raise SystemExit(f"unknown step {step!r}")
    if outcome == "done":
        u["steps"][step] = "done"
        if _next_step(u) is None:
            u["status"] = "done"
    elif outcome == "awaiting":
        u["steps"][step] = "awaiting"
        u["status"] = "awaiting"
    elif outcome == "blocked":
        u["steps"][step] = "blocked"
        u["status"], u["blocked_on"] = "blocked", note
    elif outcome == "failed":
        u["attempts"][step] = u["attempts"].get(step, 0) + 1
        u["steps"][step] = "todo"
        if u["attempts"][step] >= MAX_ATTEMPTS:
            u["status"] = "stuck"
    else:
        raise SystemExit(f"unknown outcome {outcome!r}")
    log(u, step, f"{outcome} {note}".strip())
    return u


def approve(q: dict, ref: str, gate: str = "review", note: str = "") -> dict:
    u = unit(q, ref)
    if u["steps"].get(gate) != "awaiting":
        raise SystemExit(f"{u['id']} is not awaiting {gate} (it is {u['steps'].get(gate)})")
    u["steps"][gate] = "approved"
    u["status"] = "todo"
    if gate == "approve_final":
        u["publishable"] = bool(u.get("voice") == "founder" and u["steps"].get("qa") == "done")
        u["steps"]["upload"] = "todo" if u["publishable"] else "blocked"
        if not u["publishable"]:
            u["blocked_on"] = None  # not a block on the unit; upload alone waits
    log(u, gate, f"approved by the founder {note}".strip())
    return u


def reject(q: dict, ref: str, gate: str, note: str) -> dict:
    u = unit(q, ref)
    if u["steps"].get(gate) != "awaiting":
        raise SystemExit(f"{u['id']} is not awaiting {gate}")
    u.setdefault("review_notes", []).append({"at": now(), "gate": gate, "note": note})
    # Send the unit back to the step the note is about: the script for the
    # first gate, the render chain for the second.
    back_to = "script" if gate == "review" else "scenes"
    for s in VIDEO_STEPS[VIDEO_STEPS.index(back_to):]:
        u["steps"][s] = "blocked" if s == "upload" else "todo"
    u["attempts"][gate] = u["attempts"].get(gate, 0) + 1
    u["status"] = "stuck" if u["attempts"][gate] >= MAX_ATTEMPTS else "todo"
    log(u, gate, f"rejected: {note}")
    return u


# ── STATE.md ───────────────────────────────────────────────────────────────

FOUNDER_INPUTS = [
    "Your voice: 3 to 5 minutes of clean audio now (see `docs/content/VOICE-RECORDING.md`), then `hubricon-content voice-clone --name \"Hagen Simmons\" <wav files>` and `ELEVENLABS_VOICE_ID` in `/home/lp9/Hubricon/HubriconB2B/.env`. Nothing renders in any other voice.",
    "ElevenLabs tier: Starter's 40,000 characters a month covers about six videos. Creator (100,000) unlocks the professional clone the series should ship on; Pro (500,000) covers a video a day.",
    "YouTube: a Google Cloud OAuth client JSON at `content/.secrets/client_secret.json`, then one interactive `hubricon-content youtube-auth` in a browser.",
    "One interactive Higgsfield texture batch saved to `content/assets/textures/` with `manifest.json` (or accept the procedural fallback).",
    "A licensed music bed in `content/assets/music/` (or ElevenLabs music once the key exists).",
    "Course 1 screen recordings (one raw 4–8 minute recording per lesson) and Seller Central screenshots for the pillar-1 Desk videos.",
    "`loginctl enable-linger lp9` (sudo if refused); optional `sudo pacman -S espeak-ng texlive-basic texlive-latexextra`.",
    "Merge the `content → main` pull request when `/learn` is ready; deploy is a push to `main`.",
]


def render_state(q: dict) -> str:
    caps = q.get("capabilities", {})
    lines = ["# Content pipeline — state", "", f"Updated {q.get('updated_at')} · style locked: {q.get('style_locked')}", ""]
    lines += ["## Capabilities", ""] + [f"- {k}: {v}" for k, v in caps.items()] + [""]
    cur = [u for u in q["units"] if u["status"] == "in_progress"]
    lines += ["## Now", ""]
    lines += [f"- {u['id']} · {u['title']} · step {_next_step(u) if u['kind'] == 'video' else 'checklist'}" for u in cur] or ["- idle"]
    lines += ["", "## Awaiting your review", ""]
    aw = [u for u in q["units"] if u["status"] == "awaiting"]
    lines += [f"- {u['id']} · {u['title']} · gate `{[s for s in GATES if u['steps'].get(s) == 'awaiting'][0]}` → see `content/REVIEW.md`" for u in aw] or ["- nothing waiting"]
    lines += ["", "## Done", ""]
    lines += [f"- {u['id']} · {u['title']}" for u in q["units"] if u["status"] == "done"] or ["- nothing yet"]
    lines += ["", "## Blocked on founder input", ""]
    bl = [u for u in q["units"] if u["status"] == "blocked"]
    lines += [f"- {u['id']} · {u['title']}: {u.get('blocked_on')}" for u in bl] or ["- none"]
    lines += ["", "### Inputs the pipeline needs from you", ""] + [f"{i}. {t}" for i, t in enumerate(FOUNDER_INPUTS, 1)]
    lines += ["", "## Stuck (three failures; needs a look)", ""]
    st = [u for u in q["units"] if u["status"] == "stuck"]
    lines += [f"- {u['id']} · {u['title']}: {(u.get('log') or [{}])[-1].get('note', '')}" for u in st] or ["- none"]
    lines += ["", "## Next five", ""]
    todo = sorted([u for u in q["units"] if u["status"] == "todo"], key=lambda x: (x["phase"], x.get("day") or 0, x["id"]))[:5]
    lines += [f"- {u['id']} · {u['title']}" for u in todo] or ["- none"]
    return "\n".join(lines) + "\n"
