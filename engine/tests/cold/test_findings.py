"""What the cold engine is allowed to claim, and what it must refuse to.

Every test here is really one of two questions: does the arithmetic match the
published rate card, and does the finding refuse to exist when the data cannot
support it. The second matters more. A missing finding costs a send; a wrong
one is sent to a stranger who talks to every other seller in their category.
"""

from datetime import date, datetime, timezone

import pytest

from hubricon_engine.cold import findings, priors, priors
from builders import item, snapshot

TODAY = date(2026, 6, 1)     # inside the rate card's window, after the fuel surcharge


def kinds(fs):
    return {f.kind for f in fs}


def one(fs, kind):
    matches = [f for f in fs if f.kind == kind]
    assert matches, f"expected a {kind} finding, got {kinds(fs) or 'nothing'}"
    return matches[0]


# -- the shape of every finding ----------------------------------------------------

def test_every_finding_carries_a_range_a_confidence_and_its_assumptions():
    for f in findings.detect(snapshot(), today=TODAY):
        assert f.dollars_low <= f.dollars_high
        assert 0.0 <= f.confidence <= 1.0
        assert f.assumptions, f"{f.kind} states no assumptions"
        assert all(isinstance(a, str) and a for a in f.assumptions)
        assert f.evidence.get("chart"), f"{f.kind} carries no chartable evidence"
        assert f.asin_or_sku


def test_a_snapshot_with_no_listings_produces_nothing():
    assert findings.detect(snapshot(items=[]), today=TODAY) == []


def test_a_listing_with_no_price_produces_nothing():
    assert findings.detect(snapshot(items=[item(price=None)]), today=TODAY) == []


# -- price_band_edge: the $10 and $50 fee cliffs -----------------------------------

def test_a_listing_just_over_ten_dollars_nets_less_than_the_same_listing_at_999():
    fs = findings.detect(snapshot(items=[item(price=10.49)]), today=TODAY)
    f = one(fs, "price_band_edge")
    # Amazon's low-price column is 82c-1.01 cheaper per unit across the whole
    # standard card; giving up 50c of price to save ~90c of fee is a net gain.
    assert f.evidence["edge"] == 10.0
    assert f.evidence["your_price"] == 10.49
    assert f.evidence["per_unit_low"] > 0
    assert f.dollars_low > 0


def test_the_dead_zone_ends_where_the_price_rise_pays_for_the_fee_jump():
    # Above break-even the higher price is genuinely better and there is no finding.
    assert "price_band_edge" not in kinds(findings.detect(
        snapshot(items=[item(price=12.99)]), today=TODAY))
    assert "price_band_edge" not in kinds(findings.detect(
        snapshot(items=[item(price=9.99)]), today=TODAY))


def test_the_fifty_dollar_edge_is_a_narrower_dead_zone_than_the_ten_dollar_one():
    inside = findings.detect(snapshot(items=[item(price=50.10)]), today=TODAY)
    outside = findings.detect(snapshot(items=[item(price=51.50)]), today=TODAY)
    assert one(inside, "price_band_edge").evidence["edge"] == 50.0
    assert "price_band_edge" not in kinds(outside)


def test_the_price_band_finding_needs_no_weight_at_all():
    # The fee jump between price columns is the same 82c-1.01 at every weight
    # on the standard card, so a listing with no published weight still has a
    # defensible range. This is the one finding that survives missing data.
    fs = findings.detect(snapshot(items=[item(price=10.49, item_weight_oz=None, dims_in=None)]),
                         today=TODAY)
    f = one(fs, "price_band_edge")
    assert f.evidence["per_unit_low"] < f.evidence["per_unit_high"]
    with_weight = one(findings.detect(snapshot(items=[item(price=10.49)]), today=TODAY),
                      "price_band_edge")
    assert f.confidence < with_weight.confidence


# -- fee_band_edge: an ounce over a fulfilment band --------------------------------

def test_a_listing_an_ounce_over_a_band_edge_is_priced_from_the_card():
    it = item(price=24.99, item_weight_oz=12.4, dims_in=(11.0, 8.0, 1.5),
              est_monthly_units=1000.0)
    f = one(findings.detect(snapshot(items=[it]), today=TODAY), "fee_band_edge")
    # 12.4 oz in large standard: the (12, 16] row at $4.60 against the (8, 12]
    # row at $4.20, both plus the 3.5% fuel surcharge.
    expected = (4.60 - 4.20) * 1.035
    assert f.evidence["per_unit_high"] == pytest.approx(expected, abs=1e-3)
    assert f.evidence["edge"] == 12


