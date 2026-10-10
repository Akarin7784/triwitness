#!/usr/bin/env bash
set -euo pipefail
cd /workspace/repo
cat > csvkit_lite/parse.py <<'PY'
def parse_rows(text: str) -> list[tuple[str, int]]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        rows.append((parts[0].strip(), int(parts[1])))
    return rows
PY
