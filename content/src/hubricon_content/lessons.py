"""Written lessons: Markdown with {{key}} placeholders, number-guarded, rendered
to HTML fragments the course page embeds."""

import json
from pathlib import Path

import markdown

from hubricon_engine.narrate import render as render_facts, validate as number_guard

from .state import CONTENT_DIR

LESSONS = CONTENT_DIR / "learn" / "lessons"
RENDERED = LESSONS / "rendered"
FACTS = CONTENT_DIR / "videos" / "playbook" / "facts.json"


def render_all() -> str:
    if not FACTS.exists():
        raise SystemExit("run `hubricon-content facts playbook` first")
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    RENDERED.mkdir(parents=True, exist_ok=True)
    report = []
    for src in sorted(LESSONS.glob("L*.md")):
        text = src.read_text(encoding="utf-8")
        problems = number_guard(text, facts)
        if problems:
            report.append(f"{src.name}: REJECTED — " + "; ".join(problems))
            continue
        html = markdown.markdown(render_facts(text, facts), extensions=["tables"])
        (RENDERED / (src.stem + ".html")).write_text(html + "\n", encoding="utf-8")
        report.append(f"{src.name}: ok → rendered/{src.stem}.html")
    return "\n".join(report)
