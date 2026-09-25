"""The Seal: every promise on the Profit Record fingerprinted before the move
goes live, and every measurement chained after it.

"We write the expected dollars down before a move goes live" was true and could
not be checked. The promise lived in a directives row Hubricon can edit, so a
client, a buyer's diligence team or a lender had our word for it and nothing
else. This module turns the claim into arithmetic anyone can redo.

Each move gets two entries, a double entry:

  called    sealed by issue.issue_drafts the moment the move is issued, BEFORE
            the email that states it is sent: the move, its target, the
            expected dollars, the promised band (replay._promise_band), the
            mandate, when it was issued, and a SHA-256 of the evidence the
            number was computed from.
  measured  sealed when the measurement pass banks or closes it (the IO wrapper
            cli._measure_for_run; measurement.py itself stays pure), or when a
            number is recorded by hand: the measured dollars, how we know
            (direct, isolated, attributable, unmeasurable), and the leaf of the
            called entry it answers.

An entry's document is canonical JSON — RFC 8785: sorted keys, no whitespace,
UTF-8, numbers as ECMAScript prints them — so it hashes to the same leaf here and
in the dependency-free verifier (scripts/verify-record.mjs). Money is written as
fixed two-decimal strings and timestamps as UTC to the microsecond, so neither a
float nor a clock format ever reaches a hash. The leaves are chained twice:

    leaf   = sha256(canonical(document))
    head_n = sha256(head_{n-1} || leaf_n)     raw 32-byte digests; head_0 = 64 zeros

once per client (their own Record) and once across every client, whose head is
public (`public_record_seal()`), because a hash reveals nothing.

Two witnesses make a rewrite evident rather than merely inconvenient. The
pre-move email prints each promise's short seal — the first twelve hex of its
leaf — beside its expected dollars, so the client's own inbox timestamps what
was called; and the global head is published, so any capture of it pins every
entry beneath it.

What it cannot do. It cannot stop the database owner rewriting history; it can
only make a rewrite disagree with the witnesses, which is why they exist. The
short seal is 48 bits: a receipt a person can read, not a proof — the full leaf
is in the Record export. No external timestamp anchor exists yet (OpenTimestamps
over the global head, or a Wayback capture of it); until one does, "when" rests
on the client's inbox and whatever captures of the head exist. A move issued
before the table existed, or while a write failed, is sealed later by
`catch_up` and labelled `late` — never passed off as called before. And it never
blocks a client email: every failure here is a named status, and the notice goes
out without seals, exactly as it did before this module existed.
"""

from __future__ import annotations

import hashlib
import json
import math
import numbers
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .replay import _promise_band

TABLE = "record_seals"
RPC = "public_record_seal"
MIGRATION = "20260925000002_record_seal.sql"
VERSION = 1
FORMAT = "hubricon-record-seal/1"
GENESIS = "0" * 64
SHORT = 12              # hex characters of a leaf printed in the pre-move email
ATTEMPTS = 3            # a lost race for the next sequence number is retried from a fresh read
PAGE = 1000             # PostgREST caps a response at 1,000 rows and says nothing

ALGORITHM = {
    "canonical": "RFC 8785 JSON Canonicalization Scheme, UTF-8",
    "leaf": "sha256(canonical(document)), lowercase hex",
    "head": "sha256(previous head || leaf) over the raw 32-byte digests; the first previous head is 64 zeros",
    "chains": "one per client (seq, prev_head, head) and one across all clients "
              "(global_seq, global_prev_head, global_head); the global head is public",
}

# Keys a directive's evidence gains AFTER it is issued. The measurement pass
# writes the after-half of the before/after into `evidence.after`; the promise
# is everything else, and the measured entry seals `after` on its own.
POST_ISSUE_EVIDENCE = ("after",)

# The subject a move acts on, exactly as the drafting code stored it in the
# evidence. Lists of rows (search terms, campaigns) keep their names only; the
# whole evidence is bound by its digest anyway.
TARGET_FIELDS = ("sku", "asin", "campaign_name", "scope", "item_id", "metric", "supplier", "family",
                 "skus", "claim_keys", "brand_terms")

# The attribution column's words, in the client's vocabulary (HUBRICON.md).
GRADES = {"direct": "direct", "isolated": "isolated", "attributable": "attributable", "none": "unmeasurable"}

# What a seal attempt reports: a name, never a number.
SEALED = "sealed"                 # every entry asked for is on the chain now
ALREADY = "already_sealed"        # nothing new to write: each was sealed before
PARTIAL = "partial"               # some sealed, some refused, each refusal named
REFUSED = "refused"               # every document was refused, each refusal named
NOTHING = "nothing_to_seal"
TABLE_MISSING = "table_missing"   # the migration is not applied: nothing sealed, nothing broken
UNAVAILABLE = "unavailable"       # the table exists or not; it could not be read
FAILED = "failed"                 # the write did not land; nothing was half-written

# How a called entry came to be sealed, and how a measured one.
AT_ISSUE, LATE = "at_issue", "late"
AT_MEASUREMENT, BY_HAND = "at_measurement", "by_hand"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SealError(ValueError):
    """A value the canonical form refuses rather than guesses at."""


# ── the canonical form ───────────────────────────────────────────────────────

def canonical(value) -> bytes:
    """RFC 8785: the one byte string a JSON value hashes as, in any language.

    Keys sorted by UTF-16 code unit, no whitespace, strings escaped the way
    ECMAScript's JSON.stringify escapes them, numbers printed the way
    ECMAScript prints a double. Anything JSON cannot say — NaN, infinity, a
    set, a date object, a non-string key, a lone surrogate — is refused with
    a SealError rather than coerced: a seal over a guessed value is worse
    than no seal."""
    return _jcs(value).encode("utf-8")