def test_the_band_finding_says_the_published_weight_is_a_floor_not_the_billed_weight():
    it = item(price=24.99, item_weight_oz=12.4, dims_in=(11.0, 8.0, 1.5))
    f = one(findings.detect(snapshot(items=[it]), today=TODAY), "fee_band_edge")
    assert any("packaging" in a.lower() for a in f.assumptions), f.assumptions


def test_a_weight_far_above_the_edge_is_not_a_finding_because_it_cannot_be_shaved():
    # 6 oz into the band is a redesign, not a fix, and nobody acts on it.
    it = item(price=24.99, item_weight_oz=15.9, dims_in=(11.0, 8.0, 1.5))
    assert "fee_band_edge" not in kinds(findings.detect(snapshot(items=[it]), today=TODAY))


def test_a_listing_in_the_lightest_band_has_nothing_to_drop_to():
    it = item(price=24.99, item_weight_oz=1.4, dims_in=(6.0, 4.0, 0.5))
    assert "fee_band_edge" not in kinds(findings.detect(snapshot(items=[it]), today=TODAY))


def test_without_dimensions_the_band_finding_spans_both_standard_tiers():
    known = one(findings.detect(snapshot(items=[
        item(price=24.99, item_weight_oz=12.4, dims_in=(11.0, 8.0, 1.5))]), today=TODAY),
        "fee_band_edge")
    unknown = one(findings.detect(snapshot(items=[
        item(price=24.99, item_weight_oz=12.4, dims_in=None)]), today=TODAY), "fee_band_edge")
    assert unknown.confidence < known.confidence
    assert unknown.dollars_low < unknown.dollars_high
    assert any("size tier" in a.lower() for a in unknown.assumptions), unknown.assumptions


# -- dim_weight_overage: paying for air --------------------------------------------

def test_a_light_product_in_a_big_box_is_billed_on_volume():
    # 17 x 13 x 8 in = 1768 cu in, just over the one cubic foot threshold.
    # Dimensional weight 1768/139 = 12.7 lb, against a product that weighs 1 lb.
    it = item(price=39.99, item_weight_oz=16.0, dims_in=(17.0, 13.0, 8.0),
              est_monthly_units=600.0)
    f = one(findings.detect(snapshot(items=[it]), today=TODAY), "dim_weight_overage")
    assert f.evidence["dim_weight_oz"] > f.evidence["item_weight_oz"]
    assert f.dollars_low > 0
    assert any("packed dimensions" in a.lower() for a in f.assumptions), f.assumptions


def test_a_parcel_under_a_cubic_foot_is_billed_on_weight_so_there_is_no_finding():
    it = item(price=39.99, item_weight_oz=4.0, dims_in=(9.0, 6.0, 4.0))   # 216 cu in
    assert "dim_weight_overage" not in kinds(findings.detect(snapshot(items=[it]), today=TODAY))


def test_a_genuinely_heavy_product_in_a_fitting_box_is_not_paying_for_air():
    it = item(price=39.99, item_weight_oz=17 * 16, dims_in=(17.0, 13.0, 8.0))
    assert "dim_weight_overage" not in kinds(findings.detect(snapshot(items=[it]), today=TODAY))


# -- size_tier_edge: one axis out of the small-standard envelope --------------------

def test_a_flat_product_one_axis_over_the_small_standard_envelope():
    # 15 x 12 x 0.75 is the envelope. A 0.9 in thickness is the only violation.
    it = item(price=14.99, item_weight_oz=9.0, dims_in=(12.0, 9.0, 0.9),
              est_monthly_units=1200.0)
    f = one(findings.detect(snapshot(items=[it]), today=TODAY), "size_tier_edge")
    assert f.evidence["axis"] == "thickness"
    assert f.evidence["limit_in"] == 0.75
    assert f.dollars_low > 0


