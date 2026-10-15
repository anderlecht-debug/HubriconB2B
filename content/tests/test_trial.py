"""The visual trial shows the founder every style before the look is locked
(VISUAL_SPEC.md §12, phase 5), so a style added to the library cannot skip it."""

from hubricon_content import shots, trial


def test_the_trial_has_one_shot_of_every_style_the_library_can_render():
    plan, tm = trial.build()
    have = {s["style"] for s in plan["shots"]}
    library = {k for k, v in shots.registry()["styles"].items() if not v.get("deferred")}
    assert library - have == set(), f"styles missing from the trial: {sorted(library - have)}"


def test_the_trial_cuts_only_where_a_film_could():
    plan, tm = trial.build()
    cuts = {round(c["t"], 3) for c in tm["cutpoints"]}
    assert all(round(s["end"], 3) in cuts for s in plan["shots"])
    assert abs(plan["shots"][-1]["end"] - tm["duration"]) < 1e-6
