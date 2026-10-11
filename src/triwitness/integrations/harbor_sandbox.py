"""把 Harbor 的任务环境包装成 TriWitness 的 `Sandbox`（W5-13）。

Harbor（docs.harborframework.com）负责起容器、跑 verifier；TriWitness 的 Agent 循环在宿主上运行，
每个工具调用经 `environment.exec` 进容器执行。只依赖环境对象的三个方法（`exec` / `upload_file` /
`download_file` 不需要），所以这里不 import harbor，单测可以用假环境。

不支持快照 / diff（Terminal-Bench 类任务不是 git 仓库，判分由 Harbor 在同一容器里做）：
`snapshot` / `restore` / `diff` 抛 SandboxError，编排器与工具都已按“没有 diff”处理。
"""

from __future__ import annotations

import base64
import posixpath
import shlex
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import BackendName, ExecResult, SandboxSpec


class HarborEnv(Protocol):
    """Harbor `BaseEnvironment` 里用到的部分。"""

    async def exec(self, command: str, cwd: str | None = None, env: dict[str, str] | None = None,
                   timeout_sec: int | None = None) -> Any: ...  # fmt: skip
    async def upload_file(self, source_path: Path | str, target_path: str) -> Any: ...


def _cap(text: str, limit: int) -> tuple[str, bool]:
    data = text.encode("utf-8", "replace")
    if len(data) <= limit:
        return text, False
    head = data[: int(limit * 0.6)].decode("utf-8", "ignore")
    tail = data[-int(limit * 0.4) :].decode("utf-8", "ignore")
    return f"{head}\n…[输出过长，已截断]…\n{tail}", True


class HarborSandbox:
    backend: BackendName = "remote"

    def __init__(self, env: HarborEnv, *, workdir: str, max_output_bytes: int = 200_000) -> None:
        self.env = env
        self.id = f"harbor-{uuid.uuid4().hex[:10]}"
        self.spec = SandboxSpec(workdir=workdir, network="host", max_output_bytes=max_output_bytes)

    @classmethod
    async def attach(cls, env: HarborEnv) -> HarborSandbox:
        """工作目录取容器的当前目录（Harbor 任务镜像的 WORKDIR，常见 /app）。"""
        r = await env.exec("pwd")
        wd = (getattr(r, "stdout", "") or "").strip().splitlines()
        return cls(env, workdir=wd[-1] if wd and wd[-1].startswith("/") else "/app")

    def _abs(self, path: str) -> str:
        return path if path.startswith("/") else posixpath.normpath(posixpath.join(self.spec.workdir, path))

    async def exec(self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None,
                   env: dict[str, str] | None = None) -> ExecResult:  # fmt: skip
        started = time.monotonic()
        # 用 coreutils timeout 兜底（Harbor 的 timeout_sec 超时会抛错）；124 = 超时
        wrapped = f"timeout -k 5 {int(timeout_s)} bash -c {shlex.quote(cmd)}"
        try:
            r = await self.env.exec(wrapped, cwd=self._abs(cwd) if cwd else self.spec.workdir, env=env or None,
                                    timeout_sec=int(timeout_s) + 30)  # fmt: skip
        except TimeoutError:
            return ExecResult(exit_code=124, stdout="", stderr="超时", duration_ms=int((time.monotonic() - started)
                              * 1000), timed_out=True)  # fmt: skip
        limit = self.spec.max_output_bytes
        out, t1 = _cap(getattr(r, "stdout", None) or "", limit)
        err, t2 = _cap(getattr(r, "stderr", None) or "", limit)
        code = int(getattr(r, "return_code", 1))
        return ExecResult(exit_code=code, stdout=out, stderr=err, duration_ms=int((time.monotonic() - started) * 1000),
                          timed_out=code == 124, truncated=t1 or t2)  # fmt: skip

    async def read_file(self, path: str) -> bytes:
        p = self._abs(path)
        r = await self.env.exec(f"test -f {shlex.quote(p)} && base64 -w0 {shlex.quote(p)}")
        if int(getattr(r, "return_code", 1)) != 0:
            raise SandboxError(f"文件不存在：{path}")
        return base64.b64decode((getattr(r, "stdout", "") or "").strip())

    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None:
        p = self._abs(path)
        await self.env.exec(f"mkdir -p {shlex.quote(posixpath.dirname(p) or '/')}")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            tmp = Path(f.name)
        try:
            await self.env.upload_file(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)
        await self.env.exec(f"chmod {mode:o} {shlex.quote(p)}")

    async def snapshot(self, label: str) -> str:
        raise SandboxError("Harbor 环境不支持快照")

    async def restore(self, ref: str) -> None:
        raise SandboxError("Harbor 环境不支持快照")

    async def diff(self, base: str) -> str:
        raise SandboxError("Harbor 环境不支持 diff（判分由 Harbor 在同一容器里做）")

    async def close(self) -> None:  # 容器由 Harbor 管理
        return None


__all__ = ["HarborEnv", "HarborSandbox"]


# 外部任务的复现测试位置（W5-13 第二轮）：放在任务目录之外，判分只看任务目录；Agent 运行结束后另有兜底清理
# （triwitness.tools.repro.cleanup_repro_artifacts）。`--ak repro_dir=` 设为空串可关掉这条提示。
REPRO_DIR_DEFAULT = "/tmp/tw_repro"


def external_task_prompt(instruction: str, repro_dir: str | None = REPRO_DIR_DEFAULT) -> str:
    """给外部任务的说明追加一条运行约定：复现 / 临时测试写到 repro_dir，任务目录里只留题目要求的产物。"""
    if not repro_dir:
        return instruction
    return (f"{instruction.rstrip()}\n\n---\n（TriWitness 运行约定）这个任务按产物判分，不是代码仓库："
            f"复现测试或临时脚本请写在 {repro_dir}/ 下（例如 {repro_dir}/test_issue_1.py），不要放进任务目录；"
            "结束前任务目录里只保留题目要求的文件。")  # fmt: skip
