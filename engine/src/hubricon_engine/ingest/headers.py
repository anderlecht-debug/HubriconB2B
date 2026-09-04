"""Table-driven header mapping. Amazon renames and localizes columns between
accounts and years, so every parser matches on normalized names against a
synonym list — this module is the single place those quirks accumulate."""

import hashlib
import re
from datetime import date, datetime

import pandas as pd


class IngestError(Exception):
    pass


def normalize(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).lower().replace("﻿", ""))


def clean_str(value: str) -> str | None:
    v = str(value).strip()
    return v or None


def clean_money(value: str) -> float | None:
    """Handles 'US$1,234.56', '$1,234.56', '1.234,56' and '(12.34)' negatives."""
    v = str(value).strip()
    if not v or v.lower() in ("n/a", "na", "-", "--"):
        return None
    negative = v.startswith("(") and v.endswith(")")
    v = re.sub(r"[^\d.,\-]", "", v.strip("()"))
    if not v:
        return None
    if "," in v and "." in v:
        # whichever separator comes last is the decimal point
        v = v.replace(",", "") if v.rindex(".") > v.rindex(",") else v.replace(".", "").replace(",", ".")
    elif "," in v:
        # lone comma: decimal if it looks like cents, thousands otherwise
        v = v.replace(",", ".") if re.fullmatch(r"-?\d+,\d{1,2}", v) else v.replace(",", "")
    try:
        n = float(v)
    except ValueError:
        return None
    return -n if negative else n


def clean_int(value: str) -> int | None:
    n = clean_money(value)
    return None if n is None else int(round(n))


def clean_pct(value: str) -> float | None:
    return clean_money(str(value).replace("%", ""))



def clean_bool(value: str) -> bool | None:
    """'Yes'/'No', 'true'/'false', '1'/'0' -> bool; anything else -> None."""
    v = str(value).strip().lower()
    if v in ("yes", "y", "true", "t", "1"):
        return True
    if v in ("no", "n", "false", "f", "0"):
        return False
    return None


def as_int(value) -> int | None:
    """pandas promotes an int column that also holds blanks to float (2 -> 2.0)
    on the way through map_columns; restore int so JSON payloads and row-key
    hashes are identical whether or not a file happened to contain a blank."""
    return None if value is None else int(value)


# --- dates ------------------------------------------------------------------
# Amazon exports mix 2026-07-14, 2026-07-14T10:21:00+00:00, 14.07.2026 (EU
# accounts), 7/14/2026, "Jul 14, 2026" and Payments' "Jul 1, 2026 3:12:44 AM
# PDT" — sometimes within one account. Wall-clock semantics throughout: a
# timezone name or offset is dropped, never converted, so the date a seller
# sees in Seller Central is the date stored. Blank -> None; anything
# unrecognized raises rather than guessing.

_BLANKS = {"", "n/a", "na", "-", "--", "null", "none"}
_TZ_SUFFIX = re.compile(r"\s+(?!(?:AM|PM)$)(?:[A-Z]{2,5}|(?:UTC|GMT)[+-]\d{1,2}(?::\d{2})?)$")
_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?:\s+(.*))?$")
_DOT = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(.*))?$")
_YEAR_SPLIT = re.compile(r"^(.*?\d{4})(?:\s+(.*))?$")
_DATE_FORMATS = (
    "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%d %b %Y", "%d %B %Y",
    "%d-%b-%Y", "%Y/%m/%d", "%Y.%m.%d", "%d-%m-%Y",
)
_TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p")


def _safe_date(year: int, month: int, day: int, original: str) -> date:
    try:
        return date(year, month, day)
    except ValueError as err:
        raise IngestError(f"Unrecognized date {original!r}") from err


