import json

from hubricon_content import script as sm
from hubricon_content import series

FACTS = {"s_year": {"value": "1913", "label": "the year", "source": "https://example.org/act"},
         "el_point": {"value": "-2.20", "label": "elasticity", "source": "ELASTICITY.FIT on Tarnhollow demo data"}}
SCRIPT = """TITLE: The {{s_year}} card
THUMBNAIL: {{s_year}} on paper
PILLAR: 1
TIER: D
AWARENESS STAGE: unaware
CTA: The free course at hubricon.com/learn.
SPIKY CLAIM: The {{s_year}} card never went away.
MISCONCEPTION: Fees are fixed.
RUNTIME: 30 min

HOOKS (three, pick one)
1. {{s_year}}. A card | a staircase.

SCRIPT
[0:00] COLD OPEN
  VO: In {{s_year}} the card came. Today it reads {{el_point}}.
  VISUAL: still-push on the card
  DATA SOURCE: published: the Act
  CLIP: yes

[0:20] CHAPTER — THE CARD
  VO: The card.
  VISUAL: chapter

RE-HOOK AUDIT: 0:00
DERIVED ASSETS: none
"""


def _unit(tmp_path, monkeypatch, slug="greats-99-test"):
    d = tmp_path / "videos" / slug
    d.mkdir(parents=True)
    (d / "script.md").write_text(SCRIPT, encoding="utf-8")
    (d / "facts.json").write_text(json.dumps(FACTS), encoding="utf-8")
    (d / "history.json").write_text(json.dumps({"s_year": FACTS["s_year"]}), encoding="utf-8")
    (tmp_path / "videos" / "08-not-series").mkdir()
    monkeypatch.setattr(sm, "video_dir", lambda s: tmp_path / "videos" / s)
    return d


def test_render_fills_every_figure_and_lists_its_source(tmp_path, monkeypatch):
    _unit(tmp_path, monkeypatch)
    md = series.render("greats-99-test")
    assert "{{" not in md
    assert "In 1913 ⟨s_year⟩ the card came" in md
    assert "> *Picture.* still-push on the card" in md and "> *Data.* published: the Act" in md
    assert "*Picture.* chapter" not in md
    # history first, then only the engine figures the film uses, each with its source
    assert "| `s_year` | 1913 | the year | https://example.org/act |" in md
    assert "| `el_point` | -2.20 | elasticity | ELASTICITY.FIT on Tarnhollow demo data |" in md
    assert "A card \\| a staircase" not in md.split("### Hooks")[0]


def test_only_series_units_are_rendered(tmp_path, monkeypatch):
    _unit(tmp_path, monkeypatch)
    assert series.units(tmp_path / "videos") == ["greats-99-test"]


def test_a_history_fact_without_a_source_is_refused(tmp_path):
    from hubricon_content import facts as F
    import pytest
    p = tmp_path / "history.json"
    p.write_text(json.dumps({"s_year": {"value": "1913", "label": "the year", "source": "https://example.org"}}), encoding="utf-8")
    merged = F.merge_history(F.Facts(), p)
    assert merged["s_year"] == {"value": "1913", "label": "the year", "source": "https://example.org"}
    p.write_text(json.dumps({"s_year": {"value": "1913", "label": "the year"}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="needs a value and a source"):
        F.merge_history(F.Facts(), p)
    assert F.merge_history(F.Facts(), tmp_path / "none.json") == {}


def test_a_long_films_visual_names_a_style_and_its_charts_name_their_data():
    cta = {"1": {"cta": "hubricon.com/learn"}}
    bad = SCRIPT.replace("still-push on the card", "a nice shot of the card")
    problems = sm.validate(sm.parse(bad), FACTS, "D", 1, cta)
    assert any("names at least one style" in p for p in problems)
    chart = SCRIPT.replace("still-push on the card\n  DATA SOURCE: published: the Act", "chart-build of the card")
    problems = sm.validate(sm.parse(chart), FACTS, "D", 1, cta)
    assert any("draws a chart without DATA SOURCE" in p for p in problems)
    assert not any("style" in p or "DATA SOURCE" in p for p in sm.validate(sm.parse(SCRIPT), FACTS, "D", 1, cta))
