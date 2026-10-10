#!/usr/bin/env bash
set -euo pipefail
cd /workspace/repo
cat > textkit/slug.py <<'PY'
import re

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _NON_WORD.sub("-", text.lower()).strip("-")
PY
