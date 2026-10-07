"""Every AI step of a film runs here: one `claude -p` run with a hard token budget, counted into the
film's meter (docs/content/FILM_LINE.md, content/film/budgets.json).

    hubricon-content ai-step <slug> <step> (--prompt TEXT | --prompt-file FILE) [--model M] [--budget N]

Tokens are counted as the API reports them on each assistant message, weighted to cost (input 1,
cache write 1.25, cache read 0.1, output 5), so one budget number means the same thing for a short
pass and a long one. The run is stopped the moment it spends its budget, and a film stops starting
AI steps once its own total is spent. Rendering, sourcing, grading, mixing and QA never come here:
they cost no tokens.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from . import meter
from .state import CONTENT_DIR

WEIGHTS = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1, "output_tokens": 5.0}
BUDGETS = CONTENT_DIR / "film" / "budgets.json"
CLAUDE = os.environ.get("CLAUDE_BIN", "/home/lp9/.local/bin/claude")


def budgets() -> dict:
    return json.loads(BUDGETS.read_text(encoding="utf-8"))


def weigh(usage: dict) -> float:
    return sum(w * float(usage.get(k) or 0) for k, w in WEIGHTS.items())


def run(slug: str, step: str, prompt: str, *, model: str | None = None, budget: int | None = None,
        cwd: str | Path | None = None, claude: str | None = None, extra: tuple = ()) -> dict:
    b = budgets()
    cfg = b["steps"].get(step, b["default"])
    model, budget = model or cfg["model"], int(budget or cfg["tokens"])
    spent = meter.summary(slug)["ai_weighted_tokens"]
    if spent >= b["film"]:
        return {"status": "refused", "step": step, "reason": f"the film has spent {spent:,} of its {b['film']:,} weighted tokens"}
    budget = min(budget, b["film"] - spent)
    cmd = [claude or CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", model, *extra]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            cwd=str(cwd or CONTENT_DIR.parent))
    per_msg: dict[str, dict] = {}       # one API message streams as several events: count it once
    result, stopped, cost = None, False, None
    for line in proc.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            msg = ev.get("message") or {}
            per_msg[msg.get("id") or f"m{len(per_msg)}"] = msg.get("usage") or {}
            if sum(weigh(u) for u in per_msg.values()) > budget:
                stopped = True
                proc.terminate()
                break
        elif ev.get("type") == "result":
            result, cost = ev, ev.get("total_cost_usd")
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    usage = {k: sum(int(u.get(k) or 0) for u in per_msg.values()) for k in WEIGHTS}
    if result and isinstance(result.get("usage"), dict) and not stopped:
        usage = {k: int(result["usage"].get(k) or 0) for k in WEIGHTS}      # the run's own total, when it has one
    weighted = round(weigh(usage))
    seconds = round(time.time() - t0, 1)
    meter.count(slug, "claude", "weighted tokens", weighted, step=step, model=model, budget=budget, stopped=stopped,
                usage=usage, seconds=seconds, **({"cost_usd": cost} if cost is not None else {}))
    return {"status": "stopped at budget" if stopped else "ok" if result and not result.get("is_error") else "failed",
            "step": step, "model": model, "weighted_tokens": weighted, "budget": budget, "usage": usage, "seconds": seconds,
            "result": (result or {}).get("result")}
