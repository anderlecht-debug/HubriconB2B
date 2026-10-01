"""The two platforms a client can sell on, and the few places they differ.

A client record carries ``platform`` ('amazon', 'shopify' or 'both'); every
canonical data row carries ``channel`` ('amazon' or 'shopify'). The models
are channel-blind arithmetic over the canonical tables — a unit is a unit
and a fee is a fee — so the platform only shows up where the *mechanics*
differ: which fee lines exist, how often cash arrives, whether there is a
reimbursement window to miss, what signal says a price step went too far.
Everything that needs one of those answers asks here instead of testing
strings itself, and every label a client reads comes from here so a Shopify
brand is never told about "Amazon fees".

``margin_results.amazon_fees`` keeps its column name for both channels (the
column is older than the second platform); ``fee_label`` is what it is
called in prose.
"""

PLATFORMS = ("amazon", "shopify", "both")
CHANNELS = ("amazon", "shopify")

LABEL = {"amazon": "Amazon", "shopify": "Shopify"}
FEE_LABEL = {"amazon": "Amazon fees", "shopify": "Shopify fees"}
# What the fee figure holds, said as narrowly as the code reads it. Amazon's
# SKU Economics itemises every fee line. On Shopify the figure is the payment
# processing fee alone (shopify_orders.py: Shopify Payments' 2.9% + 30¢ until a
# payouts row says otherwise); no label, app or 3PL export is read, so those
# are named as missing rather than implied (corrected 2026-10-01: this line
# said "shipping labels, apps and 3PL charges" and nothing read them). A
# pick, pack and postage cost typed on the cost sheet lands in landed cost
# (models/margin.py), not here.
FEE_PARTS = {
    "amazon": "referral, FBA fulfilment, storage and every other fee line",
    "shopify": ("Shopify Payments processing fees only; shipping labels, apps and 3PL charges are not in this "
                "figure, and a pick, pack and postage cost on your cost sheet is counted with landed cost"),
}
# When a sale becomes cash in the bank (corrected 2026-10-01; until then the
# cash cone paid a sale made on day 13 on day 14).
#
# Amazon, "Payments based on delivery date" (Seller Central help G202124090):
# "The standard reserve period is 7 days after delivery date ('DD + 7')". Its
# own example: sold January 1, delivered January 6, available January 14 — the
# funds release on the eighth calendar day after delivery. The remaining North
# American accounts moved to DD+7 on 2026-03-12. Settlement then runs every 14
# days (daily on Disburse on Demand, not assumed here) and the bank transfer
# takes up to 5 business days.
#   reserve  = delivery (ASSUMED 2 days, a typical FBA delivery) + 8 = 10 days
#              from the sale until Amazon can settle it
#   transit  = 3 business days ≈ 4 calendar days, a stated central value of
#              Amazon's "up to 5"
# Shopify Payments: payouts "typically arrive … within 3 to 5 business days
# after a customer's payment is captured", on a daily, weekly or monthly
# schedule. Modelled daily, 3 business days ≈ 4 calendar days from the sale to
# the bank; the transfer is inside that figure, so its own transit is zero.
PAYOUT_CYCLE_DAYS = {"amazon": 14, "shopify": 1}
PAYOUT_DELIVERY_DAYS = {"amazon": 2, "shopify": 0}
AMAZON_RELEASE_AFTER_DELIVERY_DAYS = 8      # DD+7: delivered Jan 6, available Jan 14
PAYOUT_RESERVE_DAYS = {"amazon": PAYOUT_DELIVERY_DAYS["amazon"] + AMAZON_RELEASE_AFTER_DELIVERY_DAYS,
                       "shopify": 4}
