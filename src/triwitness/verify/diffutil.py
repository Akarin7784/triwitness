"""diff 解析的小工具（验证器各模块共用）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from triwitness.eval.grade import FilePatch, is_infra, is_test_file, split_patch

__all__ = ["FilePatch", "Hunk", "added_lines", "changed_line_count", "is_infra", "is_test_file", "split_patch"]

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class Hunk:
    added: list[tuple[int, str]] = field(default_factory=list)  # (新文件行号, 内容)
    removed: list[str] = field(default_factory=list)


def hunks(fp: FilePatch) -> list[Hunk]:
    out: list[Hunk] = []
    line = 0
    for raw in fp.text.splitlines():
        m = _HUNK.match(raw)
        if m:
            out.append(Hunk())
            line = int(m.group(1))
            continue
        if not out or raw.startswith(("+++", "---")):
            continue
        if raw.startswith("+"):
            out[-1].added.append((line, raw[1:]))
            line += 1
        elif raw.startswith("-"):
            out[-1].removed.append(raw[1:])
        elif raw.startswith(" "):
            line += 1
    return out


def added_lines(fp: FilePatch) -> list[tuple[int, str]]:
    return [a for h in hunks(fp) for a in h.added]


def removed_lines(fp: FilePatch) -> list[str]:
    return [r for h in hunks(fp) for r in h.removed]


def changed_line_count(patch: str) -> int:
    return sum(len(added_lines(fp)) + len(removed_lines(fp)) for fp in split_patch(patch))
