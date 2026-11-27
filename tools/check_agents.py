#!/usr/bin/env python3
"""Load check for the agent team (SUPPLY_VARIABILITY.md section 3.2).

Passes only if exactly the nine agent files exist in .claude/agents/, each has a
well-formed header whose `name:` equals its file name and a non-empty
`description:`, none still points at the old project path, each mentions the
shared brief, and the shared brief exists.

    python3 tools/check_agents.py        # nine OK lines, exit 0
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT / ".claude" / "agents"
CONTEXT = "docs/agents/CONTEXT.md"
OLD_PATH = "/mnt/project-files/agents/CONTEXT.md"

AGENTS = (
    "thiel-monopoly-strategist",
    "musk-first-principles-engineer",
    "factory-physicist",
    "stein-estimation-scientist",
    "feynman-red-team",
    "jobs-product-designer",
    "hormozi-offer-architect",
    "schwartz-copy-chief",
    "graham-first-customers",
)


def header(text: str) -> dict[str, str] | None:
    """The `key: value` pairs between the opening and closing `---`, or None."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    fields = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def problems(name: str, root: Path = ROOT) -> list[str]:
    path = root / ".claude" / "agents" / f"{name}.md"
    if not path.is_file():
        return ["file missing"]
    text = path.read_text(encoding="utf-8")
    found = []
    fields = header(text)
    if fields is None:
        found.append("header must open with --- on line 1 and close with ---")
    else:
        if fields.get("name") != name:
            found.append(f"name: is {fields.get('name')!r}, expected {name!r}")
        if not fields.get("description"):
            found.append("description: is missing or empty")
    if OLD_PATH in text:
        found.append(f"still contains {OLD_PATH}")
    if CONTEXT not in text:
        found.append(f"never mentions {CONTEXT}")
    return found


def main(root: Path = ROOT) -> int:
    failed = False
    for name in AGENTS:
        found = problems(name, root)
        if found:
            failed = True
            for p in found:
                print(f"FAIL {name}: {p}")
        else:
            print(f"OK   {name}")

    agent_dir = root / ".claude" / "agents"
    present = {p.name for p in agent_dir.iterdir()} if agent_dir.is_dir() else set()
    for extra in sorted(present - {f"{n}.md" for n in AGENTS}):
        failed = True
        print(f"FAIL .claude/agents/{extra}: not one of the nine agents")

    if not (root / CONTEXT).is_file():
        failed = True
        print(f"FAIL {CONTEXT}: file missing")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
