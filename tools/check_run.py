#!/usr/bin/env python3
"""Validate a run folder of the run log (SUPPLY_VARIABILITY.md sections 6.3 and 8.3, O6, O7, O12).

    python3 tools/check_run.py <run-folder>           validate one run
    python3 tools/check_run.py <run-folder> --clean   the same, and exit 1 unless the run is clean
    python3 tools/check_run.py --all [runs]           every run, the clean streak, and the outer loop's lock (O6)
    python3 tools/check_run.py --tracked              exit 1 if git tracks any file under runs/ or brands/
    python3 tools/check_run.py <run-folder> --seal VALUE LOW HIGH NAIVE
                                                      seal the run's dollar prediction before the outcome

Prints one line per problem, `<run>: [<rule>] <what is wrong>`, one per alert, and exits 0
only when the run is valid. Exit 1 means it is not, exit 2 means the command itself was wrong.

A run whose `status` is still null is a draft: only its shape, its inputs and its separation
from other clients are checked. A finished run (`ok`, `stuck` or `failed`) must be complete.

What it computes and writes back into run.json when the field is still null (a value that is
already there and disagrees is a problem, never overwritten):

    cost.share_checking     tokens_checking / tokens_total, to 4 places
    cost.wall_time          seconds from started_at to finished_at
    numbers.counts          how many numbers in the client view are measured, sourced, inference
    loop.checker_passes     the most passes agent_check.py needed on any one text (checker.txt)
    diff_since_last_run     inputs, key numbers and recommendation against this client's last run
    outcome                 copied from outcome.json, with vs_baseline = actual - baseline

Alerts go to `runs/ALERTS.md`, one line each, and nowhere else: the repo is public, so no
GitHub issue is opened (O12). The kinds:

    failed, stuck      the run's status, or a loop that hit its cap (3 checker passes, 2 send-backs, O7)
    checker            the client view fails tools/agent_check.py --client
    rop, lead-time     a reorder point without its service level, a lead time without a label
    number-moved       a key number moved more than 25% from the last run with the same inputs (O12)
    prediction-missed  the actual dollars landed outside the sealed range
    separation         another client's code or data is in this run's folder (section 8.3)
    tracked            git tracks a file of the run log

A run is clean when it is valid, its status is `ok` (the last checker pass on every text
exits 0 and the red team's verdict is `ship`, inside the caps) and it raises no alert. The
outer loop stays locked until 5 runs in a row are clean, across at least 2 datasets or clients.

The seal is a SHA-256 over the prediction, the run and the time. It shows the prediction was
not edited afterwards. It does not show when it was made: there is no outside timestamp yet
(O21), so "sealed before" rests on this folder's own record.

`--no-write` checks without changing run.json, numbers.json, outcome.json or ALERTS.md.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_check  # noqa: E402
import new_run  # noqa: E402

LABELS = ("measured", "sourced", "inference")
MAX_CHECKER_PASSES = 3  # O7
MAX_SEND_BACKS = 2  # O7
NUMBER_MOVE = 0.25  # O12
CLEAN_RUNS = 5  # O6
CLEAN_SPREAD = 2  # O6: datasets or clients
MARKER_LENGTH = 12  # a value this long, with a letter in it, identifies the data it came from
PROTECTED = ("runs", "brands")

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Report:
    """What one check of one run folder found."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.run: dict | None = None
        self.problems: list[tuple[str, str]] = []
        self.alerts: list[tuple[str, str]] = []
        self.notes: list[str] = []
        self.changed = False

    @property
    def name(self) -> str:
        return f"{self.folder.parent.name}/{self.folder.name}"

    @property
    def status(self) -> str | None:
        return self.run.get("status") if isinstance(self.run, dict) else None

    @property
    def valid(self) -> bool:
        return not self.problems

    @property
    def clean(self) -> bool:
        return self.valid and self.status == "ok" and not self.alerts

    def problem(self, rule: str, message: str) -> None:
        self.problems.append((rule, message))

    def alert(self, kind: str, message: str) -> None:
        if (kind, message) not in self.alerts:
            self.alerts.append((kind, message))


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_time(value) -> datetime.datetime | None:
    """A run-log time, `2026-11-27T09:30:00Z`, or None when it is not one."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.datetime.strptime(value, _TIME_FORMAT)
    except ValueError:
        return None


def read_json(path: Path):
    """The JSON in a file, or None when it is missing or does not parse."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def same(a, b) -> bool:
    """Equal, allowing for a number rounded to 4 places."""
    if is_number(a) and is_number(b):
        return abs(a - b) <= 1e-4 * max(1.0, abs(b))
    return a == b


def derive(r: Report, holder: dict, key: str, value, name: str) -> None:
    """Fill a computed field that is still null. One that is set and disagrees is a problem."""
    if holder.get(key) is None:
        if value is not None:
            holder[key] = value
            r.changed = True
    elif not same(holder[key], value):
        r.problem("derived", f"`{name}` is {json.dumps(holder[key])} but the record gives {json.dumps(value)}")


