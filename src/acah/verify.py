from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import load_json, sha256_file, sha256_json
from .events import verify_event_log
from .models import VerificationResult


def verify_run(run_dir: Path) -> VerificationResult:
    errors: list[str] = []
    details: dict[str, Any] = {}
    manifest_path = run_dir / "run-manifest.json"
    if not manifest_path.exists():
        return VerificationResult(False, ("run-manifest.json is missing",), {})
    try:
        manifest = load_json(manifest_path)
    except Exception as exc:  # noqa: BLE001 - convert to verification result
        return VerificationResult(False, (f"invalid run manifest: {exc}",), {})

    run_id = manifest.get("run_id")
    for name, expected_hash in manifest.get("input_hashes", {}).items():
        path = run_dir / "inputs" / name
        if not path.exists():
            errors.append(f"missing input snapshot: {name}")
            continue
        try:
            actual = sha256_json(load_json(path))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"invalid input snapshot {name}: {exc}")
            continue
        if actual != expected_hash:
            errors.append(f"input snapshot hash mismatch: {name}")

    for name, expected_hash in manifest.get("output_hashes", {}).items():
        path = run_dir / name
        if not path.exists():
            errors.append(f"missing output: {name}")
            continue
        actual = sha256_file(path)
        if actual != expected_hash:
            errors.append(f"output hash mismatch: {name}")

    event_result = verify_event_log(run_dir / "events.jsonl", expected_run_id=run_id)
    errors.extend(event_result.errors)
    if event_result.details.get("event_count") != manifest.get("event_count"):
        errors.append("event count mismatch")
    if event_result.details.get("final_event_hash") != manifest.get("final_event_hash"):
        errors.append("final event hash mismatch")

    artifact_manifest_path = run_dir / "artifact-manifest.json"
    if artifact_manifest_path.exists():
        artifact_manifest = load_json(artifact_manifest_path)
        for entry in artifact_manifest.get("artifacts", []):
            relative = entry.get("path")
            if not isinstance(relative, str):
                errors.append("artifact entry missing path")
                continue
            path = (run_dir / relative).resolve()
            artifact_root = (run_dir / "artifacts").resolve()
            if artifact_root not in path.parents:
                errors.append(f"artifact path escapes run directory: {relative}")
                continue
            if not path.exists():
                errors.append(f"missing artifact: {relative}")
                continue
            if path.stat().st_size != entry.get("size"):
                errors.append(f"artifact size mismatch: {relative}")
            if sha256_file(path) != entry.get("sha256"):
                errors.append(f"artifact hash mismatch: {relative}")

    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        summary = load_json(summary_path)
        if summary.get("run_id") != run_id:
            errors.append("summary run_id mismatch")
        if summary.get("plan_hash") != load_json(run_dir / "plan.json").get("plan_hash"):
            errors.append("summary plan_hash mismatch")

    details.update(
        {
            "run_id": run_id,
            "event_count": event_result.details.get("event_count", 0),
            "final_event_hash": event_result.details.get("final_event_hash"),
            "manifest_sha256": sha256_file(manifest_path),
            "manifest_identity": sha256_json(manifest),
        }
    )
    return VerificationResult(not errors, tuple(errors), details)
