"""InProcessOrchestrator（spec 010 §8，W4-07）：显式状态机驱动的完整任务流程。

RECEIVED → PREPARING →（planner）PLANNING →（需确认）AWAIT_PLAN_APPROVAL →（repro-first）REPRODUCING
→ EXECUTING →（verify）VERIFYING ⇄ EXECUTING →（reviewer）REVIEWING ⇄ EXECUTING → PACKAGING → DONE

- 状态只由本编排器经 `TaskStateMachine.go()` 迁移（非法迁移抛 IllegalTransition），每次迁移写 state_change 事件；
  角色（Planner / Executor / Verifier / Reviewer）只返回结构化结果，彼此不共享消息历史。
- 角色开关来自 harness 配置 `orchestration`；全关时与 W3 的 run_task 行为、事件序列完全一致（基线可复现）。
- 评审返工 = CC 报告的“有上限的不许停”：blocker 且未到 max_rounds → 在同一 Executor 上下文里续写评审反馈。
- 所有模型调用都经同一个 Router → LLMClient → 全局账本；本任务成本由事件流上的 CostLedger 汇总。
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import posixpath
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from triwitness.core.errors import SandboxError
from triwitness.core.events import (
    ApprovalRequestedPayload,
    ApprovalResolvedPayload,
    CheckpointPayload,
    EnvironmentPreparedPayload,
    ErrorPayload,
    ReviewPayload,
    StateChangePayload,
    TaskFinishedPayload,
    TaskStartedPayload,
    VerificationPayload,
)
from triwitness.core.ids import new_hitl_id
from triwitness.core.models import Budget, CostReport, FinishReport, Plan, TaskState
from triwitness.core.state_machine import TaskStateMachine, Transition, eval_auto_decision, risk_at_least
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.cost.report import CostLedger
from triwitness.harness.approvals import Approver
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import AgentLoop, LoopOutcome, RouterLike, build_system_prompt
from triwitness.harness.prepare import PrepareOptions, PrepareResult, prepare_env
from triwitness.harness.resume import ResumeState, apply_resume, resume_note, save_progress
from triwitness.llm.pricing import pricing_version
from triwitness.prompts import load_prompt
from triwitness.roles.planner import PlannerResult, criteria_texts, render_plan, run_planner
from triwitness.roles.reviewer import ReviewInput, ReviewResult, run_review
from triwitness.sandbox.base import Sandbox
from triwitness.telemetry.otel import bridge_from_env
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolContext, ToolRegistry
from triwitness.verify.pipeline import EmittingRouter, PipelineResult, VerifyOptions, verify_task
from triwitness.verify.risk import load_policy as load_risk_policy

S = TaskState
FinishStatus = Literal["done", "failed", "budget_exceeded", "stuck", "needs_human", "cancelled"]
_STATUS: dict[str, tuple[FinishStatus, TaskState, str]] = {
    "finished": ("done", S.DONE, "完成"),
    "budget_exhausted": ("budget_exceeded", S.BUDGET_EXCEEDED, "触及安全上限"),
    "stuck": ("stuck", S.FAILED, "卡住"),
    "needs_human": ("needs_human", S.NEEDS_HUMAN, "等待人工"),
    "error": ("failed", S.FAILED, "失败"),
    "cancelled": ("cancelled", S.CANCELLED, "已取消"),
    # 1M 档：上下文抖动 / 超窗口——事件层仍报 stuck（tw-events/1 不变），原因写在 error 事件里
    "context_thrash": ("stuck", S.FAILED, "上下文反复压缩无效"),
    "context_overflow": ("stuck", S.FAILED, "上下文超出窗口"),
}
_VERDICT = {"pass": "通过", "fail": "未通过", "inconclusive": "证据不足"}
PLAN_FILE = "plan.json"


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
    prepared: PrepareResult | None = None
    plan: Plan | None = None  # Planner 启用且产出了计划
    review: ReviewResult | None = None  # 最后一轮评审
    review_rounds: int = 0  # 评审返工次数
    unresolved_blockers: int = 0  # 返工到上限后仍未解决的阻断问题
    states: list[str] | None = None  # 本次迁移序列（审计 / 测试）


def classify(outcome: LoopOutcome) -> tuple[FinishStatus, TaskState, str]:
    status, final, label = _STATUS[outcome.status]
    if outcome.status == "finished" and outcome.finish is not None and not outcome.finish.tests_passed:
        return "failed", S.FAILED, "失败"
    return status, final, label


def clip(text: str, n: int = 200) -> str:
    """事件 display 上限 200 字（tw-events/1）；完整原因在 message 里。"""
    return text if len(text) <= n else text[: n - 1] + "…"


class InProcessOrchestrator:
    def __init__(
        self,
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
        prepare: PrepareOptions | None = None,
        stream: bool = False,
        resume: ResumeState | None = None,
        progress_dir: Path | None = None,
        approver: Approver | None = None,
    ) -> None:
        self.rec = recorder
        self.router = router
        self.registry = registry
        self.sandbox = sandbox
        self.issue_title = issue_title
        self.task_prompt = task_prompt
        self.repo = repo
        self.budget = budget
        self.config_hash = config_hash
        self.issue_number = issue_number
        self.test_command = test_command
        self.mode: Literal["background", "eval"] = mode
        self.agents_md = agents_md
        self.cfg = config or HarnessConfig.default()
        self.tw_dir = tw_dir
        self.category = category
        self.verify = verify
        self.prepare = prepare
        self.stream = stream
        self.resume = resume
        self.progress_dir = progress_dir
        self.approver = approver
        self.ledger = CostLedger(task_id=recorder.task_id, pricing_version=pricing_version())
        self.sm = TaskStateMachine(on_transition=self._emit_transition)

    # ---------------------------------------------------------------- 状态
    def _emit_transition(self, t: Transition) -> None:
        self.rec.emit(StateChangePayload.model_validate({"from": t.src, "to": t.dst, "display": t.display}))

    def go(self, to: TaskState, display: str) -> None:
        self.sm.go(to, display)

    # ---------------------------------------------------------------- 入口
    async def run(self) -> TaskResult:
        rec, cfg = self.rec, self.cfg
        for ev in list(rec.events):  # 对话轮已记下的调用（同一个 run）也算进本任务成本：结论卡 = 轮次合计 = 账本
            self.ledger.observe(ev)
        rec.subscribe(self.ledger.observe)
        bridge = bridge_from_env()  # 没配置 OTLP 端点时为 None（spec 005 AC5）
        if bridge is not None:
            rec.subscribe(bridge.observe)
        head = f"Issue #{self.issue_number} · {self.issue_title}" if self.issue_number is not None else self.issue_title
        rec.emit(TaskStartedPayload(issue_title=self.issue_title, repo=self.repo, config_hash=self.config_hash,
                                    issue_number=self.issue_number, mode=self.mode, display=head, harness=cfg.name,
                                    harness_hash=cfg.config_hash(), prompt_versions=cfg.prompt_versions()))  # fmt: skip
        try:
            return await self._body()
        except asyncio.CancelledError:
            # 用户取消（桌面端 / tw run --jsonl 的 cancel）：收尾写 cancelled，正常返回，让调用方保留分支与产物
            cur = asyncio.current_task()
            if cur is not None:
                cur.uncancel()
            return self._cancelled()

    async def _body(self) -> TaskResult:
        rec, cfg, sandbox = self.rec, self.cfg, self.sandbox
        resume, registry = self.resume, self.registry
        test_command = self.test_command
        self.go(S.PREPARING, "准备沙箱")
        prepared: PrepareResult | None = None
        if self.prepare is not None:
            prepared = await self._prepare(test_command)
            test_command = test_command or prepared.test_command
            if not prepared.ok:
                return self._env_failed(prepared)
        base_ref = await self._checkpoint("start")
        repro_first = "submit_repro" in registry.names
        prompt = self.task_prompt
        repro_first_done: dict[str, Any] | None = None
        if resume is not None:  # 断点续跑：start 快照是原始代码（diff / 复验基线），再写回上次的进度
            applied, held = await apply_resume(sandbox, resume, repro_first=repro_first)
            await self._checkpoint("resumed")
            prompt = f"{self.task_prompt}\n\n{resume_note(resume, applied, held)}"
            if resume.repro_check is not None and repro_first:
                repro_first_done = dict(resume.repro_check)
        ctx = ToolContext(sandbox=sandbox, task_id=rec.task_id, run_id=rec.run_id, test_command=test_command,
                          tw_dir=self.tw_dir)  # fmt: skip

        # ---- PLANNING（可选）
        plan: Plan | None = None
        plan_note = ""
        if cfg.orchestration.planner.enabled:
            plan = self._saved_plan() if resume is not None else None
            if plan is not None and self.progress_dir is not None:  # 续跑：沿用原计划，并留一份给下一次续跑
                (self.progress_dir / PLAN_FILE).write_text(plan.model_dump_json(indent=2), encoding="utf-8")
                plan_note = " · 沿用原计划"
            if plan is None:
                self.go(S.PLANNING, "规划")
                pr = await self._plan(ctx, test_command, prepared)
                plan = pr.plan
                if plan is not None:
                    rec.artifact(PLAN_FILE, plan.model_dump(mode="json"))
                    if self.progress_dir is not None:
                        (self.progress_dir / PLAN_FILE).write_text(plan.model_dump_json(indent=2), encoding="utf-8")
                    reasons = self._plan_approval_reasons(plan)
                    if reasons:
                        self.go(S.AWAIT_PLAN_APPROVAL, clip("等待确认计划 · " + "；".join(reasons)))
                        decision = await self._approve_plan(plan, reasons)
                        if decision != "approve":
                            return self._stop_before_work(decision, plan)
                plan_note = (f" · 计划 {plan.estimated_risk}，{len(plan.acceptance_criteria)} 条验收标准"
                             if plan is not None else " · 无计划（Planner 未提交）")  # fmt: skip
            if plan is not None:
                prompt = f'{prompt}\n\n<plan source="planner">\n{render_plan(plan)}\n</plan>'

        # ---- REPRODUCING / EXECUTING
        if repro_first and repro_first_done is None:
            self.go(S.REPRODUCING, "复现" + plan_note)
        else:
            self.go(S.EXECUTING, "修复" + plan_note)
        role_prompt = load_prompt(cfg.prompts.get("executor", "executor")).text
        # token 分配：AGENTS.md 摘要只能用 prefix 预算里扣掉提示与工具 schema 后的余量
        room = (cfg.context.chars(cfg.context.allocation.prefix) - len(role_prompt)
                - len(json.dumps(registry.schemas(), ensure_ascii=False)))  # fmt: skip
        loop = AgentLoop(self.router, registry, budget=self.budget, emitter=rec, mode=self.mode, config=cfg,
                         category=self.category, stream=self.stream,
                         system_prompt=build_system_prompt(role_prompt, agents_md=self.agents_md,
                                                           tool_names=registry.names,
                                                           agents_md_max_chars=max(0, room)))  # fmt: skip
        if repro_first:
            ctx.state["repro_first"] = True
            ctx.state["on_repro_accepted"] = self._on_repro_accepted
            if repro_first_done is not None:
                ctx.state["repro_check"] = repro_first_done
        if self.progress_dir is not None:
            pdir = self.progress_dir

            async def after_step(steps: int) -> None:
                await save_progress(pdir, sandbox, issue=self.task_prompt, state=ctx.state, tw_dir=self.tw_dir,
                                    steps=steps + (resume.steps if resume else 0))  # fmt: skip

            ctx.state["after_step"] = after_step
        outcome = await loop.run(prompt, ctx)
        check = ctx.state.get("repro_check")
        repro_status = check.get("status") if check else ("missing" if repro_first else None)
        status, final, label = classify(outcome)

        # ---- VERIFYING ⇄ EXECUTING，REVIEWING ⇄ EXECUTING
        verification: PipelineResult | None = None
        review: ReviewResult | None = None
        rounds = review_rounds = unresolved = 0
        rc = cfg.orchestration.reviewer
        while status == "done" and outcome.finish is not None:
            patch = await self._diff(base_ref)
            if not patch.strip():
                break
            if self.verify is not None:
                rounds += 1
                self.go(S.VERIFYING, "验证" if rounds == 1 else f"验证（第 {rounds} 轮）")
                verification = await self._verify(outcome.finish, patch, test_command, base_ref, prepared, plan, rounds)
                ev = verification.evidence
                if ev.verdict == "fail":
                    if rounds > self.verify.max_retries:
                        status, final, label = "failed", S.FAILED, "验证未通过"
                        break
                    self.go(S.EXECUTING, "根据验证结果返工")
                    outcome = await loop.run(f"{prompt}\n\n<verification_feedback>\n{verification.feedback()}\n"
                                             "</verification_feedback>", ctx)  # fmt: skip
                    status, final, label = classify(outcome)
                    continue
            if not rc.enabled:
                break
            self.go(S.REVIEWING, "评审" if review_rounds == 0 else f"评审（第 {review_rounds + 1} 轮）")
            review = await self._review(ctx, patch, outcome.finish, plan, verification, review_rounds)
            blockers = sum(1 for f in review.findings if f.severity == "blocker")
            if review.blocking and review_rounds < rc.max_rounds:
                review_rounds += 1
                self.go(S.EXECUTING, f"根据评审返工（{blockers} 个阻断问题）")
                outcome = await loop.run(prompt, ctx, continue_with=review.feedback())
                status, final, label = classify(outcome)
                continue
            unresolved = blockers if review.blocking else 0
            if verification is not None:
                verification = verification.with_review(
                    findings=review.findings, review_model=review.model, review_variant=review.variant,
                    vendor_policy=getattr(self.router, "vendor_policy", "single_vendor"),
                    unresolved_blockers=unresolved, cost=self.ledger.report(),
                )  # fmt: skip
                self.rec.artifact(f"evidence-{rounds}-reviewed.json", verification.evidence.model_dump(mode="json"))
                self.rec.artifact(f"pr-{rounds}-reviewed.md", verification.pr_body)
            if unresolved:
                label = f"完成（评审仍有 {unresolved} 个阻断问题）"
            break

        # ---- 收尾
        etypes = {"budget_exhausted": "BudgetExceeded", "stuck": "Stuck", "error": "Error",
                  "context_thrash": "ContextThrash", "context_overflow": "ContextOverflow"}  # fmt: skip
        if outcome.status in etypes:
            etype = etypes[outcome.status]
            rec.emit(ErrorPayload(type=etype, message=outcome.reason or etype, display=clip(outcome.reason or label)))
        await self._checkpoint("final")
        if self.progress_dir is not None and status != "done":  # 停下 / 失败：留一份最新进度给“继续”
            await save_progress(self.progress_dir, sandbox, issue=self.task_prompt, state=ctx.state, tw_dir=self.tw_dir,
                                steps=outcome.steps + (resume.steps if resume else 0))  # fmt: skip
        diff = await self._diff(base_ref)
        if status == "done":
            self.go(S.PACKAGING, "整理结果")
        self.go(final, label)
        cost = self.ledger.report()
        shown = f"{label} · ¥{cost.total_cny:.3f}"
        if cost.cache_hit_rate:
            shown += f" · 命中 {cost.cache_hit_rate:.0%}"
        rec.emit(TaskFinishedPayload(status=status, finish_report=outcome.finish, cost_report=cost, display=shown))
        return TaskResult(status=status, outcome=outcome, diff=diff, cost=cost, finish=outcome.finish,
                          repro_status=repro_status, verification=verification, verify_rounds=rounds,
                          prepared=prepared, plan=plan, review=review, review_rounds=review_rounds,
                          unresolved_blockers=unresolved, states=self._states())  # fmt: skip

    # ---------------------------------------------------------------- 角色
    def _on_repro_accepted(self, check: dict[str, Any]) -> None:
        if self.sm.state == S.REPRODUCING:  # 返工轮里第一次提交复现不迁移（已在 EXECUTING）
            ok = check.get("status") == "reproduced"
            self.go(S.EXECUTING, "修复" if ok else "修复（无法复现，已降级）")

    def _role_ctx(self, ctx: ToolContext) -> ToolContext:
        """角色用独立的工具上下文（不共享 Executor 的 after_step / repro 状态）。"""
        return replace(ctx, state={})

    async def _plan(self, ctx: ToolContext, test_command: str | None, prepared: PrepareResult | None) -> PlannerResult:
        base = prepared.baseline if prepared else None
        return await run_planner(router=self.router, rec=self.rec, ctx=self._role_ctx(ctx), issue=self.task_prompt,
                                 cfg=self.cfg, budget=self.budget, mode=self.mode, category=self.category,
                                 agents_md=self.agents_md, gate=self.registry.gate, test_command=test_command,
                                 baseline_failures=len(base.failures) if base else None)  # fmt: skip

    async def _review(self, ctx: ToolContext, patch: str, finish: FinishReport, plan: Plan | None,
                      verification: PipelineResult | None, round_: int) -> ReviewResult:  # fmt: skip
        summary = ""
        if verification is not None:
            ev = verification.evidence
            runs = "；".join(f"{r.scope} 通过 {r.passed} / 失败 {r.failed}" for r in ev.test_runs)
            summary = (f"结论 {ev.verdict}；复现 {ev.repro_status}；干净环境 {ev.clean_env}；风险 {ev.risk_level}"
                       + (f"；{runs}" if runs else "")
                       + ("；说明：" + "；".join(verification.reasons[:5])
                          if verification.reasons else ""))  # fmt: skip
        inp = ReviewInput(issue=self.task_prompt, diff=patch, finish=finish, plan=plan, verification=summary,
                          feedback_round=round_)  # fmt: skip
        res = await run_review(inp, router=self.router, rec=self.rec, ctx=self._role_ctx(ctx), cfg=self.cfg,
                               budget=self.budget, mode=self.mode, category=self.category,
                               gate=self.registry.gate)  # fmt: skip
        blockers = sum(1 for f in res.findings if f.severity == "blocker")
        shown = (("有阻断问题 " + str(blockers) if res.blocking else "通过")
                 + f" · {len(res.findings)} 条发现" + (" · 共识" if res.consensus else "")
                 if res.concluded else "评审无结论（未提交）")  # fmt: skip
        self.rec.emit(ReviewPayload.model_validate({
            "model": res.model, "variant": res.variant,
            "vendor_policy": getattr(self.router, "vendor_policy", "single_vendor"),
            "findings": [f.model_dump(mode="json") for f in res.findings], "display": f"评审{shown}",
            "blocking": res.blocking, "round": round_ + 1, "consensus": res.consensus,
            "paths": {r.variant: r.path[:120] for r in res.reviews},
        }), role="reviewer")  # fmt: skip
        return res

    async def _verify(self, finish: FinishReport, patch: str, test_command: str | None, base_ref: str | None,
                      prepared: PrepareResult | None, plan: Plan | None, rounds: int) -> PipelineResult:  # fmt: skip
        assert self.verify is not None
        opts = self.verify
        if opts.router is not None:
            opts = replace(opts, router=EmittingRouter(opts.router, lambda p: self.rec.emit(p, role="verifier")))
        res = await verify_task(
            task_id=self.rec.task_id, issue=self.task_prompt, finish=finish, patch=patch, opts=opts,
            cost=self.ledger.report, config_hash=self.config_hash, workspace=self.sandbox, test_command=test_command,
            base_ref=base_ref, run_mode=self.mode, category=self.category,
            baseline=prepared.baseline if prepared else None, criteria=criteria_texts(plan),
            root_cause=plan.root_cause_hypothesis if plan else "",
        )  # fmt: skip
        ev = res.evidence
        ref = self.rec.artifact(f"evidence-{rounds}.json", ev.model_dump(mode="json"))
        self.rec.artifact(f"pr-{rounds}.md", res.pr_body)
        self.rec.emit(VerificationPayload(
            verdict=ev.verdict, evidence_ref=ref, tests_passed=res.tests_passed, risk_level=ev.risk_level,
            clean_env=ev.clean_env, unverified_reason=res.unverified_reason,
            display=f"验证{_VERDICT[ev.verdict]} · 风险 {ev.risk_level}",
        ), role="verifier")  # fmt: skip
        return res

    # ---------------------------------------------------------------- 计划确认（04 §3.7；spec 010 §11 Q1）
    def _plan_approval_reasons(self, plan: Plan) -> list[str]:
        pa = self.cfg.orchestration.plan_approval
        out: list[str] = []
        if risk_at_least(plan.estimated_risk, pa.min_risk):
            out.append(f"风险预估 {plan.estimated_risk} ≥ {pa.min_risk}")
        if plan.needs_approval:
            out.append("Planner 要求先确认")
        if pa.on_open_questions and plan.open_questions:
            out.append(f"有 {len(plan.open_questions)} 个待确认的问题")
        if pa.on_sensitive_files:
            pol = load_risk_policy()
            hits = [f for f in plan.affected_files
                    if any(fnmatch.fnmatch(f, g) or fnmatch.fnmatch(posixpath.basename(f), g) for g in pol.build_files)
                    or any(s in f.lower() for s in pol.sensitive_paths)]  # fmt: skip
            if hits:
                out.append("涉及构建 / 敏感文件：" + "、".join(hits[:3]))
        return out

    async def _approve_plan(self, plan: Plan, reasons: list[str]) -> Literal["approve", "reject", "needs_human"]:
        pa = self.cfg.orchestration.plan_approval
        rid = new_hitl_id()
        why = "；".join(reasons)
        if self.mode == "eval":  # 评测禁止人工介入：固定策略，写审计
            d = eval_auto_decision(plan.estimated_risk, reject_from=pa.eval_reject_from)
            self.rec.emit(ApprovalResolvedPayload(request_id=rid, decision="allow" if d == "approve" else "deny",
                                                  by="policy", comment=f"评测自动策略（{why}）",
                                                  display=clip(f"计划{'自动批准' if d == 'approve' else '自动拒绝'} · "
                                                               f"风险 {plan.estimated_risk}")))  # fmt: skip
            return d
        req = ApprovalRequestedPayload(request_id=rid, tool="Plan", action=render_plan(plan)[:2000], reason=why,
                                       risk=plan.estimated_risk, options=["allow_once", "deny"],
                                       display=clip(f"待批 · 计划 · 风险 {plan.estimated_risk} · {why}"))  # fmt: skip
        self.rec.emit(req)
        if self.approver is None:
            if pa.unattended == "approve":
                self.rec.emit(ApprovalResolvedPayload(request_id=rid, decision="allow", by="policy",
                                                      comment="无审批通道：配置 unattended=approve",
                                                      display="计划自动批准（无人值守）"))  # fmt: skip
                return "approve"
            return "needs_human"
        decision = await self.approver(req)
        if decision is None:
            return "needs_human"
        self.rec.emit(ApprovalResolvedPayload(
            request_id=rid, decision=decision.decision, by="user", comment=decision.comment,
            display="计划已批准" if decision.decision == "allow" else clip("计划被拒绝" + (
                f"：{decision.comment}" if decision.comment else "")),
        ))  # fmt: skip
        return "approve" if decision.decision == "allow" else "reject"

    def _stop_before_work(self, decision: str, plan: Plan) -> TaskResult:
        if decision == "reject":
            status, final, label = "cancelled", S.CANCELLED, "计划被拒绝"
        else:
            status, final, label = "needs_human", S.NEEDS_HUMAN, "等待确认计划"
        self.go(final, label)  # type: ignore[arg-type]
        cost = self.ledger.report()
        self.rec.emit(TaskFinishedPayload(status=status, cost_report=cost,  # type: ignore[arg-type]
                                          display=f"{label} · ¥{cost.total_cny:.3f}"))  # fmt: skip
        outcome = LoopOutcome(status="needs_human" if status == "needs_human" else "cancelled", steps=0, reason=label)
        return TaskResult(status=status, outcome=outcome, diff="", cost=cost, finish=None, plan=plan,  # type: ignore[arg-type]
                          states=self._states())  # fmt: skip

    def _saved_plan(self) -> Plan | None:
        """续跑：沿用被续跑那次 run 的计划（runs/<from_run>/plan.json），不重新规划、不重复审批。"""
        if self.progress_dir is None or self.resume is None:
            return None
        p = self.progress_dir.parent / self.resume.from_run / PLAN_FILE
        try:
            return Plan.model_validate_json(p.read_text(encoding="utf-8")) if p.is_file() else None
        except (OSError, ValueError):
            return None

    # ---------------------------------------------------------------- 杂项
    def _states(self) -> list[str]:
        return [S.RECEIVED.value, *(t.dst.value for t in self.sm.history)]

    async def _prepare(self, test_command: str | None) -> PrepareResult:
        assert self.prepare is not None
        opts = self.prepare
        if opts.router is not None:  # 模型推断 setup 的调用也记入账本 / 轨迹
            emitting = EmittingRouter(opts.router, lambda p: self.rec.emit(p, role="classifier"))
            opts = opts.model_copy(update={"router": emitting})
        res = await prepare_env(self.sandbox, opts=opts, test_command=test_command)
        fails = sorted(res.baseline.failures) if res.baseline else []
        ref = None
        if res.baseline:
            ref = self.rec.artifact("baseline.json", {"failures": fails, "duration_s": res.baseline.duration_s})
        shown = f"环境就绪（{res.setup_source_label()}）" if res.ok else "环境构建失败"
        if res.baseline:
            shown += f" · 基线失败 {len(fails)}"
        self.rec.emit(EnvironmentPreparedPayload(
            setup_source=res.source, install_commands=res.setup.install, installed=bool(res.installed), ok=res.ok,
            test_command=res.test_command, baseline_failures=fails[:200], baseline_failure_count=len(fails),
            baseline_duration_s=res.baseline.duration_s if res.baseline else None, baseline_ref=ref,
            notes=res.notes[:10], display=shown,
        ))  # fmt: skip
        return res

    def _env_failed(self, prepared: PrepareResult) -> TaskResult:
        reason = prepared.notes[-1] if prepared.notes else "环境构建失败"
        self.rec.emit(ErrorPayload(type="EnvironmentSetupFailed", message=reason, display="环境构建失败"))
        self.go(S.NEEDS_HUMAN, "环境构建失败")
        cost = self.ledger.report()
        self.rec.emit(TaskFinishedPayload(status="needs_human", cost_report=cost, display="环境构建失败 · 等待人工"))
        outcome = LoopOutcome(status="needs_human", steps=0, reason=reason)
        return TaskResult(status="needs_human", outcome=outcome, diff="", cost=cost, finish=None, prepared=prepared,
                          states=self._states())  # fmt: skip

    def _cancelled(self) -> TaskResult:
        if not self.sm.terminal:
            self.go(S.CANCELLED, "已取消")
        cost = self.ledger.report()
        self.rec.emit(
            TaskFinishedPayload(status="cancelled", cost_report=cost, display=f"已取消 · ¥{cost.total_cny:.3f}")
        )
        outcome = LoopOutcome(status="cancelled", steps=0, reason="用户取消")
        return TaskResult(status="cancelled", outcome=outcome, diff="", cost=cost, finish=None, states=self._states())

    async def _diff(self, base_ref: str | None) -> str:
        if base_ref is None:
            return ""
        try:
            return await self.sandbox.diff("base")
        except SandboxError:
            return ""

    async def _checkpoint(self, label: str) -> str | None:
        try:
            ref = await self.sandbox.snapshot(label)
        except (SandboxError, NotImplementedError):
            return None
        self.rec.emit(CheckpointPayload(label=label, ref=ref, display=f"快照 {label}"))
        return ref


__all__ = ["FinishStatus", "InProcessOrchestrator", "TaskBudgetGuard", "TaskResult", "classify"]
