from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .canonical import canonical_dumps, load_json, normalize_relative_path, sha256_file, write_json
from .validation import require_valid, validate_observation_fixture

SENSITIVE_ENV_TOKENS = ("TOKEN", "SECRET", "PASSWORD", "COOKIE", "KEY", "WEBHOOK")


def resolve_relative(base_file: Path, relative: str) -> Path:
    candidate = (base_file.parent / relative).resolve()
    return candidate


def load_observation_fixture(adapter_path: Path, adapter: dict[str, Any]) -> dict[str, Any]:
    fixture_path = resolve_relative(adapter_path, str(adapter["observation_file"]))
    fixture = load_json(fixture_path)
    require_valid("observation fixture", validate_observation_fixture(fixture))
    return fixture


def _minimal_environment(allowlist: list[str]) -> dict[str, str]:
    environment: dict[str, str] = {}
    for name in ("PATH", "SYSTEMROOT", "WINDIR"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    environment["PYTHONIOENCODING"] = "utf-8"
    for name in allowlist:
        upper = name.upper()
        if any(token in upper for token in SENSITIVE_ENV_TOKENS):
            raise ValueError(f"sensitive environment variable cannot be allowlisted: {name}")
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    return environment


def _expand_command(command: list[str], packet_path: Path, output_path: Path, adapter_root: Path) -> list[str]:
    replacements = {
        "{packet}": str(packet_path),
        "{output}": str(output_path),
        "{python}": sys.executable,
        "{adapter_root}": str(adapter_root),
    }
    expanded: list[str] = []
    for item in command:
        value = item
        for placeholder, replacement in replacements.items():
            value = value.replace(placeholder, replacement)
        if "{" in value or "}" in value:
            raise ValueError(f"unsupported command placeholder: {item}")
        if "\x00" in value:
            raise ValueError("command argument contains NUL")
        expanded.append(value)
    return expanded


def _validate_observations(observations: Any, case_id: str) -> list[dict[str, Any]]:
    if not isinstance(observations, list):
        raise ValueError(f"adapter observations for {case_id} must be an array")
    cleaned: list[dict[str, Any]] = []
    for index, raw in enumerate(observations):
        if not isinstance(raw, dict):
            raise ValueError(f"adapter observation {case_id}[{index}] must be an object")
        event_type = raw.get("event_type")
        if event_type not in {
            "action_executed",
            "approval_requested",
            "action_blocked",
            "artifact",
            "note",
        }:
            raise ValueError(f"invalid adapter observation type in {case_id}[{index}]")
        if event_type in {"action_executed", "approval_requested", "action_blocked"}:
            action_id = raw.get("action_id")
            if not isinstance(action_id, str) or not action_id:
                raise ValueError(f"adapter observation {case_id}[{index}] requires action_id")
        if event_type == "artifact":
            normalize_relative_path(str(raw.get("path", "")))
            if "content" not in raw:
                raise ValueError(f"artifact observation {case_id}[{index}] requires content")
        cleaned.append(dict(raw))
    return cleaned


def execute_adapter(
    *,
    adapter_path: Path,
    adapter: dict[str, Any],
    case: dict[str, Any],
    decisions: list[dict[str, Any]],
    invocation_dir: Path,
    allow_command: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kind = adapter["kind"]
    started = time.perf_counter()
    if kind in {"fixture", "replay"}:
        fixture = load_observation_fixture(adapter_path, adapter)
        observations = fixture.get("cases", {}).get(str(case["id"]), [])
        cleaned = _validate_observations(observations, str(case["id"]))
        return cleaned, {
            "kind": kind,
            "duration_ms": 0.0,
            "transport_duration_ms": 0.0,
            "exit_code": 0,
            "stdout_sha256": None,
            "stderr_sha256": None,
        }

    if kind != "command":
        raise ValueError(f"unsupported adapter kind: {kind}")
    if not allow_command:
        raise PermissionError("command adapter execution requires --allow-command")

    invocation_dir.mkdir(parents=True, exist_ok=True)
    packet_path = invocation_dir / "packet.json"
    output_path = invocation_dir / "observations.json"
    packet = {
        "schema_version": "1.0",
        "case": case,
        "decisions": decisions,
        "adapter": {
            "adapter_id": adapter["adapter_id"],
            "version": adapter["version"],
            "declared_capabilities": adapter.get("declared_capabilities", []),
        },
    }
    write_json(packet_path, packet)
    argv = _expand_command(list(adapter["command"]), packet_path, output_path, adapter_path.parent)
    timeout_seconds = int(adapter.get("timeout_seconds", 10))
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ValueError("command adapter timeout_seconds must be between 1 and 300")
    environment = _minimal_environment(list(adapter.get("env_allowlist", [])))

    with tempfile.TemporaryDirectory(prefix="acah-command-") as temporary:
        result = subprocess.run(
            argv,
            cwd=Path(temporary),
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    stdout_path = invocation_dir / "stdout.txt"
    stderr_path = invocation_dir / "stderr.txt"
    stdout_path.write_text(result.stdout[:65536], encoding="utf-8")
    stderr_path.write_text(result.stderr[:65536], encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"command adapter exited with code {result.returncode}")
    if not output_path.exists():
        raise RuntimeError("command adapter did not create observations output")
    output = load_json(output_path)
    observations = output.get("observations") if isinstance(output, dict) else output
    cleaned = _validate_observations(observations, str(case["id"]))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return cleaned, {
        "kind": kind,
        "duration_ms": elapsed_ms,
        "transport_duration_ms": elapsed_ms,
        "exit_code": result.returncode,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "packet_sha256": sha256_file(packet_path),
        "observations_sha256": sha256_file(output_path),
        "argv_hash": __import__("hashlib").sha256(canonical_dumps(argv).encode("utf-8")).hexdigest(),
        "network_enforcement": adapter.get("network_enforcement", "not_enforced"),
    }
