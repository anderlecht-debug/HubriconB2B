"""The network under sourcing (VISUAL_SPEC.md §6.3): the 24-hour cache never
holds a key, the rate limiter sleeps rather than exceed a library's limit, the
film's request counter adds up, and a film's Pexels budget holds. No network."""

import json

import pytest

from hubricon_content.sources import net as netmod

from . import sources_fixture as fx


def test_a_cached_answer_holds_no_key_and_is_reused_for_a_day(tmp_path):
    key = "SECRET-pixabay-key-123456"
    echo = lambda url, params, headers: fx.Response(text=json.dumps({"hits": [], "echo": f"key={params['key']}"}))
    net = fx.make_net(tmp_path, {"pixabay.com": echo})
    body = net.get_json("pixabay", "https://pixabay.com/api/videos/", {"key": key, "q": "pallets"}, secret=("key",))
    assert body["echo"] == "key=[key]"                      # an answer that echoes the key is cleaned
    again = net.get_json("pixabay", "https://pixabay.com/api/videos/", {"key": key, "q": "pallets"}, secret=("key",))
    assert again == body and len(net.http.calls) == 1        # the second answer came from the cache
    stored = "".join(p.read_text() for p in (tmp_path / "api").rglob("*.json"))
    assert key not in stored and '"q": "pallets"' in stored
    net.clock.t += netmod.TTL + 1                            # a day later the cache is stale
    net.get_json("pixabay", "https://pixabay.com/api/videos/", {"key": key, "q": "pallets"}, secret=("key",))
    assert len(net.http.calls) == 2


def test_a_header_key_is_never_stored(tmp_path):
    net = fx.make_net(tmp_path, {"pexels.com": {"videos": []}})
    net.get_json("pexels", "https://api.pexels.com/videos/search", {"query": "crane"}, headers={"Authorization": "HEADER-KEY-999999"})
    assert net.http.calls[0]["headers"]["Authorization"] == "HEADER-KEY-999999"
    assert net.http.calls[0]["headers"]["User-Agent"].startswith("Hubricon/1.0")
    assert "HEADER-KEY" not in "".join(p.read_text() for p in (tmp_path / "api").rglob("*.json"))


def test_an_error_never_carries_the_url_or_its_key(tmp_path):
    class Boom:
        def get(self, url, params=None, **kw):
            raise RuntimeError(f"connection failed for {url}?key={params['key']}")
    net = netmod.Net(http=Boom(), cache_dir=tmp_path / "api", asset_dir=tmp_path / "a", sleep=lambda s: None)
    with pytest.raises(netmod.SourceError) as e:
        net.get_json("pixabay", "https://pixabay.com/api/videos/", {"key": "LEAKY-KEY-1234", "q": "x"}, secret=("key",))
    assert "LEAKY" not in str(e.value) and "pixabay.com" not in str(e.value)


def test_the_limiter_sleeps_rather_than_exceed_and_remembers_across_runs(tmp_path):
    clock = fx.Clock()
    lim = netmod.Limiter(tmp_path / "rl.json", clock=clock, sleep=clock.sleep, limits={"pexels": (3, 3600.0)})
    for _ in range(3):
        lim.wait("pexels")
    assert clock.slept == []
    later = netmod.Limiter(tmp_path / "rl.json", clock=clock, sleep=clock.sleep, limits={"pexels": (3, 3600.0)})
    later.wait("pexels")              # a new run reads the hour from disk: the fourth request waits for the first to age out
    assert len(clock.slept) == 1 and 3599 < clock.slept[0] < 3601


def test_pixabay_s_hundred_a_minute(tmp_path):
    clock = fx.Clock()
    lim = netmod.Limiter(tmp_path / "rl.json", clock=clock, sleep=clock.sleep)
    for _ in range(100):
        lim.wait("pixabay")
    assert clock.slept == []
    lim.wait("pixabay")
    assert 59 < sum(clock.slept) < 61


def test_a_429_waits_for_retry_after_then_retries(tmp_path):
    answers = iter([fx.Response(status=429, text="slow down", headers={"Retry-After": "7"}), fx.Response(body={"videos": []})])
    net = fx.make_net(tmp_path, {"pexels.com": lambda *a: next(answers)})
    assert net.get_json("pexels", "https://api.pexels.com/videos/search", {"query": "dock"}) == {"videos": []}
    assert 7 in [round(s) for s in net.clock.slept]


def test_pexels_monthly_allowance_blocks_instead_of_sleeping_a_month(tmp_path):
    clock = fx.Clock()
    lim = netmod.Limiter(tmp_path / "rl.json", clock=clock, sleep=clock.sleep, monthly={"pexels": 2})
    lim.wait("pexels"); lim.wait("pexels")
    with pytest.raises(netmod.Blocked, match="resets on the 1st"):
        lim.wait("pexels")


def test_the_film_counter_and_its_pexels_budget(tmp_path):
    film = tmp_path / "film"
    net = fx.make_net(tmp_path, {"pexels.com": {"videos": []}}, film=film, budget={"pexels": 2})
    for q in ("crane", "crane", "truck"):                    # the repeat is a cache hit, not a request
        net.get_json("pexels", "https://api.pexels.com/videos/search", {"query": q})
    assert net.spent("pexels") == 2
    with pytest.raises(netmod.BudgetSpent):
        net.get_json("pexels", "https://api.pexels.com/videos/search", {"query": "pallet"})
    totals = net.save_counts()
    assert totals["pexels"]["requests"] == 2 and totals["pexels"]["cached"] == 1
    doc = json.loads((film / "sources" / "requests.json").read_text())
    assert doc["by_source"]["pexels"]["requests"] == 2 and doc["runs"]
    again = fx.make_net(tmp_path, {"pexels.com": {"videos": []}}, film=film, budget={"pexels": 2})
    assert again.spent("pexels") == 2                        # the budget is the film's, across runs


def test_a_download_lands_once_in_the_asset_cache(tmp_path):
    net = fx.make_net(tmp_path, {"cdn.example": fx.Response(content=b"frame-bytes" * 100)})
    dest = tmp_path / "assets" / "pexels" / "1.preview.mp4"
    net.download("pexels", "https://cdn.example/1.mp4", dest)
    net.download("pexels", "https://cdn.example/1.mp4", dest)
    assert dest.read_bytes().startswith(b"frame-bytes") and len(net.http.calls) == 1
    assert net.session["pexels"]["downloads"] == 1 and net.session["pexels"]["requests"] == 0
