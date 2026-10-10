"""submit_repro（W3-04，04 §4.2 repro-first）：先复现、后修复。

Executor 写好复现测试后（**改源码之前**）调用：
- 工作区里只能有测试文件的改动，否则拒绝（error_code=repro_after_fix）；
- 复现命令在当前（未修复）代码上必须**失败**，通过就拒绝（error_code=repro_passes_on_base）；
- 确实无法复现（文档 / 重构类）→ `not_applicable=true` + 原因，走降级（风险至少 L1）。
结果写进 ctx.state["repro_check"]；finish 在 repro-first 模式下要求先有它。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import TEST_ENV
from triwitness.tools.base import BaseTool, SideEffects, ToolContext, ToolResult
from triwitness.tools.pytest_report import _TEST_FILE, changed_paths

MAX_REJECTS_HINT = 2  # 第 2 次被拒后提示可以声明 not_applicable
TIMEOUT_S = 300


class SubmitReproParams(BaseModel):
    path: str | None = Field(default=None, description="复现测试文件（建议 tests/tw_repro/test_issue_<n>.py）")
    cmd: str | None = Field(default=None, description="运行复现的命令，如 python -m pytest -q <path>")
    not_applicable: bool = Field(default=False, description="确实无法用测试复现（文档 / 重构类）时为 true")
    reason: str = Field(default="", description="not_applicable 的原因")


def _is_repro_side(path: str) -> bool:
    return (
        bool(_TEST_FILE.search(path))
        or "/tests/" in f"/{path}"
        or "/tw_repro/" in f"/{path}"
        or path.startswith(".tw/")
    )


class SubmitRepro(BaseTool):
    name = "submit_repro"
    Params = SubmitReproParams
    side_effects: SideEffects = "workspace"

    @staticmethod
    def command(params: SubmitReproParams) -> str | None:
        return None if params.not_applicable else params.cmd

    def _reject(self, ctx: ToolContext, code: str, msg: str) -> ToolResult:
        n = ctx.state["repro_rejects"] = int(ctx.state.get("repro_rejects", 0)) + 1
        if n >= MAX_REJECTS_HINT:
            msg += "\n如果这个 Issue 确实无法用测试复现，调用 submit_repro(not_applicable=true, reason=...)。"
        return ToolResult(ok=False, content=msg, error_code=code)

    def _accept(self, ctx: ToolContext, check: dict[str, Any], content: str) -> ToolResult:
        first = "repro_check" not in ctx.state
        ctx.state["repro_check"] = check
        hook = ctx.state.get("on_repro_accepted")
        if first and callable(hook):
            hook(check)
        return ToolResult(ok=True, content=content, data=check)

    async def run(self, params: SubmitReproParams, ctx: ToolContext) -> ToolResult:
        if params.not_applicable:
            if not params.reason.strip():
                return ToolResult(ok=False, content="not_applicable 需要写明原因（reason）", error_code="bad_args")
            return self._accept(ctx, {"status": "not_applicable", "reason": params.reason.strip()},
                                "已记录：无法复现（not_applicable），继续修复；风险等级至少 L1。")  # fmt: skip
        if not params.path or not params.cmd:
            return ToolResult(ok=False, content="需要 path 和 cmd（或 not_applicable=true）", error_code="bad_args")
        try:
            await ctx.sandbox.read_file(params.path)
        except SandboxError:
            return ToolResult(ok=False, content=f"复现文件不存在：{params.path}", error_code="not_found")
        try:
            changed = changed_paths(await ctx.sandbox.diff("base"))
        except SandboxError:
            changed = []
        src = [c for c in changed if not _is_repro_side(c)]
        if src:
            return self._reject(ctx, "repro_after_fix",
                                "repro-first：复现要在修改源码之前提交，以证明它能在原始代码上失败。"
                                f"当前已改了非测试文件：{', '.join(src[:5])}。请先撤销这些改动"
                                "（例如 git checkout -- <文件>），再提交复现。")  # fmt: skip
        try:
            r = await ctx.sandbox.exec(params.cmd, timeout_s=TIMEOUT_S, env=dict(TEST_ENV))
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        tail = (r.stdout + r.stderr)[-1500:]
        if r.exit_code == 0 and not r.timed_out:
            return self._reject(ctx, "repro_passes_on_base",
                                "复现在未修改的代码上**通过了**，没有证明问题存在。请对照 Issue 描述的行为、"
                                f"名字与错误信息改写断言。\n$ {params.cmd}\n{tail[-600:]}")  # fmt: skip
        check = {"status": "reproduced", "path": params.path, "cmd": params.cmd, "exit_code": r.exit_code,
                 "output_tail": tail}  # fmt: skip
        return self._accept(ctx, check, f"复现成立：在原始代码上失败（exit {r.exit_code}）。现在开始修复。\n"
                                        f"$ {params.cmd}\n{tail[-800:]}")  # fmt: skip


__all__ = ["SubmitRepro", "SubmitReproParams"]
