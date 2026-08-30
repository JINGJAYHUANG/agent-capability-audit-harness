from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import load_json


def compare_runs(baseline_dir: Path, candidate_dir: Path) -> dict[str, Any]:
    baseline_summary = load_json(baseline_dir / "summary.json")
    candidate_summary = load_json(candidate_dir / "summary.json")
    baseline_cases = {
        item["case_id"]: item
        for item in load_json(baseline_dir / "case-results.json")["cases"]
    }
    candidate_cases = {
        item["case_id"]: item
        for item in load_json(candidate_dir / "case-results.json")["cases"]
    }

    regressions: list[str] = []
    improvements: list[str] = []
    if baseline_summary.get("passed") and not candidate_summary.get("passed"):
        regressions.append("overall result changed from pass to fail")
    if not baseline_summary.get("passed") and candidate_summary.get("passed"):
        improvements.append("overall result changed from fail to pass")

    for case_id in sorted(set(baseline_cases) | set(candidate_cases)):
        before = baseline_cases.get(case_id)
        after = candidate_cases.get(case_id)
        if before is None:
            improvements.append(f"new case added: {case_id}")
        elif after is None:
            regressions.append(f"case removed: {case_id}")
        elif before["passed"] and not after["passed"]:
            regressions.append(f"case regressed: {case_id}")
        elif not before["passed"] and after["passed"]:
            improvements.append(f"case improved: {case_id}")

    for metric in ("deny_leakage", "ask_bypass", "budget_violations", "gate_mismatches"):
        before = int(baseline_summary.get(metric, 0))
        after = int(candidate_summary.get(metric, 0))
        if after > before:
            regressions.append(f"{metric} increased from {before} to {after}")
        elif after < before:
            improvements.append(f"{metric} decreased from {before} to {after}")
    for metric in ("gate_accuracy", "evidence_completeness"):
        before = float(baseline_summary.get(metric, 0.0))
        after = float(candidate_summary.get(metric, 0.0))
        if after < before:
            regressions.append(f"{metric} decreased from {before} to {after}")
        elif after > before:
            improvements.append(f"{metric} increased from {before} to {after}")

    return {
        "schema_version": "1.0",
        "baseline_run_id": baseline_summary.get("run_id"),
        "candidate_run_id": candidate_summary.get("run_id"),
        "status": "regressed" if regressions else "no_regression",
        "regressions": regressions,
        "improvements": improvements,
        "baseline": baseline_summary,
        "candidate": candidate_summary,
    }
