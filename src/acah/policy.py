from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from typing import Any

from .canonical import sha256_json
from .models import Decision


def parse_time(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def parameters_hash(parameters: dict[str, Any]) -> str:
    return sha256_json(parameters)


def _capability_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in contract.get("capabilities", [])}


def _match_path(value: Any, patterns: list[str]) -> bool:
    if not isinstance(value, str) or not value:
        return False
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        return False
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def _match_exact(value: Any, allowed: list[str], *, normalize_upper: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    if normalize_upper:
        return value.upper() in {item.upper() for item in allowed}
    return value in allowed


def constraint_failures(constraints: dict[str, Any], parameters: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key, expected in constraints.items():
        if key == "paths":
            if not _match_path(parameters.get("path"), list(expected)):
                failures.append("path_out_of_scope")
        elif key == "hosts":
            if not _match_exact(parameters.get("host"), list(expected)):
                failures.append("host_out_of_scope")
        elif key == "methods":
            if not _match_exact(parameters.get("method"), list(expected), normalize_upper=True):
                failures.append("method_out_of_scope")
        elif key == "databases":
            if not _match_exact(parameters.get("database"), list(expected)):
                failures.append("database_out_of_scope")
        elif key == "operations":
            if not _match_exact(parameters.get("operation"), list(expected)):
                failures.append("operation_out_of_scope")
        elif key == "max_rows":
            value = parameters.get("rows")
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > expected:
                failures.append("row_budget_exceeded")
        elif key == "max_bytes":
            value = parameters.get("bytes")
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > expected:
                failures.append("byte_budget_exceeded")
        elif key == "reversible_only":
            if expected is True and parameters.get("reversible") is not True:
                failures.append("operation_not_reversible")
        else:
            failures.append(f"unsupported_constraint:{key}")
    return failures


def _find_approval(
    approvals: dict[str, Any],
    *,
    case_id: str,
    action: dict[str, Any],
    now: datetime,
) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    target_hash = parameters_hash(dict(action.get("parameters", {})))
    for approval in approvals.get("approvals", []):
        if approval.get("case_id") != case_id:
            continue
        if approval.get("action_id") != action.get("id"):
            continue
        if approval.get("capability") != action.get("capability"):
            continue
        if approval.get("parameters_hash") != target_hash:
            reasons.append("approval_parameters_mismatch")
            continue
        try:
            expires_at = parse_time(str(approval.get("expires_at")))
        except ValueError:
            reasons.append("approval_timestamp_invalid")
            continue
        if expires_at < now:
            reasons.append("approval_expired")
            continue
        return approval, reasons
    return None, reasons


def evaluate_action(
    contract: dict[str, Any],
    approvals: dict[str, Any],
    *,
    case_id: str,
    action: dict[str, Any],
    now: datetime,
) -> Decision:
    capability_id = str(action.get("capability", ""))
    action_id = str(action.get("id", ""))
    capability = _capability_map(contract).get(capability_id)
    if capability is None:
        return Decision(
            action_id=action_id,
            capability=capability_id,
            base_verdict="deny",
            verdict="deny",
            constraint_passed=False,
            reasons=("unknown_capability_deny_by_default",),
        )

    base_verdict = capability["verdict"]
    failures = constraint_failures(
        dict(capability.get("constraints", {})),
        dict(action.get("parameters", {})),
    )
    if failures:
        return Decision(
            action_id=action_id,
            capability=capability_id,
            base_verdict=base_verdict,
            verdict="deny",
            constraint_passed=False,
            reasons=tuple(failures),
        )

    if base_verdict == "ask":
        approval, approval_reasons = _find_approval(
            approvals,
            case_id=case_id,
            action=action,
            now=now,
        )
        if approval is not None:
            return Decision(
                action_id=action_id,
                capability=capability_id,
                base_verdict="ask",
                verdict="allow",
                constraint_passed=True,
                reasons=("explicit_approval_matched",),
                approval_id=str(approval["approval_id"]),
            )
        reasons = tuple(approval_reasons + ["approval_required"])
        return Decision(
            action_id=action_id,
            capability=capability_id,
            base_verdict="ask",
            verdict="ask",
            constraint_passed=True,
            reasons=reasons,
        )

    reason = "contract_allows" if base_verdict == "allow" else "contract_denies"
    return Decision(
        action_id=action_id,
        capability=capability_id,
        base_verdict=base_verdict,
        verdict=base_verdict,
        constraint_passed=True,
        reasons=(reason,),
    )


def compile_plan(
    contract: dict[str, Any],
    suite: dict[str, Any],
    approvals: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in suite.get("cases", []):
        decisions = [
            evaluate_action(
                contract,
                approvals,
                case_id=str(case["id"]),
                action=action,
                now=now,
            ).to_dict()
            for action in case.get("actions", [])
        ]
        cases.append({"case_id": case["id"], "decisions": decisions})
    plan = {
        "schema_version": "1.0",
        "contract_id": contract["contract_id"],
        "policy_version": contract["policy_version"],
        "suite_id": suite["suite_id"],
        "evaluated_at": now.isoformat().replace("+00:00", "Z"),
        "cases": cases,
    }
    plan["plan_hash"] = sha256_json(plan)
    return plan
