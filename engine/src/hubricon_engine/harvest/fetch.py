"""Polite fetching of public pages, with nothing installed.

Amazon serves its seller-profile, product and Best Sellers pages to a
browser-like request from a home connection and answers datacenter ranges
with a captcha. So: one user agent per run, a cookie jar, a few seconds
between requests to the same host, and the run stops for the day the moment
Amazon starts answering with captchas. Nothing here tries to defeat a
captcha; it waits once, then gives up.
"""

from __future__ import annotations

import atexit
import gzip
import http.cookiejar
import json
import os
import random
import shutil
import signal
import subprocess
import threading
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
    # The 2 KB "Sorry! Something went wrong!" page is the soft block Amazon
    # serves search and storefront requests once a client is flagged
    # (2026-09-03 evening, after seven captchas); parsing it yields nothing.
    "<title>Sorry! Something went wrong!</title>",
)


class Blocked(RuntimeError):
    """Amazon is answering with captchas; the run stops so tomorrow still works."""


# Amazon fingerprints the client, not just the pace: a plain urllib session
# drew a captcha on its second product page on 2026-09-03 while the same
# pages loaded cleanly in headless Chrome from the same connection. So the
# Amazon pages go through the Mac's own Chrome when it is installed (one
# process per page, --dump-dom, a private profile under ~/.hubricon); every
# other host keeps urllib. HARVEST_AMAZON_CLIENT=urllib turns it off.
CHROME_CANDIDATES = (
    os.environ.get("HARVEST_CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "",
)


def chrome_binary() -> str | None:
    if os.environ.get("HARVEST_AMAZON_CLIENT", "chrome").lower() != "chrome":
        return None
    return next((c for c in CHROME_CANDIDATES if c and os.path.exists(c)), None)


def _chrome_transport(chrome: str, profile_dir: str | None = None, hard_timeout: float = 45.0, runner=None):
    """transport(url, headers, timeout) → (200, rendered DOM). Chrome writes the
    DOM and then lingers (its updater child keeps the pipe open), so stdout is
    read as it arrives and the process group is killed the moment the document
    ends, or at the hard timeout."""
    # One profile per process: Chrome refuses to start on a profile another
    # instance holds (it hands the URL to that instance and exits with no
    # DOM), so a crawl, an enrich pass and the launchd run must not share one.
    profile = profile_dir or str(Path.home() / ".hubricon" / "chrome-profile" / str(os.getpid()))
    atexit.register(shutil.rmtree, profile, True)

    def transport(url: str, headers: dict, timeout: int) -> tuple[int, str]:
        Path(profile).mkdir(parents=True, exist_ok=True)
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", "--disable-background-networking", "--disable-component-update",
               "--disable-sync", "--mute-audio", f"--user-data-dir={profile}", "--window-size=1280,900",
               f"--user-agent={headers.get('User-Agent', '')}", f"--lang={headers.get('Accept-Language', 'en-US')}",
               f"--timeout={int(min(timeout, 30) * 1000)}", "--virtual-time-budget=8000", "--dump-dom", url]
        if runner:
            return runner(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        chunks: list[bytes] = []
        done = threading.Event()

        def pump():
            try:
                for chunk in iter(lambda: proc.stdout.read1(65536), b""):
                    chunks.append(chunk)
                    if b"</html>" in chunk[-200:].lower():
                        break
            finally:
                done.set()

        threading.Thread(target=pump, daemon=True).start()
        done.wait(hard_timeout)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        text = b"".join(chunks).decode("utf-8", "replace")
        if len(text.strip()) < 200:
            raise urllib.error.URLError("chrome produced no DOM")
        return 200, text

    return transport


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
                 block_pause: float = 600.0, max_block_streak: int = 2, give_up: bool = False,
                 block_pause_cap: float = 3600.0, max_interval: float = 30.0, throttle_pause: float = 20.0,
                 transport=None, sleep=time.sleep, clock=time.monotonic, user_agent: str | None = None):
        self.jar = http.cookiejar.CookieJar()
        self.transport = transport or _urllib_transport(self.jar)
        # Amazon pages through Chrome when it is installed (see chrome_binary);
        # an injected transport (tests) is used for every host.
        chrome = chrome_binary() if transport is None else None
        self.amazon_transport = _chrome_transport(chrome) if chrome else None
        self.client = "chrome" if chrome else "urllib"
        self.min_interval, self.jitter, self.timeout = min_interval, jitter, timeout
        self.block_pause, self.max_block_streak = block_pause, max_block_streak
        # give_up=True raises Blocked at max_block_streak (the original "stop
        # for the day"). The founder's rule since 2026-09-03 is that the crawl
        # never stops: give_up=False backs off 10 → 20 → 40 → 60 min, slows the
        # pace for the rest of the run, and carries on when Amazon relents.
        self.give_up, self.block_pause_cap, self.max_interval = give_up, block_pause_cap, max_interval
        self.throttle_pause = throttle_pause  # other hosts (web.archive.org, Bing): 429/503 → wait once, retry once
        self.sleep, self.clock = sleep, clock
        self.ua = user_agent or random.choice(USER_AGENTS)
        self._last: dict[str, float] = {}
        self.block_streak = 0
        self.stats = {"requests": 0, "ok": 0, "missing": 0, "errors": 0, "blocked": 0, "throttled": 0, "chars": 0}

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
        transport = self.amazon_transport if (self.amazon_transport and "amazon." in host) else self.transport
        for attempt in (1, 2):
            try:
                status, text = transport(url, hdrs, self.timeout)
                break
            except urllib.error.HTTPError as err:
                if err.code in (429, 503) and "amazon." in host:
                    return self._blocked(url)
                if err.code in (429, 503) and attempt == 1:
                    self.stats["throttled"] += 1
                    self.sleep(self.throttle_pause)
                    continue
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
        if self.give_up and self.block_streak >= self.max_block_streak:
            raise Blocked(f"Amazon answered {self.block_streak} requests in a row with a captcha ({url}); "
                          "stopping for today.")
        pause = min(self.block_pause_cap, self.block_pause * (2 ** (self.block_streak - 1)))
        self.min_interval = min(self.max_interval, self.min_interval * 1.5)
        self.stats["backoff_seconds"] = self.stats.get("backoff_seconds", 0) + pause
        print(f"  captcha #{self.block_streak} on {url}: waiting {pause / 60:.0f} min, "
              f"then {self.min_interval:.0f}–{self.min_interval + self.jitter:.0f} s between requests", flush=True)
        self.sleep(pause)
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
