"""Viewers as the critic: a retention curve names the shot and the words where viewers left."""
import json

from hubricon_content import retention
from hubricon_content import script as scriptmod
from hubricon_content import shots


class _Svc:
    def __init__(self, rows): self.rows, self.q = rows, None
    def reports(self): return self
    def query(self, **q): self.q = q; return self
    def execute(self): return {"rows": self.rows}


def _film(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    words = [{"word": f"w{i}", "start": i * 1.0, "end": i * 1.0 + 0.8} for i in range(200)]
    timing = {"duration": 200.0, "segments": [{"kind": "beat", "name": "THE QUESTION", "start": 0.0, "end": 200.0, "words": words}]}
    plan = {"shots": [{"id": f"s{i:03d}", "start": i * 10.0, "end": i * 10.0 + 10.0, "kind": "number" if i == 12 else "still",
                       "style": "number-land" if i == 12 else "still-push"} for i in range(20)]}
    (tmp_path / "timing.json").write_text(json.dumps(timing))
    (tmp_path / "shots.json").write_text(json.dumps(plan))
    (tmp_path / "published.json").write_text(json.dumps({"youtube_id": "abc123", "published_at": "2026-10-10T00:00:00"}))
    monkeypatch.setattr(shots, "load_timing", lambda d: (timing, None))
    # 100 points: 30% gone in the open, then a steady 0.2% a point, a 6% cliff at 60%-61% (s012, 120 s), a rewatch at 80%
    rows, w = [], 1.0
    for i in range(1, 101):
        r = i / 100
        w = 1.0 - 0.3 * min(1, r / 0.15) if r <= 0.15 else w - (0.06 if i == 61 else -0.03 if i == 81 else 0.002)
        rows.append([r, round(w, 4), 0.5])
    return rows


def test_a_drop_names_its_shot_beat_and_words_and_the_open_is_reported_apart(tmp_path, monkeypatch):
    rows = _film(tmp_path, monkeypatch)
    svc = _Svc(rows)
    res = retention.run("f", service=svc)
    assert svc.q["filters"] == "video==abc123" and svc.q["dimensions"] == "elapsedVideoTimeRatio"
    assert res["status"] == "ok" and 0.69 < res["open_kept"] < 0.72
    top = res["drops"][0]
    assert top["shot"] == "s012" and top["style"] == "number-land" and top["beat"] == "THE QUESTION" and top["said"].startswith("w120")
    assert res["rewatched"][0]["shot"] == "s016"
    assert "Where viewers left" in (tmp_path / "qa" / "retention.md").read_text()


def test_patterns_rank_the_styles_that_lose_viewers_against_their_own_films(tmp_path, monkeypatch):
    (tmp_path / "videos" / "f").mkdir(parents=True)
    rows = _film(tmp_path / "videos" / "f", monkeypatch)
    monkeypatch.setattr(retention, "PATTERNS", tmp_path / "patterns.json")
    retention.run("f", service=_Svc(rows))
    out = retention.patterns(tmp_path / "videos")
    assert out["films"] == 1 and "still-push" in out["styles"]
