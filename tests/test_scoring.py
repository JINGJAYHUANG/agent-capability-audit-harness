from __future__ import annotations

import copy
import unittest

from acah.policy import compile_plan, parse_time
from acah.scoring import assess_case, build_capability_matrix, summarize
from tests.helpers import APPROVALS, CONTRACT, FIXED_TIME, SUITE, load


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.contract = load(CONTRACT)
        self.suite = load(SUITE)
        self.approvals = load(APPROVALS)
        self.plan = compile_plan(self.contract, self.suite, self.approvals, now=parse_time(FIXED_TIME))
        self.case = self.suite["cases"][0]
        self.decisions = self.plan["cases"][0]["decisions"]
        self.observations = [
            {"event_type": action["expected_observation"], "action_id": action["id"]}
            for action in self.case["actions"]
        ]

    def test_compliant_case_passes(self):
        result = assess_case(
            case=self.case,
            decisions=self.decisions,
            observations=self.observations,
            runtime={"duration_ms": 0},
            artifact_bytes=0,
        )
        self.assertTrue(result["passed"])

    def test_denied_execution_is_leakage(self):
        observations = copy.deepcopy(self.observations)
        observations[2]["event_type"] = "action_executed"
        result = assess_case(case=self.case, decisions=self.decisions, observations=observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertEqual(result["metrics"]["deny_leakage"], 1)
        self.assertFalse(result["passed"])

    def test_ask_execution_is_bypass(self):
        observations = copy.deepcopy(self.observations)
        observations[1]["event_type"] = "action_executed"
        result = assess_case(case=self.case, decisions=self.decisions, observations=observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertEqual(result["metrics"]["ask_bypass"], 1)

    def test_missing_observation(self):
        result = assess_case(case=self.case, decisions=self.decisions, observations=self.observations[:-1], runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertEqual(result["metrics"]["missing_observations"], 1)

    def test_duplicate_observation(self):
        observations = self.observations + [copy.deepcopy(self.observations[0])]
        result = assess_case(case=self.case, decisions=self.decisions, observations=observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertGreaterEqual(result["metrics"]["observation_mismatches"], 1)

    def test_unexpected_action(self):
        observations = self.observations + [{"event_type": "action_executed", "action_id": "surprise"}]
        result = assess_case(case=self.case, decisions=self.decisions, observations=observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertEqual(result["metrics"]["unexpected_observations"], 1)

    def test_observation_budget(self):
        case = copy.deepcopy(self.case)
        case["budgets"]["max_observations"] = 1
        result = assess_case(case=case, decisions=self.decisions, observations=self.observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertEqual(result["metrics"]["budget_violations"], 1)

    def test_output_budget(self):
        case = copy.deepcopy(self.case)
        case["budgets"]["max_output_bytes"] = 1
        result = assess_case(case=case, decisions=self.decisions, observations=self.observations, runtime={"duration_ms": 0}, artifact_bytes=2)
        self.assertEqual(result["metrics"]["budget_violations"], 1)

    def test_duration_budget(self):
        case = copy.deepcopy(self.case)
        case["budgets"]["max_duration_ms"] = 1
        result = assess_case(case=case, decisions=self.decisions, observations=self.observations, runtime={"duration_ms": 2}, artifact_bytes=0)
        self.assertEqual(result["metrics"]["budget_violations"], 1)

    def test_evidence_completeness(self):
        result = assess_case(case=self.case, decisions=self.decisions, observations=self.observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        self.assertEqual(result["evidence_completeness"], 1.0)

    def test_matrix_not_evaluated(self):
        matrix = build_capability_matrix(self.contract, [])
        self.assertTrue(all(row["status"] == "not_evaluated" for row in matrix["capabilities"]))

    def test_matrix_behavior_verified(self):
        result = assess_case(case=self.case, decisions=self.decisions, observations=self.observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        matrix = build_capability_matrix(self.contract, [result])
        requested = {row["capability"]: row for row in matrix["capabilities"] if row["requested"]}
        self.assertEqual(requested["repo.read"]["status"], "behavior_verified")

    def test_matrix_violation(self):
        observations = copy.deepcopy(self.observations)
        observations[2]["event_type"] = "action_executed"
        result = assess_case(case=self.case, decisions=self.decisions, observations=observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        matrix = build_capability_matrix(self.contract, [result])
        row = next(row for row in matrix["capabilities"] if row["capability"] == "shell.exec")
        self.assertEqual(row["status"], "violated")

    def test_summary_pass(self):
        result = assess_case(case=self.case, decisions=self.decisions, observations=self.observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        matrix = build_capability_matrix(self.contract, [result])
        summary = summarize([result], matrix)
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["gate_accuracy"], 1.0)

    def test_summary_fail(self):
        observations = copy.deepcopy(self.observations)
        observations[1]["event_type"] = "action_executed"
        result = assess_case(case=self.case, decisions=self.decisions, observations=observations, runtime={"duration_ms": 0}, artifact_bytes=0)
        matrix = build_capability_matrix(self.contract, [result])
        summary = summarize([result], matrix)
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["ask_bypass"], 1)
