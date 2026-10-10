"""AgentLoop（spec 003 §5，W1-22）：模型 ↔ 工具循环、预算、截断、死循环检测、事件。"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from triwitness.core.errors import BudgetExceeded, SandboxError, TriWitnessError
from triwitness.core.events import LoopWarningPayload, ModelCallPayload, ToolCallPayload
from triwitness.core.models import Budget, FinishReport, Role
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.approvals import NeedsHuman
from triwitness.harness.config import HarnessConfig
from triwitness.harness.context import ContextManager
from triwitness.llm.types import LLMRequest, LLMResponse, Message
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolContext, ToolRegistry


class RouterLike(Protocol):
    async def complete(
        self,
        req: LLMRequest,
        *,
        guard: TaskBudgetGuard | None = ...,
        task_id: str | None = ...,
        mode: Any = ...,
        category: str = ...,
    ) -> LLMResponse: ...


class LoopOutcome(BaseModel):
    status: Literal["finished", "budget_exhausted", "stuck", "error", "needs_human"]
    finish: FinishReport | None = None
    steps: int
    reason: str | None = None


def prefix_hash(req: LLMRequest) -> str:
    """稳定前缀（system 消息 + 工具定义）的规范化哈希：同一配置下不同任务、不同次运行必须相同（W1-22）。"""
    import hashlib
    import json

    head = [m.model_dump(mode="json") for m in req.messages if m.role == "system"]
    blob = json.dumps({"system": head, "tools": req.tools or []}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_system_prompt(
    role_prompt: str,
    *,
    agents_md: str | None = None,
    tool_names: list[str] | None = None,
    agents_md_max_chars: int = 4000,
) -> str:
    """稳定前缀：角色提示 + AGENTS.md 摘要 + 工具清单（不含任何随任务变化的内容）。
    AGENTS.md 摘要的长度由 allocation.prefix 扣掉提示与工具 schema 后的余量决定（spec 007 §token 分配）。"""
    parts = [role_prompt.strip()]
    if agents_md and agents_md_max_chars > 0:
        parts.append("## 仓库约定（AGENTS.md 摘要）\n" + agents_md.strip()[:agents_md_max_chars])
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
        category: str = "dev",
    ) -> None:
        self.router = router
        self.category = category  # 全局账本的类别信封（eval 用 baseline 等）
        self.registry = registry
        self.system_prompt = system_prompt
        self.budget = budget
        self.emitter = emitter
        self.role: Role = role
        self.config = config or HarnessConfig.load()
        self.mode: Literal["background", "eval"] = mode
        self.guard = guard or TaskBudgetGuard(budget=budget)
        self.messages: list[Message] = []
        self.context: ContextManager | None = None

    async def _summarize(self, req: LLMRequest, task_id: str) -> LLMResponse:
        """压缩用的 summarizer 调用：同一个预算守卫与类别信封，并照常写 model_call 事件（role=summarizer）。"""
        resp = await self.router.complete(req, guard=self.guard, task_id=task_id, mode=self.mode,
                                          category=self.category)  # fmt: skip
        rec = self.emitter
        seq = rec.next_seq
        req_ref = rec.artifact(f"{seq}-request.json", {
            "role": req.role, "thinking": req.thinking,
            "messages": [m.model_dump(mode="json", exclude_none=True) for m in req.messages],
        })  # fmt: skip
        rec.emit(
            ModelCallPayload(model=_bare_model(resp.model or resp.served_model or "?"), served_model=resp.served_model,
                             thinking=req.thinking, usage=resp.usage, cost_cny=resp.cost_cny, peak=resp.peak,
                             latency_ms=resp.latency_ms, finish_reason=resp.finish_reason, request_ref=req_ref,
                             display="压缩摘要"),
            role="summarizer",
        )  # fmt: skip
        return resp

    async def run(self, task_prompt: str, ctx: ToolContext) -> LoopOutcome:
        cfg = self.config
        rec = self.emitter
        tools = self.registry.schemas()
        tool_names = [t["function"]["name"] for t in tools]
        cm = ContextManager(cfg, tools_chars=len(json.dumps(tools, ensure_ascii=False)),
                            summarize=lambda r: self._summarize(r, ctx.task_id))  # fmt: skip
        self.context = cm
        self.messages = [Message(role="system", content=self.system_prompt),
                         Message(role="user", content=cm.task_message(task_prompt))]  # fmt: skip
        no_tool = 0
        warnings = 0
        wrapped = False
        history: deque[tuple[str, bool]] = deque(maxlen=cfg.window)
        fail_streak = 0
        idle_streak = 0  # 信号 3：连续没有修改、也没有新读取目标的工具调用
        seen_reads: set[str] = set()
        steps = 0
        while True:
            # 上下文管理（spec 007）：先批量清理，仍超线再压缩；两者都会写 context_event
            cleared = cm.maybe_clear(self.messages)
            if cleared is not None:
                rec.emit(cleared, role=self.role)
            if cm.needs_compact(self.messages, steps):
                try:
                    compacted = await cm.compact(self.messages, steps, ctx)
                except BudgetExceeded as e:
                    return LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
                if compacted is not None:
                    self.messages, payload = compacted
                    rec.emit(payload, role=self.role)
            req = LLMRequest(role=self.role, messages=list(self.messages), tools=tools)
            try:
                resp = await self.router.complete(
                    req, guard=self.guard, task_id=ctx.task_id, mode=self.mode, category=self.category
                )
            except BudgetExceeded as e:
                return LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
            except TriWitnessError as e:
                return LoopOutcome(status="error", steps=steps, reason=f"{type(e).__name__}: {e}")
            steps += 1
            cm.observe(len(req.messages), resp.usage)
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
                limit, ratio = cfg.max_tool_result_chars, cfg.head_ratio_for(call.name)
                content, cut = truncate_for_model(result.content, limit, ratio)
                if cut:
                    saved = f"{ctx.tw_dir.rstrip('/')}/outputs/{ctx.step_index}.txt"
                    try:
                        await ctx.sandbox.write_file(saved, result.content.encode())
                        content += f"\n（完整输出已保存到 {saved}，可用 read_file 查看）"
                    except SandboxError:
                        saved = None
                else:
                    saved = None
                tool_msg = Message(role="tool", tool_call_id=call.id, name=call.name,
                                   content=cm.tool_content(call.name, content))  # fmt: skip
                cm.record_tool(call, result)
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
    if name == "submit_repro":
        st = (data or {}).get("status")
        if st == "reproduced":
            return f"$ submit_repro {args.get('path', '')} → 复现成立（原始代码上失败）"
        if st == "not_applicable":
            return "$ submit_repro → 无法复现（not_applicable）"
        return f"$ submit_repro {args.get('path', '')}".rstrip()
    if name == "finish":
        rep = data.get("finish_report") or {}
        return f"finish · 置信度 {rep.get('confidence', 0):.2f}"
    return f"$ {name}"


class ToolSignal:
    def __init__(self, kind: SignalKind, detail: str, reminder: str) -> None:
        self.kind: SignalKind = kind
        self.detail = detail
        self.reminder = reminder
