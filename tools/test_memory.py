#!/usr/bin/env python3
"""Tests for the team's memory: NUMBERS.md, CORRECTIONS.md and the golden set.

    python3 -m unittest tools.test_memory
    python3 -m unittest discover -s tools -p 'test_*.py'

They hold three things still. Every number in docs/agents/CONTEXT.md and in section 1 of
SUPPLY_VARIABILITY.md is a row of docs/agents/NUMBERS.md. Every row marked `proved` is
recomputed here, and every engine figure is recounted from the engine's own source. Every
entry in agents/CORRECTIONS.md has its six fields, and every golden answer still passes.

Nothing here is a result. The worked example is the handoff's own, and it is made up.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import re
import shutil
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_check  # noqa: E402
import check_golden  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BRIEF = ROOT / "SUPPLY_VARIABILITY.md"
CONTEXT = ROOT / "docs" / "agents" / "CONTEXT.md"
NUMBERS = ROOT / "docs" / "agents" / "NUMBERS.md"
CORRECTIONS = ROOT / "agents" / "CORRECTIONS.md"
GOLDEN = ROOT / "agents" / "golden"
ENGINE = ROOT / "engine" / "src" / "hubricon_engine"

FIELDS = ("Date", "From", "What was wrong", "What it became", "Commit", "Why")
OUTCOMES = ("check", "data fix", "agent-file line")
STAGES = ("production", "pickup", "booking", "ocean", "port", "customs", "trucking", "FBA check-in")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def failures(text: str, **kwargs) -> list[str]:
    """The failures of the `numbers` rule on `text`, as `line: message`."""
    found = agent_check.check(text, only=("numbers",), register=agent_check.load_register(), **kwargs)
    return [f"{f.line}: {f.message}" for f in found]


def run(*argv: str) -> tuple[int, str]:
    """Run the checker's command line and return (exit code, stdout)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = agent_check.main(list(argv))
    return code, out.getvalue()


def statuses(text: str) -> set:
    """The statuses the register lists for the one number in `text`."""
    register = agent_check.load_register()
    (number,) = agent_check.find_numbers(agent_check.mask_line(text))
    return register.rows.get(agent_check.number_key(number), set())


class TheRegister(unittest.TestCase):
    def test_it_loads(self):
        # parse_register raises on a row with no number, an unknown status, no source or no date.
        register = agent_check.load_register()
        self.assertGreater(len(register.rows), 60)

    def test_every_number_in_context_is_a_row(self):
        self.assertEqual(failures(read(CONTEXT)), [])

    def test_every_number_in_section_1_of_the_brief_is_a_row(self):
        self.assertEqual(failures(read(BRIEF), section="1"), [])

    def test_a_number_that_is_not_a_row_is_flagged(self):
        # The done-check of step 5: plant a figure in a copy of CONTEXT.md and it is named.
        planted = read(CONTEXT) + "\nThe pool needs 47 brands before it helps [inference].\n"
        found = failures(planted)
        self.assertEqual(len(found), 1)
        self.assertIn("not in docs/agents/NUMBERS.md: 47", found[0])
        self.assertTrue(found[0].startswith(f"{len(planted.splitlines())}: "))

    def test_the_command_line_flags_it_and_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "CONTEXT.md"
            copy.write_text(read(CONTEXT) + "\nThe pool needs 47 brands before it helps [inference].\n", encoding="utf-8")
            code, out = run(str(copy), "--only", "numbers")
            self.assertEqual(code, 1)
            self.assertIn("[numbers] not in docs/agents/NUMBERS.md: 47", out)
            copy.write_text(read(CONTEXT), encoding="utf-8")
            code, out = run(str(copy), "--only", "numbers")
            self.assertEqual(code, 0)
            self.assertIn("every rule passes", out)

    def test_the_unverified_simulation_is_marked_and_kept_from_clients(self):
        # O2: 5.7 days to 4.0 days is not evidence.
        self.assertEqual(statuses("5.7 days"), {"unverified simulation"})
        self.assertEqual(statuses("4.0 days"), {"unverified simulation"})
        line = "Forecast error fell from 5.7 days to 4.0 days [inference].\n"
        self.assertEqual(failures(line), [])
        found = failures(line, client=True)
        self.assertEqual(len(found), 1)
        self.assertIn("never in client text: 5.7; 4.0", found[0])

    def test_the_count_the_file_does_not_support_is_unverified(self):
        # Section 1.3: an earlier summary said 64 of 96, the file says 51 and 80.
        self.assertEqual(statuses("64 cells"), {"unverified"})
        self.assertEqual(statuses("51 cells"), {"simulated"})
        self.assertEqual(statuses("80 cells"), {"simulated"})

    def test_context_no_longer_says_what_the_scorecard_does_not(self):
        text = read(CONTEXT)
        self.assertNotIn("30 to 75 seconds", text)
        self.assertNotIn("23 models (", text)
        self.assertIn("ALL_MODELS", text)
        self.assertIn("docs/agents/NUMBERS.md", text)

    def test_context_does_not_present_pooled_demand_as_the_moat(self):
        text = read(CONTEXT)
        self.assertIn("It is not the moat", text)
        self.assertIn("Superseded 27 Nov 2026", text)


