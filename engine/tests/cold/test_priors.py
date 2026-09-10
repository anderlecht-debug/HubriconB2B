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
    assert priors.stale(date(2026, 11, 1)) is None, "the peak card covers Q4"
    assert priors.stale(date(2025, 12, 1))
    assert "2027-01-14" in priors.stale(date(2027, 2, 1))


def test_the_peak_card_takes_over_on_15_october():
    # Amazon's own worked example: a small-standard 2–4 oz unit under $10 goes
    # from $2.49 to $2.68 on the peak card. Both dates are after the surcharge.
    assert priors.card_for(date(2026, 10, 14)).name == "non_peak"
    assert priors.card_for(date(2026, 10, 15)).name == "peak"
    assert priors.card_for(date(2027, 1, 14)).name == "peak"
    assert priors.card_for(date(2027, 1, 15)) is None
    before = priors.fulfilment_fee("small_standard", 3.0, 9.49, date(2026, 10, 14))
    after = priors.fulfilment_fee("small_standard", 3.0, 9.49, date(2026, 10, 15))
    assert before == pytest.approx(2.49 * 1.035, abs=1e-4)
    assert after == pytest.approx(2.68 * 1.035, abs=1e-4)
    # The explicit card lets September price the October unit.
    peak = priors.card_named("peak")
    assert priors.fulfilment_fee("small_standard", 3.0, 9.49, date(2026, 9, 8), card=peak) == after
    # Above 3 lb the peak base steps up and the per-4-oz increment is kept.
    assert priors.fulfilment_fee("large_standard", 50.0, 25.0, date(2026, 12, 1)) == \
        pytest.approx((7.51 + 0.08) * 1.035, abs=1e-4)      # $10–50 column
    # Nothing is priced off a day no card covers.
    assert priors.fulfilment_fee("small_standard", 3.0, 9.49, date(2027, 2, 1)) is None


def test_the_ratecard_json_is_the_table():
    d = priors.ratecard_dict(date(2026, 9, 8))
    cards = d["fba"]["cards"]
    assert cards["non_peak"]["small_standard"][0] == [2, [2.43, 3.32, 3.58]]
    assert cards["peak"]["large_standard"][-1] == [48, [6.26, 7.08, 7.34]]
    assert cards["peak"]["effective"] == "2026-10-15" and cards["peak"]["through"] == "2027-01-14"
    assert d["fba"]["referral_by_category"]["electronics"] == 0.08
    assert d["carrier"]["ground_commercial"]["16"][7] == 10.67
    assert d["units_curve"]["a"] == 5.925 and d["units_curve"]["bracket"] == [0.5, 1.5]


# -- the carrier card ---------------------------------------------------------------

def test_the_carrier_card_matches_notice_123():
    # USPS Postal Explorer, Ground Advantage Commercial, effective 2026-07-12.
    assert priors.CARRIER_GROUND_COMMERCIAL[0][0] == 6.93     # under a pound, zone 1
    assert priors.CARRIER_GROUND_COMMERCIAL[0][7] == 8.40     # under a pound, zone 8
    assert priors.CARRIER_GROUND_COMMERCIAL[32][7] == 12.87   # billed at 2 lb, zone 8
    assert priors.CARRIER_EFFECTIVE == date(2026, 7, 12)
    assert all(len(row) == len(priors.CARRIER_ZONES)
               for row in priors.CARRIER_GROUND_COMMERCIAL.values())


def test_the_pound_edge_is_measured_against_the_round_up():
    """A parcel over a pound bills at *two* pounds, so the saving from dropping
    under 16 oz is measured against the flat sub-pound rate, not the one-pound
    rate that only an exactly-16.000 oz parcel pays. Measuring it the obvious
    way would understate the finding by about half."""
    now, under = priors.carrier_rows(16)
    assert now == priors.CARRIER_GROUND_COMMERCIAL[32]
    assert under == priors.CARRIER_GROUND_COMMERCIAL[0]
    assert priors.CARRIER_GROUND_USD[16] == (0.96, 4.47)      # zone 3 to zone 8
    assert priors.CARRIER_GROUND_USD[32] == (0.58, 2.88)


def test_an_edge_with_no_row_on_the_card_stays_unpriced():
    # 48 oz needs the 4 lb row, which is not on file. Absent, not guessed.
    assert priors.carrier_rows(48) is None
    assert 48 not in priors.CARRIER_GROUND_USD
    # And 0 is a row of the card, not an edge a parcel can sit above.
    assert 0 not in priors.CARRIER_GROUND_USD
