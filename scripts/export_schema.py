"""导出 schemas/tw-events-1.schema.json（由 core.events 生成，不要手改）。

用法：uv run python scripts/export_schema.py [--check]
"""

import sys
from pathlib import Path

from triwitness.core.events import dump_schema

TARGET = Path(__file__).resolve().parent.parent / "schemas" / "tw-events-1.schema.json"


def main() -> int:
    text = dump_schema()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            sys.stderr.write("schema 已过期：运行 uv run python scripts/export_schema.py\n")
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {TARGET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
