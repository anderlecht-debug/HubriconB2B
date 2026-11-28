#!/usr/bin/env python3
"""Tests for the run log: tools/new_run.py and tools/check_run.py.

    python3 -m unittest discover -s tools -p 'test_*.py'

Every run here is built from made-up data in a temporary folder. None is a result, and none
describes a client. Client codes are the neutral test codes t001, t002 and c001.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_check  # noqa: E402
import check_run  # noqa: E402
import new_run  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

QUESTION = "When should the made-up store order again?"
SOURCE = "made up for the tests"
ORDERS = "sku,order_date,units\nMADEUP-SKU-ALPHA-001,2026-10-01,12\nMADEUP-SKU-ALPHA-002,2026-10-09,30\n"
OTHER_ORDERS = "sku,order_date,units\nMADEUP-SKU-OMEGA-901,2026-09-03,7\nMADEUP-SKU-OMEGA-902,2026-09-18,19\n"
MARKER = "MARKER-7F3A-CLIENT-A-ONLY"

VERDICT = (
    "| Claim | Status | Problem | Fix or test |\n|---|---|---|---|\n"
    "| The made-up store sells about forty units a day | inference | The data is made up | Rerun on a real export |\n\n"
    "Verdict: ship\n\n## Next action\n\n- Keep this run as a test of the shape only.\n"
)


def view(units: int = 40) -> str:
    return (
        f"{new_run.NOT_A_RESULT['made-up']}\n\n"
        "Order again when you are down to 6 weeks of stock. [inference]\n\n"
        f"You sell about {units} units a day. [measured]\n"
    )


def quiet(function, argv: list[str]) -> tuple[int, str, str]:
    """Run a command's main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = function(argv)
    return code, out.getvalue(), err.getvalue()


def load(folder: Path) -> dict:
    return json.loads((folder / "run.json").read_text(encoding="utf-8"))


def save(folder: Path, run: dict) -> None:
    new_run.write_json(folder / "run.json", run)


def edit(folder: Path, **changes) -> dict:
    """Set top-level fields of a run.json."""
    run = load(folder)
    run.update(changes)
    save(folder, run)
    return run


def rules(report: check_run.Report) -> list[str]:
    return [rule for rule, _ in report.problems]


def kinds(report: check_run.Report) -> list[str]:
    return [kind for kind, _ in report.alerts]


