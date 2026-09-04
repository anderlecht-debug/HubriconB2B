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
    assert channels.has_recovery("etsy") and channels.has_fee_cliffs("etsy")


def test_case_is_not_load_bearing():
    assert channels.fee_label("Shopify") == "Shopify fees"
    assert channels.channels_for("BOTH") == ("amazon", "shopify")
    assert not channels.has_fee_cliffs("Shopify")
