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
FEE_PARTS = {
    "amazon": "referral, FBA fulfilment, storage and every other fee line",
    "shopify": "payment processing, shipping labels, apps and 3PL charges",
}
# Amazon disburses every fourteen days; Shopify Payments pays out daily
# (funds land about two business days after the sale). The cash cone uses
# the cycle; the lag is inside a day's noise at a 90-day horizon.
PAYOUT_CYCLE_DAYS = {"amazon": 14, "shopify": 1}
PAYOUT_NOTE = {
    "amazon": "Amazon settlement phase unknown — payouts assumed every 14 days",
    "shopify": "Shopify Payments pays out daily; the ~2 business-day lag is ignored at this horizon",
}
# Where the seat lives, in the client's words.
SEAT = {
    "amazon": "a permissions-scoped user in Seller Central",
    "shopify": "a collaborator account in your Shopify admin",
}
# What is watched while a price step runs: Amazon can suppress the Featured
# Offer; a Shopify store has no Buy Box, so the conversion rate carries it.
SUPPRESSION_SIGNAL = {"amazon": "Buy Box share", "shopify": "conversion rate"}
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


def payout_note(channel: str | None) -> str:
    return PAYOUT_NOTE.get((channel or "amazon").lower(), PAYOUT_NOTE["amazon"])


def suppression_signal(channel: str | None) -> str:
    return SUPPRESSION_SIGNAL.get((channel or "amazon").lower(), SUPPRESSION_SIGNAL["amazon"])


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
