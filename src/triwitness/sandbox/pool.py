"""SandboxPool 与 `tw sandbox gc`（spec 002 §5.7/5.8，W1-18）。

- `SandboxPool(backend, size)`：信号量限制同时存在的沙箱数（默认 CPU 核数 / 2，至少 1）；
  `async with pool.acquire(spec) as sb:` 结束时一定 close（异常 / 取消也一样）。
- `gc_all()`：清理崩溃残留——docker 带 `tw.managed=true` 标签的容器、本机后端所属进程已退出的 worktree。
  docker 不可用时跳过并说明原因，不报错。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from triwitness.sandbox.base import Sandbox, SandboxBackend, SandboxSpec


def default_pool_size(cpus: int | None = None) -> int:
    n = cpus if cpus is not None else (os.cpu_count() or 2)
    return max(1, n // 2)


class SandboxPool:
    def __init__(self, backend: SandboxBackend, size: int | None = None) -> None:
        self.backend = backend
        self.size = size or default_pool_size()
        self._sem = asyncio.Semaphore(self.size)
        self.active = 0
        self.peak = 0

    @contextlib.asynccontextmanager
    async def acquire(self, spec: SandboxSpec) -> AsyncIterator[Sandbox]:
        async with self._sem:
            sb = await self.backend.create(spec)
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                yield sb
            finally:
                self.active -= 1
                await asyncio.shield(sb.close())


@dataclass
class GcReport:
    docker_containers: int = 0
    worktrees: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        parts = [f"docker 容器 {self.docker_containers}", f"本机 worktree {len(self.worktrees)}"]
        parts += [f"{k} 跳过：{v}" for k, v in self.skipped.items()]
        return "已清理：" + "；".join(parts)


async def gc_all(*, home: Path | None = None, docker: bool = True, local: bool = True) -> GcReport:
    rep = GcReport()
    if local:
        from triwitness.sandbox.local import LocalSandboxBackend

        rep.worktrees = await LocalSandboxBackend(home=home).gc()
    if docker:
        try:
            from triwitness.sandbox.docker import DockerSandboxBackend

            backend = DockerSandboxBackend(home=home)
            probe = await backend.probe()
            if probe.available:
                rep.docker_containers = await backend.gc()
            else:
                rep.skipped["docker"] = probe.reason or "不可用"
        except ImportError as e:  # pragma: no cover - docker SDK 是硬依赖，保险起见
            rep.skipped["docker"] = str(e)
    return rep


__all__ = ["GcReport", "SandboxPool", "default_pool_size", "gc_all"]
