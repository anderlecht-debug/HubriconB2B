"""Pexels videos: stock footage (VISUAL_SPEC.md §6.3).

200 requests an hour and 20,000 a month, so a search asks for 40 results at a
time, landscape and at least Full HD (`size=medium`), and the same query string
is answered from the cache for every shot that asks it. The key travels in the
Authorization header and is never cached. Pexels asks for a link to Pexels and
credit to the creator, so both are kept.
"""

from __future__ import annotations

import re

from . import candidate
from . import net as netmod

NAME, KINDS, KEYS, CREDIT = "pexels", ("video",), ("PEXELS_API_KEY",), "Pexels"
API = "https://api.pexels.com/videos/search"
LICENCE, LICENCE_URL = "Pexels License", "https://www.pexels.com/license/"


def search(query: str, kind: str = "video", n: int = 40, *, net=None) -> list[dict]:
    net = net or netmod.default()
    params = {"query": query, "per_page": max(1, min(int(n), 80)), "orientation": "landscape", "size": "medium"}
    body = net.get_json(NAME, API, params, headers={"Authorization": netmod.env("PEXELS_API_KEY") or ""})
    return [c for i, v in enumerate(body.get("videos") or []) if (c := _candidate(v, i))]


def _title(url: str) -> str | None:
    m = re.search(r"/video/(.+?)-?\d*/?$", url or "")
    return m.group(1).replace("-", " ").strip() or None if m else None


def _candidate(v: dict, rank: int) -> dict | None:
    files = [f for f in v.get("video_files") or [] if f.get("link") and f.get("width") and f.get("height")]
    if not files:
        return None
    full = max(files, key=lambda f: (f["width"] * f["height"], f.get("fps") or 0))
    small = min(files, key=lambda f: f["width"] * f["height"])
    user = v.get("user") or {}
    return candidate(
        id=f"pexels:{v['id']}", source=NAME, kind="video", url=v.get("url"),
        file_url=full["link"], preview_url=small["link"], width=full["width"], height=full["height"],
        fps=round(float(full["fps"]), 3) if full.get("fps") else None, duration=float(v.get("duration") or 0) or None,
        author=user.get("name"), author_url=user.get("url"), licence=LICENCE, licence_url=LICENCE_URL,
        rights=LICENCE, title=_title(v.get("url")), description=None, credit=CREDIT,
        tags=[t for t in v.get("tags") or [] if isinstance(t, str)], rank=rank,
        preview_size=[small["width"], small["height"]], preview_bytes=small.get("size"), thumbnail=v.get("image"))
