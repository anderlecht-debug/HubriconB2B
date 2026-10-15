"""The pick (VISUAL_SPEC.md §7.2, §7.5): the `visual-pick` skill chooses, this
writes it down. `hubricon-content pick <slug> <shot> <number>` takes the
candidate numbered on the shot's contact sheet (sources/<shot>.jpg), fetches its
full-resolution file, and writes its whole provenance into shots.json as the
shot's asset, with the focus, the move and the in point the skill set; the
one-line reason goes to assets.json. Only a candidate that passed the filters
can be picked. `--none` takes the shot's fallback; `--texture` records an AI
texture made through the Higgsfield connector.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import script as scriptmod
from . import shots, sources
from .sources import net as netmod

PROVENANCE = ("id", "source", "url", "author", "author_url", "licence", "rights", "title", "description", "credit",
              "place", "date", "subject", "retrieved", "width", "height", "fps", "duration")


def _plan(d: Path) -> dict:
    return json.loads((d / "shots.json").read_text(encoding="utf-8"))


def _save(d: Path, plan: dict, shot_id: str, reason: str, asset_ids: list[str]) -> None:
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    p = d / "assets.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    doc[shot_id] = {"assets": asset_ids, "reason": reason, "on": date.today().isoformat()}
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _candidate(record: dict, number: int, side: str | None = None) -> dict:
    for c in record.get("candidates", []):
        if c.get("sheet_index") == number and (side is None or c.get("side") == side):
            if not c.get("passed_filters"):
                raise SystemExit(f"candidate {number} did not pass the filters: {'; '.join(c.get('rejected_because') or [])}")
            return c
    raise SystemExit(f"no candidate {number}{f' on the {side} side' if side else ''} on this shot's contact sheet")


def asset_of(c: dict, net=None) -> dict:
    """The candidate as a picked asset: its full file, sha256 and every provenance field."""
    sources.fetch_full(c, net=net)
    out = {k: c.get(k) for k in PROVENANCE if c.get(k) not in (None, "")}
    out.update({"file": c["file"], "sha256": c["sha256"], "passed_filters": True})
    if (c.get("checks") or {}).get("phash"):
        out["phash"] = c["checks"]["phash"]
    return out


def pick(slug: str, shot_id: str, numbers: list[int] | None = None, *, focus=None, motion=None, start=None,
         reason: str = "", then: int | None = None, now: int | None = None, net=None) -> dict:
    d = scriptmod.video_dir(slug)
    plan = _plan(d)
    shot = next((s for s in plan["shots"] if s["id"] == shot_id), None)
    if shot is None:
        raise SystemExit(f"no shot {shot_id}")
    rec_p = d / "sources" / f"{shot_id}.json"
    if not rec_p.exists():
        raise SystemExit(f"{shot_id} has no candidates: run `hubricon-content source {slug} --shot {shot_id}`")
    record = json.loads(rec_p.read_text(encoding="utf-8"))
    net = net or netmod.default()
    if shot.get("kind") == "split":
        if then is None or now is None:
            raise SystemExit("a then-and-now shot picks two: --then N --now M")
        left = asset_of(_candidate(record, then, "then"), net)
        right = asset_of(_candidate(record, now, "now"), net)
        if start is not None:
            right["in"] = float(start)
        shot["asset"] = left
        shot.setdefault("params", {})["right"] = right
        ids = [left["id"], right["id"]]
    elif shot.get("kind") == "stack":
        chosen = [asset_of(_candidate(record, n), net) for n in numbers or []]
        if not 3 <= len(chosen) <= 5:
            raise SystemExit("a photo stack shows three to five photographs (§14, W6)")
        shot["asset"] = chosen
        ids = [a["id"] for a in chosen]
    else:
        if not numbers or len(numbers) != 1:
            raise SystemExit("pick one candidate number")
        a = asset_of(_candidate(record, numbers[0]), net)
        if shot.get("kind") == "footage":
            length = float(shot["end"]) - float(shot["start"])
            a["in"] = float(start if start is not None else 0.0)
            a["out"] = round(a["in"] + length + 0.5, 3)
        shot["asset"] = a
        ids = [a["id"]]
    if focus is not None:
        shot["focus"] = [float(focus[0]), float(focus[1])]
    if motion:
        shot["motion"] = motion
    _save(d, plan, shot_id, reason, ids)
    return {"status": "ok", "shot": shot_id, "picked": ids}


def none(slug: str, shot_id: str, reason: str) -> dict:
    """No candidate shows the words: the shot takes its fallback (§7.5)."""
    d = scriptmod.video_dir(slug)
    plan = _plan(d)
    shot = next(s for s in plan["shots"] if s["id"] == shot_id)
    fb = str(shot.get("fallback") or "paper:kinetic").split("→")[-1].strip()
    if fb in ("texture", "ai"):
        shot.update(room="world", kind="texture", style="texture", sources=["higgsfield"], asset=None,
                    overlay={**(shot.get("overlay") or {}), "illustration": True})
    else:   # paper:kinetic, the floor of every chain: the words themselves, set on paper
        shot.update(room="paper", kind="kinetic", style="kinetic-thesis", asset=None, query=[], sources=[], on=None)
    shot.pop("motion", None)
    _save(d, plan, shot_id, f"fallback {fb}: {reason}", [])
    return {"status": "ok", "shot": shot_id, "fallback": fb}


def texture(slug: str, shot_id: str, file: str, job: str, model: str, prompt: str, seed, reason: str,
            focus=None, motion: str = "drift") -> dict:
    """An AI texture made through the Higgsfield connector, recorded with its job, model,
    prompt and seed (§6.5); it says "Illustration" on screen."""
    d = scriptmod.video_dir(slug)
    plan = _plan(d)
    shot = next(s for s in plan["shots"] if s["id"] == shot_id)
    if shot.get("kind") != "texture":
        raise SystemExit(f"{shot_id} is a {shot.get('kind')}, not a texture")
    p = Path(file)
    asset = {"id": f"higgsfield:{job}", "source": "higgsfield", "file": str(p.resolve()), "sha256": netmod.sha256_file(p),
             "licence": "Higgsfield (generated for Hubricon)", "author": "Higgsfield, AI image", "url": f"higgsfield:{job}",
             "retrieved": date.today().isoformat(), "job": job, "model": model, "prompt": prompt, "seed": seed,
             "passed_filters": True}
    shot["asset"] = asset
    shot["overlay"] = {**(shot.get("overlay") or {}), "illustration": True}
    shot["focus"] = [float(focus[0]), float(focus[1])] if focus else shot.get("focus") or [0.5, 0.5]
    shot["motion"] = motion
    _save(d, plan, shot_id, reason, [asset["id"]])
    return {"status": "ok", "shot": shot_id, "picked": [asset["id"]]}


def done(slug: str) -> list[str]:
    """What the pick still owes: shots.validate --picked, as the step's pass condition."""
    d = scriptmod.video_dir(slug)
    timing, _ = shots.load_timing(d)
    usage = json.loads(shots.USAGE.read_text(encoding="utf-8")) if shots.USAGE.exists() else {}
    return shots.validate(_plan(d), timing, scriptmod.load_facts(slug), picked=True, usage=usage)
