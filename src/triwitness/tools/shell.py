"""bash / powershell / run_tests / finish（spec 003 §4、§5.2，W1-20）。"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from triwitness.core.errors import SandboxError
from triwitness.core.models import FileChange, FinishReport, ReproRef
from triwitness.permissions.shell import ShellParseError, parse_bash, program, strip_wrappers
from triwitness.tools.base import BaseTool, SideEffects, ToolContext, ToolResult

DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 600
INTERACTIVE = frozenset(
    {"vim", "vi", "nvim", "nano", "emacs", "less", "more", "top", "htop", "watch", "man", "ssh", "ftp", "telnet",
     "python -i", "ipython", "tmux", "screen"}
)  # fmt: skip


def _interactive_program(cmd: str) -> str | None:
    try:
        subs = parse_bash(cmd).commands
    except ShellParseError:
        return None
    for c in subs:
        c = strip_wrappers(c)
        if not c.words:
            continue
        prog = program(c)
        if prog in INTERACTIVE:
            return prog
        if prog in ("python", "python3") and len(c.words) == 1:
            return "python（无参数 = 交互式）"
        if (
            prog == "git"
            and len(c.words) > 1
            and c.words[1].value in ("rebase", "add")
            and any(w.value in ("-i", "--interactive", "-p", "--patch") for w in c.words[2:])
        ):
            return "git -i"
    return None


def _format(r: Any) -> str:
    parts = [f"exit_code={r.exit_code}" + ("（超时）" if r.timed_out else "")]
    if r.stdout:
        parts.append(r.stdout.rstrip())
    if r.stderr:
        parts.append("[stderr]\n" + r.stderr.rstrip())
    return "\n".join(parts)


class BashParams(BaseModel):
    command: str = Field(min_length=1, description="要执行的命令（非交互）")
    timeout_s: int = Field(default=DEFAULT_TIMEOUT, ge=1, le=MAX_TIMEOUT, description="超时秒数，默认 120，最大 600")


class Bash(BaseTool):
    name = "bash"
    Params = BashParams
    side_effects: SideEffects = "workspace"

    async def run(self, params: BashParams, ctx: ToolContext) -> ToolResult:
        prog = _interactive_program(params.command)
        if prog:
            return ToolResult(ok=False, content=f"不支持交互式命令：{prog}。请改用非交互方式"
                              "（如 cat / sed -n / git --no-pager）。",
                              error_code="interactive")  # fmt: skip
        try:
            r = await ctx.sandbox.exec(params.command, timeout_s=params.timeout_s)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        return ToolResult(ok=r.exit_code == 0, content=_format(r), exit_code=r.exit_code, truncated=r.truncated,
                          data={"timed_out": r.timed_out, "duration_ms": r.duration_ms},
                          error_code="timeout" if r.timed_out else None)  # fmt: skip


class PowerShell(Bash):
    """Windows 无沙箱且找不到 Git Bash 时替代 bash（spec 002 §5.3-6）。命令按 PowerShell 语法写。"""

    name = "powershell"
    Params = BashParams

    async def run(self, params: BashParams, ctx: ToolContext) -> ToolResult:
        try:
            r = await ctx.sandbox.exec(params.command, timeout_s=params.timeout_s)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        return ToolResult(ok=r.exit_code == 0, content=_format(r), exit_code=r.exit_code, truncated=r.truncated)


# ---------------------------------------------------------------- run_tests
_SUMMARY_RE = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)")
_FAILED_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)


def parse_pytest(output: str) -> dict[str, Any]:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    lines = [ln for ln in output.splitlines() if re.search(r"\b(passed|failed|error|no tests ran)\b", ln)]
    summary = lines[-1] if lines else ""
    for n, kind in _SUMMARY_RE.findall(summary):
        key: str = {"error": "errors", "xfailed": "skipped", "xpassed": "passed"}.get(kind) or kind
        counts[key] = counts.get(key, 0) + int(n)
    return {**counts, "failures": sorted(set(_FAILED_RE.findall(output))), "summary": summary.strip("= ").strip()}


class RunTestsParams(BaseModel):
    selector: str | None = Field(default=None, description="可选：测试选择器，如 tests/test_x.py::test_y 或 -k 表达式")


class RunTests(BaseTool):
    name = "run_tests"
    Params = RunTestsParams
    side_effects: SideEffects = "workspace"

    @staticmethod
    def command(ctx: ToolContext, params: RunTestsParams) -> str | None:
        if not ctx.test_command:
            return None
        return f"{ctx.test_command} {params.selector}" if params.selector else ctx.test_command

    async def run(self, params: RunTestsParams, ctx: ToolContext) -> ToolResult:
        cmd = self.command(ctx, params)
        if cmd is None:
            return ToolResult(
                ok=False, content="任务没有配置测试命令；请用 bash 运行测试", error_code="no_test_command"
            )
        try:
            r = await ctx.sandbox.exec(cmd, timeout_s=MAX_TIMEOUT)
        except SandboxError as e:
            return ToolResult(ok=False, content=str(e), error_code="sandbox")
        parsed = parse_pytest(r.stdout + "\n" + r.stderr)
        passed = r.exit_code == 0 and not r.timed_out
        ctx.state["last_run_tests"] = {**parsed, "command": cmd, "ok": passed}
        ctx.state.setdefault("tests_run", []).append(cmd)
        head = f"测试{'通过' if passed else '失败'}：{parsed['summary'] or f'exit_code={r.exit_code}'}"
        return ToolResult(ok=passed, content=head + "\n" + _format(r), exit_code=r.exit_code, truncated=r.truncated,
                          data={**parsed, "command": cmd, "ok": passed})  # fmt: skip


# ---------------------------------------------------------------- finish
class FinishParams(BaseModel):
    summary: str = Field(description="改了什么、为什么")
    changes: list[FileChange] = Field(description="改动的文件")
    repro: ReproRef | None = Field(default=None, description="复现测试（tests/tw_repro/test_issue_<n>.py）")
    tests_run: list[str] = Field(default_factory=list, description="运行过的测试命令")
    tests_passed: bool = Field(description="最近一次测试是否全部通过")
    confidence: float = Field(ge=0, le=1, description="0–1")
    open_risks: list[str] = Field(default_factory=list)


class Finish(BaseTool):
    name = "finish"
    Params = FinishParams
    terminal = True

    async def run(self, params: FinishParams, ctx: ToolContext) -> ToolResult:
        last = ctx.state.get("last_run_tests")
        if params.tests_passed and last is not None and not last["ok"]:
            fails = ", ".join(last.get("failures", [])[:5]) or last.get("summary", "")
            return ToolResult(ok=False, content=f"不能声明 tests_passed=true：最近一次 run_tests 失败（{fails}）。"
                              "先修复或如实填写。",
                              error_code="tests_failed")  # fmt: skip
        try:
            report = FinishReport.model_validate(params.model_dump())
        except ValidationError as e:  # pragma: no cover - Params 已校验
            return ToolResult(ok=False, content=str(e), error_code="bad_args")
        return ToolResult(ok=True, content="已结束", data={"finish_report": report.model_dump(mode="json")})
