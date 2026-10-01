"""channels.py — the one place the two platforms differ.

Everything else in the engine asks these functions instead of testing
platform strings, so these are the assertions that keep a Shopify brand from
being told about Amazon fees.
"""

from hubricon_engine import channels


def test_channels_for_a_clients_platform():
    assert channels.channels_for("amazon") == ("amazon",)
    assert channels.channels_for("shopify") == ("shopify",)
    assert channels.channels_for("both") == ("amazon", "shopify")
    # every client on file before 2026-09-04 was an Amazon seller
    assert channels.channels_for(None) == ("amazon",)
    assert channels.channels_for("etsy") == ("amazon",)


def test_client_channel_is_none_only_for_a_two_platform_client():
    assert channels.client_channel({"platform": "shopify"}) == "shopify"
    assert channels.client_channel({"platform": "amazon"}) == "amazon"
    assert channels.client_channel({"platform": "both"}) is None   # the caller runs per channel
    assert channels.client_channel({}) == "amazon"
    assert channels.client_channel(None) == "amazon"


def test_labels_name_the_platform_the_client_actually_sells_on():
    assert channels.label("shopify") == "Shopify" and channels.label("amazon") == "Amazon"
    assert channels.fee_label("shopify") == "Shopify fees"
    assert channels.fee_label("amazon") == "Amazon fees"
    assert "3PL" in channels.fee_parts("shopify")
    assert "FBA" in channels.fee_parts("amazon")
    assert channels.both_label("both") == "Amazon and Shopify"
    assert channels.both_label("shopify") == "Shopify"
    assert channels.both_label(None) == "Amazon"
    assert "Shopify admin" in channels.seat("shopify")


def test_the_mechanics_only_amazon_has():
    assert channels.has_recovery("amazon") and not channels.has_recovery("shopify")
    assert channels.has_fee_cliffs("amazon") and not channels.has_fee_cliffs("shopify")
    assert channels.payout_cycle_days("amazon") == 14
    assert channels.payout_cycle_days("shopify") == 1
    assert "14 days" in channels.payout_note("amazon")
    assert "daily" in channels.payout_note("shopify")
    # no Buy Box on a Shopify store, so a price test watches conversion instead
    assert channels.suppression_signal("amazon") == "Buy Box share"
    assert channels.suppression_signal("shopify") == "conversion rate"


def test_an_unknown_channel_is_treated_as_amazon():
    for fn in (channels.label, channels.fee_label, channels.fee_parts,
               channels.payout_note, channels.suppression_signal, channels.seat):
        assert fn("etsy") == fn("amazon")
        assert fn(None) == fn("amazon")
    assert channels.payout_cycle_days(None) == 14
    assert channels.payout_reserve_days("etsy") == channels.payout_reserve_days("amazon")
    assert channels.payout_transit_days(None) == channels.payout_transit_days("amazon")
    assert channels.has_recovery("etsy") and channels.has_fee_cliffs("etsy")


def test_amazons_own_example_sold_jan_1_delivered_jan_6_is_payable_jan_14():
    """Seller Central help G202124090: the reserve runs to 7 days after the
    delivery date (DD+7), and Amazon's example releases a January 1 sale
    delivered January 6 on January 14."""
    from datetime import date, timedelta
    sold, delivered = date(2026, 1, 1), date(2026, 1, 6)
    reserve = channels.payout_reserve_days("amazon", delivery_days=(delivered - sold).days)
    assert sold + timedelta(days=reserve) == date(2026, 1, 14)
    # unstated, delivery is assumed to take 2 days: payable 10 days after the sale
    assert channels.payout_reserve_days("amazon") == 10
    assert channels.payout_transit_days("amazon") == 4         # 3 business days of Amazon's "up to 5"
    # Shopify: 3 business days from capture to the bank, the transfer inside it
    assert (channels.payout_reserve_days("shopify"), channels.payout_transit_days("shopify")) == (4, 0)
    assert channels.payout_reserve_days("shopify", delivery_days=5) == 4, "delivery does not hold Shopify money"
    # the sentences say what is assumed, with the numbers the model uses
    note = channels.payout_note("amazon")
    for phrase in ("10 days", "delivery assumed 2 days", "DD+7", "every 14 days", "4 days later",
                   "up to 5", "not on file"):
        assert phrase in note, phrase
    assert "4 days later" in channels.payout_note("shopify") and "3 to 5" in channels.payout_note("shopify")


def test_case_is_not_load_bearing():
    assert channels.fee_label("Shopify") == "Shopify fees"
    assert channels.channels_for("BOTH") == ("amazon", "shopify")
    assert not channels.has_fee_cliffs("Shopify")
