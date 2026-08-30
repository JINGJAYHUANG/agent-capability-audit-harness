from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import execute_adapter, load_observation_fixture
from .canonical import (
    canonical_dumps,
    load_json,
    normalize_relative_path,
    sha256_file,
    sha256_json,
    sha256_text,
    write_json,
)
from .events import DeterministicClock, EventLog, verify_event_log
from .policy import compile_plan, parse_time
from .reporting import render_html, render_markdown
from .scoring import assess_case, build_capability_matrix, summarize
from .validation import (
    require_valid,
    validate_adapter,
    validate_approvals,
    validate_contract,
    validate_suite,
)


def _prepare_run_directory(run_dir: Path, replace: bool) -> None:
    if run_dir.exists() and any(run_dir.iterdir()):
        if not replace:
            raise FileExistsError(f"run directory is not empty: {run_dir}")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)


def _serialize_artifact(content: Any) -> bytes:
    if isinstance(content, str):
        return content.encode("utf-8")
    return (canonical_dumps(content) + "\n").encode("utf-8")


def _write_artifact(
    run_dir: Path,
    *,
    case_id: str,
    relative_path: str,
    content: Any,
) -> dict[str, Any]:
    safe_relative = normalize_relative_path(relative_path)
    destination = run_dir / "artifacts" / case_id / safe_relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved_root = (run_dir / "artifacts").resolve()
    resolved_destination = destination.resolve()
    if resolved_root not in resolved_destination.parents:
        raise ValueError(f"artifact escapes run directory: {relative_path}")
    payload = _serialize_artifact(content)
    destination.write_bytes(payload)
    return {
        "case_id": case_id,
        "path": destination.relative_to(run_dir).as_posix(),
        "size": len(payload),
        "sha256": sha256_file(destination),
    }


