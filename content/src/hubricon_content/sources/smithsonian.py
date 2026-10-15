"""Smithsonian Open Access: archival photographs and objects (VISUAL_SPEC.md §6.3).

api.si.edu with a key from api.data.gov (`SMITHSONIAN_API_KEY`, a query
parameter, stripped before caching). CC0 only: both the record's metadata and
the media item must say CC0. The search reads every word as required, so the
query is cut to its subject words first, and asked of history and culture only
(a word like "ledger" otherwise finds the bone ledgers of the fish collection).
"""

from __future__ import annotations

from . import candidate, plain
from . import net as netmod

NAME, KINDS, KEYS, CREDIT = "smithsonian", ("image",), ("SMITHSONIAN_API_KEY",), "Smithsonian Institution"
API = "https://api.si.edu/openaccess/api/v1.0/category/history_culture/search"
MAKERS = {"photographer", "artist", "maker", "creator", "author", "writer", "manufacturer", "designer",
          "printer", "publisher", "engraver", "lithographer", "illustrator", "architect"}


def search(query: str, kind: str = "image", n: int = 40, *, net=None) -> list[dict]:
    net = net or netmod.default()
    params = {"q": f"{plain(query)} AND online_media_type:Images", "rows": max(1, min(int(n), 100)),
              "api_key": netmod.env("SMITHSONIAN_API_KEY") or ""}
    body = net.get_json(NAME, API, params, secret=("api_key",))
    out = []
    for i, row in enumerate((body.get("response") or {}).get("rows") or []):
        out += _candidates(row, i)
    return out


def _labelled(entries, labels=None) -> list[str]:
    return [e.get("content") for e in entries or [] if isinstance(e, dict) and e.get("content")
            and (labels is None or str(e.get("label", "")).lower() in labels)]


def _candidates(row: dict, rank: int) -> list[dict]:
    content = row.get("content") or {}
    dn = content.get("descriptiveNonRepeating") or {}
    ft = content.get("freetext") or {}
    record_cc0 = (dn.get("metadata_usage") or {}).get("access") == "CC0"
    unit = dn.get("data_source") or row.get("unitCode")
    makers = _labelled(ft.get("name"), MAKERS)
    url = dn.get("record_link") or (f"https://collections.si.edu/search/detail/{row['url']}" if row.get("url") else None)
    out = []
    for m in (dn.get("online_media") or {}).get("media") or []:
        if m.get("type") != "Images":
            continue
        sized = [r for r in m.get("resources") or [] if r.get("width") and r.get("height") and "jpeg" in str(r.get("label", "")).lower()]
        sized = sized or [r for r in m.get("resources") or [] if r.get("width") and r.get("height")]
        best = max(sized, key=lambda r: r["width"] * r["height"], default=None)
        ids = m.get("idsId") or ""
        preview = (f"https://ids.si.edu/ids/deliveryService/id/{ids}/800" if ids.startswith("ark:")
                   else f"https://ids.si.edu/ids/deliveryService?id={ids}&max=800") if ids else m.get("thumbnail")
        cc0 = record_cc0 and (m.get("usage") or {}).get("access") == "CC0"
        out.append(candidate(
            id=f"smithsonian:{ids or m.get('id')}", source=NAME, kind="image", url=url,
            file_url=best["url"] if best else m.get("content"), preview_url=preview,
            width=best["width"] if best else None, height=best["height"] if best else None,
            author=makers or (f"{CREDIT}, {unit}" if unit else CREDIT),
            author_note=None if makers else "no maker in the record; credited to the institution",
            licence="CC0" if cc0 else None, rights=(m.get("usage") or {}).get("access") or "no usage statement",
            title=row.get("title"), description=" ".join(_labelled(ft.get("notes"))[:2]) or m.get("extDescrAccessibility"),
            credit=f"{CREDIT}, {unit}" if unit else CREDIT, place=_labelled(ft.get("place"))[:1] or None,
            date=_labelled(ft.get("date"))[:1] or None, subject=(content.get("indexedStructured") or {}).get("topic"),
            rank=rank, resolved=True))
    return out
