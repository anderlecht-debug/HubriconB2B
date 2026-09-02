"""Bytes -> DataFrame, tolerant of how Amazon actually exports files:
UTF-8 BOMs, cp1252 from older accounts, tab-delimited .txt, and preamble
lines before the real header (the Payments date-range export opens with
seven prose definitions, some of them containing commas)."""

import csv
import io
from collections import Counter

import pandas as pd

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
DELIMITERS = (",", "\t", ";")
HEADER_SCAN_LINES = 20
MODAL_SAMPLE_LINES = 5


class ReadError(Exception):
    pass


def _decode(data: bytes) -> str:
    for enc in ENCODINGS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ReadError("File is not text in any supported encoding")


def _detect_delimiter(line: str) -> str:
    counts = {d: line.count(d) for d in DELIMITERS}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _field_count(line: str, delimiter: str) -> int:
    """Quote-aware, so a quoted sentence with commas counts as one field."""
    try:
        return len(next(csv.reader([line], delimiter=delimiter)))
    except (csv.Error, StopIteration):
        return 0


def _find_header(lines: list[str]) -> int:
    """The header is the first line (within the top 20) that splits into 3+
    fields AND whose field count matches the modal field count of the next
    five non-blank lines — a prose preamble line with commas fails the second
    test because the rows beneath it are wider. If no line passes both (e.g.
    a header with a single ragged row under it) the first 3+ field line wins,
    which is the pre-modal behaviour."""
    nonblank = [i for i, line in enumerate(lines) if line.strip()]
    fallback = None
    for pos, i in enumerate(nonblank):
        if i >= HEADER_SCAN_LINES:
            break
        delimiter = _detect_delimiter(lines[i])
        n = _field_count(lines[i], delimiter)
        if n < 3:
            continue
        if fallback is None:
            fallback = i
        following = nonblank[pos + 1 : pos + 1 + MODAL_SAMPLE_LINES]
        if following:
            counts = Counter(_field_count(lines[j], delimiter) for j in following)
            if counts.most_common(1)[0][0] == n:
                return i
    if fallback is None:
        raise ReadError("Could not find a header row in the first 20 lines")
    return fallback


def read_table(data: bytes) -> pd.DataFrame:
    """Everything comes back as strings; typed cleaning happens per column."""
    text = _decode(data)
    lines = text.splitlines()
    header_idx = _find_header(lines)

    delimiter = _detect_delimiter(lines[header_idx])
    body = "\n".join(lines[header_idx:])
    try:
        df = pd.read_csv(io.StringIO(body), sep=delimiter, dtype=str, keep_default_na=False)
    except Exception as err:
        raise ReadError(f"CSV parse failed: {err}") from err
    if df.empty:
        raise ReadError("File contains a header but no data rows")
    df.columns = [str(c) for c in df.columns]
    return df
