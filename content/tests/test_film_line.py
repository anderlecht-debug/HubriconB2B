"""The film line's AI steps run under a hard budget and are metered (FILM_LINE.md)."""
import json
import stat
import sys

from hubricon_content import ai_step, meter
from hubricon_content import script as scriptmod


def fake_claude(tmp_path, per_message_output: int, messages: int):
    """A stand-in for `claude -p --output-format stream-json`: n assistant messages, then a result."""
    p = tmp_path / "claude"
    p.write_text(f"""#!{sys.executable}
import json, sys, time
for i in range({messages}):
    print(json.dumps({{"type": "assistant", "message": {{"id": f"m{{i}}", "usage": {{"input_tokens": 1000, "cache_read_input_tokens": 10000, "output_tokens": {per_message_output}}}}}}}), flush=True)
    time.sleep(0.01)
print(json.dumps({{"type": "result", "result": "done", "is_error": False}}), flush=True)
""")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_a_step_is_metered_by_cost_weight(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    res = ai_step.run("f", "review", "look", claude=fake_claude(tmp_path, 100, 3))
    assert res["status"] == "ok"
    # each message: 1000 input + 10000 cache reads x 0.1 + 100 output x 5 = 2500
    assert res["weighted_tokens"] == 7500
    rows = json.loads((tmp_path / "meter.json").read_text())
    assert rows[-1]["step"] == "review" and rows[-1]["quantity"] == 7500
    assert meter.summary("f")["ai_by_step"]["review"]["weighted"] == 7500


def test_a_step_is_stopped_the_moment_it_spends_its_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    res = ai_step.run("f", "review", "look", budget=10000, claude=fake_claude(tmp_path, 1000, 50))
    assert res["status"] == "stopped at budget"
    assert res["weighted_tokens"] <= 10000 + 7000           # at most the message that crossed the line


def test_a_film_past_its_total_starts_no_more_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    meter.count("f", "claude", "weighted tokens", ai_step.budgets()["film"], step="plan")
    res = ai_step.run("f", "fix", "go", claude=fake_claude(tmp_path, 1, 1))
    assert res["status"] == "refused"


def test_the_runner_stops_starting_ticks_once_its_day_is_spent(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_step, "LEDGER", tmp_path / "runner-meter.json")
    cfg = ai_step.budgets()["runner"]
    first = ai_step.tick("go", claude=fake_claude(tmp_path, 100, 2))
    assert first.get("result") == "done" and first["weighted_tokens"] == 2 * 2500
    from datetime import datetime, timezone
    rows = json.loads((tmp_path / "runner-meter.json").read_text())
    rows.append({"at": datetime.now(timezone.utc).isoformat(), "weighted": cfg["day"]})
    (tmp_path / "runner-meter.json").write_text(json.dumps(rows))
    second = ai_step.tick("go", claude=fake_claude(tmp_path, 100, 2))
    assert second.get("skipped") is True and "budget spent" in second["result"]


def test_a_long_reply_is_stopped_while_it_is_written(tmp_path, monkeypatch):
    """A reply reports its tokens only at its end: the guard counts its streamed output instead."""
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    p = tmp_path / "claude"
    p.write_text(f"""#!{sys.executable}
import json, time
for i in range(400):
    print(json.dumps({{"type": "stream_event", "event": {{"type": "content_block_delta", "delta": {{"thinking": "x" * 700}}}}}}), flush=True)
    time.sleep(0.005)
print(json.dumps({{"type": "assistant", "message": {{"id": "m0", "usage": {{"output_tokens": 80000}}}}}}), flush=True)
""")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    res = ai_step.run("f", "review", "think", budget=20000, claude=str(p))
    assert res["status"] == "stopped at budget"


def test_autofix_restores_a_landing_word_the_validator_asks_for(tmp_path, monkeypatch):
    from hubricon_content import line, shots
    from . import shotplan_fixture as fx
    plan, tm = fx.fresh()
    reg = shots.registry()["styles"]
    s = next(x for x in plan["shots"] if reg.get(x.get("style"), {}).get("on") == "required" and x.get("says"))
    s["on"] = None
    (tmp_path / "shots.json").write_text(json.dumps(plan))
    (tmp_path / "timing.json").write_text(json.dumps(tm))
    (tmp_path / "facts.json").write_text("{}")
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    monkeypatch.setattr(scriptmod, "load_facts", lambda slug: {})
    before = [p for p in shots.validate(plan, tm, {}) if p.startswith(s["id"]) and "set `on`" in p]
    assert before
    assert s["id"] in line.autofix("f")["fixed"]
    after = json.loads((tmp_path / "shots.json").read_text())
    assert next(x for x in after["shots"] if x["id"] == s["id"])["on"]


def test_a_reply_step_sends_its_prompt_on_stdin_with_no_tools_and_no_session_load(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    monkeypatch.setattr(ai_step, "REPLY_DIR", tmp_path / "reply")
    p = tmp_path / "claude"
    p.write_text(f"""#!{sys.executable}
import json, sys, os
prompt = sys.stdin.read()
args = sys.argv[1:]
out = {{"args": args, "prompt_chars": len(prompt), "cwd": os.getcwd()}}
print(json.dumps({{"type": "assistant", "message": {{"id": "m0", "usage": {{"input_tokens": 700, "output_tokens": 10}}}}}}), flush=True)
print(json.dumps({{"type": "result", "result": "```json\\n" + json.dumps({{"shots": {{"s001": {{"kind": "still"}}}}, "seen": out}}) + "\\n```", "is_error": False}}), flush=True)
""")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    brief = "x" * 200_000                                  # past Linux's 128 KB cap on one argument
    res = ai_step.reply("f", "plan", "Answer with JSON.", brief, claude=str(p))
    dec = ai_step.json_reply(res["result"])
    assert res["status"] == "ok" and dec["shots"] == {"s001": {"kind": "still"}}
    seen = dec["seen"]
    assert seen["prompt_chars"] == 200_000 and brief not in seen["args"]
    a = seen["args"]
    assert a[a.index("--tools") + 1] == "" and a[a.index("--system-prompt") + 1] == "Answer with JSON."
    assert "--max-turns" in a and seen["cwd"] == str(tmp_path / "reply")    # outside the repo: no CLAUDE.md, no memory
    assert res["weighted_tokens"] == 750
    assert ai_step.json_reply("no object here") is None and ai_step.json_reply("{broken") is None


def test_a_fix_brief_carries_the_shots_its_problems_name_and_their_neighbours(tmp_path, monkeypatch):
    from hubricon_content import plan_brief
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    shots = [{"id": i, "start": n, "end": n + 1, "kind": "still", "style": "still-push"}
             for n, i in enumerate(["a01", "a02", "a03", "a03b", "a04", "a05", "a06", "a07", "a08"])]
    (tmp_path / "shots.json").write_text(json.dumps({"shots": shots}))
    brief = plan_brief.fix_brief("f", ["a03b: two push moves back to back", "a06–a07: still-push three in a row"])
    carried = [json.loads(l)["id"] for l in brief.splitlines() if l.startswith('{"id"')]
    # named: a03b, and the run a06–a07; each with one either side. "a03" inside "a03b" is not a mention
    # of a03 (it comes in as a03b's neighbour), and a02 stays out
    assert carried == ["a03", "a03b", "a04", "a05", "a06", "a07", "a08"]
    assert "What you return" in brief and "a02" not in carried
