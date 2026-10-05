"""The `source` step of a long film (VISUAL_SPEC.md §6, §7.2): candidates for
every world shot and every archival paper shot, checked by §6.4's filters and
laid out on a contact sheet, so the visual pick only ever chooses among
footage and photographs the film may honestly and legally use.

For each shot the plan names its libraries (`sources`), its literal queries
(`query`) and its fallback. The step asks only those libraries, never a
substitute (§6.3); runs the first query, and the second only when fewer than
six candidates have passed; checks the best-ranked candidates on their small
preview until nine pass; and writes, under content/videos/<slug>/sources/:

- `<shot>.json`: every candidate with its provenance, `checks`,
  `passed_filters` and, when refused, `rejected_because`; the unchecked rest as
  `reserve`, for a re-query;
- `<shot>.jpg`: the contact sheet (sheet.py);
- `textures.json`: four prompts per texture shot, each opening with the locked
  preamble of §6.5, for the runner's Claude to make through the Higgsfield
  connector (the AI image is not fetched here);
- `requests.json`: the API requests this film has spent, per library.

Each shot in shots.json gets `source_status`: `ok` (three or more candidates
passed), `fallback` (with `source_reason`), or `awaiting_textures`. Everything
is cached (API answers 24 hours, previews and their analysis by file), so a
second run costs no requests and an interrupted one resumes.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from datetime import date
from pathlib import Path

from . import script as scriptmod
from . import shots as shotmod
from . import sources
from .sources import filters
from .sources import net as netmod
from .sources import sheet, usage
from .state import CONTENT_DIR

SOURCED = {"footage", "still", "archive", "stack", "split", "texture"}
WANTS = {"footage": ("video",), "still": ("image",), "stack": ("image",), "archive": ("image", "video"),
         "split": ("image", "video")}
NEED, ENOUGH, SHEET, PROBE_CAP, RESOLVE_CAP = 3, 6, 9, 10, 20
PER_PAGE = 40
PREAMBLE = ("Photographic still life, overcast north light, cool neutral palette, matte surfaces, high-key exposure, "
            "shallow depth of field, fine film grain, 35 mm, no people, no hands, no text, no logos, no screens.")
VARIANTS = ("", ", seen close, one object in sharp focus", ", a wider arrangement with open space around it",
            ", seen from directly above")
# The first words of a refusal, folded to a short cause for a fallback's reason.
CAUSES = [("a face covers", "faces"), ("mean luma", "luma"), ("continuous take", "cuts"), ("the shot needs", "too short"),
          ("px on its", "resolution"), ("footage is at least", "resolution"), ("film is at least", "resolution"),
          ("needs a source at least", "resolution"), ("enlarged", "resolution"), ("size is not in the record", "resolution"),
          ("fps", "frame rate"), ("a duplicate of", "duplicates"), ("licence not on", "licence"), ("names Amazon", "Amazon in the record"),
          ("generated or animated", "generated"), ("half of the query's nouns", "too few of the query's nouns"),
          ("name none of the query's nouns", "the record is about something else"), ("banned cliché", "cliché"),
          ("does not name", "does not name the subject"), ("only archival evidence", "stock for a named subject"),
          ("already used", "used before"), ("provenance lacks", "provenance"), ("needs a date", "undated"),
          ("preview could not", "preview failed"), ("record could not", "record unreadable"), ("words of text", "text")]
MAX_PROBES = 30                     # previews read per side of a shot before it falls back


def _rel(p) -> str:
    p = Path(p)
    try:
        return str(p.relative_to(CONTENT_DIR))
    except ValueError:
        return str(p)


def _cause(c: dict) -> str:
    why = (c.get("rejected_because") or [""])[0]
    return next((label for key, label in CAUSES if key in why), "other")


def texture_prompts(shot: dict) -> list[str]:
    """Four prompts for a texture shot, each opening with §6.5's locked preamble verbatim."""
    qs = [re.sub(r"\s+", " ", re.sub(r"\bstill life\b", "", q, flags=re.I)).strip(" ,.") for q in shot.get("query") or []]
    qs = [q for q in qs if q] or [shot.get("intent") or "an abstract arrangement of plain objects"]
    subjects = [qs[0], qs[0], qs[0], qs[1] if len(qs) > 1 else qs[0]]
    return [f"{PREAMBLE} {s[0].upper()}{s[1:]}{v}." for s, v in zip(subjects, VARIANTS)]


