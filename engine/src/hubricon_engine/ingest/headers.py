"""Table-driven header mapping. Amazon renames and localizes columns between
accounts and years, so every parser matches on normalized names against a
synonym list — this module is the single place those quirks accumulate."""

import re

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
    return out


def dedupe_last(rows: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
    """Postgres rejects an upsert batch that hits the same key twice, and
    Amazon files do repeat rows — keep the last occurrence."""
    seen: dict[tuple, dict] = {}
    for row in rows:
        seen[tuple(row.get(k) for k in key_fields)] = row
    return list(seen.values())