class TheArithmetic(unittest.TestCase):
    """Every row marked `proved` in NUMBERS.md, recomputed."""

    def test_the_stage_ranges_sum(self):
        # Read the eight ranges from the brief itself, so a changed range changes the sum.
        line = next(l for l in read(BRIEF).splitlines() if "passes eight stages" in l)
        found = dict(
            (name, (int(low), int(high)))
            for name, low, high in re.findall(r"(production|pickup|booking|ocean|port|customs|trucking|FBA check-in) (\d+) to (\d+)", line)
        )
        self.assertEqual(tuple(found), STAGES)
        self.assertEqual(sum(low for low, _ in found.values()), 39)
        self.assertEqual(sum(high for _, high in found.values()), 75)
        # The brief says they add up to 36 to 70. They do not: NUMBERS.md lists it as open.
        self.assertIn("36 to 70 days", line)
        self.assertEqual(statuses("39 days"), {"proved"})

    def test_the_worked_example_recomputes(self):
        demand, swing, lead, lead_swing = 40, 15.4, 45, 9
        z = round(statistics.NormalDist().inv_cdf(0.95), 3)
        self.assertEqual(z, 1.645)
        lead_term = demand ** 2 * lead_swing ** 2
        self.assertEqual(lead_term, 129_600)
        demand_term = lead * swing ** 2
        self.assertEqual(round(demand_term), 10_672)
        self.assertEqual(lead * 15 ** 2, 10_125)
        # The brief prints 10,620, which needs a swing of about 15.36.
        self.assertEqual(round(math.sqrt(10_620 / lead), 2), 15.36)
        self.assertEqual(round(lead_term / 10_620, 1), 12.2)
        rop = demand * lead + z * math.sqrt(demand_term + lead_term)
        self.assertEqual(round(rop), 2_416)
        self.assertEqual(round(demand * lead + z * math.sqrt(lead * 15 ** 2 + lead_term)), 2_415)
        habit = demand * lead * 1.2
        self.assertEqual(round(habit), 2_160)
        self.assertEqual(round(rop) - round(habit), 256)

    def test_three_to_one_under_one_reading(self):
        # Inference, and NUMBERS.md says so: a 35% error in the rate over the whole lead time.
        rate_term = (0.35 * 40 * 45) ** 2
        self.assertEqual(round(rate_term), 396_900)
        self.assertEqual(round(rate_term / 129_600, 2), 3.06)

    def test_the_per_brand_estimate_does_not_follow_from_its_assumptions_alone(self):
        # 6.2% lost, 68% of it lost sales, a 30% margin, a 40% cut: about $5,059 at $1M, not $13,000.
        self.assertEqual(round(1_000_000 * 0.062 * 0.68 * 0.30 * 0.40), 5_059)
        self.assertEqual(statuses("$13,000"), {"estimate"})

    def test_the_golden_physicist_case_uses_the_same_arithmetic(self):
        lead_term, demand_term = 129_600, 45 * 15.4 ** 2
        self.assertEqual(round(100 * lead_term / (lead_term + demand_term), 1), 92.4)
        self.assertEqual(round(100 * demand_term / (lead_term + demand_term), 1), 7.6)
        spare = round(1.645 * math.sqrt(lead_term + demand_term))
        self.assertEqual(spare, 616)
        self.assertEqual(round(spare * 10 * 0.25), 1_540)
        answer = read(GOLDEN / "physicist-worked-example" / "answer.md")
        for figure in ("92.4%", "7.6%", "616 units", "$1,540", "2,416"):
            self.assertIn(figure, answer)


