"""测试替身（spec 003 §7）：FakeRouter（脚本化模型）与 FakeSandbox（内存文件系统 + 脚本化 exec）。"""

from __future__ import annotations

import difflib
import json
from collections.abc import Callable
from itertools import count
from typing import Any

from triwitness.core.errors import BudgetExceeded, SandboxError
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

    def __init__(
        self,
        script: list[Message],
        *,
        cost_cny: float = 0.001,
        usage: Usage | None = None,
        served_model: str = "fake",
        latency_ms: int = 0,
    ) -> None:
        self.script = list(script)
        self.cost_cny = cost_cny
        self.usage = usage or Usage(input_tokens=1000, cache_hit_tokens=900, cache_miss_tokens=100, output_tokens=50)
        self.served_model = served_model
        self.latency_ms = latency_ms
        self.requests: list[LLMRequest] = []

    async def complete(self, req: LLMRequest, *, guard: TaskBudgetGuard | None = None, **_: Any) -> LLMResponse:
        self.requests.append(req)
        if guard is not None:
            guard.precheck(0.0)
        msg = self.script.pop(0) if self.script else Message(role="assistant", content="（脚本结束）")
        thinking = req.thinking if req.thinking_override is None else req.thinking_override
        resp = LLMResponse(message=msg, usage=self.usage, served_model=self.served_model, raw={}, source="fake",
                           finish_reason="tool_calls" if msg.tool_calls else "stop", model="deepseek-flash",
                           cost_cny=self.cost_cny, peak=False, latency_ms=self.latency_ms,
                           thinking=thinking)  # fmt: skip
        if guard is not None:
            try:
                guard.record(self.usage, self.cost_cny)
            except BudgetExceeded as e:
                e.response = resp  # 与 LLMClient 一致：超限那次调用的回复随异常带回
                raise
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
        self.envs: list[dict[str, str] | None] = []
        self.snapshots: dict[str, dict[str, bytes]] = {"base": dict(self.files)}

    @staticmethod
    def _key(path: str) -> str:
        p = path.removeprefix("/workspace/repo/").removeprefix("./")
        if ".." in p.split("/"):
            raise SandboxError(f"路径越界：{path}")
        return p

    async def exec(self, cmd: str, *, timeout_s: int = 120, cwd: str | None = None,
                   env: dict[str, str] | None = None) -> ExecResult:  # fmt: skip
        self.commands.append(cmd)
        self.envs.append(dict(env) if env else None)
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
        ref = f"refs/tw/ckpt/fake/{label}"
        self.snapshots[ref] = dict(self.files)
        return ref

    async def restore(self, ref: str) -> None:
        if ref not in self.snapshots:
            raise SandboxError(f"快照不存在：{ref}")
        self.files = dict(self.snapshots[ref])

    async def diff(self, base: str = "base") -> str:
        """与 git diff 同形的统一 diff（只含文本文件、忽略 .tw/）。"""
        old = self.snapshots[base]
        out: list[str] = []
        for path in sorted(set(old) | set(self.files)):
            if path.startswith(".tw/") or "/.tw/" in path:
                continue
            a, b = old.get(path), self.files.get(path)
            if a == b:
                continue
            al = a.decode(errors="replace").splitlines(keepends=True) if a is not None else []
            bl = b.decode(errors="replace").splitlines(keepends=True) if b is not None else []
            out.append(f"diff --git a/{path} b/{path}\n")
            out.extend(difflib.unified_diff(al, bl, f"a/{path}" if a is not None else "/dev/null",
                                            f"b/{path}" if b is not None else "/dev/null"))  # fmt: skip
        return "".join(out)

    async def close(self) -> None:
        return None
