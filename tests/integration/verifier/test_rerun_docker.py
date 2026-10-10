"""W3-05 / W3-20：docker 后端上的干净环境复跑 → clean_env=verified；修复无效 → failed。需要 Docker。

镜像用默认 python:3.12-slim（没有 git、没有 pytest）：补丁走宿主侧 apply_patch，复现用纯 python 脚本。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from triwitness.core.models import ReproRef
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.docker import DockerSandboxBackend
from triwitness.verify.rerun import rerun_repro
from triwitness.verify.risk import RiskInputs, assess
from triwitness.verify.testing import make_patch, make_repo

pytestmark = pytest.mark.integration
REPRO = "tests/tw_repro/repro_issue_1.py"
BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
SCRIPT = "import sys\nsys.path.insert(0, '.')\nfrom calc import add\n\nassert add(1, 2) == 3, add(1, 2)\n"


@pytest.fixture(scope="module")
def backend(tmp_path_factory: pytest.TempPathFactory) -> DockerSandboxBackend:
    b = DockerSandboxBackend(home=tmp_path_factory.mktemp("twhome"))
    probe = asyncio.run(b.probe())
    if not probe.available:
        pytest.skip(f"Docker 不可用：{probe.reason}")
    return b


@pytest.mark.parametrize(("fix", "expected"), [(FIXED, "reproduced"), (BUGGY.replace("-", "*"), "failed")])
async def test_docker_rerun_is_clean(backend: DockerSandboxBackend, tmp_path: Path, fix: str, expected: str) -> None:
    repo = make_repo(tmp_path, {"calc.py": BUGGY})
    patch = make_patch(repo, {"calc.py": fix, REPRO: SCRIPT})
    spec = SandboxSpec(repo=repo, memory_mb=512, cpus=1)
    res = await rerun_repro(backend, spec, patch, ReproRef(path=REPRO, cmd=f"python {REPRO}"))
    assert res.repro_status == expected, (res.notes, res.logs)
    assert (res.clean_env, res.unverified_reason) == ("verified", None)
    assert [r.scope for r in res.test_runs] == ["repro_base", "repro_patched"]
    lv = assess(RiskInputs(patch=patch, repro_status=res.repro_status, clean_env=res.clean_env)).level
    assert lv == ("L0" if expected == "reproduced" else "L1")
