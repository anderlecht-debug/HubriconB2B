"""Every qualified lead, in a Google Sheet and in a CSV beside it.

The Sheet is the working surface: it is where a lead is read, judged and acted
on by a person, and it is the half of this pipeline that does not need any of
the rest of the machine to be running. So it carries enough to act on a row
without opening anything else — the finding, the dollars, the teardown URL and
the reason a row is or is not sendable — rather than being a dump of the table.

**Delivery is an Apps Script web app, not the Sheets API.** A service account
would mean a GCP project, an OAuth consent screen and a JSON key on the Mac
and in the GitHub environment, to write rows to one spreadsheet. A `doPost`
bound to the sheet is fifteen lines, one URL and one shared secret, and it
works unattended from the Mac and from Actions alike. `scripts/sheet-sync.gs`
holds the script; OPERATIONS.md holds the five-minute setup.

The CSV is written every run regardless, to `~/.hubricon/sourcing/leads.csv`.
It costs nothing, it opens in Excel, and it means a webhook that is not set up
yet — or has stopped answering — never loses a run's work.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .discover import CACHE_DIR

SHEET_URL = "SOURCING_SHEET_URL"
SHEET_SECRET = "SOURCING_SHEET_SECRET"
CSV_PATH = CACHE_DIR / "leads.csv"

# The sheet's columns, in order. `scripts/sheet-sync.gs` writes this list as
# its header row on first run and keys updates on `domain`, so the two must
# agree — change them together.
COLUMNS = (
    "domain", "brand", "first_name", "last_name", "email", "email_confidence",
    "role_inbox", "sendable", "not_sendable_why", "score", "tranco_rank",
    "est_annual", "products", "asp", "median_price", "discount_share",
    "discount_depth", "ladder_gap",
    "stack", "plus", "city", "state", "linkedin_url", "finding_kind",
    "finding_low", "finding_high", "teardown_url", "status", "note", "first_seen",
)


class SheetUnavailable(RuntimeError):
    """The webhook is not configured, or did not accept the rows."""


def configured() -> bool:
    return bool(os.environ.get(SHEET_URL) and os.environ.get(SHEET_SECRET))


def as_row(prospect: dict) -> dict:
    """One `sourcing_prospects` row, flattened to the sheet's columns."""
    from .contact import sendable as may_send

    ok, why = may_send(prospect)
    stack = prospect.get("stack") or {}
    if isinstance(stack, str):
        try:
            stack = json.loads(stack)
        except ValueError:
            stack = {}
    return {
        "domain": prospect.get("domain"),
        "brand": prospect.get("brand"),
        "first_name": prospect.get("first_name"),
        "last_name": prospect.get("last_name"),
        "email": prospect.get("email"),
        "email_confidence": prospect.get("email_confidence"),
        "role_inbox": "yes" if prospect.get("role_inbox") else "",
        "sendable": "yes" if ok else "no",
        "not_sendable_why": why,
        "score": prospect.get("score"),
        "tranco_rank": prospect.get("tranco_rank"),
        "est_annual": prospect.get("est_annual"),
        "products": prospect.get("products"),
        "asp": prospect.get("asp"),
        "median_price": prospect.get("median_price"),
        "discount_share": prospect.get("discount_share"),
        "discount_depth": prospect.get("compare_at_share"),
        "ladder_gap": prospect.get("ladder_gap_ratio"),
        "stack": ", ".join(stack.get("apps") or []) if isinstance(stack, dict) else "",
        "plus": "yes" if (isinstance(stack, dict) and stack.get("plus")) else "",
        "city": prospect.get("city"),
        "state": prospect.get("state"),
        "linkedin_url": prospect.get("linkedin_url"),
        "finding_kind": prospect.get("finding_kind"),
        "finding_low": prospect.get("finding_low"),
        "finding_high": prospect.get("finding_high"),
        "teardown_url": prospect.get("teardown_url"),
        "status": prospect.get("status"),
        "note": prospect.get("note"),
        "first_seen": prospect.get("first_seen"),
    }


def write_csv(rows: list[dict], path: Path | None = None) -> Path:
    """The offline copy. Always written, whether or not the webhook is set up."""
    out = Path(path) if path else CSV_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out


def post(rows: list[dict], url: str | None = None, secret: str | None = None,
         opener=None, timeout: int = 60) -> dict:
    """Send the rows to the Apps Script web app. Upserts on `domain` there."""
    url = url or os.environ.get(SHEET_URL)
    secret = secret or os.environ.get(SHEET_SECRET)
    if not url or not secret:
        raise SheetUnavailable(
            f"{SHEET_URL} and {SHEET_SECRET} are not set — see OPERATIONS.md for the "
            "five-minute Apps Script setup. The CSV was still written.")
    body = json.dumps({"secret": secret, "columns": list(COLUMNS), "rows": rows}).encode()
    if opener:
        return opener(url, body)
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Hubricon-sourcing/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        raise SheetUnavailable(f"the sheet webhook answered {err.code}: "
                               f"{err.read().decode('utf-8', 'replace')[:200]}") from err
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise SheetUnavailable(f"the sheet webhook could not be reached: {err}") from err
    try:
        return json.loads(raw)
    except ValueError:
        # Apps Script answers HTML when the deployment is wrong (not shared,
        # or deployed as the wrong identity), which is the common setup slip.
        raise SheetUnavailable(
            "the sheet webhook answered HTML rather than JSON — the web app is probably "
            "deployed with the wrong access setting. Redeploy it as 'Execute as: me' and "
            "'Who has access: anyone with the link'.")


def sync(prospects: list[dict], dry: bool = False, log=print, opener=None,
         csv_path: Path | None = None) -> dict:
    """CSV first, then the webhook. -> {rows, csv, sheet}."""
    rows = [as_row(p) for p in prospects]
    written = write_csv(rows, csv_path)
    log(f"  {len(rows)} row(s) -> {written}")
    if dry:
        return {"rows": len(rows), "csv": str(written), "sheet": "dry run"}
    if not configured():
        log(f"  {SHEET_URL}/{SHEET_SECRET} not set — the sheet was not updated (the CSV was)")
        return {"rows": len(rows), "csv": str(written), "sheet": "not configured"}
    got = post(rows, opener=opener)
    log(f"  sheet: {got.get('updated', '?')} updated, {got.get('added', '?')} added")
    return {"rows": len(rows), "csv": str(written), "sheet": got}