# --------------------------------------------------------------------------------------
# Shape: every field of the table in section 6.3 is there and is the right kind of thing
# --------------------------------------------------------------------------------------

def check_shape(r: Report, run) -> bool:
    if not isinstance(run, dict):
        r.problem("schema", "run.json is missing or is not a JSON object")
        return False
    template = new_run.empty_run("t000", "x", "made-up", "q", "")
    for key, default in template.items():
        if key not in run:
            r.problem("schema", f"run.json has no `{key}`")
        elif isinstance(default, dict) and default:
            if not isinstance(run[key], dict):
                r.problem("schema", f"`{key}` is not an object")
            else:
                for inner in default:
                    if inner not in run[key]:
                        r.problem("schema", f"run.json has no `{key}.{inner}`")
        elif isinstance(default, (list, dict)) and not isinstance(run[key], type(default)):
            r.problem("schema", f"`{key}` is not {'a list' if isinstance(default, list) else 'an object'}")
    if r.problems:
        return False
    if not isinstance(run["disagreements"]["items"], list):
        r.problem("schema", "`disagreements.items` is not a list")
    return r.valid


def check_identity(r: Report, run: dict) -> None:
    folder = r.folder
    named = new_run.RUN_FOLDER.match(folder.name)
    if not named:
        r.problem("folder", "the folder is not named <YYYY-MM-DD>_<run-id>")
    if not new_run.CLIENT_CODE.match(folder.parent.name):
        r.problem("folder", f"the client folder `{folder.parent.name}` is not a neutral code (c or t and 3 to 6 digits)")
    if run["schema"] != new_run.SCHEMA:
        r.problem("schema", f"`schema` is {run['schema']!r}, this checker reads schema {new_run.SCHEMA}")
    if run["client_code"] != folder.parent.name:
        message = f"run.json says client `{run['client_code']}` but the run is in `{folder.parent.name}`'s folder"
        r.problem("separation", message)
        r.alert("separation", message)
    if named and run["run_id"] != named.group(2):
        r.problem("folder", f"`run_id` is {run['run_id']!r} but the folder says {named.group(2)!r}")
    if run["data_kind"] not in new_run.DATA_KINDS:
        r.problem("schema", f"`data_kind` is not one of: {', '.join(new_run.DATA_KINDS)}")
    elif (folder.parent.name[:1] == "c") != (run["data_kind"] == "client"):
        r.problem("schema", "a `c` code is for client data, a `t` code is for made-up or public data")
    if not is_text(run["question"]):
        r.problem("schema", "`question` is empty")
    if run["status"] is not None and run["status"] not in new_run.STATUSES:
        r.problem("schema", f"`status` is not null or one of: {', '.join(new_run.STATUSES)}")
    started, finished = parse_time(run["started_at"]), parse_time(run["finished_at"])
    if started is None:
        r.problem("schema", "`started_at` is not a UTC time like 2026-11-27T09:30:00Z")
    if run["finished_at"] is not None and finished is None:
        r.problem("schema", "`finished_at` is not a UTC time like 2026-11-27T09:30:00Z")
    if started and finished and finished < started:
        r.problem("schema", "`finished_at` is before `started_at`")
    for name in new_run.FILES:
        if not (folder / name).is_file():
            r.problem("files", f"{name} is missing")
    if not (folder / new_run.INPUTS_DIR).is_dir():
        r.problem("files", "inputs/ is missing")


def check_agents_run(r: Report, run: dict) -> None:
    for n, entry in enumerate(run["agents_run"], 1):
        where = f"`agents_run` entry {n}"
        if not isinstance(entry, dict) or entry.get("agent") not in agent_check.AGENTS:
            r.problem("schema", f"{where} does not name one of the nine agents")
            continue
        started, finished = parse_time(entry.get("started")), parse_time(entry.get("finished"))
        if started is None or finished is None or finished < started:
            r.problem("schema", f"{where} ({entry['agent']}) needs `started` and `finished` times, in order")
        passes = entry.get("passes")
        if not isinstance(passes, int) or isinstance(passes, bool) or passes < 1:
            r.problem("schema", f"{where} ({entry['agent']}) needs `passes`, a whole number from 1")


