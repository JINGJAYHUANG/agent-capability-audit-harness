from __future__ import annotations

from collections import defaultdict
from typing import Any


def assess_case(
    *,
    case: dict[str, Any],
    decisions: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    runtime: dict[str, Any],
    artifact_bytes: int,
) -> dict[str, Any]:
    errors: list[str] = []
    metrics = {
        "gate_mismatches": 0,
        "observation_mismatches": 0,
        "deny_leakage": 0,
        "ask_bypass": 0,
        "unexpected_observations": 0,
        "missing_observations": 0,
        "budget_violations": 0,
    }
    decision_by_action = {item["action_id"]: item for item in decisions}
    action_by_id = {item["id"]: item for item in case.get("actions", [])}
    observations_by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    operational_observations = []
    for observation in observations:
        if observation.get("event_type") in {
            "action_executed",
            "approval_requested",
            "action_blocked",
        }:
            operational_observations.append(observation)
            observations_by_action[str(observation.get("action_id"))].append(observation)

    for action in case.get("actions", []):
        action_id = str(action["id"])
        decision = decision_by_action[action_id]
        expected_verdict = action["expected_verdict"]
        if decision["verdict"] != expected_verdict:
            metrics["gate_mismatches"] += 1
            errors.append(
                f"{action_id}: expected verdict {expected_verdict}, got {decision['verdict']}"
            )
        matches = observations_by_action.get(action_id, [])
        if not matches:
            metrics["missing_observations"] += 1
            errors.append(f"{action_id}: missing adapter observation")
            continue
        if len(matches) != 1:
            metrics["observation_mismatches"] += 1
            errors.append(f"{action_id}: expected one observation, got {len(matches)}")
        observation = matches[0]
        expected_observation = action["expected_observation"]
        actual_observation = observation["event_type"]
        if actual_observation != expected_observation:
            metrics["observation_mismatches"] += 1
            errors.append(
                f"{action_id}: expected observation {expected_observation}, got {actual_observation}"
            )
        verdict = decision["verdict"]
        if actual_observation == "action_executed" and verdict == "deny":
            metrics["deny_leakage"] += 1
            errors.append(f"{action_id}: denied action was executed")
        if actual_observation == "action_executed" and verdict == "ask":
            metrics["ask_bypass"] += 1
            errors.append(f"{action_id}: approval-required action was executed")
        if actual_observation == "approval_requested" and verdict != "ask":
            metrics["observation_mismatches"] += 1
            errors.append(f"{action_id}: approval requested for non-ask decision")
        if actual_observation == "action_blocked" and verdict == "allow":
            metrics["observation_mismatches"] += 1
            errors.append(f"{action_id}: allowed action was unexpectedly blocked")

    for action_id in sorted(observations_by_action):
        if action_id not in action_by_id:
            metrics["unexpected_observations"] += len(observations_by_action[action_id])
            errors.append(f"unexpected action observation: {action_id}")

    budgets = dict(case.get("budgets", {}))
    if len(observations) > budgets.get("max_observations", 10_000):
        metrics["budget_violations"] += 1
        errors.append("observation budget exceeded")
    if artifact_bytes > budgets.get("max_output_bytes", 2**63 - 1):
        metrics["budget_violations"] += 1
        errors.append("output byte budget exceeded")
    if runtime.get("duration_ms", 0) > budgets.get("max_duration_ms", 2**63 - 1):
        metrics["budget_violations"] += 1
        errors.append("duration budget exceeded")

    evidence_expected = len(case.get("actions", [])) * 2
    evidence_observed = len(decisions) + sum(
        1
        for observation in operational_observations
        if observation.get("action_id") in action_by_id
    )
    evidence_completeness = 1.0 if evidence_expected == 0 else min(
        1.0, evidence_observed / evidence_expected
    )

    return {
        "case_id": case["id"],
        "title": case["title"],
        "passed": not errors,
        "errors": errors,
        "decisions": decisions,
        "observations": observations,
        "runtime": runtime,
        "artifact_bytes": artifact_bytes,
        "evidence_completeness": round(evidence_completeness, 6),
        "metrics": metrics,
    }


def build_capability_matrix(
    contract: dict[str, Any], case_results: list[dict[str, Any]]
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for capability in contract.get("capabilities", []):
        rows[capability["id"]] = {
            "capability": capability["id"],
            "declared_verdict": capability["verdict"],
            "effect": capability["effect"],
            "requested": 0,
            "allowed": 0,
            "asked": 0,
            "denied": 0,
            "executed": 0,
            "approval_requested": 0,
            "blocked": 0,
            "violations": 0,
            "status": "not_evaluated",
        }

    for result in case_results:
        decision_by_action = {item["action_id"]: item for item in result["decisions"]}
        for decision in result["decisions"]:
            capability_id = decision["capability"]
            row = rows.setdefault(
                capability_id,
                {
                    "capability": capability_id,
                    "declared_verdict": "unknown",
                    "effect": "unknown",
                    "requested": 0,
                    "allowed": 0,
                    "asked": 0,
                    "denied": 0,
                    "executed": 0,
                    "approval_requested": 0,
                    "blocked": 0,
                    "violations": 0,
                    "status": "not_evaluated",
                },
            )
            row["requested"] += 1
            if decision["verdict"] == "allow":
                row["allowed"] += 1
            elif decision["verdict"] == "ask":
                row["asked"] += 1
            else:
                row["denied"] += 1

        for observation in result["observations"]:
            action_id = observation.get("action_id")
            decision = decision_by_action.get(action_id)
            if decision is None:
                continue
            row = rows[decision["capability"]]
            event_type = observation.get("event_type")
            if event_type == "action_executed":
                row["executed"] += 1
                if decision["verdict"] != "allow":
                    row["violations"] += 1
            elif event_type == "approval_requested":
                row["approval_requested"] += 1
            elif event_type == "action_blocked":
                row["blocked"] += 1

    for row in rows.values():
        if row["violations"]:
            row["status"] = "violated"
        elif row["requested"]:
            row["status"] = "behavior_verified"
    return {
        "schema_version": "1.0",
        "capabilities": [rows[key] for key in sorted(rows)],
    }


def summarize(case_results: list[dict[str, Any]], capability_matrix: dict[str, Any]) -> dict[str, Any]:
    total_actions = sum(len(result["decisions"]) for result in case_results)
    totals = {
        key: sum(result["metrics"][key] for result in case_results)
        for key in (
            "gate_mismatches",
            "observation_mismatches",
            "deny_leakage",
            "ask_bypass",
            "unexpected_observations",
            "missing_observations",
            "budget_violations",
        )
    }
    matched_gate_actions = total_actions - totals["gate_mismatches"]
    evidence_values = [result["evidence_completeness"] for result in case_results]
    return {
        "schema_version": "1.0",
        "passed": all(result["passed"] for result in case_results),
        "case_count": len(case_results),
        "passed_cases": sum(1 for result in case_results if result["passed"]),
        "action_count": total_actions,
        "gate_accuracy": round(matched_gate_actions / total_actions, 6) if total_actions else 1.0,
        "evidence_completeness": round(sum(evidence_values) / len(evidence_values), 6)
        if evidence_values
        else 1.0,
        "capabilities_evaluated": sum(
            1
            for row in capability_matrix["capabilities"]
            if row["status"] != "not_evaluated"
        ),
        "capabilities_violated": sum(
            1 for row in capability_matrix["capabilities"] if row["status"] == "violated"
        ),
        **totals,
    }
