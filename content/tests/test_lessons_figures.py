"""The copy critique's number rule for the written lessons: every dollar or percent
figure in a rendered lesson is a value from the playbook facts file, and every lesson
says its figures are demo data (docs/content/hubricon-learn-build-prompt.md §7,
CLAUDE.md's number-safety rule)."""

import json
import re
from pathlib import Path

import pytest

CONTENT = Path(__file__).resolve().parents[1]
FACTS = CONTENT / "videos" / "playbook" / "facts.json"
RENDERED = sorted((CONTENT / "learn" / "lessons" / "rendered").glob("L*.html"))

pytestmark = pytest.mark.skipif(not FACTS.exists() or not RENDERED, reason="render the lessons first")


def facts_values() -> set[str]:
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    return {str(v["value"]) if isinstance(v, dict) else str(v) for v in facts.values()}


@pytest.mark.parametrize("lesson", RENDERED, ids=lambda p: p.stem)
def test_every_figure_is_a_facts_value(lesson: Path) -> None:
    text = lesson.read_text(encoding="utf-8")
    figures = set(re.findall(r"\$[0-9][0-9,]*(?:\.[0-9]+)?[MK]?", text)) | set(re.findall(r"[0-9]+(?:\.[0-9]+)?%", text))
    missing = sorted(f for f in figures if f not in facts_values())
    assert not missing, f"{lesson.name}: figures not in facts.json values: {missing}"


@pytest.mark.parametrize("lesson", RENDERED, ids=lambda p: p.stem)
def test_every_lesson_labels_its_figures_demo(lesson: Path) -> None:
    text = lesson.read_text(encoding="utf-8")
    if re.search(r"\$[0-9]", text):
        assert "demo" in text.lower(), f"{lesson.name} carries dollar figures without a demo label"
