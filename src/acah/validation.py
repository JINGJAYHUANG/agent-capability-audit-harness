from __future__ import annotations

import re
from typing import Any

VERDICTS = {"allow", "ask", "deny"}
EFFECTS = {
    "read",
    "write",
    "network",
    "process",
    "secret",
    "external_side_effect",
    "analysis",
}
OBSERVATIONS = {
    "action_executed",
    "approval_requested",
    "action_blocked",
}
ADAPTER_KINDS = {"fixture", "replay", "command"}
SUPPORTED_CONSTRAINTS = {
    "paths",
    "hosts",
    "methods",
    "databases",
    "operations",
    "max_rows",
    "max_bytes",
    "reversible_only",
}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")


def _require_mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def _require_list(value: Any, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return []
    return value


def _validate_id(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        errors.append(f"{label} must match {IDENTIFIER.pattern}")


def _validate_string_list(value: Any, label: str, errors: list[str]) -> None:
    items = _require_list(value, label, errors)
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item:
            errors.append(f"{label}[{index}] must be a non-empty string")


def validate_contract(data: Any) -> list[str]:
    errors: list[str] = []
    root = _require_mapping(data, "contract", errors)
    if root.get("schema_version") != "1.0":
        errors.append("contract.schema_version must be '1.0'")
    if root.get("default_verdict") != "deny":
        errors.append("contract.default_verdict must be 'deny'")
    _validate_id(root.get("contract_id"), "contract.contract_id", errors)
    if not isinstance(root.get("policy_version"), str) or not root.get("policy_version"):
        errors.append("contract.policy_version must be a non-empty string")

    capabilities = _require_list(root.get("capabilities"), "contract.capabilities", errors)
    if not capabilities:
        errors.append("contract.capabilities must not be empty")
    seen: set[str] = set()
    for index, raw in enumerate(capabilities):
        cap = _require_mapping(raw, f"contract.capabilities[{index}]", errors)
        cap_id = cap.get("id")
        _validate_id(cap_id, f"contract.capabilities[{index}].id", errors)
        if isinstance(cap_id, str):
            if cap_id in seen:
                errors.append(f"duplicate capability id: {cap_id}")
            seen.add(cap_id)
        if cap.get("effect") not in EFFECTS:
            errors.append(f"capability {cap_id!r} has invalid effect")
        if cap.get("verdict") not in VERDICTS:
            errors.append(f"capability {cap_id!r} has invalid verdict")
        if not isinstance(cap.get("description"), str) or not cap.get("description"):
            errors.append(f"capability {cap_id!r} needs a description")
        constraints = cap.get("constraints", {})
        if not isinstance(constraints, dict):
            errors.append(f"capability {cap_id!r} constraints must be an object")
            continue
        unknown = sorted(set(constraints) - SUPPORTED_CONSTRAINTS)
        if unknown:
            errors.append(f"capability {cap_id!r} has unsupported constraints: {', '.join(unknown)}")
        for key in ("paths", "hosts", "methods", "databases", "operations"):
            if key in constraints:
                _validate_string_list(constraints[key], f"capability {cap_id!r}.{key}", errors)
        for key in ("max_rows", "max_bytes"):
            if key in constraints and (
                not isinstance(constraints[key], int) or isinstance(constraints[key], bool) or constraints[key] < 0
            ):
                errors.append(f"capability {cap_id!r}.{key} must be a non-negative integer")
        if "reversible_only" in constraints and not isinstance(constraints["reversible_only"], bool):
            errors.append(f"capability {cap_id!r}.reversible_only must be boolean")
    return errors


def validate_suite(data: Any) -> list[str]:
    errors: list[str] = []
    root = _require_mapping(data, "suite", errors)
    if root.get("schema_version") != "1.0":
        errors.append("suite.schema_version must be '1.0'")
    _validate_id(root.get("suite_id"), "suite.suite_id", errors)
    cases = _require_list(root.get("cases"), "suite.cases", errors)
    if not cases:
        errors.append("suite.cases must not be empty")
    seen_cases: set[str] = set()
    for case_index, raw_case in enumerate(cases):
        case = _require_mapping(raw_case, f"suite.cases[{case_index}]", errors)
        case_id = case.get("id")
        _validate_id(case_id, f"suite.cases[{case_index}].id", errors)
        if isinstance(case_id, str):
            if case_id in seen_cases:
                errors.append(f"duplicate case id: {case_id}")
            seen_cases.add(case_id)
        for field in ("title", "objective", "untrusted_input"):
            if not isinstance(case.get(field), str):
                errors.append(f"case {case_id!r}.{field} must be a string")
        actions = _require_list(case.get("actions"), f"case {case_id!r}.actions", errors)
        if not actions:
            errors.append(f"case {case_id!r} must have at least one action")
        seen_actions: set[str] = set()
        for action_index, raw_action in enumerate(actions):
            action = _require_mapping(raw_action, f"case {case_id!r}.actions[{action_index}]", errors)
            action_id = action.get("id")
            _validate_id(action_id, f"case {case_id!r}.actions[{action_index}].id", errors)
            if isinstance(action_id, str):
                if action_id in seen_actions:
                    errors.append(f"duplicate action id in {case_id!r}: {action_id}")
                seen_actions.add(action_id)
            _validate_id(action.get("capability"), f"action {action_id!r}.capability", errors)
            if action.get("expected_verdict") not in VERDICTS:
                errors.append(f"action {action_id!r} has invalid expected_verdict")
            if action.get("expected_observation") not in OBSERVATIONS:
                errors.append(f"action {action_id!r} has invalid expected_observation")
            if not isinstance(action.get("parameters", {}), dict):
                errors.append(f"action {action_id!r}.parameters must be an object")
        budgets = case.get("budgets", {})
        if not isinstance(budgets, dict):
            errors.append(f"case {case_id!r}.budgets must be an object")
        else:
            for key in ("max_observations", "max_output_bytes", "max_duration_ms"):
                if key in budgets and (
                    not isinstance(budgets[key], int) or isinstance(budgets[key], bool) or budgets[key] < 0
                ):
                    errors.append(f"case {case_id!r}.budgets.{key} must be non-negative integer")
    return errors


def validate_adapter(data: Any) -> list[str]:
    errors: list[str] = []
    root = _require_mapping(data, "adapter", errors)
    if root.get("schema_version") != "1.0":
        errors.append("adapter.schema_version must be '1.0'")
    _validate_id(root.get("adapter_id"), "adapter.adapter_id", errors)
    if root.get("kind") not in ADAPTER_KINDS:
        errors.append("adapter.kind must be fixture, replay, or command")
    if not isinstance(root.get("version"), str) or not root.get("version"):
        errors.append("adapter.version must be a non-empty string")
    _validate_string_list(root.get("declared_capabilities", []), "adapter.declared_capabilities", errors)
    kind = root.get("kind")
    if kind in {"fixture", "replay"}:
        if not isinstance(root.get("observation_file"), str) or not root.get("observation_file"):
            errors.append(f"{kind} adapter requires observation_file")
    if kind == "command":
        command = root.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
            errors.append("command adapter requires a non-empty string argv array")
        if root.get("network_enforcement") not in {"not_enforced", "external"}:
            errors.append("command adapter network_enforcement must be not_enforced or external")
        env_allowlist = root.get("env_allowlist", [])
        _validate_string_list(env_allowlist, "adapter.env_allowlist", errors)
    return errors


def validate_approvals(data: Any) -> list[str]:
    errors: list[str] = []
    root = _require_mapping(data, "approvals", errors)
    if root.get("schema_version") != "1.0":
        errors.append("approvals.schema_version must be '1.0'")
    entries = _require_list(root.get("approvals"), "approvals.approvals", errors)
    seen: set[str] = set()
    for index, raw in enumerate(entries):
        entry = _require_mapping(raw, f"approvals[{index}]", errors)
        approval_id = entry.get("approval_id")
        _validate_id(approval_id, f"approvals[{index}].approval_id", errors)
        if isinstance(approval_id, str):
            if approval_id in seen:
                errors.append(f"duplicate approval id: {approval_id}")
            seen.add(approval_id)
        for field in ("case_id", "action_id", "capability"):
            _validate_id(entry.get(field), f"approval {approval_id!r}.{field}", errors)
        for field in ("parameters_hash", "approved_by", "expires_at"):
            if not isinstance(entry.get(field), str) or not entry.get(field):
                errors.append(f"approval {approval_id!r}.{field} must be a non-empty string")
    return errors


def validate_observation_fixture(data: Any) -> list[str]:
    errors: list[str] = []
    root = _require_mapping(data, "observation fixture", errors)
    if root.get("schema_version") != "1.0":
        errors.append("observation fixture schema_version must be '1.0'")
    cases = _require_mapping(root.get("cases"), "observation fixture.cases", errors)
    for case_id, raw_events in cases.items():
        _validate_id(case_id, f"fixture case id {case_id!r}", errors)
        events = _require_list(raw_events, f"fixture case {case_id!r}", errors)
        for index, raw_event in enumerate(events):
            event = _require_mapping(raw_event, f"fixture {case_id}[{index}]", errors)
            event_type = event.get("event_type")
            if event_type not in OBSERVATIONS | {"artifact", "note"}:
                errors.append(f"fixture {case_id}[{index}] has invalid event_type")
            if event_type in OBSERVATIONS:
                _validate_id(event.get("action_id"), f"fixture {case_id}[{index}].action_id", errors)
            if event_type == "artifact":
                if not isinstance(event.get("path"), str) or not event.get("path"):
                    errors.append(f"fixture {case_id}[{index}] artifact requires path")
                if "content" not in event:
                    errors.append(f"fixture {case_id}[{index}] artifact requires content")
    return errors


def require_valid(label: str, errors: list[str]) -> None:
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"invalid {label}:\n{formatted}")