def _jcs(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return _jcs_string(v)
    if isinstance(v, numbers.Integral):
        n = int(v)
        # JavaScript holds every number as a double: past 2**53 an integer is
        # rounded when read, so it is rounded here the same way.
        return str(n) if abs(n) < 2 ** 53 else es_number(float(n))
    if isinstance(v, numbers.Real):
        return es_number(float(v))
    if isinstance(v, dict):
        for k in v:
            if not isinstance(k, str):
                raise SealError(f"a key of type {type(k).__name__} has no canonical JSON form")
        keys = sorted(v, key=lambda k: _utf16(k))
        return "{" + ",".join(f"{_jcs_string(k)}:{_jcs(v[k])}" for k in keys) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_jcs(x) for x in v) + "]"
    raise SealError(f"{type(v).__name__} has no canonical JSON form; convert it before sealing")


def _utf16(s: str) -> bytes:
    try:
        return s.encode("utf-16-be")
    except UnicodeEncodeError as err:
        raise SealError("a key holds a lone surrogate, which has no canonical form") from err


def _jcs_string(s: str) -> str:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError as err:
        raise SealError("a string holds a lone surrogate, which has no UTF-8 form") from err
    # Python escapes exactly what JSON.stringify escapes: the quote, the
    # backslash, and the controls below U+0020 (\b \t \n \f \r by name, the
    # rest as lowercase \u00xx). Everything else goes out as itself.
    return json.dumps(s, ensure_ascii=False)


def es_number(x: float) -> str:
    """A double as ECMAScript's Number::toString prints it (RFC 8785 §3.2.2.3).

    Python's repr and ECMAScript both produce the shortest digit string that
    reads back as the same double; only the layout differs (1e-07 against
    1e-7, 100.0 against 100). This takes repr's digits and lays them out
    ECMAScript's way."""
    if not math.isfinite(x):
        raise SealError(f"{x!r} is not a finite number; JSON has no form for it")
    if x == 0:
        return "0"                                   # and -0 prints as 0, as in ECMAScript
    r = float.__repr__(x)
    sign = ""
    if r.startswith("-"):
        sign, r = "-", r[1:]
    mantissa, _, exponent = r.partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = (whole + fraction).lstrip("0")
    e10 = (int(exponent) if exponent else 0) - len(fraction)      # x = int(digits) * 10**e10
    trimmed = digits.rstrip("0")
    e10 += len(digits) - len(trimmed)
    digits = trimmed
    k = len(digits)
    n = e10 + k                                                   # x = 0.digits * 10**n
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        out = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + out


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf_of(document: dict) -> str:
    return sha256_hex(canonical(document))


def link(prev_head: str, leaf: str) -> str:
    """head_n = sha256(head_{n-1} || leaf_n), over raw bytes. Refuses anything
    that is not two 64-character lowercase hex digests, because a hash of a
    truncated input would chain silently."""
    if not (isinstance(prev_head, str) and _HEX64.match(prev_head)
            and isinstance(leaf, str) and _HEX64.match(leaf)):
        raise SealError("a head or leaf is not a 64-character lowercase hex SHA-256")
    return sha256_hex(bytes.fromhex(prev_head) + bytes.fromhex(leaf))


def short(leaf: str | None) -> str | None:
    return leaf[:SHORT] if leaf else None


def as_stored(value):
    """The value exactly as the database will hold and return it: through
    JSON once, so a tuple is a list, a numpy float is a float and an integer
    key is a string, as they will be when the row is read back."""
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as err:
        raise SealError(f"not storable as JSON: {err}") from err


def digest(value) -> str:
    return sha256_hex(canonical(as_stored(value)))


def money(value) -> str | None:
    """Dollars as a fixed two-decimal string, rounded half away from zero —
    what a numeric(12,2) column holds for the same input."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise SealError("a boolean is not an amount")
    try:
        d = Decimal(str(value))
    except InvalidOperation as err:
        raise SealError(f"{value!r} is not an amount") from err
    if not d.is_finite():
        raise SealError(f"{value!r} is not a finite amount")
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(q if q != 0 else Decimal("0.00"), "f")


def stamp(value) -> str | None:
    """A timestamp as UTC to the microsecond, 'Z'-suffixed, whatever form it
    arrived in: Python's isoformat, Postgres's (which trims trailing zeros from
    the fraction), a datetime. An instant has one spelling or it cannot be
    hashed. A value without an offset is UTC, as timestamptz reads it here."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if len(text) > 10 and text[10] == " ":
            text = text[:10] + "T" + text[11:]
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as err:
            raise SealError(f"{value!r} is not a timestamp") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── the documents ────────────────────────────────────────────────────────────

def promise_evidence(evidence: dict | None) -> dict:
    return {k: v for k, v in (evidence or {}).items() if k not in POST_ISSUE_EVIDENCE}


def target(evidence: dict | None) -> dict:
    ev = evidence or {}
    out = {k: ev[k] for k in TARGET_FIELDS if ev.get(k) is not None}
    if isinstance(ev.get("terms"), list):
        out["terms"] = [[t.get("campaign_name"), t.get("search_term")] for t in ev["terms"] if isinstance(t, dict)]
    if isinstance(ev.get("campaigns"), list):
        out["campaigns"] = [c.get("campaign_name") for c in ev["campaigns"] if isinstance(c, dict)]
    return as_stored(out)


def called_key(directive_id) -> str:
    return f"called:{directive_id}"


def measured_key(directive_id, measured_at) -> str:
    return f"measured:{directive_id}:{stamp(measured_at)}"


def called_document(d: dict, client_id, sealed_at, sealed: str = AT_ISSUE) -> dict:
    """What was promised, as it stood when it was issued."""
    if not d.get("id"):
        raise SealError("a move without an id cannot be sealed")
    if not d.get("issued_at"):
        raise SealError("never issued, so nothing was called")
    evidence = d.get("evidence") or {}
    if not isinstance(evidence, dict):
        raise SealError("the evidence is not a JSON object")
    try:
        band = _promise_band(d)
    except (TypeError, ValueError) as err:
        raise SealError(f"the promised band is not a pair of numbers: {err}") from err
    return {
        "v": VERSION,
        "entry": "called",
        "client_id": str(client_id),
        "directive_id": str(d["id"]),
        "channel": d.get("channel"),
        "module": d.get("module"),
        "kind": d.get("kind"),
        "target": target(evidence),
        "dedupe_key": d.get("dedupe_key"),
        "action_text": d.get("action_text"),
        "expected_usd": money(d.get("expected_impact_usd")),
        "band_usd": None if band is None else {"p5": money(band[0]), "p95": money(band[1])},
        "mandate": d.get("mandate"),
        "issued_at": stamp(d.get("issued_at")),
        "evidence_sha256": digest(promise_evidence(evidence)),
        "sealed": sealed,
        "sealed_at": stamp(sealed_at),
    }