def check_inputs(r: Report, run: dict) -> None:
    folder = r.folder / new_run.INPUTS_DIR
    listed = set()
    for n, entry in enumerate(run["inputs"], 1):
        if not isinstance(entry, dict) or not is_text(entry.get("file")):
            r.problem("inputs", f"`inputs` entry {n} has no `file`")
            continue
        name = entry["file"]
        listed.add(name)
        if "/" in name or "\\" in name or name.startswith("."):
            r.problem("inputs", f"input `{name}` is not a plain file name")
            continue
        for key in ("hash", "rows", "date_range", "source"):
            if key not in entry:
                r.problem("inputs", f"input `{name}` has no `{key}`")
        if not isinstance(entry.get("hash"), str) or not _HASH.match(entry["hash"]):
            r.problem("inputs", f"input `{name}` needs a `hash` of the form sha256:<64 hex>")
        if not is_text(entry.get("source")):
            r.problem("inputs", f"input `{name}` does not say where it came from (`source`)")
        path = folder / name
        if path.is_file():
            if entry.get("hash") != new_run.sha256(path):
                r.problem("inputs", f"inputs/{name} has changed since its hash was recorded")
        elif not is_text(entry.get("stored_at")):
            r.problem("inputs", f"input `{name}` is not in inputs/ and `stored_at` does not say where it is kept")
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.name not in listed:
                r.problem("inputs", f"inputs/{path.name} is not listed in run.json")


def check_conclusions(r: Report, run: dict, finished: bool) -> None:
    for agent, entry in run["conclusions"].items():
        if agent not in agent_check.AGENTS:
            r.problem("schema", f"`conclusions` names `{agent}`, which is not one of the nine agents")
            continue
        if not isinstance(entry, dict) or not is_text(entry.get("summary")) or not is_text(entry.get("why")):
            r.problem("conclusions", f"{agent}'s conclusion needs a `summary` and a `why`")
            continue
        numbers = entry.get("key_numbers")
        if not isinstance(numbers, list):
            r.problem("conclusions", f"{agent}'s conclusion needs `key_numbers`, a list (it may be empty)")
            continue
        for k in numbers:
            ok = isinstance(k, dict) and is_text(k.get("name")) and is_number(k.get("value")) and isinstance(k.get("unit"), str)
            if not ok:
                r.problem("conclusions", f"a key number of {agent} needs a `name`, a numeric `value` and a `unit`")
            elif k.get("label") not in LABELS:
                r.problem("conclusions", f"{agent}'s key number `{k['name']}` is not labelled: {', '.join(LABELS)}")
    if finished:
        for entry in run["agents_run"]:
            agent = entry.get("agent") if isinstance(entry, dict) else None
            if agent in agent_check.AGENTS and agent not in run["conclusions"]:
                r.problem("conclusions", f"{agent} ran but `conclusions` does not say what it concluded")


def check_lists(r: Report, run: dict) -> None:
    for item in run["disagreements"]["items"]:
        if not isinstance(item, dict) or not all(is_text(item.get(k)) for k in ("topic", "winner", "reason")):
            r.problem("schema", "a disagreement needs a `topic`, a `winner` and a `reason`")
    for item in run["overrides"]:
        if not isinstance(item, dict) or not all(is_text(item.get(k)) for k in ("by", "what", "why")):
            r.problem("schema", "an override needs `by`, `what` and `why`")
    if run["disagreements"]["items"] and not read(r.folder / "disagreements.md").strip():
        r.problem("files", "run.json lists a disagreement but disagreements.md is empty")


# --------------------------------------------------------------------------------------
# The loop: checker passes, the client view, the red team's verdict, the caps of O7
# --------------------------------------------------------------------------------------

def checker_passes(folder: Path) -> dict[str, list[dict]]:
    """The passes in checker.txt, grouped by what was checked."""
    grouped: dict[str, list[dict]] = {}
    for entry in agent_check.read_log(read(folder / "checker.txt")):
        grouped.setdefault(entry["target"], []).append(entry)
    return grouped


def check_view_label(r: Report, run: dict) -> None:
    """Made-up or public data says so on the first line of anything a client could be shown."""
    label = new_run.NOT_A_RESULT.get(run["data_kind"])
    if not label:
        return
    lines = [line.strip() for line in read(r.folder / "client_view.md").splitlines() if line.strip()]
    if not lines or lines[0] != label:
        r.problem("not-a-result", f"client_view.md must start with the line `{label}`")


