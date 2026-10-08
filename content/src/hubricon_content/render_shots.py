"""One clip per shot (VISUAL_SPEC.md §8.3): `hubricon-content render-shots <slug>`.

Each shot of a picked plan becomes content/videos/<slug>/shots/<id>.mp4, exactly
its frame count at 30 fps, by one of three renderers:

- the film stage (content/film/shots.mjs), for every paper kind, the house
  charts, and world stills and textures, where a still's move is drawn by
  Chrome frame by frame (no ffmpeg zoompan steps);
- ffmpeg (footage.py), for world footage, graded and grained;
- Manim (scenes/), for the engine's own charts, restyled on the site's tokens.

A clip is named by a cache key, the sha256 of the shot's resolved job, its
assets, tokens.json, grade.json, styles.json and this renderer's version, so a
one-line change re-renders one clip, not a film. Every figure on screen is
filled from facts.json here, never typed in a plan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import footage, grade, shots, sourcelabel, tokens
from . import script as scriptmod
from .state import CONTENT_DIR

VERSION = "2026-10-05.1" + ("+v3" if os.environ.get("FILM_LOOK") == "v3" else "")
FPS = 30
REPO = CONTENT_DIR.parent
RENDER_MJS = CONTENT_DIR / "film" / "render.mjs"
GRADED = CONTENT_DIR / ".cache" / "graded"
MANIM_SCENES = {"waterfall": "Waterfall", "cash_cone": "CashCone", "paths": "Paths", "elasticity": "Elasticity",
                "newsvendor": "Newsvendor", "sample_size": "SampleSize"}
STAGE_CHARTS = {"staircase", "montecarlo", "aging"}
# The v3 look (FILM_LOOK=v3, the founder's call of 2026-10-06) draws every chart on the stage,
# the engine's too, from the same figures: the waterfall from this film's own run.json.
LOOK = "v3" if os.environ.get("FILM_LOOK") == "v3" else "paper"
V3_FAMILY = {"document": "documents", "table": "documents", "quote": "documents", "receipt": "documents",
             "still": "photos", "texture": "photos", "archive": "photos", "stack": "photos", "split": "photos",
             "footage": "photos", "chart": "charts"}   # everything else is type
# The end card's words are the site's own (the style reel's end scene, content/film/scenes.mjs).
END = {"headline": "More profit than our bill every month, or you don't pay.", "primary": "Book your call", "primary_url": "hubricon.com/apply",
       "secondary": "or learn the method, free, at hubricon.com/learn"}
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


def display_date(value) -> str | None:
    """A record's date as a label may print it, or None when the record does not say when the
    picture was made. Only a year ("1914"), a short range ("1912–1926") or a circa year ("c. 1900")
    is printed: a "?" or "ca." makes it circa; "after 1920" stays "after 1920"; a full timestamp
    gives its year, unless it is a camera's or an upload's stamp from this century on a scan
    ("2010-04-21 17:20"); a survey's own date ("Documentation compiled after 1933"), a catalogue
    note mixing the picture's guess with the scan's publication, or a guess wider than 25 years
    ("1865?-1920?") prints nothing, never one of its years as if it were known."""
    if not value:
        return None
    v = str(value).split(" date QS:")[0].strip()        # Wikidata's machine form after the words
    if not v or v.lower() in ("none", "n.d.", "nd", "undated", "unknown", "date unknown"):
        return None
    if re.search(r"documentation compiled|digiti[sz]ed|scanned|upload|published \d", v, re.I):
        return None
    m = re.fullmatch(r"(1[5-9]\d\d|20\d\d)-\d\d-\d\d([ T]\d\d:\d\d.*)?", v)
    if m:
        return None if m.group(2) and int(m.group(1)) >= 2000 else m.group(1)
    # "1912–13" is 1912–1913; "1840-01-01" is a day, not a range
    v = re.sub(r"\b(1[5-9])(\d\d)\s*[–-]\s*(\d\d)\b(?![\d-])",
               lambda m: f"{m[1]}{m[2]}–{m[1]}{m[3]}" if int(m[3]) > int(m[2]) else m[0], v)
    edge = re.search(r"\b(after|before|since)\s+(1[5-9]\d\d|20\d\d)\b", v, re.I)
    if edge:
        return f"{edge.group(1).lower()} {edge.group(2)}"
    years = [int(y) for y in re.findall(r"(?<!\d)(1[5-9]\d\d|20\d\d)(?!\d)", v)]
    if not years:
        return None
    lo, hi = min(years), max(years)
    if hi - lo > 25:
        return None
    circa = bool(re.search(r"\?|\b(c\.|ca\.?|circa|about|approx\w*)(?=\s|\d)", v, re.I))
    text = str(lo) if lo == hi else f"{lo}–{hi}"
    return f"c. {text}" if circa else text


_ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                      "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_SCALE = {"hundred": 100, "thousand": 1000, "million": 1_000_000}


def said_numbers(spoken) -> list[str]:
    """The numbers in a run of spoken words, as digit strings ("1,000" → "1000", "seventy-two" → "72",
    "eleven" → "11", "$1.90" → "1.90"), each once, in the order first said."""
    out: list[str] = []
    run = None

    def add(x):
        if x is not None and str(x) not in out:
            out.append(str(x))
    for raw in spoken:
        w = str(raw).lower().strip(".,;:!?\"'’()")
        for d in re.findall(r"\d[\d,]*(?:\.\d+)?", w):
            add(d.replace(",", "").rstrip("."))
        parts = w.replace("-", " ").split()
        if parts and all(p in _ONES or p in _TENS or p in _SCALE for p in parts):
            for p in parts:
                if p in _SCALE:
                    run = (run or 1) * _SCALE[p]
                else:
                    run = (run or 0) + _ONES.get(p, _TENS.get(p, 0))
            add(run)
        else:
            run = None
    return out


_MONTHS = ("january february march april may june july august september october november december").split()


def said_phrases(spoken) -> list[str]:
    """What the voice has said, as figures in context, lower-case and in digits: every number with the
    word after it ("15 cents", "50 miles", "1,000 units" → "1000 units"), every date whole ("february 2
    1925", "july 12 2026", "january 1913"), and a year said on its own ("in 1925" → "1925"). A figure
    is known in a later shot only as the same phrase: "15" said as "15 cents" does not make "January 15"
    known, and "2026" said in "July 12, 2026" does not make "January 15, 2026" known."""
    toks = []
    for raw in spoken:
        w = str(raw).lower().strip(".,;:!?\"'’()")
        for part in w.replace("-", " ").split():
            n = said_numbers([part])
            toks.append(n[0] if n and part not in _MONTHS else part.replace("$", ""))
    out: list[str] = []
    add = lambda x: out.append(x) if x not in out else None
    isnum = lambda t: bool(re.fullmatch(r"\d+(?:\.\d+)?", t))
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in _MONTHS:
            parts = [t]
            if i + 1 < len(toks) and isnum(toks[i + 1]) and float(toks[i + 1]) <= 31:
                parts.append(toks[i + 1])
                if i + 2 < len(toks) and re.fullmatch(r"1[5-9]\d\d|20\d\d", toks[i + 2]):
                    parts.append(toks[i + 2])
            elif i + 1 < len(toks) and re.fullmatch(r"1[5-9]\d\d|20\d\d", toks[i + 1]):
                parts.append(toks[i + 1])
            if len(parts) > 1:
                add(" ".join(parts))
                i += len(parts)
                continue
        if isnum(t):
            prev = toks[i - 1] if i else ""
            if re.fullmatch(r"1[5-9]\d\d|20\d\d", t) and prev not in _MONTHS:
                add(t)                                            # a year said on its own
            if i + 1 < len(toks) and not isnum(toks[i + 1]):
                add(f"{t} {toks[i + 1]}")
        i += 1
    return out


def frames_of(shot: dict) -> int:
    return round(float(shot["end"]) * FPS) - round(float(shot["start"]) * FPS)


def fill(obj, values: dict):
    """Every {{key}} in the plan's text, from facts.json; an unknown key is an error, never a guess."""
    if isinstance(obj, str):
        def one(m):
            if m.group(1) not in values:
                raise KeyError(f"no figure {{{{{m.group(1)}}}}} in facts.json")
            return str(values[m.group(1)])
        return PLACEHOLDER.sub(one, obj)
    if isinstance(obj, list):
        return [fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: fill(v, values) for k, v in obj.items()}
    return obj


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_url(path: Path) -> str:
    """A file under the repo as the stage's local server serves it."""
    return "/" + str(Path(path).resolve().relative_to(REPO.resolve()))


def cut_from_page(a: dict) -> bool:
    """A plate we cut from a book's page ourselves ("archive:visittosearsroeb00sear#n31-c24b"): already framed."""
    return bool(re.search(r"#[pn]\d+", str(a.get("id", ""))))


# type kinds that open over the outgoing picture, and the kinds whose picture can be held (render_shots.backdrop)
BACKDROP_KINDS = {"number", "pair", "formula", "kinetic", "timeline", "grid"}
BACKDROP_FROM = {"still", "texture", "archive", "stack", "split", "footage"}


def footage_frame(file: Path, t: float) -> Path:
    """One frame of a footage source, cached by the file and the second."""
    out = GRADED / "frames" / f"{sha(Path(file))[:16]}-{t:.2f}.jpg"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", str(file), "-frames:v", "1", "-q:v", "2", str(out)],
                       check=True, timeout=120)
    return out