def measured_document(d: dict, client_id, called_leaf: str, supersedes: str | None, sealed_at,
                      sealed: str = AT_MEASUREMENT) -> dict:
    """What the measurement found, answering the called entry by its leaf."""
    if not d.get("measured_at"):
        raise SealError("not measured yet")
    after = (d.get("evidence") or {}).get("after")
    attribution = d.get("attribution")
    return {
        "v": VERSION,
        "entry": "measured",
        "client_id": str(client_id),
        "directive_id": str(d["id"]),
        "called_leaf": called_leaf,
        "supersedes": supersedes,
        "measured_usd": money(d.get("measured_impact_usd")),
        "grade": GRADES.get(attribution, attribution or "unrecorded"),
        "status": d.get("status"),
        "measured_at": stamp(d.get("measured_at")),
        "after_sha256": None if after is None else digest(after),
        "sealed": sealed,
        "sealed_at": stamp(sealed_at),
    }


# ── the database ─────────────────────────────────────────────────────────────

def _code(err) -> str:
    return str(getattr(err, "code", "") or "")


def _why(err) -> str:
    return f"{type(err).__name__}: {str(err)[:200]}"


def _missing(err) -> bool:
    text = f"{_code(err)} {err}"
    return _code(err) in ("PGRST205", "42P01") or (
        TABLE in text and any(m in text for m in ("does not exist", "schema cache", "PGRST205", "42P01")))


def _conflict(err) -> bool:
    return _code(err) == "23505" or "duplicate key" in str(err)


def table_status(db) -> dict:
    """Is the Seal's table there to write to? Read-only, and never raises: a
    database without the migration is a database without seals, not an error
    (the same stance calibration.py takes toward its own table)."""
    try:
        db.table(TABLE).select("global_seq").limit(1).execute()
        return {"status": "ready", "reason": None}
    except Exception as err:
        if _missing(err):
            return {"status": TABLE_MISSING,
                    "reason": f"migration {MIGRATION} is not applied, so moves are issued and emailed unsealed"}
        return {"status": UNAVAILABLE, "reason": f"{TABLE} could not be read ({_why(err)})"}


def _fetch(db, client_id: str | None = None, columns: str = "*") -> list[dict]:
    """Every seal row for one client (by seq) or for all (by global_seq), paged."""
    order = "seq" if client_id else "global_seq"
    out, start = [], 0
    while True:
        q = db.table(TABLE).select(columns)
        if client_id:
            q = q.eq("client_id", client_id)
        rows = q.order(order).range(start, start + PAGE - 1).execute().data or []
        out.extend(rows)
        if len(rows) < PAGE:
            break
        start += PAGE
    return sorted(out, key=lambda r: int(r[order]))


def _global_tip(db) -> tuple[int, str]:
    rows = (db.table(TABLE).select("global_seq, global_head")
            .order("global_seq", desc=True).limit(1).execute().data)
    return (int(rows[0]["global_seq"]), rows[0]["global_head"]) if rows else (0, GENESIS)


