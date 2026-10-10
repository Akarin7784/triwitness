"""单角色任务驱动（W1-24 接入轨迹；W1-32 `tw run` 与 W1-30 评测共用）。

产出完整的 tw-events/1 事件序列：task_started → state_change → checkpoint → (model_call / tool_call …)
→ checkpoint → state_change → task_finished（含 FinishReport 与 CostReport），与桌面端 golden fixture 同形。
传入 `verify`（VerifyOptions）时，Executor 声明完成后进入 VERIFYING：干净沙箱复跑、回归、静态检查、
（可选）Verifier 模型，产出 Evidence（artifacts/evidence.json）与 PR 正文（artifacts/pr.md），并发 verification 事件；
验证 fail 且还有返工次数 → 回到 EXECUTING（带验证反馈），否则任务记为 failed。不传则与 W2 行为一致。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Literal

from triwitness.core.errors import SandboxError
from triwitness.core.events import (
    CheckpointPayload,
    ErrorPayload,
    StateChangePayload,
    TaskFinishedPayload,
    TaskStartedPayload,
    VerificationPayload,
)
from triwitness.core.models import Budget, CostReport, FinishReport, TaskState
from triwitness.cost.report import CostLedger
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import AgentLoop, LoopOutcome, RouterLike, build_system_prompt
from triwitness.llm.pricing import pricing_version
from triwitness.prompts import load_prompt
from triwitness.sandbox.base import Sandbox
from triwitness.telemetry.otel import bridge_from_env
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolContext, ToolRegistry
from triwitness.verify.pipeline import EmittingRouter, PipelineResult, VerifyOptions, verify_task

EXECUTOR_PROMPT = load_prompt("executor").text  # 版本化提示：src/triwitness/prompts/executor.md

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
    repro_status: str | None = None  # repro-first：reproduced / not_applicable / missing；未启用为 None
    verification: PipelineResult | None = None  # 传了 verify 且进入了 VERIFYING 才有
    verify_rounds: int = 0


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
    category: str = "dev",
    verify: VerifyOptions | None = None,
) -> TaskResult:
    rec = recorder
    cfg = config or HarnessConfig.load()
    ledger = CostLedger(task_id=rec.task_id, budget_cny=budget.max_cost_cny, pricing_version=pricing_version())
    rec.subscribe(ledger.observe)
    bridge = bridge_from_env()  # 没配置 OTLP 端点时为 None（spec 005 AC5）
    if bridge is not None:
        rec.subscribe(bridge.observe)
    head = f"Issue #{issue_number} · {issue_title}" if issue_number is not None else issue_title
    rec.emit(TaskStartedPayload(issue_title=issue_title, repo=repo, config_hash=config_hash,
                                issue_number=issue_number, mode=mode, display=head, harness=cfg.name,
                                harness_hash=cfg.config_hash(), prompt_versions=cfg.prompt_versions()))  # fmt: skip
    st = _States(rec)
    st.go(TaskState.PREPARING, "准备沙箱")
    base_ref = await _checkpoint(rec, sandbox, "start")
    repro_first = "submit_repro" in registry.names
    if repro_first:
        st.go(TaskState.REPRODUCING, "复现")
    else:
        st.go(TaskState.EXECUTING, "修复")
    role_prompt = load_prompt(cfg.prompts.get("executor", "executor")).text
    # token 分配：AGENTS.md 摘要只能用 prefix 预算里扣掉提示与工具 schema 后的余量
    room = (
        cfg.context.chars(cfg.context.allocation.prefix)
        - len(role_prompt)
        - len(json.dumps(registry.schemas(), ensure_ascii=False))
    )
    loop = AgentLoop(router, registry, budget=budget, emitter=rec, mode=mode, config=cfg, category=category,
                     system_prompt=build_system_prompt(role_prompt, agents_md=agents_md, tool_names=registry.names,
                                                       agents_md_max_chars=min(4000, max(0, room))))  # fmt: skip
    ctx = ToolContext(sandbox=sandbox, task_id=rec.task_id, run_id=rec.run_id, test_command=test_command,
                      tw_dir=tw_dir)  # fmt: skip
    if repro_first:
        ctx.state["repro_first"] = True
        ctx.state["on_repro_accepted"] = lambda check: st.go(
            TaskState.EXECUTING, "修复" if check.get("status") == "reproduced" else "修复（无法复现，已降级）"
        )
    outcome = await loop.run(task_prompt, ctx)
    check = ctx.state.get("repro_check")
    repro_status = check.get("status") if check else ("missing" if repro_first else None)
    status, final, label = _classify(outcome)
    verification: PipelineResult | None = None
    rounds = 0
    while verify is not None and status == "done" and outcome.finish is not None:
        patch = await _diff(sandbox, base_ref)
        if not patch.strip():
            break
        rounds += 1
        st.go(TaskState.VERIFYING, "验证" if rounds == 1 else f"验证（第 {rounds} 轮）")
        opts = verify
        if opts.router is not None:
            opts = replace(opts, router=EmittingRouter(opts.router, lambda p: rec.emit(p, role="verifier")))
        verification = await verify_task(
            task_id=rec.task_id, issue=task_prompt, finish=outcome.finish, patch=patch, opts=opts,
            cost=ledger.report, config_hash=config_hash, workspace=sandbox, test_command=test_command,
            base_ref=base_ref, run_mode=mode, category=category,
        )  # fmt: skip
        ev = verification.evidence
        ref = rec.artifact(f"evidence-{rounds}.json", ev.model_dump(mode="json"))
        rec.artifact(f"pr-{rounds}.md", verification.pr_body)
        rec.emit(VerificationPayload(
            verdict=ev.verdict, evidence_ref=ref, tests_passed=verification.tests_passed, risk_level=ev.risk_level,
            clean_env=ev.clean_env, unverified_reason=verification.unverified_reason,
            display=f"验证{_VERDICT[ev.verdict]} · 风险 {ev.risk_level}",
        ), role="verifier")  # fmt: skip
        if ev.verdict != "fail":
            break
        if rounds > verify.max_retries:
            status, final, label = "failed", TaskState.FAILED, "验证未通过"
            break
        st.go(TaskState.EXECUTING, "根据验证结果返工")
        outcome = await loop.run(f"{task_prompt}\n\n<verification_feedback>\n{verification.feedback()}\n"
                                 "</verification_feedback>", ctx)  # fmt: skip
        status, final, label = _classify(outcome)
    if outcome.status in ("budget_exhausted", "error", "stuck"):
        etype = {"budget_exhausted": "BudgetExceeded", "stuck": "Stuck", "error": "Error"}[outcome.status]
        rec.emit(ErrorPayload(type=etype, message=outcome.reason or etype, display=outcome.reason or label))
    await _checkpoint(rec, sandbox, "final")
    diff = await _diff(sandbox, base_ref)
    if status == "done":
        st.go(TaskState.PACKAGING, "整理结果")
    st.go(final, label)
    cost = ledger.report()
    shown = f"{label} · ¥{cost.total_cny:.3f}"
    if cost.cache_hit_rate:
        shown += f" · 命中 {cost.cache_hit_rate:.0%}"
    rec.emit(TaskFinishedPayload(status=status, finish_report=outcome.finish, cost_report=cost, display=shown))
    return TaskResult(status=status, outcome=outcome, diff=diff, cost=cost, finish=outcome.finish,
                      repro_status=repro_status, verification=verification, verify_rounds=rounds)  # fmt: skip


_VERDICT = {"pass": "通过", "fail": "未通过", "inconclusive": "证据不足"}


def _classify(outcome: LoopOutcome) -> tuple[FinishStatus, TaskState, str]:
    status, final, label = _STATUS[outcome.status]
    if outcome.status == "finished" and outcome.finish is not None and not outcome.finish.tests_passed:
        return "failed", TaskState.FAILED, "失败"
    return status, final, label


async def _diff(sandbox: Sandbox, base_ref: str | None) -> str:
    if base_ref is None:
        return ""
    try:
        return await sandbox.diff("base")
    except SandboxError:
        return ""


async def _checkpoint(rec: TrajectoryRecorder, sandbox: Sandbox, label: str) -> str | None:
    try:
        ref = await sandbox.snapshot(label)
    except (SandboxError, NotImplementedError):
        return None
    rec.emit(CheckpointPayload(label=label, ref=ref, display=f"快照 {label}"))
    return ref


__all__ = ["EXECUTOR_PROMPT", "TaskResult", "run_task"]
