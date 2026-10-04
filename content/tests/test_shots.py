"""shots-validate holds a long film's shot plan to VISUAL_SPEC.md §4, §5, §7.4 and
§14.8. A clean plan passes; each test breaks one rule and expects it named."""

import copy

from hubricon_content import shots
from hubricon_content.timing import cutpoints, estimate_words

from . import shotplan_fixture as fx


def problems(plan=None, tm=None, picked=False, usage=None, facts=fx.FACTS):
    if plan is None:
        plan, tm = fx.fresh()
    return shots.validate(plan, tm, facts, picked=picked, usage=usage)


def has(found, text):
    assert any(text in p for p in found), f"expected {text!r} in {found}"


def shot(plan, style, n=0):
    return [s for s in plan["shots"] if s["style"] == style][n]


def test_the_clean_plan_passes():
    assert problems() == []


# ── rule 1: coverage on legal cuts ──
def test_a_gap_between_shots_is_named():
    plan, tm = fx.fresh()
    plan["shots"][4]["end"] -= 0.5
    has(problems(plan, tm), "gap of 0.500")


def test_a_cut_that_is_not_a_legal_cut_is_named():
    plan, tm = fx.fresh()
    plan["shots"][4]["end"] += 0.2
    plan["shots"][5]["start"] += 0.2
    has(problems(plan, tm), "is not a legal cut")


def test_says_must_be_the_narration_under_the_shot():
    plan, tm = fx.fresh()
    plan["shots"][2]["says"] = "something nobody said"
    has(problems(plan, tm), "`says` is not the narration under the shot")


def test_the_plan_must_reach_the_end_of_the_narration():
    plan, tm = fx.fresh()
    plan["shots"].pop()
    has(problems(plan, tm), "the narration's end")


# ── rule 2: cadence and screen time ──
def test_a_shot_over_fourteen_seconds_is_too_long_unless_it_is_a_chart():
    plan, tm = fx.fresh()
    s = shot(plan, "doc-highlight", 1)
    s["style"] = "quote"; s["kind"] = "quote"; s["on"] = None
    nxt = plan["shots"][plan["shots"].index(s) + 1]
    s["end"] += 4; nxt["start"] += 4
    has(problems(plan, tm), "over the 14 s ceiling")


def test_the_first_minute_stays_quick():
    plan, tm = fx.fresh()
    a, b = plan["shots"][4], plan["shots"][5]
    a["end"] += 3; b["start"] += 3
    has(problems(plan, tm), "inside the first minute")


def test_a_number_holds_three_seconds_after_it_is_said():
    plan, tm = fx.fresh()
    s = shot(plan, "number-land")
    s["end"] = s["reveals"][0]["t"] + 2.5
    plan["shots"][plan["shots"].index(s) + 1]["start"] = s["end"]
    has(problems(plan, tm), "hold a number 3 s")


def test_four_shots_of_one_kind_in_a_row_is_too_many():
    plan, tm = fx.fresh()
    for s in plan["shots"][6:10]:
        s["kind"] = "footage"
    has(problems(plan, tm), "footage shots in a row")


def test_screen_time_shares_hold_for_the_mode():
    plan, tm = fx.fresh()
    plan["mode"] = "history"
    has(problems(plan, tm), "a history film keeps it within")


def test_a_long_chart_needs_something_new_every_eight_seconds():
    plan, tm = fx.fresh()
    shot(plan, "chart-build")["params"]["builds"] = []
    has(problems(plan, tm), "something new every 8 s")


# ── rule 3: figures on paper, at the second they are said ──
def test_a_figure_spoken_under_a_world_shot_fails():
    plan, tm = fx.fresh()
    s = shot(plan, "number-land")
    s.update(room="world", kind="footage", style="footage-establish", on=None, query=["pallet jack"], sources=["pexels"],
             fallback="paper:kinetic")
    has(problems(plan, tm), "figures live on paper")


def test_a_figure_must_be_revealed_when_it_is_spoken():
    plan, tm = fx.fresh()
    shot(plan, "number-land")["reveals"][0]["t"] += 0.5
    has(problems(plan, tm), "the second it is spoken")


def test_no_figure_appears_in_the_world_room():
    plan, tm = fx.fresh()
    shot(plan, "footage-establish")["overlay"]["credit"] = "Pexels · 4,200 views"
    has(problems(plan, tm), "a figure in the world room")