def _sides(shot: dict, reg: dict) -> list[tuple[str | None, list[str], tuple[str, ...]]]:
    """Which libraries answer for which kind of asset. A then-and-now split takes its
    "then" from the archives and its "now" from stock footage (§14, W11)."""
    allowed = [s for s in shot.get("sources") or [] if s in sources.MODULES]
    if shot["kind"] == "split":
        return [("then", [s for s in allowed if s in reg["sources"]["archival"]], ("image",)),
                ("now", [s for s in allowed if s in reg["sources"]["stock"]], ("video",))]
    return [(None, allowed, WANTS[shot["kind"]])]


BIG_PREVIEW = 12e6


def _order(cands: list[dict], seen: set, libs: list[str]) -> list[dict]:
    """Each library's own order, nudged by how many of the query's nouns the record names,
    then interleaved library by library. A candidate already shown on an earlier sheet, one
    whose record names none of the nouns, and a preview over 12 MB go after the rest."""
    place = {}
    for src in {c["source"] for c in cands}:
        mine = sorted((c for c in cands if c["source"] == src),
                      key=lambda c: (-(c.get("checks") or {}).get("relevance", 0), c.get("rank", 99)))
        place.update({c["id"]: i for i, c in enumerate(mine)})
    return sorted(cands, key=lambda c: (c["id"] in seen, not (c.get("checks") or {}).get("relevance", 0),
                                        float(c.get("preview_bytes") or 0) > BIG_PREVIEW, place[c["id"]],
                                        libs.index(c["source"]) if c["source"] in libs else 99))


def _examine(pool: dict, ctx: dict, net, prior: dict, hashes: dict, seen: set, order: list[str]) -> int:
    """Check the pool's unexamined candidates, best first, until nine pass or ten previews
    have been read. Returns the previews read."""
    for c in pool.values():
        if "passed_filters" not in c and "checks" not in c and not filters.precheck(c, ctx, prior):
            filters.finish(c)
    todo = _order([c for c in pool.values() if "passed_filters" not in c], seen, order)
    probes = resolves = 0
    for c in todo:
        if sum(1 for x in pool.values() if x.get("passed_filters")) >= SHEET or probes >= PROBE_CAP:
            break
        if not c.get("resolved"):
            if resolves >= RESOLVE_CAP:
                continue
            resolves += 1
            try:
                sources.resolve(c, net)
            except sources.SourceError as e:
                filters._reject(c, f"its record could not be read ({e})")
                filters.finish(c)
                continue
            if not filters.precheck(c, ctx, prior):       # the item record may change the licence
                filters.finish(c)
                continue
        if not filters.metadata(c, ctx):
            filters.finish(c)
            continue
        try:
            path = sources.fetch_preview(c, net)
            a = filters.analyse(path, c["kind"], c["preview_sha256"])
        except sources.SourceError as e:
            filters._reject(c, f"the preview could not be downloaded ({e})")
            filters.finish(c)
            continue
        except Exception as e:                           # a file ffmpeg or Pillow cannot read
            filters._reject(c, f"the preview could not be decoded ({type(e).__name__})")
            filters.finish(c)
            continue
        probes += 1
        c["probed"], c["strip"], c["preview_file"] = True, a.get("strip"), _rel(path)
        local = {x["id"]: (x["checks"].get("phash"), "already a candidate for this shot")
                 for x in pool.values() if x.get("passed_filters") and (x.get("checks") or {}).get("phash")}
        filters.media(c, a, ctx, {**hashes, **local})
    return probes