def test_a_product_over_the_envelope_on_two_axes_is_not_a_near_miss():
    it = item(price=14.99, item_weight_oz=9.0, dims_in=(16.0, 9.0, 3.0))
    assert "size_tier_edge" not in kinds(findings.detect(snapshot(items=[it]), today=TODAY))


def test_a_product_far_over_one_axis_is_a_redesign_not_a_near_miss():
    it = item(price=14.99, item_weight_oz=9.0, dims_in=(12.0, 9.0, 4.0))
    assert "size_tier_edge" not in kinds(findings.detect(snapshot(items=[it]), today=TODAY))


# -- the Shopify lane --------------------------------------------------------------

def test_a_shopify_parcel_over_a_pound_is_priced_across_the_zones():
    snap = snapshot(platform="shopify", key="testbrand",
                    items=[item(ref="testbrand.com/products/x", price=28.0,
                                item_weight_oz=17.5, dims_in=None)])
    f = one(findings.detect(snap, today=TODAY), "carrier_band_edge")
    assert f.evidence["edge"] == 16
    assert (f.per_unit_low, f.per_unit_high) == priors.CARRIER_GROUND_USD[16]
    assert f.evidence["band_below"] == "under a pound"
    assert f.evidence["band_above"] == "2 lb"
    assert any("zones 1 to 8" in a for a in f.assumptions), f.assumptions


def test_a_shopify_parcel_already_under_a_pound_has_nothing_to_drop_into():
    """USPS collapsed the 4 / 8 / 12 / 15.99 oz tiers into one flat rate on
    2026-07-12. A 9 oz parcel costs exactly what a 4 oz one does, so the old
    ounce-tier hook is not a smaller finding — it is a false one."""
    for weight in (4.5, 9.0, 15.5):
        snap = snapshot(platform="shopify", key="testbrand",
                        items=[item(ref="testbrand.com/products/x", price=28.0,
                                    item_weight_oz=weight, dims_in=None)])
        assert findings.detect(snap, today=TODAY) == [], f"{weight} oz must produce nothing"


def test_a_carrier_overage_nobody_could_trim_is_not_a_finding():
    """Twelve ounces into the two-pound band is a different product, not a
    packaging change. True, useless, and it reads as a machine talking."""
    snap = snapshot(platform="shopify", key="testbrand",
                    items=[item(ref="testbrand.com/products/x", price=95.0,
                                item_weight_oz=28.8, dims_in=None)])
    assert findings.detect(snap, today=TODAY) == []


def test_a_shopify_edge_the_card_has_no_row_for_is_stated_but_never_priced():
    snap = snapshot(platform="shopify", key="testbrand",
                    items=[item(ref="testbrand.com/products/x", price=95.0,
                                item_weight_oz=50.0, dims_in=None)])
    f = one(findings.detect(snap, today=TODAY), "carrier_band_edge")
    assert f.evidence["edge"] == 48
    assert f.dollars_high == 0.0 and f.per_unit_high == 0.0
    assert f.confidence < 0.7, "an unpriced finding must also fall under the confidence floor"


# -- the rate card's own window ----------------------------------------------------

def test_nothing_is_priced_off_a_rate_card_outside_its_window():
    fs = findings.detect(snapshot(items=[item(price=10.49)]), today=date(2026, 11, 20))
    assert fs == [], "the peak fee card applies; the non-peak card must not be used"


# -- volume ------------------------------------------------------------------------

def test_a_listing_with_no_volume_estimate_is_priced_per_unit_only():
    it = item(price=10.49, est_monthly_units=None, est_monthly_revenue=None)
    f = one(findings.detect(snapshot(items=[it]), today=TODAY), "price_band_edge")
    assert f.dollars_low == 0.0 and f.dollars_high == 0.0
    assert f.evidence["per_unit_low"] > 0
    assert f.evidence["monthly_units"] is None


def test_the_monthly_range_brackets_the_volume_estimate_on_both_sides():
    it = item(price=10.49, est_monthly_units=1000.0)
    f = one(findings.detect(snapshot(items=[it]), today=TODAY), "price_band_edge")
    lo, hi = f.evidence["per_unit_low"], f.evidence["per_unit_high"]
    assert f.dollars_low == pytest.approx(lo * 1000 * findings.UNITS_LOW, abs=0.01)
    assert f.dollars_high == pytest.approx(hi * 1000 * findings.UNITS_HIGH, abs=0.01)
