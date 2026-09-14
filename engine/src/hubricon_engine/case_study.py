"""One case study, told in full, or nothing.

index.html §3b ships only when a real client's Proving Month has closed and the
client has said yes, in writing, to publishing it. Until then the section does
not exist on the page and nothing stands in its place. This module is the only
way a row reaches that section, and every rule below is a reason it refuses:

  - the Proving Month has closed (thirty days from the day they said yes);
  - the client granted the testimonial and wrote it, thirty words or fewer;
  - the client wrote their before-state, in their own words (consents.before_text);
  - the client granted publication: named_results names the brand, and
    anonymised_results alone publishes it as "a <category> brand";
  - the Record has rows to show, and at least one of them is a recorded miss.

Nothing here is generated. The quote and the before-state are the client's own
text, copied verbatim; the three numbers come from value.compute on the client's
real ledger; the Record rows are the client's own moves and claims with every
SKU, ASIN and FNSKU masked. public_case_study() re-checks consent on every read,
so a revocation takes the section down without anyone running anything.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from . import value

QUOTE_MAX_WORDS = 30
PROVING_DAYS = 30
RECORD_MAX_ROWS = 8
# Amazon's own identifier shapes, masked even when no row names them as a SKU.
_AMAZON_ID = re.compile(r"\b(?:B0|X0)[A-Z0-9]{8}\b")


def _day(v) -> date | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _usd(v) -> float | None:
    return None if v is None else round(float(v), 2)


def words(text: str | None) -> int:
    return len((text or "").split())


def identifiers(directives: list[dict], claims: list[dict]) -> set[str]:
    """Every SKU, ASIN and FNSKU the client's own rows name."""
    found: set[str] = set()
    for d in directives:
        ev = d.get("evidence") if isinstance(d.get("evidence"), dict) else {}
        for key in ("sku", "asin", "fnsku"):
            if ev.get(key):
                found.add(str(ev[key]))
        for s in ev.get("skus") or []:
            if isinstance(s, dict) and s.get("sku"):
                found.add(str(s["sku"]))
            elif isinstance(s, str):
                found.add(s)
    for c in claims:
        for key in ("sku", "fnsku", "asin"):
            if c.get(key):
                found.add(str(c[key]))
    return {i for i in found if len(i) >= 3}


def _hide(ident: str) -> str:
    return ident[:2] + "•" * max(3, min(6, len(ident) - 2))


def mask(text: str, ids: set[str]) -> str:
    """Replace every identifier with its first two characters and dots. Longest
    first, so a SKU that contains another SKU is never half-masked."""
    for ident in sorted(ids, key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(ident)}(?![A-Za-z0-9])", _hide(ident), text)
    return _AMAZON_ID.sub(lambda m: _hide(m.group(0)), text)


def _filed(c: dict) -> bool:
    return bool(c.get("filed_at") or c.get("case_id"))


def record_rows(directives: list[dict], claims: list[dict], ids: set[str]) -> list[dict]:
    """The Record as the demo table shows it: move, expected, measured, how we know."""
    rows: list[dict] = []
    for d in directives:
        if not value._is_made(d) or d.get("expected_impact_usd") is None:
            continue
        expected, measured = _usd(d["expected_impact_usd"]), _usd(d.get("measured_impact_usd"))
        how = (d.get("measurement_notes") or "Measured on the brand's own later exports") if measured is not None \
            else "Made; not yet measured"
        rows.append({"move": mask(d.get("action_text") or "", ids), "expected": expected, "measured": measured,
                     "how": mask(str(how), ids), "miss": measured is not None and measured < expected,
                     "on": str(d.get("executed_at") or d.get("measured_at") or d.get("created_at") or "")[:10]})
    for c in claims:
        if not _filed(c) or c.get("expected_value") is None:
            continue
        kind = str(c.get("claim_type") or "reimbursement").replace("_", " ")
        units = c.get("units")
        move = f"Filed a {kind} claim" + (f" for {units} unit{'' if units == 1 else 's'}" if units else "")
        status = c.get("status")
        expected = _usd(c["expected_value"])
        if status == "paid":
            measured, how = _usd(c.get("paid_amount")), "Confirmed by Amazon's own reimbursement record"
        elif status == "denied":
            measured, how = 0.0, "Denied by Amazon — recorded, not hidden"
        else:
            measured, how = None, "Not yet — it becomes proven only when Amazon pays"
        rows.append({"move": mask(move, ids), "expected": expected, "measured": measured, "how": how,
                     "miss": measured is not None and measured < expected,
                     "on": str(c.get("filed_at") or "")[:10]})
    return rows


def shown_rows(rows: list[dict], cap: int = RECORD_MAX_ROWS) -> list[dict]:
    """Every miss first (it is the row that makes the rest believable), then the
    largest moves, shown in the order they happened."""
    misses = [r for r in rows if r["miss"]]
    rest = sorted((r for r in rows if not r["miss"]), key=lambda r: -(r["expected"] or 0))
    keep = (misses + rest)[:cap]
    return sorted(keep, key=lambda r: r["on"])


def numbers(ledger: dict, rows: list[dict]) -> list[dict]:
    found = round(sum(r["expected"] or 0 for r in rows), 2)
    return [
        {"label": "Found", "amount_usd": found,
         "method": "Every move made and every claim filed, at the dollars written down before it went live"},
        {"label": "Proven", "amount_usd": float(ledger.get("value_total") or 0),
         "method": "Measured on the exact lines of the brand's own later exports, capped at what was promised; "
                   "claims only once Amazon paid"},
        {"label": "Measured against", "amount_usd": float(ledger.get("fees_billed") or 0),
         "method": "Everything invoiced since day one; the Proving Month bills nothing"},
    ]


