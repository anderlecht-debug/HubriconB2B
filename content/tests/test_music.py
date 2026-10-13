"""The music library: cues tagged by mood, tempo and key; picked by mood, none twice in a film or a week."""
import json
from datetime import date

import numpy as np
import soundfile as sf

from hubricon_content import music


def test_a_cue_is_tagged_with_its_key_and_tempo_by_code_and_refused_without_a_licence(tmp_path):
    sr = 22050
    t = np.arange(sr * 12) / sr
    beat = (np.sin(2 * np.pi * 2.0 * t) > 0.95).astype("float32") * 0.4          # a click 2 a second: 120 BPM
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.18, 329.63)) * 0.2   # A, C#, E: A major
    sf.write(str(tmp_path / "cue.wav"), (chord + beat).astype("float32"), sr)
    side = music.tag(tmp_path / "cue.wav", "calm", "a test licence", "made for the test")
    assert side["key"] == "A major" and 100 <= side["tempo"] <= 140
    assert json.loads((tmp_path / "cue.json").read_text())["mood"] == "calm"
    try:
        music.tag(tmp_path / "cue.wav", "calm", " ", "x")
        raise AssertionError("an unlicensed cue was tagged")
    except SystemExit:
        pass


def test_a_chapter_gets_a_cue_of_its_mood_never_twice_in_a_film_nor_used_by_another_film_this_week(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "LEDGER", tmp_path / "usage.json")
    lib = [{"name": "a", "mood": "calm"}, {"name": "b", "mood": "calm"}, {"name": "c", "mood": "tension"}]
    got = music.pick("f1", ["calm", "calm", "calm", "tension", None], today=date(2026, 10, 13), library=lib)
    assert [g["name"] if g else None for g in got] == ["a", "b", None, "c", None]    # the third calm chapter keeps the bed
    later = music.pick("f2", ["calm", "tension"], today=date(2026, 10, 16), library=lib)
    assert later == [None, None]                                                     # f1 used them this week
    week_on = music.pick("f2", ["calm", "tension"], today=date(2026, 10, 21), library=lib)
    assert [g["name"] for g in week_on] == ["a", "c"]
