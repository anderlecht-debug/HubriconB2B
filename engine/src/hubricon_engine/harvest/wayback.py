"""Archived seller profiles: the Wayback Machine as a seller database.

The Internet Archive holds captures of amazon.com/sp?seller=<id> — about
1,800 distinct sellers captured since the September 2020 rule that made every
professional seller publish a business name and address. One request to
web.archive.org returns what the live crawl needs a dozen Amazon requests
for: the storefront name, the legal name and address, the country, and the
seller-feedback counts that size the account. Amazon is never asked, so
there is no captcha budget to spend and the crawl can run at any hour.

The price is staleness: a capture may be years old, so the storefront name
stands in for the brand, the size estimate comes from the feedback count at
capture time, and the row still has to earn a live website and a contact
address in `enrich` before it is pushed. Instantly verifies on import.

  captures   CDX index → seller_id → newest usable capture (captcha stubs are ~2 KB)
  crawl      captures → archived profile → classify → harvest_sellers rows (source 'wayback')
"""

from __future__ import annotations

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import amazon
from .fetch import BLOCK_MARKERS, Fetcher
from .run import _log_event, classify, seller_row

CDX = ("https://web.archive.org/cdx/search/cdx?url=amazon.com/sp?seller=*&from=2021"
       "&filter=statuscode:200&filter=mimetype:text/html&fl=original,timestamp,length")
SNAPSHOT = "https://web.archive.org/web/{ts}id_/{url}"  # id_: the original bytes, no toolbar
MIN_CAPTURE_BYTES = 30_000  # a real profile is 60–120 KB; Amazon's captcha stub is ~2 KB
LIMIT = 400          # sellers per run; ~1,800 exist, so a week of nightly runs reads them all
WORKERS = 3          # parallel fetchers; each paces itself, ~2 requests a second in total
SELLER_RE = re.compile(r"[?&]seller=([A-Z0-9]{10,16})", re.I)
DEFAULT_CDX_FILE = Path.home() / ".hubricon" / "harvest" / "wayback-sellers.cdx"


def parse_cdx(text: str) -> dict[str, tuple[str, str]]:
    """CDX lines (original, timestamp, length) → seller_id → (timestamp, url) of
    the newest usable capture. The plain profile beats the shipping-rates tab
    of the same page; stubs under MIN_CAPTURE_BYTES are captchas."""
    best: dict[str, tuple[tuple, str, str]] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3 or not parts[2].isdigit():
            continue
        url, ts, length = parts[0], parts[1], int(parts[2])
        m = SELLER_RE.search(url)
        if not m or length < MIN_CAPTURE_BYTES or not ts[:4].isdigit() or ts < "2021":
            continue
        sid = m.group(1).upper()
        key = ("sshmPath" not in url, ts)
        if sid not in best or key > best[sid][0]:
            best[sid] = (key, ts, url)
    return {sid: (ts, url) for sid, (_, ts, url) in best.items()}


def download_cdx(fetcher: Fetcher, log=print) -> str:
    """Every index page of the query (the server splits by index block, so a
    page holds a few dozen matching rows). About 35 pages, 5–10 s each."""
    count = fetcher.get(CDX + "&showNumPages=true")
    pages = int(count.strip()) if count and count.strip().isdigit() else 0
    log(f"wayback: {pages} CDX index pages of archived seller profiles")
    chunks = []
    for i in range(pages):
        text = fetcher.get(f"{CDX}&page={i}")
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def load_captures(fetcher: Fetcher, cdx_file: Path | None = None, log=print) -> dict[str, tuple[str, str]]:
    """The capture list, from disk when it was saved, else downloaded and saved."""
    path = Path(cdx_file) if cdx_file else DEFAULT_CDX_FILE
    if path.exists():
        return parse_cdx(path.read_text())
    text = download_cdx(fetcher, log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return parse_cdx(text)


def profile_from_capture(fetcher: Fetcher, ts: str, url: str) -> dict | None:
    page = fetcher.get(SNAPSHOT.format(ts=ts, url=url))
    if not page or any(m in page for m in BLOCK_MARKERS):
        return None
    prof = amazon.seller(page)
    if not prof.get("business_name") and not prof.get("seller_name"):
        return None
    prof["captured_at"] = ts
    return prof


def classify_profile(sid: str, prof: dict) -> tuple[str, str, dict]:
    """A profile-only seller: the storefront name stands in for the brand, so
    the private-label test is moot and the account is sized by its feedback."""
    name = prof.get("seller_name") or prof.get("business_name")
    agg = {"seller_id": sid, "seller_name": prof.get("seller_name"), "brand": name, "brands": [name] if name else [],
           "asins": [], "reviews_max": 0, "top_bsr": None, "top_category": None}
    if prof.get("ratings_12mo") is None and prof.get("country") in (None, "US"):
        return "skip_size", "no feedback count on the archived profile", agg
    status, note = classify(agg, prof)
    if status == "candidate":
        note = f"storefront name as brand; {prof.get('ratings_12mo'):,} seller ratings in 12 months"
    return status, note, agg


def crawl(db, captures: dict[str, tuple[str, str]], limit: int = LIMIT, workers: int = WORKERS,
          fetcher_factory=None, log=print) -> dict:
    """Newest captures first, sellers not yet on file, `limit` of them, read by
    `workers` fetchers in parallel. Rows are upserted per hundred so a killed
    run keeps what it read."""
    fetcher_factory = fetcher_factory or (lambda: Fetcher(min_interval=1.0, jitter=1.0, timeout=90))
    existing = {r["seller_id"] for r in db.table("harvest_sellers").select("seller_id").execute().data}
    todo = [(sid, ts, url) for sid, (ts, url) in sorted(captures.items(), key=lambda kv: kv[1][0], reverse=True)
            if sid not in existing][:limit]
    log(f"wayback: {len(captures)} archived sellers, {len(todo)} not yet on file, reading {len(todo)}")
    summary: dict = {"captures": len(captures), "read": 0, "unreadable": 0, "statuses": {}}
    counts: Counter = Counter()
    rows: list[dict] = []

    def work(chunk: list[tuple[str, str, str]]) -> list[dict]:
        fetcher = fetcher_factory()
        out = []
        for sid, ts, url in chunk:
            prof = profile_from_capture(fetcher, ts, url)
            if prof is None:
                out.append({"seller_id": sid, "_unreadable": True})
                continue
            status, note, agg = classify_profile(sid, prof)
            row = seller_row(sid, agg, prof, status, f"archived profile {ts[:8]}; {note}", source="wayback",
                             est_monthly_revenue=amazon.revenue_from_ratings(prof.get("ratings_12mo")))
            out.append(row)
        return out

    n = max(1, min(workers, len(todo)))
    chunks = [todo[i::n] for i in range(n)]
    with ThreadPoolExecutor(max_workers=n) as pool:
        for result in pool.map(work, chunks):
            for row in result:
                if row.get("_unreadable"):
                    summary["unreadable"] += 1
                    continue
                rows.append(row)
                counts[row["status"]] += 1
                summary["read"] += 1
    for i in range(0, len(rows), 100):
        db.table("harvest_sellers").upsert(rows[i:i + 100], on_conflict="seller_id").execute()
    summary["statuses"] = dict(counts)
    note = (f"wayback: {summary['read']} archived profiles read ({summary['unreadable']} unreadable), "
            + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    log(note)
    _log_event(db, note, summary)
    return summary
