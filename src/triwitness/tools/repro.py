"""submit_repro（W3-04，04 §4.2 repro-first）：先复现、后修复。

Executor 写好复现测试后（**改源码之前**）调用：
- 工作区里只能有测试文件的改动，否则拒绝（error_code=repro_after_fix）；
- 复现命令在当前（未修复）代码上必须**失败**，通过就拒绝（error_code=repro_passes_on_base）；
- 命令本身跑不起来（找不到命令 / 没装测试框架 / pytest 用法错误或没收集到测试）不算失败（error_code=repro_cmd_broken）；
- 确实无法复现（文档 / 重构类）→ `not_applicable=true` + 原因，走降级（风险至少 L1）。
结果写进 ctx.state["repro_check"]；finish 在 repro-first 模式下要求先有它。
"""

from __future__ import annotations

import posixpath
import re
import shlex
from typing import Any

from pydantic import BaseModel, Field

from triwitness.core.errors import SandboxError
from triwitness.sandbox.base import TEST_ENV
from triwitness.tools.base import BaseTool, SideEffects, ToolContext, ToolResult
from triwitness.tools.pytest_report import _TEST_FILE, changed_paths

MAX_REJECTS_HINT = 2  # 第 2 次被拒后提示可以声明 not_applicable
TIMEOUT_S = 300
# 0.3.1 真实 key 首跑发现：`python: command not found`（exit 127）被当成「复现成立」，复验时自然两边都失败
_BROKEN_OUT = re.compile(
    r"command not found|is not recognized as an internal or external command|No module named '?(pytest|py\.test)\b"
)


def broken_command(cmd: str, exit_code: int, output: str) -> str | None:
    """复现命令自身无法运行时给出原因；正常的测试失败返回 None。"""
    if exit_code in (126, 127):
        return f"命令无法执行（exit {exit_code}）"
    if m := _BROKEN_OUT.search(output):
        return f"命令无法运行：{m.group(0)}"
    if "pytest" in cmd and exit_code in (4, 5):
        return "pytest 用法错误或没有收集到测试（exit 4/5）"
    return None


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
        if why := broken_command(params.cmd, r.exit_code, tail):
            return self._reject(ctx, "repro_cmd_broken",
                                f"{why}，这不是复现失败，而是命令本身跑不起来。请先用 bash 确认可用的解释器"
                                "和测试框架（例如 python3 / 项目自带的 unittest），再提交能真正运行断言的命令。"
                                f"\n$ {params.cmd}\n{tail[-600:]}")  # fmt: skip
        check = {"status": "reproduced", "path": params.path, "cmd": params.cmd, "exit_code": r.exit_code,
                 "output_tail": tail}  # fmt: skip
        return self._accept(ctx, check, f"复现成立：在原始代码上失败（exit {r.exit_code}）。现在开始修复。\n"
                                        f"$ {params.cmd}\n{tail[-800:]}")  # fmt: skip


__all__ = ["SubmitRepro", "SubmitReproParams"]


# —— 外部任务（Harbor / Terminal-Bench）的复现产物清理（W5-13）——
# 这类任务没有“仓库 + diff”，判分直接看容器里的产物目录；复现测试留在里面会被当成多余文件
# （polyglot-c-py：verifier 要求 /app/polyglot 里只有 main.py.c，实际多了 tests/tw_repro/）。
# 做法：运行前记下已有的相关目录，运行后只删“新出现的”复现 / 缓存目录，再删因此变空、且是新建的 tests 目录。
ARTIFACT_DIRS: tuple[str, ...] = ("tw_repro", ".pytest_cache", "__pycache__")
_PRUNE = (".git", "node_modules", ".venv", "venv", "site-packages", "dist-packages")
_MAX_DEPTH = 8


def _find_cmd(root: str) -> str:
    prune = " -o ".join(f"-name {shlex.quote(n)}" for n in _PRUNE)
    names = " -o ".join(f"-name {shlex.quote(n)}" for n in ("tests", *ARTIFACT_DIRS))
    return (f"find {shlex.quote(root)} -maxdepth {_MAX_DEPTH} \\( {prune} \\) -prune -o "
            f"-type d \\( {names} \\) -print 2>/dev/null || true")  # fmt: skip


async def snapshot_repro_dirs(sandbox: Any, root: str) -> set[str]:
    """运行前：root 下已有的 tests / tw_repro / .pytest_cache / __pycache__ 目录（这些不会被清理）。"""
    r = await sandbox.exec(_find_cmd(root), timeout_s=60)
    return {ln for ln in r.stdout.splitlines() if ln.strip()}


async def cleanup_repro_artifacts(sandbox: Any, root: str, before: set[str]) -> list[str]:
    """运行后：删掉新出现的复现 / 缓存目录与因此变空的新 tests 目录；返回删掉的路径（root 之外的不碰）。"""
    r = await sandbox.exec(_find_cmd(root), timeout_s=60)
    new = sorted({ln for ln in r.stdout.splitlines() if ln.strip()} - before)
    doomed = [p for p in new if posixpath.basename(p) in ARTIFACT_DIRS]
    doomed = [p for p in doomed if not any(p.startswith(q + "/") for q in doomed)]  # 父目录删了，子目录不用再删
    removed: list[str] = []
    if doomed:
        res = await sandbox.exec("rm -rf -- " + " ".join(shlex.quote(p) for p in doomed), timeout_s=60)
        if res.exit_code == 0:
            removed += doomed
    # 新建的 tests 目录：由深到浅，只删已经空了的（rmdir 不会删非空目录）
    for p in sorted((p for p in new if posixpath.basename(p) == "tests"), key=lambda s: -s.count("/")):
        res = await sandbox.exec(f"rmdir -- {shlex.quote(p)} 2>/dev/null", timeout_s=30)
        if res.exit_code == 0:
            removed.append(p)
    return removed
