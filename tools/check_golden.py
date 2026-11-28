#!/usr/bin/env python3
"""Hold the golden set still (SUPPLY_VARIABILITY.md section 5.5).

A case is a folder under agents/golden/ with question.md, answer.md and meta.json. Each
answer must still pass tools/agent_check.py the way its meta.json says, and a red-team
answer must still give the verdict recorded there. Run it before keeping any change to an
agent file, docs/agents/CONTEXT.md, docs/agents/NUMBERS.md or the checker.

    python3 tools/check_golden.py              # one line per case, exit 0 when all hold
    python3 tools/check_golden.py <folder>     # another golden folder

Exit 1 when a case fails, 2 when there is no case to check. Passing shows the answers are
still labelled and shaped as accepted, never that they are true.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import agent_check

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "agents" / "golden"
FILES = ("question.md", "answer.md", "meta.json")
FIELDS = ("agent", "client", "numbers", "verdict", "data", "accepted")
DATA_KINDS = ("made-up", "public")
OPENERS = {
    "made-up": "Made-up data. Not a client. Not a result.",
    "public": "Public data. Not a client. Not a result.",
}


def cases(golden: Path = GOLDEN) -> list[Path]:
    """Every case folder, in name order."""
    if not golden.is_dir():
        return []
    return sorted(p for p in golden.iterdir() if p.is_dir() and not p.name.startswith("."))


def read_meta(case: Path) -> tuple[dict, list[str]]:
    """The case's meta.json and what is wrong with it."""
    try:
        meta = json.loads((case / "meta.json").read_text(encoding="utf-8"))
    except ValueError as err:
        return {}, [f"meta.json is not JSON: {err}"]
    if not isinstance(meta, dict):
        return {}, ["meta.json must hold one object"]
    found = [f"meta.json has no `{field}`" for field in FIELDS if field not in meta]
    if meta.get("agent") is not None and meta.get("agent") not in agent_check.AGENTS:
        found.append(f"meta.json names an agent that does not exist: {meta.get('agent')}")
    for field in ("client", "numbers"):
        if field in meta and not isinstance(meta[field], bool):
            found.append(f"meta.json `{field}` must be true or false")
    if meta.get("verdict") is not None and meta.get("verdict") not in agent_check.VERDICTS:
        found.append(f"meta.json `verdict` must be null or one of: {', '.join(agent_check.VERDICTS)}")
    if "data" in meta and meta["data"] not in DATA_KINDS:
        found.append(f"meta.json `data` is `{meta['data']}`: a golden case is made-up or public data, never a client's")
    if "accepted" in meta and not str(meta["accepted"] or "").strip():
        found.append("meta.json `accepted` must say who accepted the answer, or that nobody has yet")
    return meta, found


def says_what_it_is(text: str, kind: str) -> bool:
    """True when one of the first lines of `text` is the opener for its kind of data."""
    opener = OPENERS[kind]
    return any(line.strip() == opener for line in text.splitlines()[:6])


def problems(case: Path, register: agent_check.Register | None = None) -> list[str]:
    """What is wrong with one case. Empty when it holds."""
    missing = [f"{name} is missing" for name in FILES if not (case / name).is_file()]
    if missing:
        return missing
    meta, found = read_meta(case)
    if found:
        return found
    answer = (case / "answer.md").read_text(encoding="utf-8")
    question = (case / "question.md").read_text(encoding="utf-8")
    for name, text in (("question.md", question), ("answer.md", answer)):
        if not says_what_it_is(text, meta["data"]):
            found.append(f"{name} does not open by saying: {OPENERS[meta['data']]}")
    if meta["numbers"] and register is None:
        register = agent_check.load_register()
    failures = agent_check.check(
        answer, agent=meta["agent"], client=meta["client"], register=register if meta["numbers"] else None
    )
    found += [f"answer.md:{f.line}: [{f.rule}] {f.message}" for f in failures]
    verdict = agent_check.verdict(answer)
    if verdict != meta["verdict"]:
        found.append(f"the verdict is `{verdict}`, the accepted one is `{meta['verdict']}`")
    return found


def describe(case: Path) -> str:
    """How a case that holds is checked, for its OK line."""
    meta, _ = read_meta(case)
    parts = [meta.get("agent") or "no agent"]
    if meta.get("client"):
        parts.append("client text")
    if meta.get("numbers"):
        parts.append("numbers in the register")
    if meta.get("verdict"):
        parts.append(f"verdict {meta['verdict']}")
    parts.append(f"{meta.get('data')} data")
    return ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    golden = Path(args[0]) if args else GOLDEN
    found = cases(golden)
    if not found:
        print(f"FAIL  {golden}: no golden case to check")
        return 2
    bad = 0
    for case in found:
        try:
            wrong = problems(case)
        except ValueError as err:
            wrong = [str(err)]
        if wrong:
            bad += 1
            for line in wrong:
                print(f"FAIL  {case.name}: {line}")
        else:
            print(f"OK    {case.name}: holds ({describe(case)})")
    if bad:
        print(f"FAIL  {bad} of {len(found)} golden case(s) no longer hold: say so in the pull request")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