SHRINK_EDGE, SHRINK_BYTES = 4800, 80_000_000


def workable(src: Path) -> Path:
    """The file a still is graded from. A master scan too large to grade safely is reduced once, cached,
    to SHRINK_EDGE px on its long edge (still more than a 4K frame needs). A Library of Congress TIFF of
    700 MB and 14,000 px made ffmpeg grow to 11 GB, and with four render workers the machine ran out of
    memory (2026-10-07). The provenance and the checksum stay the original's."""
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(src) as im:
            if max(im.size) <= SHRINK_EDGE and src.stat().st_size < SHRINK_BYTES:
                return src
            out = GRADED / "shrunk" / f"{sha(src)[:20]}-{SHRINK_EDGE}.jpg"
            if not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                small = im.convert("RGB")
                small.thumbnail((SHRINK_EDGE, SHRINK_EDGE), Image.LANCZOS)
                small.save(out, quality=95)
            return out
    except Exception:   # noqa: BLE001: a file PIL can't open is graded as it was
        return src


def graded_still(file: str | Path, mono: bool | None = None, placeholder: bool = False,
                 paper: bool = False, cut: bool = False) -> dict:
    """The still with the world grade, cached by its source's sha256. A labelled placeholder
    card (no picture exists yet) is shown as it is: it is not a picture to grade. `paper`: a print
    on the desk, never refused for its exposure (grade.plan's refuse=False); `cut`: a plate cut from
    a page, given no border trim (grade.plan's frame=False)."""
    src = Path(file)
    if placeholder:
        w, h = _size(src)
        return {"url": stage_url(src), "w": w, "h": h, "sha256": sha(src)}
    look = hashlib.sha256(grade.GRADE_JSON.read_bytes()).hexdigest()[:8]   # a new grade re-grades the still
    key = sha(src)[:20] + f"-{look}" + ("-mono" if mono else "") + ("-paper" if paper else "") + ("-cut" if cut else "")
    out = GRADED / f"{key}.jpg"
    if not out.exists():
        grade.still(workable(src), out, mono=mono, refuse=not paper, frame=not cut)
    w, h = _size(out)
    # the picture's own ground (photos.mjs lays a museum object on black or on a seamless on the desk itself)
    return {"url": stage_url(out), "w": w, "h": h, "sha256": sha(src), "ground": grade.ground_of(out)}


