"""AgentLoop（spec 003 §5，W1-22）：模型 ↔ 工具循环、预算、截断、死循环检测、事件。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import deque
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from triwitness.core.errors import BudgetExceeded, ContextOverflow, SandboxError, TriWitnessError
from triwitness.core.events import LoopWarningPayload, ModelCallPayload, ToolCallPayload, billing
from triwitness.core.models import Budget, FinishReport, Role
from triwitness.core.redact import redact_text
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.approvals import NeedsHuman
from triwitness.harness.config import HarnessConfig
from triwitness.harness.context import ContextManager
from triwitness.harness.deltas import DeltaWriter
from triwitness.harness.replay import journal_write
from triwitness.llm.stream import streaming
from triwitness.llm.types import LLMRequest, LLMResponse, Message, effective_thinking
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
        executor_vendor: Any = ...,
    ) -> LLMResponse: ...


class LoopOutcome(BaseModel):
    # context_thrash：连续无效压缩；context_overflow：强制清理 + 压缩后仍超窗口硬上限 / 厂商连续两次报上下文超限
    status: Literal[
        "finished",
        "budget_exhausted",
        "stuck",
        "error",
        "needs_human",
        "cancelled",
        "context_thrash",
        "context_overflow",
    ]
    finish: FinishReport | None = None
    submission: dict[str, Any] | None = None  # 角色终止工具（submit_plan / submit_review）提交的结构化结果
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
        stream: bool = False,
        hard_limit: int | None = None,
        task_intro: str | None = None,
        effort: Literal["low", "high", "max"] | None = None,
        executor_vendor: str | None = None,
        thinking: bool | None = None,
        temperature: float | None = None,
        force_submit: str | None = None,
    ) -> None:
        # Reviewer 的 loop 带上 Executor 的厂商：vendor_policy=cross_vendor 时路由据此排除同厂商（W4-08）
        self.executor_vendor = executor_vendor
        self.task_intro = task_intro  # 角色开场白（Planner / Reviewer）；None = Executor 的默认措辞
        self.effort: Literal["low", "high", "max"] | None = effort  # 覆盖路由的思考强度（同厂商异构评审变体）
        self.thinking = thinking  # 覆盖路由的思考开关（None = 路由配置；W4-14 默认评审 checklist 非思考）
        self.temperature = temperature  # 非思考时生效（思考模式下适配器丢弃）
        # 最后一次允许的调用强制调用这个终止工具（角色的 submit_*；spec 010 §6.2“评审必须给结论”）。
        # DeepSeek 思考模式不接受强制 tool_choice，所以这一次关思考。
        self.force_submit = force_submit
        self.trusted_tail = ""  # 块外的编排器说明（例：Plan），拼在 Issue 块之后
        self.router = router
        self.hard_limit = hard_limit  # 窗口硬上限覆盖（测试用）；默认按角色从 configs/models.yaml 推导
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
        # 交互运行（tw run --jsonl）：写流式增量与工具行预览；eval / 批量运行不写，轨迹保持精简
        self.stream = stream

    async def _summarize(self, req: LLMRequest, task_id: str) -> LLMResponse:
        """压缩用的 summarizer 调用：同一个预算守卫与类别信封，并照常写 model_call 事件（role=summarizer）。"""
        resp = await self.router.complete(req, guard=self.guard, task_id=task_id, mode=self.mode,
                                          category=self.category)  # fmt: skip
        rec = self.emitter
        seq = rec.next_seq
        req_ref = rec.artifact(f"{seq}-request.json", {
            "role": req.role, "thinking": effective_thinking(req, resp),
            "messages": [m.model_dump(mode="json", exclude_none=True) for m in req.messages],
        })  # fmt: skip
        rec.emit(
            ModelCallPayload(model=_bare_model(resp.model or resp.served_model or "?"), served_model=resp.served_model,
                             thinking=effective_thinking(req, resp), usage=resp.usage, **billing(resp), peak=resp.peak,
                             latency_ms=resp.latency_ms, finish_reason=resp.finish_reason, request_ref=req_ref,
                             display="压缩摘要"),
            role="summarizer",
        )  # fmt: skip
        return resp

    def _record_call(self, req: LLMRequest, resp: LLMResponse, call_id: str, tool_names: list[str]) -> None:
        """写 model_call 事件与请求 / 回复附件（账本之外的另一份成本事实；必须每次已付费调用都写）。"""
        rec = self.emitter
        seq = rec.next_seq
        req_ref = rec.artifact(f"{seq}-request.json", {
            "role": self.role, "thinking": effective_thinking(req, resp), "tools": tool_names,
            "messages": [m.model_dump(mode="json", exclude_none=True) for m in req.messages],
            **({"tool_choice": req.tool_choice} if req.tool_choice != "auto" else {}),
        })  # fmt: skip
        resp_ref = rec.artifact(f"{seq}-response.json", {
            "message": resp.message.model_dump(mode="json", exclude_none=True),
            "usage": resp.usage.model_dump(mode="json"), "served_model": resp.served_model,
            "finish_reason": resp.finish_reason, "degraded": resp.degraded,
        })  # fmt: skip
        rec.emit(
            ModelCallPayload(call_id=call_id if self.stream else None,
                             model=_bare_model(resp.model or resp.served_model or "?"),
                             served_model=resp.served_model, thinking=effective_thinking(req, resp), usage=resp.usage,
                             **billing(resp), peak=resp.peak, latency_ms=resp.latency_ms,
                             finish_reason=resp.finish_reason, request_ref=req_ref, response_ref=resp_ref,
                             display=model_display(resp.message)),
            role=self.role,
        )  # fmt: skip

    async def _terminal_at_cap(self, msg: Message, ctx: ToolContext, steps: int) -> LoopOutcome | None:
        """安全上限在这次调用后触发：回复里若有终止工具（finish / submit_*）就照常执行并接住提交——
        这次调用在上限之内、已经付费，提交不该丢（W4-14：第 20 次调用里的 submit_review 曾被当成没结论）。"""
        for call in msg.tool_calls or []:
            tool = self.registry.get(call.name)
            if tool is None or not tool.terminal:
                continue
            ctx.step_index = self.emitter.next_seq
            try:
                result, outcome, duration_ms = await self._timed_dispatch(call, ctx)
            except (NeedsHuman, SandboxError):
                return None
            tool_msg = Message(role="tool", tool_call_id=call.id, name=call.name, content=result.content)
            seq = self.emitter.next_seq
            self.emitter.emit(
                ToolCallPayload(tool=call.name, ok=result.ok, exit_code=result.exit_code, duration_ms=duration_ms,
                                output_ref=self.emitter.artifact(f"{seq}-output.txt", result.content),
                                message_ref=self.emitter.artifact(
                                    f"{seq}-tool.json", tool_msg.model_dump(mode="json", exclude_none=True)),
                                error_type=result.error_code,
                                permission=outcome.permission if outcome else None,
                                permission_rule=outcome.rule if outcome else None,
                                display=tool_display(call.name, call.arguments, result)),
                role=self.role,
            )  # fmt: skip
            self.messages.append(tool_msg)
            if not result.ok:
                return None
            data = result.data or {}
            self.seal_dangling(f"本轮已在 {call.name} 处结束（安全上限）")
            if "finish_report" in data:
                return LoopOutcome(status="finished", finish=FinishReport.model_validate(data.get("finish_report")),
                                   steps=steps)  # fmt: skip
            return LoopOutcome(status="finished", submission=data.get("submission"), steps=steps)
        return None

    def _thrash(self, cm: ContextManager, steps: int) -> LoopOutcome:
        return LoopOutcome(status="context_thrash", steps=steps,
                           reason=f"连续 {cm.ineffective} 次压缩后上下文仍高于压缩线"
                                  f"（{cm.estimate(self.messages) // 1000}K）："
                                  "单个结果过大或尾部无法压缩，停下以免反复压缩")  # fmt: skip

    async def _fit_window(
        self, cm: ContextManager, steps: int, ctx: ToolContext, *, force_compact: bool
    ) -> LoopOutcome | None:
        """强制清理（不看阈值），仍超窗口（或 force_compact）就强制压缩；还超就以 context_overflow 结束。"""
        rec = self.emitter
        cleared = cm.maybe_clear(self.messages, force=True)
        if cleared is not None:
            rec.emit(cleared, role=self.role)
        if force_compact or cm.over_window(self.messages):
            try:
                compacted = await cm.compact(self.messages, steps, ctx)
            except BudgetExceeded as e:
                return LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
            if compacted is not None:
                self.messages, payload = compacted
                rec.emit(payload, role=self.role)
            if cm.thrashing:
                return self._thrash(cm, steps)
        if cm.over_window(self.messages):
            return LoopOutcome(status="context_overflow", steps=steps,
                               reason=f"清理并压缩后上下文仍约 {cm.estimate(self.messages) // 1000}K，"
                                      f"超过窗口硬上限 {cm.hard_limit // 1000}K")  # fmt: skip
        return None

    def _parallel_ok(self, call: Any) -> bool:
        """可并发：配置开启、在只读白名单里、工具声明无副作用且不是终止工具（CC 报告 §2：只读并行、写串行）。"""
        if not self.config.parallel_read_tools or call.name not in PARALLEL_SAFE_TOOLS:
            return False
        tool = self.registry.get(call.name)
        return tool is not None and tool.side_effects == "none" and not tool.terminal

    async def _timed_dispatch(self, call: Any, ctx: ToolContext) -> tuple[Any, Any, int]:
        t0 = self.emitter.monotonic()
        tool = self.registry.get(call.name)
        effects = getattr(tool, "side_effects", "none") if tool is not None else "none"
        run_dir = getattr(self.emitter, "run_dir", None)
        if effects != "none":  # 预写日志（spec 011 §3.3）：进程被杀时能知道哪个有副作用的工具正在执行
            args = call.arguments if isinstance(call.arguments, str) else json.dumps(call.arguments, ensure_ascii=False)
            summary = redact_text(_short(args, 160))
            journal_write(run_dir, {"phase": "start", "call_id": call.id, "tool": call.name, "side_effects": effects,
                                    "seq": self.emitter.next_seq, "role": self.role, "summary": summary})  # fmt: skip
        result, outcome = await self.registry.dispatch(call, ctx)
        if effects != "none":
            journal_write(run_dir, {"phase": "end", "call_id": call.id, "ok": bool(result.ok)})
        return result, outcome, max(0, round((self.emitter.monotonic() - t0) * 1000))

    def seal_dangling(self, reason: str = "任务在此中断") -> int:
        """给最后一条 assistant 消息里还没有结果的 tool_call 补一条错误结果（CC 报告 §2），保证历史合法、可续写。"""
        idx = next((i for i in range(len(self.messages) - 1, -1, -1)
                    if self.messages[i].role == "assistant"), None)  # fmt: skip
        if idx is None or not self.messages[idx].tool_calls:
            return 0
        answered = {m.tool_call_id for m in self.messages[idx + 1 :] if m.role == "tool"}
        missing = [c for c in self.messages[idx].tool_calls or [] if c.id not in answered]
        if not missing:
            return 0
        # 结果必须紧跟在 assistant 之后、任何 user 消息之前
        insert_at = idx + 1 + sum(1 for m in self.messages[idx + 1 :] if m.role == "tool")
        filler = [Message(role="tool", tool_call_id=c.id, name=c.name, content=f"[未执行：{reason}]") for c in missing]
        self.messages[insert_at:insert_at] = filler
        return len(filler)

    async def run(self, task_prompt: str, ctx: ToolContext, *, continue_with: str | None = None,
                  restore: list[Message] | None = None) -> LoopOutcome:  # fmt: skip
        """continue_with：沿用上一次 run 的消息历史，只追加一条 user 反馈（评审返工；只追加 → 缓存命中）。
        restore：断点续跑时从事件日志重放出来的历史（spec 011 §3）；配合 continue_with 追加续跑说明。"""
        try:
            return await self._run(task_prompt, ctx, continue_with=continue_with, restore=restore)
        finally:
            self.seal_dangling()

    async def _run(self, task_prompt: str, ctx: ToolContext, *, continue_with: str | None,
                   restore: list[Message] | None = None) -> LoopOutcome:  # fmt: skip
        cfg = self.config
        rec = self.emitter
        tools = self.registry.schemas()
        tool_names = [t["function"]["name"] for t in tools]
        if restore:
            cm = ContextManager(cfg, tools_chars=len(json.dumps(tools, ensure_ascii=False)), role=self.role,
                                hard_limit=self.hard_limit,
                                summarize=lambda r: self._summarize(r, ctx.task_id))  # fmt: skip
            self.context = cm
            self.messages = list(restore)
            self.seal_dangling("进程在此中断")
            if continue_with is not None:
                self.messages.append(Message(role="user", content=continue_with))
        elif continue_with is not None and self.context is not None and len(self.messages) > 1:
            cm = self.context
            self.seal_dangling("上一轮已结束")
            self.messages.append(Message(role="user", content=continue_with))
        else:
            cm = ContextManager(cfg, tools_chars=len(json.dumps(tools, ensure_ascii=False)), role=self.role,
                                hard_limit=self.hard_limit,
                                summarize=lambda r: self._summarize(r, ctx.task_id))  # fmt: skip
            self.context = cm
            self.messages = [Message(role="system", content=self.system_prompt),
                             Message(role="user", content=cm.task_message(task_prompt, intro=self.task_intro,
                                                                          trusted_tail=self.trusted_tail))]  # fmt: skip
        no_tool = 0
        warnings = 0
        wrapped = False
        history: deque[tuple[str, bool]] = deque(maxlen=cfg.window)
        fail_streak = 0
        idle_streak = 0  # 信号 3：连续没有修改、也没有新读取目标的工具调用
        seen_reads: set[str] = set()
        steps = 0
        overflow_retried = False
        forced_note = False
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
                if cm.thrashing:
                    return self._thrash(cm, steps)
            # 窗口硬上限（与工作预算无关）：估算超了就强制清理 + 压缩，仍超就体面结束，不等厂商 400
            if cm.over_window(self.messages):
                ended = await self._fit_window(cm, steps, ctx, force_compact=False)
                if ended is not None:
                    return ended
            # 最后一次允许的调用：强制提交（只对配置了 force_submit 的角色；按轮数上限判断）
            force = (self.force_submit is not None and self.force_submit in tool_names
                     and self.guard.turns + 1 >= self.guard.budget.max_turns)  # fmt: skip
            if force and not forced_note:
                forced_note = True
                note = cfg.reminder("final_submit", tool=self.force_submit or "")
                self.messages.append(Message(role="user", content=note))
            req = LLMRequest(
                role=self.role, messages=list(self.messages), tools=tools, effort=self.effort,
                temperature=None if force else self.temperature,
                thinking_override=False if force else self.thinking,
                tool_choice={"type": "function", "function": {"name": self.force_submit}} if force else "auto",
            )  # fmt: skip
            call_id = f"c{rec.next_seq}"
            writer = DeltaWriter(rec, self.role, call_id) if self.stream else None
            try:
                with streaming(writer):
                    extra: dict[str, Any] = {"executor_vendor": self.executor_vendor} if self.executor_vendor else {}
                    resp = await self.router.complete(
                        req, guard=self.guard, task_id=ctx.task_id, mode=self.mode, category=self.category, **extra
                    )
            except BudgetExceeded as e:
                resp_at_cap: LLMResponse | None = e.response
                if resp_at_cap is None:  # 调用前就超限：没有发出请求
                    return LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
                # 调用后记账才触发上限：这次调用已付费，照样写轨迹，并接住回复里的终止工具
                steps += 1
                self._record_call(req, resp_at_cap, call_id, tool_names)
                self.messages.append(resp_at_cap.message)
                done = await self._terminal_at_cap(resp_at_cap.message, ctx, steps)
                return done or LoopOutcome(status="budget_exhausted", steps=steps, reason=str(e))
            except ContextOverflow as e:
                # 估算偏低、厂商报上下文超限：强制压缩后重试一次；再超就结束
                if writer is not None:
                    writer.flush()
                if overflow_retried:
                    return LoopOutcome(status="context_overflow", steps=steps, reason=f"压缩后仍超出上下文窗口：{e}")
                overflow_retried = True
                ended = await self._fit_window(cm, steps, ctx, force_compact=True)
                if ended is not None:
                    return ended
                continue
            except TriWitnessError as e:
                return LoopOutcome(status="error", steps=steps, reason=f"{type(e).__name__}: {e}")
            finally:
                if writer is not None:
                    writer.flush()
            overflow_retried = False
            steps += 1
            cm.observe(len(req.messages), resp.usage)
            self._record_call(req, resp, call_id, tool_names)
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
            pending: list[Message] = []  # 提醒放到本轮全部 tool 消息之后（并行 tool_calls 中间插 user 消息会 HTTP 400）
            touched = False  # 本步有成功的工作区改动 → 步末存续跑进度（harness/resume.py）
            ready: dict[int, Any] = {}  # 并发跑完、待按顺序写回的只读工具结果
            for i, call in enumerate(calls):
                if i not in ready and self._parallel_ok(call):
                    j = i
                    while j < len(calls) and self._parallel_ok(calls[j]):
                        j += 1
                    if j - i >= 2:  # 连续 ≥2 个只读调用：并发执行，不越过有副作用的工具
                        outs = await asyncio.gather(*(self._timed_dispatch(c, ctx) for c in calls[i:j]),
                                                    return_exceptions=True)  # fmt: skip
                        ready.update(zip(range(i, j), outs, strict=True))
                try:
                    if i in ready:
                        got = ready.pop(i)
                        if isinstance(got, BaseException):
                            raise got
                        ctx.step_index = rec.next_seq
                        result, outcome, duration_ms = got
                    else:
                        ctx.step_index = rec.next_seq
                        result, outcome, duration_ms = await self._timed_dispatch(call, ctx)
                except NeedsHuman as e:
                    self.seal_dangling("等待人工审批，任务已暂停")
                    return LoopOutcome(status="needs_human", steps=steps, reason=str(e))
                except SandboxError as e:
                    self.seal_dangling("沙箱错误，任务已停止")
                    return LoopOutcome(status="error", steps=steps, reason=f"沙箱错误：{e}")
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
                                    display=tool_display(call.name, call.arguments, result),
                                    **(_previews(call_id, call.arguments, result.content) if self.stream else {})),
                    role=self.role,
                )  # fmt: skip
                self.messages.append(tool_msg)
                tool = self.registry.get(call.name)
                if result.ok and tool is not None and tool.side_effects == "workspace" and call.name != "run_tests":
                    touched = True
                if tool is not None and tool.terminal and result.ok:
                    data = result.data or {}
                    self.seal_dangling(f"本轮已在 {call.name} 处结束")
                    if "finish_report" in data:
                        report = FinishReport.model_validate(data.get("finish_report"))
                        return LoopOutcome(status="finished", finish=report, steps=steps)
                    return LoopOutcome(status="finished", submission=data.get("submission"), steps=steps)
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
                    pending.append(Message(role="user", content=cfg.reminder(signal.reminder,
                                                                             detail=signal.detail)))  # fmt: skip
            self.messages.extend(pending)
            after_step: Any = ctx.state.get("after_step")
            if after_step is not None:  # 每步结束 = 一个检查点（spec 011 §3.1）；有工作区改动时才存文件快照
                await after_step(steps, touched)
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
# 可并发执行的只读工具（spec 010 §7）：notes 虽不进 diff 但会写 .tw/NOTES.md，不在其中
PARALLEL_SAFE_TOOLS = frozenset({"read_file", "list_files", "grep", "repo_map", "git"})


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


def _previews(call_id: str, arguments: str, output: str | None) -> dict[str, Any]:
    """对话流工具行展开时看的内容：参数与输出各截一段（已脱敏）。"""
    return {
        "call_id": call_id,
        "args_preview": redact_text(arguments or "{}", max_len=600),
        "output_preview": redact_text(output or "", max_len=1200) or None,
    }


def model_display(msg: Message) -> str | None:
    if msg.content and msg.content.strip():
        first = msg.content.strip().splitlines()[0].replace("**", "").replace("`", "")
        return _short(first.rstrip("：:") or first)
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