class Case(unittest.TestCase):
    """A temporary run log, and a way to build a finished run in it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "runs"

    def source(self, text: str = ORDERS, name: str = "orders.csv") -> Path:
        path = self.tmp / "src" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def draft(self, code: str = "t001", run_id: str = "a1", day: int = 20, orders: str = ORDERS) -> Path:
        return new_run.create(
            self.root, code, "made-up", QUESTION, [self.source(orders)], SOURCE,
            run_id, f"2026-11-{day:02d}", f"2026-11-{day:02d}T10:00:00Z",
        )

    def log(self, folder: Path, name: str, *flags: str) -> int:
        code, _, _ = quiet(agent_check.main, [str(folder / name), *flags, "--log", str(folder / "checker.txt")])
        return code

    def finish(self, folder: Path, units: int = 40, status: str = "ok", verdict: str = VERDICT, text: str | None = None) -> Path:
        """Fill a draft in the way the inner loop will: view, checker passes, verdict, record."""
        day = folder.name[:10]
        (folder / "client_view.md").write_text(text if text is not None else view(units), encoding="utf-8")
        self.log(folder, "client_view.md", "--client", "--json", str(folder / "numbers.json"))
        (folder / "verdict.md").write_text(verdict, encoding="utf-8")
        self.log(folder, "verdict.md", "--agent", "feynman-red-team")
        run = load(folder)
        run["agents_run"] = [
            {"agent": "factory-physicist", "started": f"{day}T10:00:00Z", "finished": f"{day}T10:03:00Z", "passes": 1},
            {"agent": "feynman-red-team", "started": f"{day}T10:03:00Z", "finished": f"{day}T10:05:00Z", "passes": 1},
        ]
        run["conclusions"] = {
            "factory-physicist": {
                "summary": "Order at six weeks of stock.",
                "key_numbers": [{"name": "daily sales", "value": units, "unit": "units a day", "label": "measured"}],
                "why": "The made-up export shows steady sales.",
            },
            "feynman-red-team": {"summary": "Labelled, and made up.", "key_numbers": [], "why": "No claim goes past the data."},
        }
        run["cost"].update({"tokens_total": 1000, "tokens_checking": 400})
        run["prediction"]["why_none"] = "Made-up data: there is no outcome to predict."
        run["finished_at"] = f"{day}T10:05:00Z"
        run["status"] = status
        save(folder, run)
        return folder

    def clean(self, code: str = "t001", run_id: str = "a1", day: int = 20, orders: str = ORDERS, units: int = 40) -> Path:
        return self.finish(self.draft(code, run_id, day, orders), units)

    def alerts(self) -> list[str]:
        text = (self.root / new_run.ALERTS).read_text(encoding="utf-8")
        return [line for line in text.splitlines() if line.startswith("- ")]


# --------------------------------------------------------------------------------------
# new_run.py
# --------------------------------------------------------------------------------------

class NewRun(Case):
    def test_creates_every_file_of_section_6_3(self):
        folder = self.draft()
        self.assertEqual(folder, self.root / "t001" / "2026-11-20_a1")
        for name in new_run.FILES:
            self.assertTrue((folder / name).is_file(), name)
        self.assertTrue((folder / "inputs").is_dir())

    def test_run_json_has_every_field_of_the_table(self):
        run = load(self.draft())
        for key in (
            "client_code", "question", "started_at", "finished_at", "agents_run", "inputs", "conclusions",
            "numbers", "disagreements", "cost", "diff_since_last_run", "prediction", "outcome", "overrides", "status",
        ):
            self.assertIn(key, run)
        self.assertEqual(
            set(run["cost"]) - {"note"},
            {"tokens_total", "tokens_checking", "share_checking", "wall_time", "cycle_time_upload_to_first_dollar"},
        )
        self.assertEqual(set(run["prediction"]) - {"sealed_at", "why_none"}, {"sealed_hash", "value", "range", "naive_baseline"})
        self.assertEqual(set(run["outcome"]) - {"baseline_dollars"}, {"actual_dollars", "vs_baseline", "censored_days", "graded_at"})
        self.assertIsNone(run["status"])

    def test_an_input_is_copied_under_a_neutral_name_with_its_hash(self):
        folder = self.draft()
        entry = load(folder)["inputs"][0]
        self.assertEqual(entry["file"], "input-01.csv")
        self.assertEqual(entry["hash"], new_run.sha256(folder / "inputs" / "input-01.csv"))
        self.assertEqual(entry["rows"], 2)
        self.assertEqual(entry["date_range"], ["2026-10-01", "2026-10-09"])
        self.assertEqual(entry["source"], SOURCE)
        self.assertEqual([p.name for p in (folder / "inputs").iterdir()], ["input-01.csv"])

    def test_made_up_data_says_so_on_the_first_line_of_the_client_view(self):
        text = (self.draft() / "client_view.md").read_text(encoding="utf-8")
        self.assertEqual(text.splitlines()[0], "Made-up data. Not a client. Not a result.")

    def test_creates_the_alert_file_with_its_heading(self):
        self.draft()
        self.assertTrue((self.root / "ALERTS.md").read_text(encoding="utf-8").startswith("# Alerts\n"))
        self.assertEqual(self.alerts(), [])

    def test_refuses_a_name_as_a_client_code(self):
        for code in ("acme", "acme-goods", "c1", "T001", "client001"):
            with self.assertRaises(ValueError, msg=code):
                new_run.create(self.root, code, "made-up", QUESTION)
        self.assertFalse(self.root.exists())

    def test_a_c_code_is_for_client_data_and_a_t_code_is_not(self):
        with self.assertRaises(ValueError):
            new_run.create(self.root, "c001", "made-up", QUESTION)
        with self.assertRaises(ValueError):
            new_run.create(self.root, "t001", "client", QUESTION)
        self.assertTrue(new_run.create(self.root, "c001", "client", QUESTION, run_id="a1").is_dir())

    def test_refuses_a_column_of_customer_personal_data(self):
        for column in ("email", "Buyer Name", "phone", "shipping_address", "zip"):
            bad = self.source(f"sku,{column},units\nMADEUP-SKU-1,x,3\n", "bad.csv")
            with self.assertRaises(ValueError, msg=column) as caught:
                new_run.create(self.root, "t001", "made-up", QUESTION, [bad], SOURCE)
            self.assertIn("personal data", str(caught.exception))

    def test_refuses_inputs_with_no_source_an_empty_question_and_a_bad_run_id(self):
        with self.assertRaises(ValueError):
            new_run.create(self.root, "t001", "made-up", QUESTION, [self.source()])
        with self.assertRaises(ValueError):
            new_run.create(self.root, "t001", "made-up", "  ")
        with self.assertRaises(ValueError):
            new_run.create(self.root, "t001", "made-up", QUESTION, run_id="Brand Name")

    def test_refuses_to_write_over_a_run(self):
        self.draft()
        with self.assertRaises(ValueError):
            self.draft()

    def test_the_command_prints_the_folder(self):
        argv = ["t001", "--data", "made-up", "--question", QUESTION, "--root", str(self.root), "--run-id", "a1", "--date", "2026-11-20"]
        code, out, _ = quiet(new_run.main, argv)
        self.assertEqual((code, out.strip()), (0, str(self.root / "t001" / "2026-11-20_a1")))
        code, _, err = quiet(new_run.main, argv)
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)


# --------------------------------------------------------------------------------------
# check_run.py: a valid run, and the fields it computes
# --------------------------------------------------------------------------------------

class ValidRun(Case):
    def test_a_run_built_from_made_up_data_validates(self):
        folder = self.clean()
        code, out, _ = quiet(check_run.main, [str(folder), "--clean"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip().splitlines()[-1], f"OK    {folder}: valid, status ok, clean")
        self.assertEqual(self.alerts(), [])

    def test_a_draft_validates_but_is_not_clean(self):
        folder = self.draft()
        code, out, _ = quiet(check_run.main, [str(folder)])
        self.assertEqual(code, 0, out)
        self.assertIn("DRAFT", out)
        self.assertEqual(quiet(check_run.main, [str(folder), "--clean"])[0], 1)

    def test_the_cost_shares_are_computed(self):
        folder = self.clean()
        report = check_run.check(folder)
        self.assertTrue(report.clean, report.problems)
        cost = load(folder)["cost"]
        self.assertEqual(cost["share_checking"], 0.4)
        self.assertEqual(cost["wall_time"], 300)
        self.assertIn("400 of 1000 tokens went on checking (share 0.4000), wall time 300 s", quiet(check_run.main, [str(folder)])[1])

    def test_the_numbers_are_counted_by_label(self):
        folder = self.clean()
        check_run.check(folder)
        run = load(folder)
        self.assertEqual(run["numbers"]["counts"], {"measured": 1, "sourced": 0, "inference": 1, "unlabelled": 0})
        self.assertEqual(run["loop"]["checker_passes"], 1)
        self.assertEqual(run["diff_since_last_run"]["previous_run"], None)

    def test_a_computed_field_that_disagrees_is_a_problem_and_is_not_overwritten(self):
        folder = self.clean()
        run = load(folder)
        run["cost"]["share_checking"] = 0.9
        save(folder, run)
        report = check_run.check(folder)
        self.assertIn("derived", rules(report))
        self.assertEqual(load(folder)["cost"]["share_checking"], 0.9)

    def test_no_write_changes_nothing(self):
        folder = self.finish(self.draft(), status="failed")
        before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
        code, out, _ = quiet(check_run.main, [str(folder), "--no-write"])
        self.assertEqual(code, 0, out)
        self.assertIn("ALERT", out)
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()})
        self.assertEqual(self.alerts(), [])

    def test_tokens_may_be_missing_only_with_a_note_saying_why(self):
        folder = self.clean()
        run = load(folder)
        run["cost"].update({"tokens_total": None, "tokens_checking": None})
        save(folder, run)
        self.assertIn("cost", rules(check_run.check(folder)))
        run["cost"]["note"] = "Run by hand: the tokens were not metered."
        save(folder, run)
        self.assertTrue(check_run.check(folder).valid)

    def test_usage_errors_exit_2(self):
        self.assertEqual(quiet(check_run.main, [str(self.tmp / "nowhere")])[0], 2)
        self.assertEqual(quiet(check_run.main, [])[0], 2)


class Invalid(Case):
    def test_a_missing_file_is_a_problem(self):
        folder = self.clean()
        (folder / "verdict.md").unlink()
        report = check_run.check(folder)
        self.assertIn("files", rules(report))
        self.assertEqual(quiet(check_run.main, [str(folder)])[0], 1)

    def test_a_missing_field_is_a_problem(self):
        folder = self.clean()
        run = load(folder)
        del run["overrides"]
        del run["cost"]["tokens_checking"]
        save(folder, run)
        messages = [m for _, m in check_run.check(folder).problems]
        self.assertEqual(messages, ["run.json has no `cost.tokens_checking`", "run.json has no `overrides`"])

    def test_an_input_changed_after_its_hash_is_a_problem(self):
        folder = self.clean()
        (folder / "inputs" / "input-01.csv").write_text(ORDERS + "MADEUP-SKU-ALPHA-003,2026-10-11,5\n", encoding="utf-8")
        self.assertIn("inputs", rules(check_run.check(folder)))

    def test_an_input_that_is_not_listed_is_a_problem(self):
        folder = self.clean()
        (folder / "inputs" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        self.assertIn("inputs", rules(check_run.check(folder)))

    def test_an_input_kept_elsewhere_says_where(self):
        folder = self.clean()
        (folder / "inputs" / "input-01.csv").unlink()
        self.assertIn("inputs", rules(check_run.check(folder)))
        run = load(folder)
        run["inputs"][0]["stored_at"] = "private bucket, folder t001"
        save(folder, run)
        self.assertNotIn("inputs", rules(check_run.check(folder)))

    def test_made_up_data_without_its_first_line_is_a_problem(self):
        folder = self.finish(self.draft(), text="Order again when you are down to 6 weeks of stock. [inference]\n")
        self.assertIn("not-a-result", rules(check_run.check(folder)))

    def test_ok_needs_the_red_team_to_say_ship(self):
        folder = self.finish(self.draft(), verdict=VERDICT.replace("Verdict: ship", "Verdict: fix first"))
        report = check_run.check(folder)
        self.assertIn("verdict", rules(report))
        self.assertFalse(report.clean)

    def test_ok_needs_a_verdict_table(self):
        folder = self.finish(self.draft(), verdict="It all looks fine.\n\nVerdict: ship\n")
        self.assertIn("verdict", rules(check_run.check(folder)))

    def test_an_agent_that_ran_must_have_a_conclusion(self):
        folder = self.clean()
        run = load(folder)
        del run["conclusions"]["factory-physicist"]
        save(folder, run)
        self.assertIn("conclusions", rules(check_run.check(folder)))

    def test_a_key_number_must_be_labelled(self):
        folder = self.clean()
        run = load(folder)
        run["conclusions"]["factory-physicist"]["key_numbers"][0]["label"] = "guess"
        save(folder, run)
        self.assertIn("conclusions", rules(check_run.check(folder)))

    def test_an_unknown_agent_is_a_problem(self):
        folder = self.clean()
        run = load(folder)
        run["agents_run"].append({"agent": "someone-else", "started": "2026-11-20T10:00:00Z", "finished": "2026-11-20T10:01:00Z", "passes": 1})
        save(folder, run)
        self.assertIn("schema", rules(check_run.check(folder)))

    def test_a_finished_run_says_why_it_has_no_prediction(self):
        folder = self.clean()
        run = load(folder)
        run["prediction"]["why_none"] = ""
        save(folder, run)
        self.assertIn("prediction", rules(check_run.check(folder)))

    def test_numbers_json_must_match_the_client_view(self):
        folder = self.clean()
        new_run.write_json(folder / "numbers.json", [{"line": 1, "text": "99 units", "value": 99.0, "label": "measured", "source": ""}])
        self.assertIn("numbers", rules(check_run.check(folder)))


# --------------------------------------------------------------------------------------
# The loop's caps (O7) and the alerts (section 6.3, O12)
# --------------------------------------------------------------------------------------

BAD_VIEW = f"{new_run.NOT_A_RESULT['made-up']}\n\nYou sell about 40 units a day.\n"


class Alerts(Case):
    def test_a_client_view_that_fails_the_checker_is_a_problem_and_an_alert(self):
        folder = self.finish(self.draft(), text=BAD_VIEW)
        report = check_run.check(folder)
        self.assertIn("checker", rules(report))
        self.assertIn("checker", kinds(report))
        self.assertEqual(len(self.alerts()), 1)
        self.assertRegex(self.alerts()[0], r"^- \S+Z \| t001/2026-11-20_a1 \| checker \| client_view.md fails the checker: 1 failure\(s\)$")

    def test_an_alert_is_written_once(self):
        folder = self.finish(self.draft(), text=BAD_VIEW)
        check_run.check(folder)
        check_run.check(folder)
        self.assertEqual(len(self.alerts()), 1)

    def test_a_reorder_point_without_its_service_level_alerts(self):
        text = view() + "\nThe reorder point is 2,416 units. [inference]\n"
        report = check_run.check(self.finish(self.draft(), text=text))
        self.assertIn("rop", kinds(report))

    def test_a_lead_time_without_a_label_alerts(self):
        text = view() + "\nThe lead time is 45 days. [inference]\n"
        report = check_run.check(self.finish(self.draft(), text=text))
        self.assertIn("lead-time", kinds(report))

    def test_a_failed_run_is_valid_alerts_and_is_not_clean(self):
        folder = self.finish(self.draft(), status="failed")
        report = check_run.check(folder)
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(kinds(report), ["failed"])
        self.assertFalse(report.clean)
        self.assertEqual(quiet(check_run.main, [str(folder)])[0], 0)
        self.assertEqual(quiet(check_run.main, [str(folder), "--clean"])[0], 1)

    def three_failing_passes(self, status: str) -> Path:
        folder = self.draft()
        (folder / "client_view.md").write_text(BAD_VIEW, encoding="utf-8")
        self.log(folder, "client_view.md", "--client")
        self.log(folder, "client_view.md", "--client")
        return self.finish(folder, status=status, text=BAD_VIEW)

    def test_three_failing_checker_passes_is_stuck(self):
        folder = self.three_failing_passes("stuck")
        report = check_run.check(folder)
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(load(folder)["loop"]["checker_passes"], 3)
        self.assertIn("stuck", kinds(report))
        self.assertIn("still fails after 3 checker passes", dict(report.alerts)["stuck"])

    def test_a_run_at_the_cap_may_not_be_called_failed_or_ok(self):
        for status in ("failed", "ok"):
            report = check_run.check(self.three_failing_passes(status), write=False)
            self.assertIn("caps", rules(report), status)
            (self.root / "t001" / "2026-11-20_a1" / "run.json").unlink()
            for path in sorted((self.root / "t001").rglob("*"), reverse=True):
                path.unlink() if path.is_file() else path.rmdir()

    def test_a_fourth_checker_pass_is_over_the_cap(self):
        folder = self.draft()
        (folder / "client_view.md").write_text(BAD_VIEW, encoding="utf-8")
        for _ in range(3):
            self.log(folder, "client_view.md", "--client")
        report = check_run.check(self.finish(folder))
        self.assertIn("caps", rules(report))
        self.assertIn("4 checker passes on one text: the cap is 3 (O7)", [m for _, m in report.problems])

    def test_rework_inside_the_caps_can_still_be_clean(self):
        folder = self.draft()
        (folder / "client_view.md").write_text(BAD_VIEW, encoding="utf-8")
        self.log(folder, "client_view.md", "--client")
        self.finish(folder)
        edit(folder, loop={"checker_passes": None, "red_team_send_backs": 1})
        report = check_run.check(folder)
        self.assertTrue(report.clean, report.problems + report.alerts)
        self.assertEqual(load(folder)["loop"]["checker_passes"], 2)

    def test_two_send_backs_without_ship_is_stuck_and_three_is_over_the_cap(self):
        fix_first = VERDICT.replace("Verdict: ship", "Verdict: fix first")
        folder = self.finish(self.draft(), status="stuck", verdict=fix_first)
        edit(folder, loop={"checker_passes": None, "red_team_send_backs": 2})
        report = check_run.check(folder, write=False)
        self.assertTrue(report.valid, report.problems)
        self.assertIn("sent the work back 2 times", dict(report.alerts)["stuck"])
        edit(folder, loop={"checker_passes": None, "red_team_send_backs": 3})
        self.assertIn("caps", rules(check_run.check(folder, write=False)))

    def second_run(self, units: int, orders: str = ORDERS) -> check_run.Report:
        check_run.check(self.clean(units=40))
        return check_run.check(self.clean(run_id="b2", day=27, orders=orders, units=units))

    def test_a_number_that_moves_more_than_25_percent_on_the_same_inputs_alerts(self):
        report = self.second_run(52)
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(kinds(report), ["number-moved"])
        self.assertIn("`factory-physicist: daily sales` moved by 30% (40 to 52) with no change in inputs", dict(report.alerts)["number-moved"])
        diff = load(report.folder)["diff_since_last_run"]
        self.assertEqual(diff["previous_run"], "2026-11-20_a1")
        self.assertEqual(diff["inputs_changed"], False)
        self.assertEqual(diff["recommendation_changed"], True)
        self.assertEqual(diff["numbers_moved"], [{"name": "factory-physicist: daily sales", "before": 40, "after": 52, "change": 0.3}])

    def test_a_move_of_25_percent_or_less_does_not_alert(self):
        report = self.second_run(50)
        self.assertEqual(kinds(report), [])
        self.assertTrue(report.clean)

    def test_a_move_with_new_inputs_does_not_alert(self):
        report = self.second_run(52, ORDERS + "MADEUP-SKU-ALPHA-003,2026-10-20,44\n")
        self.assertEqual(kinds(report), [])
        self.assertEqual(load(report.folder)["diff_since_last_run"]["inputs_changed"], True)

    def test_the_same_run_again_changes_nothing(self):
        report = self.second_run(40)
        diff = load(report.folder)["diff_since_last_run"]
        self.assertEqual((diff["numbers_moved"], diff["recommendation_changed"]), ([], False))


# --------------------------------------------------------------------------------------
# The sealed prediction and its outcome
# --------------------------------------------------------------------------------------

class Seal(Case):
    def sealed(self) -> Path:
        folder = self.clean()
        check_run.seal(folder, 1200.0, 900.0, 1500.0, 1000.0, at="2026-11-20T10:04:00Z")
        return folder

    def grade(self, folder: Path, actual: float, graded_at: str = "2026-12-20T10:00:00Z") -> None:
        new_run.write_json(folder / "outcome.json", {
            "actual_dollars": actual, "baseline_dollars": 1000.0, "vs_baseline": None, "censored_days": 2, "graded_at": graded_at,
        })

    def test_a_sealed_prediction_validates(self):
        folder = self.sealed()
        prediction = load(folder)["prediction"]
        self.assertRegex(prediction["sealed_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual((prediction["value"], prediction["range"], prediction["naive_baseline"]), (1200.0, [900.0, 1500.0], 1000.0))
        self.assertTrue(check_run.check(folder).clean)

    def test_the_command_seals(self):
        folder = self.clean()
        code, out, _ = quiet(check_run.main, [str(folder), "--seal", "1200", "900", "1500", "1000"])
        self.assertEqual(code, 0)
        self.assertIn("sealed", out)
        self.assertEqual(quiet(check_run.main, [str(folder), "--seal", "1300", "900", "1500", "1000"])[0], 2)

    def test_a_prediction_changed_after_sealing_is_caught(self):
        folder = self.sealed()
        run = load(folder)
        run["prediction"]["value"] = 1400.0
        save(folder, run)
        report = check_run.check(folder)
        self.assertEqual([m for r, m in report.problems if r == "seal"], ["the prediction has been changed since it was sealed"])

    def test_a_seal_is_not_replaced_and_not_made_after_the_outcome(self):
        folder = self.sealed()
        with self.assertRaises(ValueError):
            check_run.seal(folder, 1300.0, 900.0, 1500.0, 1000.0)
        other = self.clean(run_id="b2", day=27)
        self.grade(other, 1100.0)
        with self.assertRaises(ValueError):
            check_run.seal(other, 1200.0, 900.0, 1500.0, 1000.0)
        with self.assertRaises(ValueError):
            check_run.seal(self.clean(run_id="c3", day=28), 2000.0, 900.0, 1500.0, 1000.0)

    def test_a_prediction_written_by_hand_is_not_a_sealed_one(self):
        folder = self.clean()
        run = load(folder)
        run["prediction"].update({"value": 1200.0, "range": [900.0, 1500.0], "naive_baseline": 1000.0})
        save(folder, run)
        self.assertIn("seal", rules(check_run.check(folder)))

    def test_an_outcome_inside_the_range_is_graded_against_the_baseline(self):
        folder = self.sealed()
        self.grade(folder, 1310.0)
        report = check_run.check(folder)
        self.assertTrue(report.clean, report.problems + report.alerts)
        self.assertEqual(json.loads((folder / "outcome.json").read_text(encoding="utf-8"))["vs_baseline"], 310.0)
        self.assertEqual(load(folder)["outcome"], {
            "actual_dollars": 1310.0, "baseline_dollars": 1000.0, "vs_baseline": 310.0, "censored_days": 2, "graded_at": "2026-12-20T10:00:00Z",
        })

    def test_an_outcome_outside_the_range_alerts(self):
        folder = self.sealed()
        self.grade(folder, 600.0)
        report = check_run.check(folder)
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(kinds(report), ["prediction-missed"])
        self.assertIn("actual $600.00 is outside the sealed range $900.00 to $1,500.00", self.alerts()[0])

    def test_an_outcome_needs_a_prediction_sealed_before_it(self):
        folder = self.clean()
        self.grade(folder, 1100.0)
        self.assertIn("outcome", rules(check_run.check(folder)))
        sealed = self.sealed_again()
        self.grade(sealed, 1100.0, "2026-11-01T00:00:00Z")
        self.assertIn("outcome", rules(check_run.check(sealed)))

    def sealed_again(self) -> Path:
        folder = self.clean(run_id="b2", day=27)
        check_run.seal(folder, 1200.0, 900.0, 1500.0, 1000.0, at="2026-11-27T10:04:00Z")
        return folder


# --------------------------------------------------------------------------------------
# Keeping clients apart (section 8.3)
# --------------------------------------------------------------------------------------

class Separation(Case):
    def two_clients(self) -> tuple[Path, Path]:
        a = self.clean("t001", "a1", 20, ORDERS + f"{MARKER},2026-10-12,8\n")
        b = self.clean("t002", "b1", 21, OTHER_ORDERS)
        return a, b

    def everything_in(self, folder: Path) -> str:
        return "\n".join(p.read_text(encoding="utf-8") for p in sorted(folder.rglob("*")) if p.is_file())

    def test_a_marker_in_client_a_s_data_is_nowhere_in_client_b_s_view(self):
        a, b = self.two_clients()
        self.assertIn(MARKER, self.everything_in(a))
        self.assertTrue(check_run.check(a).clean)
        report = check_run.check(b)
        self.assertTrue(report.clean, report.problems + report.alerts)
        self.assertNotIn(MARKER, (b / "client_view.md").read_text(encoding="utf-8"))
        self.assertNotIn(MARKER, self.everything_in(b))

    def test_the_marker_in_client_b_s_view_fails(self):
        _, b = self.two_clients()
        with (b / "client_view.md").open("a", encoding="utf-8") as fh:
            fh.write(f"\nYour slowest product is {MARKER}.\n")
        report = check_run.check(b)
        self.assertEqual([m for r, m in report.problems if r == "separation"], ["client_view.md holds 1 value(s) from the inputs of client t001"])
        self.assertIn("separation", kinds(report))
        self.assertEqual(quiet(check_run.main, [str(b)])[0], 1)
        alerts = "\n".join(self.alerts())
        self.assertIn("| t002/2026-11-21_b1 | separation |", alerts)
        self.assertNotIn(MARKER, alerts)

    def test_the_marker_anywhere_else_in_client_b_s_folder_fails(self):
        _, b = self.two_clients()
        (b / "disagreements.md").write_text(f"One agent wanted to mention {MARKER}.\n", encoding="utf-8")
        report = check_run.check(b, write=False)
        self.assertIn("disagreements.md holds 1 value(s) from the inputs of client t001", [m for _, m in report.problems])

    def test_a_value_both_clients_hold_is_not_a_leak(self):
        shared = "sku,order_date,units\nMADEUP-SKU-SHARED-500,2026-10-01,4\n"
        self.clean("t001", "a1", 20, shared)
        b = self.clean("t002", "b1", 21, shared)
        with (b / "client_view.md").open("a", encoding="utf-8") as fh:
            fh.write("\nYour one product is MADEUP-SKU-SHARED-500.\n")
        self.assertNotIn("separation", rules(check_run.check(b, write=False)))

    def test_another_client_s_code_in_the_folder_fails(self):
        _, b = self.two_clients()
        (b / "disagreements.md").write_text("Compared with t001, this store is slower.\n", encoding="utf-8")
        report = check_run.check(b, write=False)
        self.assertIn("disagreements.md names another client's code (t001)", [m for _, m in report.problems])

    def test_a_run_filed_under_the_wrong_client_fails(self):
        _, b = self.two_clients()
        edit(b, client_code="t001")
        report = check_run.check(b, write=False)
        self.assertIn("separation", rules(report))
        self.assertIn("separation", kinds(report))

    def test_a_link_out_of_the_run_folder_fails(self):
        a, b = self.two_clients()
        os.symlink(a / "inputs" / "input-01.csv", b / "borrowed.csv")
        self.assertIn("borrowed.csv is a link out of the run folder", [m for _, m in check_run.check(b, write=False).problems])


# --------------------------------------------------------------------------------------
# Nothing of the run log in git
# --------------------------------------------------------------------------------------

def git(top: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(top), *args], check=True, capture_output=True)


@contextlib.contextmanager
def inside(folder: Path):
    before = Path.cwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(before)


class Tracked(Case):
    def setUp(self):
        super().setUp()
        git(self.tmp, "init", "-q")
        (self.tmp / ".gitignore").write_text("runs/\nbrands/\n", encoding="utf-8")
        git(self.tmp, "add", ".gitignore")

    def test_an_ignored_run_log_passes(self):
        folder = self.clean()
        self.assertEqual(check_run.tracked(self.tmp), [])
        self.assertTrue(check_run.check(folder).clean)
        with inside(self.tmp):
            code, out, _ = quiet(check_run.main, ["--tracked"])
        self.assertEqual((code, out.strip()), (0, "OK    git tracks nothing under runs/ or brands/"))

    def test_a_tracked_run_file_fails(self):
        folder = self.clean()
        git(self.tmp, "add", "-f", "runs/t001/2026-11-20_a1/run.json")
        self.assertEqual(check_run.tracked(self.tmp), ["runs/t001/2026-11-20_a1/run.json"])
        with inside(self.tmp):
            code, out, _ = quiet(check_run.main, ["--tracked"])
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[0], "tracked: runs/t001/2026-11-20_a1/run.json")
        self.assertIn("FAIL", out.splitlines()[-1])
        report = check_run.check(folder)
        self.assertIn("tracked", rules(report))
        self.assertIn("tracked", kinds(report))

    def test_a_tracked_brand_file_fails(self):
        (self.tmp / "brands").mkdir()
        (self.tmp / "brands" / "notes.md").write_text("made up\n", encoding="utf-8")
        git(self.tmp, "add", "-f", "brands/notes.md")
        self.assertEqual(check_run.tracked(self.tmp), ["brands/notes.md"])
        with inside(self.tmp):
            self.assertEqual(quiet(check_run.main, ["--tracked"])[0], 1)

    def test_outside_a_git_work_tree_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as elsewhere, inside(Path(elsewhere)):
            if check_run.git_top(Path.cwd()) is None:
                self.assertEqual(quiet(check_run.main, ["--tracked"])[0], 2)


class ThisRepo(unittest.TestCase):
    def test_gitignore_keeps_the_run_log_and_brand_files_out(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("runs/", lines)
        self.assertIn("brands/", lines)

    def test_git_tracks_nothing_under_runs_or_brands(self):
        top = check_run.git_top(ROOT)
        if top is None:
            self.skipTest("not a git work tree")
        self.assertEqual(check_run.tracked(top), [])


# --------------------------------------------------------------------------------------
# Every run: the clean streak and the outer loop's lock (O6)
# --------------------------------------------------------------------------------------

class Streak(Case):
    def last_lines(self, *flags: str) -> tuple[int, list[str]]:
        code, out, _ = quiet(check_run.main, ["--all", str(self.root), *flags])
        return code, out.strip().splitlines()

    def test_five_clean_runs_across_two_clients_unlock_the_outer_loop(self):
        for n in range(3):
            self.clean("t001", f"a{n}", 20 + n)
        for n in range(2):
            self.clean("t002", f"b{n}", 23 + n, OTHER_ORDERS)
        code, lines = self.last_lines()
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[-2], "clean streak: 5 run(s) in a row, across 2 dataset(s) and 2 client(s)")
        self.assertTrue(lines[-1].startswith("outer loop: unlocked"), lines[-1])
        self.assertEqual(len([line for line in lines if "  clean  " in line]), 5)

    def test_five_clean_runs_on_one_dataset_for_one_client_do_not(self):
        for n in range(5):
            self.clean("t001", f"a{n}", 20 + n)
        _, lines = self.last_lines()
        self.assertEqual(lines[-2], "clean streak: 5 run(s) in a row, across 1 dataset(s) and 1 client(s)")
        self.assertTrue(lines[-1].startswith("outer loop: locked"), lines[-1])

    def test_four_clean_runs_do_not(self):
        for n in range(2):
            self.clean("t001", f"a{n}", 20 + n)
            self.clean("t002", f"b{n}", 22 + n, OTHER_ORDERS)
        _, lines = self.last_lines()
        self.assertTrue(lines[-1].startswith("outer loop: locked"), lines[-1])

    def test_a_failure_resets_the_count(self):
        for n in range(3):
            self.clean("t001", f"a{n}", 10 + n)
        self.finish(self.draft("t002", "b0", 13, OTHER_ORDERS), status="failed")
        for n in range(1, 3):
            self.clean("t002", f"b{n}", 13 + n, OTHER_ORDERS)
        code, lines = self.last_lines()
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[-2], "clean streak: 2 run(s) in a row, across 1 dataset(s) and 1 client(s)")
        self.assertIn("not clean (failed)", "\n".join(lines))

    def test_a_draft_does_not_count_and_does_not_break_the_streak(self):
        self.clean("t001", "a0", 20)
        self.draft("t001", "a1", 21)
        _, lines = self.last_lines()
        self.assertEqual(lines[-2], "clean streak: 1 run(s) in a row, across 1 dataset(s) and 1 client(s)")
        self.assertIn("draft", "\n".join(lines))

    def test_an_invalid_run_exits_1(self):
        folder = self.clean()
        (folder / "verdict.md").unlink()
        code, lines = self.last_lines("--no-write")
        self.assertEqual(code, 1)
        self.assertIn("INVALID", "\n".join(lines))
        self.assertEqual(lines[-2], "clean streak: 0 run(s) in a row, across 0 dataset(s) and 0 client(s)")


if __name__ == "__main__":
    unittest.main()