def _size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def _balanced(text: str) -> list[str]:
    """A thesis line in at most two lines of near-equal length, broken between words."""
    words = text.split()
    if len(" ".join(words)) <= 26 or len(words) < 4:
        return [" ".join(words)]
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


NOT_DRAWN = {"qa.mjs", "layout_qa.mjs", "profile.mjs"}   # film/v3 tools that check or time the stage
STAGE_BATCH = 12      # stage clips rendered, checked and recorded together


class Job:
    """A shot, resolved: what the renderer draws and everything that names its clip."""

    def __init__(self, shot: dict, plan: dict, timing: dict, facts: dict, d: Path):
        reg = shots.registry()
        self.shot, self.d = shot, d
        by_id = {s["id"]: s for s in plan["shots"]}
        src = by_id[shot["params"]["callback"]] if shot.get("style") == "callback" else shot
        self.kind, self.style = src.get("kind"), src.get("style")
        if shot.get("style") == "breath" and shot.get("room") == "paper":
            prev = plan["shots"][max(0, plan["shots"].index(shot) - 1)]
            src, self.kind, self.style = prev, prev.get("kind"), prev.get("style")
        values = {k: v.get("value", "") for k, v in facts.items()}
        start, self.frames = float(shot["start"]), frames_of(shot)
        if plan["shots"] and shot is plan["shots"][-1]:   # the end card holds past the last word
            self.frames += round(shots.end_tail(plan, reg) * FPS)
        self.seconds = self.frames / FPS
        words = shots.spoken(timing)
        on_abs = shots.resolve_on(shot, words)
        reveals = [{"key": r["key"], "t": round(float(r["t"]) - start, 3), "value": values.get(r["key"], "")}
                   for r in shot.get("reveals", [])]
        brand = facts.get("demo_brand", {}).get("value")
        self.room = shot.get("room")
        self.job = {
            "id": shot["id"], "kind": self.kind, "style": self.style, "seconds": self.seconds, "frames": self.frames,
            "render": reg["styles"].get(self.style, {}).get("render", {}), "drift_to": reg["drift"]["to"],
            "on": None if on_abs is None else round(on_abs - start, 3), "reveals": reveals, "says": shot.get("says", ""),
            "label": shot.get("label"), "demo_label": f"{brand} demo data" if brand else "demo data",
            # a callback draws the earlier shot again, and its own params override it (a gap, a line
            # the return should not repeat, set to null); `callback` itself is not drawn
            "params": fill({**(src.get("params") or {}),
                            **({k: v for k, v in (shot.get("params") or {}).items() if k != "callback"} if src is not shot else {})},
                           values),
            "focus": shot.get("focus") or src.get("focus"),
            "motion": shot.get("motion") or src.get("motion"), "overlay": fill(shot.get("overlay") or {}, values),
            "chart": src.get("chart"),
            # every spoken word under the shot, with its start in seconds from the shot's first
            # frame, so a stage can land a word, a stroke or a figure on the exact syllable
            "words": [{"w": w["word"], "t": round(float(w["start"]) - start, 3)}
                      for w in shots.words_in(words, start, float(shot["end"]))],
            # the figures' sources as a viewer reads them (sourcelabel.py); none where the
            # proof or demo label already says what the figure is
            # (a shot carrying the proof or demo label shows no other source: an incidental year's
            # source beside a case-study chart misleads more than it tells)
            # (a callback, or a page or ledger returning to figures said before, shows keys it does not
            # reveal: their sources are named too, after the ones it reveals)
            "source_label": None if shot.get("label") in ("proof", "demo") else sourcelabel.label(
                list(dict.fromkeys([r["key"] for r in reveals] + PLACEHOLDER.findall(json.dumps(
                    {**(src.get("params") or {}), **(shot.get("params") or {})}, ensure_ascii=False)))), facts),
        }
        # the figures the voice has already said before this shot's first frame: a kind may draw
        # them sharp from frame 0 (a table or a ledger returning to a value), never one still to come
        self.job["known"] = {r["key"]: values.get(r["key"], "") for r in shots.spoken_reveals(timing)
                             if float(r["t"]) < start - 0.05 and r["key"] in values}
        if self.kind == "archive":   # a print cut after a page or another print opens at a second scale (photos.mjs)
            i = plan["shots"].index(shot)
            prev = plan["shots"][i - 1] if i else {}
            self.job["prev_kind"] = prev.get("kind")
            self.job["prev_print"] = bool(((prev.get("params") or {}).get("print") or {}).get("asset"))
        # every number the voice has said before this shot, as digits, whatever the fact files say:
        # a figure said in an earlier shot ("1925" in e37) may stand whole in a later one (e40)
        # (numbers under 13 are too common to be the same figure again: "eight in ten" is not the 8 ounces)
        self.job["said_before"] = [n for n in said_numbers(w["word"] for w in words if float(w["start"]) < start - 0.05)
                                   if "." in n or float(n) >= 13]
        self.job["said_phrases"] = said_phrases(w["word"] for w in words if float(w["start"]) < start - 0.05)
        # a callback carries its source as it ended, so a cut straight from it continues its layout
        self.src = src
        i = plan["shots"].index(shot)
        self.prev = plan["shots"][i - 1] if i else None
        if src is not shot:
            i = plan["shots"].index(shot)
            self.job["callback"] = {"of": src["id"],
                                    "adjacent": i > 0 and plan["shots"][i - 1]["id"] == src["id"],
                                    "params": fill({k: v for k, v in (src.get("params") or {}).items() if k != "print"}, values),
                                    "seconds": frames_of(src) / FPS,
                                    "has_print": bool((src.get("params") or {}).get("print"))}
        self.assets: list[str] = []
        if LOOK == "v3" and self.kind == "chart":
            run = d / "run.json"
            scene = (self.job.get("chart") or {}).get("scene")
            if run.exists() and scene:
                self.job["chart_data"] = json.loads(run.read_text(encoding="utf-8")).get(scene)
        self._defaults(shot, timing, facts, words, start)

    def _defaults(self, shot, timing, facts, words, start):
        j, p = self.job, self.job["params"]
        key = next((r["key"] for r in j["reveals"]), None)
        if self.kind == "number":
            k = re.fullmatch(r"\{\{\s*([a-z0-9_]+)\s*\}\}", shot.get("on") or "")
            k = k.group(1) if k else key
            fact = facts.get(k, {})
            p.setdefault("value", fact.get("value", ""))
            p.setdefault("sub", fact.get("label", ""))
            p.setdefault("estimate", "estimate" in str(fact.get("source", "")).lower())
        if self.kind == "pair":
            rv = j["reveals"]
            for side, r in zip(("left", "right"), rv[:2]):
                p.setdefault(side, {})
                p[side].setdefault("value", r["value"])
                p[side].setdefault("label", facts.get(r["key"], {}).get("label", ""))
                p[side].setdefault("at", r["t"])
        if self.kind == "kinetic":
            lines = _balanced(j["says"])
            p.setdefault("lines", lines)
            if len(lines) == 2:
                first = len(lines[0].split())
                inside = shots.words_in(words, float(shot["start"]), float(shot["end"]))
                p.setdefault("at", [0.0, round(inside[first]["start"] - start, 3) if len(inside) > first else 0.9])
        if self.kind == "chapter":
            cards = [c for c in timing["segments"] if c["kind"] == "card"]
            card = next((c for c in cards if abs(float(c["start"]) - start) < 0.05), None)
            p.setdefault("title", (card or {}).get("title", ""))
            if card is not None:
                p.setdefault("index", cards.index(card) + 1)   # "Chapter IV": the card's place in the film
        if self.kind == "end":
            for k, v in END.items():
                p.setdefault(k, v)

    @property
    def renderer(self) -> str:
        if self.kind == "footage":
            return "footage"
        if self.kind == "chart":
            scene = (self.job.get("chart") or {}).get("scene")
            if LOOK == "v3":
                return "stage"
            if scene in MANIM_SCENES:
                return "manim"
            if scene in STAGE_CHARTS:
                return "stage"
            raise ValueError(f"{self.shot['id']}: no renderer draws the chart scene {scene!r}")
        return "stage"

    def resolve_assets(self):
        """Grade the stills and record every source file's sha256 for the cache key."""
        a = self.shot.get("asset")
        if self.kind in ("still", "texture", "archive", "split") and isinstance(a, dict):
            g = graded_still(a["file"], mono=True if self.kind in ("archive", "split") else None,
                             placeholder=str(a.get("id", "")).startswith("placeholder:"),
                             paper=self.kind in ("archive", "split"), cut=cut_from_page(a))
            self.job["asset"] = {**{k: a.get(k) for k in ("credit", "place", "title")}, "date": display_date(a.get("date")), **g}
            self.assets.append(g["sha256"])
        if self.kind == "stack" and isinstance(a, list):
            self.job["assets"] = []
            for x in a:
                g = graded_still(x["file"], mono=True, paper=True, cut=cut_from_page(x))
                self.job["assets"].append({**{k: x.get(k) for k in ("credit", "place", "at")}, "date": display_date(x.get("date")), **g})
                self.assets.append(g["sha256"])
        if self.kind == "footage" and isinstance(a, dict):
            self.assets.append(sha(Path(a["file"])))
        # a companion print beside a figure: the picture the sentence is about, on the desk to
        # the right of the type (v3), graded as the archive grades its prints
        comp = (self.shot.get("params") or {}).get("print") or {}
        cb = self.job.get("callback") or {}
        if not comp and cb.get("adjacent") and cb.get("has_print"):   # the source's print stays on the desk across the cut
            comp = {**((self.src.get("params") or {}).get("print") or {}), "at": None}
        if LOOK == "v3" and isinstance(comp.get("asset"), dict) and comp["asset"].get("file"):
            ca = comp["asset"]
            year = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", str(ca.get("date") or ""))
            g = graded_still(ca["file"], mono=True if year and int(year.group(1)) < 1970 else None,
                             paper=True, cut=cut_from_page(ca))
            self.job["print"] = {**{k: ca.get(k) for k in ("credit", "place", "title", "author", "trim")},
                                 "date": display_date(ca.get("date")), "at": comp.get("at"), "out": comp.get("out"),
                                 "caption": comp.get("caption"), "focus": comp.get("focus"),
                                 # photos.mjs: "object" or "print", the object's box, and its regions drawn out of focus
                                 "treat": comp.get("treat"), "box": comp.get("box"), "soft": comp.get("soft"), **g}
            self.job["params"].pop("print", None)
            self.assets.append(g["sha256"])
        if self.kind == "split":
            right = (self.shot.get("params") or {}).get("right") or {}
            if right.get("file"):
                self.assets.append(sha(Path(right["file"])))
                if LOOK == "v3":   # the print's face while it drops: the footage's first frame, graded as it will play
                    self.job.setdefault("params", {}).setdefault("right", {})["poster"] = stage_url(split_poster(right))
        self.backdrop()

    def backdrop(self) -> None:
        """The outgoing picture held under the type as it lands (a J-cut for the eye): the previous
        shot's last frame, graded as it played, so a type shot never opens on an empty desk. A
        nicety: a picture that can't be had leaves the desk as it was."""
        prev = getattr(self, "prev", None) or {}
        if LOOK != "v3" or self.kind not in BACKDROP_KINDS or self.job.get("print") or prev.get("kind") not in BACKDROP_FROM:
            return
        pa = prev.get("asset")
        pa = pa[-1] if isinstance(pa, list) and pa else pa
        if not isinstance(pa, dict) or not pa.get("file"):
            return
        try:
            src = Path(pa["file"])
            if prev["kind"] == "footage":
                t = float(pa.get("in") or 0) + float(prev["end"]) - float(prev["start"]) - 0.1
                src = footage_frame(src, t)
            paper = prev["kind"] in ("archive", "split", "stack")
            g = graded_still(src, mono=True if paper else None, paper=paper)
        except Exception:   # noqa: BLE001
            return
        self.job["backdrop"] = {"url": g["url"], "focus": prev.get("focus") or [0.5, 0.5]}
        self.assets.append(g["sha256"])

    def key(self) -> str:
        # the stage's own files are in the key; its checking tools draw nothing and are not (an edit to qa.mjs
        # once re-rendered every clip of a film)
        files = ["assets/tokens.json", "assets/grade.json", "film/styles.json", "film/shots.css", "film/shots.mjs"]
        if LOOK == "v3":   # the shared stage, and only this shot's own kind module, so editing one kind re-renders its clips alone
            v3 = CONTENT_DIR / "film" / "v3"
            family = V3_FAMILY.get(self.kind, "type")
            files += sorted(str(p.relative_to(CONTENT_DIR)) for p in v3.glob("*")
                            if p.suffix in (".css", ".mjs", ".js", ".html") and p.name not in NOT_DRAWN and not p.name.endswith(".test.mjs"))
            files += [f"film/v3/kinds/{family}.mjs", f"film/v3/kinds/{family}.css"]
            if self.job.get("print") and family != "photos":   # a companion print is drawn by the photos kind
                files += ["film/v3/kinds/photos.mjs", "film/v3/kinds/photos.css"]
        look ="".join((CONTENT_DIR / p).read_text(encoding="utf-8") for p in files)
        blob = json.dumps({"job": self.job, "assets": self.assets, "renderer": self.renderer, "room": self.room,
                           "asset": self.shot.get("asset"), "version": VERSION}, sort_keys=True, default=str)
        return hashlib.sha256((blob + look).encode()).hexdigest()


