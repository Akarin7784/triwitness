"""测试替身（spec 003 §7）：FakeRouter（脚本化模型）与 FakeSandbox（内存文件系统 + 脚本化 exec）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from itertools import count
from typing import Any

from triwitness.core.errors import SandboxError
from triwitness.core.models import Usage
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.llm.types import LLMRequest, LLMResponse, Message, ToolCallSpec
from triwitness.sandbox.base import BackendName, ExecResult, SandboxSpec

_ids = count(1)


def call(name: str, **args: Any) -> ToolCallSpec:
    return ToolCallSpec(id=f"call_{next(_ids)}", name=name, arguments=json.dumps(args, ensure_ascii=False))


def say(*calls: ToolCallSpec, text: str | None = None) -> Message:
    return Message(role="assistant", content=text, tool_calls=list(calls) or None)


class FakeRouter:
    """按顺序返回脚本里的消息；每次调用按固定用量 / 成本记入预算守卫。"""

    def __init__(self, script: list[Message], *, cost_cny: float = 0.001, usage: Usage | None = None) -> None:
        self.script = list(script)
        self.cost_cny = cost_cny
        self.usage = usage or Usage(input_tokens=1000, cache_hit_tokens=900, cache_miss_tokens=100, output_tokens=50)
        self.requests: list[LLMRequest] = []

    async def complete(self, req: LLMRequest, *, guard: TaskBudgetGuard | None = None, **_: Any) -> LLMResponse:
        self.requests.append(req)
        if guard is not None:
            guard.precheck(0.0)
        msg = self.script.pop(0) if self.script else Message(role="assistant", content="（脚本结束）")
        resp = LLMResponse(message=msg, usage=self.usage, served_model="fake", finish_reason="stop", raw={},
                           model="deepseek/deepseek-flash", cost_cny=self.cost_cny, source="fake")  # fmt: skip
        if guard is not None:
            guard.record(self.usage, self.cost_cny)
        return resp


class FakeSandbox:
    backend: BackendName = "none"

    def __init__(
        self,
        files: dict[str, str | bytes] | None = None,
        *,
        exec_handler: Callable[[str, FakeSandbox], ExecResult] | None = None,
    ) -> None:
        self.id = "fake"
        self.spec = SandboxSpec()
        self.files: dict[str, bytes] = {
            self._key(k): v.encode() if isinstance(v, str) else v for k, v in (files or {}).items()
        }
        self.exec_handler = exec_handler
        self.commands: list[str] = []

    @staticmethod
    def _key(path: str) -> str:
        p = path.removeprefix("/workspace/repo/").removeprefix("./")
        if ".." in p.split("/"):
            raise SandboxError(f"路径越界：{path}")
        return p

    async def exec(self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None,
                   env: dict[str, str] | None = None) -> ExecResult:  # fmt: skip
        self.commands.append(cmd)
        if self.exec_handler is None:
            return ExecResult(exit_code=0, stdout="", stderr="", duration_ms=1, timed_out=False)
        return self.exec_handler(cmd, self)

    async def read_file(self, path: str) -> bytes:
        k = self._key(path)
        if k not in self.files:
            raise SandboxError(f"文件不存在：{path}")
        return self.files[k]

    async def write_file(self, path: str, data: bytes, mode: int = 0o644) -> None:
        self.files[self._key(path)] = data

    async def snapshot(self, label: str) -> str:
        return f"refs/tw/ckpt/fake/{label}"

    async def restore(self, ref: str) -> None:
        return None

    async def diff(self, base: str = "base") -> str:
        return ""

    async def close(self) -> None:
        return None
