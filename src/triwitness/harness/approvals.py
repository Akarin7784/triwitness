"""审批事件接线（spec 006 §7、§11，W1-42）：工具执行前过权限引擎。

- allow → 执行；tool_call 事件带 permission / permission_rule；
- deny → 不执行，拒绝原因作为工具结果回给模型；非交互（eval / CI）的 ask 由引擎改判为 deny，
  并写 `approval_resolved(by="policy")`（AC6）；
- ask（交互）→ 写 `approval_requested`，等待决定（`ApprovalBroker` / `resolve_approval`），
  写 `approval_resolved(by="user")`；
  “本次任务内允许”加会话规则，“总是允许”写 permissions.local.yaml；拒绝附言回传模型；
  没有审批通道时抛 NeedsHuman（任务进入 needs_human）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from triwitness.core.errors import TriWitnessError
from triwitness.core.events import ApprovalRequestedPayload, ApprovalResolvedPayload
from triwitness.core.ids import new_hitl_id
from triwitness.harness.events import EventEmitter
from triwitness.llm.types import ToolCallSpec
from triwitness.permissions.config import save_local_rules
from triwitness.permissions.engine import Action, PermissionEngine, Verdict
from triwitness.tools.base import GateOutcome, Tool, ToolContext, ToolResult
from triwitness.tools.shell import RunTests

READ_TOOLS = {"read_file": "path", "list_files": "path", "grep": "path"}
EDIT_TOOLS = {"write_file": "path", "edit_file": "path"}


class NeedsHuman(TriWitnessError):
    def __init__(self, request_id: str, reason: str) -> None:
        super().__init__(f"等待人工审批：{reason}")
        self.request_id = request_id


@dataclass
class ApprovalDecision:
    decision: Literal["allow", "deny"]
    scope: Literal["once", "session", "always"] = "once"
    comment: str | None = None


Approver = Callable[[ApprovalRequestedPayload], Awaitable[ApprovalDecision | None]]


class ApprovalBroker:
    """`tw serve` 的 POST /v1/approvals/{id} 调 resolve_approval；AgentLoop 侧 await wait()。"""

    def __init__(self) -> None:
        self.pending: dict[str, asyncio.Future[ApprovalDecision]] = {}

    async def wait(self, req: ApprovalRequestedPayload) -> ApprovalDecision | None:
        fut: asyncio.Future[ApprovalDecision] = asyncio.get_running_loop().create_future()
        self.pending[req.request_id] = fut
        try:
            return await fut  # 已采纳默认：后台任务审批不超时
        finally:
            self.pending.pop(req.request_id, None)

    def resolve_approval(
        self,
        request_id: str,
        decision: Literal["allow", "deny"],
        scope: Literal["once", "session", "always"] = "once",
        comment: str | None = None,
    ) -> bool:
        fut = self.pending.get(request_id)
        if fut is None or fut.done():
            return False
        fut.set_result(ApprovalDecision(decision=decision, scope=scope, comment=comment))
        return True


def action_for(tool: Tool, params: BaseModel, ctx: ToolContext, *, shell_category: str = "Bash") -> Action | None:
    p: Any = params
    if tool.name in READ_TOOLS:
        return Action("Read", getattr(p, READ_TOOLS[tool.name]) or ".", tool=tool.name)
    if tool.name in EDIT_TOOLS:
        return Action("Edit", getattr(p, EDIT_TOOLS[tool.name]), tool=tool.name)
    if tool.name == "git":  # 只读：diff / status / log / show
        return Action("Read", p.path or ".", tool="git")
    if tool.name == "repo_map":  # 读整个仓库的 .py 签名
        return Action("Read", ".", tool="repo_map")
    if tool.name == "bash":
        return Action("Bash", p.command, tool="bash")
    if tool.name == "powershell":
        return Action("PowerShell", p.command, tool="powershell")
    if tool.name == "run_tests":
        cmd = RunTests.command(ctx, p)
        return Action(shell_category, cmd, tool="run_tests") if cmd else None  # type: ignore[arg-type]
    if tool.name == "submit_repro":  # 跑模型给的复现命令：与 run_tests 同类审批
        cmd = getattr(p, "cmd", None) if not getattr(p, "not_applicable", False) else None
        return Action(shell_category, cmd, tool="submit_repro") if cmd else None  # type: ignore[arg-type]
    return None  # finish、notes（只写 .tw/，不进 diff）等


_SCOPE = {"once": "一次", "session": "本次任务", "always": "总是"}


def _resolved_display(d: ApprovalDecision) -> str:
    if d.decision == "allow":
        return f"已允许（{_SCOPE[d.scope]}）"
    return "已拒绝" + (f"：{d.comment}" if d.comment else "")


class PermissionGate:
    def __init__(
        self,
        engine: PermissionEngine,
        emitter: EventEmitter,
        *,
        approver: Approver | None = None,
        repo_for_always: Path | None = None,
        shell_category: str = "Bash",
    ) -> None:
        self.engine = engine
        self.emitter = emitter
        self.approver = approver
        self.repo_for_always = repo_for_always
        self.shell_category = shell_category

    def _denied(self, v: Verdict, extra: str = "") -> GateOutcome:
        msg = f"权限拒绝：{v.reason}" + (f"\n{extra}" if extra else "")
        return GateOutcome(allowed=False, result=ToolResult(ok=False, content=msg, error_code="permission_denied"),
                           permission="deny", rule=v.rule_raw)  # fmt: skip

    async def __call__(self, tool: Tool, params: BaseModel, ctx: ToolContext, call: ToolCallSpec) -> GateOutcome:
        action = action_for(tool, params, ctx, shell_category=self.shell_category)
        if action is None:
            return GateOutcome(allowed=True)
        v = self.engine.check(action)
        if v.decision == "allow":
            return GateOutcome(allowed=True, permission="allow", rule=v.rule_raw)
        backend: Any = self.engine.policy.backend
        if v.decision == "deny":
            if v.by_policy:
                self.emitter.emit(ApprovalResolvedPayload(request_id=new_hitl_id(), decision="deny", by="policy",
                                                          comment=v.reason))  # fmt: skip
            return self._denied(v)
        # ask（交互）
        suggested = v.suggested_rules or self.engine.suggest_rules(action, v)
        req = ApprovalRequestedPayload(
            request_id=new_hitl_id(),
            tool=action.category,
            action=action.value[:2000],
            reason=v.reason,
            rule=v.rule_raw,
            rule_source=v.rule.source if v.rule else None,
            risk="L2" if action.category in ("Bash", "PowerShell", "Fetch") else "L1",
            suggested_rule=suggested[0] if suggested else None,
            backend=backend,
            timeout_s=self.engine.policy.approval_timeout_s,
            display=f"待批 · {action.tool or action.category} · {action.value[:160]}",
        )
        self.emitter.emit(req)
        decision = await self.approver(req) if self.approver is not None else None
        if decision is None:
            raise NeedsHuman(req.request_id, v.reason)
        saved: str | None = None
        if decision.decision == "allow" and decision.scope in ("session", "always"):
            rules = self.engine.remember(action, v, "session")
            if decision.scope == "always" and self.repo_for_always is not None and rules:
                save_local_rules(self.repo_for_always, rules)
                saved = "; ".join(rules)
        self.emitter.emit(ApprovalResolvedPayload(request_id=req.request_id, decision=decision.decision,
                                                  scope=decision.scope, by="user", saved_rule=saved,
                                                  comment=decision.comment,
                                                  display=_resolved_display(decision)))  # fmt: skip
        if decision.decision == "deny":
            return self._denied(v, f"用户拒绝{'：' + decision.comment if decision.comment else ''}")
        return GateOutcome(allowed=True, permission="ask", rule=v.rule_raw)