def check_loop(r: Report, run: dict) -> None:
    status = run["status"]
    passes = checker_passes(r.folder)
    most = max((len(entries) for entries in passes.values()), default=0)
    derive(r, run["loop"], "checker_passes", most, "loop.checker_passes")
    send_backs = run["loop"]["red_team_send_backs"]
    if not isinstance(send_backs, int) or isinstance(send_backs, bool) or send_backs < 0:
        r.problem("schema", "`loop.red_team_send_backs` is not a whole number from 0")
        send_backs = 0
    if most > MAX_CHECKER_PASSES:
        r.problem("caps", f"{most} checker passes on one text: the cap is {MAX_CHECKER_PASSES} (O7)")
    if send_backs > MAX_SEND_BACKS:
        r.problem("caps", f"{send_backs} red-team send-backs: the cap is {MAX_SEND_BACKS} (O7)")

    view = read(r.folder / "client_view.md")
    failures = agent_check.check(view, client=True) if view.strip() else []
    verdict_text = read(r.folder / "verdict.md")
    verdict = agent_check.verdict(verdict_text)
    if verdict_text.strip():
        for f in agent_check.check(verdict_text, agent="feynman-red-team", only=("sections",)):
            r.problem("verdict", f"verdict.md:{f.line}: {f.message}")

    capped = []
    for target, entries in sorted(passes.items()):
        if len(entries) >= MAX_CHECKER_PASSES and entries[-1]["exit"] != 0:
            capped.append(f"`{target}` still fails after {len(entries)} checker passes")
    if send_backs >= MAX_SEND_BACKS and verdict != "ship":
        capped.append(f"the red team has sent the work back {send_backs} times and has not said ship")
    if capped and status != "stuck":
        r.problem("caps", f"the loop hit its cap ({'; '.join(capped)}), so `status` must be `stuck`")

    if status == "ok":
        if not view.strip():
            r.problem("checker", "client_view.md is empty")
        for f in failures:
            r.problem("checker", f"client_view.md:{f.line}: [{f.rule}] {f.message}")
        logged = [t for t in passes if t.split(" ")[0] == "client_view.md" and "--client" in t.split(" ")]
        if not logged:
            r.problem("checker", "checker.txt has no pass of `agent_check.py client_view.md --client --log checker.txt`")
        for target, entries in sorted(passes.items()):
            if entries[-1]["exit"] != 0:
                r.problem("checker", f"the last checker pass on `{target}` exits {entries[-1]['exit']}")
        if verdict != "ship":
            r.problem("verdict", f"status is ok but the red team's verdict is {verdict or 'missing'}, not ship")
        if not any(isinstance(e, dict) and e.get("agent") == "feynman-red-team" for e in run["agents_run"]):
            r.problem("verdict", "status is ok but feynman-red-team is not in `agents_run`")
    elif status == "stuck":
        r.alert("stuck", "; ".join(capped) if capped else "the run is marked stuck")
    elif status == "failed":
        r.alert("failed", "the run is marked failed")

    if failures:
        r.alert("checker", f"client_view.md fails the checker: {len(failures)} failure(s)")
    for rule in ("rop", "lead-time"):
        lines = [str(f.line) for f in failures if f.rule == rule]
        if lines:
            what = "a reorder point without its service level and inputs" if rule == "rop" else "a lead time with no label"
            r.alert(rule, f"client_view.md line {', '.join(lines)}: {what}")


def check_numbers(r: Report, run: dict, write: bool) -> None:
    """numbers.json is every number in the client view, and run.json counts them by label."""
    path = r.folder / "numbers.json"
    stored = read_json(path)
    if not isinstance(stored, list):
        r.problem("numbers", "numbers.json is not a JSON list")
        return
    found = agent_check.numbers_in(read(r.folder / "client_view.md"))
    if not stored and found:
        stored = found
        if write:
            new_run.write_json(path, found)
    elif stored != found:
        r.problem("numbers", "numbers.json does not match client_view.md: rerun agent_check.py on it with --json numbers.json")
        return
    counts = {label: sum(1 for n in stored if n.get("label") == label) for label in LABELS}
    counts["unlabelled"] = sum(1 for n in stored if n.get("label") not in LABELS)
    derive(r, run["numbers"], "counts", counts, "numbers.counts")


def check_cost(r: Report, run: dict) -> None:
    cost = run["cost"]
    total, checking = cost["tokens_total"], cost["tokens_checking"]
    for key in ("tokens_total", "tokens_checking"):
        value = cost[key]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            r.problem("cost", f"`cost.{key}` is not a whole number of tokens")
            return
    if total is not None and checking is not None:
        if checking > total:
            r.problem("cost", "`cost.tokens_checking` is more than `cost.tokens_total`")
        elif total:
            derive(r, cost, "share_checking", round(checking / total, 4), "cost.share_checking")
    elif not is_text(cost.get("note")):
        r.problem("cost", "the tokens are not recorded and `cost.note` does not say why")
    started, finished = parse_time(run["started_at"]), parse_time(run["finished_at"])
    if finished is None:
        r.problem("schema", "a finished run needs `finished_at`")
    elif started:
        derive(r, cost, "wall_time", int((finished - started).total_seconds()), "cost.wall_time")
    cycle = cost["cycle_time_upload_to_first_dollar"]
    if cycle is not None and (not is_number(cycle) or cycle < 0):
        r.problem("cost", "`cost.cycle_time_upload_to_first_dollar` is not a number of seconds")


# --------------------------------------------------------------------------------------
# The sealed prediction and its outcome
# --------------------------------------------------------------------------------------

