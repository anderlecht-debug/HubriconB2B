#!/usr/bin/env python3
"""Create one run folder of the run log (SUPPLY_VARIABILITY.md sections 6.3 and 8.3, O12).

    python3 tools/new_run.py <client-code> --data {client,public,made-up} --question "<what was asked>"
                             [--input FILE ...] [--source "<where the files came from>"]
                             [--run-id ID] [--date YYYY-MM-DD] [--root runs]

Makes `runs/<client-code>/<YYYY-MM-DD>_<run-id>/` with every file section 6.3 names, prints
the folder's path and exits 0:

    run.json          the record: every field of the table in section 6.3, empty until filled
    inputs/           a copy of each --input file, renamed input-01, input-02, ...
    checker.txt       tools/agent_check.py output, one block per pass (its --log option)
    verdict.md        the red team's verdict table and ship / fix first / stop
    numbers.json      every number in the client view with its label and source (--json)
    disagreements.md  each disagreement: positions, evidence, who won and why
    client_view.md    exactly what the client saw
    outcome.json      filled in later: actual dollars, baseline, censored days

and `runs/ALERTS.md`, with its heading, when it is not there yet. Fill the folder in, then
run `python3 tools/check_run.py <folder>`.

The run log holds client data, so it lives outside git: `runs/` is in .gitignore, and
`python3 tools/check_run.py --tracked` fails if anything under it is tracked.

A client code is a neutral code, never a brand name: `c` and 3 to 6 digits for a client,
`t` and 3 to 6 digits for made-up or public test data. Input files are renamed on the way in
for the same reason. A file whose header has a column of customer personal data (an email,
a phone number, an address, a buyer's name) is refused: remove the column first (section 8.1).

A run on made-up or public data starts its client view with a line saying so. Made-up data
is never shown as a result.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import secrets
import shutil
import sys
from pathlib import Path

SCHEMA = 1
CLIENT_CODE = re.compile(r"^[ct][0-9]{3,6}$")
RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
RUN_FOLDER = re.compile(r"^([0-9]{4}-[0-9]{2}-[0-9]{2})_([a-z0-9][a-z0-9-]{0,31})$")
DATA_KINDS = ("client", "public", "made-up")
STATUSES = ("ok", "stuck", "failed")

FILES = ("run.json", "checker.txt", "verdict.md", "numbers.json", "disagreements.md", "client_view.md", "outcome.json")
INPUTS_DIR = "inputs"

# The first line of a client view built on data that is not a client's. check_run.py asks for it.
NOT_A_RESULT = {
    "made-up": "Made-up data. Not a client. Not a result.",
    "public": "Public data. Not a client. Not a result.",
}

OUTCOME = {"actual_dollars": None, "baseline_dollars": None, "vs_baseline": None, "censored_days": None, "graded_at": None}

ALERTS = "ALERTS.md"
ALERTS_HEADER = (
    "# Alerts\n\n"
    "One line per alert, oldest first: time (UTC) | run | kind | what happened.\n"
    "Written by tools/check_run.py. This file is outside git, like the rest of the run log.\n\n"
)

_PERSONAL = re.compile(
    r"e-?mail|phone|mobile|street|address|post(?:al)?[ _-]?code|zip|"
    r"(?:buyer|customer|recipient|shipping|billing|first|last|full)[ _-]?name",
    re.I,
)
_ISO_DATE = re.compile(r"(?<![0-9])([0-9]{4})-([0-9]{2})-([0-9]{2})(?![0-9])")
_TABLES = (".csv", ".tsv", ".txt")


def now() -> str:
    """The time now, in UTC, as it is written everywhere in the run log."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def read_text(path: Path, limit: int = 5_000_000) -> str | None:
    """The file as text, or None when it is not text. Only the first `limit` bytes are read."""
    with path.open("rb") as fh:
        raw = fh.read(limit)
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def header(path: Path) -> list[str]:
    """The column names of a delimited file. Empty for anything else."""
    if path.suffix.lower() not in _TABLES:
        return []
    text = read_text(path, 65536)
    if not text or not text.strip():
        return []
    first = text.splitlines()[0]
    delimiter = "\t" if first.count("\t") > first.count(",") else ","
    return [c.strip() for c in next(csv.reader([first], delimiter=delimiter))]


def personal_columns(path: Path) -> list[str]:
    """Columns whose name says they hold customer personal data."""
    return [c for c in header(path) if _PERSONAL.search(c)]


