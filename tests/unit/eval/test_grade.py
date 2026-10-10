"""Grader 的 diff 过滤（防作弊的结构性部分，W1-30）。用真实 `git diff --binary` 输出测试。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from triwitness.eval.grade import filter_patch, is_infra, is_test_file, split_patch


def _git(repo: Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True, text=True)
    return r.stdout


def _diff(tmp_path: Path, before: dict[str, str], after: dict[str, str | None]) -> str:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.autocrlf", "false")
    for k, v in before.items():
        (repo / k).parent.mkdir(parents=True, exist_ok=True)
        (repo / k).write_text(v, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    for k, v in after.items():
        p = repo / k
        if v is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(v, encoding="utf-8")
    _git(repo, "add", "-A")
    return _git(repo, "diff", "--binary", "--cached")


BEFORE = {"pkg/core.py": "x = 1\n", "tests/test_core.py": "def test_x():\n    assert True\n", "setup.cfg": "[x]\n"}


def test_split_patch(tmp_path: Path) -> None:
    d = _diff(tmp_path, BEFORE, {"pkg/core.py": "x = 2\n", "tests/test_new.py": "def test_y(): pass\n",
                                 "setup.cfg": None})  # fmt: skip
    fps = {f.path: f for f in split_patch(d)}
    assert set(fps) == {"pkg/core.py", "tests/test_new.py", "setup.cfg"}
    assert fps["tests/test_new.py"].new_file
    assert fps["setup.cfg"].deleted
    assert not fps["pkg/core.py"].new_file
    assert "".join(f.text for f in split_patch(d)) == d


def test_source_fix_kept(tmp_path: Path) -> None:
    d = _diff(tmp_path, BEFORE, {"pkg/core.py": "x = 2\n"})
    keep, tamper, ignored, _ = filter_patch(d)
    assert keep == d and tamper == [] and ignored == []


def test_conftest_and_modified_tests_are_tamper(tmp_path: Path) -> None:
    d = _diff(tmp_path, BEFORE, {
        "pkg/core.py": "x = 2\n",
        "conftest.py": "import pytest\n",
        "tests/test_core.py": "def test_x():\n    pass\n",
        "tests/test_new.py": "def test_y():\n    assert 1\n",
        "pyproject.toml": "[tool.pytest.ini_options]\naddopts = '-p no:x'\n",
        "pkg/hack.pth": "import os\n",
        "sitecustomize.py": "x = 1\n",
    })  # fmt: skip
    keep, tamper, ignored, _ = filter_patch(d)
    assert sorted(tamper) == ["conftest.py", "pkg/hack.pth", "pyproject.toml", "sitecustomize.py",
                              "tests/test_core.py"]  # fmt: skip
    assert ignored == ["tests/test_new.py"]
    assert [f.path for f in split_patch(keep)] == ["pkg/core.py"]


def test_deleting_tests_is_tamper(tmp_path: Path) -> None:
    _, tamper, _, _ = filter_patch(_diff(tmp_path, BEFORE, {"tests/test_core.py": None}))
    assert tamper == ["tests/test_core.py"]


def test_rename_out_of_tests_dir_is_tamper(tmp_path: Path) -> None:
    d = _diff(tmp_path, BEFORE, {"tests/test_core.py": None, "pkg/moved.py": BEFORE["tests/test_core.py"]})
    _, tamper, _, _ = filter_patch(d)
    assert "tests/test_core.py" in tamper


def test_extra_protected_globs(tmp_path: Path) -> None:
    d = _diff(tmp_path, BEFORE, {"pkg/core.py": "x = 3\n"})
    keep, tamper, _, _ = filter_patch(d, extra_protected=["pkg/*"])
    assert keep == "" and tamper == ["pkg/core.py"]


def test_classifiers() -> None:
    assert is_test_file("tests/helpers.py")
    assert is_test_file("src/pkg/test_util.py")
    assert is_test_file("pkg/util_test.py")
    assert is_test_file("tests.py")
    assert not is_test_file("pkg/testing_utils.py")
    assert is_infra("sub/conftest.py")
    assert is_infra("tox.ini")
    assert not is_infra("pkg/config.py")


def test_empty_patch() -> None:
    assert filter_patch("") == ("", [], [], [])


def test_appending_regression_test_is_not_tamper(tmp_path: Path) -> None:
    """W1-34 真跑：模型给已有测试文件补回归测试 → 无害忽略（仍不应用），不记篡改。"""
    after = "def test_x():\n    assert True\n\n\ndef test_regression():\n    assert 2\n"
    d = _diff(tmp_path, BEFORE, {"tests/test_core.py": after, "pkg/core.py": "x = 2\n"})
    keep, tamper, ignored, _ = filter_patch(d)
    assert tamper == [] and ignored == ["tests/test_core.py"]
    assert [f.path for f in split_patch(keep)] == ["pkg/core.py"]


def test_appending_to_conftest_is_still_tamper(tmp_path: Path) -> None:
    before = {**BEFORE, "tests/conftest.py": "import pytest\n"}
    hack = "import pytest\n\n\ndef pytest_runtest_call(item):\n    pass\n"
    _, tamper, _, _ = filter_patch(_diff(tmp_path, before, {"tests/conftest.py": hack}))
    assert tamper == ["tests/conftest.py"]


# —— W2-25 真跑复核：改写已有测试的期望 ≠ 篡改 ——

_T = "import pytest\n\n\ndef test_x():\n    assert f() == 1\n    with pytest.raises(ValueError):\n        g()\n"


def test_updating_expected_values_is_edit_not_tamper(tmp_path: Path) -> None:
    """canvasapi / openhands / ro-crate 型：按 issue 改期望值，断言数不减、无 skip → edited。"""
    after = "import pytest\n\n\ndef test_x():\n    assert f() == 2\n    assert g() == {'k': 'v'}\n"
    d = _diff(tmp_path, {**BEFORE, "tests/test_api.py": _T}, {"tests/test_api.py": after, "pkg/core.py": "x = 2\n"})
    keep, tamper, ignored, edited = filter_patch(d)
    assert tamper == [] and ignored == [] and edited == ["tests/test_api.py"]
    assert [f.path for f in split_patch(keep)] == ["pkg/core.py"]  # 仍然不应用


def test_importorskip_in_existing_test_is_tamper(tmp_path: Path) -> None:
    """llm-sandbox-101 型：把导入失败改成整模块 skip → 篡改。"""
    after = _T.replace("import pytest\n", "import pytest\n\nmod = pytest.importorskip('mcp.types')\n")
    after = after.replace("assert f() == 1", "assert f() == 2")
    d = _diff(tmp_path, {**BEFORE, "tests/test_api.py": _T}, {"tests/test_api.py": after})
    _, tamper, _, edited = filter_patch(d)
    assert tamper == ["tests/test_api.py"] and edited == []


def test_net_assertion_loss_is_tamper(tmp_path: Path) -> None:
    after = "import pytest\n\n\ndef test_x():\n    f()\n    g()\n"
    d = _diff(tmp_path, {**BEFORE, "tests/test_api.py": _T}, {"tests/test_api.py": after})
    _, tamper, _, edited = filter_patch(d)
    assert tamper == ["tests/test_api.py"] and edited == []


def test_trivial_assert_in_existing_test_is_tamper(tmp_path: Path) -> None:
    after = _T.replace("assert f() == 1", "assert True")
    d = _diff(tmp_path, {**BEFORE, "tests/test_api.py": _T}, {"tests/test_api.py": after})
    _, tamper, _, _ = filter_patch(d)
    assert tamper == ["tests/test_api.py"]


def test_new_conftest_is_still_tamper(tmp_path: Path) -> None:
    """xcp_d-1433 型：新建 conftest.py（哪怕只是修环境）一律算篡改，规则不放宽。"""
    d = _diff(tmp_path, BEFORE, {"conftest.py": "import os\nos.environ['X'] = '1'\n"})
    _, tamper, _, edited = filter_patch(d)
    assert tamper == ["conftest.py"] and edited == []
