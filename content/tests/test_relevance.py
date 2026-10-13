"""Picture relevance: candidates that show something else are not picked; doubtful shots go to one capped reply."""
import json
import stat
import sys

from hubricon_content import film_qa, line, relevance
from hubricon_content import script as scriptmod


def _film(tmp_path, monkeypatch, cands):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    (tmp_path / "sources").mkdir()
    plan = {"shots": [{"id": "s001", "start": 0, "end": 6, "room": "world", "kind": "still", "style": "still-push",
                       "says": "a five and ten cent store", "query": ["five and ten store"]}]}
    (tmp_path / "shots.json").write_text(json.dumps(plan))
    (tmp_path / "sources" / "s001.json").write_text(json.dumps({"candidates": cands}))
    picks = []
    monkeypatch.setattr(line.pk, "pick", lambda slug, sid, nums, reason="": picks.append((sid, nums, reason)))
    return picks


def test_auto_pick_takes_relevance_over_rank_and_never_a_picture_below_the_threshold(tmp_path, monkeypatch):
    picks = _film(tmp_path, monkeypatch, [
        {"id": "a", "sheet_index": 0, "rank": 1, "passed_filters": True, "relevance": -0.05},   # a winery: rank 1, wrong
        {"id": "b", "sheet_index": 1, "rank": 2, "passed_filters": True, "relevance": 0.01},
        {"id": "c", "sheet_index": 2, "rank": 3, "passed_filters": True, "relevance": 0.10}])   # the 5 & 10 store poster
    res = line.auto_pick("f")
    assert picks[0][1] == [2] and "relevance +0.100" in picks[0][2] and res["low"] == []
    picks.clear()
    _ = (tmp_path / "sources" / "s001.json").write_text(json.dumps({"candidates": [
        {"id": "a", "sheet_index": 0, "rank": 1, "passed_filters": True, "relevance": -0.05},
        {"id": "b", "sheet_index": 1, "rank": 2, "passed_filters": True, "relevance": 0.02}]}))
    res = line.auto_pick("f")
    assert picks[0][1] == [1] and res["low"] == ["s001"]                          # the best eligible, flagged for a look
    assert relevance.blend({"relevance": 0.05}, 0) > relevance.blend({"relevance": 0.05}, 9)


def test_the_visual_pick_reply_sends_contact_sheets_within_its_budget_and_applies_the_answer(tmp_path, monkeypatch):
    from PIL import Image
    from hubricon_content import ai_step
    picks = _film(tmp_path, monkeypatch, [{"id": "a", "sheet_index": 0, "passed_filters": True, "relevance": 0.01},
                                          {"id": "b", "sheet_index": 1, "passed_filters": True, "relevance": 0.02}])
    Image.new("RGB", (1200, 1600), (90, 90, 90)).save(tmp_path / "sources" / "s001.jpg")
    seen = {}

    def fake_reply(slug, step, system, prompt, images=None, **k):
        seen.update(step=step, images=len(images or []), prompt=prompt)
        return {"status": "ok", "result": '{"shots": {"s001": 1}}', "weighted_tokens": 2400}
    monkeypatch.setattr(ai_step, "reply", fake_reply)
    monkeypatch.setattr(ai_step, "budgets", lambda: {"steps": {"pick": {"tokens": 30000}}})
    res = line.visual_pick("f", ["s001"])
    assert seen["step"] == "pick" and seen["images"] == 1 and "s001" in seen["prompt"] and "+0.02" in seen["prompt"]
    assert res["reviewed"] == 1 and res["chosen"] == ["s001"] and picks[-1][1] == [1] and "visual-pick" in picks[-1][2]
    monkeypatch.setattr(ai_step, "budgets", lambda: {"steps": {"pick": {"tokens": 2000}}})
    assert line.visual_pick("f", ["s001"])["reviewed"] == 0                       # a sheet that can't fit is never sent


def test_film_qa_reports_the_median_relevance_and_the_model_reviewed_shots(tmp_path):
    plan = {"shots": [{"id": "s1", "room": "world", "relevance": 0.04}, {"id": "s2", "room": "world", "relevance": 0.10},
                      {"id": "s3", "room": "world", "relevance": 0.12}, {"id": "s4", "room": "paper"}]}
    (tmp_path / "assets.json").write_text(json.dumps({"s2": {"reason": "visual-pick: chosen from its contact sheet"}, "s3": {"reason": "auto-pick"}}))
    assert film_qa.relevance_report(tmp_path, plan) == {"median": 0.1, "scored": 3, "model_reviewed": 1}


def test_a_visual_pick_answer_is_kept_and_never_paid_for_twice(tmp_path, monkeypatch):
    from PIL import Image
    from hubricon_content import ai_step
    _film(tmp_path, monkeypatch, [{"id": "a", "sheet_index": 0, "passed_filters": True, "relevance": 0.01}])
    Image.new("RGB", (600, 800)).save(tmp_path / "sources" / "s001.jpg")
    calls = []
    monkeypatch.setattr(ai_step, "reply", lambda *a, **k: (calls.append(1), {"status": "ok", "result": '{"shots": {"s001": 0}}', "weighted_tokens": 900})[1])
    monkeypatch.setattr(ai_step, "budgets", lambda: {"steps": {"pick": {"tokens": 30000}}})
    def refuse(*a, **k):
        raise RuntimeError("commons: HTTP 429")
    monkeypatch.setattr(line.pk, "pick", refuse)
    assert line.visual_pick("f", ["s001"])["chosen"] == []          # the download refused: the shot keeps its picture
    again = line.visual_pick("f", ["s001"])
    assert calls == [1] and again["status"] == "reused" and again["weighted_tokens"] == 0
