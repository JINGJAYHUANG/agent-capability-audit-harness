from __future__ import annotations

import tempfile
from pathlib import Path

from acah.canonical import sha256_file
from acah.runner import evaluate_suite
from acah.verify import verify_run

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic"
EXPECTED = EXAMPLE / "expected" / "reference-run"
FIXED = "2026-08-30T00:00:00Z"


def file_map(root: Path):
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

with tempfile.TemporaryDirectory(prefix="acah-examples-") as temporary:
    temp = Path(temporary)
    good = temp / "good"
    bad = temp / "bad"
    command = temp / "command"
    good_summary = evaluate_suite(
        contract_path=EXAMPLE / "capability-contract.json",
        suite_path=EXAMPLE / "golden-suite.json",
        adapter_path=EXAMPLE / "adapters" / "reference.json",
        approvals_path=EXAMPLE / "approvals.json",
        run_dir=good,
        fixed_time=FIXED,
    )
    if not good_summary["passed"] or not verify_run(good).passed:
        raise SystemExit("reference example failed")
    if file_map(good) != file_map(EXPECTED):
        raise SystemExit("committed reference run drifted")

    bad_summary = evaluate_suite(
        contract_path=EXAMPLE / "capability-contract.json",
        suite_path=EXAMPLE / "golden-suite.json",
        adapter_path=EXAMPLE / "adapters" / "violating.json",
        approvals_path=EXAMPLE / "approvals.json",
        run_dir=bad,
        fixed_time=FIXED,
    )
    if bad_summary["passed"] or bad_summary["deny_leakage"] < 1 or bad_summary["ask_bypass"] < 1:
        raise SystemExit("negative control did not fail as expected")
    if not verify_run(bad).passed:
        raise SystemExit("negative control evidence bundle is internally invalid")

    command_summary = evaluate_suite(
        contract_path=EXAMPLE / "capability-contract.json",
        suite_path=EXAMPLE / "golden-suite.json",
        adapter_path=ROOT / "examples" / "command-adapter" / "adapter.json",
        approvals_path=EXAMPLE / "approvals.json",
        run_dir=command,
        fixed_time=FIXED,
        allow_command=True,
    )
    if not command_summary["passed"] or not verify_run(command).passed:
        raise SystemExit("offline command adapter example failed")
print("public examples passed: reference, negative control, and offline command adapter")
