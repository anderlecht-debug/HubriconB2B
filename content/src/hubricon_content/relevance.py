"""Picture relevance, by a local image-text model on the GPU (FILM_PROCESS.md 2.7), for no tokens.

The filters judge a picture's quality and rights, not its subject. This scores the subject: the words
spoken under a shot and each candidate picture are embedded by SigLIP (ViT-B-16, webli) and compared
by cosine similarity.

- **Below THRESHOLD:** a candidate is not eligible for auto-pick.
- **The rest:** ranked by a blend of the source's rank and the relevance.
- **Still low:** a shot whose best candidate stays below LOW goes, with the other low ones, to one capped
  visual-pick reply.

Image embeddings are cached by file (content/.cache/relevance), so a film is scored once.

    hubricon-content relevance <slug>    → scores every candidate and picked picture; qa/relevance.json
"""
from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import numpy as np

from . import script as scriptmod
from .state import CONTENT_DIR

MODEL, PRETRAINED = "ViT-B-16-SigLIP", "webli"
CACHE = CONTENT_DIR / ".cache" / "relevance"
# calibrated on G02's contact sheets (docs/content/CHANGELOG-FILMS.md, item 2): a right picture sits near 0.10
# (s125's period grocery interior +0.100, s058's "5 & 10 store" poster +0.099), a modern or tangential one
# near 0.00–0.02, a wrong one below 0 (a winery −0.054, pancakes −0.125). Below THRESHOLD a candidate is not
# picked; a shot whose best is below LOW goes to the one capped visual-pick reply.
THRESHOLD, LOW = 0.0, 0.05
RANK_WEIGHT = 0.02          # a source's first result is worth this much relevance over its tenth
TEXT_WORDS = 40             # SigLIP reads 64 tokens; the shot's words are cut to about this many

_m = {}


def _load():
    if not _m:
        import open_clip
        import torch
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        model, _, pre = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED, device=dev)
        model.eval()
        _m.update(model=model, pre=pre, tok=open_clip.get_tokenizer(MODEL), dev=dev, torch=torch)
    return _m


def text_of(shot: dict) -> str:
    """What the picture should show: the shot's picture query, then the words spoken under it. Calibrated on
    G02: the spoken words alone barely separate a right picture from a wrong one (median 0.009, p10–p90
    −0.03 to 0.05), being often abstract ("A test, then a rollout."); with the query first, a wrong picture
    falls below 0 and a right one sits near 0.10. The query is the plan's reading of those same words."""
    q = " ".join(shot.get("query") or [])
    words = f"{q}. {shot.get('says') or ''}".strip(". ").split()
    return " ".join(words[:TEXT_WORDS])


def embed_texts(texts: list[str]) -> np.ndarray:
    m = _load()
    with m["torch"].no_grad():
        t = m["model"].encode_text(m["tok"](texts).to(m["dev"]))
        t = t / t.norm(dim=-1, keepdim=True)
    return t.float().cpu().numpy()


def _key(p: Path) -> str:
    st = p.stat()
    return hashlib.sha256(f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}|{MODEL}".encode()).hexdigest()[:24]


def embed_images(paths: list[Path], batch: int = 32) -> np.ndarray:
    from PIL import Image
    m = _load()
    CACHE.mkdir(parents=True, exist_ok=True)
    out = [None] * len(paths)
    todo = []
    for i, p in enumerate(paths):
        c = CACHE / f"{_key(p)}.npy"
        if c.exists():
            out[i] = np.load(c)
        else:
            todo.append(i)
    for b in range(0, len(todo), batch):
        idx = todo[b:b + batch]
        ims = []
        for i in idx:
            with Image.open(paths[i]) as im:
                ims.append(m["pre"](im.convert("RGB")))
        with m["torch"].no_grad():
            e = m["model"].encode_image(m["torch"].stack(ims).to(m["dev"]))
            e = (e / e.norm(dim=-1, keepdim=True)).float().cpu().numpy()
        for i, v in zip(idx, e):
            np.save(CACHE / f"{_key(paths[i])}.npy", v)
            out[i] = v
    return np.stack(out) if out else np.zeros((0, 768))


def scores(text: str, paths: list[Path]) -> list[float]:
    if not paths:
        return []
    return [float(x) for x in embed_images(paths) @ embed_texts([text])[0]]


def _picture(path: Path) -> Path | None:
    """An image file to embed: the file itself, or a frame of a video (cached beside it)."""
    import subprocess
    if path.suffix.lower() not in (".mp4", ".mov", ".webm", ".m4v"):
        return path if path.exists() else None
    frame = path.with_suffix(path.suffix + ".frame.jpg")
    if not frame.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(path), "-frames:v", "1", "-vf", "scale=512:-2", str(frame)],
                       timeout=120)
    return frame if frame.exists() else None


def candidate_file(c: dict) -> Path | None:
    from . import sources
    for p in (sources.preview_path(c), Path(c["file"]) if c.get("file") else None):
        if p and p.exists():
            return _picture(p)
    return None


def rank_assets(text: str, shots: list[dict]) -> list[dict]:
    """World shots ordered by how well their picked picture shows `text` (the thumbnail's stakes)."""
    pool = [(s, _picture(Path(asset_of(s)["file"]))) for s in shots if asset_of(s).get("file")]
    pool = [(s, p) for s, p in pool if p]
    sc = scores(text, [p for _, p in pool])
    return [s for _, s in sorted(zip(sc, [s for s, _ in pool]), key=lambda x: -x[0])]


def asset_of(shot: dict) -> dict:
    """A shot's picked picture (a stack holds three: its first)."""
    a = shot.get("asset") or {}
    return (a[0] if a else {}) if isinstance(a, list) else a


def blend(c: dict, position: int) -> float:
    """Auto-pick's order: relevance first, the source's own rank a little."""
    return float(c.get("relevance", -1.0)) + RANK_WEIGHT / (1 + position)


def score_film(slug: str) -> dict:
    """Score every candidate of every picture shot (into its sources/<id>.json) and every picked picture
    (into shots.json), and write qa/relevance.json: the median, the low shots."""
    d = scriptmod.video_dir(slug)
    plan_p = d / "shots.json"
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    picked, low = [], []
    for s in plan["shots"]:
        rec_p = d / "sources" / f"{s['id']}.json"
        text = text_of(s)
        if rec_p.exists():
            rec = json.loads(rec_p.read_text(encoding="utf-8"))
            cands = [c for c in rec.get("candidates", []) if c.get("passed_filters")]
            files = [(c, candidate_file(c)) for c in cands]
            files = [(c, f) for c, f in files if f]
            for (c, _), v in zip(files, scores(text, [f for _, f in files])):
                c["relevance"] = round(v, 4)
            rec_p.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        a = asset_of(s)
        if s.get("room") == "world" and a.get("file"):
            f = _picture(Path(a["file"]))
            if f:
                s["relevance"] = round(scores(text, [f])[0], 4)
                picked.append(s["relevance"])
                if s["relevance"] < LOW:
                    low.append(s["id"])
    plan_p.write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    out = {"model": f"{MODEL}/{PRETRAINED}", "threshold": THRESHOLD, "low": LOW, "picked": len(picked),
           "median": round(statistics.median(picked), 4) if picked else None, "low_shots": low}
    (d / "qa").mkdir(exist_ok=True)
    (d / "qa" / "relevance.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out
