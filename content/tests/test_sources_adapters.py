"""Each library read the same way (VISUAL_SPEC.md §6.3): recorded answers in,
candidates with full provenance out, and each library's accept list applied.
No network: tests/fixtures/sources/ holds trimmed real answers, keys never in them."""

import pytest

from hubricon_content import sources
from hubricon_content.shots import licence_ok
from hubricon_content.sources import commons, loc

from . import sources_fixture as fx

PROVENANCE = ("id", "source", "kind", "url", "file_url", "preview_url", "author", "credit", "retrieved", "rights")


def _search(tmp_path, monkeypatch, source, routes, query="warehouse shelf cartons close up", kind=None):
    fx.set_keys(monkeypatch)
    net = fx.make_net(tmp_path, routes)
    kind = kind or ("video" if source in ("pexels", "pixabay", "archive", "nara") else "image")
    return sources.search(source, query, kind, 40, net=net), net


def test_pexels_candidates_carry_full_provenance_and_the_key_stays_in_the_header(tmp_path, monkeypatch):
    found, net = _search(tmp_path, monkeypatch, "pexels", {"api.pexels.com": fx.fixture("pexels")})
    call = net.http.calls[0]
    assert call["headers"]["Authorization"] == fx.KEYS["PEXELS_API_KEY"] and "key" not in call["params"]
    assert call["params"]["per_page"] == 40 and call["params"]["size"] == "medium"
    c = found[1]
    assert all(c[k] for k in PROVENANCE)
    assert c["id"] == "pexels:6170323" and c["licence"] == "Pexels License" and c["credit"] == "Pexels"
    assert (c["width"], c["height"], c["fps"]) == (3840, 2160, 25.0)
    assert c["preview_url"].endswith("sd_426_240_25fps.mp4") and "uhd" in c["file_url"]
    assert c["title"] == "delivery guy searching for the parcel in the rack"


def test_pixabay_asks_for_filmed_footage_by_its_nouns_and_keeps_the_key_out_of_the_cache(tmp_path, monkeypatch):
    found, net = _search(tmp_path, monkeypatch, "pixabay", {"pixabay.com": fx.fixture("pixabay")})
    params = net.http.calls[0]["params"]
    assert params["q"] == "warehouse shelf cartons" and params["video_type"] == "film" and params["key"]
    assert fx.KEYS["PIXABAY_API_KEY"] not in "".join(p.read_text() for p in (tmp_path / "api").rglob("*.json"))
    film, anim = found
    assert film["id"] == "pixabay:91523" and film["fps"] is None and film["fps_from"] == "preview"
    assert (film["width"], film["height"]) == (3840, 2160) and film["preview_url"].endswith("_tiny.mp4")
    assert film["author_url"] and film["licence"] == "Pixabay Content License"
    assert anim["footage_type"] == "animation" and "amazon" in anim["tags"]


def test_the_library_of_congress_accepts_only_no_known_restrictions_on_publication(tmp_path, monkeypatch):
    found, net = _search(tmp_path, monkeypatch, "loc", {"loc.gov": fx.fixture("loc")}, query="bank teller window interior photograph")
    assert net.http.calls[0]["params"]["q"] == "bank teller window"            # the medium words go
    assert "User-Agent" in net.http.calls[0]["headers"] and "films@example.org" in net.http.calls[0]["headers"]["User-Agent"]
    by = {c["id"]: c for c in found}
    ok = by["loc:2011660924"]
    assert ok["licence"] == "No known restrictions on publication" and ok["rights"].startswith("No known restrictions on publication")
    assert ok["credit"] == "Library of Congress" and ok["date"] == "1908" and "Somerville" in ok["place"]
    assert ok["author"] == "Library of Congress" and ok["author_note"]       # no creator: credited to the institution
    habs = by["loc:ga0757"]
    assert habs["licence"] is None and "U.S. Government" in habs["rights"]    # a narrower statement is not accepted
    assert by["loc:03027422"]["licence"] is None


def test_loc_resolve_reads_the_master_tiff_size_from_its_header(tmp_path, monkeypatch):
    import struct
    head = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 2) + \
        struct.pack("<HHII", 256, 3, 1, 2400) + struct.pack("<HHII", 257, 4, 1, 1900) + b"\x00" * 64
    routes = {"tile.loc.gov/storage-services/master": fx.Response(content=head, status=206),
              "www.loc.gov/item/": fx.fixture("loc_item"), "www.loc.gov/photos": fx.fixture("loc")}
    found, net = _search(tmp_path, monkeypatch, "loc", routes, query="bank teller")
    c = next(c for c in found if c["id"] == "loc:2011660924")
    sources.resolve(c, net)
    assert (c["width"], c["height"]) == (2400, 1900) and c["file_url"].endswith("u.tif")
    assert loc.tiff_size(head) == (2400, 1900) and loc.tiff_size(b"not a tiff") is None


