"""The v3 film look's surfaces, made by code (no AI, no stock): aged paper, the dark desk, film
dust. Deterministic (fixed seeds), so every film draws the same surfaces.
    python content/film/v3/textures.py  →  content/assets/film/*.jpg|png"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

OUT = Path(__file__).resolve().parents[2] / "assets" / "film"


def noise(w, h, rng, octaves=((8, 1.0), (32, 0.5), (128, 0.25), (512, 0.12))):
    """Multi-octave value noise in 0..1: random grids upscaled smoothly and summed."""
    acc = np.zeros((h, w), np.float32)
    total = 0.0
    for cells, amp in octaves:
        gw, gh = max(2, cells), max(2, int(cells * h / w))
        g = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        acc += np.asarray(g, np.float32) / 255 * amp
        total += amp
    acc /= total
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-9)


def paper(w=2400, h=1600, seed=7):
    rng = np.random.default_rng(seed)
    base = np.array([234, 226, 207], np.float32)          # aged ivory
    blot = noise(w, h, rng)                                  # uneven ageing
    fine = noise(w, h, rng, ((600, 1.0), (1200, 0.6)))       # tooth
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]) / (0.18 * min(w, h))
    edge = np.clip(edge, 0, 1) ** 0.6                         # darker toward the edges (foxing)
    shade = 0.86 + 0.10 * blot + 0.05 * fine
    shade *= 0.90 + 0.10 * edge
    img = base[None, None, :] * shade[..., None]
    img[..., 2] *= 0.97 + 0.03 * blot                         # a touch warmer where it has aged
    # fibres: faint short strokes
    fib = Image.new("L", (w, h), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(fib)
    for _ in range(1400):
        x, y = rng.random() * w, rng.random() * h
        a, L = rng.random() * np.pi, 6 + rng.random() * 26
        d.line([(x, y), (x + L * np.cos(a), y + L * np.sin(a))], fill=int(18 + rng.random() * 30), width=1)
    fib = np.asarray(fib.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    img *= (1 - 0.35 * fib)[..., None]
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT / "paper.jpg", quality=92)


def desk(w=2560, h=1440, seed=11):
    rng = np.random.default_rng(seed)
    base = np.array([21, 19, 17], np.float32)                # warm black, lifted so the desk reads (critique 2026-10-06)
    n = noise(w, h, rng, ((6, 1.0), (40, 0.4), (300, 0.2), (1200, 0.15)))
    img = base[None, None, :] * (0.85 + 0.35 * n)[..., None]
    img += (rng.normal(0, 1.4, (h, w)))[..., None]           # fine grain baked in
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT / "desk.jpg", quality=94)


def dust(w=1920, h=1080, seed=23):
    """Film dust and hairline scratches on transparency, for archival prints (used at low alpha)."""
    rng = np.random.default_rng(seed)
    from PIL import ImageDraw
    a = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(a)
    for _ in range(260):
        x, y, r = rng.random() * w, rng.random() * h, 0.6 + rng.random() * 2.2
        d.ellipse([x - r, y - r, x + r, y + r], fill=int(90 + rng.random() * 140))
    for _ in range(14):
        x, y = rng.random() * w, rng.random() * h
        d.line([(x, y), (x + rng.normal(0, 6), y + 40 + rng.random() * 220)], fill=int(60 + rng.random() * 80), width=1)
    a = a.filter(ImageFilter.GaussianBlur(0.7))
    rgba = Image.merge("RGBA", (Image.new("L", (w, h), 245), Image.new("L", (w, h), 240), Image.new("L", (w, h), 230), a))
    rgba.save(OUT / "dust.png", optimize=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    paper(); desk(); dust()
    print("textures:", ", ".join(sorted(p.name for p in OUT.iterdir())))
