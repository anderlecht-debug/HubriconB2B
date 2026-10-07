"""The network under sourcing: one polite client, a 24-hour cache, a request
counter per film and a rate limiter that sleeps rather than exceed a library's
limit (VISUAL_SPEC.md §6.3).

Pexels allows 200 requests an hour and 20,000 a month; Pixabay allows 100 a
minute and asks that every response be cached for 24 hours; the Library of
Congress, Wikimedia Commons and the Internet Archive ask automated readers to
say who they are. So every request goes through `Net`: it answers from
content/.cache/api/ when it can, waits its turn when it must, counts what it
spent in the film's sources/requests.json, and never writes a key anywhere.
Keys travel in a header or in a parameter that is stripped before anything is
cached, counted or raised, and a response that echoes a key has it removed
before it is stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

from ..state import CONTENT_DIR

CACHE = CONTENT_DIR / ".cache"
API_CACHE = CACHE / "api"
ASSET_CACHE = CACHE / "assets"
TTL = 24 * 3600                       # Pixabay's rule, applied to every source
# (requests, seconds): the published limits, and a polite pace where none is published.
LIMITS = {"pexels": (200, 3600.0), "pixabay": (100, 60.0), "loc": (15, 15.0), "smithsonian": (1000, 3600.0),
          "commons": (20, 10.0), "archive": (15, 10.0), "nara": (15, 10.0)}
FILE_LIMITS = {"loc": (10, 10.0), "commons": (10, 10.0), "archive": (5, 10.0), "nara": (5, 10.0),
               "smithsonian": (10, 10.0)}
MONTHLY = {"pexels": 20000}
FILM_BUDGET = {"pexels": 150}         # §6.3: a 40-minute film stays under 150 Pexels requests
RETRIES = 3


class SourceError(Exception):
    """A request that failed. The message never carries a URL, so it never carries a key."""


class Blocked(Exception):
    """The step cannot go on: a missing key, or an allowance spent. Names which."""


class BudgetSpent(Blocked):
    """This film has spent its share of a library (FILM_BUDGET); other shots go on without it."""


def env(name: str) -> str | None:
    return (os.environ.get(name) or "").strip() or None


def user_agent() -> str:
    email = env("CONTENT_CONTACT_EMAIL")
    return f"Hubricon/1.0 (+{email})" if email else "Hubricon/1.0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Limiter:
    """A sliding window per source, kept on disk so a resumed run still respects
    the hour. `wait` sleeps until a request may go; nothing is ever sent early."""

    def __init__(self, path: Path, clock=time.time, sleep=time.sleep, limits=None, monthly=None):
        self.path, self.clock, self.sleep = Path(path), clock, sleep
        self.limits = {**LIMITS, **{f"{k}:files": v for k, v in FILE_LIMITS.items()}, **(limits or {})}
        self.monthly = MONTHLY if monthly is None else monthly
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state), encoding="utf-8")

    def wait(self, source: str) -> float:
        """Block until `source` may send one more request; returns the seconds slept."""
        st = self.state.setdefault(source, {"times": []})
        slept = 0.0
        hold = float(st.get("until") or 0) - self.clock()
        if hold > 0:
            self.sleep(hold)
            slept += hold
        if source in self.limits:
            n, window = self.limits[source]
            now = self.clock()
            times = [t for t in st["times"] if now - t < window]
            if len(times) >= n:
                pause = window - (now - times[-n]) + 0.05
                self.sleep(pause)
                slept += pause
                now = self.clock()
                times = [t for t in times if now - t < window]
            st["times"] = times + [now]
        month = datetime.fromtimestamp(self.clock(), timezone.utc).strftime("%Y-%m")
        if st.get("month") != month:
            st["month"], st["month_count"] = month, 0
        if source in self.monthly and st["month_count"] >= self.monthly[source]:
            raise Blocked(f"{source}: this month's {self.monthly[source]:,} requests are spent; the allowance resets on the 1st")
        st["month_count"] += 1
        self._save()
        return slept

    def hold(self, source: str, until: float) -> None:
        """The server said when to come back (Retry-After, a rate-limit reset)."""
        self.state.setdefault(source, {"times": []})["until"] = until
        self._save()


class Net:
    """One sourcing run's connection to the libraries: cache, limiter and counter."""

    def __init__(self, film_dir: Path | None = None, clock=time.time, sleep=time.sleep, http=None,
                 cache_dir: Path = API_CACHE, asset_dir: Path = ASSET_CACHE, limits=None, budget=None):
        self.film_dir = Path(film_dir) if film_dir else None
        self.clock, self.sleep = clock, sleep
        self.cache_dir, self.asset_dir = Path(cache_dir), Path(asset_dir)
        self.limiter = Limiter(self.cache_dir / "ratelimit.json", clock=clock, sleep=sleep, limits=limits)
        self.budget = FILM_BUDGET if budget is None else budget
        self._http = http
        self.run: dict[str, dict] = {}          # since the last save
        self.session: dict[str, dict] = {}      # this process, for the summary
        self.slept = 0.0
        self.prior = self._read_counts().get("by_source", {})

    # ── the counter ──
    @property
    def counts_path(self) -> Path | None:
        return self.film_dir / "sources" / "requests.json" if self.film_dir else None

    def _read_counts(self) -> dict:
        p = self.counts_path
        if p and p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                return {}
        return {}

    def _count(self, source: str, field: str, n: int = 1) -> None:
        for book in (self.run, self.session):
            book.setdefault(source, {"requests": 0, "cached": 0, "downloads": 0, "bytes": 0})[field] += n

    def spent(self, source: str) -> int:
        """API requests this film has sent to `source`, this run included."""
        return int(self.prior.get(source, {}).get("requests", 0)) + self.run.get(source, {}).get("requests", 0)

    def save_counts(self) -> dict:
        """Fold this run into the film's requests.json; returns the totals."""
        p = self.counts_path
        if not p:
            return {}
        doc = self._read_counts()
        totals = doc.get("by_source", {})
        for src, row in self.run.items():
            t = totals.setdefault(src, {"requests": 0, "cached": 0, "downloads": 0, "bytes": 0})
            for k, v in row.items():
                t[k] = t.get(k, 0) + v
        runs = (doc.get("runs") or []) + [{"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                                           "by_source": self.run, "slept_s": round(self.slept, 1)}]
        doc = {"by_source": totals, "runs": runs[-50:],
               "note": "API requests sent per source for this film (cached answers are not requests); VISUAL_SPEC.md §6.3"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        self.prior, self.run = totals, {}
        return totals

    # ── requests ──
    @property
    def http(self):
        if self._http is None:
            import requests
            self._http = requests.Session()
        return self._http

    def _key(self, source: str, url: str, public: dict) -> str:
        blob = json.dumps([source, url, sorted((k, str(v)) for k, v in public.items())])
        return hashlib.sha256(blob.encode()).hexdigest()

    def cached(self, source: str, url: str, params: dict | None = None, secret=()) -> dict | None:
        public = {k: v for k, v in (params or {}).items() if k not in secret}
        p = self.cache_dir / source / f"{self._key(source, url, public)}.json"
        if p.exists():
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                return None
            if self.clock() - float(doc.get("at", 0)) < TTL:
                return doc
        return None

    def _send(self, source: str, url: str, params=None, headers=None, stream=False, limiter_key=None):
        """One GET under the limiter, retried on 429 and 5xx. Errors never carry the URL."""
        headers = {"User-Agent": user_agent(), **(headers or {})}
        for attempt in range(RETRIES):
            self.slept += self.limiter.wait(limiter_key or source)
            try:
                r = self.http.get(url, params=params, headers=headers, timeout=60, stream=stream)
            except Exception as e:                                    # requests' messages carry the URL
                if attempt == RETRIES - 1:
                    raise SourceError(f"{source}: {type(e).__name__} (no response)") from None
                continue
            status = int(getattr(r, "status_code", 0))
            if status == 429 or status >= 500:
                wait = _retry_after(r, default=30.0 if status == 429 else 5.0 * (attempt + 1))
                if attempt == RETRIES - 1:
                    raise SourceError(f"{source}: HTTP {status}")
                self.limiter.hold(limiter_key or source, self.clock() + wait)
                continue
            if status >= 400:
                raise SourceError(f"{source}: HTTP {status}")
            if source == "pexels":
                _pexels_reset(self.limiter, r)
            return r
        raise SourceError(f"{source}: no response")

    def get_json(self, source: str, url: str, params: dict | None = None, headers: dict | None = None,
                 secret=()) -> dict:
        """A JSON answer, from the 24-hour cache when it is there. `secret` names the
        parameters that carry a key: they are sent, never cached and never counted."""
        params = dict(params or {})
        public = {k: v for k, v in params.items() if k not in secret}
        hit = self.cached(source, url, params, secret)
        if hit is not None:
            self._count(source, "cached")
            return hit["body"]
        if source in self.budget and self.spent(source) >= self.budget[source]:
            raise BudgetSpent(f"{source}: this film has spent its {self.budget[source]} requests (§6.3)")
        r = self._send(source, url, params=params, headers=headers)
        self._count(source, "requests")
        text = r.text
        for v in [params[k] for k in secret if k in params] + list((headers or {}).values()):
            if v and len(str(v)) >= 8:
                text = text.replace(str(v), "[key]")
        try:
            body = json.loads(text)
        except ValueError:
            raise SourceError(f"{source}: the answer was not JSON") from None
        p = self.cache_dir / source / f"{self._key(source, url, public)}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"at": self.clock(), "source": source, "url": url, "params": public,
                                 "retrieved": date.today().isoformat(), "body": body}), encoding="utf-8")
        return body

    def head_bytes(self, source: str, url: str, n: int = 65536) -> bytes:
        """The first `n` bytes of a file (a TIFF's header, for its size), by a range request. A
        connection that drops is tried again; one that keeps dropping gives no bytes, so that one
        candidate goes unmeasured and a long sourcing run doesn't stop (G02, 2026-10-07)."""
        for attempt in range(3):
            try:
                return self._head_bytes(source, url, n)
            except _TRANSIENT:
                self.sleep(1.5 * (attempt + 1))
        return b""

    def _head_bytes(self, source: str, url: str, n: int) -> bytes:
        r = self._send(source, url, headers={"Range": f"bytes=0-{n - 1}"}, stream=True, limiter_key=f"{source}:files")
        self._count(source, "requests")
        buf = b""
        for chunk in (r.iter_content(1 << 14) if hasattr(r, "iter_content") else [r.content]):
            buf += chunk
            if len(buf) >= n:                 # a server that ignores the range is not read to the end
                break
        if hasattr(r, "close"):
            r.close()
        return buf[:n]

    def download(self, source: str, url: str, dest: Path) -> Path:
        """Fetch a file once into content/.cache/assets/ (download, never hotlink). A connection
        that drops mid-file is tried again, twice."""
        for attempt in range(3):
            try:
                return self._download(source, url, dest)
            except _TRANSIENT:
                if attempt == 2:
                    raise
                self.sleep(1.5 * (attempt + 1))

    def _download(self, source: str, url: str, dest: Path) -> Path:
        dest = Path(dest)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = self._send(source, url, stream=True, limiter_key=f"{source}:files")
        tmp = dest.with_name(dest.name + ".part")
        size = 0
        with tmp.open("wb") as fh:
            chunks = r.iter_content(1 << 16) if hasattr(r, "iter_content") else [r.content]
            for chunk in chunks:
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)
        if size == 0:
            tmp.unlink(missing_ok=True)
            raise SourceError(f"{source}: an empty file")
        tmp.replace(dest)
        self._count(source, "downloads")
        self._count(source, "bytes", size)
        return dest


try:   # a connection that breaks mid-transfer is worth trying again; anything else is not
    from requests.exceptions import ChunkedEncodingError, ConnectionError as _ConnError
    _TRANSIENT: tuple = (ChunkedEncodingError, _ConnError)
except ImportError:   # pragma: no cover
    _TRANSIENT = (ConnectionError,)


def _retry_after(r, default: float) -> float:
    try:
        return max(1.0, float(r.headers.get("Retry-After")))
    except (TypeError, ValueError, AttributeError):
        return default


def _pexels_reset(limiter: Limiter, r) -> None:
    """Pexels says how many requests are left and when the allowance resets."""
    try:
        if int(r.headers.get("X-Ratelimit-Remaining")) <= 0:
            limiter.hold("pexels", float(r.headers.get("X-Ratelimit-Reset")))
    except (TypeError, ValueError, AttributeError):
        pass


_default: Net | None = None


def default() -> Net:
    """The process's Net when a caller does not pass one (no film counter)."""
    global _default
    if _default is None:
        _default = Net()
    return _default
