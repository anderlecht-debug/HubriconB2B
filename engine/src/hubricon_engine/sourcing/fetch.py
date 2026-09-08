"""Plain HTTP first, headless Chrome only when a store actually refuses.

`harvest/shopify.py` routes every Shopify request through Chrome
(`chrome_hosts=("",)`), on the strength of a 2026-09-04 pass in which every
`/meta.json` and `/products.json` fetched with a plain urllib session answered
429. That is six seconds and one browser process per page, which is why the
harvest reads about 120 stores a run.

Re-measured on 2026-09-05 across seven stores and three user agents — a browser
UA, a named bot UA, and `Python-urllib/3.12`:

    allbirds.com      meta 200   products 200   (every agent)
    brooklinen.com    meta 200   products 200   (every agent)
    drinkolipop.com   meta 200   products 200   (every agent)
    gymshark.com      meta 404   products 403   (every agent)
    ridge.com         meta 403   products 403   (every agent)
    bombas.com        meta 429   products 429   (every agent)
    italic.com        meta 404   products 404   (every agent)

The agent made no difference anywhere; the *store* made all of it. What refuses
is the edge in front of the store — Cloudflare on ridge, Vercel on bombas — and
what answers, answers to anything. So "Shopify blocks plain HTTP" is really
"some Shopify stores sit behind something that does", and paying six seconds of
Chrome for the ones that do not is the whole cost of the lane.

Hence: try plain, escalate on refusal. A 404 is not a refusal — it is the store
saying the endpoint is not there, which is the common answer from a headless
(Hydrogen) storefront — so it does not spend a Chrome launch.

Nothing here modifies `harvest/fetch.py`. It composes two of its `Fetcher`s,
which keeps this package clear of a file another session is editing.
"""

from __future__ import annotations

from ..harvest.fetch import Fetcher, chrome_binary
from ..harvest.shopify import json_payload

# Distinguishes "build me one" from an explicit "there is no fallback".
_BUILD = object()

# A named agent with somewhere to complain to. These are public integration
# endpoints and reading them politely is fine; doing it anonymously at volume
# is how a channel gets Cloudflare-flagged for everybody.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0.0.0 Safari/537.36 (+https://gethubricon.com/bot)")


def plain_fetcher(min_interval: float = 1.0, jitter: float = 0.5, timeout: int = 20) -> Fetcher:
    """One request a second per host, no browser. Shopify's own robots.txt
    disallows neither /products.json nor /meta.json (checked 2026-09-05), and
    a second between requests to one store is well inside polite."""
    return Fetcher(min_interval=min_interval, jitter=jitter, timeout=timeout,
                   chrome_hosts=(), user_agent=USER_AGENT)


def chrome_fetcher(min_interval: float = 2.0, jitter: float = 1.5, timeout: int = 30) -> Fetcher:
    """The escalation path: `harvest.shopify.store_fetcher`'s settings, every
    host through Chrome. Only the stores that refused plain HTTP reach it."""
    return Fetcher(min_interval=min_interval, jitter=jitter, timeout=timeout,
                   chrome_hosts=("",), user_agent=USER_AGENT)


class DualFetcher:
    """`get`/`get_json` over a plain fetcher, falling back to a Chrome one.

    `escalations` and `refused` are counted so a run can report what the
    fallback actually cost; if the plain pass ever stops working the numbers
    say so before the throughput does.
    """

    def __init__(self, plain: Fetcher | None = None, chrome: Fetcher | None = _BUILD,
                 escalate: bool = True):
        self.plain = plain or plain_fetcher()
        # `chrome=None` explicitly means "there is no fallback" and must not be
        # confused with "you decide" — a default of None made the two the same
        # and quietly built a browser for a caller who had asked for none.
        if chrome is _BUILD:
            # No Chrome on the machine (or HARVEST_AMAZON_CLIENT=urllib) is a
            # legitimate state, not an error: escalating to a Fetcher that will
            # itself fall back to plain HTTP just repeats the request that was
            # already refused.
            chrome = chrome_fetcher() if (escalate and chrome_binary()) else None
        self.chrome = chrome
        self.stats = {"plain_ok": 0, "escalations": 0, "chrome_ok": 0, "refused": 0, "missing": 0}

    def get(self, url: str, headers: dict | None = None) -> str | None:
        """The page, from whichever client can get it."""
        missing_before = self.plain.stats["missing"]
        text = self.plain.get(url, headers)
        if text is not None:
            self.stats["plain_ok"] += 1
            return text
        if self.plain.stats["missing"] > missing_before:
            # 404: the endpoint is not there. Chrome will not conjure it.
            self.stats["missing"] += 1
            return None
        return self._escalate(url, headers)

    def get_json(self, url: str, headers: dict | None = None) -> dict | list | None:
        """The JSON at `url`, escalating when plain HTTP returns something that
        is not JSON — an interstitial, a challenge page, a React shell — as
        well as when it returns nothing at all."""
        missing_before = self.plain.stats["missing"]
        text = self.plain.get(url, headers)
        if text is not None:
            doc = json_payload(text)
            if doc is not None:
                self.stats["plain_ok"] += 1
                return doc
        elif self.plain.stats["missing"] > missing_before:
            self.stats["missing"] += 1
            return None
        got = self._escalate(url, headers)
        return json_payload(got)

    def _escalate(self, url: str, headers: dict | None) -> str | None:
        if self.chrome is None:
            self.stats["refused"] += 1
            return None
        self.stats["escalations"] += 1
        text = self.chrome.get(url, headers)
        if text is None:
            self.stats["refused"] += 1
        else:
            self.stats["chrome_ok"] += 1
        return text

    def summary(self) -> str:
        s = self.stats
        return (f"{s['plain_ok']} plain, {s['chrome_ok']}/{s['escalations']} via Chrome, "
                f"{s['missing']} missing, {s['refused']} refused")


def dual_fetcher(escalate: bool = True) -> DualFetcher:
    """The fetcher a sourcing pass runs on."""
    return DualFetcher(escalate=escalate)
