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
