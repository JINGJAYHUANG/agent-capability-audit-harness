from __future__ import annotations

import json
import unittest

from acah.compare import compare_runs
from acah.runner import evaluate_suite
from tests.helpers import (
    APPROVALS,
    CONTRACT,
    FIXED_TIME,
    REFERENCE_ADAPTER,
    SUITE,
    VIOLATING_ADAPTER,
    temporary_directory,
)


class CompareTests(unittest.TestCase):
    def _run(self, run_dir, adapter):
        evaluate_suite(
            contract_path=CONTRACT,
            suite_path=SUITE,
            adapter_path=adapter,
            approvals_path=APPROVALS,
            run_dir=run_dir,
            fixed_time=FIXED_TIME,
        )

    def test_identical_runs_have_no_regression(self):
        with temporary_directory() as temp:
            first, second = temp / "first", temp / "second"
            self._run(first, REFERENCE_ADAPTER)
            self._run(second, REFERENCE_ADAPTER)
            result = compare_runs(first, second)
            self.assertEqual(result["status"], "no_regression")
            self.assertEqual(result["regressions"], [])

    def test_safe_to_violating_is_regression(self):
        with temporary_directory() as temp:
            baseline, candidate = temp / "baseline", temp / "candidate"
            self._run(baseline, REFERENCE_ADAPTER)
            self._run(candidate, VIOLATING_ADAPTER)
            result = compare_runs(baseline, candidate)
            self.assertEqual(result["status"], "regressed")
            self.assertTrue(any("deny_leakage" in item for item in result["regressions"]))
            self.assertTrue(any("ask_bypass" in item for item in result["regressions"]))

    def test_violating_to_safe_is_improvement(self):
        with temporary_directory() as temp:
            baseline, candidate = temp / "baseline", temp / "candidate"
            self._run(baseline, VIOLATING_ADAPTER)
            self._run(candidate, REFERENCE_ADAPTER)
            result = compare_runs(baseline, candidate)
            self.assertEqual(result["status"], "no_regression")
            self.assertTrue(any("overall" in item for item in result["improvements"]))

    def test_case_removal_is_regression(self):
        with temporary_directory() as temp:
            baseline, candidate = temp / "baseline", temp / "candidate"
            self._run(baseline, REFERENCE_ADAPTER)
            self._run(candidate, REFERENCE_ADAPTER)
            data = json.loads((candidate / "case-results.json").read_text())
            data["cases"] = data["cases"][:-1]
            (candidate / "case-results.json").write_text(json.dumps(data))
            result = compare_runs(baseline, candidate)
            self.assertTrue(any("case removed" in item for item in result["regressions"]))

    def test_new_case_is_improvement_marker(self):
        with temporary_directory() as temp:
            baseline, candidate = temp / "baseline", temp / "candidate"
            self._run(baseline, REFERENCE_ADAPTER)
            self._run(candidate, REFERENCE_ADAPTER)
            data = json.loads((baseline / "case-results.json").read_text())
            data["cases"] = data["cases"][:-1]
            (baseline / "case-results.json").write_text(json.dumps(data))
            result = compare_runs(baseline, candidate)
            self.assertTrue(any("new case" in item for item in result["improvements"]))

    def test_result_contains_run_ids(self):
        with temporary_directory() as temp:
            first, second = temp / "first", temp / "second"
            self._run(first, REFERENCE_ADAPTER)
            self._run(second, REFERENCE_ADAPTER)
            result = compare_runs(first, second)
            self.assertIsNotNone(result["baseline_run_id"])
            self.assertEqual(result["baseline_run_id"], result["candidate_run_id"])
