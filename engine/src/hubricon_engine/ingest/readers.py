"""Bytes -> DataFrame, tolerant of how Amazon actually exports files:
UTF-8 BOMs, cp1252 from older accounts, tab-delimited .txt, and the odd
preamble line before the real header."""

import io

import pandas as pd

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
DELIMITERS = (",", "\t", ";")


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


def read_table(data: bytes) -> pd.DataFrame:
    """Everything comes back as strings; typed cleaning happens per column."""
    text = _decode(data)
    lines = text.splitlines()

    # Header = first line that splits into 3+ fields; anything above is preamble.
    header_idx = None
    for i, line in enumerate(lines[:20]):
        if not line.strip():
            continue
        if len(line.split(_detect_delimiter(line))) >= 3:
            header_idx = i
            break
    if header_idx is None:
        raise ReadError("Could not find a header row in the first 20 lines")

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
