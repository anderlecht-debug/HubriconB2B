"""A scene cuts inside itself, to VISUAL_SPEC.md §4: a shot runs three to fourteen
seconds, a spoken figure holds three before the cut, the stage is never blank and no
figure is ever early. The kinetic scene plans its shots from the narration's own
alignment, so the plan can be held to the cadence without rendering a frame."""

import json
from pathlib import Path

from hubricon_content import qa
from hubricon_content.scenes.base import FIGURE_HOLD_S, SHOT_MAX_S, SHOT_MIN_S, HubriconScene, phrases, sentences
from hubricon_content.scenes.charts import Kinetic

ROOT = Path(__file__).resolve().parents[2]


def words(text: str, at: float = 0.0, per: float = 0.4) -> list[dict]:
    return [{"word": w, "start": round(at + i * per, 3), "end": round(at + (i + 1) * per - 0.05, 3)}
            for i, w in enumerate(text.split())]


class Stub:
    """What Kinetic.shots reads: the segment and the unit's facts."""

    def __init__(self, seg, facts=None):
        self.seg, self.facts = seg, facts or {}


def plan(seg, facts=None):
    shots = Kinetic.shots(Stub(seg, facts))
    length = float(seg["end"]) - float(seg["start"])
    return [(s, (shots[i + 1]["t"] if i + 1 < len(shots) else length) - s["t"]) for i, s in enumerate(shots)]


# ── the narration's sentences are where a card cuts ──
def test_sentences_split_on_the_spoken_stop():
    s = sentences(words("One moves. Two does not."))
    assert [x["text"] for x in s] == ["One moves.", "Two does not."]


def test_a_sentence_under_the_minimum_joins_the_next():
    p = phrases(words("Short. The next sentence runs long enough to hold its own shot."))
    assert len(p) == 1 and p[0]["text"].startswith("Short.")


def test_a_long_sentence_keeps_its_own_shot():
    p = phrases(words("A sentence long enough to hold a shot by itself. And a second one just as long here."))
    assert len(p) == 2


# ── the shot plan ──
def seg_of(text: str, reveals=None, length=None):
    w = words(text)
    return {"kind": "beat", "index": 0, "start": 0.0, "end": length or (w[-1]["end"] + 0.5), "vo": text,
            "words": w, "reveals": reveals or {}}


def test_the_stage_is_never_blank_at_a_segments_first_frame():
    seg = seg_of("The first card is up from the first frame. It holds while the sentence is spoken.")
    assert plan(seg)[0][0]["t"] == 0.0


def test_no_shot_holds_past_the_cadences_maximum():
    seg = seg_of("One sentence that is quite long on its own. " * 6)
    assert all(span <= SHOT_MAX_S for _, span in plan(seg))


def test_no_card_is_flashed_under_the_minimum():
    seg = seg_of("A first sentence here. Short. Another sentence that holds its own shot nicely.")
    assert all(span >= SHOT_MIN_S for s, span in plan(seg) if "figure" not in s)


def test_a_figure_lands_on_the_word_that_speaks_it_and_holds():
    text = "The gap between them is the figure. It is the whole point of the segment."
    seg = seg_of(text, reveals={"gap": {"t": 6.0, "value": "$65,320"}}, length=12.0)
    figures = [(s, span) for s, span in plan(seg) if "figure" in s]
    assert figures and figures[0][0]["t"] == 6.0 and figures[0][1] >= FIGURE_HOLD_S


def test_a_figure_the_segment_ends_under_is_not_cut_to():
    text = "The gap between them is the figure. It is the whole point of the segment."
    seg = seg_of(text, reveals={"gap": {"t": 6.0, "value": "$65,320"}})
    assert not [s for s, _ in plan(seg) if "figure" in s]


def test_a_figure_is_never_early():
    seg = seg_of("A sentence that opens the segment and holds.", reveals={"gap": {"t": 3.5, "value": "$1"}})
    assert all(s["t"] >= 3.5 for s, _ in plan(seg) if "figure" in s)


# ── a landing is filed under the clip it happened in ──
def test_a_chapter_card_does_not_file_its_landing_under_a_beats_number():
    beat = {"index": 3, "position": 2}
    card = {"index": None, "position": 3}
    assert HubriconScene.position.fget(Stub(beat)) != HubriconScene.position.fget(Stub(card))


def test_a_segment_rendered_before_position_existed_still_files_under_its_number():
    assert HubriconScene.position.fget(Stub({"index": 4})) == 4


# ── a hold has to carry the run of figures it leads into (§4) ──
def test_a_run_of_figures_too_close_to_cut_between_is_carried_by_one_picture():
    """V05's first chapter: two figures, a wide gap, then six about three seconds
    apart. The hold that leads into the run has to know the run reaches 28.0, or it
    spends the chart's whole build clock on the drift in front of it."""
    ts = [3.2, 5.6, 19.7, 22.6, 25.1, 28.0, 34.8]
    assert HubriconScene.cluster_end(None, ts, 2) == 28.0


def test_a_hold_with_a_window_after_it_looks_no_further_than_itself():
    ts = [3.2, 5.6, 19.7, 22.6]
    assert HubriconScene.cluster_end(None, ts, 1) == 5.6


def test_the_last_figure_looks_no_further_than_itself():
    ts = [3.2, 5.6, 19.7]
    assert HubriconScene.cluster_end(None, ts, 2) == 19.7


# ── what the program check makes of a film's cutting ──
def test_a_film_the_detector_finds_no_cuts_in_fails():
    assert not qa.cadence_holds({"cuts": 0, "mean_interval": None, "max_interval": None})
    assert not qa.cadence_holds({"cuts": 1, "mean_interval": None, "max_interval": None})


def test_a_film_cut_to_the_cadence_passes():
    assert qa.cadence_holds({"cuts": 34, "mean_interval": 8.1, "max_interval": 13.4})


def test_a_stretch_longer_than_a_chart_build_fails():
    assert not qa.cadence_holds({"cuts": 9, "mean_interval": 9.0, "max_interval": 55.2})


def test_cutting_faster_than_the_minimum_shot_fails():
    assert not qa.cadence_holds({"cuts": 200, "mean_interval": 1.4, "max_interval": 4.0})


# ── the film in the repo ──
def test_v01s_kinetic_segments_all_meet_the_cadence():
    d = ROOT / "content" / "videos" / "01-survivorship-bias"
    if not (d / "timing.json").exists():
        return
    timing = json.loads((d / "timing.json").read_text(encoding="utf-8"))
    facts = json.loads((d / "facts.json").read_text(encoding="utf-8"))
    for seg in timing["segments"]:
        if seg["kind"] != "beat" or "kinetic" not in (seg.get("visual") or ""):
            continue
        p = plan(seg, facts)
        assert p[0][0]["t"] == 0.0, f"segment {seg['index']} opens on a blank stage"
        for s, span in p:
            floor_s = FIGURE_HOLD_S if "figure" in s else SHOT_MIN_S
            assert span <= SHOT_MAX_S, f"segment {seg['index']} holds a shot {span:.1f}s"
            assert span >= floor_s - 0.01, f"segment {seg['index']} cuts a shot after {span:.1f}s"
