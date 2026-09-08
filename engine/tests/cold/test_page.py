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


def test_a_long_catalogue_is_shown_not_dumped():
    """A Shopify store publishes up to 250 products. The table is evidence that
    we looked at the shelf, not an inventory report."""
    from hubricon_engine.cold import shelf as shelfmod
    many = snapshot(items=[item(ref=f"B{i:09d}", title=f"Listing {i}", price=24.99,
                                item_weight_oz=12.4, dims_in=(11.0, 8.0, 1.5),
                                est_monthly_units=800.0) for i in range(28)])
    f = select.best(findings.detect(many, today=TODAY), many)
    html = page.render(f, many, token="t", cta_url="https://x",
                       expires_on=date(2026, 10, 20),
                       shelf_rows=shelfmod.shelf(many, TODAY))
    assert html.count("<tr>") <= page.SHELF_ROWS + 2
    assert "and 18 more listings we can see" in html
    assert "Across the 28 listings we can see" in html


def test_the_shopify_benchmark_uses_the_carrier_ladder_not_the_fba_one():
    """A pound boundary under a Shopify parcel and an FBA band under an Amazon
    one. Mixing the two would put the wrong edge under someone's business."""
    from hubricon_engine.cold import shelf as shelfmod
    rows = ([{"platform": "shopify", "weight_oz": 17.0 + i * 0.2, "category": "Bags"}
             for i in range(40)]
            + [{"platform": "amazon", "weight_oz": 4.5, "category": "Bags", "dims": None}] * 40)
    shop = shelfmod.benchmark(rows, "Bags", your_weight_oz=17.2, platform="shopify")
    amz = shelfmod.benchmark(rows, "Bags", your_weight_oz=4.5, platform="amazon")
    assert shop.category == "Shopify brands"      # product_type is free text; no shared taxonomy
    assert shop.measured == 40 and amz.measured == 40
    assert shop.your_over_by == 1.2               # over the 16 oz pound boundary
    assert amz.your_over_by == 0.5                # over the 4 oz FBA band


def test_the_shelf_columns_match_the_cells_on_both_platforms():
    """Header and cells were written out separately and drifted: a Shopify page
    printed 'Amazon's fee' over a column of dashes and a band width under a
    heading that said size tier."""
    from hubricon_engine.cold import shelf as shelfmod
    import re as _re
    # Amazon needs dimensions for a known size tier; Shopify has none to give.
    for plat, ref, weight, dims, price in (
            ("amazon", "B00TEST0001", 12.4, (11.0, 8.0, 1.5), 24.99),
            # A carrier range spans zones, so its top end is wide; at $24.99 the
            # claim would exceed a quarter of the listing's revenue and select
            # would rightly refuse it.
            ("shopify", "b.com/products/harbor-tote", 17.2, None, 68.0)):
        snap = snapshot(platform=plat, items=[item(ref=ref, price=price, item_weight_oz=weight,
                                                   dims_in=dims, est_monthly_units=900.0)])
        f = select.best(findings.detect(snap, today=TODAY), snap)
        html = page.render(f, snap, token="t", cta_url="https://x",
                           expires_on=date(2026, 10, 20),
                           shelf_rows=shelfmod.shelf(snap, TODAY))
        head = _re.search(r"<thead><tr>(.*?)</tr></thead>", html, _re.S).group(1)
        first = _re.search(r"<tbody><tr>(.*?)</tr>", html, _re.S).group(1)
        # count the tags, not the literal "<td>": the last cell is styled.
        assert head.count("<th") == first.count("<td"), plat
        if plat == "shopify":
            assert "Amazon" not in head
            assert "harbor-tote" in first and "b.com/products" not in first


def test_a_shopify_listing_is_named_by_its_handle_not_its_whole_url():
    # A forty-character URL forced the first column so wide that every other one
    # scrolled off the page.
    from hubricon_engine.cold import shelf as shelfmod
    snap = snapshot(platform="shopify",
                    items=[item(ref="www.holtzleather.com/products/american-walnut-cutting-board",
                                price=48.0, item_weight_oz=17.2, dims_in=None)])
    row = shelfmod.shelf(snap, TODAY)[0]
    assert row.label == "american-walnut-cutting-board"
    assert row.ref.startswith("www.holtzleather.com")


def test_the_shelf_leads_with_the_listings_that_have_something_to_say():
    from hubricon_engine.cold import shelf as shelfmod
    snap = snapshot(platform="shopify", items=[
        item(ref="b.com/products/aaa-heavy", price=40.0, item_weight_oz=40.0, dims_in=None),
        item(ref="b.com/products/zzz-near", price=40.0, item_weight_oz=17.2, dims_in=None)])
    assert [r.label for r in shelfmod.shelf(snap, TODAY)][0] == "zzz-near", \
        "alphabetical order put ten arbitrary handles at the top of the evidence"


def test_the_proof_line_renders_above_the_button_and_never_unescaped():
    from datetime import date as _date
    from hubricon_engine.cold import page as _page, findings as _findings, select as _select
    from builders import item as _item, snapshot as _snapshot
    snap = _snapshot(items=[_item(price=10.49, est_monthly_units=1200.0)])
    f = _select.best(_findings.detect(snap, today=_date(2026, 6, 1)), snap)
    html = _page.render(f, snap, token="tok", cta_url="https://x/t/tok?cta=1", expires_on=_date(2026, 7, 15),
                        proof_line="A <kitchen> brand took the free month and has $12,300 on its ledger.")
    assert 'class="proof"' in html and "&lt;kitchen&gt;" in html and "$12,300" in html
    assert html.index('class="proof"') < html.index("Get the full teardown, free")
    bare = _page.render(f, snap, token="tok", cta_url="https://x/t/tok?cta=1", expires_on=_date(2026, 7, 15))
    assert 'class="proof"' not in bare
