"""§6.4's automatic filters on synthetic media made here with ffmpeg and Pillow:
resolution, frame rate, length, the luma band of §3.2, cuts by scdet, faces
(the detector monkeypatched), text, duplicates by perceptual hash, the licence
and the record's own checks. Each test names the rule it holds."""

import pytest

from hubricon_content.sources import filters

from . import sources_fixture as fx


def ctx(kind="footage", style="footage-insert", length=5.0, specific=None):
    return filters.context({"id": "s001", "kind": kind, "style": style, "start": 0.0, "end": length, "specific": specific})


def cand(source="pexels", kind="video", **kw):
    c = {"id": f"{source}:1", "source": source, "kind": kind, "url": "https://example.org/1", "author": "A. Maker",
         "licence": {"pexels": "Pexels License", "pixabay": "Pixabay Content License"}.get(source, "Public domain"),
         "rights": "stated", "width": 3840, "height": 2160, "fps": 30.0, "duration": 12.0, "title": "cartons on a shelf",
         "query": "cartons shelf"}
    c.update(kw)
    return c


def checked(c, x, prior=None):
    filters.precheck(c, x, prior) and filters.metadata(c, x)
    return filters.finish(c)


def has(c, text):
    assert any(text in r for r in c.get("rejected_because", [])), c.get("rejected_because")


# ── the record ──
def test_a_clean_record_passes():
    assert checked(cand(), ctx())["passed_filters"]


def test_licence_and_provenance_are_required():
    c = checked(cand(licence=None, rights="CC BY-SA 4.0"), ctx())
    has(c, "licence not on the accept list: CC BY-SA 4.0")
    has(checked(cand(author=None), ctx()), "provenance lacks author")


def test_nothing_that_names_amazon_and_nothing_generated():
    has(checked(cand(source="pixabay", tags=["amazon", "box"]), ctx()), "names Amazon")
    has(checked(cand(source="pixabay", footage_type="animation"), ctx()), "generated or animated")
    has(checked(cand(source="pixabay", ai_generated=True), ctx()), "generated or animated")


def test_a_stock_clip_whose_title_or_tags_name_a_cliche_is_refused():
    has(checked(cand(title="coffee mugs between a laptop and a calendar", query="desk calendar"), ctx()), "'laptop', a banned cliché")
    has(checked(cand(source="pixabay", title="notebook", tags=["notebook", "desk", "laptop"], query="notebook desk"), ctx()), "banned cliché")
    old = checked(cand(source="loc", kind="image", title="Bank teller counting cash, 1939", width=3000, height=2200,
                       query="bank teller photograph"), ctx(kind="still", style="still-push"))
    assert old["passed_filters"] and old["checks"]["cliche_words"] == ["cash"]   # an archival record is noted, not refused


def test_a_pixabay_clip_must_name_half_of_the_query_s_nouns():
    has(checked(cand(source="pixabay", title="lipstick, bride", tags=["lipstick"], query="cartons shelf close up"), ctx()),
        "fewer than half of the query's nouns")
    c = checked(cand(source="pixabay", title="boxes", tags=["carton", "warehouse"], query="cartons shelf close up"), ctx())
    assert c["passed_filters"] and c["checks"]["relevance"] == 0.5
    ship = cand(source="pixabay", title="container, cargo", tags=["cargo", "delivery", "loading"], query="delivery van loading parcels")
    has(checked(ship, ctx()), "fewer than half")       # "loading" is a verb, and one noun of three is not enough
    assert checked(cand(title="warehouse employee loading delivery van", query="delivery van loading parcels"), ctx())["passed_filters"]


def test_a_named_subject_needs_archival_evidence_that_names_it():
    x = ctx(kind="still", style="still-push", specific="Woolworth")
    has(checked(cand(), x), "only archival evidence may show it")
    has(checked(cand(source="loc", kind="image", title="A dime store"), x), "does not name 'Woolworth'")
    assert checked(cand(source="loc", kind="image", title="F. W. Woolworth store, 1915", width=3000, height=2200,
                        query="Woolworth store photograph"), x)["passed_filters"]


def test_an_asset_in_the_usage_window_is_refused():
    has(checked(cand(), ctx(), prior={"pexels:1": "in 03-reorder-point, inside the last ten films"}), "03-reorder-point")


# ── the full rendition ──
def test_footage_is_full_hd_and_archival_film_at_least_720p():
    has(checked(cand(width=1280, height=720), ctx()), "footage is at least 1920×1080")
    assert checked(cand(source="archive", width=1280, height=960, fps=18.0), ctx())["passed_filters"]
    has(checked(cand(source="archive", width=640, height=480), ctx()), "archival film is at least 1280×720")


def test_frame_rate_and_length():
    has(checked(cand(fps=15.0), ctx()), "15 fps")
    has(checked(cand(duration=5.5), ctx(length=5.0)), "the shot needs 6.0 s, its length plus one")
    assert checked(cand(duration=6.0), ctx(length=5.0))["passed_filters"]


