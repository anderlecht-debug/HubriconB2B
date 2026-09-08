"""The passes, in order, and the one place that writes to the database.

    discover  ->  qualify  ->  contact  ->  sheet / push  ->  promote

Each pass reads the rows the previous one left and writes back the columns it
owns, so a run that dies halfway keeps its work and the next one picks up. The
same reason the harvest writes per store rather than per run.

`promote` is the seam with the rest of the machine: it copies a qualified,
contactable prospect into `harvest_sellers` at status `candidate`, where
`cold/sources/harvest.py` can build a teardown from it. `candidate` is chosen
deliberately — `harvest/run.py::push` selects `enriched` rows and pushes them
into the auto-enrolled Instantly list, so a promoted row must not wear that
status. It is fence 4 from `push.py`, enforced on the other side of the wall.

Runs on the Mac, like the harvest, and for a smaller reason: nothing here is
adversarial (Shopify is not Amazon), but the Mac is where the Chrome fallback
and the DNS resolver live and where a long pass can take its time.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..harvest import shopify as shopify_harvest
from . import catalog as catalogmod
from . import contact as contactmod
from . import discover as discovermod
from . import push as pushmod
from . import score as scoremod
from . import sheet as sheetmod

TABLE = "sourcing_prospects"
DISCOVER_LIMIT = int(os.environ.get("SOURCING_DISCOVER_LIMIT", "2000"))
QUALIFY_LIMIT = int(os.environ.get("SOURCING_QUALIFY_LIMIT", "200"))
CONTACT_LIMIT = int(os.environ.get("SOURCING_CONTACT_LIMIT", "60"))
PROMOTE_LIMIT = int(os.environ.get("SOURCING_PROMOTE_LIMIT", "40"))
RUN_HOURS = (7, 19)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_event(db, note: str, payload: dict) -> None:
    try:
        db.table("funnel_events").insert(
            {"kind": "sourcing", "note": note, "payload": payload}).execute()
    except Exception as err:  # the log must never stop the run
        print(f"  (could not log sourcing event: {err})", file=sys.stderr)


def all_rows(db, table: str, columns: str = "*", page: int = 1000,
             filters: dict | None = None) -> list[dict]:
    """Every row, paged. PostgREST caps a response at 1,000 and says nothing
    about it — `harvest/run.py` records a morning where the digest read
    "1000 sellers" against a table holding 1,837."""
    out: list[dict] = []
    start = 0
    while True:
        q = db.table(table).select(columns)
        for key, value in (filters or {}).items():
            q = q.eq(key, value)
        rows = q.range(start, start + page - 1).execute().data
        out.extend(rows)
        if len(rows) < page:
            return out
        start += page


# What a contact pass is allowed to write. Every one of these is a column on
# sourcing_prospects; anything `contact.resolve` learns that is not here is
# deliberately not persisted.
CONTACT_FIELDS = ("email", "email_confidence", "role_inbox", "first_name", "last_name",
                  "contact_source", "linkedin_url", "business_name", "address",
                  "city", "state", "status", "note")


def _cursor(db) -> int:
    """The rank the last pass reached, or the start of the window."""
    from ..outbound import get_state

    try:
        got = get_state(db, discovermod.CURSOR_KEY)
    except Exception:      # noqa: BLE001 - a missing state row is not an error
        got = None
    at = int(got or 0)
    # Past the end of the window, start again: the list is rebuilt daily and a
    # store that was not there in March is there in September.
    if at < discovermod.RANK_FROM or at >= discovermod.RANK_TO:
        return discovermod.RANK_FROM
    return at


def _set_cursor(db, rank: int, log=print) -> None:
    from ..outbound import set_state

    try:
        set_state(db, discovermod.CURSOR_KEY, rank)
        log(f"  next pass resumes at rank {rank:,}")
    except Exception as err:  # noqa: BLE001 - losing the cursor costs a repeat, not the run
        print(f"  (could not save the tranco cursor: {err})", file=sys.stderr)


def _upsert(db, rows: list[dict]) -> int:
    """A discovery pass writes every DNS hit at once — over a thousand of them
    on a good slice — so this goes through `db.chunked_upsert` rather than one
    enormous PostgREST call."""
    if not rows:
        return 0
    from .. import db as dbmod

    return dbmod.chunked_upsert(db, TABLE, rows, "domain")


def _update(db, domain: str, **fields) -> None:
    fields["updated_at"] = _now()
    db.table(TABLE).update(fields).eq("domain", domain).execute()


# -- discover ----------------------------------------------------------------------

def discover(db, fetcher, limit: int = DISCOVER_LIMIT, resolver=None, opener=None,
             log=print, source: str = "tranco", search_fetcher=None,
             cache_dir: Path | None = None) -> dict:
    """New domains into the table. Existing rows are left exactly as they are."""
    found: list[dict] = []
    if source in ("tranco", "both"):
        # Where the last run stopped. The ranking is stable enough day to day
        # that walking it once is walking it; without the cursor every run
        # re-probes the same slice and the lane never reaches the ranks where
        # the stores actually are.
        cursor = _cursor(db)
        rows, reached = discovermod.discover(fetcher, limit=limit, resolver=resolver,
                                             opener=opener, log=log, cache_dir=cache_dir,
                                             rank_from=cursor)
        found += rows
        _set_cursor(db, reached, log=log)
    if source in ("search", "both"):
        found += discovermod.discover_search(
            search_fetcher or shopify_harvest.archive_fetcher(), fetcher, log=log)

    known = {r["domain"] for r in all_rows(db, TABLE, "domain")}
    fresh = []
    for row in found:
        if row["domain"] in known:
            continue
        meta = row.pop("meta", None) or {}
        fresh.append({
            "domain": row["domain"], "myshopify_handle": row.get("myshopify_handle"),
            "brand": meta.get("name"), "tranco_rank": row.get("tranco_rank"),
            "is_shopify": True, "detected_via": row.get("detected_via"),
            "city": meta.get("city"), "state": meta.get("province"),
            "country": meta.get("country"), "currency": meta.get("currency"),
            "status": row.get("status") or "discovered", "note": row.get("note"),
            "first_seen": _now(), "updated_at": _now(),
        })
    written = _upsert(db, fresh)
    log(f"discover: {written} new domain(s), {len(found) - written} already on file")
    _log_event(db, "discover", {"found": len(found), "new": written, "source": source})
    return {"found": len(found), "new": written}


# -- qualify -----------------------------------------------------------------------

def qualify(db, fetcher, limit: int = QUALIFY_LIMIT, log=print, today=None) -> dict:
    """Catalogue, stack and score for rows that have none yet."""
    from . import stack as stackmod

    rows = [r for r in all_rows(db, TABLE) if r.get("status") == "discovered"]
    rows.sort(key=lambda r: (r.get("tranco_rank") is None, r.get("tranco_rank") or 10 ** 9))
    rows = rows[:limit]
    counts = {"looked": len(rows), "qualified": 0, "disqualified": 0, "no_catalog": 0}
    for row in rows:
        domain = row["domain"]
        handle = row.get("myshopify_handle")
        meta = None
        if not handle:
            # Discovered by DNS and never probed — `discover` records every hit
            # and only spends HTTP on the first `limit` of them.
            handle, meta = discovermod.fingerprint_http(fetcher, domain)
            meta = meta or {}
            if handle:
                _update(db, domain, myshopify_handle=handle,
                        brand=row.get("brand") or meta.get("name"),
                        city=meta.get("city"), state=meta.get("province"),
                        country=meta.get("country"), currency=meta.get("currency"))
                row.update(myshopify_handle=handle, brand=row.get("brand") or meta.get("name"),
                           country=meta.get("country"), currency=meta.get("currency"))
        # The country is the cheapest disqualifier there is and it goes first,
        # before a single catalogue page is read. Skipping it scored
        # oglmove.com — a Hong Kong store — at 76 on 2026-09-07 and then spent
        # a whole contact pass on a company we can never write to.
        if row.get("country") or row.get("currency"):
            bad, why = shopify_harvest.classify_meta(
                {"country": row.get("country"), "currency": row.get("currency")})
            if bad:
                _update(db, domain, status="disqualified", note=why)
                counts["disqualified"] += 1
                log(f"  {domain}: disqualified — {why}")
                continue
        got = catalogmod.read(fetcher, domain, handle)
        if not got["products"]:
            _update(db, domain, status="disqualified",
                    note="no catalogue published at /products.json")
            counts["no_catalog"] += 1
            continue
        stack = stackmod.read(fetcher, domain)
        vendors = shopify_harvest.vendor_profile(got["products"])
        ladder, disc = got["ladder"], got["discounts"]
        est_annual = _est_annual(got, row)
        status, note, total, parts = scoremod.verdict({
            "tranco_rank": row.get("tranco_rank"), "stack": stack, "vendors": vendors,
            "products": got["count"], "ladder": ladder, "velocity": got["velocity"],
            "est_annual": est_annual,
        })
        _update(
            db, domain, status=status, note=note, score=total, score_parts=parts,
            products=got["count"], asp=ladder.get("asp"), median_price=ladder.get("median"),
            # Two different numbers: how much of the shelf is marked down, and
            # how far under the anchor the marked-down part sits. A catalogue
            # 90% discounted by 3% is a rounding error; 60% discounted by 40%
            # is a business model.
            discount_share=disc.get("share"), compare_at_share=disc.get("mean_depth"),
            velocity_days=got["velocity"].get("days_since_update"),
            ladder_gap_ratio=ladder.get("gap_ratio"),
            stack=stack, plus_signals=bool(stack.get("plus")), est_annual=est_annual,
            brand=row.get("brand") or vendors.get("dominant"),
        )
        counts["qualified" if status == "qualified" else "disqualified"] += 1
        log(f"  {domain}: {status} ({total:,.0f}) — {note}")
    _log_event(db, "qualify", counts)
    return counts


def _est_annual(got: dict, row: dict) -> float | None:
    """The existing review-based estimate, over the catalogue we just read.

    Reuses `harvest/shopify.py::estimate_annual` rather than inventing a second
    size model. It is weak — OPERATIONS.md flags `ORDERS_PER_REVIEW = 50` as an
    uncalibrated guess the whole band rides on — which is exactly why `score.py`
    weights it low and the rank carries more.
    """
    products = got["products"]
    if not products:
        return None
    asp = got["ladder"].get("asp")
    age = shopify_harvest.store_age_years(products)
    # No product pages are fetched here, so there are no review counts to feed
    # it; the estimate only exists for rows a later pass enriched.
    reviews = [p.get("reviews") for p in products if p.get("reviews")]
    if not reviews:
        return None
    return shopify_harvest.estimate_annual(reviews, len(products), asp, age)


# -- contact -----------------------------------------------------------------------

def contact(db, fetcher, limit: int = CONTACT_LIMIT, log=print, search_fetcher=None) -> dict:
    """A named person and a published address, for the rows that earned it."""
    rows = [r for r in all_rows(db, TABLE) if r.get("status") == "qualified"]
    rows.sort(key=lambda r: -(r.get("score") or 0))
    rows = rows[:limit]
    counts = {"looked": len(rows), "found": 0, "pattern": 0, "none": 0, "role": 0}
    for row in rows:
        got = contactmod.resolve(fetcher, row["domain"], row.get("brand"),
                                 search_fetcher=search_fetcher, log=log)
        # Named rather than splatted: `resolve` returns what it learned about
        # the store, which is not the same set as the columns this table has,
        # and the first live pass died mid-batch on the difference.
        _update(db, row["domain"], **{k: got[k] for k in CONTACT_FIELDS})
        if got["status"] == "contacted_found":
            counts["found"] += 1
            if got["role_inbox"]:
                counts["role"] += 1
        elif got["status"] == "sheet_only":
            counts["pattern"] += 1
        else:
            counts["none"] += 1
        log(f"  {row['domain']}: {got['status']} — {got['note']}")
    _log_event(db, "contact", counts)
    return counts


# -- sinks -------------------------------------------------------------------------

def sheet(db, dry: bool = False, log=print, opener=None) -> dict:
    """Every qualified lead to the Google Sheet and the CSV.

    "Qualified" and not "sendable": a store whose only address is a role inbox
    is on the sheet with `sendable = no` and the reason, because it is still a
    brand worth a human's ninety seconds. It is `push` that refuses it.
    """
    rows = [r for r in all_rows(db, TABLE)
            if r.get("status") in ("qualified", "contacted_found", "sheet_only", "promoted")]
    rows.sort(key=lambda r: -(r.get("score") or 0))
    log(f"sheet: {len(rows)} qualified lead(s)")
    return sheetmod.sync(rows, dry=dry, log=log, opener=opener)


def push(db, api, dry: bool = False, limit: int = 200, log=print) -> dict:
    """Contactable leads into the Instantly holding pen. Nothing is sent."""
    rows = [r for r in all_rows(db, TABLE) if r.get("status") == "contacted_found"]
    rows.sort(key=lambda r: -(r.get("score") or 0))
    log(f"push: {len(rows)} contacted lead(s) on file")
    got = pushmod.push(db, api, rows, dry=dry, limit=limit, log=log)
    _log_event(db, "push", got)
    return got


# -- promote -----------------------------------------------------------------------

def promote(db, fetcher, limit: int = PROMOTE_LIMIT, log=print, resolver=None) -> dict:
    """Sourced prospects into `harvest_sellers`, so the cold engine can see them.

    The store is re-read through `harvest/shopify.py::read_store` rather than
    translated out of our own columns: that function is what produces the row
    shape the whole downstream expects, review counts and all, and reproducing
    it here would be a second implementation to keep in step.

    Two rules about the status, and the first live run got the second wrong.

    A row never lands at `enriched`: `harvest/run.py::push` selects exactly that
    status and pushes it into the auto-enrolled Instantly list, so an `enriched`
    promotion would be cold-emailed by the hourly operator with nobody having
    approved it. Anywhere on the pipeline becomes `candidate`.

    But a *skip* is a verdict, not a status to be overwritten. The first version
    wrote `candidate` unconditionally and promoted Boston Scally, which
    `read_store` had just rejected as a multi-brand catalogue — laundering a
    reseller into the prospect table on this package's own say-so. A skip is
    recorded against the sourcing row and the store is not promoted.
    """
    rows = [r for r in all_rows(db, TABLE)
            if r.get("status") == "contacted_found" and r.get("myshopify_handle")]
    rows.sort(key=lambda r: -(r.get("score") or 0))
    rows = rows[:limit]
    counts = {"looked": len(rows), "promoted": 0, "skipped": 0}
    for row in rows:
        handle = row["myshopify_handle"]
        got = shopify_harvest.read_store(fetcher, handle, resolver=resolver)
        if not got.get("meta"):
            _update(db, row["domain"], note=f"promote: {got.get('note')}")
            counts["skipped"] += 1
            continue
        verdict = got.get("status") or "candidate"
        if verdict not in shopify_harvest.PIPELINE:
            # read_store rejected it — non-US, a reseller, past the ceiling.
            # Its judgement is the one the cold engine trusts, so it stands.
            _update(db, row["domain"], status="disqualified",
                    note=f"promote: {verdict} — {got.get('note')}")
            counts["skipped"] += 1
            log(f"  skip {row['domain']}: {verdict} — {got.get('note')}")
            continue
        seller = shopify_harvest.store_row(
            handle, got["meta"], got["products"], got["sampled"], got["vendors"],
            got["est_annual"], got["contact"], "candidate", got["note"])
        seller["source"] = "sourcing"
        # What this package found beats what the re-read guessed: the contact
        # pass is the one that applied the published-only rule.
        if row.get("email_confidence") == "published":
            seller.update(email=row["email"], email_confidence="published",
                          first_name=row.get("first_name"), last_name=row.get("last_name"),
                          person_source=row.get("contact_source"))
        db.table("harvest_sellers").upsert([seller], on_conflict="seller_id").execute()
        products = shopify_harvest.catalogue_rows(row["domain"], seller["seller_id"], got)
        products = _with_compare_at(fetcher, row, products)
        if products:
            db.table("harvest_products").upsert(products, on_conflict="asin").execute()
            _keep_history(db, products, log)
        counts["promoted"] += 1
        log(f"  promoted {row['domain']} -> {seller['seller_id']} (candidate)")
    _log_event(db, "promote", counts)
    return counts


def _with_compare_at(fetcher, row: dict, products: list[dict]) -> list[dict]:
    """Put the anchor price back on the rows `catalogue_rows` builds.

    `harvest/shopify.py::product_row` predates the `permanent_discount`
    detector and does not carry `compare_at_price`; rather than edit that file
    — another session is in it — the catalogue is re-read here through
    `catalog.parse_catalog`, which keeps the field, and the two are joined on
    the product handle. The endpoint is cached by the fetcher, so this is not a
    second round trip in practice.
    """
    if not products:
        return products
    got = catalogmod.read(fetcher, row["domain"], row.get("myshopify_handle"))
    anchors = {p["handle"]: p.get("compare_at") for p in got["products"] if p.get("compare_at")}
    if not anchors:
        return products
    for product in products:
        handle = (product.get("asin") or "").rsplit("/products/", 1)[-1]
        product["compare_at_price"] = anchors.get(handle)
    return products


def _keep_history(db, product_rows: list[dict], log=print) -> None:
    """Price history, appended on every pass. It cannot be recovered later."""
    from ..cold.run import record_observations

    try:
        record_observations(db, product_rows, log=log)
    except Exception as err:  # history must never cost the run its real work
        print(f"  (could not record observations: {err})", file=sys.stderr)


# -- the whole run -----------------------------------------------------------------

def run_all(db, fetcher=None, api=None, dry: bool = False, limit: int | None = None,
            log=print, source: str = "tranco", resolver=None) -> dict:
    """One scheduled pass: discover, qualify, contact, sheet, push."""
    from .fetch import dual_fetcher

    fetcher = fetcher or dual_fetcher()
    out: dict = {}
    out["discover"] = discover(db, fetcher, limit=limit or DISCOVER_LIMIT,
                               resolver=resolver, log=log, source=source)
    out["qualify"] = qualify(db, fetcher, log=log)
    out["contact"] = contact(db, fetcher, log=log)
    out["sheet"] = sheet(db, dry=dry, log=log)
    out["push"] = push(db, api, dry=dry, log=log)
    if getattr(fetcher, "summary", None):
        log(f"fetch: {fetcher.summary()}")
    return out


# -- status ------------------------------------------------------------------------

def status(db) -> dict:
    rows = all_rows(db, TABLE, "domain,status,score,email_confidence,role_inbox,tranco_rank")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.get("status") or "?"] = by_status.get(r.get("status") or "?", 0) + 1
    sendable = sum(1 for r in rows
                   if r.get("email_confidence") == "published" and not r.get("role_inbox"))
    return {"total": len(rows), "by_status": by_status, "sendable": sendable,
            "role_inbox": sum(1 for r in rows if r.get("role_inbox")),
            "pattern": sum(1 for r in rows if r.get("email_confidence") == "pattern")}


def status_text(db) -> str:
    s = status(db)
    lines = [f"{s['total']:,} domains on file"]
    for name, count in sorted(s["by_status"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {name:<18} {count:>6,}")
    lines += [
        "",
        f"  {'sendable':<18} {s['sendable']:>6,}  published address, named person",
        f"  {'role inbox':<18} {s['role_inbox']:>6,}  sheet only, founder lane",
        f"  {'pattern':<18} {s['pattern']:>6,}  guessed, never sent to",
    ]
    return "\n".join(lines)


# -- launchd -----------------------------------------------------------------------

def launchd_plist(engine_dir: Path, uv: str = "/opt/homebrew/bin/uv",
                  hours: tuple[int, ...] = RUN_HOURS, minute: int = 40) -> dict:
    log_dir = Path.home() / "Library" / "Logs"
    return {
        "Label": "com.hubricon.sourcing",
        "ProgramArguments": [uv, "run", "hubricon", "source", "all"],
        "WorkingDirectory": str(engine_dir),
        "StartCalendarInterval": [{"Hour": h, "Minute": minute} for h in hours],
        "StandardOutPath": str(log_dir / "hubricon-sourcing.log"),
        "StandardErrorPath": str(log_dir / "hubricon-sourcing.err"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
                                 "PYTHONUNBUFFERED": "1"},
    }


def install_launchd(engine_dir: Path | None = None, hours: tuple[int, ...] = RUN_HOURS,
                    minute: int = 40, runner=subprocess.run) -> str:
    """Its own label and its own hours, half an hour off the harvest's so the
    two are never competing for Chrome on the same machine."""
    engine_dir = engine_dir or Path(__file__).resolve().parents[3]
    uv = subprocess.run(["which", "uv"], capture_output=True, text=True).stdout.strip() \
        or "/opt/homebrew/bin/uv"
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.hubricon.sourcing.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(plistlib.dumps(launchd_plist(engine_dir, uv, hours, minute)))
    domain = f"gui/{os.getuid()}"
    runner(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
    res = runner(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
    state = "loaded" if res.returncode == 0 else f"launchctl said: {(res.stderr or res.stdout).strip()}"
    when = " and ".join(f"{h:02d}:{minute:02d}" for h in hours)
    return (f"{plist_path}\n  runs `uv run hubricon source all` daily at {when} local; "
            f"logs in ~/Library/Logs/hubricon-sourcing.log\n  {state}")


def calibrate(db, path: Path, log=print) -> str:
    """Hand-labelled stores against their scores. See score.calibrate."""
    import csv as csvmod

    labels: dict[str, bool] = {}
    with Path(path).open(newline="") as fh:
        for row in csvmod.DictReader(fh):
            domain = (row.get("domain") or "").strip().lower()
            if domain:
                labels[domain] = (row.get("good") or "").strip().lower() in ("1", "y", "yes", "true")
    scored = {r["domain"]: r.get("score") for r in all_rows(db, TABLE, "domain,score")}
    missing = [d for d in labels if d not in scored]
    rows = [{"domain": d, "score": scored.get(d), "good": good}
            for d, good in labels.items() if scored.get(d) is not None]
    out = scoremod.calibrate(rows)
    if missing:
        out += (f"\n\n{len(missing)} labelled domain(s) have no score yet — run "
                f"`hubricon source qualify` over them first: {', '.join(missing[:8])}"
                + (" …" if len(missing) > 8 else ""))
    return out
