from __future__ import annotations

import copy
import unittest

from acah.validation import (
    validate_adapter,
    validate_approvals,
    validate_contract,
    validate_observation_fixture,
    validate_suite,
)
from tests.helpers import (
    APPROVALS,
    CONTRACT,
    REFERENCE_ADAPTER,
    SUITE,
    load,
)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.contract = load(CONTRACT)
        self.suite = load(SUITE)
        self.adapter = load(REFERENCE_ADAPTER)
        self.approvals = load(APPROVALS)

    def test_valid_contract(self):
        self.assertEqual(validate_contract(self.contract), [])

    def test_valid_suite(self):
        self.assertEqual(validate_suite(self.suite), [])

    def test_valid_adapter(self):
        self.assertEqual(validate_adapter(self.adapter), [])

    def test_valid_approvals(self):
        self.assertEqual(validate_approvals(self.approvals), [])

    def test_contract_requires_deny_default(self):
        value = copy.deepcopy(self.contract)
        value["default_verdict"] = "allow"
        self.assertTrue(any("default_verdict" in item for item in validate_contract(value)))

    def test_contract_rejects_duplicate_capability(self):
        value = copy.deepcopy(self.contract)
        value["capabilities"].append(copy.deepcopy(value["capabilities"][0]))
        self.assertTrue(any("duplicate capability" in item for item in validate_contract(value)))

    def test_contract_rejects_unknown_constraint(self):
        value = copy.deepcopy(self.contract)
        value["capabilities"][0]["constraints"]["magic"] = True
        self.assertTrue(any("unsupported constraints" in item for item in validate_contract(value)))

    def test_contract_rejects_invalid_effect(self):
        value = copy.deepcopy(self.contract)
        value["capabilities"][0]["effect"] = "telepathy"
        self.assertTrue(any("invalid effect" in item for item in validate_contract(value)))

    def test_contract_rejects_invalid_verdict(self):
        value = copy.deepcopy(self.contract)
        value["capabilities"][0]["verdict"] = "maybe"
        self.assertTrue(any("invalid verdict" in item for item in validate_contract(value)))

    def test_contract_rejects_negative_budget(self):
        value = copy.deepcopy(self.contract)
        value["capabilities"][0]["constraints"]["max_bytes"] = -1
        self.assertTrue(any("non-negative integer" in item for item in validate_contract(value)))

    def test_contract_rejects_boolean_numeric_budget(self):
        value = copy.deepcopy(self.contract)
        value["capabilities"][0]["constraints"]["max_bytes"] = True
        self.assertTrue(any("non-negative integer" in item for item in validate_contract(value)))

    def test_suite_rejects_duplicate_case(self):
        value = copy.deepcopy(self.suite)
        value["cases"].append(copy.deepcopy(value["cases"][0]))
        self.assertTrue(any("duplicate case" in item for item in validate_suite(value)))

    def test_suite_rejects_duplicate_action(self):
        value = copy.deepcopy(self.suite)
        value["cases"][0]["actions"].append(copy.deepcopy(value["cases"][0]["actions"][0]))
        self.assertTrue(any("duplicate action" in item for item in validate_suite(value)))

    def test_suite_rejects_missing_actions(self):
        value = copy.deepcopy(self.suite)
        value["cases"][0]["actions"] = []
        self.assertTrue(any("at least one action" in item for item in validate_suite(value)))

    def test_suite_rejects_invalid_expected_verdict(self):
        value = copy.deepcopy(self.suite)
        value["cases"][0]["actions"][0]["expected_verdict"] = "unknown"
        self.assertTrue(any("expected_verdict" in item for item in validate_suite(value)))

    def test_suite_rejects_invalid_observation(self):
        value = copy.deepcopy(self.suite)
        value["cases"][0]["actions"][0]["expected_observation"] = "teleport"
        self.assertTrue(any("expected_observation" in item for item in validate_suite(value)))

    def test_suite_rejects_negative_case_budget(self):
        value = copy.deepcopy(self.suite)
        value["cases"][0]["budgets"]["max_duration_ms"] = -1
        self.assertTrue(any("non-negative integer" in item for item in validate_suite(value)))

    def test_adapter_requires_observation_file(self):
        value = copy.deepcopy(self.adapter)
        value.pop("observation_file")
        self.assertTrue(any("observation_file" in item for item in validate_adapter(value)))

    def test_command_adapter_requires_argv(self):
        value = copy.deepcopy(self.adapter)
        value["kind"] = "command"
        value.pop("observation_file")
        value["command"] = []
        value["network_enforcement"] = "not_enforced"
        self.assertTrue(any("argv" in item for item in validate_adapter(value)))

    def test_command_adapter_requires_network_label(self):
        value = copy.deepcopy(self.adapter)
        value["kind"] = "command"
        value.pop("observation_file")
        value["command"] = ["python"]
        self.assertTrue(any("network_enforcement" in item for item in validate_adapter(value)))

    def test_approvals_reject_duplicate_id(self):
        value = copy.deepcopy(self.approvals)
        value["approvals"].append(copy.deepcopy(value["approvals"][0]))
        self.assertTrue(any("duplicate approval" in item for item in validate_approvals(value)))

    def test_approvals_require_parameter_hash(self):
        value = copy.deepcopy(self.approvals)
        value["approvals"][0]["parameters_hash"] = ""
        self.assertTrue(any("parameters_hash" in item for item in validate_approvals(value)))

    def test_fixture_rejects_invalid_event(self):
        value = {"schema_version": "1.0", "cases": {"case-a": [{"event_type": "boom"}]}}
        self.assertTrue(any("invalid event_type" in item for item in validate_observation_fixture(value)))

    def test_fixture_artifact_requires_content(self):
        value = {"schema_version": "1.0", "cases": {"case-a": [{"event_type": "artifact", "path": "x"}]}}
        self.assertTrue(any("requires content" in item for item in validate_observation_fixture(value)))

    def test_fixture_action_requires_action_id(self):
        value = {"schema_version": "1.0", "cases": {"case-a": [{"event_type": "action_blocked"}]}}
        self.assertTrue(any("action_id" in item for item in validate_observation_fixture(value)))


# Every published capability must remain individually valid. These generated tests
# make accidental catalog drift visible without duplicating fixture content.
def _make_capability_test(index: int):
    def test(self):
        value = {
            "schema_version": "1.0",
            "contract_id": "isolated-contract",
            "policy_version": "v1",
            "default_verdict": "deny",
            "capabilities": [copy.deepcopy(self.contract["capabilities"][index])],
        }
        self.assertEqual(validate_contract(value), [])
    return test


for _index in range(len(load(CONTRACT)["capabilities"])):
    setattr(ValidationTests, f"test_published_capability_{_index:02d}", _make_capability_test(_index))
