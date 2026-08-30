from __future__ import annotations

import json
import unittest
from pathlib import Path

from acah.canonical import sha256_file
from acah.runner import evaluate_suite
from tests.helpers import (
    APPROVALS,
    COMMAND_ADAPTER,
    CONTRACT,
    EMPTY_APPROVALS,
    FIXED_TIME,
    REFERENCE_ADAPTER,
    SUITE,
    VIOLATING_ADAPTER,
    temporary_directory,
)


def file_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class RunnerTests(unittest.TestCase):
    def _run(self, run_dir: Path, *, adapter=REFERENCE_ADAPTER, approvals=APPROVALS, **kwargs):
        return evaluate_suite(
            contract_path=CONTRACT,
            suite_path=SUITE,
            adapter_path=adapter,
            approvals_path=approvals,
            run_dir=run_dir,
            fixed_time=FIXED_TIME,
            **kwargs,
        )

    def test_reference_run_passes(self):
        with temporary_directory() as temp:
            summary = self._run(temp / "run")
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["passed_cases"], 8)
            self.assertEqual(summary["action_count"], 21)

    def test_reference_has_no_leakage(self):
        with temporary_directory() as temp:
            summary = self._run(temp / "run")
            self.assertEqual(summary["deny_leakage"], 0)
            self.assertEqual(summary["ask_bypass"], 0)

    def test_violating_adapter_fails(self):
        with temporary_directory() as temp:
            summary = self._run(temp / "run", adapter=VIOLATING_ADAPTER)
            self.assertFalse(summary["passed"])
            self.assertGreater(summary["deny_leakage"], 0)
            self.assertGreater(summary["ask_bypass"], 0)

    def test_empty_approvals_fail_approved_case(self):
        with temporary_directory() as temp:
            summary = self._run(temp / "run", approvals=EMPTY_APPROVALS)
            self.assertFalse(summary["passed"])
            self.assertGreater(summary["gate_mismatches"], 0)

    def test_run_outputs_exist(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            for name in (
                "plan.json",
                "events.jsonl",
                "case-results.json",
                "capability-matrix.json",
                "artifact-manifest.json",
                "summary.json",
                "report.md",
                "report.html",
                "run-manifest.json",
            ):
                self.assertTrue((run_dir / name).exists(), name)

    def test_input_snapshots_exist(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            names = {path.name for path in (run_dir / "inputs").iterdir()}
            self.assertEqual(
                names,
                {
                    "contract.json",
                    "suite.json",
                    "adapter.json",
                    "approvals.json",
                    "adapter-observations.json",
                },
            )

    def test_artifacts_are_manifested(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            manifest = json.loads((run_dir / "artifact-manifest.json").read_text())
            self.assertEqual(len(manifest["artifacts"]), 8)
            for entry in manifest["artifacts"]:
                self.assertTrue((run_dir / entry["path"]).exists())

    def test_event_log_has_final_event(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            last = json.loads((run_dir / "events.jsonl").read_text().splitlines()[-1])
            self.assertEqual(last["event_type"], "run_completed")

    def test_fixed_fixture_run_is_deterministic(self):
        with temporary_directory() as temp:
            first = temp / "first"
            second = temp / "second"
            self._run(first)
            self._run(second)
            self.assertEqual(file_map(first), file_map(second))

    def test_run_id_changes_with_adapter(self):
        with temporary_directory() as temp:
            good = self._run(temp / "good")
            bad = self._run(temp / "bad", adapter=VIOLATING_ADAPTER)
            self.assertNotEqual(good["run_id"], bad["run_id"])

    def test_nonempty_run_directory_refused(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            run_dir.mkdir()
            (run_dir / "existing.txt").write_text("x")
            with self.assertRaises(FileExistsError):
                self._run(run_dir)

    def test_replace_run_directory(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            run_dir.mkdir()
            (run_dir / "existing.txt").write_text("x")
            summary = self._run(run_dir, replace=True)
            self.assertTrue(summary["passed"])
            self.assertFalse((run_dir / "existing.txt").exists())

    def test_command_requires_flag(self):
        with temporary_directory() as temp:
            with self.assertRaises(PermissionError):
                self._run(temp / "run", adapter=COMMAND_ADAPTER)

    def test_command_adapter_passes_with_flag(self):
        with temporary_directory() as temp:
            summary = self._run(temp / "run", adapter=COMMAND_ADAPTER, allow_command=True)
            self.assertTrue(summary["passed"])
            self.assertFalse(summary["deterministic"])

    def test_reports_do_not_include_absolute_source_paths(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            report = (run_dir / "report.md").read_text()
            self.assertNotIn(str(CONTRACT.parent), report)
            self.assertNotIn("/mnt/data", report)

    def test_summary_binds_plan(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            summary = self._run(run_dir)
            plan = json.loads((run_dir / "plan.json").read_text())
            self.assertEqual(summary["plan_hash"], plan["plan_hash"])

    def test_capability_matrix_includes_unknown_denial(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            matrix = json.loads((run_dir / "capability-matrix.json").read_text())
            row = next(item for item in matrix["capabilities"] if item["capability"] == "runtime.root_access")
            self.assertEqual(row["declared_verdict"], "unknown")
            self.assertEqual(row["denied"], 1)

    def test_html_report_is_self_contained(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._run(run_dir)
            html = (run_dir / "report.html").read_text()
            self.assertIn("<style>", html)
            self.assertNotIn("<script", html.lower())
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)
