"""Every AI run of the content pipeline goes through here, under a hard token budget
(docs/content/FILM_LINE.md, content/film/budgets.json).

    hubricon-content ai-step <slug> <step> (--prompt TEXT | --prompt-file FILE) [--model M] [--budget N]
    hubricon-content ai-tick --prompt TEXT [--model M] -- <claude args>     (the unattended runner)

Tokens are counted as the API reports them on each assistant message, weighted to cost (input 1,
cache write 1.25, cache read 0.1, output 5), so one budget number means the same thing for a short
pass and a long one. A run is stopped the moment it spends its budget.
- A film step is counted in the film's meter (meter.json), and a film stops starting steps once its
  own total is spent.
- A runner tick is counted in the runner's ledger (content/.cache/runner-meter.json) against a
  per-tick, per-day and per-week cap. A tick past a cap does not start.
Rendering, sourcing, grading, mixing and QA never come here: they cost no tokens.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from . import meter
from .state import CONTENT_DIR

WEIGHTS = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1, "output_tokens": 5.0}
BUDGETS = CONTENT_DIR / "film" / "budgets.json"
LEDGER = CONTENT_DIR / ".cache" / "runner-meter.json"
CLAUDE = os.environ.get("CLAUDE_BIN", "/home/lp9/.local/bin/claude")
# a film step may run the content CLI and edit the film's files, as the runner may, and nothing more
STEP_ARGS = ("--settings", str(CONTENT_DIR.parent / "scripts" / "content-runner.settings.json"),
             "--permission-mode", "acceptEdits", "--max-turns", "120", "--no-session-persistence", "--strict-mcp-config")


def budgets() -> dict:
    return json.loads(BUDGETS.read_text(encoding="utf-8"))


def weigh(usage: dict) -> float:
    return sum(w * float(usage.get(k) or 0) for k, w in WEIGHTS.items())


def stream(cmd: list[str], budget: int, cwd: str | Path) -> dict:
    """Run `claude -p … --output-format stream-json --verbose`, stopping it the moment it spends its budget."""
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, cwd=str(cwd))
    per_msg: dict[str, dict] = {}       # one API message streams as several events: count it once
    result, stopped, chars = None, False, 0
    for line in proc.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "stream_event":
            # the output as it is written (text, thinking, tool input): a long reply reports its tokens
            # only at its end, so it is counted here, about 3.5 characters a token (G02's plan step
            # spent 1.3M against a 700k budget before this)
            delta = (ev.get("event") or {}).get("delta") or {}
            chars += len(delta.get("text") or delta.get("thinking") or delta.get("partial_json") or "")
        elif ev.get("type") == "assistant":
            msg = ev.get("message") or {}
            per_msg[msg.get("id") or f"m{len(per_msg)}"] = msg.get("usage") or {}
        elif ev.get("type") == "result":
            result = ev
            continue
        reported = sum(weigh(u) for u in per_msg.values())
        out_reported = sum(float(u.get("output_tokens") or 0) for u in per_msg.values())
        if reported + WEIGHTS["output_tokens"] * max(0.0, chars / 3.5 - out_reported) > budget:
            stopped = True
            proc.terminate()
            break
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    usage = {k: sum(int(u.get(k) or 0) for u in per_msg.values()) for k in WEIGHTS}
    if result and isinstance(result.get("usage"), dict):
        # the run's own total can under-count (G02's plan reported 188 output tokens for a session that
        # wrote whole scripts): neither count is trusted alone, the larger of the two is kept, field by field
        usage = {k: max(usage[k], int(result["usage"].get(k) or 0)) for k in WEIGHTS}
    return {"usage": usage, "weighted": round(weigh(usage)), "stopped": stopped, "result": result,
            "seconds": round(time.time() - t0, 1)}


def _cmd(claude: str | None, prompt: str, model: str, extra, effort: str = "low") -> list[str]:
    # effort sets how much the model thinks before it answers: a film step makes many small judgments,
    # not one deep one, so it runs low unless budgets.json says otherwise
    return [claude or CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose", "--include-partial-messages",
            "--model", model, "--effort", effort, *extra]


def run(slug: str, step: str, prompt: str, *, model: str | None = None, budget: int | None = None,
        cwd: str | Path | None = None, claude: str | None = None, extra: tuple = ()) -> dict:
    """One AI step of a film, under its budget, counted in the film's meter."""
    b = budgets()
    cfg = b["steps"].get(step, b["default"])
    model, budget = model or cfg["model"], int(budget or cfg["tokens"])
    spent = meter.summary(slug)["ai_weighted_tokens"]
    if spent >= b["film"]:
        return {"status": "refused", "step": step, "reason": f"the film has spent {spent:,} of its {b['film']:,} weighted tokens"}
    budget = min(budget, b["film"] - spent)
    r = stream(_cmd(claude, prompt, model, extra, cfg.get("effort", "low")), budget, cwd or CONTENT_DIR.parent)
    cost = (r["result"] or {}).get("total_cost_usd")
    meter.count(slug, "claude", "weighted tokens", r["weighted"], step=step, model=model, budget=budget, stopped=r["stopped"],
                usage=r["usage"], seconds=r["seconds"], **({"cost_usd": cost} if cost is not None else {}))
    res = r["result"] or {}
    return {"status": "stopped at budget" if r["stopped"] else "ok" if res and not res.get("is_error") else "failed",
            "step": step, "model": model, "weighted_tokens": r["weighted"], "budget": budget, "usage": r["usage"],
            "seconds": r["seconds"], "result": res.get("result")}


def _ledger() -> list[dict]:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def runner_spent(now: datetime | None = None) -> dict:
    """The runner's weighted tokens today and this ISO week (UTC)."""
    now = now or datetime.now(timezone.utc)
    day, week = now.date().isoformat(), now.isocalendar()[:2]
    spent = {"day": 0, "week": 0}
    for r in _ledger():
        at = datetime.fromisoformat(r["at"])
        if at.isocalendar()[:2] == week:
            spent["week"] += r["weighted"]
            if at.date().isoformat() == day:
                spent["day"] += r["weighted"]
    return spent


def tick(prompt: str, *, model: str | None = None, cwd: str | Path | None = None, claude: str | None = None,
         extra: tuple = ()) -> dict:
    """One unattended runner session under the runner's caps. Returns the session's result event (the
    shape `--output-format json` prints), so the runner's own checks read it as before."""
    cfg = budgets()["runner"]
    spent = runner_spent()
    room = min(cfg["tick"], cfg["day"] - spent["day"], cfg["week"] - spent["week"])
    if room <= 0:
        return {"type": "result", "subtype": "budget", "is_error": False, "skipped": True,
                "result": f"runner budget spent (today {spent['day']:,} of {cfg['day']:,}; this week {spent['week']:,} of {cfg['week']:,})"}
    model = model or cfg["model"]
    r = stream(_cmd(claude, prompt, model, extra, cfg.get("effort", "medium")), int(room), cwd or CONTENT_DIR.parent)
    rows = _ledger()
    rows.append({"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "model": model, "weighted": r["weighted"],
                 "budget": int(room), "stopped": r["stopped"], "usage": r["usage"], "seconds": r["seconds"]})
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(rows[-2000:], indent=0) + "\n", encoding="utf-8")
    except OSError:
        pass
    res = dict(r["result"] or {"type": "result", "is_error": True, "result": "the session ended without a result"})
    res.update({"weighted_tokens": r["weighted"], "budget": int(room), "stopped_at_budget": r["stopped"]})
    return res
