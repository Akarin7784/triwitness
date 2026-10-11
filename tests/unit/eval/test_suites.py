"""W2-23：冻结的 dev / test / dev-smoke 切分。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from triwitness.eval.suites import Suite, SuiteTask, check_suite, digest, dump_suite, load_suite, suite_dirs

ROOT = Path(__file__).resolve().parents[3]
SUITES, TASKS = ROOT / "evals" / "suites", ROOT / "evals" / "tasks"
PERMISSIVE = ("MIT", "Apache", "BSD", "ISC", "PSF", "Unlicense", "0BSD")


def _mini(tmp: Path) -> tuple[Path, Path]:
    tasks, suites = tmp / "tasks", tmp / "suites"
    for split, names in (("dev", ["csv-blank-line", "slugify-edges"]), ("test", ["duration-minutes"])):
        for n in names:
            shutil.copytree(TASKS / "dev" / n, tasks / split / n)
    for name, split, parent in (("dev", "dev", None), ("test", "test", None), ("dev-smoke", "dev", "dev")):
        dirs = sorted((tasks / split).iterdir())[: 1 if name == "dev-smoke" else None]
        tk = [SuiteTask(id=d.name, source="synthetic", created_at="2026-10-10", difficulty="easy", license="Apache-2.0")
              for d in dirs]  # fmt: skip
        dump_suite(Suite(name=name, parent=parent, digest=digest(dirs), tasks=tk), suites)
    return tasks, suites


def test_frozen_digest_detects_content_change(tmp_path: Path) -> None:
    tasks, suites = _mini(tmp_path)
    assert check_suite("dev", suites=suites, tasks=tasks) == []
    assert check_suite("dev-smoke", suites=suites, tasks=tasks) == []
    assert [p.name for p in suite_dirs("test", suites=suites, tasks=tasks)] == ["duration-minutes"]
    sol = tasks / "dev" / "slugify-edges" / "tests" / "test.sh"
    sol.write_text(sol.read_text() + "\n# 改了隐藏测试\n")
    assert any("内容变了" in p for p in check_suite("dev", suites=suites, tasks=tasks))


def test_subset_and_missing_task(tmp_path: Path) -> None:
    tasks, suites = _mini(tmp_path)
    s = load_suite("dev-smoke", suites)
    bad = s.model_copy(update={"tasks": [*s.tasks, s.tasks[0].model_copy(update={"id": "duration-minutes"})]})
    dump_suite(bad, suites)
    assert any("子集" in p for p in check_suite("dev-smoke", suites=suites, tasks=tasks))
    shutil.rmtree(tasks / "test" / "duration-minutes")
    assert any("找到 0 处" in p for p in check_suite("test", suites=suites, tasks=tasks))


def test_test_suite_requires_allow_test() -> None:
    from triwitness.cli.main import app

    r = CliRunner().invoke(app, ["eval", "run", "--suite", "test", "--agent", "null"], env={"NO_COLOR": "1"})
    plain = re.sub(r"\x1b\[[0-9;]*m|[\s│╭╮╰╯─]", "", r.output)  # rich 面板会上色、折行
    assert r.exit_code != 0 and "--allow-test" in plain


@pytest.mark.skipif(not (SUITES / "test.yaml").exists(), reason="切分尚未生成")
def test_real_split_is_frozen_and_well_formed() -> None:
    for name in ("dev", "test", "dev-smoke"):
        assert check_suite(name, suites=SUITES, tasks=TASKS) == [], name
    dev, test, smoke = (load_suite(n, SUITES) for n in ("dev", "test", "dev-smoke"))
    assert len(dev.tasks) == 15 and len(test.tasks) == 35 and len(smoke.tasks) == 5
    assert not set(dev.ids) & set(test.ids)
    for t in dev.tasks + test.tasks:
        assert t.license.startswith(PERMISSIVE), (t.id, t.license)
    # leaderboard 部分（污染风险最低）比 dev 里所有真实任务都新；leaderboard 只产出 23 个，其余用 filtered 补齐，
    # 报告里按来源分开给 Resolved@1
    fresh = [t for t in test.tasks if "leaderboard" in t.source]
    assert len(fresh) >= 20
    assert min(t.created_at for t in fresh) >= max(t.created_at for t in dev.tasks if t.source != "synthetic")


@pytest.mark.skipif(not (SUITES / "ext.yaml").exists(), reason="扩展集尚未生成")
def test_ext_suites_are_frozen_hardened_and_disjoint() -> None:
    """W5-12：ext / ext-reserve 冻结、与 dev / test 不重叠、全部匿名 ID，ext 取较新的一批。"""
    for name in ("ext", "ext-reserve"):
        assert check_suite(name, suites=SUITES, tasks=TASKS) == [], name
    ext, reserve, dev, test = (load_suite(n, SUITES) for n in ("ext", "ext-reserve", "dev", "test"))
    assert len(ext.tasks) + len(dev.tasks) + len(test.tasks) >= 95
    ids = set(ext.ids) | set(reserve.ids)
    assert not set(ext.ids) & set(reserve.ids)
    assert not ids & (set(dev.ids) | set(test.ids))
    assert all(re.fullmatch(r"t-[0-9a-f]{10}", i) for i in ids)
    for t in ext.tasks + reserve.tasks:
        assert t.license.startswith(PERMISSIVE), (t.id, t.license)
    assert min(t.created_at for t in ext.tasks) >= max(t.created_at for t in reserve.tasks)
