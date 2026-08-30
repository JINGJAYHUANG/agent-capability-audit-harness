from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from acah.policy import (
    compile_plan,
    constraint_failures,
    evaluate_action,
    parameters_hash,
    parse_time,
)
from tests.helpers import APPROVALS, CONTRACT, EMPTY_APPROVALS, FIXED_TIME, SUITE, load


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.contract = load(CONTRACT)
        self.suite = load(SUITE)
        self.approvals = load(APPROVALS)
        self.empty = load(EMPTY_APPROVALS)
        self.now = parse_time(FIXED_TIME)

    def test_parse_zulu_time(self):
        self.assertEqual(parse_time("2026-01-01T00:00:00Z").tzinfo, timezone.utc)

    def test_parse_requires_timezone(self):
        with self.assertRaises(ValueError):
            parse_time("2026-01-01T00:00:00")

    def test_parameter_hash_is_stable(self):
        self.assertEqual(parameters_hash({"a": 1, "b": 2}), parameters_hash({"b": 2, "a": 1}))

    def test_unknown_capability_denied(self):
        action = {"id": "unknown-action", "capability": "unknown.capability", "parameters": {}}
        decision = evaluate_action(self.contract, self.empty, case_id="case-x", action=action, now=self.now)
        self.assertEqual(decision.verdict, "deny")
        self.assertIn("unknown_capability_deny_by_default", decision.reasons)

    def test_ask_without_approval(self):
        action = {"id": "write", "capability": "repo.write", "parameters": {"path": "repo/x", "reversible": True}}
        decision = evaluate_action(self.contract, self.empty, case_id="case-x", action=action, now=self.now)
        self.assertEqual(decision.verdict, "ask")
        self.assertIsNone(decision.approval_id)

    def test_exact_approval_allows(self):
        case = next(item for item in self.suite["cases"] if item["id"] == "approved-patch")
        action = next(item for item in case["actions"] if item["id"] == "apply-approved-patch")
        decision = evaluate_action(self.contract, self.approvals, case_id=case["id"], action=action, now=self.now)
        self.assertEqual(decision.base_verdict, "ask")
        self.assertEqual(decision.verdict, "allow")
        self.assertEqual(decision.approval_id, "approval-approved-patch-001")

    def test_approval_parameters_mismatch(self):
        case = next(item for item in self.suite["cases"] if item["id"] == "approved-patch")
        action = copy.deepcopy(next(item for item in case["actions"] if item["id"] == "apply-approved-patch"))
        action["parameters"]["path"] = "repo/src/other.py"
        decision = evaluate_action(self.contract, self.approvals, case_id=case["id"], action=action, now=self.now)
        self.assertEqual(decision.verdict, "ask")
        self.assertIn("approval_parameters_mismatch", decision.reasons)

    def test_expired_approval(self):
        approvals = copy.deepcopy(self.approvals)
        approvals["approvals"][0]["expires_at"] = "2020-01-01T00:00:00Z"
        case = next(item for item in self.suite["cases"] if item["id"] == "approved-patch")
        action = next(item for item in case["actions"] if item["id"] == "apply-approved-patch")
        decision = evaluate_action(self.contract, approvals, case_id=case["id"], action=action, now=self.now)
        self.assertEqual(decision.verdict, "ask")
        self.assertIn("approval_expired", decision.reasons)

    def test_wrong_case_approval_does_not_apply(self):
        approvals = copy.deepcopy(self.approvals)
        approvals["approvals"][0]["case_id"] = "other-case"
        case = next(item for item in self.suite["cases"] if item["id"] == "approved-patch")
        action = next(item for item in case["actions"] if item["id"] == "apply-approved-patch")
        decision = evaluate_action(self.contract, approvals, case_id=case["id"], action=action, now=self.now)
        self.assertEqual(decision.verdict, "ask")

    def test_path_constraint_accepts_declared_scope(self):
        self.assertEqual(constraint_failures({"paths": ["repo/**"]}, {"path": "repo/a/b.py"}), [])

    def test_path_constraint_rejects_traversal(self):
        self.assertIn("path_out_of_scope", constraint_failures({"paths": ["repo/**"]}, {"path": "../x"}))

    def test_host_constraint_exact_match(self):
        self.assertEqual(constraint_failures({"hosts": ["docs.example.test"]}, {"host": "docs.example.test"}), [])

    def test_host_constraint_rejects_subdomain(self):
        self.assertIn("host_out_of_scope", constraint_failures({"hosts": ["docs.example.test"]}, {"host": "x.docs.example.test"}))

    def test_method_constraint_is_case_insensitive(self):
        self.assertEqual(constraint_failures({"methods": ["GET"]}, {"method": "get"}), [])

    def test_row_budget(self):
        self.assertIn("row_budget_exceeded", constraint_failures({"max_rows": 10}, {"rows": 11}))

    def test_byte_budget(self):
        self.assertIn("byte_budget_exceeded", constraint_failures({"max_bytes": 10}, {"bytes": 11}))

    def test_reversible_constraint(self):
        self.assertIn("operation_not_reversible", constraint_failures({"reversible_only": True}, {"reversible": False}))

    def test_constraint_failure_overrides_allow(self):
        action = {"id": "escape", "capability": "repo.read", "parameters": {"path": "outside/x"}}
        decision = evaluate_action(self.contract, self.empty, case_id="case-x", action=action, now=self.now)
        self.assertEqual(decision.base_verdict, "allow")
        self.assertEqual(decision.verdict, "deny")
        self.assertFalse(decision.constraint_passed)

    def test_plan_hash_is_deterministic(self):
        first = compile_plan(self.contract, self.suite, self.approvals, now=self.now)
        second = compile_plan(self.contract, self.suite, self.approvals, now=self.now)
        self.assertEqual(first, second)

    def test_plan_hash_changes_with_time(self):
        first = compile_plan(self.contract, self.suite, self.approvals, now=self.now)
        second = compile_plan(self.contract, self.suite, self.approvals, now=datetime(2026, 8, 30, 0, 0, 1, tzinfo=timezone.utc))
        self.assertNotEqual(first["plan_hash"], second["plan_hash"])


# Each golden action is a dedicated policy regression case.
def _make_action_test(case_index: int, action_index: int):
    def test(self):
        case = self.suite["cases"][case_index]
        action = case["actions"][action_index]
        decision = evaluate_action(
            self.contract,
            self.approvals,
            case_id=case["id"],
            action=action,
            now=self.now,
        )
        self.assertEqual(decision.verdict, action["expected_verdict"])
    return test


for _ci, _case in enumerate(load(SUITE)["cases"]):
    for _ai, _action in enumerate(_case["actions"]):
        setattr(
            PolicyTests,
            f"test_golden_action_{_ci:02d}_{_ai:02d}_{_action['id'].replace('-', '_')}",
            _make_action_test(_ci, _ai),
        )
