from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic"
CONTRACT = EXAMPLE / "capability-contract.json"
SUITE = EXAMPLE / "golden-suite.json"
APPROVALS = EXAMPLE / "approvals.json"
EMPTY_APPROVALS = EXAMPLE / "empty-approvals.json"
REFERENCE_ADAPTER = EXAMPLE / "adapters" / "reference.json"
VIOLATING_ADAPTER = EXAMPLE / "adapters" / "violating.json"
COMMAND_ADAPTER = ROOT / "examples" / "command-adapter" / "adapter.json"
FIXED_TIME = "2026-08-30T00:00:00Z"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def temporary_directory():
    with tempfile.TemporaryDirectory(prefix="acah-test-") as temp:
        yield Path(temp)
