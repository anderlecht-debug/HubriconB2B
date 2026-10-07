"""One look across every film (VISUAL_SPEC.md §3.1): the site's tokens and Inter,
everywhere, read from content/assets/tokens.json. No module keeps a colour or a
typeface of its own, and the retired night system (navy, amber, Fraunces,
JetBrains Mono) is gone from the code."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

CONTENT = Path(__file__).resolve().parents[1]
TREES = [CONTENT / "src", CONTENT / "film"]
SUFFIXES = {".py", ".mjs", ".js", ".css", ".html"}


V3 = CONTENT / "film" / "v3"   # the long films' look since the founder's call of 2026-10-06 (FILM_LOOK_V3.md)


def _files():
    """The paper look's code. v3 keeps its own rules, below."""
    for tree in TREES:
        for p in tree.rglob("*"):
            if p.suffix in SUFFIXES and ".venv" not in p.parts and "__pycache__" not in p.parts and V3 not in p.parents:
                yield p


def test_no_colour_is_typed_outside_tokens_json():
    hits = [f"{p.relative_to(CONTENT)}:{n}" for p in _files()
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if re.search(r"#[0-9a-fA-F]{6}\b", line)]
    assert hits == [], f"hex colours outside content/assets/tokens.json: {hits}"


def test_the_retired_typefaces_are_gone():
    hits = [f"{p.relative_to(CONTENT)}:{n}" for p in _files()
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if re.search(r"Fraunces|JetBrains", line)]
    assert hits == [], hits


def test_manim_draws_the_site_palette_and_no_red_or_green():
    from hubricon_content import tokens
    from hubricon_content.scenes import base
    t = tokens.load()["colour"]
    assert (base.PAPER, base.INK, base.INK_3, base.BLUE) == (t["paper"], t["ink"], t["ink_3"], t["blue"])
    assert not hasattr(base, "GREEN") and not hasattr(base, "RED") and not hasattr(base, "AMBER")
    assert base.FONT == "Inter Display"
    assert "WHITE" in (CONTENT / "manim.cfg").read_text(encoding="utf-8")


def test_the_fonts_are_in_the_repo_and_the_stage_needs_no_network():
    for f in ("InterVariable.ttf", "InterDisplay-Regular.ttf", "InterDisplay-SemiBold.ttf", "Inter-Regular.ttf",
              "Inter-SemiBold.ttf", "Inter-OFL.txt"):
        assert (CONTENT / "assets" / "fonts" / f).exists(), f
    stage = (CONTENT / "film" / "stage.html").read_text(encoding="utf-8")
    assert "googleapis" not in stage and "/content/film/fonts.css" in stage


def test_subtitles_and_thumbnail_read_the_tokens():
    from hubricon_content import subtitles, tokens
    assert tokens.ass("ink") == "&H00" + tokens.colour("ink")[5:7].upper() + tokens.colour("ink")[3:5].upper() + tokens.colour("ink")[1:3].upper()
    assert "fontsdir=" in subtitles.ass_filter(Path("x.ass"))
    src = (CONTENT / "src" / "hubricon_content" / "thumbnail.py").read_text(encoding="utf-8")
    assert "Tarnhollow" not in src, "the demo label comes from the unit's facts"


@pytest.mark.skipif(shutil.which("node") is None, reason="node writes tokens.json")
def test_tokens_json_is_current_with_the_site_css_and_the_stage():
    res = subprocess.run(["node", str(CONTENT / "film" / "tokens.mjs"), "--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_v3_keeps_one_palette_in_its_base():
    """v3 ("the archive at night") has its own palette, defined once in film/v3/base.css; every kind
    draws with its tokens (var(--…)) and types no colour of its own."""
    hits = [f"{p.relative_to(CONTENT)}:{n}" for p in V3.rglob("*") if p.suffix in SUFFIXES and p.name != "base.css"
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if re.search(r"#[0-9a-fA-F]{6}\b", line)]
    assert hits == [], f"v3 colours outside film/v3/base.css: {hits}"
