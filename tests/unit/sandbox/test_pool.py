"""W1-18：SandboxPool 并发上限与必定关闭；`tw sandbox gc` 命令。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from typer.testing import CliRunner

from triwitness.cli.main import app
from triwitness.harness.testing import FakeSandbox
from triwitness.sandbox.base import Capabilities, Probe, SandboxSpec
from triwitness.sandbox.pool import GcReport, SandboxPool, default_pool_size


class Closing(FakeSandbox):
    closed = 0

    async def close(self) -> None:
        Closing.closed += 1


class FakeBackend:
    name = "none"
    capabilities = Capabilities(isolation="none", network_enforced=False, clean_env=False, host_fs_visible=True,
                                allows_full_access=False)  # fmt: skip

    async def probe(self) -> Probe:
        return Probe(available=True)

    async def create(self, spec: SandboxSpec) -> FakeSandbox:
        await asyncio.sleep(0)
        return Closing()


def test_default_size() -> None:
    assert default_pool_size(8) == 4 and default_pool_size(1) == 1 and default_pool_size() >= 1


async def test_pool_limits_concurrency_and_closes() -> None:
    Closing.closed = 0
    pool = SandboxPool(FakeBackend(), size=3)  # type: ignore[arg-type]

    async def job(i: int) -> int:
        async with pool.acquire(SandboxSpec()) as sb:
            await asyncio.sleep(0.01)
            r = await sb.exec("pytest --version")
            return r.exit_code

    assert await asyncio.gather(*[job(i) for i in range(8)]) == [0] * 8
    assert pool.peak == 3 and pool.active == 0 and Closing.closed == 8


async def test_pool_closes_on_error() -> None:
    Closing.closed = 0
    pool = SandboxPool(FakeBackend(), size=1)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        async with pool.acquire(SandboxSpec()):
            raise RuntimeError("boom")
    assert Closing.closed == 1 and pool.active == 0


def test_cli_sandbox_gc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, bool] = {}

    async def fake_gc(*, docker: bool = True, local: bool = True, home: Path | None = None) -> GcReport:
        seen.update(docker=docker, local=local)
        return GcReport(docker_containers=2, worktrees=["r_old"], skipped={})

    monkeypatch.setattr("triwitness.sandbox.pool.gc_all", fake_gc)
    r = CliRunner().invoke(app, ["sandbox", "gc", "--backend", "none"])
    assert r.exit_code == 0, r.output
    assert "docker 容器 2" in r.output and "r_old" in r.output and seen == {"docker": False, "local": True}
    assert CliRunner().invoke(app, ["sandbox", "gc", "--backend", "x"]).exit_code != 0


async def test_gc_all_without_docker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from triwitness.sandbox import pool
    from triwitness.sandbox.docker import DockerSandboxBackend

    async def no_docker(self: object) -> Probe:
        return Probe(available=False, reason="docker 未运行")

    monkeypatch.setattr(DockerSandboxBackend, "probe", no_docker)
    rep = await pool.gc_all(home=tmp_path)
    assert rep.skipped == {"docker": "docker 未运行"} and rep.worktrees == []
    assert "docker 跳过" in rep.summary()
