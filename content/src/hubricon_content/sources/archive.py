"""The Internet Archive: archival film and photographs (VISUAL_SPEC.md §6.3).

Two scopes, never the open uploads (anyone can mark a file public domain
there): the Prelinger Archives (`archive`) and the National Archives' own
uploads, identifiers `gov.archives.*` (`nara`, in nara.py). Public-domain marks
only: an item is accepted when its `licenseurl` is the Public Domain Mark, the
old public-domain dedication or CC0, and the mark is kept as its rights text.

The search gives the record; `resolve` reads the item's file list once, for
only the candidates worth checking, to find the master scan, its size and
length, and the smallest derivative to preview.
"""

from __future__ import annotations

import json

from . import candidate, plain, stem
from . import net as netmod

NAME, KINDS, KEYS = "archive", ("video", "image"), ("CONTENT_CONTACT_EMAIL",)
CREDIT = "Prelinger Archives (Internet Archive)"
SCOPE = "collection:prelinger"
API = "https://archive.org/advancedsearch.php"
FIELDS = ["identifier", "title", "description", "date", "licenseurl", "mediatype", "collection", "creator"]
VIDEO = (".mp4", ".mov", ".mpeg", ".mpg", ".m4v", ".avi", ".mkv")
IMAGE = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def licence_of(url: str | None) -> str | None:
    u = str(url or "").lower()
    if "publicdomain/zero" in u:
        return "CC0"
    if "publicdomain/mark" in u or "licenses/publicdomain" in u:
        return "Public domain"
    return None


def search(query: str, kind: str = "video", n: int = 40, *, net=None, name=NAME, scope=SCOPE, credit=CREDIT) -> list[dict]:
    net = net or netmod.default()
    media = "movies" if kind == "video" else "image"
    params = {"q": f"({plain(query)}) AND {scope} AND mediatype:{media}", "fl[]": FIELDS,
              "rows": max(1, min(int(n), 100)), "output": "json"}
    body = net.get_json(name, API, params)
    docs = (body.get("response") or {}).get("docs") or []
    return [_candidate(d, i, kind, name, credit) for i, d in enumerate(docs) if d.get("identifier")]


def _candidate(d: dict, rank: int, kind: str, name: str, credit: str) -> dict:
    ident = d["identifier"]
    return candidate(
        id=f"{name}:{ident}", source=name, kind=kind, url=f"https://archive.org/details/{ident}",
        file_url=None, preview_url=None, author=d.get("creator") or credit,
        author_note=None if d.get("creator") else "no creator in the record; credited to the institution",
        licence=licence_of(d.get("licenseurl")), rights=d.get("licenseurl") or "no licence mark in the record",
        title=d.get("title"), description=d.get("description"), credit=credit,
        date=str(d.get("date") or "")[:10] or None, rank=rank, identifier=ident, resolved=False)


def resolve(c: dict, net) -> dict:
    """The master file and the smallest playable derivative, from the item's metadata."""
    memo = net.asset_dir / c["source"] / f"{stem(c)}.resolved.json"
    if memo.exists():
        c.update(json.loads(memo.read_text(encoding="utf-8")))
        return c
    ident = c.get("identifier") or c["id"].split(":", 1)[1]
    doc = net.get_json(c["source"], f"https://archive.org/metadata/{ident}")
    meta = doc.get("metadata") or {}
    exts = VIDEO if c["kind"] == "video" else IMAGE

    def size(f):
        try:
            return int(f.get("width") or 0), int(f.get("height") or 0)
        except ValueError:
            return 0, 0
    files = [f for f in doc.get("files") or [] if str(f.get("name", "")).lower().endswith(exts) and all(size(f))]
    found: dict = {}
    if files:
        full = max(files, key=lambda f: size(f)[0] * size(f)[1])
        mp4 = [f for f in files if str(f["name"]).lower().endswith(".mp4")] or files
        small = min(mp4, key=lambda f: (size(f)[0] * size(f)[1], int(f.get("size") or 0)))
        base = f"https://archive.org/download/{ident}/"
        found = {"file_url": base + full["name"], "width": size(full)[0], "height": size(full)[1],
                 "preview_url": base + small["name"]}
        try:
            found["duration"] = float(full.get("length") or small.get("length") or 0) or None
        except ValueError:
            found["duration"] = None
        fr = str(meta.get("frame_rate") or "").split()
        found["fps"] = float(fr[0]) if fr and fr[0].replace(".", "", 1).isdigit() else None
    found.update({k: v for k, v in {"licence": licence_of(meta.get("licenseurl")) or c.get("licence"),
                                    "rights": meta.get("licenseurl") or c.get("rights"),
                                    "place": meta.get("location"), "date": meta.get("production_date") or c.get("date")}.items() if v})
    c.update(found)
    memo.parent.mkdir(parents=True, exist_ok=True)
    memo.write_text(json.dumps(found), encoding="utf-8")
    return c
