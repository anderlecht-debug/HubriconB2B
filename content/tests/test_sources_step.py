"""The `source` step on a tiny plan (VISUAL_SPEC.md §6, §7.2), with the libraries
replaced by a local catalogue of synthetic clips and stills served through the
real cache, counter and downloader. No network. Also the usage ledger (§6.7)
and the contact sheet."""

import json
import shutil

import pytest

from hubricon_content import shots as shotmod
from hubricon_content import sourcing, sources
from hubricon_content.sources import filters, sheet, usage

from . import sources_fixture as fx

SLUG = "99-sourcing-test"


def plan() -> dict:
    def shot(sid, start, end, room, kind, style, **kw):
        return {"id": sid, "beat": "b01", "start": start, "end": end, "says": f"words under {sid}", "room": room,
                "kind": kind, "style": style, "intent": f"{style} for {sid}", "params": {}, "overlay": {}, "reveals": [],
                "on": None, "fallback": "paper:kinetic", "asset": None, **kw}
    return {"slug": SLUG, "mode": "explainer", "fps": 30, "shots": [
        shot("s001", 0.0, 4.0, "world", "footage", "footage-insert", sources=["pexels", "pixabay"],
             query=["cartons shelf close up", "parcel boxes"]),
        shot("s002", 4.0, 10.0, "world", "still", "still-push", sources=["loc", "commons"], query=["bank teller window photograph"]),
        shot("s003", 10.0, 17.0, "world", "texture", "texture", sources=["higgsfield"],
             query=["empty cardboard boxes stacked still life"], overlay={"illustration": True}),
        shot("s004", 17.0, 21.0, "paper", "kinetic", "kinetic-thesis"),
        shot("s005", 21.0, 27.0, "world", "footage", "footage-insert", sources=["pexels"], query=["night port"]),
    ]}


@pytest.fixture
def film(tmp_path, monkeypatch):
    """A film folder, a ledger and a catalogue of synthetic media behind fake libraries."""
    fx.set_keys(monkeypatch)
    videos = tmp_path / "videos"
    (videos / SLUG).mkdir(parents=True)
    (videos / SLUG / "shots.json").write_text(json.dumps(plan(), indent=1))
    monkeypatch.setattr(sourcing.scriptmod, "video_dir", lambda slug: videos / slug)
    monkeypatch.setattr(usage, "USAGE", tmp_path / "usage.json")
    monkeypatch.setattr(filters, "detect_faces", lambda bgr: [])
    monkeypatch.setattr(filters.shutil, "which", lambda name: None)
    media = tmp_path / "media"
    media.mkdir()
    files = {"p1.mp4": fx.clip(media / "p1.mp4", "testsrc2", seconds=8), "p2.mp4": fx.clip(media / "p2.mp4", "testsrc", seconds=8),
             "x1.mp4": fx.clip(media / "x1.mp4", "smptehdbars", seconds=8),
             "dark.mp4": fx.clip(media / "dark.mp4", "color=c=0x181818", seconds=8),
             "dark2.mp4": fx.clip(media / "dark2.mp4", "color=c=0x101010", seconds=8),
             "cut.mp4": fx.clip(media / "cut.mp4", "testsrc2", seconds=6, then="smptehdbars"),
             "i1.jpg": fx.still(media / "i1.jpg", pattern=0), "i2.jpg": fx.still(media / "i2.jpg", pattern=1),
             "i3.jpg": fx.still(media / "i3.jpg", grey=128)}

    def video(src, n, name, **kw):
        return sources.candidate(id=f"{src}:{n}", source=src, kind="video", url=f"https://{src}.test/{n}",
                                 file_url=f"https://cdn.test/full/{name}", preview_url=f"https://cdn.test/{name}",
                                 width=3840, height=2160, fps=30.0, duration=8.0, author="A. Maker", title=f"cartons on a shelf {n}",
                                 licence={"pexels": "Pexels License", "pixabay": "Pixabay Content License"}[src],
                                 rights="the library's licence", credit=src.title(), rank=n, tags=["cartons", "shelf"])

    def image(src, n, name):
        return sources.candidate(id=f"{src}:{n}", source=src, kind="image", url=f"https://{src}.test/{n}",
                                 file_url=f"https://cdn.test/full/{name}", preview_url=f"https://cdn.test/{name}",
                                 width=3000, height=2200, author="A. Photographer", title=f"bank teller window {n}",
                                 licence="Public domain", rights="Public domain", credit=src.upper(), rank=n, resolved=True)
    catalogue = {
        ("pexels", "cartons shelf close up"): [video("pexels", 1, "p1.mp4"), video("pexels", 2, "dark.mp4"), video("pexels", 3, "cut.mp4")],
        ("pexels", "parcel boxes"): [video("pexels", 4, "p2.mp4")],
        ("pixabay", "cartons shelf close up"): [video("pixabay", 1, "x1.mp4")],
        ("loc", "bank teller window photograph"): [image("loc", 1, "i1.jpg"), image("loc", 2, "i2.jpg")],
        ("commons", "bank teller window photograph"): [image("commons", 1, "i3.jpg")],
        ("pexels", "night port"): [video("pexels", 9, "dark2.mp4")],
    }

    def search(source, query, kind="video", n=40, *, net=None):
        net.get_json(source, f"https://{source}.test/search", {"q": query, "kind": kind})     # one counted request
        return [dict(c) for c in catalogue.get((source, query), []) if c["kind"] == kind]
    monkeypatch.setattr(sources, "search", search)
    serve = lambda url, params, headers: fx.Response(content=files[url.rsplit("/", 1)[-1]].read_bytes())
    nets = []

    def make_net():
        nets.append(fx.make_net(tmp_path, {".test/search": {}, "cdn.test": serve}, film=videos / SLUG))
        return nets[-1]
    return {"dir": videos / SLUG, "make_net": make_net, "nets": nets, "tmp": tmp_path}