def seal_hash(run: dict) -> str:
    """The SHA-256 a sealed prediction must still have."""
    p = run["prediction"]
    body = {
        "client_code": run["client_code"],
        "run_id": run["run_id"],
        "value": float(p["value"]),
        "range": [float(p["range"][0]), float(p["range"][1])],
        "naive_baseline": float(p["naive_baseline"]),
        "sealed_at": p["sealed_at"],
    }
    text = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def prediction_shape(p: dict) -> str | None:
    """What is wrong with a prediction's own fields, or None."""
    rng = p.get("range")
    if not is_number(p.get("value")) or not is_number(p.get("naive_baseline")):
        return "a prediction needs a numeric `value` and `naive_baseline`"
    if not isinstance(rng, list) or len(rng) != 2 or not all(is_number(x) for x in rng):
        return "a prediction needs a `range` of [low, high]"
    if not rng[0] <= p["value"] <= rng[1]:
        return "the predicted value is outside its own range"
    if parse_time(p.get("sealed_at")) is None:
        return "a prediction needs `sealed_at`"
    return None


def check_prediction(r: Report, run: dict, finished: bool) -> bool:
    """True when the run holds a sealed prediction that still matches its seal."""
    p = run["prediction"]
    if p["sealed_hash"] is None:
        if any(p[k] is not None for k in ("value", "range", "naive_baseline", "sealed_at")):
            r.problem("seal", "the prediction is written but not sealed: use --seal VALUE LOW HIGH NAIVE")
        elif finished and not is_text(p.get("why_none")):
            r.problem("prediction", "no sealed prediction, and `prediction.why_none` does not say why")
        return False
    wrong = prediction_shape(p)
    if wrong:
        r.problem("seal", wrong)
        return False
    if seal_hash(run) != p["sealed_hash"]:
        r.problem("seal", "the prediction has been changed since it was sealed")
        return False
    return True


def check_outcome(r: Report, run: dict, sealed: bool, write: bool) -> None:
    path = r.folder / "outcome.json"
    outcome = read_json(path)
    if not isinstance(outcome, dict) or any(k not in outcome for k in new_run.OUTCOME):
        r.problem("outcome", f"outcome.json needs the fields: {', '.join(new_run.OUTCOME)}")
        return
    actual, baseline, graded = outcome["actual_dollars"], outcome["baseline_dollars"], outcome["graded_at"]
    for key in ("actual_dollars", "baseline_dollars", "vs_baseline", "censored_days"):
        if outcome[key] is not None and not is_number(outcome[key]):
            r.problem("outcome", f"`{key}` in outcome.json is not a number")
            return
    before = dict(outcome)
    if actual is not None:
        if parse_time(graded) is None:
            r.problem("outcome", "an outcome needs `graded_at`")
        if not sealed:
            r.problem("outcome", "an outcome with no sealed prediction: the prediction is sealed first")
        else:
            p = run["prediction"]
            if parse_time(graded) and parse_time(graded) < parse_time(p["sealed_at"]):
                r.problem("outcome", "the outcome is graded before the prediction was sealed")
            low, high = p["range"]
            if not low <= actual <= high:
                r.alert("prediction-missed", f"actual ${actual:,.2f} is outside the sealed range ${low:,.2f} to ${high:,.2f}")
        if baseline is not None:
            derive(r, outcome, "vs_baseline", round(actual - baseline, 2), "vs_baseline (outcome.json)")
    if outcome != before and write:
        new_run.write_json(path, outcome)
    if all(run["outcome"].get(k) is None for k in new_run.OUTCOME):
        if any(v is not None for v in outcome.values()):
            run["outcome"] = {k: outcome[k] for k in new_run.OUTCOME}
            r.changed = True
    elif any(not same(run["outcome"].get(k), outcome[k]) for k in new_run.OUTCOME):
        r.problem("outcome", "`outcome` in run.json does not match outcome.json")


# --------------------------------------------------------------------------------------
# What changed since this client's last run, and the 25% alert of O12
# --------------------------------------------------------------------------------------

def run_folders(client_dir: Path) -> list[Path]:
    if not client_dir.is_dir():
        return []
    return sorted(p for p in client_dir.iterdir() if p.is_dir() and new_run.RUN_FOLDER.match(p.name))


def previous_run(folder: Path, run: dict) -> tuple[Path, dict] | None:
    """This client's run just before this one, by start time."""
    mine = (str(run.get("started_at")), folder.name)
    best = None
    for other in run_folders(folder.parent):
        if other.name == folder.name:
            continue
        data = read_json(other / "run.json")
        if not isinstance(data, dict):
            continue
        key = (str(data.get("started_at")), other.name)
        if key < mine and (best is None or key > best[0]):
            best = (key, other, data)
    return (best[1], best[2]) if best else None