def test_smithsonian_is_cc0_only_and_keeps_its_key_out(tmp_path, monkeypatch):
    found, net = _search(tmp_path, monkeypatch, "smithsonian", {"api.si.edu": fx.fixture("smithsonian")}, query="ledger photograph")
    assert net.http.calls[0]["params"]["q"].startswith("ledger AND online_media_type:Images")
    c = found[0]
    assert c["licence"] == "CC0" and c["width"] == 7940 and c["author"] == "Benjamin Franklin, American, 1706 - 1790"
    assert c["credit"].startswith("Smithsonian Institution") and c["preview_url"].endswith("&max=800")
    body = fx.fixture("smithsonian")
    body["response"]["rows"][0]["content"]["descriptiveNonRepeating"]["online_media"]["media"][0]["usage"]["access"] = "Usage conditions apply"
    found, _ = _search(tmp_path / "b", monkeypatch, "smithsonian", {"api.si.edu": body}, query="ledger")
    assert found[0]["licence"] is None


def test_commons_accepts_public_domain_cc0_and_cc_by_and_refuses_the_rest(tmp_path, monkeypatch):
    found, _ = _search(tmp_path, monkeypatch, "commons", {"commons.wikimedia.org": fx.fixture("commons")}, query="bank teller")
    lic = {c["rights"]: c["licence"] for c in found}
    assert lic["Public domain"] == "Public domain" and lic["CC0"] == "CC0" and lic["CC BY 2.0"] == "CC BY 2.0"
    assert lic["CC BY-SA 4.0"] is None and lic["No restrictions"] is None
    assert all(c["url"].startswith("https://commons.wikimedia.org/wiki/File:") and "?" not in c["file_url"] for c in found)
    assert commons.licence_of({"License": "cc-by-nc-4.0"}) is None
    assert commons.licence_of({"License": "pd", "NonFree": "true"}) is None
    assert commons.licence_of({"License": "pd", "Restrictions": "trademarked"}) is None


def test_the_archive_takes_public_domain_marks_only_and_resolves_the_master(tmp_path, monkeypatch):
    routes = {"advancedsearch": fx.fixture("archive"), "archive.org/metadata/": fx.fixture("archive_meta")}
    found, net = _search(tmp_path, monkeypatch, "archive", routes, query="steel mill")
    assert "collection:prelinger" in net.http.calls[0]["params"]["q"]
    marked, unmarked = found
    assert marked["licence"] == "Public domain" and unmarked["licence"] is None
    sources.resolve(unmarked, net)
    assert unmarked["licence"] == "Public domain"                             # the item record carries the mark
    assert (unmarked["width"], unmarked["height"], unmarked["fps"]) == (2048, 1536, 24.0)
    assert unmarked["file_url"].endswith(".mov") and unmarked["preview_url"].endswith(".mp4")
    assert unmarked["duration"] == pytest.approx(590.58)
    found, net = _search(tmp_path / "n", monkeypatch, "nara", routes, query="steel mill")
    assert "identifier:gov.archives*" in net.http.calls[0]["params"]["q"] and found[0]["source"] == "nara"


def test_every_accepted_licence_passes_the_plan_s_accept_list():
    for lic in ("Pexels License", "Pixabay Content License", "No known restrictions on publication", "CC0",
                "Public domain", "CC BY 4.0"):
        assert licence_ok(lic), lic
    for lic in ("CC BY-SA 4.0", "CC BY-NC 2.0", "fair use", "unknown"):
        assert not licence_ok(lic), lic


def test_a_missing_key_is_named_exactly(monkeypatch):
    for k in fx.KEYS:
        monkeypatch.delenv(k, raising=False)
    assert sources.missing_keys("pexels") == ["PEXELS_API_KEY"]
    assert sources.missing_keys("smithsonian") == ["SMITHSONIAN_API_KEY"]
    assert sources.missing_keys("loc") == ["CONTENT_CONTACT_EMAIL"]
    with pytest.raises(KeyError):
        sources.adapter("amazon")