class _Index:
    """One client's chain as it stands: every entry, by key and in order."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows: list[dict] = []
        self.by_key: dict[str, dict] = {}
        self.add(rows or [])

    @classmethod
    def load(cls, db, client_id: str) -> "_Index":
        return cls(_fetch(db, client_id))

    def add(self, rows: list[dict]) -> None:
        for r in rows:
            self.rows.append(r)
            self.by_key[r["entry_key"]] = r

    def tip(self) -> tuple[int, str]:
        return (int(self.rows[-1]["seq"]), self.rows[-1]["head"]) if self.rows else (0, GENESIS)

    def leaf(self, key: str) -> str | None:
        row = self.by_key.get(key)
        return row["leaf"] if row else None

    def last_measured(self, directive_id: str) -> str | None:
        hits = [r for r in self.rows if r["entry"] == "measured" and str(r.get("directive_id")) == str(directive_id)]
        return hits[-1]["leaf"] if hits else None


@dataclass
class _Item:
    key: str
    entry: str
    directive_id: str
    document: dict
    leaf: str


def chain_rows(client_id: str, items: list[_Item], client_tip: tuple[int, str],
               global_tip: tuple[int, str]) -> list[dict]:
    """The rows that append `items` to both chains, from their tips. Pure: the
    same items on the same tips are the same rows, which is what lets the golden
    fixture, the engine and the database agree."""
    c_seq, c_head = client_tip
    g_seq, g_head = global_tip
    rows = []
    for it in items:
        c_seq += 1
        g_seq += 1
        row = {"global_seq": g_seq, "client_id": str(client_id), "seq": c_seq, "entry": it.entry,
               "entry_key": it.key, "directive_id": it.directive_id, "document": it.document,
               "leaf": it.leaf, "prev_head": c_head, "head": link(c_head, it.leaf),
               "global_prev_head": g_head, "global_head": link(g_head, it.leaf),
               "sealed_at": it.document["sealed_at"]}
        c_head, g_head = row["head"], row["global_head"]
        rows.append(row)
    return rows


def _seal(db, client_id: str, plan) -> tuple[list[dict], _Index]:
    """Append what `plan(index)` asks for, in one insert.

    One statement, so the entries land together or not at all. The unique keys
    (global_seq, client_id+seq, entry_key) and the database's own trigger make
    a second writer's insert fail rather than fork a chain; the loser re-reads
    and re-plans, and anything the winner already sealed drops out of the plan."""
    for attempt in range(1, ATTEMPTS + 1):
        index = _Index.load(db, client_id)
        items = plan(index)
        if not items:
            return [], index
        rows = chain_rows(client_id, items, index.tip(), _global_tip(db))
        try:
            db.table(TABLE).insert(rows).execute()
        except Exception as err:
            if attempt < ATTEMPTS and _conflict(err):
                continue
            raise
        index.add(rows)
        return rows, index
    return [], _Index()        # unreachable: the last attempt returns or raises


def _outcome(new: int, refused: dict, asked: int) -> str:
    if refused:
        return PARTIAL if len(refused) < asked else REFUSED
    if not asked:
        return NOTHING
    return SEALED if new else ALREADY


# ── sealing ──────────────────────────────────────────────────────────────────

def seal_called(db, client_id: str, directives: list[dict], sealed_at=None, sealed: str = AT_ISSUE) -> dict:
    """Seal the promise each directive makes, as issued. Returns a named
    status and each move's short seal for the email; never raises."""
    ready = table_status(db)
    if ready["status"] != "ready":
        return {"status": ready["status"], "reason": ready["reason"], "sealed": 0, "short": {}, "refused": {}}
    when = sealed_at or _now()
    refused: dict[str, str] = {}

    def plan(index: _Index) -> list[_Item]:
        items, have = [], index.by_key
        for d in directives:
            key = called_key(d.get("id"))
            if key in have or str(d.get("id")) in refused:
                continue
            try:
                doc = called_document(d, client_id, when, sealed)
                items.append(_Item(key, "called", str(d["id"]), doc, leaf_of(doc)))
            except SealError as err:
                refused[str(d.get("id"))] = str(err)
        return items

    try:
        rows, index = _seal(db, client_id, plan)
    except Exception as err:
        return {"status": FAILED, "reason": _why(err), "sealed": 0, "short": {}, "refused": refused}
    have = index.by_key
    marks = {d["id"]: short(have[called_key(d["id"])]["leaf"])
             for d in directives if d.get("id") and called_key(d["id"]) in have}
    status = _outcome(len(rows), refused, len(directives))
    return {"status": status, "reason": "; ".join(f"{k[:8]}: {v}" for k, v in refused.items()) or None,
            "sealed": len(rows), "short": marks, "refused": refused}


def _plan_measured(client_id: str, rows: list[dict], when, sealed: str, refused: dict):
    """The measured entries for `rows` (directives as they now stand), with a
    late called entry first for any move that was never sealed when issued, so
    every measured entry answers a called one."""
    def plan(index: _Index) -> list[_Item]:
        items: list[_Item] = []
        have = index.by_key
        planned_called: dict[str, str] = {}
        planned_measured: dict[str, str] = {}
        for d in rows:
            did = str(d.get("id"))
            if did in refused:
                continue
            try:
                called = index.leaf(called_key(did)) or planned_called.get(did)
                if called is None:
                    doc = called_document(d, client_id, when, LATE)
                    called = leaf_of(doc)
                    items.append(_Item(called_key(did), "called", did, doc, called))
                    planned_called[did] = called
                key = measured_key(did, d.get("measured_at"))
                if key in have or any(it.key == key for it in items):
                    continue
                prior = planned_measured.get(did) or index.last_measured(did)
                doc = measured_document(d, client_id, called, prior, when, sealed)
                items.append(_Item(key, "measured", did, doc, leaf_of(doc)))
                planned_measured[did] = items[-1].leaf
            except SealError as err:
                refused[did] = str(err)
                items = [it for it in items if it.directive_id != did]
        return items
    return plan


def seal_measured(db, client_id: str, directives: list[dict], sealed: str = AT_MEASUREMENT,
                  sealed_at=None) -> dict:
    """Seal what the measurement found for each directive (as it now stands:
    status, measured dollars, grade, measured_at). Never raises."""
    rows = [d for d in directives if d.get("measured_at")]
    ready = table_status(db)
    if ready["status"] != "ready":
        return {"status": ready["status"], "reason": ready["reason"], "sealed": 0, "refused": {}}
    refused: dict[str, str] = {}
    try:
        new, _ = _seal(db, client_id, _plan_measured(client_id, rows, sealed_at or _now(), sealed, refused))
    except Exception as err:
        return {"status": FAILED, "reason": _why(err), "sealed": 0, "refused": refused}
    return {"status": _outcome(len(new), refused, len(rows)), "sealed": len(new), "refused": refused,
            "reason": "; ".join(f"{k[:8]}: {v}" for k, v in refused.items()) or None}


def catch_up(db, client_id: str, sealed_at=None) -> dict:
    """Seal what should already be on the chain and is not: a move issued
    before the table existed or while a write failed, a measurement whose seal
    did not land. Every entry written here says `late`, so nothing sealed after
    the fact can pass for a promise called before. Never raises."""
    ready = table_status(db)
    if ready["status"] != "ready":
        return {"status": ready["status"], "reason": ready["reason"], "sealed": 0, "refused": {}}
    when = sealed_at or _now()
    refused: dict[str, str] = {}
    try:
        from .db import fetch_all          # paged: PostgREST cuts a response at 1,000 rows and says nothing
        directives = [d for d in fetch_all(db, "directives", client_id)
                      if d.get("issued_at") and d.get("status") != "draft"]
        if not directives:
            return {"status": NOTHING, "sealed": 0, "refused": {}, "reason": None}
        issued = sorted(directives, key=lambda d: (stamp(d["issued_at"]), str(d["id"])))
        measured = sorted((d for d in directives if d.get("measured_at")),
                          key=lambda d: (stamp(d["measured_at"]), str(d["id"])))

        def plan(index: _Index) -> list[_Item]:
            items, have = [], index.by_key
            for d in issued:
                key = called_key(d["id"])
                if key in have or str(d["id"]) in refused:
                    continue
                try:
                    doc = called_document(d, client_id, when, LATE)
                    items.append(_Item(key, "called", str(d["id"]), doc, leaf_of(doc)))
                except SealError as err:
                    refused[str(d["id"])] = str(err)
            # the measured half, planned against the chain as it will stand
            # once the late called entries above are on it
            ahead = _Index(index.rows + [{"entry_key": it.key, "entry": it.entry, "directive_id": it.directive_id,
                                          "leaf": it.leaf, "seq": 0} for it in items])
            items += _plan_measured(client_id, measured, when, LATE, refused)(ahead)
            return items

        new, _ = _seal(db, client_id, plan)
    except Exception as err:
        return {"status": FAILED, "reason": _why(err), "sealed": 0, "refused": refused}
    return {"status": _outcome(len(new), refused, len(new) + len(refused)) if (new or refused) else ALREADY,
            "sealed": len(new), "refused": refused,
            "reason": "; ".join(f"{k[:8]}: {v}" for k, v in refused.items()) or None}


