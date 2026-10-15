"""Pixabay videos: stock footage (VISUAL_SPEC.md §6.3).

100 requests a minute; Pixabay's terms ask that responses be cached for 24
hours and that files be downloaded, never hotlinked, so both hold for every
source here. A search asks for filmed footage only (`video_type=film`: no
animations) at Full HD or better. The key is a query parameter, so it is named
secret and stripped before the answer is cached.

Pixabay's search matches any one tag, so a camera word ("close up") brings back
every close-up on the site: the query goes without them, and the filters refuse
a clip whose tags name fewer than half of the query's nouns (filters.relevance).

Pixabay does not publish a clip's frame rate; the filters read it from the
preview rendition (§6.4), and `fps_from` says so.
"""

from __future__ import annotations

from . import candidate, plain
from . import net as netmod

NAME, KINDS, KEYS, CREDIT = "pixabay", ("video",), ("PIXABAY_API_KEY",), "Pixabay"
API = "https://pixabay.com/api/videos/"
LICENCE, LICENCE_URL = "Pixabay Content License", "https://pixabay.com/service/license-summary/"
SIZES = ("large", "medium", "small", "tiny")


def search(query: str, kind: str = "video", n: int = 40, *, net=None) -> list[dict]:
    net = net or netmod.default()
    params = {"key": netmod.env("PIXABAY_API_KEY") or "", "q": plain(query)[:100], "per_page": max(3, min(int(n), 200)),
              "video_type": "film", "safesearch": "true", "min_width": 1920, "min_height": 1080}
    body = net.get_json(NAME, API, params, secret=("key",))
    return [c for i, h in enumerate(body.get("hits") or []) if (c := _candidate(h, i))]


def _candidate(h: dict, rank: int) -> dict | None:
    vids = {k: v for k, v in (h.get("videos") or {}).items() if isinstance(v, dict) and v.get("url") and v.get("width")}
    if not vids:
        return None
    full = max(vids.values(), key=lambda v: v["width"] * v["height"])
    small = next((vids[k] for k in reversed(SIZES) if k in vids), full)
    tags = [t.strip() for t in str(h.get("tags") or "").split(",") if t.strip()]
    user, uid = h.get("user"), h.get("user_id")
    return candidate(
        id=f"pixabay:{h['id']}", source=NAME, kind="video", url=h.get("pageURL"),
        file_url=full["url"], preview_url=small["url"], width=full["width"], height=full["height"],
        fps=None, fps_from="preview", duration=float(h.get("duration") or 0) or None,
        author=user, author_url=h.get("userURL") or (f"https://pixabay.com/users/{user}-{uid}/" if user and uid else None),
        licence=LICENCE, licence_url=LICENCE_URL, rights=LICENCE, title=", ".join(tags[:3]) or None,
        description=", ".join(tags) or None, credit=CREDIT, tags=tags, rank=rank,
        footage_type=h.get("type"), ai_generated=bool(h.get("isAiGenerated")),
        preview_size=[small["width"], small["height"]], preview_bytes=small.get("size"), thumbnail=small.get("thumbnail"))
