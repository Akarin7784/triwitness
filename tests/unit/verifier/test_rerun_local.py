"""W3-05 / W3-07 / W3-20：干净环境复跑证人，离线跑在真实 none 后端（git worktree + 真 pytest）上。

none 后端没有干净环境：结论一律 clean_env = unverified、unverified_reason = no_sandbox；
另用一个声明 clean_env=True 的后端子类验证“有沙箱”分支的标记。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from triwitness.core.models import ReproRef
from triwitness.sandbox.base import Capabilities, SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.verify.rerun import only_test_files, regression, rerun_repro
from triwitness.verify.risk import RiskInputs, assess

PY = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'
REPRO = "tests/tw_repro/test_issue_1.py"
BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"


def git(repo: Path, *a: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                       check=True, capture_output=True, text=True)  # fmt: skip
    return r.stdout


def make_repo(tmp: Path, files: dict[str, str]) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    for k, v in files.items():
        (repo / k).parent.mkdir(parents=True, exist_ok=True)
        (repo / k).write_text(v)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    return repo


def make_patch(repo: Path, files: dict[str, str]) -> str:
    """在仓库里写入改动 → 取 diff → 还原（模拟 Executor 交出来的补丁）。"""
    for k, v in files.items():
        (repo / k).parent.mkdir(parents=True, exist_ok=True)
        (repo / k).write_text(v)
    git(repo, "add", "-A")
    patch = git(repo, "diff", "--cached", "--binary")
    git(repo, "reset", "-q", "--hard")
    git(repo, "clean", "-qfd")
    return patch


class CleanLocal(LocalSandboxBackend):
    """测试替身：声明有干净环境（模拟 docker 后端的 capabilities）。"""

    capabilities = Capabilities(isolation="container", network_enforced=True, clean_env=True,
                                host_fs_visible=False, allows_full_access=False)  # fmt: skip


@pytest.fixture
def setup(tmp_path: Path) -> tuple[LocalSandboxBackend, SandboxSpec, Path]:
    repo = make_repo(tmp_path, {"calc.py": BUGGY, "tests/__init__.py": "", "tests/tw_repro/__init__.py": ""})
    return LocalSandboxBackend(home=tmp_path / "home"), SandboxSpec(repo=repo), repo


def repro_test(body: str) -> str:
    return f"from calc import add\n\n\ndef test_issue():\n    {body}\n"


async def test_reproduced_but_unverified_without_sandbox(setup: tuple) -> None:  # type: ignore[type-arg]
    backend, spec, repo = setup
    patch = make_patch(repo, {"calc.py": FIXED, REPRO: repro_test("assert add(1, 2) == 3")})
    assert REPRO in only_test_files(patch) and "calc.py" not in only_test_files(patch).split(REPRO)[0]
    res = await rerun_repro(backend, spec, patch, ReproRef(path=REPRO, cmd=f"{PY} {REPRO}"))
    assert res.repro_status == "reproduced", (res.notes, res.logs)
    assert (res.clean_env, res.unverified_reason) == ("unverified", "no_sandbox")
    base, fixed = res.test_runs
    assert (base.scope, base.failed, fixed.scope, fixed.failed, fixed.passed) == (
        "repro_base",
        1,
        "repro_patched",
        0,
        1,
    )
    # 无沙箱 → 风险至少 L2（即使其他一切完美）
    assert assess(RiskInputs(patch=patch, clean_env=res.clean_env)).level == "L2"
    assert git(repo, "status", "--porcelain") == ""  # 证人从不碰用户的工作区


async def test_clean_backend_marks_verified(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"calc.py": BUGGY, "tests/__init__.py": "", "tests/tw_repro/__init__.py": ""})
    patch = make_patch(repo, {"calc.py": FIXED, REPRO: repro_test("assert add(1, 2) == 3")})
    res = await rerun_repro(CleanLocal(home=tmp_path / "home"), SandboxSpec(repo=repo), patch,
                            ReproRef(path=REPRO, cmd=f"{PY} {REPRO}"))  # fmt: skip
    assert (res.repro_status, res.clean_env, res.unverified_reason) == ("reproduced", "verified", None)
    assert assess(RiskInputs(patch=patch, clean_env=res.clean_env)).level == "L0"


async def test_repro_passing_on_base_is_inconclusive(setup: tuple) -> None:  # type: ignore[type-arg]
    backend, spec, repo = setup
    patch = make_patch(repo, {"calc.py": FIXED, REPRO: repro_test("assert add(0, 0) == 0")})  # 基线上也成立
    res = await rerun_repro(backend, spec, patch, ReproRef(path=REPRO, cmd=f"{PY} {REPRO}"))
    assert res.repro_status == "inconclusive" and "基线上就通过" in res.notes[0]


async def test_fix_that_does_not_fix_is_failed(setup: tuple) -> None:  # type: ignore[type-arg]
    backend, spec, repo = setup
    patch = make_patch(
        repo, {"calc.py": "def add(a, b):\n    return a * b\n", REPRO: repro_test("assert add(1, 2) == 3")}
    )
    res = await rerun_repro(backend, spec, patch, ReproRef(path=REPRO, cmd=f"{PY} {REPRO}"))
    assert res.repro_status == "failed" and "仍失败" in res.notes[0]


async def test_no_repro_is_not_applicable(setup: tuple) -> None:  # type: ignore[type-arg]
    backend, spec, repo = setup
    res = await rerun_repro(backend, spec, make_patch(repo, {"calc.py": FIXED}), None)
    assert res.repro_status == "not_applicable" and res.test_runs == []


async def test_unappliable_patch(setup: tuple) -> None:  # type: ignore[type-arg]
    backend, spec, _ = setup
    bogus = f"diff --git a/{REPRO} b/{REPRO}\n--- a/{REPRO}\n+++ b/{REPRO}\n@@ -1,1 +1,1 @@\n-nope\n+x\n"
    res = await rerun_repro(backend, spec, bogus, ReproRef(path=REPRO, cmd=f"{PY} {REPRO}"))
    assert res.repro_status == "inconclusive" and "git apply" in res.notes[0]


async def test_regression_counts_only_new_failures_and_flaky(tmp_path: Path) -> None:
    marker = (tmp_path / "flaky-marker").as_posix()
    repo = make_repo(tmp_path, {
        "calc.py": BUGGY + "\n\ndef sub(a, b):\n    return a - b\n",
        "tests/__init__.py": "",
        "tests/test_old.py": "from calc import add, sub\n\n\ndef test_add():\n    assert add(1, 2) == 3\n\n\n"
                             "def test_sub():\n    assert sub(3, 1) == 2\n\n\ndef test_broken():\n    assert False\n",
    })  # fmt: skip
    flaky = (f"import os\n\n\ndef test_flaky():\n    m = {marker!r}\n    first = not os.path.exists(m)\n"
             "    open(m, 'w').close()\n    assert not first\n")  # fmt: skip
    patch = make_patch(repo, {
        "calc.py": FIXED + "\n\ndef sub(a, b):\n    return b - a\n",  # 修好 add，却把 sub 改坏
        "tests/test_flaky.py": flaky,
    })  # fmt: skip
    run, res = await regression(LocalSandboxBackend(home=tmp_path / "home"), SandboxSpec(repo=repo), patch, PY)
    assert run.scope == "full" and len(run.new_failures) == 1 and run.new_failures[0].endswith("test_sub"), res.logs
    assert len(run.flaky) == 1 and run.flaky[0].endswith("test_flaky")
    assert any("基线上就存在" in n for n in res.notes)  # test_broken 在基线上就失败，不算回归
    assert res.clean_env == "unverified"
