"""The Library of Congress: archival photographs (VISUAL_SPEC.md §6.3).

The loc.gov JSON API (`?fo=json`) on the photos format. Only items whose rights
statement says "No known restrictions on publication" are accepted, and the
whole statement is kept: the Library says the user decides rights, so the
record is the defence. No key; a polite User-Agent with a contact address.

The search answer carries the rights, the creators, the place and the date,
but not the full-resolution file: the Prints and Photographs Division serves
the master as a TIFF whose size is not in the record. `resolve` reads the item
once and, when the TIFF's size is missing, its header (the first 64 KB), for
only the candidates worth checking.
"""

from __future__ import annotations

import json
import re
import struct

from . import candidate, plain, stem
from . import net as netmod

NAME, KINDS, KEYS, CREDIT = "loc", ("image",), ("CONTENT_CONTACT_EMAIL",), "Library of Congress"
API = "https://www.loc.gov/photos/"
ACCEPT = "No known restrictions on publication"


def search(query: str, kind: str = "image", n: int = 40, *, net=None) -> list[dict]:
    net = net or netmod.default()
    body = net.get_json(NAME, API, {"q": plain(query), "fo": "json", "c": max(1, min(int(n), 100)), "at": "results"})
    return [c for i, r in enumerate(body.get("results") or []) if (c := _candidate(r, i))]


def _sized(urls) -> list[tuple[str, int, int]]:
    out = []
    for u in urls or []:
        m = re.search(r"#h=(\d+)&w=(\d+)", u)
        if m and re.search(r"\.(jpe?g)#", u, re.I):
            out.append((u.split("#")[0], int(m.group(2)), int(m.group(1))))
    return out


def rights_of(r: dict) -> str:
    item = r.get("item") or {}
    ra = item.get("rights_advisory") or item.get("rights_information") or r.get("rights")
    return (ra[0] if isinstance(ra, list) and ra else ra or "").strip()


def _candidate(r: dict, rank: int) -> dict | None:
    if r.get("access_restricted") or "image" not in (r.get("online_format") or []):
        return None
    sized = _sized(r.get("image_url"))
    if not sized:
        return None
    preview = max((s for s in sized if max(s[1], s[2]) <= 1100), key=lambda s: s[1] * s[2], default=sized[0])
    best = max(sized, key=lambda s: s[1] * s[2])
    item = r.get("item") or {}
    rights = rights_of(r)
    creators = [c.get("title") for c in item.get("creators") or [] if isinstance(c, dict) and c.get("title")]
    creators = creators or [c for c in r.get("contributor") or [] if isinstance(c, str)]
    loc = item.get("location") or r.get("location")
    dates = r.get("dates") or [item.get("date") or r.get("date")]
    return candidate(
        id=f"loc:{(r.get('url') or r.get('id') or '').rstrip('/').rsplit('/', 1)[-1]}", source=NAME, kind="image",
        url=r.get("url") or r.get("id"), file_url=best[0], preview_url=preview[0], width=best[1], height=best[2],
        author=creators or CREDIT, author_note=None if creators else "no creator in the record; credited to the institution",
        licence=ACCEPT if rights.lower().startswith(ACCEPT.lower()) else None, rights=rights or "no rights statement",
        title=r.get("title"), description=item.get("summary") or r.get("description"), credit=CREDIT,
        place=loc, date=(dates or [None])[0], subject=item.get("subjects") or r.get("subject"), rank=rank,
        resource=(r.get("resources") or [{}])[0].get("url"), item_url=r.get("url"))


def tiff_size(head: bytes) -> tuple[int, int] | None:
    """Width and height from a TIFF's first IFD, when it sits inside `head`."""
    if len(head) < 8 or head[:2] not in (b"II", b"MM"):
        return None
    o = "<" if head[:2] == b"II" else ">"
    ifd = struct.unpack(o + "I", head[4:8])[0]
    if ifd + 2 > len(head):
        return None
    size = {}
    for i in range(struct.unpack(o + "H", head[ifd:ifd + 2])[0]):
        e = ifd + 2 + 12 * i
        if e + 12 > len(head):
            break
        tag, typ = struct.unpack(o + "HH", head[e:e + 4])
        if tag in (256, 257):
            size[tag] = struct.unpack(o + ("H" if typ == 3 else "I"), head[e + 8:e + (10 if typ == 3 else 12)])[0]
    return (size[256], size[257]) if 256 in size and 257 in size else None


def resolve(c: dict, net) -> dict:
    """The largest file in the item record (the master TIFF, as a rule) and its size."""
    memo = net.asset_dir / NAME / f"{stem(c)}.resolved.json"
    if memo.exists():
        c.update(json.loads(memo.read_text(encoding="utf-8")))
        return c
    item = net.get_json(NAME, (c.get("item_url") or c["url"]).split("?")[0], {"fo": "json", "at": "resources"})
    files = [f for res in item.get("resources") or [] for group in res.get("files") or [] for f in group
             if isinstance(f, dict) and str(f.get("mimetype", "")).startswith("image/") and f.get("url")]
    jpg = [f for f in files if f.get("width") and f.get("height")]
    best = max(jpg, key=lambda f: f["width"] * f["height"], default=None)
    found = {"file_url": best["url"], "width": best["width"], "height": best["height"]} if best else {}
    for t in sorted((f for f in files if "tif" in f["mimetype"]), key=lambda f: -int(f.get("size") or 0)):
        w, h = t.get("width") or 0, t.get("height") or 0
        if not (w and h):
            wh = tiff_size(net.head_bytes(NAME, t["url"]))
            w, h = wh or (0, 0)
        if w and h and (not found or w * h > found["width"] * found["height"]):
            found = {"file_url": t["url"], "width": w, "height": h}
        break
    if found:
        c.update(found)
        memo.parent.mkdir(parents=True, exist_ok=True)
        memo.write_text(json.dumps(found), encoding="utf-8")
    return c
