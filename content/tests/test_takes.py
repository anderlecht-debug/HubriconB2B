"""The founder's own takes become the unit's narration through the same files the
clone writes (VISUAL_SPEC.md §7.2), so everything after `tts` is one path."""

import json

import numpy as np
import soundfile as sf

from hubricon_content import script as scriptmod
from hubricon_content import tts


def _unit(tmp_path, monkeypatch, beats):
    d = tmp_path / "v"
    (d / "takes").mkdir(parents=True)
    (d / "script.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: d)
    monkeypatch.setattr(scriptmod, "load_facts", lambda slug: {})
    monkeypatch.setattr(scriptmod, "parse", lambda text: {})
    monkeypatch.setattr(scriptmod, "render", lambda sc, facts: {"beats": [{"name": f"B{i}", "VO": vo} for i, vo in enumerate(beats, 1)]})
    # The transcriber spells numbers its own way; the alignment must carry the script's words.
    monkeypatch.setattr(tts, "align", lambda wav: [{"word": "Twelve", "start": 0.1, "end": 0.4},
                                                   {"word": "dollars", "start": 0.45, "end": 0.8}])
    return d


def _take(path):
    sf.write(str(path), np.zeros(4800, dtype=np.float32), 48000)


def test_every_take_becomes_vo_and_alignment_in_the_script_words(tmp_path, monkeypatch):
    d = _unit(tmp_path, monkeypatch, ["$12 a unit.", "", "Paid on every unit."])
    _take(d / "takes" / "b1.wav")
    _take(d / "takes" / "b3.wav")
    (d / "audio").mkdir()
    (d / "audio" / "vo-01.mp3").write_bytes(b"clone")   # an earlier clone read steps aside
    u = {"slug": "s", "voice": "founder", "publishable": True}
    res = tts.takes_to_vo(u, {})
    assert res == {"status": "ok", "voice": "own", "beats": 2}
    assert sorted(p.name for p in (d / "audio").iterdir()) == ["vo-01.wav", "vo-03.wav"]
    meta = json.loads((d / "alignment" / "vo-01.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "own" and [w["word"] for w in meta["words"]] == ["$12", "a", "unit."]
    assert u["voice"] == "own" and u["publishable"] is False


def test_a_missing_take_blocks_with_the_beat_named(tmp_path, monkeypatch):
    d = _unit(tmp_path, monkeypatch, ["One.", "Two."])
    _take(d / "takes" / "b1.wav")
    res = tts.takes_to_vo({"slug": "s"}, {})
    assert res["status"] == "blocked" and "b2" in res["reason"] and not (d / "audio").exists()