def _source_side(shot, side, libs, kinds, ctx, net, prior, hashes, seen, log) -> tuple[list[dict], list[dict], str | None]:
    """One pool of candidates for one side of a shot: (examined, reserve, why it fell short)."""
    pool: dict[str, dict] = {}
    queries = [q for q in shot.get("query") or [] if str(q).strip()]
    note, probes = None, 0
    if not libs:
        return [], [], "the plan names no library this step reads for it"
    if not queries:
        return [], [], "the plan gives no query"
    for n, query in enumerate(queries):
        for src in libs:
            for kind in kinds:
                if kind not in sources.adapter(src).KINDS:
                    continue
                before = net.session.get(src, {}).get("requests", 0)
                try:
                    found = sources.search(src, query, kind, PER_PAGE, net=net)
                except sources.BudgetSpent as e:
                    note = str(e)
                    log.append({"source": src, "query": query, "kind": kind, "error": str(e)})
                    continue
                except sources.SourceError as e:
                    log.append({"source": src, "query": query, "kind": kind, "error": str(e)})
                    continue
                log.append({"source": src, "query": query, "kind": kind, "results": len(found),
                            "sent": net.session.get(src, {}).get("requests", 0) > before, "side": side})
                broad = sources.nouns(query)
                if not found and src in ctx["archival"] and broad != sources.plain(query):
                    try:                   # an archive reads every word as required: once more, by the nouns
                        found = sources.search(src, broad, kind, PER_PAGE, net=net)
                    except sources.SourceError as e:
                        found = []
                        log.append({"source": src, "query": broad, "kind": kind, "error": str(e)})
                    log.append({"source": src, "query": broad, "broadened_from": query, "kind": kind,
                                "results": len(found), "side": side})
                for c in found:
                    if c["id"] not in pool:
                        c["query"], c["side"] = query, side
                        pool[c["id"]] = c
        probes += _examine(pool, ctx, net, prior, hashes, seen, libs)
        filters.fps_rule(list(pool.values()), ctx, NEED)
        if sum(1 for c in pool.values() if c.get("passed_filters")) >= ENOUGH:
            break
    while sum(1 for c in pool.values() if c.get("passed_filters")) < NEED and probes < MAX_PROBES:
        more = _examine(pool, ctx, net, prior, hashes, seen, libs)    # the pool is cached: no request
        if not more:
            break
        probes += more
        filters.fps_rule(list(pool.values()), ctx, NEED)
    examined = [c for c in pool.values() if "passed_filters" in c]
    reserve = [c for c in pool.values() if "passed_filters" not in c]
    passed = sum(1 for c in examined if c["passed_filters"])
    if passed >= NEED:
        return examined, reserve, None
    causes = Counter(_cause(c) for c in examined if not c["passed_filters"])
    why = (f"{passed} of the {NEED} needed passed after {len(queries[:n + 1])} "
           f"quer{'y' if n == 0 else 'ies'} on {', '.join(libs)}; {len(pool)} found, {len(examined)} checked")
    if causes:
        why += ": refused for " + ", ".join(f"{k} ({v})" for k, v in causes.most_common(4))
    if note:
        why += f"; {note}"
    return examined, reserve, why


def _slim(c: dict) -> dict:
    """A candidate as written to <shot>.json: no in-memory paths outside content/."""
    out = {k: v for k, v in c.items() if k != "strip"}
    if c.get("strip"):
        out["strip"] = _rel(c["strip"])
    return out