def _load_and_validate(
    contract_path: Path,
    suite_path: Path,
    adapter_path: Path,
    approvals_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_json(contract_path)
    suite = load_json(suite_path)
    adapter = load_json(adapter_path)
    approvals = (
        load_json(approvals_path)
        if approvals_path is not None
        else {"schema_version": "1.0", "approvals": []}
    )
    require_valid("capability contract", validate_contract(contract))
    require_valid("golden suite", validate_suite(suite))
    require_valid("adapter manifest", validate_adapter(adapter))
    require_valid("approval ledger", validate_approvals(approvals))
    return contract, suite, adapter, approvals


def evaluate_suite(
    *,
    contract_path: Path,
    suite_path: Path,
    adapter_path: Path,
    run_dir: Path,
    approvals_path: Path | None = None,
    fixed_time: str | None = None,
    allow_command: bool = False,
    replace: bool = False,
) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    suite_path = suite_path.resolve()
    adapter_path = adapter_path.resolve()
    approvals_path = approvals_path.resolve() if approvals_path else None
    _prepare_run_directory(run_dir, replace)
    contract, suite, adapter, approvals = _load_and_validate(
        contract_path, suite_path, adapter_path, approvals_path
    )

    base_time = parse_time(fixed_time) if fixed_time else datetime.now(timezone.utc)
    deterministic = fixed_time is not None and adapter["kind"] in {"fixture", "replay"}

    input_values: dict[str, Any] = {
        "contract.json": contract,
        "suite.json": suite,
        "adapter.json": adapter,
        "approvals.json": approvals,
    }
    if adapter["kind"] in {"fixture", "replay"}:
        input_values["adapter-observations.json"] = load_observation_fixture(
            adapter_path, adapter
        )

    input_hashes = {name: sha256_json(value) for name, value in input_values.items()}
    run_id = sha256_json(
        {
            "inputs": input_hashes,
            "evaluated_at": base_time.isoformat().replace("+00:00", "Z"),
            "harness_version": "0.1.0",
        }
    )[:24]

    inputs_dir = run_dir / "inputs"
    for name, value in input_values.items():
        write_json(inputs_dir / name, value)

    plan = compile_plan(contract, suite, approvals, now=base_time)
    write_json(run_dir / "plan.json", plan)
    plan_by_case = {item["case_id"]: item["decisions"] for item in plan["cases"]}

    event_log = EventLog(
        path=run_dir / "events.jsonl",
        run_id=run_id,
        clock=DeterministicClock(base_time),
    )
    event_log.append(
        "run_started",
        case_id=None,
        source="acah.runner",
        payload={
            "contract_hash": input_hashes["contract.json"],
            "suite_hash": input_hashes["suite.json"],
            "adapter_hash": input_hashes["adapter.json"],
            "plan_hash": plan["plan_hash"],
            "deterministic": deterministic,
        },
    )

    case_results: list[dict[str, Any]] = []
    artifact_entries: list[dict[str, Any]] = []
    for case in suite["cases"]:
        case_id = str(case["id"])
        decisions = list(plan_by_case[case_id])
        event_log.append(
            "case_started",
            case_id=case_id,
            source="golden_suite",
            payload={
                "title": case["title"],
                "objective_hash": sha256_text(case["objective"]),
                "untrusted_input_hash": sha256_text(case["untrusted_input"]),
                "untrusted_input_bytes": len(case["untrusted_input"].encode("utf-8")),
                "action_count": len(case["actions"]),
            },
        )
        for decision in decisions:
            event_log.append(
                "policy_decision",
                case_id=case_id,
                source="deterministic_gate",
                payload=decision,
            )

        invocation_dir = run_dir / "invocations" / case_id
        observations, runtime = execute_adapter(
            adapter_path=adapter_path,
            adapter=adapter,
            case=case,
            decisions=decisions,
            invocation_dir=invocation_dir,
            allow_command=allow_command,
        )
        normalized_observations: list[dict[str, Any]] = []
        artifact_bytes = 0
        for observation in observations:
            if observation["event_type"] == "artifact":
                entry = _write_artifact(
                    run_dir,
                    case_id=case_id,
                    relative_path=str(observation["path"]),
                    content=observation["content"],
                )
                artifact_entries.append(entry)
                artifact_bytes += entry["size"]
                normalized = {
                    "event_type": "artifact",
                    "path": entry["path"],
                    "size": entry["size"],
                    "sha256": entry["sha256"],
                }
            else:
                normalized = dict(observation)
            normalized_observations.append(normalized)
            event_log.append(
                "adapter_observation",
                case_id=case_id,
                source=str(adapter["adapter_id"]),
                payload=normalized,
            )

        result = assess_case(
            case=case,
            decisions=decisions,
            observations=normalized_observations,
            runtime=runtime,
            artifact_bytes=artifact_bytes,
        )
        case_results.append(result)
        event_log.append(
            "case_completed",
            case_id=case_id,
            source="acah.scoring",
            payload={
                "passed": result["passed"],
                "error_count": len(result["errors"]),
                "metrics": result["metrics"],
                "evidence_completeness": result["evidence_completeness"],
            },
        )

    capability_matrix = build_capability_matrix(contract, case_results)
    summary = summarize(case_results, capability_matrix)
    summary.update(
        {
            "run_id": run_id,
            "contract_id": contract["contract_id"],
            "policy_version": contract["policy_version"],
            "suite_id": suite["suite_id"],
            "adapter_id": adapter["adapter_id"],
            "adapter_kind": adapter["kind"],
            "deterministic": deterministic,
            "evaluated_at": base_time.isoformat().replace("+00:00", "Z"),
            "plan_hash": plan["plan_hash"],
        }
    )

    write_json(run_dir / "case-results.json", {"schema_version": "1.0", "cases": case_results})
    write_json(run_dir / "capability-matrix.json", capability_matrix)
    write_json(
        run_dir / "artifact-manifest.json",
        {"schema_version": "1.0", "artifacts": sorted(artifact_entries, key=lambda x: x["path"])},
    )
    write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(
        render_markdown(summary, case_results, capability_matrix), encoding="utf-8", newline="\n"
    )
    (run_dir / "report.html").write_text(
        render_html(summary, case_results, capability_matrix), encoding="utf-8", newline="\n"
    )

    summary_hash = sha256_file(run_dir / "summary.json")
    event_log.append(
        "run_completed",
        case_id=None,
        source="acah.runner",
        payload={"passed": summary["passed"], "summary_sha256": summary_hash},
    )
    event_verification = verify_event_log(run_dir / "events.jsonl", expected_run_id=run_id)
    if not event_verification.passed:
        raise RuntimeError("newly written event log failed self-verification")

    output_names = [
        "plan.json",
        "events.jsonl",
        "case-results.json",
        "capability-matrix.json",
        "artifact-manifest.json",
        "summary.json",
        "report.md",
        "report.html",
    ]
    output_hashes = {name: sha256_file(run_dir / name) for name in output_names}
    manifest = {
        "schema_version": "1.0",
        "harness_version": "0.1.0",
        "run_id": run_id,
        "deterministic": deterministic,
        "evaluated_at": summary["evaluated_at"],
        "input_hashes": input_hashes,
        "output_hashes": output_hashes,
        "artifact_manifest_sha256": output_hashes["artifact-manifest.json"],
        "final_event_hash": event_verification.details["final_event_hash"],
        "event_count": event_verification.details["event_count"],
    }
    write_json(run_dir / "run-manifest.json", manifest)
    return summary
