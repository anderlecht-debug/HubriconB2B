"""A long film is held to how people learn from narrated pictures (docs/content/LEARNING_DESIGN.md)."""
from hubricon_content import film_qa, plan_skeleton
from hubricon_content import script as sm


def _script(ch2_vo, keep="A price you never move is a price you never measured.", try_=True, recall="{{a}} and {{b}}"):
    filler = " ".join(["word"] * 240)
    return sm.parse(f"""TITLE: t
HOOKS
1. A hook.
SCRIPT
[0:00] COLD OPEN
  VO: In {{{{a}}}} it began.
[0:30] CHAPTER — ONE
  VO: One.
  VISUAL: chapter
[0:33] FIRST
  VO: What would you guess? {filler} It cost {{{{a}}}} and {{{{b}}}}. {keep}
  VISUAL: number-land
  KEEP: {keep}
[3:00] CHAPTER — TWO
  VO: Two.
  VISUAL: chapter
[3:03] SECOND
  VO: {ch2_vo} Back to {recall}. Now try it. A price you never move is a price you never measured.
  VISUAL: kinetic-thesis
  KEEP: A price you never move is a price you never measured.
  TRY: {"yes" if try_ else "no"}
""")


def test_a_clean_chapter_structure_passes():
    vo = "Which would you raise? " + " ".join(["word"] * 240)
    assert sm.learning(_script(vo)) == []


def test_a_long_chapter_a_chapter_with_no_question_and_a_missing_try_are_named():
    problems = sm.learning(_script(" ".join(["word"] * 1000), try_=False, recall="nothing"))
    assert any("chapter TWO: 10" in p and "split a long one" in p for p in problems)
    assert any("chapter TWO: asks the viewer nothing" in p for p in problems)
    assert any("no TRY beat" in p for p in problems)
    assert any("brings back 0 of the film's earlier figures" in p for p in problems)


def test_a_takeaway_must_be_said_and_short():
    s = _script("Which? " + " ".join(["word"] * 240))
    s["beats"][2]["KEEP"] = "Something the voice never says in this beat at all."
    assert any("said word for word" in p for p in sm.learning(s))
    s["beats"][2]["KEEP"] = " ".join(["long"] * 13)
    assert any("13 words; 12 at most" in p for p in sm.learning(s))


def test_the_takeaway_becomes_a_fixed_card_spanning_its_sentence():
    words = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in
             enumerate("So here it is. One price, never measured. Then on.".split())]
    timing = {"segments": [{"kind": "beat", "start": 0.0, "end": 5.0, "keep": "One price, never measured.", "words": words}]}
    cuts = [0.0, 1.55, 3.15, 5.0]
    assert plan_skeleton._keeps(timing, cuts) == [(1.55, 3.15, "One price, never measured.")]


def test_film_qa_names_figures_off_their_word_and_long_chapters():
    timing = {"duration": 900.0, "chapters": [{"at": 10.0, "title": "Long"}],
              "segments": [{"kind": "beat", "spoken": [{"key": "a", "t": 13.0}, {"key": "b", "t": 20.2}]}]}
    plan = {"shots": [{"id": "s1", "start": 10.0, "end": 16.0, "room": "paper", "kind": "number", "style": "number-land"},
                      {"id": "s2", "start": 20.0, "end": 26.0, "room": "paper", "kind": "number", "style": "number-land"}]}
    msgs = [p["msg"] for p in film_qa.learning(plan, timing, own_voice=False)]
    assert any("50% of figure shots open on their figure's word" in m for m in msgs)
    assert any("chapter 'Long' runs 14.8 min" in m for m in msgs)
