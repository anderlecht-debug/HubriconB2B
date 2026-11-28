#!/usr/bin/env python3
"""The checker for agent output and client text (SUPPLY_VARIABILITY.md section 3.3).

    python3 tools/agent_check.py <file> [--agent <name>] [--client]

Prints one line per failure, `<file>:<line>: [<rule>] <what is wrong>`, and exits 0 only
when there are none. Exit 1 means failures, exit 2 means the command itself was wrong.

Passing shows that a claim is labelled, never that it is true. Truth stays with the
feynman-red-team agent and the proof scripts. A clean run here is the floor, not the verdict.

The rules, one per row of the table in section 3.3:

    label        a line with a number carries [measured], [sourced: <source>] or [inference]
    unit         a number has a unit or %, unless it is a date, an ID, or on a line marked [count]
    quote        text in quotation marks over 6 words is followed by a (source with a year)
    next-action  the last section is headed `Next action` and holds one item
    rop          a reorder point shows its service level and μd, μL, σd, σL, or a link to them
    lead-time    a lead time given as one number is [measured] or says "assumed"
    jargon       with --client, the first line has no sigma, σ, z-score, ROP or μ
    sections     with --agent, the output has that agent's required sections
    baseline     a claimed % improvement names `baseline:`

What counts as a number: digits that are not a date, a year, a time, an ID (O12, SKU-104,
a hash, a version), a reference (section 3.3, step 5, #12), a path, a URL, an ordinal, a list
or heading number, or code. Fenced code and inline code are skipped, except a bare number in
backticks, which is still a number. Labels are read per line, as the brief words the rule.

Two more options, for checking part of a file or one rule:

    --section 1.3     check only the section whose heading starts with 1.3
    --only label,unit run only the named rules

And two for the run log (section 6.3), which keeps the evidence of every pass:

    --log checker.txt   append this pass, with its exit code, to the run's checker.txt
    --json numbers.json write every number in the file with its label and source
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

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

RULES = (
    "label",
    "unit",
    "quote",
    "next-action",
    "rop",
    "lead-time",
    "jargon",
    "sections",
    "baseline",
)

# Rules that judge the whole document, so they are skipped when only one section is checked.
WHOLE_DOCUMENT_RULES = ("next-action", "jargon", "sections")

VERDICTS = ("ship", "fix first", "stop")
VERDICT_STATUSES = ("proven", "sourced", "inference", "unsupported", "wrong")


class Failure(NamedTuple):
    line: int
    rule: str
    message: str


class Number(NamedTuple):
    start: int
    end: int
    text: str
    has_unit: bool
    is_time: bool
    is_percent: bool


# --------------------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------------------

LABEL = re.compile(r"\[(measured|inference|count|sourced)(?::([^\]]*))?\]", re.I)


def labels(line: str) -> list[tuple[int, str, str]]:
    """Every label on a line as (position, name, source). Source is '' unless sourced."""
    return [(m.start(), m.group(1).lower(), (m.group(2) or "").strip()) for m in LABEL.finditer(line)]


def provenance(line: str) -> list[str]:
    """The labels that say where a number came from. [count] is about units, so it is left out."""
    return [name for _, name, source in labels(line) if name != "count" and (name != "sourced" or source)]


# --------------------------------------------------------------------------------------
# What is not a number: masked out before numbers are looked for
# --------------------------------------------------------------------------------------

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)
_ORD = r"(?:st|nd|rd|th)?"
_REF = (
    r"(?:sections?|sec\.|steps?|items?|appendix|chapters?|ch\.|pages?|pp?\.|figures?|fig\.|tables?|"
    r"rules?|questions?|tests?|rounds?|requirements?|lines?|rows?|seeds?|stages?|parts?|phases?|"
    r"options?|notes?|lessons?|edition|version|vol\.|no\.|RFC|PRs?|issues?)"
)
_REF_NUM = r"[0-9]+(?:\.[0-9]+)*[a-z]?"

_UNIT_TIME = (
    "ms", "s", "sec", "secs", "second", "seconds", "min", "mins", "minute", "minutes",
    "h", "hr", "hrs", "hour", "hours", "day", "days", "week", "weeks", "wk", "wks",
    "month", "months", "mo", "quarter", "quarters", "year", "years", "yr", "yrs",
)
_UNIT_OTHER = (
    "dollar", "dollars", "cent", "cents", "usd", "eur", "gbp",
    "percent", "pp", "bps", "point", "points", "times", "x",
    "kg", "g", "lb", "lbs", "oz", "ton", "tons", "tonne", "tonnes",
    "km", "m", "cm", "mm", "ft", "mile", "miles", "litre", "litres", "liter", "liters", "ml",
    "cbm", "teu", "unit", "units", "token", "tokens", "kb", "mb", "gb",
)
_UNITS = "|".join(sorted(_UNIT_TIME + _UNIT_OTHER, key=len, reverse=True))
_MAGNITUDE = r"(?:hundred|thousand|million|billion|trillion)"

MASKS = tuple(
    re.compile(p, flags)
    for p, flags in (
        # URLs and the target of a markdown link
        (r"https?://\S+", 0),
        (r"\]\([^)\s]*\)", 0),
        # Paths: a file with an extension, or a folder written with its trailing slash
        (r"(?:[\w.~-]*/)+[\w.-]+\.[A-Za-z]\w*", 0),
        (r"(?:[\w.~-]+/)+(?=[\s,.;:)`'\"]|$)", 0),
        # Dates and times
        (r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2})?(?:Z|[+-][0-9]{2}:?[0-9]{2})?)?", 0),
        (r"\b[0-9]{1,2}" + _ORD + r"(?:\s*(?:to|and|or|-|–)\s*[0-9]{1,2}" + _ORD + r")?\s+" + _MONTH + r"(?:,?\s+[0-9]{4})?(?![0-9])", 0),
        (r"\b" + _MONTH + r"\s+[0-9]{1,2}" + _ORD + r"(?:,\s*[0-9]{4})?(?![0-9A-Za-z])", 0),
        (r"\b" + _MONTH + r",?\s+[0-9]{4}(?![0-9])", 0),
        (r"\b[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}\b", 0),
        (r"\b[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?(?![0-9])(?:\s?(?:am|pm|AM|PM|UTC)\b)?", 0),
        # IDs: O12, T1, sim2, SKU-104, a commit hash, a version, #12, a footnote
        (r"\b[A-Za-z_]\w*[0-9]\w*", 0),
        (r"\b[A-Z][A-Z0-9]*-[0-9]+\b", 0),
        (r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,}\b", 0),
        (r"\b[0-9]+(?:\.[0-9]+){2,}\b", 0),
        (r"#[0-9]+\b", 0),
        (r"\[\^?[0-9]+\]", 0),
        # References: section 3.3, steps 1 to 8, seeds 101/202/303 and 404/505/606, §10
        (r"\b" + _REF + r"\s*" + _REF_NUM + r"(?:\s*(?:,|/|to|and|or|–|-|&)\s*" + _REF_NUM + r"(?![0-9]))*", re.I),
        (r"§\s*" + _REF_NUM, 0),
        # Ordinals: 3rd, 21st
        (r"\b[0-9]+(?:st|nd|rd|th)\b", 0),
        # Years, unless a unit follows (2000 units is a quantity)
        (r"(?<![0-9,.$€£])(?:19|20)[0-9]{2}(?![0-9]|,[0-9]{3}|\.[0-9]|%|\s?-?(?:" + _UNITS + r")\b)", re.I),
    )
)

_LINE_PREFIX = (
    re.compile(r"^(\s{0,3}#{1,6}\s+)([0-9]+(?:\.[0-9]+)*[.)]?)(?=\s)"),  # ## 1.3 Heading
    re.compile(r"^(\s*(?:>\s*)*)([0-9]+[.)])(?=\s)"),  # 1. list item
)

_INLINE_CODE = re.compile(r"(`+)(.+?)\1")
_BARE_NUMBER = re.compile(r"[-+±~]?[$€£]?[0-9][0-9,]*(?:\.[0-9]+)?\s?(?:%|[A-Za-z/ -]{0,20})")
_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def _blank(m: "re.Match[str]") -> str:
    return " " * (m.end() - m.start())


def _code(m: "re.Match[str]") -> str:
    inner = m.group(2)
    if _BARE_NUMBER.fullmatch(inner.strip()):
        return " " * len(m.group(1)) + inner + " " * len(m.group(1))
    return _blank(m)


def mask_line(line: str) -> str:
    """The line with everything that is not a number blanked out, same length as the line."""
    s = _INLINE_CODE.sub(_code, line)
    s = LABEL.sub(_blank, s)
    for rx in _LINE_PREFIX:
        s = rx.sub(lambda m: m.group(1) + " " * len(m.group(2)), s)
    for rx in MASKS:
        s = rx.sub(_blank, s)
    return s


def visible_lines(text: str) -> list[str]:
    """The lines of a document with front matter, fenced code and HTML comments blanked."""
    text = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    lines = text.split("\n")
    out = list(lines)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                for j in range(i + 1):
                    out[j] = ""
                break
    fence = None
    for i, line in enumerate(out):
        m = _FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                out[i] = ""
        else:
            closes = m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip(fence[0] + " \t")
            out[i] = ""
            if closes:
                fence = None
    return out


# --------------------------------------------------------------------------------------
# Numbers and their units
# --------------------------------------------------------------------------------------

_NUMBER = re.compile(
    r"(?<![\w.,])(?P<cur>[$€£])?(?P<num>[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?P<dec>\.[0-9]+)?"
    r"(?P<suffix>%|[A-Za-zµμ×]+)?"
)
_GLUED_UNITS = {"x", "×", "s", "ms", "h", "hr", "hrs", "d", "min", "kg", "g", "lb", "lbs", "oz", "km", "cm", "mm", "m", "ft", "gb", "mb", "kb", "pp", "bps"}
_GLUED_TIME = {"s", "ms", "h", "hr", "hrs", "d", "min"}
_GLUED_MAGNITUDE = {"k", "K", "M", "B", "bn", "MM"}
_UNIT_AFTER = re.compile(
    r"(?:[ \t]?-?|/)(?:" + _MAGNITUDE + r"[ \t]+)?(?:(?:calendar|business|working)[ \t]+)?(?P<unit>" + _UNITS + r")\b",
    re.I,
)
_RATIO_AFTER = re.compile(r"[\s-]*(?:out[\s-]+of|of|in)[\s-]+[$€£]?[0-9]|/[0-9]", re.I)
_RATIO_BEFORE = re.compile(r"(?:[0-9%][\s-]*(?:out[\s-]+of|of|in)[\s-]+|[0-9]/)$", re.I)
_CURRENCY_BEFORE = re.compile(r"\b(?:USD|EUR|GBP)\s?$")
_DIMENSIONLESS_BEFORE = re.compile(r"(?:^|[\s(])(?:z|p|r|ρ|R²|z[- ]score)\s*(?:=|≈|of|is|:)\s*$")
_RANGE_BETWEEN = re.compile(r"\s*(?:to|and|or|–|—|-|,|/|,\s*(?:and|or))\s*[<>~≈±]?\s*$", re.I)
_SPREAD_BEFORE = re.compile(r"(?:±|\+/-|\+-|give or take(?: about)?)\s*$", re.I)
_TIME_WORDS = set(_UNIT_TIME)


def find_numbers(masked: str) -> list[Number]:
    """The numbers on a masked line, each with whether it has a unit."""
    found = []
    for m in _NUMBER.finditer(masked):
        suffix = m.group("suffix") or ""
        if suffix and suffix != "%" and suffix.lower() not in _GLUED_UNITS and suffix not in _GLUED_MAGNITUDE:
            continue  # 3PL, 2FA: a name, not a quantity
        before, after = masked[: m.start()], masked[m.end() :]
        unit = bool(m.group("cur")) or bool(_CURRENCY_BEFORE.search(before))
        is_time = False
        percent = suffix == "%"
        if suffix == "%" or suffix.lower() in _GLUED_UNITS:
            unit = True
            is_time = suffix.lower() in _GLUED_TIME
        ua = _UNIT_AFTER.match(after)
        if ua:
            unit = True
            word = ua.group("unit").lower()
            is_time = is_time or word in _TIME_WORDS
            percent = percent or word == "percent"
        if _RATIO_AFTER.match(after) or _RATIO_BEFORE.search(before) or _DIMENSIONLESS_BEFORE.search(before):
            unit = True
        text = (m.group("cur") or "") + m.group("num") + (m.group("dec") or "") + suffix
        found.append(Number(m.start(), m.end(), text, unit, is_time, percent))

    # A range or a list takes the unit of its last member: 36 to 70 days, 13, 14 and 16 days.
    for i in range(len(found) - 2, -1, -1):
        a, b = found[i], found[i + 1]
        if not a.has_unit and b.has_unit and _RANGE_BETWEEN.fullmatch(masked[a.end : b.start]):
            found[i] = a._replace(has_unit=True, is_time=b.is_time, is_percent=b.is_percent)
    for i in range(1, len(found)):
        a, b = found[i - 1], found[i]
        if b.has_unit or not a.has_unit:
            continue
        between = masked[a.end : b.start]
        # 40 units a day ±15, $10 to 20
        if _SPREAD_BEFORE.search(masked[: b.start]) or (a.text[:1] in "$€£" and _RANGE_BETWEEN.fullmatch(between)):
            found[i] = b._replace(has_unit=True, is_time=a.is_time)
    # 3 to 1 is a ratio
    for i in range(len(found) - 1):
        a, b = found[i], found[i + 1]
        if not a.has_unit and not b.has_unit and b.text == "1" and re.fullmatch(r"\s+to\s+", masked[a.end : b.start]):
            found[i] = a._replace(has_unit=True)
            found[i + 1] = b._replace(has_unit=True)
    return found


# --------------------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------------------

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")


class Doc:
    """A document split into lines, with code blanked and the numbers on each line found."""

    def __init__(self, text: str):
        self.raw = text.split("\n")
        self.lines = visible_lines(text)
        self.masked = [mask_line(line) for line in self.lines]
        self.numbers = [find_numbers(line) for line in self.masked]
        self.active = [True] * len(self.lines)

    def headings(self) -> list[tuple[int, int, str]]:
        """(line index, level, title) for every heading outside code."""
        out = []
        for i, line in enumerate(self.lines):
            m = _HEADING.match(line)
            if m:
                out.append((i, len(m.group(1)), _plain(m.group(2))))
        return out

    def restrict(self, prefix: str) -> bool:
        """Keep only the section whose heading starts with `prefix`. False if there is none."""
        heads = self.headings()
        for n, (i, level, title) in enumerate(heads):
            if title == prefix or title.startswith((prefix + " ", prefix + ".", prefix + ":")):
                end = len(self.lines)
                for j, other_level, _ in heads[n + 1 :]:
                    if other_level <= level:
                        end = j
                        break
                self.active = [i <= k < end for k in range(len(self.lines))]
                return True
        return False

    def tables(self) -> list[list[int]]:
        """Each table as the list of its line indexes, header row first."""
        blocks, block = [], []
        for i, line in enumerate(self.lines):
            if line.strip().startswith("|"):
                block.append(i)
            elif block:
                blocks.append(block)
                block = []
        if block:
            blocks.append(block)
        return [b for b in blocks if len(b) >= 2]


def _plain(title: str) -> str:
    """A heading without its emphasis marks or trailing colon."""
    return re.sub(r"[*_`]", "", title).strip().rstrip(":").strip()


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


# --------------------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------------------


def rule_label(doc: Doc, **_) -> list[Failure]:
    out = []
    for i, nums in enumerate(doc.numbers):
        if not nums or not doc.active[i]:
            continue
        for _, name, source in labels(doc.lines[i]):
            if name == "sourced" and not source:
                out.append(Failure(i + 1, "label", "[sourced] names no source: write [sourced: <source>]"))
        if not provenance(doc.lines[i]):
            listed = "; ".join(n.text for n in nums)
            out.append(Failure(i + 1, "label", f"no [measured], [sourced: <source>] or [inference] label on: {listed}"))
    return out


def rule_unit(doc: Doc, **_) -> list[Failure]:
    out = []
    for i, nums in enumerate(doc.numbers):
        if not nums or not doc.active[i]:
            continue
        if any(name == "count" for _, name, _ in labels(doc.lines[i])):
            continue
        bare = [n.text for n in nums if not n.has_unit]
        if bare:
            out.append(Failure(i + 1, "unit", f"no unit or % on: {'; '.join(bare)} (give the unit, or mark the line [count])"))
    return out


_YEAR = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")
_SOURCE_AFTER = re.compile(r"[\s.,;:!?*_)\]]*\(([^()]*)\)")


def _quotes(doc: Doc) -> list[tuple[int, str, str]]:
    """Every quotation as (line index, quoted text, the text after it in the same paragraph)."""
    found = []
    para: list[int] = []
    for i in range(len(doc.lines) + 1):
        line = doc.lines[i] if i < len(doc.lines) else ""
        if line.strip():
            para.append(i)
            continue
        if para:
            parts = [_INLINE_CODE.sub(_blank, doc.lines[k]) for k in para]
            text = "\n".join(parts)
            starts, pos = [], 0
            for part in parts:
                starts.append(pos)
                pos += len(part) + 1
            open_at = None
            for at, ch in enumerate(text):
                if ch == "“" or (ch == '"' and open_at is None):
                    if ch == '"' and at > 0 and text[at - 1].isdigit():
                        continue  # an inch mark
                    open_at = at
                elif ch in '"”' and open_at is not None:
                    line_index = para[max(n for n, s in enumerate(starts) if s <= open_at)]
                    found.append((line_index, text[open_at + 1 : at], text[at + 1 :]))
                    open_at = None
            para = []
    return found


def rule_quote(doc: Doc, **_) -> list[Failure]:
    out = []
    for i, quoted, after in _quotes(doc):
        if not doc.active[i]:
            continue
        words = re.findall(r"[\w'’$%-]+(?:[.,][0-9]+)*", quoted)
        if len(words) <= 6:
            continue
        m = _SOURCE_AFTER.match(after)
        if not m or not _YEAR.search(m.group(1)):
            start = " ".join(words[:4])
            out.append(Failure(i + 1, "quote", f'the quote starting "{start} ..." is not followed by a (source with a year)'))
    return out


_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|[0-9]+[.)])\s+\S")


def rule_next_action(doc: Doc, **_) -> list[Failure]:
    heads = doc.headings()
    last_line = max(len(doc.lines), 1)
    if not heads:
        return [Failure(last_line, "next-action", "no `Next action` section: the last section must be headed Next action")]
    i, _, title = heads[-1]
    title = re.sub(r"^[0-9.]+\s+", "", title)
    if title.rstrip(".").lower() != "next action":
        return [Failure(i + 1, "next-action", f"the last section is headed `{title}`, not `Next action`")]
    body = doc.lines[i + 1 :]
    items = [m for m in (_LIST_ITEM.match(line) for line in body) if m]
    if items:
        top = min(len(m.group(1)) for m in items)
        count = sum(1 for m in items if len(m.group(1)) == top)
    else:
        count = sum(1 for k, line in enumerate(body) if line.strip() and (k == 0 or not body[k - 1].strip()))
    if count != 1:
        return [Failure(i + 1, "next-action", f"`Next action` holds {count} items, it must hold one")]
    return []


_ROP = re.compile(r"\breorder[ -]points?\b|\bROPs?\b")
_ROP_I = re.compile(r"\breorder[ -]points?\b", re.I)
_SERVICE = re.compile(r"service[ -]level|%\s+(?:cycle[ -])?service|\bz\s*=", re.I)
_INPUTS = (
    ("μd", re.compile(r"(?:μ|µ|mu)_?d(?![A-Za-z])")),
    ("μL", re.compile(r"(?:μ|µ|mu)_?[Ll](?![A-Za-z])")),
    ("σd", re.compile(r"(?:σ|sigma)_?d(?![A-Za-z])")),
    ("σL", re.compile(r"(?:σ|sigma)_?[Ll](?![A-Za-z])")),
)
_LINK = re.compile(r"\]\([^)\s]+\)|https?://\S+")
_SENTENCE_END = re.compile(r"[.!?](?:\s+|$)")


def _mentions_rop(text: str) -> bool:
    return bool(_ROP.search(text) or _ROP_I.search(text))


def _reports_rop(line: str, masked: str, numbers: list[Number]) -> bool:
    """True when a sentence on the line names a reorder point and gives a number."""
    start = 0
    for m in list(_SENTENCE_END.finditer(masked)) + [None]:
        end = m.start() if m else len(masked)
        if _mentions_rop(line[start:end]) and any(start <= n.start < end for n in numbers):
            return True
        start = m.end() if m else end
    return False


def _rop_missing(text: str) -> list[str]:
    """What a reorder point on this text still has to state. Empty when nothing."""
    if _LINK.search(text):
        return []
    missing = [] if _SERVICE.search(text) else ["the service level"]
    missing += [name for name, rx in _INPUTS if not rx.search(text)]
    return missing


def rule_rop(doc: Doc, **_) -> list[Failure]:
    out = []
    in_checked_table = set()
    for block in doc.tables():
        header = doc.lines[block[0]]
        if _mentions_rop(header) and not doc.numbers[block[0]]:
            in_checked_table.update(block)
            if not doc.active[block[0]]:
                continue
            missing = _rop_missing("\n".join(doc.lines[k] for k in block))
            if missing:
                out.append(Failure(block[0] + 1, "rop", "this table gives reorder points without " + ", ".join(missing) + " (state them, or link to them)"))
    for i, line in enumerate(doc.lines):
        if i in in_checked_table or not doc.active[i] or not _reports_rop(line, doc.masked[i], doc.numbers[i]):
            continue
        missing = _rop_missing(line)
        if missing:
            out.append(Failure(i + 1, "rop", "a reorder point without " + ", ".join(missing) + " (state them on the line, or link to them)"))
    return out


_LEAD_TIME = re.compile(r"\blead[ -]times?\b", re.I)
_ASSUMED = re.compile(r"\bassum", re.I)


def _is_measured(text: str) -> bool:
    return any(name == "measured" for _, name, _ in labels(text))


def rule_lead_time(doc: Doc, **_) -> list[Failure]:
    out = []
    for block in doc.tables():
        header = doc.lines[block[0]]
        if not doc.active[block[0]] or not _LEAD_TIME.search(header) or doc.numbers[block[0]]:
            continue
        text = "\n".join(doc.lines[k] for k in block)
        if not _is_measured(text) and not _ASSUMED.search(text):
            out.append(Failure(block[0] + 1, "lead-time", "this table gives lead times that are neither [measured] nor said to be assumed"))
    for i, line in enumerate(doc.lines):
        nums = doc.numbers[i]
        if not doc.active[i] or not nums or not _LEAD_TIME.search(line):
            continue
        timed = [n for n in nums if n.is_time]
        single = len(timed) == 1 or (not timed and len(nums) == 1)
        if single and not _is_measured(line) and not _ASSUMED.search(line):
            value = (timed or nums)[0].text
            out.append(Failure(i + 1, "lead-time", f"a lead time given as one number ({value}) with no [measured] label must say it is assumed"))
    return out


_JARGON = (
    ("sigma", re.compile(r"sigma", re.I)),
    ("σ", re.compile(r"σ")),
    ("z-score", re.compile(r"z[- ]score", re.I)),
    ("ROP", re.compile(r"\bROP\b")),
    ("μ", re.compile(r"[μµ]")),
)


def rule_jargon(doc: Doc, client: bool = False, **_) -> list[Failure]:
    if not client:
        return []
    for i, line in enumerate(doc.lines):
        if line.strip():
            hits = [name for name, rx in _JARGON if rx.search(doc.raw[i])]
            if hits:
                return [Failure(i + 1, "jargon", "the first line of client text uses " + ", ".join(hits))]
            return []
    return []


def _heading(*alternatives: str) -> tuple[str, tuple[str, ...]]:
    return ("heading", alternatives)


def _table(*columns: str) -> tuple[str, tuple[str, ...]]:
    return ("table", columns)


# What each agent's "Output" section promises. A heading matches when it contains any of the
# alternatives; a table matches when its header row has a column for each name (a|b means either).
REQUIRED = {
    "thiel-monopoly-strategist": (
        _heading("secret"), _heading("seven questions", "seven-question", "scorecard"), _heading("10x"),
        _heading("first market"), _heading("moat"), _heading("threat"), _heading("kill list"), _heading("grade"),
    ),
    "musk-first-principles-engineer": (
        _heading("truths"), _heading("limit"), _heading("gap"), _heading("deleted"), _heading("mechanism"),
        _heading("test"), _heading("cycle time", "cycle-time"), _heading("grade"),
    ),
    "factory-physicist": (
        _table("variance", "buffer", "lever", "saving"), _heading("formula", "inputs"),
        _heading("plain reading", "plain-language", "plain language", "plain words"),
    ),
    "stein-estimation-scientist": (
        _heading("model"), _heading("assumptions"), _heading("estimator"), _heading("proof", "backtest"),
        _heading("pool size", "pool-size"), _heading("dollar"), _heading("failure modes"),
    ),
    "feynman-red-team": (_table("claim", "status", "problem", "fix|test"), ("verdict", ())),
    "jobs-product-designer": (
        _heading("customer moment", "customer's moment"), _heading("one answer", "single answer"),
        _heading("ten-second", "ten second", "10-second"), _heading("one-minute", "one minute", "1-minute"),
        _heading("full math"), _heading("removed"), _heading("test"), _heading("grade"),
    ),
    "hormozi-offer-architect": (
        _heading("offer"), _heading("price"), _heading("guarantee"), _heading("proof"),
        _heading("value equation", "value-equation"), _heading("lead plan"), _heading("grade"),
    ),
    "schwartz-copy-chief": (
        _heading("copy"), _heading("headline"), _heading("awareness"),
        _heading("claim-source", "claim source", "claims and sources"),
    ),
    "graham-first-customers": (_heading("weekly plan"), _heading("call script", "script")),
}

_VERDICT_LINE = re.compile(r"^[\s>*_#-]*(?:overall\s+)?verdict[\s*_:.-]*(ship|fix first|stop)[\s*_.]*$", re.I)


def verdict(text: str) -> str | None:
    """The red team's overall verdict, `ship`, `fix first` or `stop`. None unless exactly one is given."""
    found = [m.group(1).lower() for m in (_VERDICT_LINE.match(line) for line in visible_lines(text)) if m]
    return found[0] if len(found) == 1 else None


