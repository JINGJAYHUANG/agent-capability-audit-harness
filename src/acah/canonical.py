from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


def canonical_dumps(value: Any) -> str:
    """Serialize JSON deterministically with a trailing newline omitted."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_dumps(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_dumps(value) + "\n", encoding="utf-8")


def normalize_relative_path(value: str) -> str:
    """Return a safe POSIX relative path or raise ValueError."""
    candidate = value.replace("\\", "/")
    pure = PurePosixPath(candidate)
    if not candidate or pure.is_absolute():
        raise ValueError(f"path must be relative: {value!r}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"path contains unsafe segment: {value!r}")
    return pure.as_posix()