def draft(client: dict, directives: list[dict], claims: list[dict], consents: list[dict],
          invoices: list[dict] | None = None, today: date | None = None,
          allow_no_miss: bool = False) -> tuple[dict, list[str]]:
    """The row public_case_study() would serve, and every reason it may not."""
    today = today or date.today()
    problems: list[str] = []

    started = _day(client.get("retainer_started_at"))
    closed = started + timedelta(days=PROVING_DAYS) if started else None
    if closed is None:
        problems.append("no retainer start on file: the Proving Month has not begun, so it cannot have closed")
    elif closed > today:
        problems.append(f"the Proving Month closes on {closed.isoformat()}, not before")

    by_kind = {k.get("kind"): k for k in consents}
    granted = lambda kind: bool((by_kind.get(kind) or {}).get("granted"))  # noqa: E731
    testimonial = by_kind.get("testimonial") or {}
    quote = (testimonial.get("testimonial") or "").strip()
    before = (testimonial.get("before_text") or "").strip()
    if not granted("testimonial"):
        problems.append("testimonial consent not granted")
    if not quote:
        problems.append("no testimonial text: the quote has to be the client's own words")
    elif words(quote) > QUOTE_MAX_WORDS:
        problems.append(f"the quote is {words(quote)} words; the section takes {QUOTE_MAX_WORDS} or fewer, "
                        "and shortening it is the client's call, not ours")
    if not before:
        problems.append("no before-state: the client writes it on their consent page, in their own words")
    named = granted("named_results")
    if not (named or granted("anonymised_results")):
        problems.append("publication not granted: neither named_results nor anonymised_results")
    if not named and not client.get("industry"):
        problems.append("anonymised but no industry on the client row: set it with `hubricon proof set`")

    rows = record_rows(directives, claims, identifiers(directives, claims))
    if not rows:
        problems.append("the Record has no made moves or filed claims to show")
    elif not any(r["miss"] for r in rows) and not allow_no_miss:
        problems.append("the Record shows no recorded miss. A case study without one is not consistent with "
                        "the page; pass --allow-no-miss only if that really is the whole Record")

    ledger = value.compute(client, directives, claims, invoices, today)
    row = {
        "client_id": client["id"],
        "brand_name": client.get("company_name") if named else None,
        "industry": client.get("industry"),
        "platform": client.get("platform") or "amazon",
        "before_text": before,
        "quote": quote,
        "numbers": numbers(ledger, rows),
        "record": shown_rows(rows),
        "proving_month_closed_on": closed.isoformat() if closed else None,
    }
    return row, problems


def load(db, client_id: str) -> tuple[dict, list[dict], list[dict], list[dict], list[dict]]:
    client = db.table("clients").select("*").eq("id", client_id).execute().data[0]
    directives = db.table("directives").select("*").eq("client_id", client_id).execute().data
    claims = db.table("recovery_claims").select("*").eq("client_id", client_id).execute().data
    consents = db.table("consents").select("*").eq("client_id", client_id).execute().data
    invoices = db.table("invoices").select("*").eq("client_id", client_id).execute().data
    return client, directives, claims, consents, invoices


def build(db, client_id: str, today: date | None = None, allow_no_miss: bool = False) -> tuple[dict, list[str]]:
    client, directives, claims, consents, invoices = load(db, client_id)
    return draft(client, directives, claims, consents, invoices, today, allow_no_miss)


def publish(db, client_id: str, today: date | None = None, allow_no_miss: bool = False) -> tuple[dict, list[str]]:
    """Write and publish, or write nothing and say why."""
    row, problems = build(db, client_id, today, allow_no_miss)
    if problems:
        return row, problems
    now = datetime.now(timezone.utc).isoformat()
    db.table("case_studies").upsert({**row, "published": True, "published_at": now, "drafted_at": now},
                                    on_conflict="client_id").execute()
    db.table("funnel_events").insert({"kind": "case_study_published", "client_id": client_id,
                                      "payload": {"named": row["brand_name"] is not None,
                                                  "rows": len(row["record"])}}).execute()
    return row, []


def unpublish(db, client_id: str) -> None:
    db.table("case_studies").update({"published": False}).eq("client_id", client_id).execute()
    db.table("funnel_events").insert({"kind": "case_study_unpublished", "client_id": client_id,
                                      "payload": {}}).execute()


def render_text(row: dict) -> str:
    """The section as a founder would read it, for the terminal."""
    usd = lambda v: "—" if v is None else f"${v:,.0f}"  # noqa: E731
    who = row["brand_name"] or f"A {row.get('industry') or '(no industry)'} brand"
    lines = [f"{who} · Proving Month closed {row.get('proving_month_closed_on') or '(not closed)'}", "",
             f"Before: “{row['before_text'] or '(missing)'}”", ""]
    for n in row["numbers"]:
        lines.append(f"  {n['label']:<17} {usd(n['amount_usd']):>10}   {n['method']}")
    lines.append("")
    for r in row["record"]:
        flag = "  MISS" if r["miss"] else ""
        lines.append(f"  {r['on'] or '          '}  {usd(r['expected']):>9} → {usd(r['measured']):>9}{flag}  {r['move']}  ({r['how']})")
    lines += ["", f"Quote: “{row['quote'] or '(missing)'}”"]
    return "\n".join(lines)
