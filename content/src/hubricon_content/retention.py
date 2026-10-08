"""Viewers as the critic (docs/content/LEARNING_DESIGN.md): a published film's audience-retention curve
from YouTube Analytics, mapped onto its beats and shots, so a drop names the sentence and the picture it
happened on, and across films, the styles that hold viewers and the ones that lose them.

    hubricon-content retention <slug>       → videos/<slug>/qa/retention.json and retention.md
    hubricon-content retention-patterns     → content/.cache/retention-patterns.json

Needs the YouTube token with the read-only analytics scope (`youtube-auth` asks for it) and a published
film (published.json). Costs no tokens: this replaces critic rounds with what viewers actually did.
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
PATTERNS = CONTENT_DIR / ".cache" / "retention-patterns.json"
OPEN_S = 30.0          # the open's loss is reported on its own: every video loses most there


def _analytics():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from .upload import SCOPES, TOKEN
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtubeAnalytics", "v2", credentials=creds)


def fetch(slug: str, service=None) -> list[dict]:
    """The curve: 100 points, each the share of the film's length watched (`ratio`), the share of views
    still watching there (`watch`, above 1 where people rewatch) and how that compares with videos of the
    same length (`relative`, 0.5 is typical)."""
    d = scriptmod.video_dir(slug)
    pub = json.loads((d / "published.json").read_text(encoding="utf-8"))
    svc = service or _analytics()
    res = svc.reports().query(ids="channel==MINE", startDate=str(pub.get("published_at", "2026-01-01"))[:10],
                              endDate=date.today().isoformat(), dimensions="elapsedVideoTimeRatio",
                              metrics="audienceWatchRatio,relativeRetentionPerformance",
                              filters=f"video=={pub['youtube_id']}").execute()
    return [{"ratio": float(r[0]), "watch": float(r[1]), "relative": float(r[2])} for r in res.get("rows") or []]


def _at(plan: dict, t: float) -> dict:
    return next((s for s in plan["shots"] if float(s["start"]) <= t < float(s["end"])), plan["shots"][-1])


def analyse(points: list[dict], plan: dict, timing: dict) -> dict:
    """The open's loss, then the steepest drops and the rewatched moments beyond it, each with its shot,
    beat and words."""
    from . import shots
    dur = float(timing["duration"])
    words = shots.spoken(timing)
    beats = [s for s in timing["segments"] if s.get("kind") == "beat"]
    pts = sorted(points, key=lambda p: p["ratio"])
    at = lambda p: p["ratio"] * dur
    first = next((p for p in pts if at(p) >= OPEN_S), pts[-1])

    def place(t0, t1):
        s = _at(plan, t0)
        b = next((x for x in beats if float(x["start"]) <= t0 < float(x["end"])), None)
        said = " ".join(w["word"] for w in shots.words_in(words, t0, t1))[:160]
        return {"t": round(t0, 1), "shot": s["id"], "kind": s.get("kind"), "style": s.get("style"),
                "beat": (b or {}).get("name"), "said": said}

    steps = [(a, b, a["watch"] - b["watch"]) for a, b in zip(pts, pts[1:]) if at(a) >= OPEN_S]
    if not steps:
        return {"open_kept": round(first["watch"], 3), "drops": [], "rewatched": []}
    loss = [x for _, _, x in steps]
    med = statistics.median(loss)
    mad = statistics.median(abs(x - med) for x in loss) or 0.002
    drops = sorted((s for s in steps if s[2] > med + 2.5 * mad), key=lambda s: -s[2])[:8]
    rewatch = sorted((s for s in steps if s[2] < -max(0.01, mad)), key=lambda s: s[2])[:5]
    return {"open_kept": round(first["watch"], 3), "typical_loss_per_point": round(med, 4),
            "drops": [{**place(at(a), at(b)), "lost": round(x, 4)} for a, b, x in drops],
            "rewatched": [{**place(at(a), at(b)), "gained": round(-x, 4)} for a, b, x in rewatch],
            "relative_mean": round(statistics.mean(p["relative"] for p in pts), 3)}


def run(slug: str, service=None) -> dict:
    from . import shots
    d = scriptmod.video_dir(slug)
    points = fetch(slug, service)
    if not points:
        return {"status": "waiting", "reason": "no retention data yet (YouTube reports it once a video has views)"}
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    timing, _ = shots.load_timing(d)
    res = analyse(points, plan, timing)
    (d / "qa").mkdir(exist_ok=True)
    (d / "qa" / "retention.json").write_text(json.dumps({"points": points, **res}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    mmss = lambda t: f"{int(t // 60)}:{int(t % 60):02d}"
    md = [f"# Retention: {slug}", "", f"- Still watching at {int(OPEN_S)} s: {res['open_kept']:.0%}",
          f"- Against videos of its length: {res.get('relative_mean', 0):.2f} (0.5 is typical)", "", "## Where viewers left", ""]
    md += [f"- {mmss(x['t'])} · {x['lost']:.1%} left · {x['shot']} {x['style']} · {x['beat']}: \"{x['said']}\"" for x in res["drops"]] or ["- no drop beyond the film's usual pace"]
    md += ["", "## What viewers watched again", ""]
    md += [f"- {mmss(x['t'])} · +{x['gained']:.1%} · {x['shot']} {x['style']} · {x['beat']}: \"{x['said']}\"" for x in res["rewatched"]] or ["- nothing"]
    (d / "qa" / "retention.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"status": "ok", **res}


def patterns(videos: Path | None = None) -> dict:
    """Across every film with a curve: each style's loss per minute on screen against the films' own, so
    a rule can be written from what viewers did (a style that loses twice the film's pace, a card that holds)."""
    from . import shots
    videos = videos or CONTENT_DIR / "videos"
    by, films = {}, 0
    for r in sorted(videos.glob("*/qa/retention.json")):
        d = r.parent.parent
        data = json.loads(r.read_text(encoding="utf-8"))
        plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
        timing, _ = shots.load_timing(d)
        dur = float(timing["duration"])
        pts = sorted(data["points"], key=lambda p: p["ratio"])
        steps = [(a["ratio"] * dur, b["ratio"] * dur, a["watch"] - b["watch"]) for a, b in zip(pts, pts[1:]) if a["ratio"] * dur >= OPEN_S]
        if not steps:
            continue
        films += 1
        pace = sum(x for _, _, x in steps) / sum(t1 - t0 for t0, t1, _ in steps) * 60
        for t0, t1, x in steps:
            for s in plan["shots"]:
                o = min(t1, float(s["end"])) - max(t0, float(s["start"]))
                if o > 0:
                    e = by.setdefault(s.get("style"), {"seconds": 0.0, "lost": 0.0, "film_pace": []})
                    e["seconds"] += o
                    e["lost"] += x * o / (t1 - t0)
                    e["film_pace"].append(pace)
    out = {"films": films, "styles": {}}
    for style, e in by.items():
        if e["seconds"] >= 60:
            per_min = e["lost"] / e["seconds"] * 60
            out["styles"][style] = {"minutes": round(e["seconds"] / 60, 1), "loss_per_min": round(per_min, 4),
                                    "against_film": round(per_min / (statistics.mean(e["film_pace"]) or 1e-9), 2)}
    out["styles"] = dict(sorted(out["styles"].items(), key=lambda kv: -kv[1]["against_film"]))
    PATTERNS.parent.mkdir(parents=True, exist_ok=True)
    PATTERNS.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out
