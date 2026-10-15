"""Helpers for the sourcing tests: no network, ever. Recorded library answers
(tests/fixtures/sources/, keys never in them), a fake HTTP session that serves
them, a fake clock for the rate limiter, and synthetic media made on the spot
with ffmpeg's lavfi sources and Pillow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from hubricon_content.sources import net as netmod

FIXTURES = Path(__file__).parent / "fixtures" / "sources"
KEYS = {"PEXELS_API_KEY": "pexels-test-key-0000000000", "PIXABAY_API_KEY": "pixabay-test-key-0000000",
        "SMITHSONIAN_API_KEY": "smithsonian-test-key-00000", "CONTENT_CONTACT_EMAIL": "films@example.org"}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class Response:
    def __init__(self, status=200, body=None, text=None, content=b"", headers=None):
        self.status_code = status
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")
        self.content = content or self.text.encode()
        self.headers = headers or {}

    def iter_content(self, n):
        for i in range(0, len(self.content), n):
            yield self.content[i:i + n]


class HTTP:
    """Serves a route's answer for any URL containing its key; records every call."""

    def __init__(self, routes: dict):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, headers=None, timeout=None, stream=False):
        self.calls.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {})})
        for key, answer in self.routes.items():
            if key in url:
                answer = answer(url, params, headers) if callable(answer) else answer
                return answer if isinstance(answer, Response) else Response(body=answer)
        return Response(status=404, text="not found")


class Clock:
    def __init__(self, t: float = 1_790_000_000.0):
        self.t = t
        self.slept = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


def make_net(tmp: Path, routes: dict | None = None, film: Path | None = None, **kw) -> netmod.Net:
    clock = kw.pop("clock", None) or Clock()
    return netmod.Net(film_dir=film, clock=clock, sleep=clock.sleep, http=HTTP(routes or {}),
                      cache_dir=tmp / "api", asset_dir=tmp / "assets", **kw)


def set_keys(monkeypatch) -> None:
    for k, v in KEYS.items():
        monkeypatch.setenv(k, v)


# ── synthetic media ──
def clip(path: Path, source: str = "testsrc2", size="640x360", rate=30, seconds=8.0, then: str | None = None) -> Path:
    """A clip from a lavfi source; with `then`, a hard cut halfway to a second source."""
    path = Path(path)
    join = ":" if "=" in source else "="
    a = f"{source}{join}s={size}:r={rate}:d={seconds if then is None else seconds / 2}"
    if then is None:
        cmd = ["-f", "lavfi", "-i", a]
    else:
        b = f"{then}=s={size}:r={rate}:d={seconds / 2}"
        cmd = ["-f", "lavfi", "-i", a, "-f", "lavfi", "-i", b, "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
                    str(path)], check=True, timeout=120)
    return path


def still(path: Path, size=(1200, 800), grey: int | None = None, pattern: int = 0) -> Path:
    """A still: a flat grey, or a pattern for the perceptual hash (0: a diagonal, 1: a disc)."""
    from PIL import Image, ImageDraw
    w, h = size
    im = Image.new("RGB", size, (grey, grey, grey) if grey is not None else (200, 200, 200))
    if grey is None:
        d = ImageDraw.Draw(im)
        if pattern == 0:
            d.polygon([(0, h), (w, 0), (w, h)], fill=(50, 50, 50))
        else:
            d.ellipse([w * 0.3, h * 0.2, w * 0.7, h * 0.8], fill=(40, 40, 40))
    im.save(path, quality=92)
    return Path(path)