# ── rule 4: a named thing needs its own evidence ──
def test_a_named_company_is_never_stock():
    plan, tm = fx.fresh()
    shot(plan, "footage-establish")["specific"] = "Sears, Roebuck and Co."
    has(problems(plan, tm), "only archival sources may show it")


def test_a_named_thing_needs_matching_provenance_once_picked():
    plan, tm = fx.fresh()
    s = shot(plan, "still-push")
    s["specific"] = "Woolworth"
    s["asset"] = {"id": "loc:1", "file": "a.jpg", "sha256": "x", "licence": "No known restrictions", "author": "LoC",
                  "url": "https://loc.gov/x", "retrieved": "2026-10-04", "title": "A shop front", "passed_filters": True}
    has(problems(plan, tm, picked=True), "does not name 'Woolworth'")


# ── rule 5: concrete nouns, never a cliché ──
def test_a_cliche_query_is_refused():
    plan, tm = fx.fresh()
    shot(plan, "footage-establish")["query"] = ["businessmen handshake office"]
    has(problems(plan, tm), "banned cliché")


def test_a_world_shot_needs_a_query():
    plan, tm = fx.fresh()
    shot(plan, "footage-observe")["query"] = []
    has(problems(plan, tm), "needs a query")


# ── rule 6: no asset twice ──
def _pick_all(plan):
    for n, s in enumerate(plan["shots"]):
        if s["kind"] in ("footage", "still", "texture", "archive", "stack", "split"):
            s["asset"] = {"id": f"pexels:{n}", "file": f"{n}.mp4", "sha256": str(n), "licence": "Pexels", "author": "a",
                          "url": "https://pexels.com", "retrieved": "2026-10-04", "passed_filters": True,
                          "in": 0.0, "out": 20.0, "job": "j", "model": "m", "prompt": "p", "seed": 1}
            if s["kind"] in ("still", "texture"):
                s["focus"] = [0.5, 0.5]
                s["motion"] = {"still-push": "push", "still-pan": "pan-right", "texture": "drift"}.get(s["style"], "push")


def test_picks_pass_when_every_asset_is_new_and_documented():
    plan, tm = fx.fresh()
    _pick_all(plan)
    assert problems(plan, tm, picked=True) == []


def test_an_asset_twice_in_one_film_fails():
    plan, tm = fx.fresh()
    _pick_all(plan)
    shot(plan, "footage-establish", 1)["asset"]["id"] = shot(plan, "footage-establish", 0)["asset"]["id"]
    has(problems(plan, tm, picked=True), "already in this film")


def test_an_asset_from_the_last_ten_films_fails():
    plan, tm = fx.fresh()
    _pick_all(plan)
    used = shot(plan, "footage-observe")["asset"]["id"]
    has(problems(plan, tm, picked=True, usage={"films": [{"slug": "older", "assets": [used]}]}), "used in the last 10 films")


def test_the_licence_accept_list():
    for ok in ("Pexels License", "Pixabay Content License", "No known restrictions on publication", "CC0 1.0",
               "Public domain", "CC BY 4.0"):
        assert shots.licence_ok(ok), ok
    for bad in ("CC BY-SA 4.0", "CC BY-NC 2.0", "CC BY-ND 3.0", "Fair use", "unknown", "All rights reserved"):
        assert not shots.licence_ok(bad), bad


def test_a_licence_off_the_accept_list_fails():
    plan, tm = fx.fresh()
    _pick_all(plan)
    shot(plan, "still-pan")["asset"]["licence"] = "CC BY-SA 4.0"
    has(problems(plan, tm, picked=True), "not on the accept list")


# ── rule 7: labels ──
def test_an_ai_image_says_illustration():
    plan, tm = fx.fresh()
    shot(plan, "texture")["overlay"] = {}
    has(problems(plan, tm), "overlay.illustration")


def test_a_demo_figure_says_demo_data():
    plan, tm = fx.fresh()
    shot(plan, "number-land")["label"] = None
    has(problems(plan, tm), "label \"demo\"")


