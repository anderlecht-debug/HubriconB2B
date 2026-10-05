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
    # no Buy Box on a Shopify store, and no code reads its conversion rate: a
    # step is read on the units its own orders show (2026-10-01)
    assert channels.suppression_signal("amazon") == "Buy Box share"
    assert channels.suppression_signal("shopify") == "units sold, read on your orders"
    assert channels.has_buy_box("amazon") and not channels.has_buy_box("shopify")


def test_what_is_watched_is_said_once_and_only_as_far_as_the_code_goes():
    """Every 'Buy Box watched' a client reads comes from channels.watch_phrase,
    so a Shopify step is never promised a Buy Box, and nothing is 'watched
    daily' that no code watches."""
    assert channels.watch_phrase("amazon") == "Buy Box watched while the step is live."
    assert channels.watch_phrase(None, "markdown") == "Buy Box watched while the markdown is live."
    shop = channels.watch_phrase("shopify")
    assert "Buy Box" in shop and shop.startswith("No Buy Box on Shopify")
    assert "read on your own orders" in shop and "before and after" in shop
    for text in (shop, channels.watch_phrase("shopify", "markdown"), channels.watch_clause("shopify")):
        assert "daily" not in text and "conversion" not in text
    assert channels.watch_clause("amazon") == "watch your Buy Box while a step is live"
    assert "Buy Box" not in channels.watch_clause("shopify")


def test_the_shopify_fee_figure_names_only_what_is_read():
    """No label, app or 3PL export is read, so the fee figure says they are
    not in it rather than implying they are (finding 2, 2026-10-01)."""
    parts = channels.fee_parts("shopify")
    assert parts.startswith("Shopify Payments processing fees only")
    assert "shipping labels, apps and 3PL charges are not in this figure" in parts


def test_a_two_store_client_is_told_which_store_and_a_one_store_client_is_not():
    assert channels.store_name("both", "shopify") == "Shopify"
    assert channels.store_name("both", "amazon") == "Amazon"
    assert channels.store_name("BOTH", "Shopify") == "Shopify"
    for platform in ("amazon", "shopify", None):
        assert channels.store_name(platform, "shopify") is None
        assert channels.store_place(platform, "amazon") is None
    assert channels.store_name("both", None) is None
    assert channels.store_place("both", "shopify") == "Shopify store"
    assert channels.store_place("both", "amazon") == "Amazon account"
    # the seat a Shopify owner can grant alone
    assert channels.seat("shopify") == "a staff account in your Shopify admin"


def test_an_unknown_channel_is_treated_as_amazon():
    for fn in (channels.label, channels.fee_label, channels.fee_parts,
               channels.payout_note, channels.suppression_signal, channels.seat,
               channels.watch_phrase, channels.watch_clause, channels.has_buy_box):
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
