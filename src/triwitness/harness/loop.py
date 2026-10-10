"""AgentLoop（spec 003 §5，W1-21）：模型 ↔ 工具循环、预算、截断、死循环检测、事件。"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from triwitness.config import load_config
from triwitness.core.errors import BudgetExceeded, SandboxError, TriWitnessError
from triwitness.core.events import LoopWarningPayload, ModelCallPayload, ToolCallPayload
from triwitness.core.models import Budget, FinishReport, Role
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.approvals import NeedsHuman
from triwitness.harness.events import EventEmitter
from triwitness.llm.types import LLMRequest, LLMResponse, Message
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
        emitter: EventEmitter,
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
        self.messages = [Message(role="system", content=self.system_prompt), Message(role="user", content=task_prompt)]
        tools = self.registry.schemas()
        no_tool = 0
        warnings = 0
        wrapped = False
        history: deque[tuple[str, bool]] = deque(maxlen=cfg.window)
        fail_streak = 0
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
            self.emitter.emit(
                ModelCallPayload(model=resp.model or resp.served_model or "?", served_model=resp.served_model,
                                 thinking=req.thinking, usage=resp.usage, cost_cny=resp.cost_cny, peak=resp.peak,
                                 latency_ms=resp.latency_ms, finish_reason=resp.finish_reason),
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
                ctx.step_index = len(self.emitter.events)
                t0 = time.monotonic()
                try:
                    result, outcome = await self.registry.dispatch(call, ctx)
                except NeedsHuman as e:
                    return LoopOutcome(status="needs_human", steps=steps, reason=str(e))
                except SandboxError as e:
                    return LoopOutcome(status="error", steps=steps, reason=f"沙箱错误：{e}")
                content, cut = truncate_for_model(result.content, cfg.tool_result_max_chars, cfg.head_ratio)
                output_ref = None
                if cut:
                    output_ref = f"{ctx.tw_dir.rstrip('/')}/outputs/{ctx.step_index}.txt"
                    try:
                        await ctx.sandbox.write_file(output_ref, result.content.encode())
                        content += f"\n（完整输出已保存到 {output_ref}，可用 read_file 查看）"
                    except SandboxError:
                        output_ref = None
                self.emitter.emit(
                    ToolCallPayload(tool=call.name, ok=result.ok, exit_code=result.exit_code,
                                    duration_ms=int((time.monotonic() - t0) * 1000), output_ref=output_ref,
                                    truncated=cut or result.truncated, error_type=result.error_code,
                                    permission=outcome.permission if outcome else None,
                                    permission_rule=outcome.rule if outcome else None),
                    role=self.role,
                )  # fmt: skip
                self.messages.append(Message(role="tool", tool_call_id=call.id, name=call.name, content=content))
                tool = self.registry.get(call.name)
                if tool is not None and tool.terminal and result.ok:
                    report = FinishReport.model_validate((result.data or {}).get("finish_report"))
                    return LoopOutcome(status="finished", finish=report, steps=steps)
                # 死循环检测（spec 003 §5.4 信号 1、2）
                sig = _signature(call.name, call.arguments)
                history.append((sig, result.ok))
                fail_streak = 0 if result.ok else fail_streak + 1
                signal: ToolSignal | None = None
                repeats = sum(1 for s, _ in history if s == sig)
                if repeats >= cfg.repeat_threshold:
                    signal = ToolSignal("repeat_action", f"{call.name} × {repeats}")
                elif fail_streak >= cfg.failure_threshold:
                    signal = ToolSignal("consecutive_failures", f"连续 {fail_streak} 次失败")
                if signal is not None:
                    warnings += 1
                    history.clear()
                    fail_streak = 0
                    self.emitter.emit(LoopWarningPayload(signal=signal.kind, level=min(warnings, 3),
                                                         detail=signal.detail), role=self.role)  # fmt: skip
                    if warnings >= cfg.max_warnings:
                        return LoopOutcome(status="stuck", steps=steps, reason=f"死循环：{signal.detail}")
                    key = "repeat" if signal.kind == "repeat_action" else "failures"
                    self.messages.append(Message(role="user", content=cfg.reminder(key, detail=signal.detail)))
            if self.guard.should_wrap_up and not wrapped:
                wrapped = True
                self.messages.append(Message(role="user", content=cfg.reminder("wrap_up")))


class ToolSignal:
    def __init__(self, kind: Literal["repeat_action", "consecutive_failures"], detail: str) -> None:
        self.kind: Literal["repeat_action", "consecutive_failures"] = kind
        self.detail = detail
