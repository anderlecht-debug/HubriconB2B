"""The automatic filters every candidate passes before anything is picked
(VISUAL_SPEC.md §6.4), so the visual pick spends its eye only on footage and
photographs the film could actually use.

Three stages, cheapest first, each recording what it found in `checks` and,
in plain words, why it refused in `rejected_because`:

- `precheck`, from the record alone: the licence is on §6.3's accept list, the
  provenance names an author, a page and a licence, nothing in it suggests
  Amazon (§6.1), nothing generated or animated (§6.5), a named subject is named
  by the record (§6.2), and the asset is not inside the usage window (§6.7);
- `metadata`, from the full rendition's size, frame rate and length;
- `media`, from the small preview (downloaded once and analysed once): mean
  luma inside the band the grade can reach (§3.2), the cuts (`scdet`) and the
  longest continuous take, faces (YuNet, a frame every 2 s), text (tesseract,
  when installed) and a perceptual hash against the film's picks and the
  ledger.

The luma band is §3.2's arithmetic: the grade lands mean luma at 138 ± 10 and
refuses an asset that needs more than ±0.12 `eq=brightness` (about ±31 of 255),
so a source is usable from about 97 to 179; under 64 it is night or low-key,
which §6.1 rejects outright.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import shots as shotmod
from ..state import CONTENT_DIR

MODEL = CONTENT_DIR / "assets" / "models" / "face_detection_yunet_2023mar.onnx"
FOOTAGE_MIN = (1920, 1080)
# Ruling, 2026-10-05 (§6.4 note): archival film at 1080p barely exists, so it is held to
# the stills' "never upscaled past 1.5×": at least 1280×720.
ARCHIVAL_FILM_MIN = (1280, 720)
STILL_LONG_EDGE, ARCHIVAL_LONG_EDGE = 2400, 1600
MAX_UPSCALE = 1.5
STYLE_FLOOR = {"still-push": ("long edge", 2000), "still-reveal": ("width", 2600)}   # §14, W1 and W3
STYLE_ZOOM = {"still-reveal": 1.35}                                                    # W3 starts at 1.35
PAPER_BOX = {"archive": (1180, 760), "stack": (1180, 760), "split": (880, 620)}        # W5, W6, W11
LUMA_TARGET, LUMA_TOL, MAX_SHIFT = 138, 10, 0.12
LUMA_BAND = (LUMA_TARGET - LUMA_TOL - MAX_SHIFT * 255, LUMA_TARGET + LUMA_TOL + MAX_SHIFT * 255)
LUMA_NIGHT = 64                                                                        # 0.25 of full scale (§6.1)
FACE_MAX, FACE_SCORE = 0.01, 0.8
SAMPLE_EVERY = 2.0
OCR_WORDS = 2
OCR_UNAVAILABLE = "ocr: unavailable — the visual pick checks by eye"
PHASH_DUP = 10
SCDET_THRESHOLD = 12
NEED = 3
ANALYSIS_VERSION = 2


# ── the shot a candidate is checked for ──
def context(shot: dict, reg: dict | None = None) -> dict:
    reg = reg or shotmod.registry()
    st = reg["styles"].get(shot.get("style"), {})
    return {"id": shot.get("id"), "kind": shot.get("kind"), "style": shot.get("style"),
            "length": round(float(shot["end"]) - float(shot["start"]), 3), "specific": shot.get("specific"),
            "zoom": STYLE_ZOOM.get(shot.get("style"), st.get("max_scale", 1.08)),
            "archival": set(reg["sources"]["archival"]), "stock": set(reg["sources"]["stock"]),
            "cliches": reg.get("cliches", [])}


def archival(c: dict, ctx: dict) -> bool:
    return c["source"] in ctx["archival"]


def _check(c: dict, key: str, value) -> None:
    c.setdefault("checks", {})[key] = value


def _reject(c: dict, why: str) -> None:
    c.setdefault("rejected_because", []).append(why)


def finish(c: dict) -> dict:
    c["passed_filters"] = not c.get("rejected_because")
    return c


def fps_family(fps) -> str | None:
    if not fps:
        return None
    r = round(float(fps))
    return "30/60" if r in (30, 60, 120) else "24/25" if r in (24, 25, 48, 50) else "other"


def _words(c: dict) -> str:
    return " ".join(str(c.get(k) or "") for k in ("title", "description", "subject", "place")) + " " + " ".join(c.get("tags") or [])


STOP = {"and", "the", "with", "of", "on", "in", "at", "a", "an", "for", "to", "from", "by", "into", "onto"}
# Libraries whose search matches any one word of the query, so a result may share none of its nouns:
# their candidates must name at least half of them.
ANY_WORD, ANY_WORD_MIN = {"pixabay"}, 0.5


def _stem(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("xes", "ches", "shes", "sses")):
        return w[:-2]
    return w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w


def relevance(c: dict, query: str, titled: bool = False) -> float:
    """The share of the query's nouns (its subject words, verbs of action dropped) that the
    record names in its title, tags, description or page; with `titled`, in its title,
    subjects and tags only (an archive's search also matches its long catalogue notes)."""
    from . import nouns
    want = {_stem(w) for w in re.findall(r"[a-z]+", nouns(query).lower()) if len(w) > 2 and w not in STOP}
    text = (" ".join(str(c.get(k) or "") for k in ("title", "subject")) + " " + " ".join(c.get("tags") or [])
            if titled else _words(c) + " " + str(c.get("url") or ""))
    have = {_stem(w) for w in re.findall(r"[a-z]+", text.lower())}
    return round(len(want & have) / len(want), 2) if want else 0.0


# ── 1. the record ──
def precheck(c: dict, ctx: dict, prior: dict | None = None) -> bool:
    """What the record alone decides. `prior` maps an asset id already spoken for to where:
    another shot's pick in this film, or a film inside the usage window."""
    c["checks"], c["rejected_because"] = {}, []
    lic = c.get("licence")
    if lic and shotmod.licence_ok(lic):
        _check(c, "licence", lic)
    else:
        _check(c, "licence", None)
        _reject(c, f"licence not on the accept list: {c.get('rights') or 'none stated'} (§6.3)")
    missing = [k for k in ("author", "url") if not c.get(k)]
    _check(c, "provenance", "complete" if not missing else f"lacks {', '.join(missing)}")
    if missing:
        _reject(c, f"provenance lacks {', '.join(missing)} (§6.4)")
    words = _words(c).lower()
    if re.search(r"\bamazon", words):
        _check(c, "brand", "amazon")
        _reject(c, "the record names Amazon: nothing may suggest affiliation (§6.1)")
    if c.get("ai_generated") or c.get("footage_type") == "animation":
        _check(c, "generated", True)
        _reject(c, "generated or animated, not filmed (§6.5)")
    if c.get("query"):
        rel = relevance(c, c["query"])
        _check(c, "relevance", rel)
        if rel < ANY_WORD_MIN and c["source"] in ANY_WORD:
            _reject(c, "its tags name fewer than half of the query's nouns (§6.1, the concrete noun)")
        if archival(c, ctx) and not relevance(c, c["query"], titled=True):
            _reject(c, "its title and subjects name none of the query's nouns (§6.1, the concrete noun)")
    hits = sorted({x for x in ctx.get("cliches", []) if re.search(rf"\b{re.escape(x)}\b", words)})
    if hits:
        _check(c, "cliche_words", hits)
        named = " ".join([str(c.get("title") or "")] + list(c.get("tags") or [])).lower()
        shown = [x for x in hits if re.search(rf"\b{re.escape(x)}\b", named)]
        if shown and c["source"] in ctx["stock"]:   # a stock clip's title and tags say what is in the picture
            _reject(c, f"its title or tags name {shown[0]!r}, a banned cliché (§6.1)")
    name = ctx.get("specific")
    if name:
        named = name.lower() in words or name.lower() in str(c.get("url", "")).lower()
        _check(c, "names_specific", named)
        if not archival(c, ctx):
            _reject(c, f"the sentence names {name!r}: only archival evidence may show it (§6.2)")
        elif not named:
            _reject(c, f"the record does not name {name!r} (§6.2)")
    if ctx.get("kind") == "split" and c.get("side") == "then" and not c.get("date"):
        _reject(c, "the then side of a then-and-now needs a date in its record (§14, W11)")
    if prior and c["id"] in prior:
        _check(c, "usage", prior[c["id"]])
        _reject(c, f"already used {prior[c['id']]} (§6.7)")
    return not c["rejected_because"]


# ── 2. the full rendition's metadata ──
def metadata(c: dict, ctx: dict) -> bool:
    w, h = int(c.get("width") or 0), int(c.get("height") or 0)
    arch = archival(c, ctx)
    if not (w and h):
        _reject(c, "the full rendition's size is not in the record (§6.4)")
        return False
    _check(c, "resolution", f"{w}×{h}")
    if c["kind"] == "video":
        fw, fh = ARCHIVAL_FILM_MIN if arch else FOOTAGE_MIN
        if w < fw or h < fh:
            _reject(c, f"{w}×{h}: {'archival film' if arch else 'footage'} is at least {fw}×{fh} (§6.4)")
        _fps(c, ctx)
        need = ctx["length"] + 1
        if c.get("duration") and float(c["duration"]) < need - 1e-6:
            _reject(c, f"{float(c['duration']):.1f} s long; the shot needs {need:.1f} s, its length plus one (§6.4)")
    else:
        floor = ARCHIVAL_LONG_EDGE if arch else STILL_LONG_EDGE
        if max(w, h) < floor:
            _reject(c, f"{w}×{h}: {'an archival' if arch else 'a'} still is at least {floor:,} px on its long edge (§6.4)")
        what, px = STYLE_FLOOR.get(ctx.get("style"), (None, 0))
        if what and (max(w, h) if what == "long edge" else w) < px:
            _reject(c, f"{w}×{h}: {ctx['style']} needs a source at least {px:,} px on its {what} (§14)")
        if ctx["kind"] in PAPER_BOX:
            bw, bh = PAPER_BOX[ctx["kind"]]
            scale = min(bw / w, bh / h)
        else:
            scale = max(1920 / w, 1080 / h) * float(ctx.get("zoom") or 1.08)
        _check(c, "upscale", round(scale, 2))
        if scale > MAX_UPSCALE + 1e-6:
            _reject(c, f"would be enlarged {scale:.2f}× on screen; never past {MAX_UPSCALE}× (§6.4)")
    return not c["rejected_because"]


def _fps(c: dict, ctx: dict) -> None:
    """30 or 60 fps; 24 or 25 only when a shot has nothing else (decided in `fps_rule`).
    Archival film runs at its own rate (16 to 24 fps) and is conformed, so it is only recorded."""
    fps = c.get("fps")
    if not fps:
        return
    _check(c, "fps", fps)
    if not archival(c, ctx) and fps_family(fps) == "other":
        _reject(c, f"{float(fps):g} fps: footage runs at 30 or 60 (24 or 25 only when nothing else exists) (§6.4)")


def fps_rule(cands: list[dict], ctx: dict, need: int = NEED) -> None:
    """§6.4: 24 and 25 fps only when nothing else exists. Read per shot and per sentence: a
    passing 24/25 clip is refused when `need` passing clips at 30 or 60 fps name at least as
    many of the query's nouns (`relevance`); otherwise it stays, so a shot is never left with
    smooth footage of the wrong thing, and says so."""
    live = [c for c in cands if c.get("passed_filters") and c["kind"] == "video" and not archival(c, ctx)]
    pref = [c for c in live if fps_family(c.get("fps")) == "30/60"]
    for c in (c for c in live if fps_family(c.get("fps")) == "24/25"):
        rel = (c.get("checks") or {}).get("relevance", 0)
        better = [x for x in pref if (x.get("checks") or {}).get("relevance", 0) >= rel]
        if len(better) >= need:
            c["checks"].pop("fps_note", None)
            _reject(c, f"{float(c['fps']):g} fps: this shot has {len(better)} candidates at 30 or 60 fps "
                       f"that name as much of the query (§6.4)")
            finish(c)
        else:
            _check(c, "fps_note", f"{float(c['fps']):g} fps admitted: fewer than {need} candidates at 30 or 60 fps "
                                  f"name as much of the query")


# ── 3. the preview ──
def probe(path: Path) -> dict:
    """Width, height, frame rate and length of a media file, by ffprobe."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=120)
    doc = json.loads(out.stdout or "{}")
    st = (doc.get("streams") or [{}])[0]

    def rate(s):
        try:
            a, b = str(s).split("/")
            return float(a) / float(b) if float(b) else None
        except (ValueError, ZeroDivisionError):
            return None
    fps = rate(st.get("avg_frame_rate")) or rate(st.get("r_frame_rate"))
    try:
        dur = float((doc.get("format") or {}).get("duration") or 0) or None
    except ValueError:
        dur = None
    return {"width": st.get("width"), "height": st.get("height"), "fps": round(fps, 3) if fps else None, "duration": dur}


def luma_and_cuts(path: Path, video: bool = True) -> tuple[float | None, list[float]]:
    """Mean luma (signalstats YAVG, TV range, 0–255) and the scene cuts (scdet), in one pass."""
    with tempfile.TemporaryDirectory() as tmp:
        meta = Path(tmp) / "meta.txt"
        chain = (f"scdet=threshold={SCDET_THRESHOLD}," if video else "") + \
            f"scale=out_range=tv,format=yuv420p,signalstats,metadata=mode=print:file={meta}"
        cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vf", chain, "-an"] + ([] if video else ["-frames:v", "1"]) + ["-f", "null", "-"]
        subprocess.run(cmd, capture_output=True, timeout=900)
        text = meta.read_text(encoding="utf-8") if meta.exists() else ""
    ys = [float(m) for m in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", text)]
    cuts = sorted({round(float(m), 3) for m in re.findall(r"lavfi\.scd\.time=([\d.]+)", text)})
    return (round(sum(ys) / len(ys), 2) if ys else None), [t for t in cuts if t > 0]


def longest_take(cuts: list[float], duration: float | None) -> float:
    edges = [0.0] + sorted(cuts) + [float(duration or 0)]
    return round(max(b - a for a, b in zip(edges, edges[1:])), 3) if duration else 0.0


_detector = None


def detect_faces(bgr) -> list[tuple[float, float]]:
    """Faces in one frame as (share of the frame's area, score), by OpenCV's YuNet."""
    global _detector
    import cv2
    h, w = bgr.shape[:2]
    if _detector is None:
        _detector = cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), FACE_SCORE, 0.3, 5000)
    _detector.setInputSize((w, h))
    _, faces = _detector.detect(bgr)
    return [(float(f[2] * f[3]) / float(w * h), float(f[-1])) for f in (faces if faces is not None else [])]


def ocr_words(img) -> int | None:
    """Words tesseract reads in a frame, or None where tesseract is not installed."""
    if not shutil.which("tesseract"):
        return None
    import pytesseract
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    return sum(1 for w, conf in zip(data["text"], data["conf"])
               if len(re.sub(r"\W", "", str(w))) >= 2 and float(conf) >= 60)


def _frames(path: Path, info: dict, every: float = SAMPLE_EVERY):
    """One frame every `every` seconds, decoded at no more than 640 px wide, as BGR arrays."""
    import numpy as np
    w0, h0 = int(info.get("width") or 0), int(info.get("height") or 0)
    if not (w0 and h0):
        return
    w = min(640, w0) // 2 * 2
    h = max(2, round(h0 * w / w0 / 2) * 2)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vf", f"fps=1/{every:g},scale={w}:{h}",
                             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = w * h * 3
    try:
        k = 0
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield k * every, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            k += 1
    finally:
        proc.stdout.close()
        proc.wait(timeout=60)


def _strip(frames, video: bool):
    """The contact-sheet strip: three frames of footage at 320×180, or the image within 480×360."""
    from PIL import Image
    from .. import tokens
    if video:
        out = Image.new("RGB", (960, 180), tokens.rgb("paper_2"))
        for i, im in enumerate(frames[:3]):
            out.paste(_cover(im, 320, 180), (320 * i, 0))
        return out
    out = Image.new("RGB", (480, 360), tokens.rgb("paper_2"))
    im = frames[0].copy()
    im.thumbnail((480, 360))
    out.paste(im, ((480 - im.width) // 2, (360 - im.height) // 2))
    return out


def _cover(im, w, h):
    s = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))))
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def analyse(path: Path, kind: str, sha256: str | None = None) -> dict:
    """Everything the preview tells, independent of the shot: cached beside the preview,
    so a candidate offered to two shots is decoded once."""
    import imagehash
    import numpy as np
    from PIL import Image
    path = Path(path)
    memo, strip_path = path.with_name(path.name + ".analysis.json"), path.with_name(path.name + ".strip.jpg")
    if memo.exists() and strip_path.exists():
        doc = json.loads(memo.read_text(encoding="utf-8"))
        if doc.get("version") == ANALYSIS_VERSION and (sha256 is None or doc.get("sha256") == sha256):
            doc["strip"] = str(strip_path)
            return doc
    video = kind == "video"
    faces, picks = [], []
    if video:
        info = probe(path)
        luma, cuts = luma_and_cuts(path, video=True)
        samples = []
        for t, bgr in _frames(path, info):
            found = detect_faces(bgr)
            faces.append({"t": t, "max_area": round(max((a for a, _ in found), default=0.0), 4), "n": len(found)})
            samples.append((t, bgr))
        if not samples:
            raise ValueError("no frames could be decoded")
        n = len(samples)
        idx = sorted({min(n - 1, int((n - 1) * f + 0.5)) for f in (1 / 6, 1 / 2, 5 / 6)})
        picks = [Image.fromarray(samples[i][1][:, :, ::-1].copy()) for i in idx]
        middle = Image.fromarray(samples[n // 2][1][:, :, ::-1].copy())
        del samples
    else:
        with Image.open(path) as im:
            middle = im.convert("RGB")
        info = {"width": middle.width, "height": middle.height, "fps": None, "duration": None}
        luma, cuts = luma_and_cuts(path, video=False)
        small = middle.copy()
        small.thumbnail((1280, 1280))
        found = detect_faces(np.asarray(small)[:, :, ::-1].copy())
        faces.append({"t": 0.0, "max_area": round(max((a for a, _ in found), default=0.0), 4), "n": len(found)})
        picks = [middle]
    doc = {"version": ANALYSIS_VERSION, "sha256": sha256, "preview": info, "luma": luma, "cuts": cuts,
           "longest_take": longest_take(cuts, info.get("duration")) if video else None,
           "faces": faces, "max_face": max((f["max_area"] for f in faces), default=0.0),
           "phash": str(imagehash.phash(middle)), "ocr_words": ocr_words(middle)}
    _strip(picks, video).save(strip_path, quality=85)
    memo.write_text(json.dumps(doc), encoding="utf-8")
    doc["strip"] = str(strip_path)
    return doc


def phash_distance(a: str, b: str) -> int:
    import imagehash
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def media(c: dict, a: dict, ctx: dict, hashes: dict | None = None) -> bool:
    """What the preview decides for this shot. `hashes` maps an asset id to (phash, where it is
    already used): the film's picks, the usage window, and the candidates already passed here."""
    arch = archival(c, ctx)
    luma = a.get("luma")
    _check(c, "luma", luma)
    lo, hi = LUMA_BAND
    if luma is None:
        _reject(c, "the preview's luma could not be measured")
    elif luma < LUMA_NIGHT:
        _reject(c, f"mean luma {luma:.0f}: night or low-key, under {LUMA_NIGHT} (§6.1)")
    elif not lo <= luma <= hi:
        _reject(c, f"mean luma {luma:.0f}: outside {lo:.0f}–{hi:.0f}, the band the grade can reach (§3.2)")
    if c["kind"] == "video":
        pv = a.get("preview") or {}
        if not c.get("fps") and pv.get("fps"):
            c["fps"] = pv["fps"]
            c["fps_from"] = "preview"
            _fps(c, ctx)
        if not c.get("duration") and pv.get("duration"):
            c["duration"] = round(pv["duration"], 2)
            if c["duration"] < ctx["length"] + 1 - 1e-6:
                _reject(c, f"{c['duration']:.1f} s long; the shot needs {ctx['length'] + 1:.1f} s, its length plus one (§6.4)")
        take = a.get("longest_take") or 0.0
        need = ctx["length"] * (0.8 if round(float(c.get("fps") or 0)) == 60 else 1.0)   # 60 fps plays at 0.8× (§3.4)
        _check(c, "cuts", a.get("cuts") or [])
        _check(c, "longest_take", take)
        if take < need - 1e-6:
            _reject(c, f"no continuous take of {need:.1f} s between its cuts; the longest is {take:.1f} s (§6.4)")
    exempt = arch and bool(ctx.get("specific"))
    big = float(a.get("max_face") or 0.0)
    _check(c, "faces", {"max_area": big, "sampled": len(a.get("faces") or []),
                        "with_face_over_1pct": sum(1 for f in a.get("faces") or [] if f["max_area"] > FACE_MAX),
                        "exempt": "archival portrait of the film's named subject, credited (§13.1)" if exempt else None})
    if big > FACE_MAX and not exempt:
        _reject(c, f"a face covers {big * 100:.1f}% of the frame; over 1% is refused (§6.6)")
    words = a.get("ocr_words")
    if words is None:
        _check(c, "text", OCR_UNAVAILABLE)
    else:
        _check(c, "text", words)
        if words > OCR_WORDS and not arch:   # in a 1908 photograph, a sign is provenance, not a watermark
            _reject(c, f"{words} words of text in the frame; more than {OCR_WORDS} is refused (§6.4)")
    _check(c, "phash", a.get("phash"))
    for other, (h, where) in (hashes or {}).items():
        if other != c["id"] and h and a.get("phash"):
            d = phash_distance(a["phash"], h)
            if d < PHASH_DUP:
                _check(c, "duplicate", {"of": other, "distance": d, "where": where})
                _reject(c, f"a duplicate of {other} {where} (phash distance {d}) (§6.7)")
                break
    return finish(c)["passed_filters"]