def run(film, **kw):
    return sourcing.run({"slug": SLUG}, net=film["make_net"](), **kw)


def test_the_source_step_sources_a_plan(film):
    res = run(film)
    assert res["status"] == "ok" and res["shots"] == 4                        # s004 is paper, not sourced
    assert set(res["ok"]) == {"s001", "s002"} and res["awaiting_textures"] == ["s003"]
    assert "luma" in res["fallback"]["s005"] and "0 of the 3 needed passed" in res["fallback"]["s005"]
    d = film["dir"]
    saved = {s["id"]: s for s in json.loads((d / "shots.json").read_text())["shots"]}
    assert saved["s001"]["source_status"] == "ok" and saved["s005"]["source_status"] == "fallback"
    assert saved["s003"]["source_status"] == "awaiting_textures" and "source_status" not in saved["s004"]
    rec = json.loads((d / "sources" / "s001.json").read_text())
    passed = [c for c in rec["candidates"] if c["passed_filters"]]
    assert {c["id"] for c in passed} == {"pexels:1", "pixabay:1", "pexels:4"}   # the second query ran: under six passed
    for c in rec["candidates"]:
        assert all(c.get(k) for k in ("id", "source", "url", "file_url", "preview_url", "author", "licence", "credit", "retrieved"))
        assert isinstance(c["checks"], dict) and isinstance(c["passed_filters"], bool)
    refused = {c["id"]: c["rejected_because"][0] for c in rec["candidates"] if not c["passed_filters"]}
    assert "night or low-key" in refused["pexels:2"] and "no continuous take" in refused["pexels:3"]
    assert sorted(c["sheet_index"] for c in rec["candidates"]) == list(range(len(rec["candidates"])))
    assert (d / "sources" / "s001.jpg").exists() and (d / "sources" / "s002.jpg").exists()
    assert rec["filters"]["ocr"] == filters.OCR_UNAVAILABLE


def test_texture_shots_get_four_prompts_with_the_locked_preamble(film):
    run(film)
    tex = json.loads((film["dir"] / "sources" / "textures.json").read_text())
    prompts = tex["shots"]["s003"]["prompts"]
    assert len(prompts) == 4 and len(set(prompts)) == 4
    assert all(p.startswith(sourcing.PREAMBLE + " Empty cardboard boxes stacked") for p in prompts)
    assert "Photographic still life, overcast north light" in tex["preamble"] and tex["shots"]["s003"]["status"] == "awaiting"


def test_a_second_run_costs_no_requests_and_says_the_same(film):
    first = run(film)
    sent = sum(first["requests_this_run"].values())
    assert sent == 7 and first["film_requests"]["pexels"] == 3   # s001 twice on two libraries, s002 on two, s005 once
    second = run(film)
    assert sum(second["requests_this_run"].values()) == 0 and second["downloads_this_run"] == 0
    assert second["ok"] == first["ok"] and second["fallback"] == first["fallback"]
    counts = json.loads((film["dir"] / "sources" / "requests.json").read_text())
    assert counts["by_source"]["pexels"]["requests"] == 3 and counts["by_source"]["pexels"]["cached"] >= 3
    assert len(counts["runs"]) >= 2