# ── the export, and checking it ──────────────────────────────────────────────

def _entry(r: dict) -> dict:
    return {k: r.get(k) for k in ("seq", "global_seq", "entry", "entry_key", "document", "leaf",
                                  "prev_head", "head", "global_prev_head", "global_head")}


def bundle(client_id: str, rows: list[dict], directives: list[dict], global_rows: list[dict],
           generated_at=None) -> dict:
    """The Record's seals as one self-contained file: each entry's canonical
    document, leaf and heads; the evidence each promise was computed from, so
    its digest can be redone; and every global leaf from the client's first
    entry to the current global head, so the entries can be placed in the
    public chain. Other clients' leaves are hashes of documents keyed by
    random ids: they say how many entries exist and nothing else. Pure."""
    rows = sorted(rows, key=lambda r: int(r["seq"]))
    global_rows = sorted(global_rows, key=lambda r: int(r["global_seq"]))
    out = {"format": FORMAT, "client_id": str(client_id), "generated_at": stamp(generated_at or _now()),
           "algorithm": ALGORITHM, "status": "sealed" if rows else "empty",
           "entries": [_entry(r) for r in rows], "head": rows[-1]["head"] if rows else GENESIS}
    sealed_ids = {str(r.get("directive_id")) for r in rows if r.get("directive_id")}
    out["evidence"] = {str(d["id"]): {"before": promise_evidence(d.get("evidence")),
                                      "after": (d.get("evidence") or {}).get("after")}
                       for d in sorted(directives, key=lambda d: str(d["id"])) if str(d["id"]) in sealed_ids}
    if rows and global_rows:
        first = int(rows[0]["global_seq"])
        tail = [g for g in global_rows if int(g["global_seq"]) >= first]
        last = global_rows[-1]
        out["global"] = {"head": last["global_head"], "entries": int(last["global_seq"]),
                         "last_sealed_at": stamp(last.get("sealed_at")), "from_seq": first,
                         "leaves": [g["leaf"] for g in tail]}
    else:
        out["global"] = None
    return out


def export_bundle(db, client_id: str) -> dict:
    ready = table_status(db)
    if ready["status"] != "ready":
        return {"format": FORMAT, "client_id": str(client_id), "generated_at": stamp(_now()),
                "algorithm": ALGORITHM, "status": ready["status"], "reason": ready["reason"],
                "entries": [], "head": GENESIS, "evidence": {}, "global": None}
    rows = _fetch(db, client_id)
    ids = sorted({str(r["directive_id"]) for r in rows if r.get("directive_id")})
    directives = []
    for i in range(0, len(ids), 100):
        directives += db.table("directives").select("id, evidence").in_("id", ids[i:i + 100]).execute().data or []
    global_rows = _fetch(db, None, "global_seq, leaf, global_head, sealed_at") if rows else []
    return bundle(client_id, rows, directives, global_rows)


