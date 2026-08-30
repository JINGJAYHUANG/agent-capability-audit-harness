from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".jsonl", ".toml", ".yml", ".yaml", ".txt", ".cff", ".html"
}
SKIP_PARTS = {".git", ".venv", "build", "dist", "__pycache__", ".pytest_cache"}
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "aws-access-key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "windows-user-path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"),
    "mac-user-path": re.compile(r"/" + r"Users/[^/\s]+"),
    "local-identity-fragment": re.compile(r"\bh1419\b", re.IGNORECASE),
}
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
findings = []
scanned = 0
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
        continue
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", "MANIFEST.in"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    scanned += 1
    relative = path.relative_to(ROOT).as_posix()
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            findings.append(f"{relative}: {name}")
    for match in EMAIL.finditer(text):
        email = match.group(0).lower()
        if email.endswith("@example.test") or email.endswith("@users.noreply.github.com"):
            continue
        findings.append(f"{relative}: public email address")
if findings:
    print("public audit failed")
    for finding in findings:
        print(f"- {finding}")
    raise SystemExit(1)
print(f"public audit passed: {scanned} text files scanned")