def _grain(room: str) -> str:
    return grade.spec()["grain"]["paper" if room == "paper" else "world"]


def _clip_ok(path: Path, frames: int) -> bool:
    return path.exists() and footage.probe(path)["frames"] == frames


def _manim(job: Job, out: Path):
    """An engine chart as a shot: the Manim scene renders the shot's own time span."""
    from .render_scenes import ENTRY
    s = job.shot
    seg = {"start": float(s["start"]), "end": float(s["start"]) + job.seconds, "index": int(re.sub(r"\D", "", s["id"]) or 0),
           # a callout is a figure: a spoken label ("demo data", the demo's name) is not drawn as one
           "reveals": {r["key"]: {"t": float(s["start"]) + r["t"], "value": r["value"]} for r in job.job["reveals"]
                       if re.search(r"\d", str(r.get("value", "")))},
           "vo": s.get("says", ""), "proof": s.get("label") == "proof", "kind": "beat",
           "title": (job.job["params"] or {}).get("heading", "")}
    with tempfile.TemporaryDirectory(prefix="hubricon-manim-") as tmp:
        env = {**os.environ, "HC_CONTEXT": json.dumps({"dir": str(job.d), "segment": seg}), "PYTHONWARNINGS": "ignore"}
        cmd = [str(CONTENT_DIR / ".venv" / "bin" / "manim"), "render", "-r", "1920,1080", "--fps", str(FPS), "--disable_caching",
               "--media_dir", tmp, "-o", "clip.mp4", "-v", "WARNING", "--progress_bar", "none", str(ENTRY),
               MANIM_SCENES[job.job["chart"]["scene"]]]
        res = subprocess.run(cmd, cwd=str(CONTENT_DIR), env=env, capture_output=True, text=True, timeout=3600)
        if res.returncode != 0:
            raise RuntimeError(f"manim failed on {s['id']}:\n{res.stderr[-1500:]}")
        raw = next(Path(tmp).rglob("clip.mp4"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", f"{_grain('paper')},format=yuv420p,tpad=stop_mode=clone:stop_duration=0.5",
                        "-frames:v", str(job.frames), "-r", str(FPS), "-an", *grade.encode_args(), str(out)], check=True, timeout=1800)


