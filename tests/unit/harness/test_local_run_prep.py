"""0.5.0：run_local 的准备阶段——非 git 文件夹自动初始化、auto 模式 docker 准备失败回退 none。全部离线、¥0。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from triwitness.core.errors import SandboxError
from triwitness.harness.config import HarnessConfig
from triwitness.harness.local_run import run_local
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.sandbox.base import Capabilities, Probe, SandboxSpec, report_progress
from triwitness.sandbox.local import LocalSandboxBackend

FIN = {"summary": "没改", "changes": [], "tests_run": [], "tests_passed": True, "confidence": 0.5}


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig-empty"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


class BrokenDocker:
    name = "docker"
    capabilities = Capabilities(isolation="container", network_enforced=True, clean_env=True, host_fs_visible=False,
                                allows_full_access=True)  # fmt: skip

    async def probe(self) -> Probe:
        return Probe(available=True, version="fake")

    async def create(self, spec: SandboxSpec):  # type: ignore[no-untyped-def]
        report_progress("pull_image", "running", "拉取镜像 python:3.12-slim")
        report_progress("pull_image", "failed", "拉取镜像 python:3.12-slim 超过 600s")
        raise SandboxError("拉取镜像 python:3.12-slim 超时（600s）")


def _sp(run_dir: Path) -> list[dict]:
    lines = (run_dir / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines]


async def test_plain_folder_auto_init_and_docker_fallback(tmp_path: Path) -> None:
    work = tmp_path / "测试任务"
    work.mkdir()
    (work / "index.html").write_text("<p>hi</p>\n", encoding="utf-8")
    home = tmp_path / "home"
    out = await run_local(work, "看看", router=FakeRouter([say(call("finish", **FIN))]), harness=HarnessConfig.load(),
                          backend="auto", backends=[BrokenDocker(), LocalSandboxBackend(home=home)], home=home)  # type: ignore[list-item]  # fmt: skip
    assert out.backend == "none"
    assert (work / ".git").is_dir()
    evs = _sp(out.run_dir)
    sp = [e["payload"] for e in evs if e["kind"] == "sandbox_progress"]
    assert sp[0]["stage"] == "git_init" and "已自动初始化 git 仓库" in sp[0]["display"]
    assert [p["stage"] for p in sp[1:3]] == ["pull_image", "pull_image"]
    fb = next(p for p in sp if p["stage"] == "fallback")
    assert fb["status"] == "warn" and fb["backend"] == "none" and "none" in fb["message"]
    # 准备阶段的事件都在 task_started 之前
    kinds = [e["kind"] for e in evs]
    assert kinds.index("task_started") > max(i for i, k in enumerate(kinds) if k == "sandbox_progress")


async def test_explicit_docker_does_not_fall_back(tmp_path: Path) -> None:
    work = tmp_path / "w"
    work.mkdir()
    home = tmp_path / "home"
    with pytest.raises(SandboxError, match="超时"):
        await run_local(work, "x", router=FakeRouter([]), backend="docker",
                        backends=[BrokenDocker(), LocalSandboxBackend(home=home)], home=home)  # type: ignore[list-item]  # fmt: skip
