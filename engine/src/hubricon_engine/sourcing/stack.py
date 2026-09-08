"""What a storefront loads, and what it says about the money behind it.

This module exists because the ad-spend signal LEAD_SOURCING.md leans on is
not available (see `discover.py` on the Meta Ad Library). Something has to
answer "is this a real operation or a dropshipper", and the honest free answer
turns out to be sitting in the page source: **the apps a store pays for**.

Nobody installs Elevar or Northbeam without media spend worth attributing.
Nobody pays for Attentive or Postscript without a list worth texting. Recharge
means recurring revenue, Gorgias means enough tickets to need a queue, Rebuy
means someone is optimising AOV on purpose. Each one is a monthly invoice a
hobby store does not sign, which makes the stack a spend proxy in the way a
free theme with no apps is a spend proxy in the other direction.

Tiers are weighted by what the app costs and who buys it, not by how common it
is. `judge.me` and `loox` are deliberately worth less than `okendo` and
`yotpo`: the first pair skew to small stores and the second to this ICP —
which is `harvest/shopify.py`'s own observation, kept here.

Measured 2026-09-05, one homepage fetch each:
    allbirds.com   elevar, attentive, yotpo, tiktok
    gymshark.com   rebuy, loox, tiktok
Both real, both detected, and neither needed more than the bytes the browser
already downloads.
"""

from __future__ import annotations

import re

# tier -> {app: marker regex}. Markers are the strings the app's own script tag
# or its injected DOM leaves behind; they are matched against lowercased HTML.
APPS: dict[str, dict[str, str]] = {
    # Server-side attribution. The strongest single signal on this list: you
    # buy it to answer "which ads paid", which presumes ads worth the question.
    "attribution": {
        "elevar": r"elevar",
        "northbeam": r"northbeam",
        "triple_whale": r"triplewhale|triple-whale",
        "rockerbox": r"rockerbox",
    },
    "sms": {
        "attentive": r"attentivemobile|attentive\.com",
        "postscript": r"postscript\.io|postscript-",
        "klaviyo_sms": r"klaviyo.*sms",
    },
    "email": {
        "klaviyo": r"klaviyo",
        "omnisend": r"omnisend",
    },
    # Paid review platforms. Okendo and Yotpo skew to the size band we want.
    "reviews_paid": {
        "okendo": r"okendo",
        "yotpo": r"yotpo",
        "stamped": r"stamped\.io|stamped-",
        "bazaarvoice": r"bazaarvoice",
    },
    # Cheap or free review apps: a real signal that the store cares, a weak
    # one about its size.
    "reviews_light": {
        "judge_me": r"judge\.me|jdgm-",
        "loox": r"loox\.io|loox-",
    },
    "subscription": {
        "recharge": r"rechargepayments|recharge-",
        "skio": r"skio",
        "bold_subscriptions": r"bold.*subscription",
    },
    "helpdesk": {
        "gorgias": r"gorgias",
        "zendesk": r"zendesk",
        "reamaze": r"reamaze",
        "richpanel": r"richpanel",
    },
    "merchandising": {
        "rebuy": r"rebuy",
        "searchspring": r"searchspring",
        "nosto": r"nosto",
        "dynamic_yield": r"dynamicyield",
    },
    "loyalty": {
        "smile_io": r"smile\.io",
        "loyaltylion": r"loyaltylion",
        "swell": r"swellrewards",
    },
    "returns": {
        "loop_returns": r"loopreturns|loop-returns",
        "returnly": r"returnly",
        "aftership": r"aftership",
    },
    "ads": {
        "meta_pixel": r"connect\.facebook\.net|fbevents\.js",
        "tiktok_pixel": r"analytics\.tiktok\.com",
        "google_ads": r"googleadservices|gtag/js\?id=aw-",
        "pinterest": r"pintrk",
    },
}

# What one detection in each tier is worth. Attribution and SMS carry the most
# because they are the ones with a real monthly invoice behind them and the
# ones a store only buys once it is spending on acquisition.
TIER_WEIGHTS = {
    "attribution": 3.0, "sms": 2.5, "subscription": 2.0, "helpdesk": 1.5,
    "reviews_paid": 1.5, "merchandising": 1.5, "returns": 1.0, "loyalty": 1.0,
    "email": 1.0, "reviews_light": 0.5, "ads": 0.5,
}

# Shopify Plus starts around $2,300/month, so a positive is a strong size
# proxy. Absence proves nothing at all — most brands in the band are on
# Advanced — so this only ever adds.
PLUS_MARKERS = (
    r"shopify-plus", r"checkout\.shopify\.com/.*plus", r'"plus":true',
    r"script-editor", r"shopify\.checkout\.apiclientid",
)

_COMPILED = {tier: {app: re.compile(pat, re.I) for app, pat in apps.items()}
             for tier, apps in APPS.items()}
_PLUS = [re.compile(p, re.I) for p in PLUS_MARKERS]


def detect(html: str | None) -> dict:
    """-> {apps, tiers, weight, plus}. One pass over the page source.

    `weight` is the sum of the tier weights the store scored in, counted once
    per tier rather than once per app: a store running three review apps is
    not three times the operation, it is one operation mid-migration.
    """
    low = (html or "").lower()
    if not low:
        return {"apps": [], "tiers": [], "weight": 0.0, "plus": False}
    apps: list[str] = []
    tiers: list[str] = []
    for tier, patterns in _COMPILED.items():
        hit = False
        for app, pattern in patterns.items():
            if pattern.search(low):
                apps.append(app)
                hit = True
        if hit:
            tiers.append(tier)
    return {
        "apps": sorted(apps), "tiers": sorted(tiers),
        "weight": round(sum(TIER_WEIGHTS.get(t, 0.0) for t in tiers), 2),
        "plus": any(p.search(low) for p in _PLUS),
    }


def read(fetcher, domain: str) -> dict:
    """The stack for one store, from its homepage."""
    return detect(fetcher.get(f"https://{domain}/"))
