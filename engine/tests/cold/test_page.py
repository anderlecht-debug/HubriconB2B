"""The teardown page. It is the proof, so it has to hold the proof."""

import html as htmlmod
from datetime import date

import pytest

from hubricon_engine.cold import findings, page, select
from builders import item, snapshot

TODAY = date(2026, 6, 1)


def built(**kw):
    snap = snapshot(items=[item(**kw)])
    f = select.best(findings.detect(snap, today=TODAY), snap)
    assert f is not None
    return f, snap, page.render(f, snap, token="tok123", cta_url="https://hubricon.com/t/tok123?cta=1",
                                expires_on=date(2026, 10, 20), generated_on=date(2026, 9, 4))


@pytest.mark.parametrize("kw", [
    dict(price=10.49, est_monthly_units=1200.0),                                  # net_vs_price
    dict(price=24.99, item_weight_oz=12.4, dims_in=(11.0, 8.0, 1.5)),             # fee_vs_weight
    dict(price=14.99, item_weight_oz=9.0, dims_in=(12.0, 9.0, 0.9)),              # size_tier
    dict(price=39.99, item_weight_oz=16.0, dims_in=(17.0, 13.0, 8.0)),            # dim weight
])
def test_every_finding_kind_renders_a_page_with_a_chart(kw):
    f, snap, html = built(**kw)
    assert "<svg" in html, f"{f.kind} rendered no chart, and the chart is the proof"
    assert html.count("<svg") == 1
    assert snap.display_name in html
    assert f.asin_or_sku in html


def test_the_assumptions_are_on_the_page_verbatim():
    f, _, html = built(price=10.49, est_monthly_units=1200.0)
    for assumption in f.assumptions:
        assert htmlmod.escape(assumption, quote=True) in html


def test_the_page_says_what_it_could_not_see():
    _, _, html = built(price=10.49)
    assert "could not see" in html
    assert "landed cost" in html


def test_the_page_carries_its_expiry_and_a_way_to_stop_it():
    _, _, html = built(price=10.49)
    assert "October 20, 2026" in html
    assert "STOP" in html


def test_the_page_is_never_indexed():
    _, _, html = built(price=10.49)
    assert 'name="robots" content="noindex, nofollow"' in html


def test_the_page_loads_nothing_and_runs_nothing():
    """A teardown that fetches a font or runs a script renders differently
    behind a corporate proxy than it did when the founder approved it."""
    _, _, html = built(price=10.49)
    assert "<script" not in html
    assert "http://" not in html
    for tag in ("src=", "@import", "fonts.googleapis"):
        assert tag not in html


def test_a_brand_name_with_html_in_it_cannot_break_the_page():
    snap = snapshot(brand='Acme <script>alert(1)</script> & Co',
                    items=[item(price=10.49, est_monthly_units=1200.0)])
    f = select.best(findings.detect(snap, today=TODAY), snap)
    html = page.render(f, snap, token="t", cta_url="https://x", expires_on=date(2026, 10, 20))
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
