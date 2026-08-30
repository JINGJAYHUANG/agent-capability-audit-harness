from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

from . import __version__
from .adapters import load_observation_fixture
from .canonical import canonical_dumps, load_json, write_json
from .compare import compare_runs
from .policy import compile_plan, parse_time
from .runner import evaluate_suite
from .validation import (
    validate_adapter,
    validate_approvals,
    validate_contract,
    validate_observation_fixture,
    validate_suite,
)
from .verify import verify_run


def _path(value: str) -> Path:
    return Path(value)


def _load_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_json(args.contract)
    suite = load_json(args.suite)
    adapter = load_json(args.adapter)
    approvals = (
        load_json(args.approvals)
        if getattr(args, "approvals", None)
        else {"schema_version": "1.0", "approvals": []}
    )
    return contract, suite, adapter, approvals


def _validation_errors(
    contract: dict[str, Any],
    suite: dict[str, Any],
    adapter: dict[str, Any],
    approvals: dict[str, Any],
    adapter_path: Path,
) -> list[str]:
    errors = []
    errors.extend(f"contract: {item}" for item in validate_contract(contract))
    errors.extend(f"suite: {item}" for item in validate_suite(suite))
    errors.extend(f"adapter: {item}" for item in validate_adapter(adapter))
    errors.extend(f"approvals: {item}" for item in validate_approvals(approvals))
    if not validate_adapter(adapter) and adapter.get("kind") in {"fixture", "replay"}:
        try:
            fixture = load_observation_fixture(adapter_path, adapter)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"observation fixture: {exc}")
        else:
            errors.extend(
                f"observation fixture: {item}"
                for item in validate_observation_fixture(fixture)
            )
    return errors


def command_validate(args: argparse.Namespace) -> int:
    try:
        contract, suite, adapter, approvals = _load_inputs(args)
        errors = _validation_errors(contract, suite, adapter, approvals, args.adapter)
    except Exception as exc:  # noqa: BLE001
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 2
    print(
        f"VALID contract={contract['contract_id']} suite={suite['suite_id']} "
        f"adapter={adapter['adapter_id']} capabilities={len(contract['capabilities'])} "
        f"cases={len(suite['cases'])}"
    )
    return 0


def command_plan(args: argparse.Namespace) -> int:
    contract, suite, adapter, approvals = _load_inputs(args)
    errors = _validation_errors(contract, suite, adapter, approvals, args.adapter)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 2
    now = parse_time(args.fixed_time) if args.fixed_time else datetime.now(timezone.utc)
    plan = compile_plan(contract, suite, approvals, now=now)
    if args.output:
        write_json(args.output, plan)
    else:
        print(canonical_dumps(plan))
    return 0