def test_one_shot_alone(film):
    res = run(film, shot="s002")
    assert res["shots"] == 1 and res["ok"] == ["s002"]
    assert sourcing.run({"slug": SLUG}, net=film["make_net"](), shot="s004")["status"] == "failed"


def test_a_missing_key_blocks_the_step_by_its_name_and_sends_nothing(film, monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY")
    res = run(film)
    assert res["status"] == "blocked" and "PIXABAY_API_KEY is not set (needed by s001)" in res["reason"]
    assert film["nets"][-1].http.calls == []
    assert not (film["dir"] / "sources").exists()


def test_the_ledger_window_refuses_an_asset_another_film_used(film):
    usage.record_film("98-earlier", ["pexels:1"], {"pexels:1": "8000000000000000"})
    run(film, shot="s001")
    rec = json.loads((film["dir"] / "sources" / "s001.json").read_text())
    c = next(c for c in rec["candidates"] if c["id"] == "pexels:1")
    assert not c["passed_filters"] and "98-earlier" in c["rejected_because"][0]


def test_a_picked_asset_is_not_offered_again_in_the_same_film(film):
    p = json.loads((film["dir"] / "shots.json").read_text())
    p["shots"][4]["asset"] = {"id": "pexels:1", "file": "x", "sha256": "y"}
    (film["dir"] / "shots.json").write_text(json.dumps(p))
    run(film, shot="s001")
    rec = json.loads((film["dir"] / "sources" / "s001.json").read_text())
    c = next(c for c in rec["candidates"] if c["id"] == "pexels:1")
    assert "already used in this film, for s005" in c["rejected_because"][0]


# ── the ledger (§6.7) ──
def test_record_film_keeps_the_shape_shots_validate_reads(tmp_path):
    path = tmp_path / "usage.json"
    usage.record_film("01-a", ["pexels:1", "loc:2"], {"pexels:1": "ffff000000000000"}, path=path)
    ledger = usage.read(path)
    assert ledger["films"][0]["slug"] == "01-a" and ledger["films"][0]["assets"] == ["pexels:1", "loc:2"]
    assert usage.window_ids("02-b", ledger) == {"pexels:1": "01-a", "loc:2": "01-a"}
    assert usage.window_ids("01-a", ledger) == {}
    assert usage.window_hashes("02-b", ledger)["pexels:1"][0] == "ffff000000000000"
    with pytest.raises(ValueError, match="once per film"):
        usage.record_film("02-b", ["pexels:9", "pexels:9"], path=path)
    with pytest.raises(ValueError, match="inside the last 10 films"):
        usage.record_film("02-b", ["loc:2"], path=path)
    usage.record_film("01-a", ["pexels:3"], path=path)                       # recording a film again replaces it
    assert [f["assets"] for f in usage.read(path)["films"]] == [["pexels:3"]]


def test_the_window_is_ten_films(tmp_path):
    path = tmp_path / "usage.json"
    usage.record_film("00-first", ["pexels:1"], path=path)
    for i in range(1, 11):
        usage.record_film(f"{i:02d}-film", [f"pixabay:{i}"], path=path)
    assert "pexels:1" not in usage.window_ids("11-next", usage.read(path))
    usage.record_film("11-next", ["pexels:1"], path=path)                      # eleven films later it may return
    assert shotmod.USAGE_WINDOW == 10


# ── the contact sheet ──
def test_the_contact_sheet_labels_and_marks_refusals(tmp_path):
    strip = tmp_path / "s.jpg"
    fx.still(strip, size=(960, 180), pattern=0)
    ok = {"id": "pexels:1", "kind": "video", "width": 3840, "height": 2160, "fps": 29.97, "duration": 12, "sheet_index": 0,
          "checks": {"luma": 131.4, "faces": {"max_area": 0.004}}, "passed_filters": True, "strip": str(strip)}
    bad = dict(ok, id="pexels:2", sheet_index=1, passed_filters=False, rejected_because=["mean luma 40: night or low-key"])
    assert sheet.label(ok) == ["0  pexels:1", "3840×2160 · 29.97 fps · 12 s · luma 131 · face 0.4%"]
    out = sheet.write(tmp_path / "s001.jpg", ["s001 · footage-insert", "“words”"], [(None, [ok, bad])])
    from PIL import Image
    im = Image.open(out)
    assert im.width >= 3 * 960 and im.height > 300