PAYOUT_TRANSIT_DAYS = {"amazon": 4, "shopify": 0}
PAYOUT_NOTE = {
    "amazon": (f"A sale becomes payable {PAYOUT_RESERVE_DAYS['amazon']} days after it is made (delivery assumed "
               f"{PAYOUT_DELIVERY_DAYS['amazon']} days, then Amazon's reserve until 7 days after delivery, DD+7); "
               f"Amazon settles every {PAYOUT_CYCLE_DAYS['amazon']} days and the transfer is assumed to reach your "
               f"bank {PAYOUT_TRANSIT_DAYS['amazon']} days later (3 business days; Amazon says up to 5). Your "
               f"settlement date is not on file, so the last transfer is assumed to have reached your bank today "
               f"and the next to land in {PAYOUT_CYCLE_DAYS['amazon']} days, the longest wait"),
    "shopify": (f"Shopify Payments is assumed to pay out daily, each day's sales reaching your bank "
                f"{PAYOUT_RESERVE_DAYS['shopify']} days later (3 business days; Shopify says 3 to 5). A weekly or "
                f"monthly payout schedule would hold cash longer and is not modelled"),
}
# Where the seat lives, in the client's words. On Shopify a staff account the
# owner adds is the route they can take alone; a collaborator request needs a
# Shopify Partner organisation on our side, which the onboarding copy names
# only as an alternative (onboarding.SEAT_HINT).
SEAT = {
    "amazon": "a permissions-scoped user in Seller Central",
    "shopify": "a staff account in your Shopify admin",
}
# What says a price step went too far. Amazon can suppress the Featured Offer,
# and the Buy Box share is read while a step runs (the Business Report in the
# measurement pass, and the daily reading `hubricon watch` records and
# .github/workflows/issue.yml asks for). A Shopify store has no Buy Box, and no code
# reads its conversion rate (only a number typed by hand into `hubricon watch
# --conversion`), so what carries it is what is ingested: the units the product
# sells on the client's own orders, before and after the step
# (measurement.measure_price_step, from the Orders export).
SUPPRESSION_SIGNAL = {"amazon": "Buy Box share", "shopify": "units sold, read on your orders"}
HAS_BUY_BOX = {"amazon": True, "shopify": False}
# Every sentence a client reads about what is watched while a price move is
# live comes from here, so no draft, plan or report can say more than the code
# does. `{what}` is "step", "markdown" or "test".
WATCH_SENTENCE = {
    "amazon": "Buy Box watched while the {what} is live.",
    "shopify": ("No Buy Box on Shopify: the {what} is read on your own orders, the units this product sells "
                "before and after it."),
}
WATCH_CLAUSE = {
    "amazon": "watch your Buy Box while a step is live",
    "shopify": "read each step on your own orders, the units sold before and after it",
}
# Where a move happens, for a client who sells on both (store_place).
PLACE = {"amazon": "Amazon account", "shopify": "Shopify store"}
# Reimbursement recovery reconciles Amazon's own bleed exports (ledger,
# returns, reimbursements, settlements). A Shopify store has no warehouse
# that loses units on its behalf and no claim window to miss.
HAS_RECOVERY = {"amazon": True, "shopify": False}
# The FBA fee cliffs (low-inventory fee, aged-inventory surcharge, peak
# storage) are Amazon's step functions; a Shopify store pays its 3PL's flat
# rate, or nothing when it ships from its own shelf.
HAS_FEE_CLIFFS = {"amazon": True, "shopify": False}


# Core exports only one platform can produce. Amazon's Business Report
# (sessions, page views, Buy Box share) has no Shopify equivalent the models
# read, so a Shopify client scored against it could never reach full data
# coverage — it would be marked down forever for a file it cannot send.
AMAZON_ONLY_REPORTS = frozenset({"asin_traffic"})


def reports_available(reports, channel: str | None) -> tuple[str, ...]:
    """The subset of `reports` the channel can actually produce. Used wherever
    data coverage is scored, so 'complete' means complete for this platform."""
    if (channel or "amazon").lower() == "amazon":
        return tuple(reports)
    return tuple(r for r in reports if r not in AMAZON_ONLY_REPORTS)


def channels_for(platform: str | None) -> tuple[str, ...]:
    """The channels a client's data can carry: one for a single-platform
    client, both for 'both'. Unknown/None is treated as Amazon (every client
    before 2026-09-04 was)."""
    p = (platform or "amazon").lower()
    if p == "both":
        return CHANNELS
    return (p,) if p in CHANNELS else ("amazon",)


