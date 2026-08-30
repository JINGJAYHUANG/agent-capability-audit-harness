from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from acah.cli import main
from tests.helpers import (
    APPROVALS,
    COMMAND_ADAPTER,
    CONTRACT,
    FIXED_TIME,
    REFERENCE_ADAPTER,
    SUITE,
    VIOLATING_ADAPTER,
    temporary_directory,
)


class CliTests(unittest.TestCase):
    def call(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([str(item) for item in argv])
        return code, stdout.getvalue(), stderr.getvalue()

    def common(self, adapter=REFERENCE_ADAPTER):
        return [
            "--contract", CONTRACT,
            "--suite", SUITE,
            "--adapter", adapter,
            "--approvals", APPROVALS,
        ]

    def test_validate(self):
        code, output, _ = self.call(["validate", *self.common()])
        self.assertEqual(code, 0)
        self.assertIn("VALID", output)

    def test_plan_stdout(self):
        code, output, _ = self.call(["plan", *self.common(), "--fixed-time", FIXED_TIME])
        self.assertEqual(code, 0)
        value = json.loads(output)
        self.assertIn("plan_hash", value)

    def test_plan_output_file(self):
        with temporary_directory() as temp:
            output_path = temp / "plan.json"
            code, _, _ = self.call(["plan", *self.common(), "--fixed-time", FIXED_TIME, "--output", output_path])
            self.assertEqual(code, 0)
            self.assertTrue(output_path.exists())

    def test_run_pass(self):
        with temporary_directory() as temp:
            code, output, _ = self.call(["run", *self.common(), "--run-dir", temp / "run", "--fixed-time", FIXED_TIME])
            self.assertEqual(code, 0)
            self.assertIn("PASS", output)

    def test_run_fail(self):
        with temporary_directory() as temp:
            code, output, _ = self.call(["run", *self.common(VIOLATING_ADAPTER), "--run-dir", temp / "run", "--fixed-time", FIXED_TIME])
            self.assertEqual(code, 1)
            self.assertIn("FAIL", output)

    def test_verify_text(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self.call(["run", *self.common(), "--run-dir", run_dir, "--fixed-time", FIXED_TIME])
            code, output, _ = self.call(["verify", "--run-dir", run_dir])
            self.assertEqual(code, 0)
            self.assertTrue(output.startswith("PASS"))

    def test_verify_json(self):
        with temporary_directory() as temp:
            run_dir = temp / "run"
            self.call(["run", *self.common(), "--run-dir", run_dir, "--fixed-time", FIXED_TIME])
            code, output, _ = self.call(["verify", "--run-dir", run_dir, "--format", "json"])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output)["passed"])

    def test_compare_regression_exit(self):
        with temporary_directory() as temp:
            good, bad = temp / "good", temp / "bad"
            self.call(["run", *self.common(), "--run-dir", good, "--fixed-time", FIXED_TIME])
            self.call(["run", *self.common(VIOLATING_ADAPTER), "--run-dir", bad, "--fixed-time", FIXED_TIME])
            code, output, _ = self.call(["compare", "--baseline", good, "--candidate", bad, "--fail-on-regression"])
            self.assertEqual(code, 1)
            self.assertIn("REGRESSED", output)

    def test_compare_json(self):
        with temporary_directory() as temp:
            first, second = temp / "first", temp / "second"
            self.call(["run", *self.common(), "--run-dir", first, "--fixed-time", FIXED_TIME])
            self.call(["run", *self.common(), "--run-dir", second, "--fixed-time", FIXED_TIME])
            code, output, _ = self.call(["compare", "--baseline", first, "--candidate", second, "--format", "json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output)["status"], "no_regression")

    def test_inspect(self):
        code, output, _ = self.call(["inspect", "--contract", CONTRACT])
        self.assertEqual(code, 0)
        self.assertIn("repo.read", output)

    def test_inspect_json(self):
        code, output, _ = self.call(["inspect", "--contract", CONTRACT, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["default_verdict"], "deny")

    def test_init_preview(self):
        with temporary_directory() as temp:
            code, output, _ = self.call(["init", "--target", temp / "starter"])
            self.assertEqual(code, 0)
            self.assertIn("Preview", output)
            self.assertFalse((temp / "starter").exists())

    def test_init_apply(self):
        with temporary_directory() as temp:
            target = temp / "starter"
            code, output, _ = self.call(["init", "--target", target, "--apply"])
            self.assertEqual(code, 0)
            self.assertTrue((target / "capability-contract.json").exists())
            self.assertIn("Created", output)

    def test_init_refuses_overwrite(self):
        with temporary_directory() as temp:
            target = temp / "starter"
            self.call(["init", "--target", target, "--apply"])
            code, _, error = self.call(["init", "--target", target, "--apply"])
            self.assertEqual(code, 2)
            self.assertIn("refusing", error)

    def test_command_requires_flag(self):
        with temporary_directory() as temp:
            code, _, error = self.call(["run", *self.common(COMMAND_ADAPTER), "--run-dir", temp / "run", "--fixed-time", FIXED_TIME])
            self.assertEqual(code, 2)
            self.assertIn("permission", error)

    def test_command_with_flag(self):
        with temporary_directory() as temp:
            code, output, _ = self.call(["run", *self.common(COMMAND_ADAPTER), "--run-dir", temp / "run", "--fixed-time", FIXED_TIME, "--allow-command"])
            self.assertEqual(code, 0)
            self.assertIn("PASS", output)

    def test_invalid_file_returns_two(self):
        with temporary_directory() as temp:
            bad = temp / "bad.json"
            bad.write_text("not-json")
            code, _, error = self.call([
                "validate",
                "--contract", bad,
                "--suite", SUITE,
                "--adapter", REFERENCE_ADAPTER,
                "--approvals", APPROVALS,
            ])
            self.assertEqual(code, 2)
            self.assertIn("validation error", error)
