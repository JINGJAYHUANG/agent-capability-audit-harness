from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path

from acah.adapters import (
    _expand_command,
    _minimal_environment,
    _validate_observations,
    execute_adapter,
    load_observation_fixture,
)
from tests.helpers import (
    COMMAND_ADAPTER,
    REFERENCE_ADAPTER,
    SUITE,
    load,
    temporary_directory,
)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.case = load(SUITE)["cases"][0]
        self.decisions = [
            {
                "action_id": action["id"],
                "capability": action["capability"],
                "base_verdict": action["expected_verdict"],
                "verdict": action["expected_verdict"],
                "constraint_passed": True,
                "reasons": [],
                "approval_id": None,
            }
            for action in self.case["actions"]
        ]

    def test_load_reference_fixture(self):
        adapter = load(REFERENCE_ADAPTER)
        fixture = load_observation_fixture(REFERENCE_ADAPTER, adapter)
        self.assertIn("repo-review", fixture["cases"])

    def test_fixture_adapter_returns_events(self):
        adapter = load(REFERENCE_ADAPTER)
        with temporary_directory() as temp:
            observations, runtime = execute_adapter(
                adapter_path=REFERENCE_ADAPTER,
                adapter=adapter,
                case=self.case,
                decisions=self.decisions,
                invocation_dir=temp,
                allow_command=False,
            )
        self.assertGreaterEqual(len(observations), 4)
        self.assertEqual(runtime["kind"], "fixture")
        self.assertEqual(runtime["duration_ms"], 0.0)

    def test_command_adapter_requires_explicit_flag(self):
        adapter = load(COMMAND_ADAPTER)
        with temporary_directory() as temp:
            with self.assertRaises(PermissionError):
                execute_adapter(
                    adapter_path=COMMAND_ADAPTER,
                    adapter=adapter,
                    case=self.case,
                    decisions=self.decisions,
                    invocation_dir=temp,
                    allow_command=False,
                )

    def test_command_adapter_executes_safe_fixture(self):
        adapter = load(COMMAND_ADAPTER)
        with temporary_directory() as temp:
            observations, runtime = execute_adapter(
                adapter_path=COMMAND_ADAPTER,
                adapter=adapter,
                case=self.case,
                decisions=self.decisions,
                invocation_dir=temp,
                allow_command=True,
            )
            self.assertTrue((temp / "packet.json").exists())
            self.assertTrue((temp / "observations.json").exists())
        self.assertEqual(runtime["kind"], "command")
        self.assertEqual(runtime["exit_code"], 0)
        self.assertTrue(any(item["event_type"] == "artifact" for item in observations))

    def test_command_expansion(self):
        expanded = _expand_command(
            ["{python}", "{adapter_root}/tool.py", "{packet}", "{output}"],
            Path("/tmp/packet.json"),
            Path("/tmp/output.json"),
            Path("/tmp/adapter"),
        )
        self.assertEqual(expanded[1], "/tmp/adapter/tool.py")
        self.assertIn("packet.json", expanded[2])

    def test_unknown_placeholder_rejected(self):
        with self.assertRaises(ValueError):
            _expand_command(["{unknown}"], Path("p"), Path("o"), Path("a"))

    def test_sensitive_environment_name_rejected(self):
        with self.assertRaises(ValueError):
            _minimal_environment(["EXAMPLE_API_TOKEN"])

    def test_regular_environment_allowlist(self):
        os.environ["ACAH_TEST_VALUE"] = "safe"
        try:
            environment = _minimal_environment(["ACAH_TEST_VALUE"])
            self.assertEqual(environment["ACAH_TEST_VALUE"], "safe")
        finally:
            os.environ.pop("ACAH_TEST_VALUE", None)

    def test_observation_requires_array(self):
        with self.assertRaises(ValueError):
            _validate_observations({}, "case")

    def test_observation_requires_action_id(self):
        with self.assertRaises(ValueError):
            _validate_observations([{"event_type": "action_executed"}], "case")

    def test_artifact_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            _validate_observations([{"event_type": "artifact", "path": "../x", "content": "x"}], "case")

    def test_artifact_requires_content(self):
        with self.assertRaises(ValueError):
            _validate_observations([{"event_type": "artifact", "path": "x"}], "case")

    def test_invalid_event_type_rejected(self):
        with self.assertRaises(ValueError):
            _validate_observations([{"event_type": "teleport"}], "case")

    def test_command_timeout_range(self):
        adapter = load(COMMAND_ADAPTER)
        adapter["timeout_seconds"] = 0
        with temporary_directory() as temp:
            with self.assertRaises(ValueError):
                execute_adapter(
                    adapter_path=COMMAND_ADAPTER,
                    adapter=adapter,
                    case=self.case,
                    decisions=self.decisions,
                    invocation_dir=temp,
                    allow_command=True,
                )
