"""A film's worksheet: its takeaways, this week's step as numbered steps, the figures with their sources."""
from hubricon_content import script as scriptmod
from hubricon_content import worksheet


def test_the_try_beat_becomes_numbered_steps_with_its_figures_and_their_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(scriptmod, "video_dir", lambda slug: tmp_path)
    monkeypatch.setattr(scriptmod, "load_facts", lambda slug: {"move": {"value": "2%", "label": "the movement the fit needs",
                                                                         "source": "ELASTICITY.FIT on Tarnhollow demo data"}})
    (tmp_path / "script.md").write_text("""TITLE: The dime
HOOKS
1. A hook.
SCRIPT
[1:00] THE IDEA
  VO: Which would you raise? A price you never move is a price you never measured.
  KEEP: A price you never move is a price you never measured.
[2:00] WHAT YOU CAN DO
  VO: So here's this week. Pull your prices. Check they moved {{move}}. If not, you have a dime. Write it down.
  TRY: yes
""")
    res = worksheet.build("f")
    text = (tmp_path / "worksheet.md").read_text()
    assert res["status"] == "ok" and res["steps"] == 3
    assert "1. Pull your prices." in text and "2. Check they moved 2%. If not, you have a dime." in text and "3. Write it down." in text
    assert "- A price you never move is a price you never measured." in text
    assert "| 2% (demo data) | the movement the fit needs | ELASTICITY.FIT on Tarnhollow demo data |" in text