def _find_table(doc: Doc, columns: tuple[str, ...]) -> list[int] | None:
    for block in doc.tables():
        header = [c.lower() for c in _cells(doc.lines[block[0]])]
        if all(any(alt in cell for cell in header for alt in col.split("|")) for col in columns):
            return block
    return None


def rule_sections(doc: Doc, agent: str | None = None, **_) -> list[Failure]:
    if not agent:
        return []
    out = []
    last_line = max(len(doc.lines), 1)
    titles = [title.lower() for _, _, title in doc.headings()]
    for kind, wanted in REQUIRED[agent]:
        if kind == "heading":
            if not any(alt in title for title in titles for alt in wanted):
                out.append(Failure(last_line, "sections", f"{agent} output has no section headed `{wanted[0]}`"))
        elif kind == "table":
            block = _find_table(doc, wanted)
            names = ", ".join(c.replace("|", " or ") for c in wanted)
            if block is None:
                out.append(Failure(last_line, "sections", f"{agent} output has no table with the columns: {names}"))
            elif agent == "feynman-red-team":
                out += _verdict_statuses(doc, block)
        elif kind == "verdict":
            if verdict("\n".join(doc.lines)) is None:
                out.append(Failure(last_line, "sections", "no single verdict line: write `Verdict: ship`, `Verdict: fix first` or `Verdict: stop`"))
    return out