class TheEngine(unittest.TestCase):
    """The engine rows of NUMBERS.md, recounted from the engine's own source."""

    def models(self) -> list[str]:
        # Python 3.9 cannot parse cli.py, so the tuple is read as text.
        block = re.search(r"^ALL_MODELS = \((.*?)\)", read(ENGINE / "cli.py"), re.S | re.M)
        self.assertIsNotNone(block, "cli.py no longer defines ALL_MODELS as a tuple")
        return re.findall(r'"([a-z_]+)"', block.group(1))

    def test_a_run_executes_23_models(self):
        names = self.models()
        self.assertEqual(len(names), 23)
        self.assertEqual(len(set(names)), 23)
        self.assertEqual(statuses("23 models"), {"measured"})

    def test_a_shopify_run_skips_only_fee_recovery(self):
        gates = re.findall(r'if "([a-z_]+)" in wanted and not channels\.(\w+)\(channel\)', read(ENGINE / "cli.py"))
        self.assertEqual(gates, [("recovery", "has_recovery")])
        self.assertIn("recovery", self.models())
        self.assertIn("def has_recovery", read(ENGINE / "channels.py"))
        self.assertEqual(statuses("22 models"), {"measured"})

    def test_the_lead_time_spread_is_assumed_at_a_fifth(self):
        self.assertRegex(read(ENGINE / "models" / "inventory_sim.py"), r"(?m)^LEAD_TIME_CV = 0\.2\b")
        self.assertIn("assumption", statuses("20%"))

    def test_the_scorecard_gives_the_two_timings_and_nothing_else(self):
        scorecard = read(ROOT / "engine" / "MATH_SCORECARD.md")
        self.assertIn("What it costs to run", scorecard)
        self.assertIn("75.5s", scorecard)
        self.assertIn("about 29 seconds", scorecard)
        self.assertNotIn("23 models", scorecard)
        self.assertNotIn("30 to 75 seconds", scorecard)
        self.assertEqual(statuses("75.5 seconds"), {"sourced"})


class TheCorrections(unittest.TestCase):
    def entries(self) -> list[tuple[int, str, dict]]:
        """Each entry as (number, title, {field: text})."""
        out = []
        for block in re.split(r"(?m)^## (?=C\d+\. )", read(CORRECTIONS))[1:]:
            head, _, body = block.partition("\n")
            number, _, title = head.partition(". ")
            fields = dict(re.findall(r"(?m)^- ([A-Z][A-Za-z ]+?): *(.*)$", body))
            out.append((int(number[1:]), title.strip(), fields))
        return out

    def test_entries_are_numbered_in_order(self):
        numbers = [n for n, _, _ in self.entries()]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        self.assertGreaterEqual(len(numbers), 6)

    def test_every_entry_has_its_six_fields(self):
        for number, title, fields in self.entries():
            with self.subTest(entry=f"C{number}"):
                self.assertTrue(title)
                self.assertEqual(tuple(fields), FIELDS)
                for name in FIELDS:
                    self.assertTrue(fields[name].strip(), f"C{number} has an empty `{name}`")

    def test_every_entry_says_what_it_became(self):
        for number, _, fields in self.entries():
            with self.subTest(entry=f"C{number}"):
                self.assertTrue(
                    fields["What it became"].lower().startswith(OUTCOMES),
                    f"C{number} must open `What it became` with one of: {', '.join(OUTCOMES)}",
                )

    def test_dates_and_commits_have_their_shape(self):
        for number, _, fields in self.entries():
            with self.subTest(entry=f"C{number}"):
                self.assertRegex(fields["Date"], r"^20\d\d-\d\d-\d\d\b")
                self.assertRegex(fields["Commit"], r"^[0-9a-f]{7,40}\b")

    def test_the_simulation_and_the_model_count_are_logged(self):
        text = read(CORRECTIONS)
        self.assertIn("5.7", text)
        self.assertIn("ALL_MODELS", text)
        self.assertIn("30 to 75 seconds", text)

    def test_the_log_names_no_client(self):
        # Client codes are c or t and three to six digits (tools/new_run.py). None belongs here yet.
        self.assertEqual(re.findall(r"\b[ct]\d{3,6}\b", read(CORRECTIONS)), [])


