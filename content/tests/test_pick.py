"""The pick writes down what the visual-pick skill chose (VISUAL_SPEC.md §7.5):
only a candidate that passed the filters, with its whole provenance."""

import json

import pytest

from hubricon_content import pick, sources
from hubricon_content import script as scriptmod


def _unit(tmp_path, monkeypatch):
    d = tmp_path / "film"
    (d / "sources").mkdir(parents=True)
    plan = {"shots": [{"id": "s001", "start": 0.0, "end": 8.0, "kind": "footage", "room": "world", "style": "footage-establish",
                       "fallback": "paper:kinetic", "query": ["container port"]}]}
    (d / "shots.json").write_text(json.dumps(plan))
    cands = [{"id": "pexels:1", "source": "pexels", "sheet_index": 0, "passed_filters": True, "licence": "Pexels License",
              "author": "Ana", "url": "https://pexels.com/v/1", "retrieved": "2026-10-05", "title": "Port", "checks": {"phash": "ab"}},
             {"id": "pexels:2", "source": "pexels", "sheet_index": 1, "passed_filters": False, "rejected_because": ["a face over 1%"]}]
    (d / "sources" / "s001.json").write_text(json.dumps({"candidates": cands}))
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: d)

    def fake_full(c, net=None):
        c["file"], c["sha256"] = "/tmp/port.mp4", "f00d"
        return c["file"]
    monkeypatch.setattr(sources, "fetch_full", fake_full)
    return d


def test_a_passed_candidate_is_picked_with_its_provenance(tmp_path, monkeypatch):
    d = _unit(tmp_path, monkeypatch)
    pick.pick("film", "s001", [0], start=2.0, reason="the berth, wide, in daylight", net=object())
    a = json.loads((d / "shots.json").read_text())["shots"][0]["asset"]
    assert a["id"] == "pexels:1" and a["sha256"] == "f00d" and a["licence"] == "Pexels License" and a["passed_filters"]
    assert a["in"] == 2.0 and a["out"] == 10.5 and a["phash"] == "ab"
    assert json.loads((d / "assets.json").read_text())["s001"]["reason"] == "the berth, wide, in daylight"


def test_a_refused_candidate_cannot_be_picked(tmp_path, monkeypatch):
    _unit(tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match="did not pass the filters"):
        pick.pick("film", "s001", [1], net=object())


def test_no_fitting_candidate_takes_the_fallback_onto_paper(tmp_path, monkeypatch):
    d = _unit(tmp_path, monkeypatch)
    pick.none("film", "s001", "nothing shows a berth")
    s = json.loads((d / "shots.json").read_text())["shots"][0]
    assert (s["room"], s["kind"], s["style"]) == ("paper", "kinetic", "kinetic-thesis") and s["asset"] is None