def key_numbers(run: dict) -> dict[str, float]:
    """The numbers a run stands on: each agent's key numbers and the sealed prediction."""
    out = {}
    conclusions = run.get("conclusions")
    for agent, entry in (conclusions.items() if isinstance(conclusions, dict) else ()):
        for k in (entry.get("key_numbers") or []) if isinstance(entry, dict) else []:
            if isinstance(k, dict) and is_text(k.get("name")) and is_number(k.get("value")):
                out[f"{agent}: {k['name']}"] = k["value"]
    prediction = run.get("prediction")
    if isinstance(prediction, dict) and is_number(prediction.get("value")):
        out["prediction"] = prediction["value"]
    return out


def input_hashes(run: dict) -> list[str]:
    inputs = run.get("inputs")
    return sorted(str(e.get("hash")) for e in (inputs if isinstance(inputs, list) else []) if isinstance(e, dict))


def diff_since(folder: Path, run: dict) -> dict:
    found = previous_run(folder, run)
    if not found:
        return {"previous_run": None, "inputs_changed": None, "numbers_moved": [], "recommendation_changed": None}
    other, data = found
    before, after = key_numbers(data), key_numbers(run)
    moved = []
    for name in sorted(set(before) & set(after)):
        if not same(before[name], after[name]):
            change = round((after[name] - before[name]) / abs(before[name]), 4) if before[name] else None
            moved.append({"name": name, "before": before[name], "after": after[name], "change": change})
    return {
        "previous_run": other.name,
        "inputs_changed": input_hashes(data) != input_hashes(run),
        "numbers_moved": moved,
        "recommendation_changed": read(other / "client_view.md") != read(folder / "client_view.md"),
    }


def check_diff(r: Report, run: dict) -> None:
    diff = diff_since(r.folder, run)
    stored = run["diff_since_last_run"]
    gone = isinstance(stored, dict) and stored.get("previous_run") and not (r.folder.parent / str(stored["previous_run"])).is_dir()
    if stored is None:
        run["diff_since_last_run"] = diff
        r.changed = True
    elif gone:
        diff = stored  # the run it was compared with has been deleted: the record stands
    elif stored != diff:
        r.problem("derived", "`diff_since_last_run` does not match this client's previous run")
    if not isinstance(diff, dict) or diff.get("inputs_changed") is not False:
        return
    for move in diff.get("numbers_moved") or []:
        change = move.get("change")
        if change is None or abs(change) > NUMBER_MOVE:
            by = "from zero" if change is None else f"by {abs(change):.0%}"
            r.alert("number-moved", f"`{move['name']}` moved {by} ({move['before']} to {move['after']}) with no change in inputs")


# --------------------------------------------------------------------------------------
# Keeping clients apart (section 8.3)
# --------------------------------------------------------------------------------------

def values_of(path: Path) -> set[str]:
    """The cells of a data file long enough to identify it. A header row is left out."""
    text = new_run.read_text(path)
    if not text:
        return set()
    if path.suffix.lower() in (".csv", ".tsv"):
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        rows = list(csv.reader(text.splitlines()[1:], delimiter=delimiter))
        cells = (cell for row in rows for cell in row)
    else:
        cells = iter(re.split(r'[,\t"\n\r]', text))
    out = set()
    for cell in cells:
        cell = cell.strip()
        if len(cell) >= MARKER_LENGTH and re.search(r"[A-Za-z]", cell):
            out.add(cell)
    return out


def client_values(client_dir: Path, cache: dict) -> set[str]:
    """Every identifying value in one client's inputs, across its runs."""
    key = str(client_dir)
    if key not in cache:
        found: set[str] = set()
        for folder in run_folders(client_dir):
            inputs = folder / new_run.INPUTS_DIR
            for path in sorted(inputs.iterdir()) if inputs.is_dir() else []:
                if path.is_file() and not path.is_symlink():
                    found |= values_of(path)
        cache[key] = found
    return cache[key]


def check_separation(r: Report, cache: dict) -> None:
    folder, root = r.folder, r.folder.parent.parent
    found = []
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            found.append(f"{path.relative_to(folder)} is a link out of the run folder")
    texts = {}
    for path in sorted(folder.rglob("*")):
        inside = path.relative_to(folder)
        if path.is_file() and not path.is_symlink() and inside.parts[0] != new_run.INPUTS_DIR:
            texts[str(inside)] = read(path)
    others = [
        d for d in sorted(root.iterdir())
        if d.is_dir() and d.name != folder.parent.name and new_run.CLIENT_CODE.match(d.name)
    ] if root.is_dir() else []
    own = client_values(folder.parent, cache)
    for other in others:
        code = re.compile(rf"(?<![A-Za-z0-9]){re.escape(other.name)}(?![A-Za-z0-9])")
        foreign = client_values(other, cache) - own
        for name, text in texts.items():
            if code.search(text):
                found.append(f"{name} names another client's code ({other.name})")
            hits = sum(1 for value in foreign if value in text)
            if hits:
                found.append(f"{name} holds {hits} value(s) from the inputs of client {other.name}")
    for message in found:
        r.problem("separation", message)
        r.alert("separation", message)