class TheGoldenSet(unittest.TestCase):
    def copy(self, tmp: str, name: str) -> Path:
        case = Path(tmp) / name
        shutil.copytree(GOLDEN / name, case)
        return case

    def test_there_are_cases_and_each_holds(self):
        found = check_golden.cases()
        self.assertGreaterEqual(len(found), 3)
        for case in found:
            with self.subTest(case=case.name):
                self.assertEqual(check_golden.problems(case), [])

    def test_the_command_prints_one_ok_line_per_case(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_golden.main([])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), len(check_golden.cases()))
        self.assertTrue(all(line.startswith("OK    ") for line in lines))

    def test_no_case_is_marked_reviewed_before_hagen_reviews_it(self):
        for case in check_golden.cases():
            meta = json.loads(read(case / "meta.json"))
            self.assertIn(meta["data"], ("made-up", "public"))
            self.assertIn("not yet reviewed by Hagen", meta["accepted"])

    def test_an_answer_that_stops_passing_the_checker_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "physicist-worked-example")
            answer = case / "answer.md"
            answer.write_text(read(answer) + "\nThe saving is 12% of stock value.\n", encoding="utf-8")
            wrong = check_golden.problems(case)
            self.assertTrue(any("[label]" in line for line in wrong), wrong)

    def test_a_changed_verdict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "red-team-section-1-3")
            answer = case / "answer.md"
            answer.write_text(read(answer).replace("Verdict: fix first", "Verdict: ship"), encoding="utf-8")
            self.assertIn("the verdict is `ship`, the accepted one is `fix first`", check_golden.problems(case))

    def test_a_number_that_leaves_the_register_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "client-view-made-up")
            answer = case / "answer.md"
            answer.write_text(read(answer).replace("2,416 units are left", "2,417 units are left"), encoding="utf-8")
            wrong = check_golden.problems(case)
            self.assertTrue(any("[numbers]" in line and "2,417" in line for line in wrong), wrong)

    def test_client_data_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "client-view-made-up")
            meta = json.loads(read(case / "meta.json"))
            meta["data"] = "client"
            (case / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            wrong = check_golden.problems(case)
            self.assertEqual(len(wrong), 1)
            self.assertIn("never a client's", wrong[0])

    def test_a_case_that_does_not_say_what_it_is_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "client-view-made-up")
            answer = case / "answer.md"
            answer.write_text(read(answer).replace("Made-up data. Not a client. Not a result.\n", ""), encoding="utf-8")
            wrong = check_golden.problems(case)
            self.assertIn("answer.md does not open by saying: Made-up data. Not a client. Not a result.", wrong)

    def test_a_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "red-team-section-1-3")
            (case / "question.md").unlink()
            self.assertEqual(check_golden.problems(case), ["question.md is missing"])

    def test_a_broken_case_makes_the_command_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = self.copy(tmp, "red-team-section-1-3")
            (case / "meta.json").write_text("{not json", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = check_golden.main([tmp])
            self.assertEqual(code, 1)
            self.assertIn("FAIL  red-team-section-1-3: meta.json is not JSON", out.getvalue())
            self.assertIn("1 of 1 golden case(s) no longer hold", out.getvalue())

    def test_an_empty_golden_folder_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = check_golden.main([tmp])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
