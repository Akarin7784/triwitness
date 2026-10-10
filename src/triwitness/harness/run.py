"""单角色任务驱动（W1-24 接入轨迹；W1-32 `tw run` 与 W1-30 评测共用）。

产出完整的 tw-events/1 事件序列：task_started → state_change → checkpoint → (model_call / tool_call …)
→ checkpoint → state_change → task_finished（含 FinishReport 与 CostReport），与桌面端 golden fixture 同形。
三角色（planner / verifier / reviewer）在 W3 接入，这里只跑 executor。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from triwitness.core.errors import SandboxError
from triwitness.core.events import (
    CheckpointPayload,
    ErrorPayload,
    StateChangePayload,
    TaskFinishedPayload,
    TaskStartedPayload,
)
from triwitness.core.models import Budget, CostReport, FinishReport, TaskState
from triwitness.cost.report import cost_report_from_events
from triwitness.harness.loop import AgentLoop, HarnessConfig, LoopOutcome, RouterLike, build_system_prompt
from triwitness.llm.pricing import pricing_version
from triwitness.sandbox.base import Sandbox
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolContext, ToolRegistry

EXECUTOR_PROMPT = (
    "你是 TriWitness 的执行者。在仓库里定位并修复问题：先读相关代码，必要时写复现测试，"
    "修改后用 run_tests 验证，最后调用 finish 如实报告（测试没过就写 tests_passed=false）。"
)

FinishStatus = Literal["done", "failed", "budget_exceeded", "stuck", "needs_human", "cancelled"]
_STATUS: dict[str, tuple[FinishStatus, TaskState, str]] = {
    "finished": ("done", TaskState.DONE, "完成"),
    "budget_exhausted": ("budget_exceeded", TaskState.BUDGET_EXCEEDED, "预算耗尽"),
    "stuck": ("stuck", TaskState.FAILED, "卡住"),
    "needs_human": ("needs_human", TaskState.NEEDS_HUMAN, "等待人工"),
    "error": ("failed", TaskState.FAILED, "失败"),
}


@dataclass
class TaskResult:
    status: FinishStatus
    outcome: LoopOutcome
    diff: str
    cost: CostReport
    finish: FinishReport | None


class _States:
    def __init__(self, rec: TrajectoryRecorder) -> None:
        self.rec = rec
        self.state = TaskState.RECEIVED

    def go(self, to: TaskState, display: str) -> None:
        self.rec.emit(StateChangePayload.model_validate({"from": self.state, "to": to, "display": display}))
        self.state = to


async def run_task(
    *,
    recorder: TrajectoryRecorder,
    router: RouterLike,
    registry: ToolRegistry,
    sandbox: Sandbox,
    issue_title: str,
    task_prompt: str,
    repo: str,
    budget: Budget,
    config_hash: str,
    issue_number: int | None = None,
    test_command: str | None = None,
    mode: Literal["background", "eval"] = "background",
    agents_md: str | None = None,
    config: HarnessConfig | None = None,
    tw_dir: str = "/workspace/.tw",
) -> TaskResult:
    rec = recorder
    head = f"Issue #{issue_number} · {issue_title}" if issue_number is not None else issue_title
    rec.emit(TaskStartedPayload(issue_title=issue_title, repo=repo, config_hash=config_hash,
                                issue_number=issue_number, mode=mode, display=head))  # fmt: skip
    st = _States(rec)
    st.go(TaskState.PREPARING, "准备沙箱")
    base_ref = await _checkpoint(rec, sandbox, "start")
    st.go(TaskState.EXECUTING, "修复")
    loop = AgentLoop(router, registry, budget=budget, emitter=rec, mode=mode, config=config,
                     system_prompt=build_system_prompt(EXECUTOR_PROMPT, agents_md=agents_md,
                                                       tool_names=registry.names))  # fmt: skip
    ctx = ToolContext(sandbox=sandbox, task_id=rec.task_id, run_id=rec.run_id, test_command=test_command,
                      tw_dir=tw_dir)  # fmt: skip
    outcome = await loop.run(task_prompt, ctx)
    status, final, label = _STATUS[outcome.status]
    if outcome.status == "finished" and outcome.finish is not None and not outcome.finish.tests_passed:
        status, final, label = "failed", TaskState.FAILED, "失败"
    if outcome.status in ("budget_exhausted", "error", "stuck"):
        etype = {"budget_exhausted": "BudgetExceeded", "stuck": "Stuck", "error": "Error"}[outcome.status]
        rec.emit(ErrorPayload(type=etype, message=outcome.reason or etype, display=outcome.reason or label))
    await _checkpoint(rec, sandbox, "final")
    try:
        diff = await sandbox.diff("base") if base_ref is not None else ""
    except SandboxError:
        diff = ""
    if status == "done":
        st.go(TaskState.PACKAGING, "整理结果")
    st.go(final, label)
    cost = cost_report_from_events(rec.events, task_id=rec.task_id, budget_cny=budget.max_cost_cny,
                                   pricing_version=pricing_version())  # fmt: skip
    shown = f"{label} · ¥{cost.total_cny:.3f}"
    if cost.cache_hit_rate:
        shown += f" · 命中 {cost.cache_hit_rate:.0%}"
    rec.emit(TaskFinishedPayload(status=status, finish_report=outcome.finish, cost_report=cost, display=shown))
    return TaskResult(status=status, outcome=outcome, diff=diff, cost=cost, finish=outcome.finish)


async def _checkpoint(rec: TrajectoryRecorder, sandbox: Sandbox, label: str) -> str | None:
    try:
        ref = await sandbox.snapshot(label)
    except (SandboxError, NotImplementedError):
        return None
    rec.emit(CheckpointPayload(label=label, ref=ref, display=f"快照 {label}"))
    return ref


__all__ = ["EXECUTOR_PROMPT", "TaskResult", "run_task"]
