"""Rhythm and sound: BREATHE holds, MONTAGE runs, a motivated camera, fewer effects, a silence a chapter."""
import json
from types import SimpleNamespace

from hubricon_content import audio, plan_skeleton, render_shots
from hubricon_content import script as scriptmod


def _timing(breathe=False, montage=False, length=40.0):
    words = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(int(length / 0.5))]
    return {"segments": [{"kind": "beat", "start": 0.0, "end": length, "breathe": breathe, "montage": montage,
                          "visual": "a store", "words": words}]}


def test_a_breathe_beat_is_held_in_pictures_of_at_most_25_s_and_a_montage_beat_cut_every_2_to_3_s():
    cuts = [round(0.45 + 0.5 * i, 3) for i in range(80)]
    held = plan_skeleton._held(_timing(breathe=True), cuts, 3.0, [])
    shots = held[0][2]
    assert [s["style"] for s in shots] == ["breathe-hold", "breathe-hold"] and all(s["fixed"] and s["pictures"] for s in shots)
    assert all(s["end"] - s["start"] <= 25.0 for s in shots) and shots[0]["start"] == 0.0 and shots[-1]["end"] == 40.0
    run = plan_skeleton._held(_timing(montage=True, length=12.0), cuts, 3.0, [])[0][2]
    lens = [round(s["end"] - s["start"], 2) for s in run]
    assert all(s["style"] == "montage-cut" for s in run) and all(2.0 <= x <= 3.0 + 1e-6 for x in lens[:-1]) and lens[-1] >= 2.0


def test_the_decision_picks_a_fixed_shots_picture_and_nothing_else(tmp_path, monkeypatch):
    from hubricon_content import shots as shotmod
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    plan = {"shots": [{"id": "s001", "start": 0.0, "end": 20.0, "room": "world", "kind": "still", "style": "breathe-hold",
                       "fixed": True, "pictures": True, "query": [], "params": {}}]}
    (tmp_path / "shots.json").write_text(json.dumps(plan))
    monkeypatch.setattr(shotmod, "registry", lambda: {"styles": {}})
    monkeypatch.setattr(shotmod, "load_timing", lambda d: ({"segments": []}, None))
    monkeypatch.setattr(shotmod, "spoken", lambda t: [])
    plan_skeleton.apply("f", {"shots": {"s001": {"style": "still-push", "kind": "footage", "query": ["empty store"], "sources": ["loc"]}}})
    s = json.loads((tmp_path / "shots.json").read_text())["shots"][0]
    assert s["style"] == "breathe-hold" and s["kind"] == "still" and s["query"] == ["empty store"] and s["sources"] == ["loc"]


def test_ticks_mark_a_shots_first_figure_and_heroes_and_each_chapter_gets_its_silence():
    shots = [
        {"id": "s1", "room": "paper", "style": "number-pair", "start": 0.0, "end": 8.0, "reveals": [{"key": "a", "t": 1.0}, {"key": "b", "t": 3.0}, {"key": "c", "t": 5.0}]},
        {"id": "s2", "room": "paper", "style": "chapter", "start": 8.0, "end": 10.5, "reveals": []},
        {"id": "s3", "room": "world", "style": "breathe-hold", "start": 10.5, "end": 25.0, "reveals": []},
        {"id": "s4", "room": "paper", "style": "number-land", "on": "{{d}}", "start": 25.0, "end": 31.0, "reveals": [{"key": "d", "t": 26.0}]},
        {"id": "s5", "room": "paper", "style": "kinetic-thesis", "fixed": True, "start": 31.0, "end": 35.0, "reveals": []}]
    timing = {"duration": 35.0, "segments": [{"kind": "card", "start": 8.0, "end": 10.5}], "chapters": [{"at": 8.0, "title": "One"}]}
    ev = audio.score_events({"shots": shots}, timing)
    assert ev["ticks"] == [1.0, 5.0, 26.0]                         # the pair's first figure and its hero (5.0); never 3.0
    assert ev["breathe"] == [(10.5, 25.0)] and not any(10.5 <= t <= 25.0 for k in ("ticks", "rooms", "paper") for t in ev[k])
    assert ev["silences"] == [(2.7, 4.9), (28.7, 30.9)]            # the open's before its hero (5.0); the chapter's before its KEEP card
    assert all(not (28.7 <= t <= 30.9) for t in ev["ticks"] + ev["subs"] + ev["rooms"])