def client_channel(client: dict | None) -> str | None:
    """The single channel of a single-platform client; None for 'both'
    (the caller then runs per channel)."""
    chans = channels_for((client or {}).get("platform"))
    return chans[0] if len(chans) == 1 else None


def label(channel: str | None) -> str:
    return LABEL.get((channel or "amazon").lower(), "Amazon")


def fee_label(channel: str | None) -> str:
    return FEE_LABEL.get((channel or "amazon").lower(), FEE_LABEL["amazon"])


def fee_parts(channel: str | None) -> str:
    return FEE_PARTS.get((channel or "amazon").lower(), FEE_PARTS["amazon"])


def payout_cycle_days(channel: str | None) -> int:
    return PAYOUT_CYCLE_DAYS.get((channel or "amazon").lower(), PAYOUT_CYCLE_DAYS["amazon"])


def payout_reserve_days(channel: str | None, delivery_days: int | None = None) -> int:
    """Calendar days from a sale until the platform can settle it. For Amazon
    `delivery_days` replaces the assumed delivery time: Amazon's own example,
    sold Jan 1 and delivered Jan 6 (5 days), is payable Jan 14 (13 days)."""
    ch = (channel or "amazon").lower()
    if ch not in PAYOUT_RESERVE_DAYS:
        ch = "amazon"
    if delivery_days is not None and ch == "amazon":
        return int(delivery_days) + AMAZON_RELEASE_AFTER_DELIVERY_DAYS
    return PAYOUT_RESERVE_DAYS[ch]


def payout_transit_days(channel: str | None) -> int:
    """Calendar days from a settlement to the money in the seller's bank."""
    return PAYOUT_TRANSIT_DAYS.get((channel or "amazon").lower(), PAYOUT_TRANSIT_DAYS["amazon"])


def payout_note(channel: str | None) -> str:
    return PAYOUT_NOTE.get((channel or "amazon").lower(), PAYOUT_NOTE["amazon"])


def suppression_signal(channel: str | None) -> str:
    return SUPPRESSION_SIGNAL.get((channel or "amazon").lower(), SUPPRESSION_SIGNAL["amazon"])


def has_buy_box(channel: str | None) -> bool:
    return HAS_BUY_BOX.get((channel or "amazon").lower(), True)


def watch_phrase(channel: str | None, what: str = "step") -> str:
    """The one sentence on what is watched while a price move is live:
    'Buy Box watched while the step is live.' on Amazon; on Shopify, where the
    move is read on the client's own orders."""
    ch = (channel or "amazon").lower()
    return WATCH_SENTENCE.get(ch, WATCH_SENTENCE["amazon"]).format(what=what)


def watch_clause(channel: str | None) -> str:
    """The same promise as a clause after 'we': 'watch your Buy Box while a
    step is live', or, on Shopify, 'read each step on your own orders…'."""
    return WATCH_CLAUSE.get((channel or "amazon").lower(), WATCH_CLAUSE["amazon"])


def store_name(platform: str | None, channel: str | None) -> str | None:
    """'Amazon' or 'Shopify' when the client sells on both, so every notice,
    Brief and alert says which store it is about; None for a one-store client,
    whose mail reads exactly as it did before."""
    if channel is None or len(channels_for(platform)) < 2:
        return None
    return label(channel)


def store_place(platform: str | None, channel: str | None) -> str | None:
    """'Amazon account' or 'Shopify store' for a two-store client, else None."""
    if store_name(platform, channel) is None:
        return None
    return PLACE.get(channel.lower(), PLACE["amazon"])


def has_recovery(channel: str | None) -> bool:
    return HAS_RECOVERY.get((channel or "amazon").lower(), True)


def has_fee_cliffs(channel: str | None) -> bool:
    return HAS_FEE_CLIFFS.get((channel or "amazon").lower(), True)


def seat(channel: str | None) -> str:
    return SEAT.get((channel or "amazon").lower(), SEAT["amazon"])


def both_label(platform: str | None) -> str:
    """'Amazon', 'Shopify', or 'Amazon and Shopify' for a client's masthead."""
    chans = channels_for(platform)
    return " and ".join(LABEL[c] for c in chans)
