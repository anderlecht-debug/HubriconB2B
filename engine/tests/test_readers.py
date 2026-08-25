import csv
import io
from pathlib import Path

import pytest

from hubricon_engine.ingest.readers import ReadError, read_table

FIXTURES = Path(__file__).parent / "fixtures"


def _tab_bom_variant(csv_path: Path) -> bytes:
    """Re-encode a comma fixture as BOM-prefixed tab-delimited text."""
    rows = list(csv.reader(csv_path.read_text().splitlines()))
    out = io.StringIO()
    csv.writer(out, delimiter="\t").writerows(rows)
    return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")


def test_reads_clean_csv():
    df = read_table((FIXTURES / "business_report_clean.csv").read_bytes())
    assert len(df) == 3
    assert "(Child) ASIN" in df.columns


def test_tab_delimited_with_bom_matches_csv():
    clean = read_table((FIXTURES / "business_report_clean.csv").read_bytes())
    tabbed = read_table(_tab_bom_variant(FIXTURES / "business_report_clean.csv"))
    assert list(clean.columns) == list(tabbed.columns)
    assert clean.to_dict(orient="records") == tabbed.to_dict(orient="records")


def test_cp1252_fallback():
    data = "sku,asin,notes\nA-1,B0X,café supplier\n".encode("cp1252")
    df = read_table(data)
    assert df.iloc[0]["notes"] == "café supplier"


def test_preamble_skipped():
    data = b'"Report generated 2026-08-25"\n\nsku,asin,units\nA-1,B0X,5\n'
    df = read_table(data)
    assert list(df.columns) == ["sku", "asin", "units"]


def test_headerless_garbage_raises():
    with pytest.raises(ReadError):
        read_table(b"just one field\nanother\n")