def test_the_camera_holds_a_breath_and_under_motivated_motion_moves_only_with_a_reason(monkeypatch):
    j = lambda shot, prev, room: SimpleNamespace(shot=shot, prev=prev, room=room, job={"motion": shot.get("motion")})
    b = j({"style": "breathe-hold", "kind": "still"}, None, "world")
    render_shots.Job._camera(b)
    assert b.job["motion"] == "hold" and b.job["cam"] == "still"
    monkeypatch.setattr(render_shots, "MOTION", "locked")
    w = j({"style": "still-push", "kind": "still"}, {"room": "paper", "reveals": []}, "world")
    render_shots.Job._camera(w)
    assert w.job["motion"] is None and "cam" not in w.job                          # the locked look: unchanged
    monkeypatch.setattr(render_shots, "MOTION", "motivated")
    after = j({"style": "still-push", "kind": "still"}, {"room": "paper", "reveals": [{"key": "a"}]}, "world")
    alone = j({"style": "still-push", "kind": "still"}, {"room": "world"}, "world")
    desk = j({"style": "doc-highlight", "kind": "document"}, None, "paper")
    for x in (after, alone, desk):
        render_shots.Job._camera(x)
    assert after.job["motion"] == "push" and alone.job["motion"] == "hold" and desk.job["cam"] == "still"


def test_a_redraft_keeps_every_unchanged_shots_decisions_and_asks_only_for_the_rest():
    prev = {"moods": {"the open": "calm"}, "shots": [
        {"id": "s001", "start": 0.0, "end": 6.0, "kind": "number", "style": "number-land", "intent": "the date", "params": {"value": "{{a}}"}},
        {"id": "s002", "start": 6.0, "end": 12.0, "kind": "still", "style": "still-push", "intent": "the store", "query": ["store"],
         "asset": {"id": "loc:1"}}]}
    plan = {"shots": [{"id": "s001", "start": 0.0, "end": 6.0, "kind": "number", "style": "number-land", "params": {}},
                      {"id": "s002", "start": 6.0, "end": 9.0, "kind": "still", "style": "still-push", "params": {}},
                      {"id": "s003", "start": 9.0, "end": 12.0, "kind": "still", "style": "still-push", "params": {}}]}
    assert plan_skeleton.carry(prev, plan) == 1
    s1, s2, _ = plan["shots"]
    assert s1["carried"] and s1["intent"] == "the date" and s1["params"] == {"value": "{{a}}"} and "carried" not in s2
    assert plan["moods"] == {"the open": "calm"}


def test_a_beat_that_says_figures_is_never_held_under_a_picture():
    from hubricon_content import line
    from hubricon_content import script as sm
    t = _timing(breathe=True)
    t["segments"][0]["spoken"] = [{"key": "a", "t": 3.0}]
    assert plan_skeleton._held(t, [round(0.45 + 0.5 * i, 3) for i in range(80)], 3.0, [3.0]) == []
    s = {"header": {"FORM": "story"}, "hooks": {}, "tail": {}, "beats": [
        {"at": 0, "name": "THE CHAIN", "VO": "By {{y}} there were {{n}} stores.", "MONTAGE": "yes", "KEEP": "", "TRY": "", "CTA": ""}]}
    assert any("this beat says figures" in p for p in sm.learning(s))
    plan = {"mode": "history", "shots": [{"id": "s9", "fixed": True, "pictures": True, "style": "breathe-hold", "query": [],
                                          "says": "a bar of soap on the counter", "intent": "BREATHE"}]}
    line.fixed_pictures(plan)
    assert plan["shots"][0]["query"] == ["bar soap counter"] and plan["shots"][0]["fallback"] == "paper:kinetic"
