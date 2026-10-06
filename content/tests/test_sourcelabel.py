"""A figure frame's source line reads as a name, never a URL, never a guess."""
from hubricon_content import sourcelabel as sl


def test_known_titles_publishers_and_covered_sources():
    assert sl.one("https://archive.org/details/parcelpostreport00unit (Joint Committee…)").startswith("Joint Committee")
    assert sl.one("https://www.prc.gov/sites/default/files/papers/enterprise.pdf") == "Postal Regulatory Commission"
    assert sl.one("https://example.org/x") == "example.org"
    assert sl.one("MARGIN.DECOMP on Tarnhollow demo data (seed 42)") is None
    assert sl.one("Hubricon's public-data case study (data/case-study.json; …)") is None
    assert sl.one("Amazon's published US FBA fee card, 2026 non-peak schedule (effective January 15, 2026), as recorded in ratecard.json") \
        == "Amazon's published US FBA fee card, 2026 non-peak schedule"


def test_label_joins_distinct_sources():
    facts = {"a": {"source": "https://about.usps.com/publications/pub100.pdf"},
             "b": {"source": "https://about.usps.com/publications/pub100.pdf"},
             "c": {"source": "https://www.nber.org/system/files/chapters/c10234/c10234.pdf"}}
    assert sl.label(["a", "b", "c"], facts) == "USPS, The United States Postal Service: An American History · Raff and Temin, NBER"
    assert sl.label([], facts) is None
