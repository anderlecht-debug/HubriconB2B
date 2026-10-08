from hubricon_content import script as sm

FACTS = {"big": {"value": "$65,320", "label": "spread", "source": "demo"}, "n": {"value": "2,000", "label": "paths", "source": "demo"}}
CTA = {"4": {"cta": "hubricon.com/learn"}, "0": {"cta": "the call, then hubricon.com/learn"}}
GOOD = """TITLE: Why {{big}} of results is luck
THUMBNAIL: {{big}} on the fan
PILLAR: 4
TIER: A
AWARENESS STAGE: unaware
CTA: The free course at hubricon.com/learn.
SPIKY CLAIM: Most of it is dice.
MISCONCEPTION: Winners did something different.
RUNTIME: 5 min

HOOKS (three, pick one)
1. {{big}} separates the lucky tenth from the unlucky tenth. You'd call that skill. It isn't.
2. {{n}} paths, one plan. The winners tell a story.
3. {{big}} is the gap. Same plan. Here's why.

SCRIPT
[0:00] HOOK
  VO: {{big}} separates the lucky tenth from the unlucky tenth. You'd call that skill. It isn't.
  VISUAL: kinetic
  CLIP: yes

[0:30] CHAPTER 1 — PATHS
  VO: Here are {{n}} versions of the same year. WORDS
  VISUAL: paths
  DATA SOURCE: cash horizon paths, demo data
  CLIP: yes

[1:00] THE HONEST LIMIT
  VO: You can ask how many peers ran the same plan and lost. WORDS
  VISUAL: kinetic
  CTA: The whole method is free at hubricon.com/learn.
  CLIP: yes

RE-HOOK AUDIT: 0:00, 0:30, 1:00
DERIVED ASSETS: none
"""


def _pad(text, n=680):
    return text.replace("WORDS", " ".join(["word"] * n))


def test_clean_script_passes():
    sc = sm.parse(_pad(GOOD, 340))
    assert sm.validate(sc, FACTS, "A", 4, CTA) == []


def test_digit_in_vo_is_rejected():
    sc = sm.parse(_pad(GOOD, 340).replace("Here are {{n}} versions", "Here are 2,000 versions"))
    assert any("digits" in p for p in sm.validate(sc, FACTS, "A", 4, CTA))


def test_number_word_and_banned_phrase():
    sc = sm.parse(_pad(GOOD, 340).replace("It isn't.", "It's simply half of it."))
    p = sm.validate(sc, FACTS, "A", 4, CTA)
    assert any("number words" in x for x in p) and any("banned" in x for x in p)


def test_rehook_gap_and_cta_mismatch():
    bad = _pad(GOOD, 340).replace("[1:00] THE HONEST LIMIT", "[1:50] THE HONEST LIMIT").replace("RE-HOOK AUDIT: 0:00, 0:30, 1:00", "RE-HOOK AUDIT: 0:00")
    sc = sm.parse(bad)
    p = sm.validate(sc, FACTS, "A", 4, CTA)
    assert any("re-hook gap" in x for x in p)
    sc2 = sm.parse(_pad(GOOD, 340).replace("CTA: The free course at hubricon.com/learn.", "CTA: Get your free Profit Teardown."))
    p2 = sm.validate(sc2, FACTS, "A", 4, CTA)
    assert any("Teardown is killed" in x for x in p2)
    no_learn = _pad(GOOD, 340).replace("hubricon.com/learn", "our site")
    assert any("/learn" in x for x in sm.validate(sm.parse(no_learn), FACTS, "A", 4, CTA))


def test_the_home_page_film_points_to_the_call_first():
    sc = sm.parse(_pad(GOOD, 340))
    assert any("call first" in x for x in sm.validate(sc, FACTS, "A", 0, CTA))
    film = _pad(GOOD, 340).replace("  CTA: The whole method is free at hubricon.com/learn.", "  CTA: Book the call. Or learn the method free at hubricon.com/learn.")
    assert not any("call first" in x for x in sm.validate(sm.parse(film), FACTS, "A", 0, CTA))


def test_chart_needs_demo_data_source():
    sc = sm.parse(_pad(GOOD, 340).replace("  DATA SOURCE: cash horizon paths, demo data\n", ""))
    assert any("DATA SOURCE" in x for x in sm.validate(sc, FACTS, "A", 4, CTA))


def test_render_substitutes_values():
    r = sm.render(sm.parse(_pad(GOOD, 10)), FACTS)
    assert "$65,320" in r["hooks"][1] and "{{" not in r["beats"][0]["VO"]


def test_a_key_the_facts_no_longer_have_is_named_not_a_crash():
    gone = GOOD.replace("{{n}} paths", "{{pm_sku}} paths")
    problems = sm.validate(sm.parse(gone), FACTS, "A", 4, CTA)
    assert any("unknown placeholder {{pm_sku}}" in p for p in problems)
