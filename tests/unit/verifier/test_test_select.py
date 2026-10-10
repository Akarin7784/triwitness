"""W3-06：相关测试选择（命名约定 + 导入图 + 可选覆盖率映射）。"""

from __future__ import annotations

from pathlib import Path

from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.verify.test_select import coverage_map, gather_sources, imports_of, module_names, select_tests
from triwitness.verify.testing import make_repo

REPO = {
    "src/pkg/__init__.py": "",
    "src/pkg/core.py": "def add(a, b):\n    return a + b\n",
    "src/pkg/api.py": "from .core import add\n\n\ndef total(xs):\n    return sum(xs)\n",
    "src/pkg/cli.py": "from pkg import api\n",
    "src/pkg/sub/__init__.py": "",
    "src/pkg/sub/deep.py": "from ..core import add\n",
    "src/pkg/unrelated.py": "X = 1\n",
    "tests/test_core.py": "from pkg.core import add\n",
    "tests/test_api.py": "import pkg.api\n",
    "tests/test_cli.py": "from pkg.cli import *\n",
    "tests/test_misc.py": "import os\n",
    "tests/sub/test_deep.py": "from pkg.sub.deep import add\n",
    "tests/broken_test.py": "def (:\n",
}


def test_module_names_src_layout() -> None:
    assert module_names("src/pkg/core.py") == ["src.pkg.core", "pkg.core"]
    assert module_names("src/pkg/__init__.py") == ["src.pkg", "pkg"]
    assert module_names("README.md") == []


def test_relative_imports_resolved() -> None:
    assert {"pkg.core", "pkg.core.add"} <= imports_of("src/pkg/api.py", REPO["src/pkg/api.py"])
    assert "pkg.core" in imports_of("src/pkg/sub/deep.py", REPO["src/pkg/sub/deep.py"])
    assert imports_of("tests/broken_test.py", "def (:\n") == set()


def test_direct_and_transitive_importers() -> None:
    sel = select_tests(["src/pkg/core.py"], REPO)
    assert {"tests/test_core.py", "tests/test_api.py", "tests/sub/test_deep.py"} <= set(sel.tests)
    assert "tests/test_cli.py" in sel.tests  # core ← api ← cli ← test_cli（3 跳）
    assert "tests/test_misc.py" not in sel.tests
    assert any("命名约定" in r for r in sel.reasons["tests/test_core.py"])
    assert any("间接" in r for r in sel.reasons["tests/test_api.py"] + sel.reasons["tests/test_cli.py"])
    assert sel.unresolved == []


def test_depth_limit() -> None:
    sel = select_tests(["src/pkg/core.py"], REPO, max_depth=1)
    assert "tests/test_core.py" in sel.tests and "tests/test_cli.py" not in sel.tests


def test_changed_test_file_and_unresolved() -> None:
    sel = select_tests(["tests/test_misc.py", "src/pkg/unrelated.py", "docs/x.md"], REPO)
    assert sel.tests == ["tests/test_misc.py"]
    assert sel.unresolved == ["src/pkg/unrelated.py"]


def test_coverage_map_toggle() -> None:
    cov = coverage_map({"files": {"src/pkg/unrelated.py": {"contexts": {
        "1": ["tests/test_misc.py::test_x|run", ""], "2": ["tests/test_misc.py::test_y|run"]}}}})  # fmt: skip
    assert cov == {"src/pkg/unrelated.py": {"tests/test_misc.py"}}
    assert select_tests(["src/pkg/unrelated.py"], REPO).tests == []
    sel = select_tests(["src/pkg/unrelated.py"], REPO, coverage=cov)
    assert sel.tests == ["tests/test_misc.py"] and sel.reasons["tests/test_misc.py"][0].startswith("覆盖率")


async def test_gather_sources_from_sandbox(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {**REPO, "README.md": "x\n"})
    sb = await LocalSandboxBackend(home=tmp_path / "home").create(SandboxSpec(repo=repo))
    try:
        src = await gather_sources(sb)
    finally:
        await sb.close()
    assert set(src) == set(REPO) and src["src/pkg/api.py"].startswith("from .core")
    assert "tests/test_cli.py" in select_tests(["src/pkg/core.py"], src).tests
