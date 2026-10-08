"""A script written elsewhere becomes a film in one command (SCRIPT_KIT.md)."""
import json

from hubricon_content import facts as factsmod
from hubricon_content import intake, state
from hubricon_content import script as scriptmod

SCRIPT = """SERIES:           Greats of Commerce
TITLE:            The Store That Sold {{x_year}}
PILLAR:           3
TIER:             D

SCRIPT
[0:00] COLD OPEN
  VO: In {{x_year}} a store opened.
  VISUAL: still-push on the store
"""


def test_the_facts_block_is_split_off_and_every_figure_needs_its_source():
    text = SCRIPT + """
## FACTS
| key | value | label | source |
|---|---|---|---|
| x_year | 1879 | the year it opened | https://example.org/history |
y_rent | $30 | the rent |
Z | 1 | bad key | somewhere
"""
    script, facts, problems = intake.split(text)
    assert "FACTS" not in script and script.rstrip().endswith("still-push on the store")
    assert facts == {"x_year": {"value": "1879", "label": "the year it opened", "source": "https://example.org/history"}}
    assert any("y_rent" in p and "four parts" in p for p in problems) and any("`Z` is not a key" in p for p in problems)


def test_a_greats_film_takes_the_next_number_and_a_slug_from_its_title():
    q = {"units": [{"id": "G01"}, {"id": "G03"}, {"id": "V30"}]}
    head = intake.header(SCRIPT)
    assert head["TIER"] == "D" and head["SERIES"] == "Greats of Commerce"
    assert intake.name(head, q) == ("G04", "greats-04-store-sold")
    assert intake.name({"TITLE": "Why Prices Stick"}, q) == ("F01", "prices-stick")
    assert intake.name({**head, "SHORT": "the dime"}, q) == ("G04", "greats-04-the-dime")      # SHORT kept as written


def test_a_clean_script_is_filed_and_queued_waiting_on_his_takes(tmp_path, monkeypatch):
    q = {"units": []}
    monkeypatch.setattr(state, "load", lambda: q)
    monkeypatch.setattr(state, "save", lambda x: None)
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path / slug)
    monkeypatch.setattr(factsmod, "cached_run", lambda force=False: {})
    monkeypatch.setattr(factsmod, "load_data", lambda: {})
    monkeypatch.setattr(factsmod, "build_facts", lambda run, data: {})
    monkeypatch.setattr(factsmod, "write", lambda slug, force=False: None)
    monkeypatch.setattr(scriptmod, "validate", lambda *a: [])
    src = tmp_path / "draft.md"
    src.write_text(SCRIPT + "\nFACTS\nx_year | 1879 | the year it opened | https://example.org/history\n")
    assert intake.script_in(src, dry=True)["status"] == "clean" and not q["units"]      # a dry run writes nothing
    res = intake.script_in(src)
    assert res["status"] == "ok" and res["slug"] == "greats-01-store-sold"
    d = tmp_path / "greats-01-store-sold"
    assert json.loads((d / "history.json").read_text())["x_year"]["value"] == "1879"
    assert "FACTS" not in (d / "script.md").read_text()
    u = q["units"][0]
    assert u["voice"] == "own" and u["status"] == "blocked" and "record.mjs greats-01-store-sold" in u["blocked_on"]
    assert u["steps"]["review"] == "approved" and u["steps"]["tts"] == "blocked" and "shots" in u["steps"]
    missing = tmp_path / "missing.md"
    missing.write_text(SCRIPT)                                   # no FACTS: {{x_year}} has no source
    res = intake.script_in(missing, slug="other")
    assert res["status"] == "refused" and any("x_year" in p for p in res["problems"])
