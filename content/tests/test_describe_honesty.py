"""A film's description says truthfully who narrates it and where its numbers come from, and every
link carries the film's source code (so a booked call can be traced to it)."""
from pathlib import Path

from hubricon_content import describe, qa


def test_the_disclosure_says_whose_voice_it_is():
    assert qa.disclosure_for("own") == "Narrated by Hagen Simmons, in his own voice."
    assert "not for publishing" in qa.disclosure_for(None) and "not for publishing" in qa.disclosure_for("placeholder")
    assert qa.PUBLISHABLE_VOICES == ("own",)


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


def test_credits_come_from_the_picks_provenance_only():
    plan = {"shots": [
        {"kind": "footage", "asset": {"id": "pexels:1", "source": "pexels", "author": "Ana Lima"}},
        {"kind": "footage", "asset": {"id": "pixabay:2", "source": "pixabay", "author": "Kim Ode"}},
        {"kind": "still", "asset": {"id": "loc:3", "source": "loc", "title": "Mail-order warehouse, 1925", "licence": "No known restrictions on publication"}},
        {"kind": "texture", "asset": {"id": "higgsfield:4", "source": "higgsfield"}},
        {"kind": "number"}]}
    text = describe.credits(plan)
    assert "Pexels (pexels.com) and Pixabay (pixabay.com)" in text and "Ana Lima, Kim Ode" in text
    assert "Mail-order warehouse, 1925, Library of Congress (No known restrictions on publication)" in text
    assert "AI-generated" in text
    assert describe.credits({"shots": [{"kind": "number"}]}) == ""
