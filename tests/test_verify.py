from __future__ import annotations

import json
import unittest

from acah.runner import evaluate_suite
from acah.verify import verify_run
from tests.helpers import APPROVALS, CONTRACT, FIXED_TIME, REFERENCE_ADAPTER, SUITE, temporary_directory


class VerifyTests(unittest.TestCase):
    def _make_run(self, root):
        evaluate_suite(
            contract_path=CONTRACT,
            suite_path=SUITE,
            adapter_path=REFERENCE_ADAPTER,
            approvals_path=APPROVALS,
            run_dir=root,
            fixed_time=FIXED_TIME,
        )

    def test_valid_run(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            self.assertTrue(verify_run(run_dir).passed)

    def test_missing_manifest(self):
        with temporary_directory() as temp:
            result = verify_run(temp)
            self.assertFalse(result.passed)

    def test_tampered_summary(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            summary = json.loads((run_dir / "summary.json").read_text())
            summary["passed"] = False
            (run_dir / "summary.json").write_text(json.dumps(summary))
            result = verify_run(run_dir)
            self.assertFalse(result.passed)
            self.assertTrue(any("summary.json" in item for item in result.errors))

    def test_tampered_input(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            contract = json.loads((run_dir / "inputs" / "contract.json").read_text())
            contract["policy_version"] = "tampered"
            (run_dir / "inputs" / "contract.json").write_text(json.dumps(contract))
            result = verify_run(run_dir)
            self.assertFalse(result.passed)
            self.assertTrue(any("input snapshot" in item for item in result.errors))

    def test_tampered_event(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            lines = (run_dir / "events.jsonl").read_text().splitlines()
            event = json.loads(lines[2])
            event["payload"]["verdict"] = "allow"
            lines[2] = json.dumps(event)
            (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n")
            result = verify_run(run_dir)
            self.assertFalse(result.passed)
            self.assertTrue(any("event" in item for item in result.errors))

    def test_missing_output(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            (run_dir / "report.md").unlink()
            result = verify_run(run_dir)
            self.assertFalse(result.passed)
            self.assertIn("missing output: report.md", result.errors)

    def test_tampered_artifact(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            artifact = next((run_dir / "artifacts").rglob("result.json"))
            artifact.write_text("tampered")
            result = verify_run(run_dir)
            self.assertFalse(result.passed)
            self.assertTrue(any("artifact" in item for item in result.errors))

    def test_missing_artifact(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            artifact = next((run_dir / "artifacts").rglob("result.json"))
            artifact.unlink()
            result = verify_run(run_dir)
            self.assertFalse(result.passed)
            self.assertTrue(any("missing artifact" in item for item in result.errors))

    def test_manifest_details(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self._make_run(run_dir)
            result = verify_run(run_dir)
            self.assertEqual(result.details["event_count"], 68)
            self.assertEqual(len(result.details["manifest_sha256"]), 64)
