"""The teardown page. It is the proof, so it has to hold the proof."""

import html as htmlmod
from datetime import date

import pytest

from hubricon_engine.cold import charts, findings, page, select
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


# -- the chart may not put a number on the page it cannot stand behind -------------

def _y_ticks(svg: str) -> list[str]:
    import re
    return re.findall(r'text-anchor="end" font-size="11" fill="#5A6480">([^<]+)</text>', svg)


def test_the_price_chart_plots_what_they_keep_when_the_fee_is_known():
    f, _, _ = built(price=10.49, est_monthly_units=1200.0)
    svg = charts.net_vs_price(f.evidence)
    values = [float(t.lstrip("$")) for t in _y_ticks(svg)]
    # $10.49 less a 15% referral less a ~$3.91 fulfilment fee is about $5.70.
    assert all(4.0 < v < 8.0 for v in values), values
    assert "YOU KEEP, PER UNIT" in svg


def test_the_price_chart_goes_relative_when_the_fee_is_not_known():
    """Without a weight the absolute fee is unknown, but the step between price
    columns is not. Plotting an absolute anyway put a figure on the page that was
    too high by the whole fulfilment fee — the one thing a teardown must not do.
    The step cancels out of a difference, so the relative curve is exact."""
    snap = snapshot(items=[item(price=10.49, item_weight_oz=None, dims_in=None,
                                est_monthly_units=1200.0)])
    f = select.best(findings.detect(snap, today=TODAY), snap)
    svg = charts.net_vs_price(f.evidence)
    assert "AGAINST PRICING AT $9.99" in svg
    assert "YOU KEEP" not in svg
    values = [float(t.replace("+", "")) for t in _y_ticks(svg)]
    assert min(values) < 0 < max(values), values
    assert all(abs(v) < 3.0 for v in values), "a difference, not a price"


# -- the shelf and the category around it ------------------------------------------

def _two_listing_snapshot():
    return snapshot(items=[
        item(ref="B00LEAD0001", title="Lead listing", price=24.99, item_weight_oz=12.4,
             dims_in=(11.0, 8.0, 1.5), est_monthly_units=1500.0),
        item(ref="B00OTHER002", title="No weight published", price=19.99,
             item_weight_oz=None, dims_in=None, est_monthly_units=400.0)])


def _render(snap, **kw):
    from hubricon_engine.cold import shelf as shelfmod
    f = select.best(findings.detect(snap, today=TODAY), snap)
    return f, page.render(f, snap, token="t", cta_url="https://x",
                          expires_on=date(2026, 10, 20), generated_on=date(2026, 9, 5),
                          shelf_rows=shelfmod.shelf(snap, TODAY), **kw)


def test_the_shelf_shows_every_listing_and_totals_them():
    f, html = _render(_two_listing_snapshot())
    assert "Your shelf, as the fee schedule sees it" in html
    assert "B00LEAD0001" in html and "B00OTHER002" in html
    assert "Across the 2 listings we can see" in html


def test_a_listing_we_cannot_price_says_why_rather_than_showing_a_dash():
    _, html = _render(_two_listing_snapshot())
    assert "no published weight" in html


def test_the_last_blind_spot_does_not_contradict_the_shelf():
    """"This is one listing" under a table of two reads as boilerplate, and
    boilerplate is what the rest of the page is trying not to be."""
    _, one = _render(snapshot(items=[item(price=24.99, item_weight_oz=12.4,
                                          dims_in=(11.0, 8.0, 1.5))]))
    _, two = _render(_two_listing_snapshot())
    assert "This is one listing." in one
    assert "This is one listing." not in two
    assert "We can see 2 of your listings" in two


def test_the_category_benchmark_needs_a_sample_worth_quoting():
    from hubricon_engine.cold import shelf as shelfmod
    # Dimensions make the size tier certain, so every row counts. Without them
    # the ladders disagree at most weights and the sample halves.
    rows = [{"category": "Baby", "weight_oz": 4.1 + i * 0.1, "dims": "10 x 8 x 2 inches"}
            for i in range(40)]
    deep = shelfmod.benchmark(rows, "Baby", your_weight_oz=4.6)
    thin = shelfmod.benchmark(rows[:5], "Baby", your_weight_oz=4.6)
    assert deep.worth_showing and not thin.worth_showing
    _, with_bench = _render(_two_listing_snapshot(), bench=deep)
    _, without = _render(_two_listing_snapshot(), bench=thin)
    assert "The same mistake, Baby-wide" in with_bench
    assert f"{deep.measured:,}" in with_bench
    assert "same mistake" not in without, "a thin sample is left off, not rounded up"
