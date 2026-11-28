#!/usr/bin/env python3
"""Tests for tools/agent_check.py: a known-good and a known-bad sample for every rule.

    python3 -m unittest discover -s tools -p 'test_*.py'

Every sample is made up. None is a result, and none describes a client.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_check  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def rules(text: str, **kwargs) -> list[str]:
    """The rule names that fail on `text`."""
    return [f.rule for f in agent_check.check(text, **kwargs)]


def run(text: str, *flags: str) -> tuple[int, str]:
    """Run the command on `text` and return (exit code, stdout)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.md"
        path.write_text(text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = agent_check.main([str(path), *flags])
        return code, out.getvalue().replace(str(path), "sample.md")


# One known-good and one known-bad sample per rule of section 3.3. Each pair differs only in
# the thing the rule looks for, so a rule that stops working shows up as one failing test.
SAMPLES = {
    "label": (
        "Stock on hand covers 14 days. [measured]\n",
        "Stock on hand covers 14 days.\n",
    ),
    "unit": (
        "The made-up store sold 120 units last week. [inference]\n",
        "The made-up store sold 120 last week. [inference]\n",
    ),
    "quote": (
        'Feynman said "you must not fool yourself and you are the easiest person to fool" (Caltech, 1974).\n',
        'Feynman said "you must not fool yourself and you are the easiest person to fool" at Caltech.\n',
    ),
    "next-action": (
        "# Note\n\nSome finding.\n\n## Next action\n\n- Send the made-up export to the checker.\n",
        "# Note\n\nSome finding.\n\n## Next action\n\n- Send the export.\n- Then call the supplier.\n",
    ),
    "rop": (
        "The reorder point is 2,416 units at a 95% service level, from μd = 40 units a day, "
        "σd = 15.4 units a day, μL = 45 days (assumed) and σL = 9 days. [inference]\n",
        "The reorder point is 2,416 units. [inference]\n",
    ),
    "lead-time": (
        "The lead time is assumed to be 45 days. [inference]\n",
        "The lead time is 45 days. [inference]\n",
    ),
    "jargon": (
        "Order again when you are down to your last six weeks of stock.\n",
        "Your ROP is too low for this product.\n",
    ),
    "sections": (
        "| Claim | Status | Problem | Fix or test |\n|---|---|---|---|\n"
        "| The sample is made up | proven | none | none |\n\nVerdict: ship\n",
        "The claims look fine to me.\n\nVerdict: ship\n",
    ),
    "baseline": (
        "Pooling cut slow-seller error by 27%, baseline: each store's own mean. [inference]\n",
        "Pooling cut slow-seller error by 27%. [inference]\n",
    ),
}
FLAGS = {"jargon": {"client": True}, "sections": {"agent": "feynman-red-team"}}


class EveryRule(unittest.TestCase):
    def test_a_sample_pair_exists_for_every_rule(self):
        self.assertEqual(set(SAMPLES), set(agent_check.RULES))

    def test_good_sample_passes_and_bad_sample_fails(self):
        for rule, (good, bad) in SAMPLES.items():
            flags = FLAGS.get(rule, {})
            with self.subTest(rule=rule, sample="good"):
                self.assertNotIn(rule, rules(good, only=(rule,), **flags))
            with self.subTest(rule=rule, sample="bad"):
                self.assertIn(rule, rules(bad, only=(rule,), **flags))

    def test_failure_names_the_line_and_the_rule(self):
        failures = agent_check.check("Fine.\n\nStock covers 14 days.\n", only=("label",))
        self.assertEqual([(f.line, f.rule) for f in failures], [(3, "label")])
        self.assertIn("14", failures[0].message)


class Label(unittest.TestCase):
    def test_each_of_the_three_labels_passes(self):
        for label in ("[measured]", "[sourced: sales export, made up]", "[inference]"):
            with self.subTest(label=label):
                self.assertEqual(rules(f"Stock covers 14 days. {label}\n", only=("label",)), [])

    def test_sourced_must_name_its_source(self):
        self.assertEqual(rules("Stock covers 14 days. [sourced]\n", only=("label",)), ["label", "label"])
        self.assertEqual(rules("Stock covers 14 days. [sourced: ]\n", only=("label",)), ["label", "label"])

    def test_count_is_not_a_provenance_label(self):
        self.assertEqual(rules("We checked 83 stores. [count]\n", only=("label",)), ["label"])

    def test_the_label_is_read_per_line(self):
        text = "Stock covers 14 days.\nDemand is 40 units a day. [measured]\n"
        self.assertEqual([f.line for f in agent_check.check(text, only=("label",))], [1])

    def test_a_table_row_needs_its_own_label(self):
        text = "| Product | Cover |\n|---|---|\n| A | 14 days [measured] |\n| B | 9 days |\n"
        self.assertEqual([f.line for f in agent_check.check(text, only=("label",))], [4])

    def test_lines_without_numbers_need_no_label(self):
        self.assertEqual(rules("Nothing to count here.\n", only=("label",)), [])


class WhatIsNotANumber(unittest.TestCase):
    """Dates, IDs, references, paths and code are never asked for a label or a unit."""

    def clean(self, text: str):
        self.assertEqual(rules(text, only=("label", "unit")), [], text)

    def test_dates_and_times(self):
        self.clean("Written 27 Nov 2026, revised 2026-11-27 at 10:30 UTC.\n")
        self.clean("Hagen said so on 22 to 23 Nov, and again on May 25, 1998.\n")
        self.clean("Stein proved it in 1956, and James and Stein in 1961.\n")

    def test_ids_and_references(self):
        self.clean("See O12, T1, SKU-104, commit 74a8ff4 and issue #12.\n")
        self.clean("Section 3.3, steps 1 to 8, item 8 and seeds 101/202/303 and 404/505/606.\n")
        self.clean("The terms (§10) and RFC 3161 both apply. Version 1.2.3 shipped.\n")
        self.clean("The 3PL sent it on the 1st, and again on the 21st.\n")

    def test_paths_urls_and_code(self):
        self.clean("Read docs/agents/CONTEXT.md and https://example.com/page/42 first.\n")
        self.clean("Run `python3 tools/check_agents.py --n 9` from the root.\n")
        self.clean("```\nprint(42)\n```\n")
        self.clean("---\nname: x\nversion: 2\n---\nNo numbers in the body.\n")

    def test_heading_and_list_numbers(self):
        self.clean("## 1.3 How it works\n\n1. First do this.\n2. Then that.\n")

    def test_a_year_followed_by_a_unit_is_a_quantity(self):
        self.assertEqual(rules("We hold 2000 units.\n", only=("label",)), ["label"])

    def test_a_bare_number_in_backticks_is_still_a_number(self):
        self.assertEqual(rules("The answer is `42`.\n", only=("label",)), ["label"])


class Unit(unittest.TestCase):
    def ok(self, text: str):
        self.assertEqual(rules(text, only=("unit",)), [], text)

    def test_units_the_checker_accepts(self):
        self.ok("It costs $1,200 a month, or 6.2% of sales.\n")
        self.ok("Lead times run 36 to 70 days, and air costs 8 to 12 times the ocean rate.\n")
        self.ok("Demand is 40 units/day ±15, on a 45-day lead time ±9 days.\n")
        self.ok("Brands from $1M to $20M, a market of $1.7 trillion.\n")
        self.ok("The engine ran in 30 to 75 seconds and is 10x faster.\n")
        self.ok("It scored 11 out of 5, won 51 of 96 cells and leads 3 to 1.\n")
        self.ok("Use z = 1.645 for 95% service.\n")

    def test_count_marks_a_unitless_count(self):
        self.assertEqual(rules("We checked 83 stores.\n", only=("unit",)), ["unit"])
        self.ok("We checked 83 stores. [count]\n")

    def test_count_does_not_stand_in_for_a_provenance_label(self):
        self.assertEqual(rules("We checked 83 stores. [count]\n", only=("label", "unit")), ["label"])


class Quote(unittest.TestCase):
    def test_six_words_or_fewer_need_no_source(self):
        self.assertEqual(rules('He called it "the best part is no part".\n', only=("quote",)), [])

    def test_a_source_without_a_year_fails(self):
        text = '"All happy companies are different because each one earns a monopoly" (Zero to One).\n'
        self.assertEqual(rules(text, only=("quote",)), ["quote"])

    def test_curly_quotes_and_emphasis(self):
        text = "**“All happy companies are different because each one earns a monopoly.”** (*Zero to One*, 2014)\n"
        self.assertEqual(rules(text, only=("quote",)), [])

    def test_a_quote_may_run_over_two_lines(self):
        text = '"All happy companies are different\nbecause each one earns a monopoly" (Zero to One, 2014)\n'
        self.assertEqual(rules(text, only=("quote",)), [])

    def test_a_number_with_a_decimal_is_one_word(self):
        self.assertEqual(rules('The claim "5.7 days to 4.0 days" is not evidence.\n', only=("quote",)), [])


class NextAction(unittest.TestCase):
    def test_one_paragraph_is_one_item(self):
        self.assertEqual(rules("# Note\n\n## Next action\n\nCall the supplier\nthis week.\n", only=("next-action",)), [])

    def test_the_section_must_be_last(self):
        text = "# Note\n\n## Next action\n\n- Call.\n\n## Appendix\n\nMore.\n"
        self.assertEqual(rules(text, only=("next-action",)), ["next-action"])

    def test_a_missing_or_empty_section_fails(self):
        self.assertEqual(rules("Just a paragraph.\n", only=("next-action",)), ["next-action"])
        self.assertEqual(rules("# Note\n\n## Next action\n", only=("next-action",)), ["next-action"])

    def test_sub_items_do_not_count_as_more_actions(self):
        text = "## Next action\n\n- Call the supplier.\n  - Ask for both dates.\n  - Ask for the order number.\n"
        self.assertEqual(rules(text, only=("next-action",)), [])


class ReorderPoint(unittest.TestCase):
    def test_a_link_to_the_inputs_passes(self):
        text = "The reorder point is 2,416 units ([inputs](inputs.md)). [inference]\n"
        self.assertEqual(rules(text, only=("rop",)), [])

    def test_the_failure_says_what_is_missing(self):
        text = "ROP is 2,416 units at a 95% service level with μd 40 and μL 45. [inference]\n"
        failures = agent_check.check(text, only=("rop",))
        self.assertEqual(len(failures), 1)
        self.assertIn("σd, σL", failures[0].message)
        self.assertNotIn("service level", failures[0].message)

    def test_a_mention_without_a_number_is_not_a_report(self):
        text = "The engine computes reorder points. Its spread is assumed to be 20%. [inference]\n"
        self.assertEqual(rules(text, only=("rop",)), [])

    def test_a_table_of_reorder_points(self):
        bad = "| Product | ROP |\n|---|---|\n| A | 2,416 units |\n"
        good = bad + "\nService level 95%. Inputs: μd, σd, μL and σL are in [inputs](inputs.md).\n"
        self.assertEqual(rules(bad, only=("rop",)), ["rop"])
        inline = "| Product | ROP | Service level | μd | σd | μL | σL |\n|---|---|---|---|---|---|---|\n| A | 2,416 units | 95% | 40 | 15.4 | 45 | 9 |\n"
        self.assertEqual(rules(inline, only=("rop",)), [])
        self.assertEqual(rules(good, only=("rop",)), ["rop"])  # the table itself must carry them


class LeadTime(unittest.TestCase):
    def test_measured_passes(self):
        self.assertEqual(rules("The lead time is 45 days. [measured]\n", only=("lead-time",)), [])

    def test_a_mean_with_its_spread_is_not_a_single_number(self):
        text = "The lead time is 45 days, give or take 9 days. [inference]\n"
        self.assertEqual(rules(text, only=("lead-time",)), [])

    def test_a_table_of_lead_times(self):
        bad = "| Supplier | Lead time |\n|---|---|\n| S1 | 45 days |\n"
        self.assertIn("lead-time", rules(bad, only=("lead-time",)))
        good = "| Supplier | Lead time |\n|---|---|\n| S1 | 45 days (assumed) |\n"
        self.assertEqual(rules(good, only=("lead-time",)), [])


class Jargon(unittest.TestCase):
    def test_only_with_client(self):
        self.assertEqual(rules("Your ROP is too low.\n", only=("jargon",)), [])

    def test_every_banned_term(self):
        for line in ("Sigma is high.", "σ is high.", "The z-score is 1.6.", "ROP is low.", "μ is 40."):
            with self.subTest(line=line):
                self.assertEqual(rules(line + "\n", client=True, only=("jargon",)), ["jargon"])

    def test_only_the_first_line_is_checked(self):
        text = "Order again at six weeks of stock.\n\nFull maths: ROP uses σ and μ.\n"
        self.assertEqual(rules(text, client=True, only=("jargon",)), [])

    def test_a_word_that_contains_rop_is_not_jargon(self):
        self.assertEqual(rules("Your profit dropped in Europe.\n", client=True, only=("jargon",)), [])

    def test_client_text_needs_no_next_action_heading(self):
        self.assertEqual(rules("Order again at six weeks of stock.\n", client=True), [])


class Sections(unittest.TestCase):
    def test_every_agent_has_required_sections(self):
        self.assertEqual(set(agent_check.REQUIRED), set(agent_check.AGENTS))
        self.assertEqual(len(agent_check.AGENTS), 9)

    def test_an_empty_note_fails_for_every_agent(self):
        for agent in agent_check.AGENTS:
            with self.subTest(agent=agent):
                self.assertIn("sections", rules("Nothing here.\n", agent=agent, only=("sections",)))

    def test_a_note_with_every_heading_passes(self):
        text = "".join(f"## {h}\n\nText.\n\n" for h in ("Weekly plan", "Call script"))
        self.assertEqual(rules(text, agent="graham-first-customers", only=("sections",)), [])
        self.assertEqual(rules("## Weekly plan\n\nText.\n", agent="graham-first-customers", only=("sections",)), ["sections"])

    def test_the_physicist_needs_its_table(self):
        table = "| SKU | Variance shares | Buffer cost | Cheapest lever | Expected saving |\n|---|---|---|---|---|\n| A | x | y | z | w |\n"
        text = table + "\n## Formula and inputs\n\nText.\n\n## Plain reading\n\nText.\n"
        self.assertEqual(rules(text, agent="factory-physicist", only=("sections",)), [])
        self.assertIn("sections", rules("## Formula\n\n## Plain reading\n", agent="factory-physicist", only=("sections",)))

    def test_red_team_status_must_come_from_its_list(self):
        text = "| Claim | Status | Problem | Fix or test |\n|---|---|---|---|\n| X | probably | none | none |\n\nVerdict: stop\n"
        failures = agent_check.check(text, agent="feynman-red-team", only=("sections",))
        self.assertEqual([(f.line, f.rule) for f in failures], [(3, "sections")])

    def test_red_team_needs_exactly_one_verdict(self):
        table = "| Claim | Status | Problem | Fix or test |\n|---|---|---|---|\n| X | proven | none | none |\n"
        self.assertEqual(rules(table, agent="feynman-red-team", only=("sections",)), ["sections"])
        both = table + "\nVerdict: ship\n\nVerdict: stop\n"
        self.assertEqual(rules(both, agent="feynman-red-team", only=("sections",)), ["sections"])

    def test_verdict_reads_the_three_outcomes(self):
        for word in agent_check.VERDICTS:
            self.assertEqual(agent_check.verdict(f"Text.\n\n**Verdict: {word}**\n"), word)
        self.assertIsNone(agent_check.verdict("No verdict here.\n"))


class Baseline(unittest.TestCase):
    def test_a_share_is_not_a_gain(self):
        self.assertEqual(rules("86.3% of profit landed inside the range. [measured]\n", only=("baseline",)), [])

    def test_comparatives_count_as_gains(self):
        self.assertEqual(rules("Error was 27% lower with pooling. [inference]\n", only=("baseline",)), ["baseline"])

    def test_a_dollar_gain_is_not_this_rule(self):
        self.assertEqual(rules("Profit rose by $400 a month. [inference]\n", only=("baseline",)), [])


class SectionAndOnly(unittest.TestCase):
    TEXT = "# Title\n\n## 1.2 First\n\nStock covers 14 days.\n\n## 1.3 Second\n\nDemand is 40 units a day.\n\n### Detail\n\nCover is 9 days.\n\n## 1.4 Third\n\nCover is 3 days.\n"

    def test_section_keeps_original_line_numbers(self):
        failures = agent_check.check(self.TEXT, section="1.3", only=("label",))
        self.assertEqual([f.line for f in failures], [9, 13])

    def test_section_skips_whole_document_rules(self):
        self.assertNotIn("next-action", rules(self.TEXT, section="1.3"))

    def test_an_unknown_section_is_an_error(self):
        with self.assertRaises(ValueError):
            agent_check.check(self.TEXT, section="9.9")

    def test_headings_inside_code_are_ignored(self):
        text = "## 1.3 Real\n\nCover is 9 days.\n\n````markdown\n## 1.4 Not a heading\n````\n\nCover is 3 days.\n"
        self.assertEqual([f.line for f in agent_check.check(text, section="1.3", only=("label",))], [3, 9])


class CommandLine(unittest.TestCase):
    def test_clean_file_exits_0(self):
        code, out = run("Stock covers 14 days. [measured]\n\n## Next action\n\n- Reorder product A.\n")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("OK   sample.md"))

    def test_failures_exit_1_one_line_each(self):
        code, out = run("Stock covers 14 days.\n", "--only", "label,unit")
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[0], "sample.md:1: [label] no [measured], [sourced: <source>] or [inference] label on: 14")
        self.assertEqual(out.splitlines()[-1], "FAIL sample.md: 1 failure(s)")

    def test_client_flag(self):
        self.assertEqual(run("Your ROP is too low.\n", "--client")[0], 1)
        self.assertEqual(run("Order again at six weeks of stock.\n", "--client")[0], 0)

    def test_agent_flag(self):
        code, out = run("## Next action\n\n- Call.\n", "--agent", "graham-first-customers")
        self.assertEqual(code, 1)
        self.assertIn("[sections]", out)

    def test_usage_errors_exit_2(self):
        self.assertEqual(run("Text.\n", "--only", "nonsense")[0], 2)
        self.assertEqual(run("Text.\n", "--section", "9.9")[0], 2)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(agent_check.main(["/no/such/file.md"]), 2)
            with self.assertRaises(SystemExit) as caught:
                agent_check.main(["x.md", "--agent", "nobody"])
        self.assertEqual(caught.exception.code, 2)


class OnTheBrief(unittest.TestCase):
    """The acceptance check of build step 3: run on section 1.3 and list the unlabelled numbers."""

    def test_section_1_3_lists_its_unlabelled_numbers(self):
        text = (ROOT / "SUPPLY_VARIABILITY.md").read_text(encoding="utf-8")
        failures = agent_check.check(text, section="1.3", only=("label",))
        self.assertTrue(failures)
        listed = " ".join(f.message for f in failures)
        for number in ("27%", "5.7", "4.0", "11,090", "86.3%", "78.6%", "3,000"):
            self.assertIn(number, listed)
        start = text.split("\n").index("### 1.3 How Hubricon solves it, and what has been proven") + 1
        self.assertTrue(all(f.line > start for f in failures))


if __name__ == "__main__":
    unittest.main()
