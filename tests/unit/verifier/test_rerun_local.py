"""W3-05 / W3-07 / W3-20：干净环境复跑证人，离线跑在真实 none 后端（git worktree + 真 pytest）上。

none 后端没有干净环境：结论一律 clean_env = unverified、unverified_reason = no_sandbox；
另用一个声明 clean_env=True 的后端子类验证“有沙箱”分支的标记。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from triwitness.core.models import ReproRef
from triwitness.sandbox.base import Capabilities, SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.verify.rerun import Baseline, only_test_files, plan_scope, regression, rerun_repro
from triwitness.verify.risk import RiskInputs, assess
from triwitness.verify.testing import git, make_patch, make_repo

PY = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'
REPRO = "tests/tw_repro/test_issue_1.py"
BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"


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


def test_plan_scope_full_vs_related_sample() -> None:
    assert plan_scope(30, ["t/test_a.py"], ["t/test_a.py", "t/test_b.py"]) == ("full", [], None)
    assert plan_scope(9999, None, None)[0] == "full"  # 没有相关测试信息就只能全量
    tests = [f"t/test_{i}.py" for i in range(11)]
    scope, files, note = plan_scope(900, ["t/test_0.py"], tests, sample_rate=0.2, seed=1)
    assert scope == "related" and "t/test_0.py" in files and len(files) == 1 + 2  # ceil(10 × 0.2)
    assert files == plan_scope(900, ["t/test_0.py"], tests, sample_rate=0.2, seed=1)[1]  # 固定种子可复现
    assert note and "15.0 分钟" in note and "抽样 2/10" in note


async def test_regression_related_when_full_too_slow(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {
        "calc.py": BUGGY, "tests/__init__.py": "",
        "tests/test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 2) == 4\n",
        "tests/test_other.py": "def test_other():\n    assert False\n",
    })  # fmt: skip
    patch = make_patch(repo, {"calc.py": FIXED})
    base = Baseline(failures={"tests.test_calc::test_add"}, duration_s=1200)
    run, res = await regression(LocalSandboxBackend(home=tmp_path / "home"), SandboxSpec(repo=repo), patch, PY,
                                related=["tests/test_calc.py"], all_tests=["tests/test_calc.py", "tests/test_other.py"],
                                baseline=base, sample_rate=0.0)  # fmt: skip
    assert run.scope == "related" and run.passed == 1 and run.failed == 0, res.logs  # test_other 没被选中
    assert run.new_failures == [] and any("改跑相关 1 个" in n for n in res.notes)


async def test_crash_without_junit_counts_as_failure(tmp_path: Path) -> None:
    """pytest 收集阶段崩溃 / 命令不存在 → 没有 junit 报告：按退出码判失败，而不是“0 个失败 = 通过”。"""
    repo = make_repo(tmp_path, {"calc.py": BUGGY, "tests/__init__.py": "", "tests/tw_repro/__init__.py": ""})
    patch = make_patch(repo, {"calc.py": FIXED, REPRO: repro_test("assert add(1, 2) == 3")})
    res = await rerun_repro(LocalSandboxBackend(home=tmp_path / "home"), SandboxSpec(repo=repo), patch,
                            ReproRef(path=REPRO, cmd="no-such-pytest-binary " + REPRO))  # fmt: skip
    assert res.repro_status == "failed"  # 修复前后都“失败”：绝不能判为 reproduced
    assert [r.failed for r in res.test_runs] == [1, 1]


# ---------------------------------------------------------------- W3-14 后续：回归盲区（W3-14：46 个补丁里 10 个）


def test_normalize_test_cmd() -> None:
    from triwitness.verify.rerun import normalize_test_cmd

    assert normalize_test_cmd("python -m pytest -q -x") == "python -m pytest --continue-on-collection-errors -q"
    assert normalize_test_cmd("pytest --maxfail=1 tests") == "pytest --continue-on-collection-errors tests"
    assert (
        normalize_test_cmd("uv run pytest --maxfail 3 --exitfirst") == "uv run pytest --continue-on-collection-errors"
    )
    assert normalize_test_cmd("pytest -k 'x or y'") == "pytest --continue-on-collection-errors -k 'x or y'"
    same = "pytest --continue-on-collection-errors -q"
    assert normalize_test_cmd(same) == same
    assert normalize_test_cmd("make test -x") == "make test -x"  # 非 pytest 原样
    p = '"/tmp/pytest-of-box/py" -m pytest -x'  # 路径里的 pytest 不动
    assert normalize_test_cmd(p) == '"/tmp/pytest-of-box/py" -m pytest --continue-on-collection-errors'


async def test_regression_survives_exitfirst_and_collection_error(tmp_path: Path) -> None:
    """断网沙箱里某个测试文件收集期就报错 + `-x`：以前整套停在第一个错误（0 通过，回归盲区）。"""
    repo = make_repo(tmp_path, {
        "calc.py": BUGGY, "tests/__init__.py": "",
        "tests/test_aaa_net.py": "raise ConnectionError('pypi.org: Temporary failure in name resolution')\n",
        "tests/test_calc.py": "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n",
    })  # fmt: skip
    patch = make_patch(repo, {"calc.py": FIXED})
    run, res = await regression(LocalSandboxBackend(home=tmp_path / "home"), SandboxSpec(repo=repo), patch,
                                f"{PY} -x")  # fmt: skip
    assert run.scope == "full" and run.passed == 1 and run.errors >= 1 and run.new_failures == [], res.logs
    assert "--continue-on-collection-errors" in run.command and " -x" not in run.command


async def test_regression_blind_falls_back_to_related_tests(tmp_path: Path) -> None:
    """全量一个都没通过（这里：某个测试文件导入时直接让进程退出）→ 改跑与改动相关的测试文件。"""
    repo = make_repo(tmp_path, {
        "calc.py": BUGGY, "tests/__init__.py": "",
        "tests/test_aaa_crash.py": "import os\nos._exit(3)\n",
        "tests/test_calc.py": "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n",
    })  # fmt: skip
    patch = make_patch(repo, {"calc.py": FIXED})
    run, res = await regression(LocalSandboxBackend(home=tmp_path / "home"), SandboxSpec(repo=repo), patch, PY)
    assert run.scope == "related" and run.passed == 1 and "tests/test_calc.py" in run.command, (res.notes, res.logs)
    assert any("改跑与改动相关的 1 个测试文件" in n for n in res.notes)
    off, _ = await regression(LocalSandboxBackend(home=tmp_path / "home2"), SandboxSpec(repo=repo), patch, PY,
                              related_fallback=False)  # fmt: skip
    assert off.scope == "full" and off.passed == 0