def describe(path: Path) -> tuple[int | None, list[str] | None]:
    """(rows, date range) of an input file. Rows leave out the header of a delimited file."""
    text = read_text(path)
    if text is None:
        return None, None
    lines = [line for line in text.splitlines() if line.strip()]
    rows = max(len(lines) - 1, 0) if path.suffix.lower() in (".csv", ".tsv") else len(lines)
    dates = []
    for y, m, d in _ISO_DATE.findall(text):
        try:
            dates.append(datetime.date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    return rows, ([min(dates), max(dates)] if dates else None)


def empty_run(client_code: str, run_id: str, data_kind: str, question: str, started_at: str) -> dict:
    """A run.json with every field of the table in section 6.3, nothing filled in."""
    return {
        "schema": SCHEMA,
        "client_code": client_code,
        "run_id": run_id,
        "data_kind": data_kind,
        "question": question,
        "started_at": started_at,
        "finished_at": None,
        "agents_run": [],
        "inputs": [],
        "conclusions": {},
        "numbers": {"file": "numbers.json", "counts": None},
        "disagreements": {"file": "disagreements.md", "items": []},
        "cost": {
            "tokens_total": None,
            "tokens_checking": None,
            "share_checking": None,
            "wall_time": None,
            "cycle_time_upload_to_first_dollar": None,
            "note": "",
        },
        "diff_since_last_run": None,
        "prediction": {"sealed_hash": None, "sealed_at": None, "value": None, "range": None, "naive_baseline": None, "why_none": ""},
        "outcome": dict(OUTCOME),
        "overrides": [],
        "loop": {"checker_passes": None, "red_team_send_backs": 0},
        "status": None,
    }


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def alerts_file(root: Path) -> Path:
    """The run log's alert file, created with its heading when it is not there yet."""
    path = root / ALERTS
    if not path.is_file():
        root.mkdir(parents=True, exist_ok=True)
        path.write_text(ALERTS_HEADER, encoding="utf-8")
    return path


def create(
    root: Path,
    client_code: str,
    data_kind: str,
    question: str,
    inputs: list[Path] | None = None,
    source: str = "",
    run_id: str | None = None,
    date: str | None = None,
    started_at: str | None = None,
) -> Path:
    """Create the run folder and return its path. Raises ValueError on anything it refuses."""
    inputs = inputs or []
    if not CLIENT_CODE.match(client_code):
        raise ValueError(f"client code {client_code!r} is not a neutral code: use c or t and 3 to 6 digits, e.g. c001 or t001")
    if data_kind not in DATA_KINDS:
        raise ValueError(f"--data must be one of: {', '.join(DATA_KINDS)}")
    if (client_code[0] == "c") != (data_kind == "client"):
        raise ValueError("a `c` code is for client data, a `t` code is for made-up or public data")
    if not question.strip():
        raise ValueError("the question is empty: say what was asked")
    run_id = run_id or secrets.token_hex(4)
    if not RUN_ID.match(run_id):
        raise ValueError(f"run id {run_id!r}: use lower-case letters, digits and hyphens, at most 32")
    started_at = started_at or now()
    date = date or started_at[:10]
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        raise ValueError(f"date {date!r} is not YYYY-MM-DD") from None
    if inputs and not source.strip():
        raise ValueError("--source is missing: say where the input files came from")
    for path in inputs:
        if not path.is_file():
            raise ValueError(f"{path}: no such input file")
        personal = personal_columns(path)
        if personal:
            raise ValueError(f"{path}: columns that look like customer personal data ({', '.join(personal)}). Remove them first (section 8.1)")

    folder = root / client_code / f"{date}_{run_id}"
    if folder.exists():
        raise ValueError(f"{folder} already exists")
    (folder / INPUTS_DIR).mkdir(parents=True)
    alerts_file(root)
    run = empty_run(client_code, run_id, data_kind, question.strip(), started_at)
    for n, path in enumerate(inputs, 1):
        name = f"input-{n:02d}{path.suffix.lower()}"
        shutil.copyfile(path, folder / INPUTS_DIR / name)
        rows, date_range = describe(folder / INPUTS_DIR / name)
        run["inputs"].append({
            "file": name,
            "hash": sha256(folder / INPUTS_DIR / name),
            "rows": rows,
            "date_range": date_range,
            "source": source.strip(),
        })
    write_json(folder / "run.json", run)
    write_json(folder / "numbers.json", [])
    write_json(folder / "outcome.json", dict(OUTCOME))
    for name in ("checker.txt", "verdict.md", "disagreements.md"):
        (folder / name).write_text("", encoding="utf-8")
    label = NOT_A_RESULT.get(data_kind)
    (folder / "client_view.md").write_text(f"{label}\n\n" if label else "", encoding="utf-8")
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create one run folder of the run log (section 6.3).")
    parser.add_argument("client_code", help="a neutral code: c001 for a client, t001 for test data")
    parser.add_argument("--data", required=True, choices=DATA_KINDS, help="what kind of data the run uses")
    parser.add_argument("--question", required=True, help="what was asked")
    parser.add_argument("--input", action="append", default=[], help="a file the run uses (repeat for more)")
    parser.add_argument("--source", default="", help="where the input files came from")
    parser.add_argument("--run-id", help="default: 8 random hex characters")
    parser.add_argument("--date", help="default: today, UTC")
    parser.add_argument("--root", default="runs", help="the run log's folder (default: runs)")
    args = parser.parse_args(argv)
    try:
        folder = create(
            Path(args.root), args.client_code, args.data, args.question,
            [Path(p) for p in args.input], args.source, args.run_id, args.date,
        )
    except ValueError as err:
        print(f"new_run: {err}", file=sys.stderr)
        return 2
    print(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