def _verdict_statuses(doc: Doc, block: list[int]) -> list[Failure]:
    """Each row of the red team's table has a status from its own list."""
    header = [c.lower() for c in _cells(doc.lines[block[0]])]
    col = next(n for n, cell in enumerate(header) if "status" in cell)
    out = []
    for i in block[1:]:
        cells = _cells(doc.lines[i])
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c) or col >= len(cells):
            continue
        status = _plain(cells[col]).lower()
        if status not in VERDICT_STATUSES:
            out.append(Failure(i + 1, "sections", f"status `{cells[col]}` is not one of: {', '.join(VERDICT_STATUSES)}"))
    return out


_GAIN_WORD = re.compile(
    r"\b(?:improv\w*|gain\w*|reduc\w*|cut|cuts|cutting|fell|drop\w*|lift\w*|rais\w*|rose|boost\w*|"
    r"sav(?:e|es|ed|ing|ings)|beat\w*|grew|grow\w*|shr[iu]nk\w*|decreas\w*|increas\w*|uplift)\b",
    re.I,
)
_GAIN_AFTER = re.compile(r"\s*(?:percent\s+)?(?:more|less|fewer|better|lower|higher|faster|cheaper)\b", re.I)
_BASELINE = re.compile(r"\bbaseline\s*:", re.I)