def test_stills_long_edge_style_floor_and_upscale():
    x = ctx(kind="still", style="still-push", length=6.0)
    has(checked(cand(source="loc", kind="image", width=1536, height=1218), x), "at least 1,600 px")
    has(checked(cand(source="loc", kind="image", width=1800, height=1200), x), "still-push needs a source at least 2,000 px")
    has(checked(cand(source="loc", kind="image", width=1200, height=2000), x), "would be enlarged 1.79×")
    has(checked(cand(source="commons", kind="image", width=2400, height=1800), ctx(kind="still", style="still-reveal")),
        "still-reveal needs a source at least 2,600 px on its width")
    assert checked(cand(source="loc", kind="image", width=3000, height=2200), x)["passed_filters"]
    assert checked(cand(source="loc", kind="image", width=1700, height=1300), ctx(kind="archive", style="archive-framed"))["passed_filters"]


def test_the_fps_rule_admits_24_and_25_only_when_nothing_as_good_exists():
    x = ctx()
    fast = [filters.finish(dict(cand(fps=30.0), id=f"pexels:{i}", checks={"relevance": 0.5}, rejected_because=[]))
            for i in range(3)]
    slow = filters.finish(dict(cand(fps=25.0), id="pexels:9", checks={"relevance": 0.5}, rejected_because=[]))
    filters.fps_rule(fast + [slow], x)
    has(slow, "25 fps: this shot has 3 candidates at 30 or 60 fps")
    slow = filters.finish(dict(cand(fps=25.0), id="pexels:9", checks={"relevance": 0.5}, rejected_because=[]))
    filters.fps_rule(fast[:2] + [slow], x)
    assert slow["passed_filters"] and "admitted" in slow["checks"]["fps_note"]
    better = filters.finish(dict(cand(fps=25.0), id="pexels:8", checks={"relevance": 1.0}, rejected_because=[]))
    filters.fps_rule(fast + [better], x)                     # smooth footage of the wrong thing does not win
    assert better["passed_filters"]


# ── the preview ──
@pytest.fixture
def no_faces(monkeypatch):
    monkeypatch.setattr(filters, "detect_faces", lambda bgr: [])
    monkeypatch.setattr(filters.shutil, "which", lambda name: None)


def test_luma_band_from_signalstats(tmp_path, no_faces):
    x = ctx(kind="archive", style="archive-framed")
    lo, hi = filters.LUMA_BAND
    assert 97 <= lo <= 98 and 178 <= hi <= 179
    for grey, ok, why in ((128, True, None), (30, False, "night or low-key"), (252, False, "outside 97–179")):
        p = fx.still(tmp_path / f"g{grey}.jpg", size=(1800, 1200), grey=grey)
        a = filters.analyse(p, "image")
        c = cand(source="loc", kind="image", width=1800, height=1200)
        filters.precheck(c, x) and filters.metadata(c, x)
        assert filters.media(c, a, x) is ok, (grey, a["luma"], c["rejected_because"])
        if why:
            has(c, why)
    assert a["ocr_words"] is None


def test_scdet_finds_a_hard_cut_and_the_take_must_fit_the_shot(tmp_path, no_faces):
    p = fx.clip(tmp_path / "cut.mp4", "testsrc2", seconds=8.0, then="smptehdbars")
    a = filters.analyse(p, "video")
    assert len(a["cuts"]) == 1 and a["cuts"][0] == pytest.approx(4.0, abs=0.1)
    assert a["longest_take"] == pytest.approx(4.0, abs=0.1) and a["preview"]["fps"] == pytest.approx(30)
    long_shot = cand(duration=8.0)
    filters.precheck(long_shot, ctx(length=5.0))
    assert not filters.media(long_shot, a, ctx(length=5.0))
    has(long_shot, "no continuous take of 5.0 s")
    short_shot = cand(duration=8.0)
    filters.precheck(short_shot, ctx(length=3.0))
    assert filters.media(short_shot, a, ctx(length=3.0)), short_shot["rejected_because"]
    assert short_shot["checks"]["text"] == filters.OCR_UNAVAILABLE
    assert (tmp_path / "cut.mp4.strip.jpg").exists()


def test_a_preview_without_a_frame_rate_takes_it_from_the_file(tmp_path, no_faces):
    p = fx.clip(tmp_path / "pal.mp4", "testsrc2", rate=25, seconds=4.0)
    a = filters.analyse(p, "video")
    c = cand(source="pixabay", fps=None, duration=None)
    filters.precheck(c, ctx(length=2.0))
    filters.media(c, a, ctx(length=2.0))
    assert c["fps"] == 25 and c["fps_from"] == "preview" and c["duration"] == pytest.approx(4.0, abs=0.1)


