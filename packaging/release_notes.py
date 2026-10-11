"""从 CHANGELOG.md 取出某个版本的整节，作为 GitHub Release 说明（release.yml 用）。

用法：python packaging/release_notes.py v0.3.0-preview > notes.md
找不到对应版本时退出码 1（发布流程随之失败，避免发出空说明）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def section(changelog: str, version: str) -> str | None:
    version = version.removeprefix("v")
    head = re.compile(rf"^## \[{re.escape(version)}\][^\n]*$", re.M)
    m = head.search(changelog)
    if not m:
        return None
    nxt = re.compile(r"^## \[", re.M).search(changelog, m.end())
    body = changelog[m.end() : nxt.start() if nxt else len(changelog)].strip()
    return body or None


def main() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = section(text, sys.argv[1])
    if body is None:
        print(f"CHANGELOG.md 里没有 {sys.argv[1]} 这一节", file=sys.stderr)
        raise SystemExit(1)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(body)
    print(
        "\n---\n安装：下载 `*-setup.exe`，SmartScreen 提示时点“更多信息 → 仍要运行”（未签名）。"
        "用同名 `.sha256` 核对文件（PowerShell：`Get-FileHash <文件>`）。"
        "\n已知限制：https://github.com/Akarin7784/triwitness/blob/main/docs/release/known-limitations.md"
    )


if __name__ == "__main__":
    main()