def rule_baseline(doc: Doc, **_) -> list[Failure]:
    out = []
    for i, nums in enumerate(doc.numbers):
        percents = [n for n in nums if n.is_percent]
        if not percents or not doc.active[i]:
            continue
        line = doc.lines[i]
        claims = _GAIN_WORD.search(line) or any(_GAIN_AFTER.match(doc.masked[i][n.end :]) for n in percents)
        if claims and not _BASELINE.search(line):
            out.append(Failure(i + 1, "baseline", f"a % improvement ({percents[0].text}) with no `baseline:` named on the line"))
    return out


RULE_FUNCTIONS = {
    "label": rule_label,
    "unit": rule_unit,
    "quote": rule_quote,
    "next-action": rule_next_action,
    "rop": rule_rop,
    "lead-time": rule_lead_time,
    "jargon": rule_jargon,
    "sections": rule_sections,
    "baseline": rule_baseline,
}


def check(
    text: str,
    agent: str | None = None,
    client: bool = False,
    section: str | None = None,
    only: tuple[str, ...] | None = None,
) -> list[Failure]:
    """Every failure in `text`, in line order.

    Client text is not an agent note, so with `client` the `Next action` section is asked for
    only when an agent is named as well.
    """
    doc = Doc(text)
    names = [r for r in RULES if only is None or r in only]
    if section is not None:
        if not doc.restrict(section):
            raise ValueError(f"no section whose heading starts with {section!r}")
        names = [r for r in names if r not in WHOLE_DOCUMENT_RULES]
    if client and not agent:
        names = [r for r in names if r != "next-action"]
    failures = []
    for name in names:
        failures += RULE_FUNCTIONS[name](doc, agent=agent, client=client)
    return sorted(failures, key=lambda f: (f.line, RULES.index(f.rule)))