NOW_GRADE = "eq=saturation=0.65,colortemperature=temperature=5400:mix=0.5"   # = photos.mjs NOW_GRADE


def split_poster(right: dict) -> Path:
    """The then-and-now's "now" frame at its in point, with the world grade and the stage's NOW_GRADE,
    cached by the footage's sha256 and in point."""
    src = Path(right["file"])
    start = float(right.get("in", 0.0))
    out = GRADED / f"poster-{sha(src)[:16]}-{start:.2f}.jpg"
    if not out.exists():
        g = grade.plan(src, focus=right.get("focus", (0.5, 0.5)), start=start, duration=1.0, strict=False, grain=False)
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"{g['filter']},{NOW_GRADE}", "-q:v", "2", str(out)], check=True, timeout=300)
    return out


def _split_composite(job: Job, stage_clip: Path, rect: dict, out: Path):
    """Then and now (W11): the present-day footage plays inside the stage's right panel. The v3
    stage declares its contract on `.split-right`: `at` (the landing frame the footage starts on),
    `rot` (degrees clockwise about the rect's centre, so it sits square in its tilted print) and
    `grade` (an ffmpeg chain after the world grade); the paper stage gives none of them."""
    right = job.shot["params"]["right"]
    at = rect.get("at")
    if at is None:
        at = float(job.shot.get("params", {}).get("right_at", job.job["on"] if job.job["on"] is not None else job.job["render"]["right_at_s"]))
    n = max(1, job.frames - round(float(at) * FPS))
    with tempfile.TemporaryDirectory(prefix="hubricon-split-") as tmp:
        clip = Path(tmp) / "right.mp4"
        footage.render(Path(right["file"]), clip, n, start=float(right.get("in", 0.0)), focus=right.get("focus", (0.5, 0.5)))
        w, h = round(rect["w"]), round(rect["h"])
        cx, cy = rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2
        rot = float(rect.get("rot") or 0.0)
        chain = [f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}"] + ([rect["grade"]] if rect.get("grade") else [])
        if rot:
            r = f"{rot}*PI/180"
            chain += ["format=rgba", f"rotate={r}:c=none:ow=rotw({r}):oh=roth({r})"]
        fc = (f"[1:v]fps={FPS},{','.join(chain)},setpts=PTS-STARTPTS+{float(at):.3f}/TB[r];"
              f"[0:v][r]overlay=x={cx:.1f}-overlay_w/2:y={cy:.1f}-overlay_h/2:eof_action=pass:repeatlast=0,format=yuv420p")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(stage_clip), "-i", str(clip), "-filter_complex", fc,
                        "-frames:v", str(job.frames), "-an", *grade.encode_args(), str(out)], check=True, timeout=1800)


