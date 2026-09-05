"""The rate card is the only place a cold dollar figure comes from, so it is
checked against the published schedule row by row rather than trusted."""

from datetime import date

import pytest

from hubricon_engine.cold import priors

BEFORE_FUEL = date(2026, 3, 1)     # the 3.5% surcharge starts 2026-04-17
AFTER_FUEL = date(2026, 6, 1)


def test_price_bands_split_at_ten_and_fifty():
    assert priors.price_band(9.99) == 0
    assert priors.price_band(10.00) == 1
    assert priors.price_band(50.00) == 1
    assert priors.price_band(50.01) == 2
    assert priors.price_band(None) is None
    assert priors.price_band(0) is None


@pytest.mark.parametrize("weight,band_price,expected", [
    (2.0, 5.00, 2.43), (2.0, 20.00, 3.32), (2.0, 99.00, 3.58),
    (8.0, 20.00, 3.54), (15.0, 20.00, 3.96), (16.0, 20.00, 3.96),
])
def test_small_standard_matches_the_published_card(weight, band_price, expected):
    assert priors.fulfilment_fee("small_standard", weight, band_price, BEFORE_FUEL) == expected


@pytest.mark.parametrize("weight,expected", [
    (4.0, 3.73), (8.0, 3.95), (12.0, 4.20), (16.0, 4.60),
    (20.0, 5.04), (48.0, 6.67),
])
def test_large_standard_matches_the_published_card(weight, expected):
    assert priors.fulfilment_fee("large_standard", weight, 20.00, BEFORE_FUEL) == expected


def test_large_standard_above_three_pounds_is_base_plus_eight_cents_a_quarter_pound():
    # 3 lb + one 4 oz step: 6.97 + 0.08
    assert priors.fulfilment_fee("large_standard", 52.0, 20.00, BEFORE_FUEL) == 7.05
    # part of a step bills as a whole step
    assert priors.fulfilment_fee("large_standard", 49.0, 20.00, BEFORE_FUEL) == 7.05


def test_small_standard_stops_at_sixteen_ounces():
    assert priors.fulfilment_fee("small_standard", 16.5, 20.00, BEFORE_FUEL) is None


def test_off_the_card_returns_none_not_a_plausible_number():
    assert priors.fulfilment_fee("oversize", 40.0, 20.00, BEFORE_FUEL) is None
    assert priors.fulfilment_fee("large_standard", 21 * 16, 20.00, BEFORE_FUEL) is None
    assert priors.fulfilment_fee("large_standard", 10.0, None, BEFORE_FUEL) is None


def test_the_fuel_surcharge_applies_from_its_effective_date():
    plain = priors.fulfilment_fee("small_standard", 8.0, 20.00, BEFORE_FUEL)
    fuelled = priors.fulfilment_fee("small_standard", 8.0, 20.00, AFTER_FUEL)
    assert plain == 3.54
    assert fuelled == pytest.approx(3.54 * 1.035, abs=1e-4)


def test_band_edge_below_is_the_edge_you_could_drop_under():
    assert priors.band_edge_below("small_standard", 12.3) == 12
    assert priors.band_edge_below("small_standard", 12.0) == 10
    assert priors.band_edge_below("small_standard", 1.5) is None
    assert priors.band_edge_below("large_standard", 52.0) == 48
    assert priors.band_edge_below("large_standard", 57.0) == 56


def test_the_card_says_when_it_is_out_of_its_window():
    assert priors.stale(date(2026, 6, 1)) is None
    assert "peak" in priors.stale(date(2026, 11, 1))
    assert priors.stale(date(2025, 12, 1))


def test_the_shopify_carrier_card_is_empty_on_purpose():
    # Loading it turns the Shopify lane on; inventing it would be the failure
    # mode COLD_ENGINE.md §0 names. See priors.CARRIER_GROUND_USD.
    assert priors.CARRIER_GROUND_USD == {}
    assert priors.CARRIER_EFFECTIVE is None
