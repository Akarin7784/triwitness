"""AgentLoop（spec 003 §5，W1-22）：模型 ↔ 工具循环、预算、截断、死循环检测、事件。"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from triwitness.config import load_config
from triwitness.core.errors import BudgetExceeded, SandboxError, TriWitnessError
from triwitness.core.events import LoopWarningPayload, ModelCallPayload, ToolCallPayload
from triwitness.core.models import Budget, FinishReport, Role
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.approvals import NeedsHuman
from triwitness.llm.types import LLMRequest, LLMResponse, Message
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolContext, ToolRegistry


class RouterLike(Protocol):
    async def complete(self, req: LLMRequest, **kw: Any) -> LLMResponse: ...


class HarnessConfig(BaseModel):
    stuck_after_no_tool: int = 3
    tool_result_max_chars: int = 32_000
    head_ratio: float = 0.6
    window: int = 8
    repeat_threshold: int = 3
    failure_threshold: int = 5
    no_progress_threshold: int = 6
    max_warnings: int = 3
    reminders: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def load(cls, name: str = "harness/baseline.yaml") -> HarnessConfig:
        cfg = load_config(name)
        return cls(**cfg.get("loop", {}), **cfg.get("loop_detection", {}), reminders=cfg.get("reminders", {}))

    def reminder(self, key: str, **kw: str) -> str:
        defaults = {
            "no_tool": "请调用工具继续，或调用 finish 结束。",
            "wrap_up": "预算已用到警戒线，请尽快收尾。",
            "repeat": "你在重复同样的动作（{detail}），请换个思路。",
            "failures": "连续多次工具调用失败（{detail}），请换一种做法。",
            "no_progress": "已经 {detail}，请修改代码、运行测试或调用 finish。",
        }
        return self.reminders.get(key, defaults[key]).format(**kw)


class LoopOutcome(BaseModel):
    status: Literal["finished", "budget_exhausted", "stuck", "error", "needs_human"]
    finish: FinishReport | None = None
    steps: int
    reason: str | None = None


def build_system_prompt(role_prompt: str, *, agents_md: str | None = None, tool_names: list[str] | None = None) -> str:
    """稳定前缀：角色提示 + AGENTS.md 摘要 + 工具清单（不含任何随任务变化的内容）。"""
    parts = [role_prompt.strip()]
    if agents_md:
        parts.append("## 仓库约定（AGENTS.md 摘要）\n" + agents_md.strip()[:4000])
    if tool_names:
        parts.append("## 可用工具\n" + "、".join(sorted(tool_names)))
    return "\n\n".join(parts)


def truncate_for_model(text: str, max_chars: int, head_ratio: float) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    head = int(max_chars * head_ratio)
    tail = max_chars - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n…[省略 {omitted} 字符]…\n{text[-tail:]}", True


def _signature(name: str, arguments: str) -> str:
    try:
        norm = json.dumps(json.loads(arguments or "{}"), sort_keys=True, ensure_ascii=False)
    except json.JSONDecodeError:
        norm = arguments
    return hashlib.sha256(f"{name}\0{norm}".encode()).hexdigest()[:16]


class AgentLoop:
    def __init__(
        self,
        router: RouterLike,
        registry: ToolRegistry,
        *,
        system_prompt: str,
        budget: Budget,
        emitter: TrajectoryRecorder,
        role: Role = "executor",
        config: HarnessConfig | None = None,
        mode: Literal["background", "eval"] = "background",
        guard: TaskBudgetGuard | None = None,
    ) -> None:
        self.router = router
        self.registry = registry
        self.system_prompt = system_prompt
        self.budget = budget
        self.emitter = emitter
        self.role: Role = role
        self.config = config or HarnessConfig.load()
        self.mode: Literal["background", "eval"] = mode
        self.guard = guard or TaskBudgetGuard(budget=budget)
        self.messages: list[Message] = []

    async def run(self, task_prompt: str, ctx: ToolContext) -> LoopOutcome:
        cfg = self.config
        rec = self.emitter
        self.messages = [Message(role="system", content=self.system_prompt), Message(role="user", content=task_prompt)]
        tools = self.registry.schemas()
        tool_names = [t["function"]["name"] for t in tools]
        no_tool = 0
        warnings = 0
        wrapped = False
        history: deque[tuple[str, bool]] = deque(maxlen=cfg.window)
        fail_streak = 0
        idle_streak = 0  # 信号 3：连续没有修改、也没有新读取目标的工具调用
        seen_reads: set[str] = set()
        steps = 0
        while True:
            req = LLMRequest(role=self.role, messages=list(self.messages), tools=tools)
            try:
                resp = await self.router.complete(req, guard=self.guard, task_id=ctx.task_id, mode=self.mode)
            except BudgetExceeded as e:
                return LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
            except TriWitnessError as e:
                return LoopOutcome(status="error", steps=steps, reason=f"{type(e).__name__}: {e}")
            steps += 1
            seq = rec.next_seq
            req_ref = rec.artifact(f"{seq}-request.json", {
                "role": self.role, "thinking": req.thinking, "tools": tool_names,
                "messages": [m.model_dump(mode="json", exclude_none=True) for m in req.messages],
            })  # fmt: skip
            resp_ref = rec.artifact(f"{seq}-response.json", {
                "message": resp.message.model_dump(mode="json", exclude_none=True),
                "usage": resp.usage.model_dump(mode="json"), "served_model": resp.served_model,
                "finish_reason": resp.finish_reason, "degraded": resp.degraded,
            })  # fmt: skip
            rec.emit(
                ModelCallPayload(model=_bare_model(resp.model or resp.served_model or "?"),
                                 served_model=resp.served_model, thinking=req.thinking, usage=resp.usage,
                                 cost_cny=resp.cost_cny, peak=resp.peak, latency_ms=resp.latency_ms,
                                 finish_reason=resp.finish_reason, request_ref=req_ref, response_ref=resp_ref,
                                 display=model_display(resp.message)),
                role=self.role,
            )  # fmt: skip
            self.messages.append(resp.message)
            # 客户端在 record() 里已检查上限；这里再查一次，覆盖不经 LLMClient 的路由
            try:
                self.guard.precheck(0.0)
            except BudgetExceeded as e:
                return LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
            calls = resp.message.tool_calls or []
            if not calls:
                no_tool += 1
                if no_tool >= cfg.stuck_after_no_tool:
                    return LoopOutcome(status="stuck", steps=steps, reason=f"连续 {no_tool} 次没有调用工具")
                self.messages.append(Message(role="user", content=cfg.reminder("no_tool")))
                continue
            no_tool = 0
            for call in calls:
                ctx.step_index = rec.next_seq
                t0 = rec.monotonic()
                try:
                    result, outcome = await self.registry.dispatch(call, ctx)
                except NeedsHuman as e:
                    return LoopOutcome(status="needs_human", steps=steps, reason=str(e))
                except SandboxError as e:
                    return LoopOutcome(status="error", steps=steps, reason=f"沙箱错误：{e}")
                duration_ms = max(0, round((rec.monotonic() - t0) * 1000))
                content, cut = truncate_for_model(result.content, cfg.tool_result_max_chars, cfg.head_ratio)
                if cut:
                    saved = f"{ctx.tw_dir.rstrip('/')}/outputs/{ctx.step_index}.txt"
                    try:
                        await ctx.sandbox.write_file(saved, result.content.encode())
                        content += f"\n（完整输出已保存到 {saved}，可用 read_file 查看）"
                    except SandboxError:
                        saved = None
                else:
                    saved = None
                tool_msg = Message(role="tool", tool_call_id=call.id, name=call.name, content=content)
                seq = rec.next_seq
                output_ref = rec.artifact(f"{seq}-output.txt", result.content) or saved
                message_ref = rec.artifact(f"{seq}-tool.json", tool_msg.model_dump(mode="json", exclude_none=True))
                rec.emit(
                    ToolCallPayload(tool=call.name, ok=result.ok, exit_code=result.exit_code, duration_ms=duration_ms,
                                    output_ref=output_ref, message_ref=message_ref,
                                    truncated=cut or result.truncated, error_type=result.error_code,
                                    permission=outcome.permission if outcome else None,
                                    permission_rule=outcome.rule if outcome else None,
                                    display=tool_display(call.name, call.arguments, result)),
                    role=self.role,
                )  # fmt: skip
                self.messages.append(tool_msg)
                tool = self.registry.get(call.name)
                if tool is not None and tool.terminal and result.ok:
                    report = FinishReport.model_validate((result.data or {}).get("finish_report"))
                    return LoopOutcome(status="finished", finish=report, steps=steps)
                # 死循环检测（spec 003 §5.4）
                sig = _signature(call.name, call.arguments)
                history.append((sig, result.ok))
                fail_streak = 0 if result.ok else fail_streak + 1
                if _made_progress(tool, call.name, sig, result.ok, seen_reads):
                    idle_streak = 0
                else:
                    idle_streak += 1
                signal: ToolSignal | None = None
                repeats = sum(1 for s, _ in history if s == sig)
                if repeats >= cfg.repeat_threshold:
                    signal = ToolSignal("repeat_action", f"{call.name} × {repeats}", "repeat")
                elif fail_streak >= cfg.failure_threshold:
                    signal = ToolSignal("consecutive_failures", f"连续 {fail_streak} 次失败", "failures")
                elif idle_streak >= cfg.no_progress_threshold:
                    signal = ToolSignal("no_progress", f"连续 {idle_streak} 步没有修改文件、也没有新的读取目标",
                                        "no_progress")  # fmt: skip
                if signal is not None:
                    warnings += 1
                    history.clear()
                    fail_streak = 0
                    idle_streak = 0
                    rec.emit(LoopWarningPayload(signal=signal.kind, level=min(warnings, 3), detail=signal.detail,
                                                display=_WARN_DISPLAY[signal.kind]), role=self.role)  # fmt: skip
                    if warnings >= cfg.max_warnings:
                        return LoopOutcome(status="stuck", steps=steps, reason=f"死循环：{signal.detail}")
                    self.messages.append(Message(role="user", content=cfg.reminder(signal.reminder,
                                                                                   detail=signal.detail)))  # fmt: skip
            if self.guard.should_wrap_up and not wrapped:
                wrapped = True
                self.messages.append(Message(role="user", content=cfg.reminder("wrap_up")))


SignalKind = Literal["repeat_action", "consecutive_failures", "no_progress"]
_WARN_DISPLAY: dict[str, str] = {
    "repeat_action": "⚠ 重复动作：换个思路",
    "consecutive_failures": "⚠ 连续失败：换个做法",
    "no_progress": "⚠ 无进展",
}
_READ_TOOLS = frozenset({"read_file", "list_files", "grep"})


def _made_progress(tool: Any, name: str, sig: str, ok: bool, seen_reads: set[str]) -> bool:
    """有进展 = 成功的修改（有副作用的工具，run_tests 除外）或第一次出现的读取目标。"""
    if not ok:
        return False
    if name in _READ_TOOLS:
        if sig in seen_reads:
            return False
        seen_reads.add(sig)
        return True
    return tool is not None and tool.side_effects == "workspace" and name != "run_tests"


def _bare_model(name: str) -> str:
    return name.rsplit("/", 1)[-1]


def _short(text: str, n: int = 120) -> str:
    one = " ".join(text.split())
    return one if len(one) <= n else one[: n - 1] + "…"


def model_display(msg: Message) -> str | None:
    if msg.content and msg.content.strip():
        return _short(msg.content.strip().splitlines()[0])
    if msg.tool_calls:
        return "→ " + "、".join(c.name for c in msg.tool_calls)
    return None


def tool_display(name: str, arguments: str, result: Any) -> str:
    """推流里的一行：`$ tool 目标 → 摘要`；失败时 `tool：错误首行`。"""
    try:
        args: dict[str, Any] = json.loads(arguments or "{}")
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        args = {}
    if not result.ok and name != "run_tests":
        first = (result.content or "").strip().splitlines()[0] if (result.content or "").strip() else "失败"
        return _short(f"{name}：{first}")
    data = result.data or {}
    if name in ("bash", "powershell"):
        head = f"$ {_short(str(args.get('command', '')), 100)}"
        return head if result.exit_code in (0, None) else f"{head} → 退出码 {result.exit_code}"
    if name == "read_file":
        rng = ""
        if args.get("start_line") or args.get("end_line"):
            rng = f" {args.get('start_line', 1)}-{args.get('end_line', '')}".rstrip("-")
        return f"$ read_file {args.get('path', '')}{rng}"
    if name in ("write_file", "edit_file", "list_files"):
        return f"$ {name} {args.get('path', '.')}".rstrip()
    if name == "grep":
        return _short(f"$ grep {args.get('pattern', '')} {args.get('path', '.')}")
    if name == "run_tests":
        parts = [f"{data[k]} {k}" for k in ("failed", "passed", "skipped") if data.get(k)]
        return "$ run_tests → " + (", ".join(parts) if parts else ("通过" if result.ok else "失败"))
    if name == "finish":
        rep = data.get("finish_report") or {}
        return f"finish · 置信度 {rep.get('confidence', 0):.2f}"
    return f"$ {name}"


class ToolSignal:
    def __init__(self, kind: SignalKind, detail: str, reminder: str) -> None:
        self.kind: SignalKind = kind
        self.detail = detail
        self.reminder = reminder