def render(u: dict, q: dict | None = None, force: bool = False, only: set[str] | None = None,
           workers: int | None = None) -> dict:
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    tokens.refresh()
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, note = shots.load_timing(d)
    if timing is None:
        return {"status": "failed", "reason": "no timing"}
    if timing.get("estimated"):
        return {"status": "blocked", "reason": "the timing is the 150-wpm estimate; render-shots needs the narration's own timing"}
    facts = scriptmod.load_facts(slug)
    if slug != "visual-trial":   # a film renders on the look the founder approved, or not at all
        from . import visual_lock
        moved = visual_lock.drift()
        if moved is None:
            return {"status": "blocked", "reason": "the long films' look is not locked yet: the founder watches the visual trial, then `hubricon-content visual-lock`"}
        if moved:
            return {"status": "blocked", "reason": f"the look moved since the founder locked it: {', '.join(moved)}; re-run the trial and re-lock deliberately"}
    out_dir = d / "shots"
    out_dir.mkdir(exist_ok=True)
    workers = workers or max(1, min(4, (os.cpu_count() or 4) // 4))
    stage, others, done, skipped = [], [], [], []
    for s in plan["shots"]:
        if only and s["id"] not in only:
            continue
        job = Job(s, plan, timing, facts, d)
        job.resolve_assets()
        clip, side = out_dir / f"{s['id']}.mp4", out_dir / f"{s['id']}.json"
        k = job.key()
        if not force and side.exists() and json.loads(side.read_text()).get("key") == k and _clip_ok(clip, job.frames):
            skipped.append(s["id"])
            continue
        (stage if job.renderer == "stage" else others).append((job, clip, side, k))
    def finish(job, clip, side, k):
        if not _clip_ok(clip, job.frames):
            raise RuntimeError(f"{clip.name}: not {job.frames} frames")
        side.write_text(json.dumps({"key": k, "frames": job.frames, "renderer": job.renderer, "version": VERSION}) + "\n")
        done.append(job.shot["id"])

    # the stage renders in batches, each recorded the moment it finishes: an interrupted run keeps every
    # finished batch (2026-10-07: the sidecars were written only after the whole film, so a reboot an hour
    # in threw the hour away, twice)
    for b in range(0, len(stage), STAGE_BATCH):
        part = stage[b:b + STAGE_BATCH]
        jobs = []
        for job, clip, side, k in part:
            target = clip.with_suffix(".stage.mp4") if job.kind == "split" else clip
            jobs.append({**job.job, "out": str(target), "vf": _grain(job.room), "encode": grade.encode_args()})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(jobs, f)
            jobs_file = f.name
        try:
            res = subprocess.run(["node", str(RENDER_MJS), "--shots", jobs_file, "--workers", str(workers)], cwd=str(REPO),
                                 capture_output=True, text=True, timeout=6 * 3600)
        finally:
            os.unlink(jobs_file)
        if res.returncode != 0:
            raise RuntimeError(f"the stage failed:\n{res.stderr[-2000:]}")
        rects = json.loads(res.stdout.strip().splitlines()[-1])
        for job, clip, side, k in part:
            if job.kind == "split":
                tmp = clip.with_suffix(".stage.mp4")
                _split_composite(job, tmp, rects[job.shot["id"]]["rect"], clip)
                tmp.unlink()
            finish(job, clip, side, k)
    for job, clip, side, k in others:
        if job.renderer == "footage":
            a = job.shot["asset"]
            footage.render(Path(a["file"]), clip, job.frames, start=float(a.get("in", 0.0)), focus=job.job["focus"] or (0.5, 0.5))
        elif job.renderer == "manim":
            _manim(job, clip)
        finish(job, clip, side, k)
    return {"status": "ok", "rendered": len(done), "cached": len(skipped), "workers": workers}


def run(u: dict, q: dict, force: bool = False) -> dict:
    return render(u, q, force=force)