_MAGNITUDES = {"k": 1e3, "K": 1e3, "M": 1e6, "MM": 1e6, "B": 1e9, "bn": 1e9}


def _value(text: str) -> float | None:
    """The number a piece of text stands for: `$1,200` is 1200.0 and `$20M` is 20000000.0."""
    m = re.match(r"[$€£]?([0-9][0-9,]*(?:\.[0-9]+)?)(.*)$", text)
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * _MAGNITUDES.get(m.group(2), 1)


def numbers_in(text: str) -> list[dict]:
    """Every number in a document: its line, its text, its value, its label and the source named.

    A number takes the first label written after it on the line, or failing that the last one
    before it. `label` is None for a number on a line with no label, which is what `label` fails.
    """
    doc = Doc(text)
    out = []
    for i, nums in enumerate(doc.numbers):
        marks = [(pos, name, source) for pos, name, source in labels(doc.lines[i]) if name != "count" and (name != "sourced" or source)]
        for n in nums:
            after = [mark for mark in marks if mark[0] >= n.start]
            mark = after[0] if after else (marks[-1] if marks else None)
            out.append({
                "line": i + 1,
                "text": n.text,
                "value": _value(n.text),
                "label": mark[1] if mark else None,
                "source": mark[2] if mark else "",
            })
    return out


