"""The National Archives' films, as the Archives published them on the Internet
Archive (identifiers `gov.archives.*`), read exactly as archive.py reads the
Prelinger Archives: public-domain marks only (VISUAL_SPEC.md §6.3)."""

from __future__ import annotations

from . import archive

NAME, KINDS, KEYS = "nara", ("video", "image"), ("CONTENT_CONTACT_EMAIL",)
CREDIT = "National Archives and Records Administration (Internet Archive)"
SCOPE = "identifier:gov.archives*"
resolve = archive.resolve


def search(query: str, kind: str = "video", n: int = 40, *, net=None) -> list[dict]:
    return archive.search(query, kind, n, net=net, name=NAME, scope=SCOPE, credit=CREDIT)