def _with_time(day: date, rest: str | None, original: str) -> datetime:
    rest = (rest or "").strip()
    if not rest:
        return datetime(day.year, day.month, day.day)
    for fmt in _TIME_FORMATS:
        try:
            return datetime.combine(day, datetime.strptime(rest, fmt).time())
        except ValueError:
            continue
    raise IngestError(f"Unrecognized time of day in {original!r}")


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    v = re.sub(r"\s+", " ", str(value).strip())
    if v.lower() in _BLANKS:
        return None
    v = _TZ_SUFFIX.sub("", v)
    try:
        # 2026-07-14, 2026-07-14 10:21, ...T10:21:00+00:00, Shopify's
        # "2026-07-03 14:22:10 -0400": an offset is dropped like a zone name
        return datetime.fromisoformat(v).replace(tzinfo=None)
    except ValueError:
        pass
    if m := _SLASH.match(v):
        a, b, year, rest = m.groups()
        a, b = int(a), int(b)
        month, day = (b, a) if a > 12 else (a, b)  # US order unless that is impossible
        y = int(year) if len(year) == 4 else 2000 + int(year)
        return _with_time(_safe_date(y, month, day, v), rest, v)
    if m := _DOT.match(v):
        day, month, year, rest = m.groups()
        return _with_time(_safe_date(int(year), int(month), int(day), v), rest, v)
    # "<date> <time>": split after the 4-digit year ("Jul 1, 2026 3:12:44 AM"),
    # else at the first space, else treat the whole string as a date.
    heads = [(v, None)]
    if " " in v:
        heads.insert(0, tuple(v.split(" ", 1)))
    if m := _YEAR_SPLIT.match(v):
        heads.insert(0, (m.group(1), m.group(2)))
    for head, rest in heads:
        for fmt in _DATE_FORMATS:
            try:
                day = datetime.strptime(head, fmt).date()
            except ValueError:
                continue
            return _with_time(day, rest, v)
    raise IngestError(f"Unrecognized date {value!r}")


def to_iso_date(value) -> str | None:
    dt = parse_datetime(value)
    return None if dt is None else dt.date().isoformat()


def to_iso_datetime(value) -> str | None:
    """Full timestamp when the source carries one, else midnight of the date."""
    dt = parse_datetime(value)
    return None if dt is None else dt.isoformat()


def is_total_row(value) -> bool:
    """Google Ads downloads close with "Total: Account" / "Total: Filtered
    campaigns" trailer lines in the first column; they are sums, not rows.

    The colon is load-bearing (2026-09-04): a bare `startswith("total")`
    also swallows "total gym mat" and a campaign called "Total Store", which
    is silent data loss on exactly the search-terms report the ad model
    reads. Google's trailers are always "Total:" or the bare word."""
    v = str(value or "").strip().lower()
    return v == "total" or v.startswith("total:")


def row_key(*parts) -> str:
    """sha1 over a row's natural-key fields joined by '|' (None -> ''). The
    unique constraint pairs it with client_id, so it needs to be stable across
    re-uploads of the same export, not globally unique."""
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()

def map_columns(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """spec: canonical -> {"synonyms": [normalized...], "required": bool, "cleaner": fn}.
    Returns a frame of canonical columns; raises listing the headers actually
    found when a required column is missing (so a synonym can be added and the
    upload re-parsed)."""
    by_norm = {}
    for col in df.columns:
        by_norm.setdefault(normalize(col), col)

    out = pd.DataFrame(index=df.index)
    missing = []
    for canonical, rule in spec.items():
        source = next((by_norm[s] for s in rule["synonyms"] if s in by_norm), None)
        if source is None:
            if rule.get("required"):
                missing.append(canonical)
            else:
                out[canonical] = None
            continue
        out[canonical] = df[source].map(rule["cleaner"])
    if missing:
        raise IngestError(
            f"Missing required column(s) {missing}; file headers were: {list(df.columns)}"
        )
    # Series.map turns a cleaner's None into NaN, which is not JSON-compliant
    # and would poison the PostgREST payload — normalize back to None.
    return out.astype(object).where(pd.notnull(out), None)


def dedupe_last(rows: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
    """Postgres rejects an upsert batch that hits the same key twice, and
    Amazon files do repeat rows — keep the last occurrence."""
    seen: dict[tuple, dict] = {}
    for row in rows:
        seen[tuple(row.get(k) for k in key_fields)] = row
    return list(seen.values())