def command_run(args: argparse.Namespace) -> int:
    try:
        summary = evaluate_suite(
            contract_path=args.contract,
            suite_path=args.suite,
            adapter_path=args.adapter,
            approvals_path=args.approvals,
            run_dir=args.run_dir,
            fixed_time=args.fixed_time,
            allow_command=args.allow_command,
            replace=args.replace,
        )
    except PermissionError as exc:
        print(f"permission error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"run error: {exc}", file=sys.stderr)
        return 2
    print(
        f"{'PASS' if summary['passed'] else 'FAIL'} run_id={summary['run_id']} "
        f"cases={summary['passed_cases']}/{summary['case_count']} "
        f"gate_accuracy={summary['gate_accuracy']:.3f} "
        f"deny_leakage={summary['deny_leakage']} ask_bypass={summary['ask_bypass']}"
    )
    return 0 if summary["passed"] else 1


def command_verify(args: argparse.Namespace) -> int:
    result = verify_run(args.run_dir)
    if args.format == "json":
        print(canonical_dumps(result.to_dict()))
    else:
        print("PASS" if result.passed else "FAIL")
        for error in result.errors:
            print(f"- {error}")
        for key, value in sorted(result.details.items()):
            print(f"{key}: {value}")
    return 0 if result.passed else 2


def command_compare(args: argparse.Namespace) -> int:
    try:
        result = compare_runs(args.baseline, args.candidate)
    except Exception as exc:  # noqa: BLE001
        print(f"compare error: {exc}", file=sys.stderr)
        return 2
    if args.output:
        write_json(args.output, result)
    if args.format == "json":
        print(canonical_dumps(result))
    else:
        print(result["status"].upper())
        for item in result["regressions"]:
            print(f"REGRESSION {item}")
        for item in result["improvements"]:
            print(f"IMPROVEMENT {item}")
    if args.fail_on_regression and result["regressions"]:
        return 1
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    try:
        contract = load_json(args.contract)
    except Exception as exc:  # noqa: BLE001
        print(f"inspect error: {exc}", file=sys.stderr)
        return 2
    errors = validate_contract(contract)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 2
    if args.json:
        print(canonical_dumps(contract))
    else:
        print(f"Contract: {contract['contract_id']} ({contract['policy_version']})")
        print(f"Default: {contract['default_verdict']}")
        for capability in contract["capabilities"]:
            print(
                f"{capability['id']:<32} {capability['verdict']:<5} "
                f"{capability['effect']:<20} {capability['description']}"
            )
    return 0


def _template_files() -> dict[str, str]:
    root = resources.files("acah.data")
    return {
        "capability-contract.json": root.joinpath("default-contract.json").read_text(encoding="utf-8"),
        "golden-suite.json": root.joinpath("default-suite.json").read_text(encoding="utf-8"),
        "adapter.json": root.joinpath("default-adapter.json").read_text(encoding="utf-8"),
        "observations.json": root.joinpath("default-observations.json").read_text(encoding="utf-8"),
        "approvals.json": root.joinpath("default-approvals.json").read_text(encoding="utf-8"),
    }


def command_init(args: argparse.Namespace) -> int:
    target = args.target
    files = _template_files()
    planned = [target / name for name in files]
    conflicts = [path for path in planned if path.exists()]
    if not args.apply:
        print(f"Preview: would create {len(planned)} files under {target}")
        for path in planned:
            suffix = " [exists]" if path.exists() else ""
            print(f"- {path}{suffix}")
        return 1 if conflicts else 0
    if conflicts and not args.replace:
        for path in conflicts:
            print(f"refusing to overwrite: {path}", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        destination = target / name
        if destination.exists() and args.replace:
            backup = destination.with_suffix(destination.suffix + ".bak")
            shutil.copy2(destination, backup)
        destination.write_text(content, encoding="utf-8", newline="\n")
    print(f"Created {len(files)} files under {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acah",
        description="Deny-by-default agent capability audit harness.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate contracts, suite, adapter, and approvals")
    _add_common_inputs(validate_parser)
    validate_parser.set_defaults(func=command_validate)

    plan_parser = subparsers.add_parser("plan", help="compile deterministic policy decisions without running an adapter")
    _add_common_inputs(plan_parser)
    plan_parser.add_argument("--fixed-time")
    plan_parser.add_argument("--output", type=_path)
    plan_parser.set_defaults(func=command_plan)

    run_parser = subparsers.add_parser("run", help="run a golden-task capability evaluation")
    _add_common_inputs(run_parser)
    run_parser.add_argument("--run-dir", required=True, type=_path)
    run_parser.add_argument("--fixed-time")
    run_parser.add_argument("--allow-command", action="store_true")
    run_parser.add_argument("--replace", action="store_true")
    run_parser.set_defaults(func=command_run)

    verify_parser = subparsers.add_parser("verify", help="verify a run's hashes, event chain, and artifacts")
    verify_parser.add_argument("--run-dir", required=True, type=_path)
    verify_parser.add_argument("--format", choices=("text", "json"), default="text")
    verify_parser.set_defaults(func=command_verify)

    compare_parser = subparsers.add_parser("compare", help="compare baseline and candidate runs")
    compare_parser.add_argument("--baseline", required=True, type=_path)
    compare_parser.add_argument("--candidate", required=True, type=_path)
    compare_parser.add_argument("--format", choices=("text", "json"), default="text")
    compare_parser.add_argument("--output", type=_path)
    compare_parser.add_argument("--fail-on-regression", action="store_true")
    compare_parser.set_defaults(func=command_compare)

    inspect_parser = subparsers.add_parser("inspect", help="list capabilities in a contract")
    inspect_parser.add_argument("--contract", required=True, type=_path)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.set_defaults(func=command_inspect)

    init_parser = subparsers.add_parser("init", help="preview or create a starter audit project")
    init_parser.add_argument("--target", type=_path, default=Path("acah-starter"))
    init_parser.add_argument("--apply", action="store_true")
    init_parser.add_argument("--replace", action="store_true")
    init_parser.set_defaults(func=command_init)
    return parser


def _add_common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract", required=True, type=_path)
    parser.add_argument("--suite", required=True, type=_path)
    parser.add_argument("--adapter", required=True, type=_path)
    parser.add_argument("--approvals", type=_path)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
