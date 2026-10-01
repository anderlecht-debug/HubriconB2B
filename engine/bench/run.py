"""Run the Simons–Thorp–Griffin test.

    cd engine && uv run python -m bench.run --tests 3            # seeds 101, 202, 303
    cd engine && uv run python -m bench.run --seed 101 --worlds clean reactive

One test = one seed: six worlds (bench/worlds.py) plus the stability checks
on the clean world, scored by bench/rubric.py. Writes the full evidence as
JSON beside the printed scorecard.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

from hubricon_engine.models import drift, elasticity, seasonality

from . import rubric
from .pipeline import pricing_sweep, run_engine
from .score import world_report
from .worlds import WORLDS, build, period

TEST_SEEDS = (101, 202, 303)


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _dumps(o):
    return json.dumps(_jsonable(o), sort_keys=True, default=str)


def _promises(drafts):
    return {(d["kind"], str(d["evidence"].get("sku") or d["evidence"].get("campaign_name")),
             str(d["evidence"].get("reason"))): d["expected_impact_usd"] for d in drafts}


def world_task(args):
    name, seed = args
    t0 = time.perf_counter()
    data, truth = build(name, seed)
    out = run_engine(data)
    rep = world_report(name, data, truth, out, seed)
    rep["seconds"] = round(time.perf_counter() - t0, 1)
    if name == "clean":
        rep["_digest"] = hashlib.sha256(_dumps(out["drafts"]).encode()).hexdigest()
        rep["_promises"] = [[list(k), v] for k, v in _promises(out["drafts"]).items()]
    return ("world", seed, name, _jsonable(rep))


def rerun_task(args):
    """The clean world again: once on the same seed, once on another."""
    seed, engine_seed = args
    data, _ = build("clean", seed)
    out = run_engine(data, seed=engine_seed)
    return ("rerun", seed, engine_seed, {"digest": hashlib.sha256(_dumps(out["drafts"]).encode()).hexdigest(),
                                         "promises": [[list(k), v] for k, v in _promises(out["drafts"]).items()]})


def perturb_task(seed):
    """One month dropped (twice), and one clean month more, on the clean world."""
    data, _ = build("clean", seed)
    n = WORLDS["clean"].get("n_periods", 12)
    base = {d["evidence"]["sku"]: (np.sign(d["evidence"]["step_fraction"]), abs(float(d["expected_impact_usd"] or 0)))
            for d in pricing_sweep(data) if d["kind"] == "price_step" and d["evidence"].get("reason") != "stretch"}
    flips, compared, flip_usd, common_usd = 0, 0, 0.0, 0.0
    for drop in (2, 6):
        start, _ = period(drop, n)
        d2 = {**data, "sku_economics": [r for r in data["sku_economics"] if r["period_start"] != start],
              "asin_traffic": [r for r in data["asin_traffic"] if r["period_start"] != start]}
        for d in pricing_sweep(d2):
            if d["kind"] != "price_step" or d["evidence"].get("reason") == "stretch":
                continue
            sku = d["evidence"]["sku"]
            if sku not in base:
                continue
            compared += 1
            sign0, usd0 = base[sku]
            common_usd += usd0
            if np.sign(d["evidence"]["step_fraction"]) != sign0:
                flips += 1
                flip_usd += usd0
    last = max(r["period_start"] for r in data["sku_economics"])
    short = {**data, "sku_economics": [r for r in data["sku_economics"] if r["period_start"] != last],
             "asin_traffic": [r for r in data["asin_traffic"] if r["period_start"] != last]}
    new = elasticity.run(data, seasonal=seasonality.indices(data))
    old = elasticity.run(short, seasonal=seasonality.indices(short))
    dr = drift.compare_runs(new, old, [], [])
    n_pairs = dr.get("n_pairs") or 0
    return ("perturb", seed, None, {"flips": flips, "compared": compared,
                                   "flip_share": flips / max(1, compared),
                                   "flip_dollar_share": flip_usd / max(1e-9, common_usd),
                                   "drift_pairs": n_pairs, "drift_alarms": dr.get("n_drifted") or 0,
                                   "drift_alarm_share": (dr.get("n_drifted") or 0) / max(1, n_pairs)})


def _dispatch(task):
    kind, args = task
    return {"world": world_task, "rerun": rerun_task, "perturb": perturb_task}[kind](args)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, action="append")
    ap.add_argument("--tests", type=int, default=None)
    ap.add_argument("--worlds", nargs="*", default=list(WORLDS))
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-stability", action="store_true")
    ap.add_argument("--rescore", default=None, help="score a saved JSON under the current rubric")
    a = ap.parse_args(argv)
    if a.rescore:
        saved = json.loads(Path(a.rescore).read_text())
        for s, v in saved.items():
            card = rubric.score(v["reports"], v["stability"])
            print(f"\n══ TEST seed {s}: {card['score']}/{card['of']} (rescored) ══")
            for c in card["criteria"]:
                print(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['id']} {c['lens']:7s} {c['name']}")
                for line in c["evidence"]:
                    print(f"          {line}")
        return saved
    seeds = a.seed or list(TEST_SEEDS[: (a.tests or 1)])
    tasks = []
    for s in seeds:
        tasks += [("world", (w, s)) for w in a.worlds]
        if not a.no_stability:
            tasks += [("rerun", (s, 42)), ("rerun", (s, 7)), ("perturb", s)]
    t0 = time.perf_counter()
    results = []
    with mp.get_context("fork").Pool(a.jobs) as pool:
        for res in pool.imap_unordered(_dispatch, tasks):
            results.append(res)
            print(f"  … {res[0]} seed {res[1]} {res[2] or ''} done ({time.perf_counter() - t0:.0f}s)", flush=True)
    summary = {}
    for s in seeds:
        reports = [r[3] for r in results if r[0] == "world" and r[1] == s]
        reports.sort(key=lambda r: list(WORLDS).index(r["world"]))
        stab = None
        if not a.no_stability:
            clean = next((r for r in reports if r["world"] == "clean"), None)
            same = next(r[3] for r in results if r[0] == "rerun" and r[1] == s and r[2] == 42)
            other = next(r[3] for r in results if r[0] == "rerun" and r[1] == s and r[2] == 7)
            pert = next(r[3] for r in results if r[0] == "perturb" and r[1] == s)
            as_map = lambda pairs: {tuple(k): v for k, v in pairs}
            stab = {"byte_identical": bool(clean and same["digest"] == clean["_digest"]),
                    # the same promises, in any order: drafts are ranked by
                    # scores that can tie, and a tie's order is not a promise
                    "seed_invariant": bool(clean and as_map(other["promises"]) == as_map(clean["_promises"])),
                    **pert}
        card = rubric.score(reports, stab)
        summary[s] = {"card": card, "stability": stab, "reports": reports}
        print(f"\n══ TEST seed {s}: {card['score']}/{card['of']} ══")
        for c in card["criteria"]:
            print(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['id']} {c['lens']:7s} {c['name']}")
            for line in c["evidence"]:
                print(f"          {line}")
    print(f"\ntotal {time.perf_counter() - t0:.0f}s; scores: " + ", ".join(f"seed {s}: {summary[s]['card']['score']}/10" for s in seeds))
    if a.out:
        Path(a.out).write_text(json.dumps(_jsonable(summary), indent=1, default=str))
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