def test_a_case_study_figure_carries_the_proof_label():
    plan, tm = fx.fresh()
    facts = copy.deepcopy(fx.FACTS)
    facts["leak"]["source"] = "public-data case study, estimate"
    has(problems(plan, tm, facts=facts), "label \"proof\"")


# ── rule 8: styles and variety ──
def test_an_unknown_style_fails():
    plan, tm = fx.fresh()
    shot(plan, "texture")["style"] = "ken-burns-zoom"
    has(problems(plan, tm), "not in the library")


def test_a_style_in_the_wrong_room_fails():
    plan, tm = fx.fresh()
    shot(plan, "doc-highlight")["room"] = "world"
    has(problems(plan, tm), "belongs in the paper room")


def test_on_must_be_spoken_inside_the_shot():
    plan, tm = fx.fresh()
    shot(plan, "table-scan")["on"] = "nowhere"
    has(problems(plan, tm), "is not spoken inside the shot")


def test_the_depth_push_waits_for_its_build():
    plan, tm = fx.fresh()
    shot(plan, "still-push")["style"] = "still-depth"
    has(problems(plan, tm), "built after the visual trial")


def test_two_textures_in_a_row_fail():
    plan, tm = fx.fresh()
    i = plan["shots"].index(shot(plan, "texture"))
    nxt = plan["shots"][i + 1]
    nxt.update(style="texture", kind="texture", overlay={"illustration": True}, sources=["higgsfield"],
               query=["cardboard grain close"], fallback="paper:kinetic")
    has(problems(plan, tm), "texture at most 1 in a row")


def test_the_thesis_line_comes_once_every_three_minutes():
    plan, tm = fx.fresh()
    s = shot(plan, "formula-build")
    s.update(style="kinetic-thesis", kind="kinetic", on=None)
    has(problems(plan, tm), "kinetic-thesis: two within")


def test_any_twenty_minutes_uses_ten_styles():
    seq = [("footage-establish", 8), ("chart-build", 10), ("footage-observe", 12), ("counterfactual", 10)] * 40
    plan, tm = fx.build(seq)
    has(problems(plan, tm), "any 20 minutes uses at least 10")


# ── timing: legal cuts and the estimate ──
def test_cutpoints_fall_in_pauses_and_at_sentence_ends():
    words = [{"word": "One", "start": 0.0, "end": 0.3}, {"word": "two.", "start": 0.35, "end": 0.7},
             {"word": "Three", "start": 0.75, "end": 1.0}, {"word": "four", "start": 1.3, "end": 1.6}]
    cuts = [c["t"] for c in cutpoints([{"kind": "beat", "start": 0.0, "end": 2.0, "words": words}])]
    assert cuts == [0.0, 0.725, 1.15, 2.0]   # the sentence end, the 300 ms pause, the beat's ends


def test_the_estimate_reads_at_a_hundred_and_fifty_words_a_minute():
    words, dur = estimate_words(" ".join(["word"] * 150))
    assert 58 <= dur <= 61 and words[1]["start"] == 0.4


def test_fill_snaps_cuts_and_copies_the_narration_and_the_figures():
    plan, tm = fx.fresh()
    for s in plan["shots"]:
        s["says"], s["reveals"], s["label"] = "", [], None
    plan["shots"][3]["end"] += 0.2          # off a legal cut; fill puts it back
    plan["shots"][4]["start"] += 0.2
    shots.fill(plan, tm, fx.FACTS)
    assert problems(plan, tm) == []


def test_a_chapter_shot_sits_exactly_on_the_timings_card():
    plan, tm = fx.fresh()
    i = plan["shots"].index(shot(plan, "chapter"))
    plan["shots"][i]["end"] += 0.5
    plan["shots"][i + 1]["start"] += 0.5
    has(problems(plan, tm), "needs a `chapter` shot exactly over it")


def test_figures_spoken_close_together_may_hold_past_eight_seconds_in_the_first_minute():
    seq = [("number-land", 10, {"reveal": "leak", "at": 7})] + fx.SEQUENCE[1:]
    plan, tm = fx.build(seq)
    assert not [p for p in problems(plan, tm) if "first minute" in p]
    seq = [("number-land", 10, {"reveal": "leak", "at": 2})] + fx.SEQUENCE[1:]   # held well before the cut
    plan, tm = fx.build(seq)
    has(problems(plan, tm), "inside the first minute")
