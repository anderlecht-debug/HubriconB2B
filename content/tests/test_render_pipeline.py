"""The long film's renderer: the grade lands the look or refuses the asset, footage
clips are frame-exact, every figure on screen is filled from facts, and every
stage kind draws (VISUAL_SPEC.md §3.2, §8)."""

import json
import subprocess
from pathlib import Path

import pytest

from hubricon_content import footage, grade, render_shots, shots

CONTENT = Path(__file__).resolve().parents[1]


def _clip(path: Path, vf: str, seconds: float = 3, rate: int = 30, size: str = "1920x1080"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={size}:r={rate}:d={seconds}", "-vf", vf,
                    "-c:v", "libx264", "-preset", "ultrafast", str(path)], check=True)
    return path


def test_the_grade_lands_a_bright_clip_in_the_band_and_refuses_night(tmp_path):
    p = grade.plan(_clip(tmp_path / "day.mp4", "eq=brightness=0.05"))
    lo, hi = 138 - 10, 138 + 10
    assert lo <= p["yavg"] <= hi and not p["mono"]
    with pytest.raises(grade.Rejected):
        grade.plan(_clip(tmp_path / "night.mp4", "eq=brightness=-0.6"))


def test_a_black_and_white_photograph_stays_monochrome(tmp_path):
    src = tmp_path / "old.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=2000x1400,format=gray", "-frames:v", "1", str(src)], check=True)
    out = grade.still(src, tmp_path / "old.jpg")
    assert out["mono"] and grade.measure(tmp_path / "old.jpg", image=True)["satavg"] < 3


def test_a_footage_clip_is_exactly_its_frames_and_slowed_only_from_sixty(tmp_path):
    src = _clip(tmp_path / "sixty.mp4", "eq=brightness=0.05", seconds=4, rate=60)
    r = footage.render(src, tmp_path / "shot.mp4", frames=45, start=0.5)
    assert r["slowed"] and footage.probe(tmp_path / "shot.mp4")["frames"] == 45
    with pytest.raises(grade.Rejected):
        footage.render(src, tmp_path / "long.mp4", frames=300, start=0.5)


def test_every_figure_is_filled_from_facts_and_an_unknown_one_is_an_error():
    assert render_shots.fill({"a": ["{{x}} a month"]}, {"x": "$3,874"}) == {"a": ["$3,874 a month"]}
    with pytest.raises(KeyError):
        render_shots.fill("{{nope}}", {})


def test_shot_frames_follow_the_films_frame_grid():
    assert render_shots.frames_of({"start": 0.0, "end": 7.51}) == 225
    assert render_shots.frames_of({"start": 7.51, "end": 15.0}) == 225   # the two add up to the whole: 450


def test_a_number_shot_takes_its_figure_and_label_from_facts(tmp_path):
    facts = {"leak": {"value": "$4,200", "label": "a year on one step", "source": "public-data case study, estimate"}}
    tm = {"duration": 8.0, "segments": [{"kind": "beat", "start": 0, "end": 8, "words": [{"word": "$4,200", "start": 1.0, "end": 1.4}]}]}
    shot = {"id": "s001", "start": 0.0, "end": 8.0, "style": "number-land", "kind": "number", "room": "paper",
            "on": "{{leak}}", "reveals": [{"key": "leak", "t": 1.0}], "says": "$4,200", "label": "proof"}
    job = render_shots.Job(shot, {"shots": [shot]}, tm, facts, tmp_path)
    assert job.renderer == "stage" and job.job["on"] == 1.0
    assert job.job["params"] == {"value": "$4,200", "sub": "a year on one step", "estimate": True}


def test_engine_charts_go_to_manim_and_house_charts_to_the_stage(tmp_path):
    tm = {"duration": 8.0, "segments": []}
    for scene, renderer in (("cash_cone", "manim"), ("staircase", "stage")):
        shot = {"id": "s001", "start": 0, "end": 8, "style": "chart-build", "kind": "chart", "room": "paper", "chart": {"scene": scene}}
        assert render_shots.Job(shot, {"shots": [shot]}, tm, {}, tmp_path).renderer == renderer


def test_every_stage_kind_draws(tmp_path):
    reg = shots.registry()
    kinds = {st["kinds"][0] for st in reg["styles"].values()} - {"footage", "chart", "end"}
    script = ("import { shotHTML, KINDS } from '%s';\n" % (CONTENT / "film" / "shots.mjs").as_posix() +
              "const kinds = %s;\n" % json.dumps(sorted(kinds)) +
              "for (const k of kinds) { const html = shotHTML({ id: 'x', kind: k, style: 'x', seconds: 6, render: { every_s: [1.6, 2.4], "
              "per_dot_max: 2000, dot_px: 14, gap_px: 5, fill_ms: 1500, box_w: 1180, box_h: 760, height_px: 520, gutter_px: 32, line_every_s: 0.9 }, "
              "params: { lines: ['a'], rows: [['a']], columns: ['a'], terms: [{ text: 'a' }], events: [{ date: 'a', label: 'b' }], text: 'a', title: 'a', total: '10', filled: '5' }, "
              "asset: { url: '/x.jpg', w: 10, h: 10 }, assets: [{ url: '/x.jpg' }], says: 'a' }, {}); "
              "if (!html.includes('class=\"shot\"')) throw new Error(k); }\nconsole.log('ok', kinds.length);\n")
    js = tmp_path / "kinds.mjs"
    js.write_text(script)
    out = subprocess.run(["node", str(js)], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.startswith("ok"), out.stderr


def test_a_film_renders_only_on_the_look_the_founder_locked(tmp_path, monkeypatch):
    from hubricon_content import visual_lock
    monkeypatch.setattr(visual_lock, "LOCK", tmp_path / "visual-lock.json")
    assert visual_lock.drift() is None
    q = {}
    visual_lock.lock(q, "approved after the trial")
    assert q["visual_locked"] and visual_lock.drift() == []
    doc = __import__("json").loads((tmp_path / "visual-lock.json").read_text())
    doc["files"]["content/assets/grade.json"] = "changed"
    (tmp_path / "visual-lock.json").write_text(__import__("json").dumps(doc))
    assert visual_lock.drift() == ["content/assets/grade.json"]
