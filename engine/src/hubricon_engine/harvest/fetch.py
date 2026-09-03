"""Polite fetching of public pages, with nothing installed.

Amazon serves its seller-profile, product and Best Sellers pages to a
browser-like request from a home connection and answers datacenter ranges
with a captcha. So: one user agent per run, a cookie jar, a few seconds
between requests to the same host, and the run stops for the day the moment
Amazon starts answering with captchas. Nothing here tries to defeat a
captcha; it waits once, then gives up.
"""

from __future__ import annotations

import gzip
import http.cookiejar
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
]
BLOCK_MARKERS = (
    "validateCaptcha",
    "Robot Check",
    "To discuss automated access to Amazon data",
    "Type the characters you see in this image",
)


class Blocked(RuntimeError):
    """Amazon is answering with captchas; the run stops so tomorrow still works."""


def _urllib_transport(jar: http.cookiejar.CookieJar):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def transport(url: str, headers: dict, timeout: int) -> tuple[int, str]:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=timeout) as res:
            raw = res.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return res.status, raw.decode("utf-8", "replace")

    return transport


class Fetcher:
    """`get(url)` → page text, or None when the page is missing, errored, or a captcha.

    Pace: 7–12 s between requests to the same host. On 2026-09-03 about 180
    Amazon requests in 35 minutes at 4–7 s drew captchas; roughly 350 an hour
    is the ceiling we stay under. transport(url, headers, timeout) ->
    (status, text) is injectable for tests.
    """

    def __init__(self, min_interval: float = 7.0, jitter: float = 5.0, timeout: int = 40,
                 block_pause: float = 600.0, max_block_streak: int = 2,
                 transport=None, sleep=time.sleep, clock=time.monotonic, user_agent: str | None = None):
        self.jar = http.cookiejar.CookieJar()
        self.transport = transport or _urllib_transport(self.jar)
        self.min_interval, self.jitter, self.timeout = min_interval, jitter, timeout
        self.block_pause, self.max_block_streak = block_pause, max_block_streak
        self.sleep, self.clock = sleep, clock
        self.ua = user_agent or random.choice(USER_AGENTS)
        self._last: dict[str, float] = {}
        self.block_streak = 0
        self.stats = {"requests": 0, "ok": 0, "missing": 0, "errors": 0, "blocked": 0, "chars": 0}

    def _pace(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval + random.random() * self.jitter - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)
        self._last[host] = self.clock()

    def get(self, url: str, headers: dict | None = None) -> str | None:
        host = urllib.parse.urlparse(url).netloc
        self._pace(host)
        hdrs = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
            **(headers or {}),
        }
        self.stats["requests"] += 1
        try:
            status, text = self.transport(url, hdrs, self.timeout)
        except urllib.error.HTTPError as err:
            if err.code in (429, 503) and "amazon." in host:
                return self._blocked(url)
            self.stats["missing" if err.code == 404 else "errors"] += 1
            return None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            self.stats["errors"] += 1
            return None
        self.stats["chars"] += len(text)
        if "amazon." in host and any(m in text for m in BLOCK_MARKERS):
            return self._blocked(url)
        self.block_streak = 0
        self.stats["ok"] += 1
        return text

    def _blocked(self, url: str) -> None:
        self.stats["blocked"] += 1
        self.block_streak += 1
        if self.block_streak >= self.max_block_streak:
            raise Blocked(f"Amazon answered {self.block_streak} requests in a row with a captcha ({url}); "
                          "stopping for today.")
        self.sleep(self.block_pause)
        return None


class Cache:
    """Parsed results on disk (never raw HTML), keyed by kind/key, with an age limit.

    Default root ~/.hubricon/harvest. A page parsed last week is not fetched
    again this week; the crawl's cost is bounded by what is new.
    """

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else Path.home() / ".hubricon" / "harvest"

    def _path(self, kind: str, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return self.root / kind / f"{safe}.json"

    def get(self, kind: str, key: str, max_age_days: int = 30) -> dict | None:
        p = self._path(kind, key)
        if not p.exists():
            return None
        try:
            doc = json.loads(p.read_text())
        except (OSError, ValueError):
            return None
        stamp = datetime.fromisoformat(doc.get("_at", "1970-01-01T00:00:00+00:00"))
        if datetime.now(timezone.utc) - stamp > timedelta(days=max_age_days):
            return None
        return doc.get("value")

    def put(self, kind: str, key: str, value) -> None:
        p = self._path(kind, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"_at": datetime.now(timezone.utc).isoformat(), "value": value}))