# --------------------------------------------------------------------------------------
# Nothing of the run log in git
# --------------------------------------------------------------------------------------

def git_top(path: Path) -> Path | None:
    """The top of the git work tree `path` is in, or None."""
    start = path if path.is_dir() else path.parent
    try:
        done = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def tracked(top: Path, names=PROTECTED) -> list[str]:
    """The files git tracks under the folders that must stay out of it."""
    done = subprocess.run(
        ["git", "-C", str(top), "ls-files", "-z", "--", *names],
        capture_output=True, text=True, check=False,
    )
    return sorted(name for name in done.stdout.split("\0") if name)


def check_tracked(r: Report) -> None:
    root = r.folder.parent.parent.resolve()
    top = git_top(root)
    if top is None:
        return
    try:
        inside = str(root.relative_to(top.resolve()))
    except ValueError:
        return
    if inside == ".":
        return
    files = tracked(top, (inside,))
    if files:
        message = f"git tracks {len(files)} file(s) of the run log, e.g. {files[0]}: client data never goes into git"
        r.problem("tracked", message)
        r.alert("tracked", message)


# --------------------------------------------------------------------------------------
# One run
# --------------------------------------------------------------------------------------

def check(folder: Path, write: bool = True, cache: dict | None = None) -> Report:
    """Check one run folder. With `write`, fill in the computed fields and append the alerts."""
    folder = Path(folder)
    r = Report(folder)
    run = read_json(folder / "run.json")
    if not check_shape(r, run):
        return r
    r.run = run
    check_identity(r, run)
    check_agents_run(r, run)
    check_inputs(r, run)
    check_lists(r, run)
    finished = run["status"] in new_run.STATUSES
    check_conclusions(r, run, finished)
    check_view_label(r, run)
    sealed = check_prediction(r, run, finished)
    check_outcome(r, run, sealed, write)
    if finished:
        check_loop(r, run)
        check_numbers(r, run, write)
        check_cost(r, run)
        check_diff(r, run)
    check_separation(r, cache if cache is not None else {})
    check_tracked(r)
    if write:
        if r.changed:
            new_run.write_json(folder / "run.json", run)
        write_alerts(r)
    return r


def write_alerts(r: Report) -> list[str]:
    """Append this run's alerts to ALERTS.md. An alert already there is not written twice."""
    if not r.alerts:
        return []
    path = new_run.alerts_file(r.folder.parent.parent)
    have = path.read_text(encoding="utf-8")
    lines = []
    for kind, message in r.alerts:
        tail = f" | {r.name} | {kind} | {message}"
        if tail not in have:
            lines.append(f"- {new_run.now()}{tail}")
    if lines:
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return lines


def report_lines(r: Report, shown: str) -> list[str]:
    lines = [f"{shown}: [{rule}] {message}" for rule, message in r.problems]
    lines += [f"ALERT {shown}: [{kind}] {message}" for kind, message in r.alerts]
    if r.run is not None and r.status in new_run.STATUSES:
        cost = r.run["cost"]
        if is_number(cost.get("share_checking")):
            lines.append(
                f"cost  {shown}: {cost['tokens_checking']} of {cost['tokens_total']} tokens went on checking "
                f"(share {cost['share_checking']:.4f}), wall time {cost.get('wall_time')} s"
            )
    if not r.valid:
        lines.append(f"FAIL  {shown}: {len(r.problems)} problem(s)")
    elif r.status is None:
        lines.append(f"DRAFT {shown}: the shape is valid, the run is not finished (status is null)")
    elif r.clean:
        lines.append(f"OK    {shown}: valid, status ok, clean")
    else:
        lines.append(f"OK    {shown}: valid, status {r.status}, not clean ({len(r.alerts)} alert(s))")
    return lines


# --------------------------------------------------------------------------------------
# Sealing a prediction
# --------------------------------------------------------------------------------------

def seal(folder: Path, value: float, low: float, high: float, naive: float, at: str | None = None) -> str:
    """Write and seal the run's dollar prediction. Raises ValueError when it may not be sealed."""
    folder = Path(folder)
    run = read_json(folder / "run.json")
    if not isinstance(run, dict) or not isinstance(run.get("prediction"), dict):
        raise ValueError("run.json is missing or has no `prediction`")
    if run["prediction"].get("sealed_hash"):
        raise ValueError("the prediction is already sealed, and a seal is not replaced")
    outcome = read_json(folder / "outcome.json") or {}
    if outcome.get("actual_dollars") is not None or outcome.get("graded_at") is not None:
        raise ValueError("the outcome is already recorded: a prediction is sealed before its outcome")
    if not low <= value <= high:
        raise ValueError("the value must lie inside the range: VALUE LOW HIGH NAIVE")
    run["prediction"].update({
        "value": float(value), "range": [float(low), float(high)],
        "naive_baseline": float(naive), "sealed_at": at or new_run.now(), "why_none": "",
    })
    run["prediction"]["sealed_hash"] = seal_hash(run)
    new_run.write_json(folder / "run.json", run)
    return run["prediction"]["sealed_hash"]


