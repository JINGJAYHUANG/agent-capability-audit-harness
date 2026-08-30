from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
errors = []
for path in sorted(ROOT.rglob("*.md")):
    if any(part in {".git", ".venv", "build", "dist"} for part in path.parts):
        continue
    text = path.read_text(encoding="utf-8")
    for raw in LINK.findall(text):
        target = raw.strip().split()[0].strip("<>")
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = unquote(target.split("#", 1)[0])
        candidate = (path.parent / target).resolve()
        if not candidate.exists():
            errors.append(f"{path.relative_to(ROOT)} -> {target}")
if errors:
    print("broken Markdown links")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)
print("markdown links passed")
