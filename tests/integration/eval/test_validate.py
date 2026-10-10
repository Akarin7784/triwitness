"""`tw task validate` 的真实 Docker 路径（W1-26）：原始代码 reward 0，参考解 reward 1；坏参考解被拦下。

本地：`sg docker -c "uv run pytest -m integration tests/integration/eval"`
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from triwitness.eval.task import load_task
from triwitness.eval.validate import validate_sync
from triwitness.sandbox.docker import LABEL, DockerSandboxBackend, _client

pytestmark = pytest.mark.integration

EXAMPLE = Path(__file__).resolve().parents[3] / "evals" / "tasks" / "dev" / "csv-blank-line"


@pytest.fixture(scope="module", autouse=True)
def _docker(tmp_path_factory: pytest.TempPathFactory) -> None:
    probe = asyncio.run(DockerSandboxBackend(home=tmp_path_factory.mktemp("h")).probe())
    if not probe.available:
        pytest.skip(f"Docker 不可用：{probe.reason}")


def _no_leftovers() -> None:
    left = _client().containers.list(all=True, filters={"label": [f"{LABEL}=true", "tw.kind=task-validate"]})
    assert left == []


def test_example_validates() -> None:
    rep = validate_sync(load_task(EXAMPLE))
    assert rep.ok, rep.problems
    assert rep.without_solution.reward == 0
    assert rep.with_solution.reward == 1
    assert "1 failed" in rep.without_solution.log_tail
    _no_leftovers()


def test_noop_solution_rejected(tmp_path: Path) -> None:
    d = tmp_path / "csv-blank-line"
    shutil.copytree(EXAMPLE, d)
    (d / "solution" / "solve.sh").write_text("#!/usr/bin/env bash\ntrue\n", encoding="utf-8")
    rep = validate_sync(load_task(d))
    assert not rep.ok
    assert rep.with_solution.reward == 0
    assert any("参考解" in p for p in rep.problems)
    _no_leftovers()


def test_test_sh_without_reward_rejected(tmp_path: Path) -> None:
    d = tmp_path / "csv-blank-line"
    shutil.copytree(EXAMPLE, d)
    (d / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    rep = validate_sync(load_task(d))
    assert rep.without_solution.reward is None
    assert any("reward" in p for p in rep.problems)