def write_export(zf, db, client_id: str, verifier_path=None) -> list[str]:
    """record-seal.json (and the verifier beside it) into an open export zip.
    Returns the manifest lines. Never raises: the export is a promise of its
    own, and a seal problem must not cost the client their data."""
    try:
        b = export_bundle(db, client_id)
        text = json.dumps(b, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    except Exception as err:
        return [f"  record-seal.json: unavailable ({_why(err)})"]
    zf.writestr("record-seal.json", text)
    entries = b["entries"]
    if not entries:
        # The manifest is the client's to read; the precise reason is in the file.
        line = ("  record-seal.json — nothing sealed yet ("
                + ("the Seal is not switched on for this Record yet" if b.get("status") in (TABLE_MISSING, UNAVAILABLE)
                   else "no move has been issued since the Seal began") + ")")
    else:
        called = sum(1 for e in entries if e["entry"] == "called")
        line = (f"  record-seal.json — {len(entries)} sealed entries ({called} called, {len(entries) - called} "
                f"measured), head {b['head'][:16]}…")
    lines = [line]
    if verifier_path is not None:
        try:
            with open(verifier_path, "rb") as fh:
                zf.writestr("verify-record.mjs", fh.read())
            lines.append("  verify-record.mjs — checks record-seal.json offline: node verify-record.mjs record-seal.json")
        except OSError as err:
            lines.append(f"  verify-record.mjs: not included ({err.strerror})")
    return lines


def _hk(v):
    """A hashable stand-in for a value read from a file, which may be anything."""
    return v if isinstance(v, (str, int, float, bool, type(None))) else json.dumps(v, sort_keys=True, default=str)


def verify_bundle(b: dict, witnesses=()) -> dict:
    """Every check a third party can run with nothing but the export file —
    the same checks, in the same order, as scripts/verify-record.mjs.

    Per entry: numbered in order; the document hashes to its leaf; the entry
    follows the one before it; the head is sha256(prev_head || leaf) in both
    chains; it is this client's; its key is the one its document implies; a
    measured entry answers the called entry for the same move and supersedes
    the measurement before it. Then the evidence each promise was computed
    from still hashes to the digest it was sealed with; the client's entries
    sit where they claim in the global chain, which leads to the global head;
    and each witness (a short seal from an email, a head captured earlier)
    is found. `first_broken_seq` is the client sequence number of the first
    entry that fails, or None when only the file as a whole does."""
    problems: list[dict] = []

    def bad(seq, check, detail):
        problems.append({"seq": seq, "check": check, "detail": detail})

    if not isinstance(b, dict) or b.get("format") != FORMAT:
        return {"status": "unreadable", "problems": [{"seq": None, "check": "format",
                                                      "detail": f"not a {FORMAT} file"}],
                "first_broken_seq": None, "entries": 0}
    # A file is data from outside: anything malformed is reported, never raised on.
    entries = [e if isinstance(e, dict) else {} for e in
               (b.get("entries") if isinstance(b.get("entries"), list) else [])]
    client = b.get("client_id")
    prev = GENESIS
    called_by: dict[str, str] = {}
    measured_by: dict[str, str] = {}
    last_measured_entry: dict[str, dict] = {}
    keys: set = set()
    counts = {"called": 0, "measured": 0, "late": 0}
    heads = set()
    for i, e in enumerate(entries, start=1):
        seq = e.get("seq")
        if seq != i:
            bad(i, "sequence", f"entry {i} is numbered {seq}")
            seq = i
        doc = e.get("document")
        if not isinstance(doc, dict):
            bad(seq, "document", "no document: the entry cannot be recomputed")
            prev = e.get("head")
            continue
        try:
            if leaf_of(doc) != e.get("leaf"):
                bad(seq, "leaf", "the document no longer hashes to its seal")
        except SealError as err:
            bad(seq, "leaf", f"the document has no canonical form: {err}")
        if e.get("prev_head") != prev:
            bad(seq, "link", "does not follow the entry before it")
        for p, h in (("prev_head", "head"), ("global_prev_head", "global_head")):
            try:
                if link(e.get(p), e.get("leaf")) != e.get(h):
                    bad(seq, h, f"{h} is not sha256({p} || leaf)")
            except SealError as err:
                bad(seq, h, str(err))
        heads.add(_hk(e.get("head")))
        if doc.get("client_id") != client:
            bad(seq, "client", "sealed for a different client")
        entry, did = doc.get("entry"), _hk(doc.get("directive_id"))
        if e.get("entry") != entry:
            bad(seq, "entry", "the row and its document disagree on what kind of entry this is")
        want = (called_key(did) if entry == "called"
                else f"measured:{did}:{doc.get('measured_at')}" if entry == "measured" else None)
        if e.get("entry_key") != want:
            bad(seq, "entry_key", "the entry's key is not the one its document implies")
        if _hk(e.get("entry_key")) in keys:
            bad(seq, "duplicate", "sealed twice")
        keys.add(_hk(e.get("entry_key")))
        if doc.get("sealed") == LATE:
            counts["late"] += 1
        if entry == "called":
            counts["called"] += 1
            if did in called_by:
                bad(seq, "duplicate", "a second called entry for the same move")
            called_by[did] = e.get("leaf")
        elif entry == "measured":
            counts["measured"] += 1
            if doc.get("called_leaf") is None or called_by.get(did) != doc.get("called_leaf"):
                bad(seq, "double_entry", "does not answer the called entry for this move")
            if doc.get("supersedes") != measured_by.get(did):
                bad(seq, "supersedes", "does not name the measurement it replaces")
            measured_by[did] = e.get("leaf")
            last_measured_entry[did] = {"seq": seq, "doc": doc}
        else:
            bad(seq, "entry", f"unknown entry {entry!r}")
        prev = e.get("head")
    if entries and b.get("head") != prev:
        bad(None, "head", "the Record's head is not its last entry's head")

    evidence = b.get("evidence") if isinstance(b.get("evidence"), dict) else {}
    for i, e in enumerate(entries, start=1):
        doc = e.get("document")
        if not isinstance(doc, dict) or doc.get("entry") != "called":
            continue
        ev = evidence.get(doc.get("directive_id")) if isinstance(doc.get("directive_id"), str) else None
        if not isinstance(ev, dict):
            continue
        try:
            if digest(ev.get("before") or {}) != doc.get("evidence_sha256"):
                bad(i, "evidence", "the evidence behind this promise is not the evidence it was sealed with")
        except SealError as err:
            bad(i, "evidence", str(err))
    for did, m in last_measured_entry.items():
        ev = evidence.get(did) if isinstance(did, str) else None
        if not isinstance(ev, dict):
            continue
        after = ev.get("after")
        try:
            got = None if after is None else digest(after)
        except SealError as err:
            bad(m["seq"], "evidence_after", str(err))
            continue
        if got != m["doc"].get("after_sha256"):
            bad(m["seq"], "evidence_after", "the measurement's evidence is not the evidence it was sealed with")

    g = b.get("global")
    global_heads = set()
    if isinstance(g, dict) and entries:
        from_seq = g.get("from_seq")
        leaves = g.get("leaves") if isinstance(g.get("leaves"), list) else []
        if not isinstance(from_seq, int) or isinstance(from_seq, bool):
            bad(None, "global", "the global section does not say where its leaves start")
        else:
            at = {e.get("global_seq"): (i, e) for i, e in enumerate(entries, start=1)
                  if isinstance(e.get("global_seq"), int) and not isinstance(e.get("global_seq"), bool)}
            h = entries[0].get("global_prev_head")
            try:
                for j, leaf in enumerate(leaves):
                    h = link(h, leaf)
                    global_heads.add(h)
                    hit = at.get(from_seq + j)
                    if hit and (hit[1].get("leaf") != leaf or hit[1].get("global_head") != h):
                        bad(hit[0], "global", f"not at global entry {from_seq + j} of the chain in this file")
            except SealError as err:
                bad(None, "global", str(err))
            for i, e in enumerate(entries, start=1):
                gs = e.get("global_seq")
                if not isinstance(gs, int) or isinstance(gs, bool) or not (from_seq <= gs < from_seq + len(leaves)):
                    bad(i, "global", "outside the global leaves in this file")
            if h != g.get("head"):
                bad(None, "global_head", "the global leaves do not lead to the global head in this file")
            if from_seq + len(leaves) - 1 != g.get("entries"):
                bad(None, "global_count", "the global leaves do not cover the chain up to its head")

    for w in witnesses or ():
        w = str(w).strip().lower()
        if len(w) == 64:
            found = w in heads or w in global_heads or (isinstance(g, dict) and w == g.get("head"))
        else:
            found = len(w) >= 8 and any((e.get("leaf") or "").startswith(w) for e in entries
                                        if (e.get("document") or {}).get("entry") == "called")
        if not found:
            bad(None, "witness", f"nothing in this Record carries {w}")

    seqs = [p["seq"] for p in problems if p["seq"] is not None]
    status = "ok" if not problems else "broken"
    if not entries and not problems:
        status = "empty"
    return {"status": status, "entries": len(entries), **counts, "head": b.get("head"),
            "global_head": (g or {}).get("head") if isinstance(g, dict) else None,
            "first_broken_seq": min(seqs) if seqs else None, "problems": problems}


def _live_problems(entries: list[dict], live: dict[str, dict], client_id: str) -> list[dict]:
    """Does each directive row still say what was sealed? A promise edited in
    the table after its seal — the expected dollars, the words, the mandate —
    fails here, at the called entry's sequence number."""
    problems = []
    latest_measured: dict[str, dict] = {}
    for e in entries:
        doc = e.get("document") or {}
        if doc.get("entry") == "measured":
            latest_measured[doc.get("directive_id")] = e
    for e in entries:
        doc = e.get("document") or {}
        did, seq = doc.get("directive_id"), e.get("seq")
        row = live.get(did)
        if row is None:
            problems.append({"seq": seq, "check": "live_missing", "detail": "the move's row is gone"})
            continue
        try:
            if doc.get("entry") == "called":
                now = called_document(row, client_id, doc.get("sealed_at"), doc.get("sealed"))
            elif latest_measured.get(did) is e:
                now = measured_document(row, client_id, doc.get("called_leaf"), doc.get("supersedes"),
                                        doc.get("sealed_at"), doc.get("sealed"))
            else:
                continue            # an earlier measurement, superseded on the chain itself
        except SealError as err:
            problems.append({"seq": seq, "check": "live_" + doc.get("entry", "entry"), "detail": str(err)})
            continue
        changed = sorted(k for k in set(doc) | set(now) if doc.get(k) != now.get(k))
        if changed:
            detail = "; ".join(f"{k} sealed {doc.get(k)!r}, the row now says {now.get(k)!r}" for k in changed)
            problems.append({"seq": seq, "check": "live_promise" if doc.get("entry") == "called"
                             else "live_measurement", "detail": detail})
        if doc.get("entry") == "called" and doc.get("sealed") == AT_ISSUE:
            for field_ in ("notified_at", "executed_at"):
                if row.get(field_) and stamp(row[field_]) < doc.get("sealed_at"):
                    problems.append({"seq": seq, "check": "order",
                                     "detail": f"sealed after {field_}, so it was not called before"})
    return problems


def verify(db, client_id: str | None = None, live: bool = True, witnesses=()) -> dict:
    """`hubricon seal verify`: one client's Record (with the live rows compared
    unless live=False), or with client_id=None the global chain across every
    client. Returns a named status and the first broken sequence number."""
    ready = table_status(db)
    if ready["status"] != "ready":
        return {"status": ready["status"], "reason": ready["reason"], "problems": [], "first_broken_seq": None,
                "entries": 0}
    if client_id is None:
        return verify_global(_fetch(db), witnesses)
    b = export_bundle(db, client_id)
    out = verify_bundle(b, witnesses)
    if live and b["entries"]:
        ids = sorted({(e["document"] or {}).get("directive_id") for e in b["entries"] if e.get("document")})
        rows = {}
        for i in range(0, len(ids), 100):
            for r in db.table("directives").select("*").in_("id", ids[i:i + 100]).execute().data or []:
                rows[str(r["id"])] = r
        extra = _live_problems(b["entries"], rows, client_id)
        if extra:
            out["problems"] += extra
            seqs = [p["seq"] for p in out["problems"] if p["seq"] is not None]
            out["first_broken_seq"] = min(seqs) if seqs else None
            out["status"] = "broken"
    out["problems"].sort(key=lambda p: (p["seq"] is None, p["seq"] or 0))
    return out


def verify_global(rows: list[dict], witnesses=()) -> dict:
    """The chain across every client, from genesis to the published head. A
    deleted client's rows keep their leaves, so the links still verify; only
    their documents are gone, and those entries are counted, not recomputed."""
    problems = []
    prev = GENESIS
    redacted = 0
    heads = set()
    for i, r in enumerate(sorted(rows, key=lambda r: int(r["global_seq"])), start=1):
        gs = int(r["global_seq"])
        if gs != i:
            problems.append({"seq": i, "check": "sequence", "detail": f"global entry {i} is numbered {gs}"})
        if r.get("global_prev_head") != prev:
            problems.append({"seq": i, "check": "link", "detail": "does not follow the global entry before it"})
        try:
            if link(r.get("global_prev_head"), r.get("leaf")) != r.get("global_head"):
                problems.append({"seq": i, "check": "global_head", "detail": "is not sha256(prev || leaf)"})
        except SealError as err:
            problems.append({"seq": i, "check": "global_head", "detail": str(err)})
        doc = r.get("document")
        if doc is None:
            redacted += 1
        else:
            try:
                if leaf_of(doc) != r.get("leaf"):
                    problems.append({"seq": i, "check": "leaf", "detail": "the document no longer hashes to its seal"})
            except SealError as err:
                problems.append({"seq": i, "check": "leaf", "detail": str(err)})
        prev = r.get("global_head")
        heads.add(prev)
    for w in witnesses or ():
        w = str(w).strip().lower()
        hit = w in heads if len(w) == 64 else any((r.get("leaf") or "").startswith(w) for r in rows)
        if not hit:
            problems.append({"seq": None, "check": "witness", "detail": f"nothing in the global chain carries {w}"})
    seqs = [p["seq"] for p in problems if p["seq"] is not None]
    return {"status": "broken" if problems else "ok" if rows else "empty",
            "scope": "global", "entries": len(rows), "redacted": redacted, "head": prev,
            "first_broken_seq": min(seqs) if seqs else None, "problems": problems}


def status(db) -> dict:
    """`hubricon seal status`: the global head and what each client's Record holds."""
    ready = table_status(db)
    if ready["status"] != "ready":
        return {**ready, "entries": 0}
    rows = _fetch(db, None, "global_seq, client_id, entry, document, global_head, head, sealed_at")
    clients: dict = {}
    for r in rows:
        c = clients.setdefault(r.get("client_id"), {"entries": 0, "called": 0, "measured": 0, "late": 0,
                                                     "head": None})
        c["entries"] += 1
        c[r["entry"]] += 1
        c["late"] += int((r.get("document") or {}).get("sealed") == LATE)
        c["head"] = r.get("head")
    published = None
    try:
        published = db.rpc(RPC, {}).execute().data
    except Exception as err:
        published = {"error": _why(err)}
    last = rows[-1] if rows else None
    return {"status": "ready", "entries": len(rows), "head": last["global_head"] if last else GENESIS,
            "last_sealed_at": stamp(last.get("sealed_at")) if last else None, "clients": clients,
            "published": published}


# ── the command ──────────────────────────────────────────────────────────────

def _render_problems(out: dict, label: str, log) -> None:
    first = out.get("first_broken_seq")
    where = f"at entry {first}" if first is not None else "(the file as a whole)"
    log(f"BROKEN {where} of {label}:")
    for p in out["problems"][:20]:
        log(f"  {str(p['seq'] if p['seq'] is not None else '—'):>5}  {p['check']:<16} {p['detail']}")
    if len(out["problems"]) > 20:
        log(f"  … and {len(out['problems']) - 20} more")


def run_cli(db, args, resolve_client, log=print) -> int:
    """hubricon seal status | verify <client> [--global] [--witness X]... [--no-live] | sync [<client>].
    Exit 0 when intact, 1 when broken, 2 when the Seal is not there to check."""
    if args.action == "status":
        s = status(db)
        if s["status"] != "ready":
            log(f"The Seal is not running: {s['reason']}.")
            return 2
        log(f"The Seal — {s['entries']} entries on the global chain")
        log(f"  global head  {s['head']}")
        log(f"  last sealed  {s['last_sealed_at'] or '—'}")
        pub = s.get("published")
        if isinstance(pub, dict) and pub.get("head"):
            same = pub.get("head") == s["head"] and int(pub.get("entries") or 0) == s["entries"]
            log(f"  published    {'the same head, via ' + RPC + '()' if same else 'DIFFERENT: ' + str(pub)}")
        else:
            log(f"  published    {RPC}() not callable ({(pub or {}).get('error') if isinstance(pub, dict) else pub})")
        names = {}
        if s["clients"]:
            ids = [c for c in s["clients"] if c]
            for r in (db.table("clients").select("id, company_name, contact_email").in_("id", ids).execute().data
                      if ids else []):
                names[r["id"]] = r.get("company_name") or r.get("contact_email")
        for cid, c in s["clients"].items():
            name = names.get(cid) or ("(deleted client)" if cid is None else str(cid)[:8])
            log(f"  {name:<28} {c['entries']:>4} entries: {c['called']} called"
                + (f" ({c['late']} sealed late)" if c["late"] else "") + f", {c['measured']} measured")
        return 0

    if args.action == "verify":
        witnesses = getattr(args, "witness", None) or ()
        if getattr(args, "global_chain", False) or not args.client:
            out = verify(db, None, witnesses=witnesses)
            label = "the global chain"
        else:
            client = resolve_client(db, args.client)
            out = verify(db, client["id"], live=not getattr(args, "no_live", False), witnesses=witnesses)
            label = f"{client.get('company_name') or client.get('contact_email')}'s Record"
        if out["status"] in (TABLE_MISSING, UNAVAILABLE):
            log(f"Nothing to verify: {out['reason']}.")
            return 2
        if out["status"] == "empty":
            log(f"{label}: nothing sealed yet.")
            return 0
        log(f"{label}: {out['entries']} entries"
            + (f" — {out.get('called', 0)} called ({out.get('late', 0)} sealed late), {out.get('measured', 0)} measured"
               if out.get("scope") != "global" else
               (f", {out['redacted']} of them a deleted client's (leaf kept, words gone)" if out.get("redacted") else "")))
        log(f"  head {out.get('head')}")
        if out["status"] == "ok":
            log("OK — every entry matches its seal and the chain is unbroken"
                + ("; every measurement answers its promise, and the live rows still say what was sealed."
                   if out.get("scope") != "global" else "."))
            return 0
        _render_problems(out, label, log)
        return 1

    if args.action == "sync":
        clients = ([resolve_client(db, args.client)] if args.client
                   else db.table("clients").select("*").in_("status", ["pending", "active", "churned"]).execute().data)
        worst = 0
        for c in clients:
            res = catch_up(db, c["id"])
            name = c.get("company_name") or c.get("contact_email")
            if res["status"] in (TABLE_MISSING, UNAVAILABLE):
                log(f"Nothing sealed: {res['reason']}.")
                return 2
            log(f"  {name}: {res['status']}" + (f", {res['sealed']} entr{'y' if res['sealed'] == 1 else 'ies'} "
                                                 f"sealed late" if res["sealed"] else "")
                + (f" — refused: {res['reason']}" if res.get("reason") else ""))
            worst = max(worst, 1 if res["status"] in (FAILED, PARTIAL, REFUSED) else 0)
        return worst
    log(f"unknown action {args.action!r}")
    return 2
