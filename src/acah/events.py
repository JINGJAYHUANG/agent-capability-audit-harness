from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .canonical import canonical_dumps, sha256_json
from .models import VerificationResult


class DeterministicClock:
    def __init__(self, base: datetime) -> None:
        if base.tzinfo is None:
            raise ValueError("clock base must be timezone-aware")
        self._base = base.astimezone(timezone.utc)
        self._index = 0

    def next(self) -> str:
        value = self._base + timedelta(microseconds=self._index)
        self._index += 1
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass
class EventLog:
    path: Path
    run_id: str
    clock: DeterministicClock
    sequence: int = 0
    previous_hash: str = "0" * 64

    def append(
        self,
        event_type: str,
        *,
        case_id: str | None,
        source: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = {
            "seq": self.sequence,
            "ts": self.clock.next(),
            "run_id": self.run_id,
            "case_id": case_id,
            "event_type": event_type,
            "source": source,
            "payload": payload,
            "previous_hash": self.previous_hash,
        }
        event_hash = sha256_json(body)
        event = {**body, "event_hash": event_hash}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_dumps(event) + "\n")
        self.sequence += 1
        self.previous_hash = event_hash
        return event


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"event line {line_number} must be an object")
            events.append(value)
    return events


def verify_event_log(path: Path, *, expected_run_id: str | None = None) -> VerificationResult:
    errors: list[str] = []
    try:
        events = load_events(path)
    except (OSError, ValueError) as exc:
        return VerificationResult(False, (str(exc),), {"event_count": 0})

    previous_hash = "0" * 64
    for index, event in enumerate(events):
        if event.get("seq") != index:
            errors.append(f"event {index} has non-contiguous sequence")
        if event.get("previous_hash") != previous_hash:
            errors.append(f"event {index} previous_hash mismatch")
        if expected_run_id is not None and event.get("run_id") != expected_run_id:
            errors.append(f"event {index} run_id mismatch")
        event_hash = event.get("event_hash")
        body = dict(event)
        body.pop("event_hash", None)
        calculated = sha256_json(body)
        if event_hash != calculated:
            errors.append(f"event {index} hash mismatch")
        if isinstance(event_hash, str):
            previous_hash = event_hash
        else:
            previous_hash = ""
    details = {
        "event_count": len(events),
        "final_event_hash": previous_hash if events else "0" * 64,
    }
    return VerificationResult(not errors, tuple(errors), details)
