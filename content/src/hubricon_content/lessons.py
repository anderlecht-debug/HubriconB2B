"""Written lessons: Markdown with {{key}} placeholders, number-guarded, rendered
to HTML fragments the course page embeds."""

import json
import re
from pathlib import Path

import markdown

from hubricon_engine.narrate import render as render_facts, validate as number_guard

from .state import CONTENT_DIR

LESSONS = CONTENT_DIR / "learn" / "lessons"
RENDERED = LESSONS / "rendered"
FACTS = CONTENT_DIR / "videos" / "playbook" / "facts.json"
# The course page the fragments land in, between its `<!-- lesson:L1 -->` markers.
PAGE = CONTENT_DIR.parent / "learn" / "reimbursement-playbook.html"
_H2 = re.compile(r"<h2>(.*?)</h2>", re.S)


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


def _between(page: str, start: str, end: str, body: str) -> str:
    a, b = page.find(start), page.find(end)
    if a < 0 or b < 0 or b < a:
        raise SystemExit(f"{PAGE.name}: markers {start!r} … {end!r} not found in order")
    a += len(start)
    return page[:a] + "\n" + body + "\n" + page[b:]


def embed(page_path: Path = PAGE) -> str:
    """Copy each rendered lesson into the course page between its markers, and write
    the lesson list from the lessons' own headings. Idempotent: run it after every
    render-lessons and the page never drifts from the Markdown."""
    if not RENDERED.exists():
        raise SystemExit("run `hubricon-content render-lessons` first")
    if not page_path.exists():
        raise SystemExit(f"{page_path} does not exist")
    page = page_path.read_text(encoding="utf-8")
    items = []
    for src in sorted(RENDERED.glob("L*.html")):
        stem = src.stem
        html = src.read_text(encoding="utf-8").rstrip()
        m = _H2.search(html)
        title = m.group(1) if m else stem
        page = _between(page, f"<!-- lesson:{stem} -->", f"<!-- /lesson:{stem} -->", html)
        locked = "" if stem == "L1" else ' class="locked"'
        items.append(f'        <li{locked}><a href="#{stem}" data-lesson="{stem}">{title}</a></li>')
    page = _between(page, "<!-- lesson-nav -->", "<!-- /lesson-nav -->", "\n".join(items))
    page_path.write_text(page, encoding="utf-8")
    return f"{page_path.relative_to(CONTENT_DIR.parent)}: {len(items)} lessons embedded"
