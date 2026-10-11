"""VERIFYING 阶段：把验证流水线接进 run_task 主流程（04 §4，W3-12 后续）。

顺序：防作弊 + 声明审计 → 干净沙箱复跑复现（基线必须失败、修复后必须通过）→ 回归（基线 vs 修复后，
PREPARING 记录的基线失败集合可直接传入）→ 静态检查（改动文件，只算新增问题）→ 确定性判定 →（可选）
Verifier 模型判读，取更保守者 → build_evidence + render_pr。

复跑沙箱一律从 `VerifyOptions.backend` 新建，与 Executor 沙箱互不复用。none 后端用 `EphemeralBackend`
包一层：每个复跑沙箱独立 worktree，用完即丢（不留 tw/<run_id> 分支）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Literal

from triwitness.core.events import ModelCallPayload, billing
from triwitness.core.ids import new_run_id
from triwitness.core.models import CostReport, Evidence, Finding, FinishReport, RiskFactor, TestRun, Vendor
from triwitness.llm.types import LLMRequest, LLMResponse
from triwitness.sandbox.base import BackendName, Capabilities, Probe, Sandbox, SandboxBackend, SandboxSpec
from triwitness.verify import anticheat
from triwitness.verify.claim import verify_claim
from triwitness.verify.evidence import build_evidence, render_pr
from triwitness.verify.rerun import Baseline, PatchApplyError, RerunResult, regression, rerun_repro
from triwitness.verify.risk import RiskResult
from triwitness.verify.static_checks import StaticReport, run_static_checks
from triwitness.verify.verifier import (
    ModelPolicy,
    RouterLike,
    VerdictLabel,
    VerifierInput,
    VerifierResult,
    combine,
    deterministic_verdict,
    needs_model,
    run_verifier,
    thin_evidence,
)

UNVERIFIED_REASONS = ("no_sandbox", "backend_unavailable", "skipped")


@dataclass
class VerifyOptions:
    backend: SandboxBackend  # 复跑用的“新建沙箱”来源
    spec: SandboxSpec = field(default_factory=SandboxSpec)
    mode: Literal["deterministic", "model"] = "deterministic"
    router: RouterLike | None = None  # mode=model 时必填
    # W3-14 结论：model 只在“确定性 pass 但证据薄”时调用（判 1 次）；always = 每次都判
    model_policy: ModelPolicy = "thin_pass"
    executor_vendor: Vendor | None = "deepseek"
    regression: bool = True
    static: bool = True
    static_tools: tuple[str, ...] = ("ruff", "pyright", "bandit")
    python: str = "python"
    timeout_s: int = 600
    max_retries: int = 0  # 验证 fail 后回到 EXECUTING 返工的次数（architecture：VERIFYING → EXECUTING）


@dataclass
class PipelineResult:
    evidence: Evidence
    risk: RiskResult
    pr_body: str
    deterministic: VerdictLabel
    reasons: list[str]
    static: StaticReport | None = None
    model: VerifierResult | None = None
    rebuild: Callable[..., tuple[Evidence, RiskResult]] | None = None  # 带评审结果重建证据包（spec 010 §6.3）

    def with_review(
        self,
        *,
        findings: list[Finding],
        review_model: str,
        review_variant: str,
        vendor_policy: Literal["single_vendor", "cross_vendor"] = "single_vendor",
        unresolved_blockers: int = 0,
        cost: CostReport | None = None,
    ) -> PipelineResult:
        """把评审结论并进证据包：major / blocker 计入风险（review_major_open）；返工到上限仍有 blocker → 下限 L2。"""
        if self.rebuild is None:
            return self
        kw: dict[str, Any] = {"findings": findings, "review_model": review_model, "review_variant": review_variant}
        if cost is not None:
            kw["cost"] = cost
        ev, risk = self.rebuild(**kw)
        upd: dict[str, Any] = {"vendor_policy": vendor_policy}
        if unresolved_blockers and ev.risk_level in ("L0", "L1"):
            upd["risk_level"] = "L2"
            upd["risk_factors"] = [*ev.risk_factors, RiskFactor(
                code="floor:review_blocker_unresolved", points=0,
                detail=f"评审返工到上限后仍有 {unresolved_blockers} 个阻断问题未解决")]  # fmt: skip
        ev = ev.model_copy(update=upd)
        return PipelineResult(evidence=ev, risk=risk, pr_body=render_pr(ev), deterministic=self.deterministic,
                              reasons=self.reasons, static=self.static, model=self.model,
                              rebuild=self.rebuild)  # fmt: skip

    @property
    def tests_passed(self) -> bool:
        runs = [r for r in self.evidence.test_runs if r.scope != "repro_base"]
        return all(not r.new_failures for r in runs) and all(
            not (r.failed or r.errors) for r in runs if r.scope == "repro_patched"
        )

    @property
    def unverified_reason(self) -> Literal["no_sandbox", "backend_unavailable", "skipped"] | None:
        r = self.evidence.unverified_reason
        return r if r in UNVERIFIED_REASONS else None  # type: ignore[return-value]

    def feedback(self) -> str:
        """验证 fail 时回给 Executor 的返工说明（不含隐藏信息，只有本次验证自己的证据）。"""
        lines = [f"独立验证结论：{self.evidence.verdict}（风险 {self.evidence.risk_level}）。原因："]
        lines += [f"- {r}" for r in self.reasons[:8]]
        for run in self.evidence.test_runs:
            if run.new_failures:
                lines.append(f"- {run.scope} 新增失败：{', '.join(run.new_failures[:5])}")
        if self.evidence.anticheat_flags:
            lines.append(f"- 防作弊标记：{', '.join(self.evidence.anticheat_flags)}")
        lines.append("请在现有改动基础上修正，然后重新调用 finish。")
        return "\n".join(lines)


class _Ephemeral:
    """代理沙箱：close 时连 worktree / 分支一起丢掉（none 后端的复跑沙箱不该留下分支）。"""

    def __init__(self, inner: Sandbox) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def close(self) -> None:
        finish = getattr(self._inner, "finish", None)
        if finish is not None:
            await finish("discard")
        else:
            await self._inner.close()


class EphemeralBackend:
    """每次 create 换一个新 run_id（none 后端 worktree 不能重名），close 即丢弃。"""

    def __init__(self, inner: SandboxBackend) -> None:
        self._inner = inner
        self.name: BackendName = inner.name
        self.capabilities: Capabilities = inner.capabilities

    async def probe(self) -> Probe:  # pragma: no cover - 透传
        return await self._inner.probe()

    async def create(self, spec: SandboxSpec) -> Sandbox:
        sb = await self._inner.create(spec.model_copy(update={"run_id": f"verify-{new_run_id()}"}))
        return _Ephemeral(sb)  # type: ignore[return-value]


class EmittingRouter:
    """给 Verifier 的模型调用补发 model_call 事件（role=verifier），让成本账本和轨迹都能看到。"""

    def __init__(self, inner: RouterLike, emit: Callable[[ModelCallPayload], object]) -> None:
        self.inner = inner
        self.emit = emit

    async def complete(self, req: LLMRequest, **kw: Any) -> LLMResponse:
        resp = await self.inner.complete(req, **kw)
        self.emit(ModelCallPayload(
            model=(resp.model or resp.served_model or "?").rsplit("/", 1)[-1], served_model=resp.served_model,
            thinking=req.thinking, usage=resp.usage, **billing(resp), peak=resp.peak,
            latency_ms=resp.latency_ms, finish_reason=resp.finish_reason, display="Verifier 判读",
        ))  # fmt: skip
        return resp


async def verify_task(
    *,
    task_id: str,
    issue: str,
    finish: FinishReport,
    patch: str,
    opts: VerifyOptions,
    cost: Callable[[], CostReport],
    config_hash: str,
    workspace: Sandbox | None = None,
    test_command: str | None = None,
    baseline: Baseline | None = None,
    base_ref: str | None = None,
    run_mode: Literal["background", "eval"] = "background",
    category: str = "dev",
    criteria: list[str] | None = None,
    root_cause: str = "",
) -> PipelineResult:
    spec, t = opts.spec, opts.timeout_s
    reasons: list[str] = []
    ac = anticheat.check(patch)
    claim = verify_claim(issue=issue, claim=finish, patch=patch)
    try:
        rr = await rerun_repro(opts.backend, spec, patch, finish.repro, timeout_s=t)
    except PatchApplyError as e:
        clean = "unverified" if not opts.backend.capabilities.clean_env else "verified"
        rr = RerunResult(repro_status="inconclusive", clean_env=clean, notes=[str(e)[:300]])
    reasons += rr.notes
    runs: list[TestRun] = list(rr.test_runs)
    reg: TestRun | None = None
    if opts.regression and test_command:
        try:
            reg, res = await regression(opts.backend, spec, patch, test_command, timeout_s=t, baseline=baseline)
            reasons += res.notes
        except PatchApplyError as e:
            reasons.append(str(e)[:300])
    static: StaticReport | None = None
    if opts.static and workspace is not None:
        base_sb = await opts.backend.create(spec)
        try:
            static = await run_static_checks(
                workspace, patch, base=base_sb, python=opts.python, tools=opts.static_tools, timeout_s=t
            )
        finally:
            await base_sb.close()
    det, why = deterministic_verdict(rr.repro_status, runs + ([reg] if reg else []), ac, claim)
    reasons = why + reasons
    final: VerdictLabel = det
    vr: VerifierResult | None = None
    thin = thin_evidence(runs + ([reg] if reg else []), ac, claim, finish.open_risks)
    if opts.mode == "model" and not needs_model(det, thin, opts.model_policy):
        reasons.append("Verifier 模型未调用：" + ("确定性 pass 且证据充分" if det == "pass" else "确定性结论不是 pass"))
    elif opts.mode == "model":
        if opts.router is None:
            raise ValueError("verifier=model 需要 router")
        vr = await run_verifier(opts.router, VerifierInput(
            issue=issue, diff=patch, repro_status=rr.repro_status, test_runs=runs + ([reg] if reg else []),
            notes=reasons, anticheat_flags=ac.codes, claim_flags=claim.flags, executor_summary=finish.summary,
            executor_open_risks=finish.open_risks, criteria=criteria or [],
        ), executor_vendor=opts.executor_vendor, mode=run_mode, task_id=task_id, category=category)  # fmt: skip
        final = combine(det, vr.verdict.verdict)
        reasons += [f"Verifier 缺口：{g}" for g in vr.verdict.evidence_gaps[:3]]
    rebuild = partial(
        build_evidence,
        task_id=task_id, finish=finish, patch=patch, rerun=rr, regression=reg, static=static, verdict=final,
        verifier_model=(vr.model if vr else None) or "deterministic",
        verifier_confidence=vr.verdict.confidence if vr else 1.0,
        criteria_results=vr.verdict.criteria_results() if vr else None, claim=claim, cost=cost(),
        config_hash=config_hash, base_ref=base_ref, root_cause=root_cause,
    )  # fmt: skip
    ev, risk = rebuild()
    return PipelineResult(evidence=ev, risk=risk, pr_body=render_pr(ev), deterministic=det, reasons=reasons,
                          static=static, model=vr, rebuild=rebuild)  # fmt: skip


__all__ = ["EmittingRouter", "EphemeralBackend", "PipelineResult", "VerifyOptions", "verify_task"]