def test_faces_refuse_stock_but_not_the_archival_portrait_of_the_named_subject(tmp_path, monkeypatch):
    monkeypatch.setattr(filters, "detect_faces", lambda bgr: [(0.03, 0.95)])
    p = fx.still(tmp_path / "face.jpg", size=(2600, 1800), grey=128)
    a = filters.analyse(p, "image")
    assert a["max_face"] == pytest.approx(0.03)
    stock = cand()
    filters.precheck(stock, ctx())
    assert not filters.media(stock, a, ctx())
    has(stock, "a face covers 3.0% of the frame")
    x = ctx(kind="still", style="still-push", specific="Woolworth")
    portrait = cand(source="loc", kind="image", title="Frank W. Woolworth, portrait", width=2600, height=1800,
                    query="Frank Woolworth portrait photograph")
    filters.precheck(portrait, x)
    assert filters.media(portrait, a, x), portrait["rejected_because"]
    assert "§13.1" in portrait["checks"]["faces"]["exempt"]
    anonymous = cand(source="loc", kind="image", width=2600, height=1800)
    filters.precheck(anonymous, ctx(kind="still", style="still-push"))
    assert not filters.media(anonymous, a, ctx(kind="still", style="still-push"))


def test_small_faces_in_a_distant_crowd_are_fine(tmp_path, monkeypatch):
    monkeypatch.setattr(filters, "detect_faces", lambda bgr: [(0.004, 0.9), (0.002, 0.9)])
    a = filters.analyse(fx.still(tmp_path / "crowd.jpg", size=(1800, 1200), grey=128), "image")
    x = ctx(kind="archive", style="archive-framed")
    c = cand(source="loc", kind="image", width=1800, height=1200)
    filters.precheck(c, x)
    assert filters.media(c, a, x), c["rejected_because"]


def test_duplicates_by_perceptual_hash(tmp_path, no_faces):
    one = filters.analyse(fx.still(tmp_path / "a.jpg", pattern=1), "image")
    same = filters.analyse(fx.still(tmp_path / "b.png", size=(900, 600), pattern=1), "image")   # resized, re-encoded
    other = filters.analyse(fx.still(tmp_path / "c.jpg", pattern=0), "image")
    assert filters.phash_distance(one["phash"], same["phash"]) < filters.PHASH_DUP
    assert filters.phash_distance(one["phash"], other["phash"]) >= filters.PHASH_DUP
    x = ctx(kind="archive", style="archive-framed")
    c = cand(source="loc", kind="image", id="loc:2", width=1800, height=1200)
    filters.precheck(c, x)
    assert not filters.media(c, same, x, {"pexels:7": (one["phash"], "picked for s004")})
    has(c, "a duplicate of pexels:7 picked for s004")
    d = cand(source="loc", kind="image", id="loc:3", width=1800, height=1200)
    filters.precheck(d, x)
    filters.media(d, other, x, {"pexels:7": (one["phash"], "picked for s004")})
    assert "duplicate" not in d["checks"]


def test_the_analysis_is_cached_beside_the_preview(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(filters, "detect_faces", lambda bgr: calls.append(1) or [])
    p = fx.still(tmp_path / "x.jpg", grey=128)
    filters.analyse(p, "image", "abc")
    filters.analyse(p, "image", "abc")
    assert len(calls) == 1
    filters.analyse(p, "image", "a-different-file")          # a new preview under the same name is analysed again
    assert len(calls) == 2


def test_a_then_and_now_needs_a_dated_then():
    x = ctx(kind="split", style="split-then-now", length=6.0)
    has(checked(cand(source="loc", kind="image", side="then", width=3000, height=2000), x), "needs a date in its record")
    assert checked(cand(source="loc", kind="image", side="then", date="1908", width=3000, height=2000), x)["passed_filters"]


def test_an_archival_record_must_be_about_the_query_s_nouns_not_mention_them():
    x = ctx(kind="still", style="still-push", length=6.0)
    clipping = cand(source="smithsonian", kind="image", title="Homemade Christmas Candies", width=3000, height=2200,
                    description="a clipping kept between the pages of a household ledger", query="accountant reading ledger photograph")
    has(checked(clipping, x), "title and subjects name none of the query's nouns")
    ledger = cand(source="smithsonian", kind="image", title="Ledger page from an account book", width=3000, height=2200,
                  query="accountant reading ledger photograph")
    assert checked(ledger, x)["passed_filters"]


def test_a_catalogue_s_way_of_writing_a_name_still_names_it():
    from hubricon_content.shots import names
    assert names("Robert E. Wood", "WOOD, ROBERT E. Portrait, 1937")
    assert names("Robert E. Wood", "R.E. Wood, President of Sears")
    assert names("Robert E. Wood", "R. E. Wood at his desk")
    assert not names("Robert E. Wood", "Grant Wood, painter")
    assert names("Sears, Roebuck and Company", "Mail order plant of Sears, Roebuck and Company")
    assert not names("Adams Express Company", "Adams County courthouse; express train")