def source_shot(shot: dict, net, reg: dict, prior: dict, hashes: dict, seen: set, out: Path) -> dict:
    ctx = filters.context(shot, reg)
    log: list[dict] = []
    record = {"shot": shot["id"], "kind": shot["kind"], "style": shot.get("style"), "room": shot.get("room"),
              "start": shot["start"], "end": shot["end"], "length": ctx["length"], "says": shot.get("says"),
              "intent": shot.get("intent"), "query": shot.get("query"), "sources": shot.get("sources"),
              "fallback": shot.get("fallback"), "specific": shot.get("specific"), "sourced": date.today().isoformat(),
              "filters": {"luma_band": [round(x, 1) for x in filters.LUMA_BAND], "face_max": filters.FACE_MAX,
                          "ocr": "tesseract" if shutil.which("tesseract") else filters.OCR_UNAVAILABLE}}
    unknown = [s for s in shot.get("sources") or [] if s not in sources.MODULES]
    if unknown:
        record["unread_sources"] = unknown
    sections, candidates, reserve, short = [], [], [], []
    for side, libs, kinds in _sides(shot, reg):
        examined, spare, why = _source_side(shot, side, libs, kinds, ctx, net, prior, hashes, seen, log)
        order = sorted(examined, key=lambda c: (not c["passed_filters"], not c.get("probed")))
        on_sheet = [c for c in order if c.get("probed")][:SHEET]
        shown = {c["id"] for c in on_sheet}
        for c in order:                    # sheet_index is the candidate's place in <shot>.json
            if c["id"] in shown:
                c["sheet_index"] = len(candidates)
            else:
                c.pop("sheet_index", None)
            candidates.append(c)
        seen |= shown
        title = {"then": "Then: archival, with a dated record", "now": "Now: present-day footage"}.get(side)
        sections.append((title, on_sheet))
        reserve += spare
        if why:
            short.append(f"{side}: {why}" if side else why)
    passed = sum(1 for c in candidates if c["passed_filters"])
    record.update({"status": "fallback" if short else "ok", "reason": "; ".join(short) or None,
                   "passed": passed, "checked": len(candidates), "searches": log,
                   "sheet": f"{shot['id']}.jpg", "candidates": [_slim(c) for c in candidates],
                   "reserve": [_slim(c) for c in reserve]})
    header = [f"{shot['id']} · {shot.get('style')} · {ctx['length']:.1f} s · {record['status']}"
              + (f" → {shot.get('fallback')}" if short else f" · {passed} passed"),
              f"“{shot.get('says') or ''}”", f"query: {' | '.join(shot.get('query') or [])}"]
    sheet.write(out / f"{shot['id']}.jpg", header, sections)
    (out / f"{shot['id']}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def _picked(plan: dict, skip: str | None = None) -> tuple[dict, dict]:
    """The film's picks so far: id → where (for exact reuse) and id → (phash, where)."""
    ids, hashes = {}, {}
    for s in plan.get("shots", []):
        if s.get("id") == skip:
            continue
        assets = s.get("asset") if isinstance(s.get("asset"), list) else [s.get("asset")]
        for a in assets:
            if isinstance(a, dict) and a.get("id"):
                ids[a["id"]] = f"in this film, for {s['id']}"
                h = a.get("phash") or (a.get("checks") or {}).get("phash")
                if h:
                    hashes[a["id"]] = (h, f"picked for {s['id']}")
    return ids, hashes


def _write_textures(out: Path, shot: dict) -> dict:
    p = out / "textures.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    doc.update({"preamble": PREAMBLE, "note": "Four prompts per texture shot (VISUAL_SPEC.md §6.5), for the runner's "
                "Claude to make through the Higgsfield connector; record job, model, prompt, seed and date per image."})
    entry = doc.setdefault("shots", {}).setdefault(shot["id"], {})
    entry.update({"says": shot.get("says"), "intent": shot.get("intent"), "query": shot.get("query"),
                  "prompts": texture_prompts(shot)})
    entry.setdefault("status", "awaiting")
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rec = {"shot": shot["id"], "kind": "texture", "status": "awaiting_textures", "prompts": entry["prompts"],
           "says": shot.get("says"), "intent": shot.get("intent"), "sourced": date.today().isoformat()}
    (out / f"{shot['id']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return rec


def run(u: dict, q: dict | None = None, force: bool = False, shot: str | None = None, net=None) -> dict:
    """Source a film's plan, or one shot of it (`shot`). Blocked, naming the key, when a
    library the plan allows has no key; never substitutes one the plan did not allow."""
    d = scriptmod.video_dir(u["slug"])
    if not (d / "shots.json").exists():
        return {"status": "failed", "reason": "no shots.json: invoke the shot-plan skill first"}
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    targets = [s for s in plan.get("shots", []) if s.get("kind") in SOURCED and (shot is None or s.get("id") == shot)]
    if shot and not targets:
        return {"status": "failed", "reason": f"{shot} is not a sourced shot in shots.json"}
    missing: dict[str, list[str]] = {}
    for s in targets:
        if s["kind"] == "texture":
            continue
        for src in s.get("sources") or []:
            if src in sources.MODULES:
                for k in sources.missing_keys(src):
                    missing.setdefault(k, []).append(s["id"])
    if missing:
        return {"status": "blocked", "reason": "; ".join(
            f"{k} is not set (needed by {', '.join(sorted(set(v))[:6])}{' …' if len(set(v)) > 6 else ''})"
            for k, v in missing.items()) + " (VISUAL_SPEC.md §6.3)"}
    reg = shotmod.registry()
    out = d / "sources"
    out.mkdir(parents=True, exist_ok=True)
    net = net or netmod.Net(film_dir=d)
    ledger = usage.read()
    results: dict[str, dict] = {}
    seen: set[str] = set()
    try:
        for s in targets:
            if s["kind"] == "texture":
                rec = _write_textures(out, s)
                s["source_status"] = "awaiting_textures"
                s["source_reason"] = "four prompts in sources/textures.json, made through the Higgsfield connector (§6.5)"
            else:
                picked_ids, picked_hashes = _picked(plan, skip=s["id"])
                prior = {**{a: f"in {f}, inside the last ten films" for a, f in usage.window_ids(u["slug"], ledger).items()},
                         **picked_ids}
                hashes = {**usage.window_hashes(u["slug"], ledger), **picked_hashes}
                rec = source_shot(s, net, reg, prior, hashes, seen, out)
                s["source_status"], s["source_reason"] = rec["status"], rec["reason"]
            results[s["id"]] = rec
            net.save_counts()
    except sources.Blocked as e:
        net.save_counts()
        _save_plan(d, plan)
        return {"status": "blocked", "reason": str(e), "done": sorted(results)}
    _save_plan(d, plan)
    totals = net.save_counts() or net.prior
    ok = [k for k, r in results.items() if r["status"] == "ok"]
    fallback = {k: r["reason"] for k, r in results.items() if r["status"] == "fallback"}
    textures = [k for k, r in results.items() if r["status"] == "awaiting_textures"]
    session = net.session
    return {"status": "ok", "slug": u["slug"], "shots": len(results), "ok": ok, "fallback": fallback,
            "awaiting_textures": textures,
            "requests_this_run": {k: v["requests"] for k, v in session.items()},
            "cached_this_run": {k: v["cached"] for k, v in session.items()},
            "downloads_this_run": sum(v["downloads"] for v in session.values()),
            "mb_this_run": round(sum(v["bytes"] for v in session.values()) / 1e6, 1),
            "film_requests": {k: v.get("requests", 0) for k, v in totals.items()},
            "slept_s": round(net.slept, 1)}


def _save_plan(d: Path, plan: dict) -> None:
    (d / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def summary(result: dict) -> list[str]:
    """The lines `hubricon-content source` prints above its JSON."""
    if result.get("status") != "ok":
        return [f"source {result.get('status')}: {result.get('reason')}"]
    lines = [f"{result['slug']}: {result['shots']} shots · {len(result['ok'])} with three or more candidates · "
             f"{len(result['fallback'])} on fallback · {len(result['awaiting_textures'])} awaiting textures"]
    lines.append("requests this run: " + (", ".join(f"{k} {v}" for k, v in result["requests_this_run"].items() if v)
                                          or "none (all from the cache)")
                 + f" · previews downloaded: {result['downloads_this_run']} ({result['mb_this_run']} MB)")
    lines.append("requests this film: " + ", ".join(f"{k} {v}" for k, v in result["film_requests"].items()))
    for k, why in result["fallback"].items():
        lines.append(f"  {k} fallback: {why}")
    return lines
