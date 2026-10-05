"""A film's description says truthfully who narrates it and where its numbers come from, and every
link carries the film's source code (so a booked call can be traced to it)."""
from pathlib import Path

from hubricon_content import describe, qa


def test_the_disclosure_matches_the_voice_and_never_claims_a_clone_that_is_not_one():
    assert qa.disclosure_for("own") == "Narrated by Hagen Simmons, in his own voice."
    assert "AI clone" in qa.disclosure_for("founder")
    assert "not for publishing" in qa.disclosure_for(None)
    assert "AI clone" not in qa.disclosure_for("own")
    assert set(qa.PUBLISHABLE_VOICES) == {"own", "founder", "library"}
    # the library voice the founder chose is never passed off as his
    assert "Hagen Simmons's voice" not in qa.disclosure_for("library") and "AI voice" in qa.disclosure_for("library")


def test_the_data_line_names_the_films_own_source_with_its_label():
    store = describe.data_line({"models": ["store_study"]})
    assert "CC BY 4.0" in store and "10.24432/C5CG6D" in store and "Not a client · Not a result" in store
    assert "public page" in describe.data_line({"models": ["case_study", "ratecard"]})
    assert "Tarnhollow" in describe.data_line({"models": ["margin"]})


def test_no_description_offers_what_the_site_no_longer_has():
    src = Path(describe.__file__).read_text(encoding="utf-8")
    written = [ln for ln in src.splitlines() if 'f"' in ln and not ln.strip().startswith("#")]   # what a description says
    for gone in ("Teardown", "/method", "Reimbursement Playbook"):
        assert not any(gone in ln for ln in written), gone
    assert "?src={code}" in src
