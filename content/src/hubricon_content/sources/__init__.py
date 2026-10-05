"""Sourcing (VISUAL_SPEC.md §6): one interface over the stock libraries and the
public archives, so the `source` step asks every library the same way and gets
back the same record.

Each library is a module with `search(query, kind, n, *, net=None)` returning
candidates, and, where its search leaves the full-resolution file out (the
Library of Congress, the Internet Archive), `resolve(candidate, net)` to fill it
in for the few candidates worth checking. A candidate carries its whole
provenance, because §6.2 and §11 need it later: who made it, under which
licence, where it lives, and when we read it.

The AI textures are not fetched here: the runner's Claude makes them through
the Higgsfield connector (§6.3, §6.5), from the prompts `sourcing` writes.
Amazon is never read, in any form (HUBRICON_SPEC.md, amended 2026-10-01).
"""

from __future__ import annotations

import hashlib
import importlib
import re
from datetime import date
from pathlib import Path

from . import net as netmod
from .net import Blocked, BudgetSpent, SourceError  # noqa: F401  (the step catches them from here)

# The library names a shot plan may list (content/film/styles.json "sources"), and the
# module that reads each. NARA's films are read from the Internet Archive, where the
# Archives published them (identifiers gov.archives.*).
MODULES = {"pexels": "pexels", "pixabay": "pixabay", "loc": "loc", "smithsonian": "smithsonian",
           "commons": "commons", "archive": "archive", "nara": "nara"}
FIELDS = ("id", "source", "kind", "url", "file_url", "preview_url", "width", "height", "fps", "duration",
          "author", "author_url", "licence", "rights", "title", "description", "credit", "place", "date",
          "subject", "retrieved")
# Words that describe the medium or the camera, not the subject: an archive's search
# reads every word as required, so they are dropped there (and kept for stock).
MEDIUM_WORDS = {"photograph", "photographs", "photo", "photos", "image", "images", "picture", "archive",
                "archival", "historic", "historical", "old", "vintage", "close", "up", "closeup", "wide",
                "daylight", "static", "interior", "exterior", "shot", "footage", "still", "life"}


def adapter(source: str):
    if source not in MODULES:
        raise KeyError(f"no library called {source!r} (VISUAL_SPEC.md §6.3)")
    return importlib.import_module(f"{__name__}.{MODULES[source]}")


def missing_keys(source: str) -> list[str]:
    """The environment variables `source` needs that are not set, by exact name."""
    return [k for k in adapter(source).KEYS if not netmod.env(k)]


def search(source: str, query: str, kind: str = "video", n: int = 40, *, net=None) -> list[dict]:
    mod = adapter(source)
    if kind not in mod.KINDS:
        return []
    return mod.search(query, kind, n, net=net or netmod.default())


def resolve(c: dict, net=None) -> dict:
    """Fill in a candidate's full-resolution file and size when its search left them out."""
    mod = adapter(c["source"])
    if hasattr(mod, "resolve") and not c.get("resolved"):
        mod.resolve(c, net or netmod.default())
    c["resolved"] = True
    return c


STOP_WORDS = {"a", "an", "the", "and", "or", "of", "on", "in", "at", "to", "for", "with", "by", "from", "into", "onto"}


def plain(query: str) -> str:
    """A query's subject words, for a search that reads every word as required (an archive's)
    or any one word as enough (Pixabay's): MEDIUM_WORDS and STOP_WORDS dropped."""
    words = [w for w in re.findall(r"[\w'’-]+", query) if w.lower() not in MEDIUM_WORDS | STOP_WORDS]
    return " ".join(words) or query


def nouns(query: str) -> str:
    """A broader query for an archive that found nothing: the subject words without the
    verbs of action ("bookkeeper writing in ledger" → "bookkeeper ledger")."""
    words = [w for w in plain(query).split() if not re.search(r"ing$", w.lower())]
    return " ".join(words) or plain(query)


def text(value) -> str:
    """Flatten a record field (a string, a list, None, a little HTML) to plain text."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(t for t in (text(v) for v in value) if t)
    s = re.sub(r"<[^>]+>", " ", str(value))
    s = s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def candidate(**fields) -> dict:
    """A candidate with every provenance field present (None where the record has none)."""
    c = {k: fields.pop(k, None) for k in FIELDS}
    c.update(fields)
    c["retrieved"] = c["retrieved"] or date.today().isoformat()
    for k in ("title", "description", "author", "place", "date", "rights"):
        if c[k] is not None:
            c[k] = text(c[k])[:600] or None
    return c


def stem(c: dict) -> str:
    """A file-safe name for a candidate: its id, cleaned, with a short hash for uniqueness."""
    raw = c["id"].split(":", 1)[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")[:60]
    return f"{safe}-{hashlib.sha256(c['id'].encode()).hexdigest()[:8]}"


def _ext(url: str, default: str) -> str:
    m = re.search(r"\.(mp4|mov|webm|m4v|jpe?g|png|tiff?|gif)(?:[?#]|$)", url or "", re.I)
    return "." + m.group(1).lower().replace("jpeg", "jpg") if m else default


def preview_path(c: dict, asset_dir: Path | None = None) -> Path:
    base = Path(asset_dir or netmod.ASSET_CACHE) / c["source"]
    return base / f"{stem(c)}.preview{_ext(c['preview_url'], '.mp4' if c['kind'] == 'video' else '.jpg')}"


def full_path(c: dict, asset_dir: Path | None = None) -> Path:
    base = Path(asset_dir or netmod.ASSET_CACHE) / c["source"]
    return base / f"{stem(c)}{_ext(c['file_url'], '.mp4' if c['kind'] == 'video' else '.jpg')}"


def fetch_preview(c: dict, net=None) -> Path:
    """The small rendition, for the filters and the contact sheet (§6.4). Records its sha256."""
    net = net or netmod.default()
    if not c.get("preview_url"):
        raise SourceError(f"{c['id']}: no preview rendition")
    p = net.download(c["source"], c["preview_url"], preview_path(c, net.asset_dir))
    c["preview_file"] = str(p)
    c["preview_sha256"] = netmod.sha256_file(p)
    return p


def fetch_full(c: dict, net=None) -> Path:
    """The full-resolution file, fetched only for the picked asset. Records its sha256,
    which the render cache keys on (§8.3)."""
    net = net or netmod.default()
    resolve(c, net)
    if not c.get("file_url"):
        raise SourceError(f"{c['id']}: no full-resolution file in the record")
    p = net.download(c["source"], c["file_url"], full_path(c, net.asset_dir))
    c["file"] = str(p)
    c["sha256"] = netmod.sha256_file(p)
    return p
