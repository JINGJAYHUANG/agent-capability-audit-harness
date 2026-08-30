from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Verdict = Literal["allow", "ask", "deny"]
ObservationType = Literal[
    "action_executed",
    "approval_requested",
    "action_blocked",
    "artifact",
    "note",
]


@dataclass(frozen=True)
class Decision:
    action_id: str
    capability: str
    base_verdict: Verdict
    verdict: Verdict
    constraint_passed: bool
    reasons: tuple[str, ...]
    approval_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        return result


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    errors: tuple[str, ...]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "details": self.details,
        }