# --------------------------------------------------------------------------------------
# Every run: the clean streak and the outer loop's lock (O6)
# --------------------------------------------------------------------------------------

def all_runs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    clients = sorted(d for d in root.iterdir() if d.is_dir() and new_run.CLIENT_CODE.match(d.name))
    return [folder for client in clients for folder in run_folders(client)]


def dataset(run: dict) -> str:
    """A short name for the set of input files a run used."""
    hashes = input_hashes(run)
    if not hashes:
        return "no-inputs"
    return hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest()[:12]


def summary(root: Path, write: bool = True) -> tuple[list[str], bool, bool]:
    """(lines to print, every run valid, outer loop unlocked) for the whole run log."""
    cache: dict = {}
    reports = [check(folder, write, cache) for folder in all_runs(root)]
    finished = [r for r in reports if r.run is None or r.status in new_run.STATUSES]
    finished.sort(key=lambda r: (str((r.run or {}).get("finished_at") or (r.run or {}).get("started_at")), r.name))
    lines = []
    for r in reports:
        if not r.valid:
            lines += [f"{r.name}: [{rule}] {message}" for rule, message in r.problems]
    for r in finished + [r for r in reports if r not in finished]:
        if not r.valid:
            state = "INVALID"
        elif r.status is None:
            state = "draft"
        else:
            state = "clean" if r.clean else f"not clean ({', '.join(sorted({k for k, _ in r.alerts})) or r.status})"
        loop = (r.run or {}).get("loop") or {}
        lines.append(
            f"{r.name}  status {r.status or '-'}  {state}  dataset {dataset(r.run or {})}  "
            f"checker passes {loop.get('checker_passes')}  send-backs {loop.get('red_team_send_backs')}"
        )
    streak = []
    for r in reversed(finished):
        if not r.clean:
            break
        streak.append(r)
    datasets = {dataset(r.run) for r in streak}
    clients = {r.folder.parent.name for r in streak}
    unlocked = len(streak) >= CLEAN_RUNS and max(len(datasets), len(clients)) >= CLEAN_SPREAD
    lines.append(f"clean streak: {len(streak)} run(s) in a row, across {len(datasets)} dataset(s) and {len(clients)} client(s)")
    lines.append(
        f"outer loop: {'unlocked' if unlocked else 'locked'} "
        f"(needs {CLEAN_RUNS} clean runs in a row across at least {CLEAN_SPREAD} datasets or clients, O6)"
    )
    return lines, all(r.valid for r in reports), unlocked


# --------------------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a run folder of the run log (section 6.3).")
    parser.add_argument("folder", nargs="?", help="a run folder: runs/<client-code>/<YYYY-MM-DD>_<run-id>")
    parser.add_argument("--clean", action="store_true", help="exit 1 unless the run is clean")
    parser.add_argument("--all", nargs="?", const="runs", metavar="ROOT", help="check every run under ROOT (default: runs)")
    parser.add_argument("--tracked", action="store_true", help="fail if git tracks any file under runs/ or brands/")
    parser.add_argument("--seal", nargs=4, type=float, metavar=("VALUE", "LOW", "HIGH", "NAIVE"), help="seal the dollar prediction")
    parser.add_argument("--no-write", action="store_true", help="change nothing: no computed fields, no alerts")
    args = parser.parse_args(argv)

    if args.tracked:
        top = git_top(Path.cwd())
        if top is None:
            print("check_run: not inside a git work tree", file=sys.stderr)
            return 2
        files = tracked(top)
        for name in files:
            print(f"tracked: {name}")
        if files:
            print(f"FAIL  git tracks {len(files)} file(s) under runs/ or brands/: client data never goes into git")
            return 1
        print("OK    git tracks nothing under runs/ or brands/")
        return 0

    if args.all is not None:
        root = Path(args.all)
        if not root.is_dir():
            print(f"check_run: {root}: no such folder", file=sys.stderr)
            return 2
        lines, valid, _ = summary(root, not args.no_write)
        print("\n".join(lines))
        return 0 if valid else 1

    if not args.folder:
        parser.print_usage(sys.stderr)
        return 2
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"check_run: {folder}: no such run folder", file=sys.stderr)
        return 2
    if args.seal:
        try:
            sealed = seal(folder, *args.seal)
        except ValueError as err:
            print(f"check_run: {err}", file=sys.stderr)
            return 2
        print(f"sealed {folder}: {sealed}")
        return 0
    r = check(folder, not args.no_write)
    print("\n".join(report_lines(r, str(folder))))
    if not r.valid:
        return 1
    return 1 if args.clean and not r.clean else 0


if __name__ == "__main__":
    sys.exit(main())
