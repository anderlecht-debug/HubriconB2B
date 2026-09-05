"""The upload page, the API behind it and the parsers have to agree.

A report type lives in four places: the parser registry, the report types
`/api/intake` admits, the `uploads.report_type` check constraint, and the
card the client actually sees. Nothing at runtime notices when one of them
falls behind — the client just gets "unknown report_type" after picking
their files, or a card whose file nothing will ever read. These tests read
the JS and the HTML as text and hold the four together.

The last test is the one that earns its keep: the browser checks a picked
file's header against the same required columns the parser will demand, so
the client learns their export is wrong while the Shopify tab is still open
instead of by email tomorrow. That promise only holds while the signature
in the page stays at least as strict as the parser's SPEC.
"""

import json
import re
from pathlib import Path

import pytest

from hubricon_engine.ingest import PARSERS

ROOT = Path(__file__).resolve().parents[2]
INTAKE_JS = (ROOT / "api" / "intake.js").read_text()
INTAKE_HTML = (ROOT / "intake.html").read_text()
MIGRATIONS = ROOT / "supabase" / "migrations"

# The one card that is not a report type: it offers a choice of two.
CARD_CHOICES = {"ppc": {"ppc_search_terms", "ppc_campaign"}}


def _js_string_set(name: str) -> set[str]:
    """The contents of `const NAME = new Set([...])` in api/intake.js."""
    body = re.search(rf"const {name} = new Set\(\[(.*?)\]\)", INTAKE_JS, re.S).group(1)
    return set(re.findall(r'"([^"]+)"', body))


def _js_signatures() -> dict[str, list[list[str]]]:
    """The SIGNATURES table from intake.html: report type -> groups of
    interchangeable normalized column names."""
    body = re.search(r"const SIGNATURES = \{(.*?)\n\};", INTAKE_HTML, re.S).group(1)
    quoted = re.sub(r"^(\s*)(\w+):", r'\1"\2":', body, flags=re.M)
    return json.loads("{" + quoted.rstrip().rstrip(",") + "}")


def _card_types() -> list[str]:
    return re.findall(r'<div class="card" data-type="([\w]+)"', INTAKE_HTML)


def _card_scope(report_type: str) -> str | None:
    card = re.search(rf'<div class="card" data-type="{report_type}"([^>]*)>', INTAKE_HTML).group(1)
    scope = re.search(r'data-scope="(\w+)"', card)
    return scope.group(1) if scope else None


def _required_synonyms(report_type: str) -> list[list[str]]:
    spec = getattr(PARSERS[report_type], "SPEC", {})
    return [rule["synonyms"] for rule in spec.values() if rule.get("required")]


def test_the_api_admits_exactly_the_report_types_that_have_parsers():
    assert _js_string_set("REPORT_TYPES") == set(PARSERS)


def test_the_check_constraint_admits_exactly_those_report_types():
    """The newest migration that rewrites uploads_report_type_check wins."""
    latest = max((p for p in MIGRATIONS.glob("*.sql")
                  if "uploads_report_type_check" in p.read_text()), key=lambda p: p.name)
    body = re.search(r"report_type in \((.*?)\)\)", latest.read_text(), re.S).group(1)
    assert set(re.findall(r"'([^']+)'", body)) == set(PARSERS)


def test_every_card_on_the_page_is_a_report_type_the_api_takes():
    admitted = _js_string_set("REPORT_TYPES")
    for card in _card_types():
        for report_type in CARD_CHOICES.get(card, {card}):
            assert report_type in admitted, f"the {card} card sends a type the API rejects"


def test_every_shopify_report_type_has_a_card():
    on_page = {t for card in _card_types() for t in CARD_CHOICES.get(card, {card})}
    shopify = {t for t in PARSERS if t.startswith("shopify_")}
    assert shopify <= on_page, "a Shopify export nobody can send is an export nobody sends"


@pytest.mark.parametrize("report_type", sorted(t for t in PARSERS if t.startswith("shopify_")))
def test_a_shopify_card_asks_for_the_dates_its_report_type_is_scoped_by(report_type):
    scope = _card_scope(report_type)
    if report_type in _js_string_set("RANGE_SCOPED"):
        assert scope == "range"
    elif report_type in _js_string_set("SNAPSHOT_SCOPED"):
        assert scope == "snapshot"
    else:
        assert scope is None


def test_the_pages_signature_is_at_least_as_strict_as_the_parser():
    """A file the browser calls right cannot fail the server for a missing
    column: every column the parser requires has a signature group made only
    of that column's own synonyms, so satisfying the group resolves it."""
    signatures = _js_signatures()
    for report_type, groups in signatures.items():
        assert report_type in PARSERS, f"{report_type} has a signature but no parser"
        for synonyms in _required_synonyms(report_type):
            assert any(set(group) <= set(synonyms) for group in groups), (
                f"{report_type}: the page can pass a file with no {synonyms[0]!r} column, "
                "which the parser then rejects"
            )


def test_every_shopify_report_type_has_a_signature_to_check_against():
    signatures = _js_signatures()
    for report_type in PARSERS:
        if report_type.startswith("shopify_"):
            assert report_type in signatures