_LOG_HEADER = re.compile(r"^== pass (\d+) \| (\S+) \| (.*) \| exit (\d+)$")


def read_log(text: str) -> list[dict]:
    """The passes recorded in a checker.txt, oldest first: {n, at, target, exit}."""
    out = []
    for line in text.split("\n"):
        m = _LOG_HEADER.match(line)
        if m:
            out.append({"n": int(m.group(1)), "at": m.group(2), "target": m.group(3), "exit": int(m.group(4))})
    return out


def append_log(log: Path, target: str, code: int, output: str) -> None:
    """Add one pass to a checker.txt. Passes on the same target are numbered from 1."""
    before = log.read_text(encoding="utf-8") if log.is_file() else ""
    n = 1 + sum(1 for entry in read_log(before) if entry["target"] == target)
    at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"== pass {n} | {at} | {target} | exit {code}\n{output}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check agent output or client text against the rules of section 3.3.")
    parser.add_argument("file")
    parser.add_argument("--agent", choices=AGENTS, help="also require this agent's sections")
    parser.add_argument("--client", action="store_true", help="client-facing text: no jargon in the first line")
    parser.add_argument("--section", help="check only the section whose heading starts with this")
    parser.add_argument("--only", help="comma-separated rule names to run")
    parser.add_argument("--log", help="append this pass and its exit code to a run's checker.txt")
    parser.add_argument("--json", help="write every number in the file, with its label and source, to this JSON file")
    args = parser.parse_args(argv)

    only = None
    if args.only:
        only = tuple(r.strip() for r in args.only.split(",") if r.strip())
        unknown = [r for r in only if r not in RULES]
        if unknown:
            print(f"unknown rule: {', '.join(unknown)} (rules: {', '.join(RULES)})", file=sys.stderr)
            return 2
    path = Path(args.file)
    if not path.is_file():
        print(f"{args.file}: no such file", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    try:
        failures = check(text, args.agent, args.client, args.section, only)
    except ValueError as err:
        print(f"{args.file}: {err}", file=sys.stderr)
        return 2
    lines = [f"{args.file}:{f.line}: [{f.rule}] {f.message}" for f in failures]
    if failures:
        lines.append(f"FAIL {args.file}: {len(failures)} failure(s)")
    else:
        lines.append(f"OK   {args.file}: every rule passes (labelled, not proven true)")
    print("\n".join(lines))
    code = 1 if failures else 0
    if args.json:
        Path(args.json).write_text(json.dumps(numbers_in(text), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.log:
        flags = [f"--agent {args.agent}"] if args.agent else []
        flags += ["--client"] if args.client else []
        flags += [f"--section {args.section}"] if args.section else []
        flags += [f"--only {','.join(only)}"] if only else []
        append_log(Path(args.log), " ".join([path.name] + flags), code, "\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
