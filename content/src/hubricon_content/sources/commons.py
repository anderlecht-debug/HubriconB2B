"""Wikimedia Commons: archival photographs (VISUAL_SPEC.md §6.3).

The MediaWiki API with `extmetadata`. Accepted: public domain, CC0 and CC BY
(with credit). Refused: share-alike, non-commercial, no-derivatives, fair use,
anything trademarked, and anything whose licence the record does not state:
Flickr's "no known copyright restrictions" is not on Commons' accept list, so
it is refused here (the Library of Congress's own statement is accepted in
loc.py, where the Library stands behind it). No key; a polite User-Agent.
"""

from __future__ import annotations

import re

from . import candidate, plain, text
from . import net as netmod

NAME, KINDS, KEYS, CREDIT = "commons", ("image",), ("CONTENT_CONTACT_EMAIL",), "Wikimedia Commons"
API = "https://commons.wikimedia.org/w/api.php"
META = ("LicenseShortName|License|UsageTerms|LicenseUrl|Artist|Credit|ImageDescription|DateTimeOriginal|"
        "ObjectName|NonFree|Restrictions|Copyrighted|AttributionRequired")


CATEGORY = re.compile(r"^\s*category:\s*(.+?)\s*$", re.I)


def search(query: str, kind: str = "image", n: int = 40, *, net=None) -> list[dict]:
    """A full-text search, or, for a query written `category: <name>`, the files of that Commons
    category: curated by Commons' editors, so far more exact for a named subject than the words
    of a file title. The category is kept as the record's subject, where the filters read it."""
    net = net or netmod.default()
    params = {"action": "query", "format": "json", "formatversion": 2,
              "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 960,
              "iiextmetadatafilter": META, "iiextmetadatalanguage": "en"}
    cat = CATEGORY.match(query)
    if cat:
        params.update({"generator": "categorymembers", "gcmtitle": f"Category:{cat.group(1)}", "gcmtype": "file",
                       "gcmlimit": max(1, min(int(n), 50))})
    else:
        params.update({"generator": "search", "gsrsearch": f"{plain(query)} filetype:bitmap", "gsrnamespace": 6,
                       "gsrlimit": max(1, min(int(n), 50))})
    body = net.get_json(NAME, API, params)
    pages = sorted((body.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    found = [c for i, p in enumerate(pages) if (c := _candidate(p, i))]
    if cat:
        for c in found:
            c["subject"] = f"Commons category: {cat.group(1)}"
    return found


def licence_of(meta: dict) -> str | None:
    """Commons' accept list, read from the machine field `License`, never from free text."""
    if str(meta.get("NonFree", "")).lower() == "true" or "trademark" in str(meta.get("Restrictions", "")).lower():
        return None
    code = str(meta.get("License", "")).lower().strip()
    if code in ("pd", "public domain") or code.startswith("pd-"):
        return "Public domain"
    if code == "cc0":
        return "CC0"
    m = re.fullmatch(r"cc-by-(\d(?:\.\d)?)", code)
    return f"CC BY {m.group(1)}" if m else None


def _clean(url: str | None) -> str | None:
    return url.split("?")[0] if url else None


def _candidate(p: dict, rank: int) -> dict | None:
    info = (p.get("imageinfo") or [None])[0]
    if not info or not str(info.get("mime", "")).startswith("image/") or info.get("mime") == "image/svg+xml":
        return None
    meta = {k: v.get("value") for k, v in (info.get("extmetadata") or {}).items() if isinstance(v, dict)}
    artist = text(meta.get("Artist"))
    if not artist or re.fullmatch(r"https?://\S+", artist):      # some uploads give a link as the artist
        artist = text(meta.get("Credit")) or artist
    title = text(meta.get("ObjectName")) or re.sub(r"^File:|\.\w+$", "", p.get("title", ""))
    return candidate(
        id=f"commons:{p.get('pageid')}", source=NAME, kind="image", url=info.get("descriptionurl"),
        file_url=_clean(info.get("url")), preview_url=_clean(info.get("thumburl")),
        width=info.get("width"), height=info.get("height"), author=artist or None,
        licence=licence_of(meta), licence_url=meta.get("LicenseUrl"),
        rights=text(meta.get("LicenseShortName")) or text(meta.get("UsageTerms")) or "no licence in the record",
        restrictions=text(meta.get("Restrictions")) or None, title=title,
        description=text(meta.get("ImageDescription"))[:600] or None, credit=CREDIT,
        date=text(meta.get("DateTimeOriginal")) or None, rank=rank, file_title=p.get("title"), resolved=True)
