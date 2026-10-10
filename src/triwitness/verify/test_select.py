"""相关测试选择（04 §4.3.1，W3-06）。

三路信号，结果写明每个测试为什么被选中：
1. 命名约定：`pkg/foo.py` → `test_foo.py` / `foo_test.py`；`pkg/__init__.py` → `test_pkg.py`、`tests/pkg/`。
2. 导入图（反向依赖）：改动模块被哪些测试（直接或经由其他模块，≤ max_depth 跳）导入。
3. 覆盖率上下文（可选，`coverage json --show-contexts` 的产物）：哪些测试执行过改动文件。

改动的测试文件本身总是入选。纯函数，输入是“路径 → 源码”；`gather_sources` 负责从沙箱读取。
"""

from __future__ import annotations

import ast
import json
import posixpath
import re
import shlex
from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel, Field

from triwitness.sandbox.base import Sandbox

TEST_FILE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.py$")
SRC_ROOTS = ("src/", "lib/", "python/")
MAX_FILES = 3000
MAX_BYTES = 400_000


class Selection(BaseModel):
    tests: list[str] = Field(default_factory=list)  # 测试文件（相对仓库根，排序）
    reasons: dict[str, list[str]] = Field(default_factory=dict)  # 测试文件 → 入选原因
    unresolved: list[str] = Field(default_factory=list)  # 找不到任何相关测试的改动文件

    def add(self, test: str, why: str) -> None:
        if test not in self.reasons:
            self.reasons[test] = []
            self.tests = sorted({*self.tests, test})
        if why not in self.reasons[test]:
            self.reasons[test].append(why)


def is_test_file(path: str) -> bool:
    return bool(TEST_FILE.search(path))


def module_names(path: str) -> list[str]:
    """文件路径对应的可能模块名（同时考虑 src/ 布局与仓库根布局）。"""
    if not path.endswith(".py"):
        return []
    p = path[:-3]
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    out = [p.replace("/", ".")]
    for root in SRC_ROOTS:
        if path.startswith(root):
            out.append(p[len(root) :].replace("/", "."))
    return [m for m in out if m]


def _package(path: str) -> str:
    """文件所在包（相对导入的锚点）。"""
    names = module_names(path)
    mod = names[-1] if names else ""
    return mod if path.endswith("__init__.py") else mod.rpartition(".")[0]


def imports_of(path: str, source: str) -> set[str]:
    """文件导入的模块名（含 `from a import b` 时的 `a.b`，相对导入已展开）。语法错误时返回空集。"""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    out: set[str] = set()
    pkg = _package(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = pkg.split(".") if pkg else []
                anchor = parts[: len(parts) - (node.level - 1)] if node.level - 1 <= len(parts) else []
                base = ".".join([*anchor, base] if base else anchor)
            if base:
                out.add(base)
                out.update(f"{base}.{a.name}" for a in node.names if a.name != "*")
    return out


def _resolve(imported: set[str], index: dict[str, str]) -> set[str]:
    """导入名 → 仓库内文件；`a.b.c` 找不到时退到 `a.b`（from a.b import c 导入的是属性）。"""
    hit: set[str] = set()
    for name in imported:
        n = name
        while n:
            if n in index:
                hit.add(index[n])
                break
            n = n.rpartition(".")[0]
    return hit


def coverage_map(data: str | dict[str, Any]) -> dict[str, set[str]]:
    """`coverage json --show-contexts` → 源文件 → 执行过它的测试文件集合。上下文形如 `tests/test_x.py::test_a|run`。"""
    d = json.loads(data) if isinstance(data, str) else data
    out: dict[str, set[str]] = defaultdict(set)
    for path, info in (d.get("files") or {}).items():
        for ctxs in (info.get("contexts") or {}).values():
            for c in ctxs:
                test = c.split("|", 1)[0].split("::", 1)[0]
                if test.endswith(".py"):
                    out[path.replace("\\", "/")].add(test)
    return dict(out)


def select_tests(
    changed: list[str],
    sources: dict[str, str],
    *,
    max_depth: int = 3,
    coverage: dict[str, set[str]] | None = None,
) -> Selection:
    sel = Selection()
    found: set[str] = set()  # 至少找到一个相关测试的改动文件

    def hit(test: str, src: str, why: str) -> None:
        sel.add(test, why)
        found.add(src)

    files = sorted(sources)
    tests = [f for f in files if is_test_file(f)]
    for c in changed:
        if is_test_file(c) and c in sources:
            sel.add(c, "改动的测试文件")

    # 1. 命名约定
    for c in changed:
        if not c.endswith(".py") or is_test_file(c):
            continue
        stem = posixpath.splitext(posixpath.basename(c))[0]
        if stem == "__init__":
            stem = posixpath.basename(posixpath.dirname(c))
        names = {f"test_{stem}.py", f"{stem}_test.py"}
        for t in tests:
            if posixpath.basename(t) in names or f"/{stem}/" in f"/{posixpath.dirname(t)}/":
                hit(t, c, f"命名约定：{c}")

    # 2. 导入图（反向依赖，BFS）
    index: dict[str, str] = {}
    for f in files:
        for m in module_names(f):
            index.setdefault(m, f)
    importers: dict[str, set[str]] = defaultdict(set)
    for f in files:
        for dep in _resolve(imports_of(f, sources[f]), index):
            if dep != f:
                importers[dep].add(f)
    for c in changed:
        if not c.endswith(".py") or is_test_file(c):
            continue
        seen = {c}
        q: deque[tuple[str, int]] = deque([(c, 0)])
        while q:
            cur, depth = q.popleft()
            if depth >= max_depth:
                continue
            for imp in sorted(importers.get(cur, ())):
                if imp in seen:
                    continue
                seen.add(imp)
                if is_test_file(imp):
                    hit(imp, c, f"导入 {c}" if depth == 0 else f"经 {cur} 间接导入 {c}（{depth + 1} 跳）")
                else:
                    q.append((imp, depth + 1))

    # 3. 覆盖率上下文（可选）
    if coverage:
        for c in changed:
            for t in sorted(coverage.get(c, ())):
                if t in sources:
                    hit(t, c, f"覆盖率：执行过 {c}")

    for c in changed:
        if c.endswith(".py") and not is_test_file(c) and c not in found:
            sel.unresolved.append(c)
    return sel


async def gather_sources(sb: Sandbox, *, limit: int = MAX_FILES) -> dict[str, str]:
    """从沙箱读出所有 .py 文件（跳过 .git / .tw / venv / node_modules；超大文件跳过）。不依赖镜像里有 git。"""
    r = await sb.exec(
        "find . \\( -name .git -o -name .tw -o -name node_modules -o -name .venv -o -name venv -o -name __pycache__ "
        f"-o -name .tox \\) -prune -o -type f -name '*.py' -size -{MAX_BYTES // 1000}k -print 2>/dev/null "
        f"| sed 's|^\\./||' | sort | head -n {int(limit)}",
        timeout_s=60,
    )
    out: dict[str, str] = {}
    for path in (ln for ln in r.stdout.splitlines() if ln):
        try:
            out[path] = (await sb.read_file(path)).decode("utf-8", errors="replace")
        except Exception:
            continue
    return out


def pytest_args(tests: list[str]) -> str:
    return " ".join(shlex.quote(t) for t in tests)


__all__ = [
    "Selection",
    "coverage_map",
    "gather_sources",
    "imports_of",
    "is_test_file",
    "module_names",
    "pytest_args",
    "select_tests",
]
