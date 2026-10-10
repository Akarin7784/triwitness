"""评测接入验证器（W3-13，04 §4.5、§6.2）。

档位（RunConfig.verifier）：
- `none`：不验证（W2 基线）。
- `deterministic`：干净沙箱复跑复现 + 回归对比 + 防作弊 + 声明审计 → deterministic_verdict，不调模型。
- `model`：在 deterministic 之上加 Verifier 模型判读，结论取二者中更保守的。

复跑沙箱用 Grader 同款的任务镜像（`sandbox_factory`），与 Agent 沙箱、判分沙箱互不复用；隐藏测试从不进入。
指标（以隐藏测试 resolved 为真值）：Verifier 精确率 / 召回率、验证后的假成功数、风险等级 vs 实际通过率。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, Field

from triwitness.core.models import FinishReport, TestRun
from triwitness.sandbox.base import BackendName, Capabilities, Probe, Sandbox, SandboxSpec
from triwitness.verify import anticheat
from triwitness.verify.claim import verify_claim
from triwitness.verify.rerun import PatchApplyError, regression, rerun_repro
from triwitness.verify.risk import RiskInputs, assess
from triwitness.verify.verifier import (
    ModelPolicy,
    RouterLike,
    VerdictLabel,
    VerifierInput,
    combine,
    deterministic_verdict,
    needs_model,
    run_verifier,
    thin_evidence,
)

VerifierMode = Literal["none", "deterministic", "model"]
DOCKER_CAPS = Capabilities(isolation="container", network_enforced=True, clean_env=True, host_fs_visible=False,
                           allows_full_access=False)  # fmt: skip


class FactoryBackend:
    """把“按任务新建沙箱”的工厂包装成 SandboxBackend（rerun 每次 create 都拿到全新容器）。"""

    name: BackendName = "docker"

    def __init__(self, factory: Callable[[], Awaitable[Sandbox]], capabilities: Capabilities = DOCKER_CAPS) -> None:
        self.factory = factory
        self.capabilities = capabilities

    async def probe(self) -> Probe:  # pragma: no cover - 不需要
        return Probe(available=True)

    async def create(self, spec: SandboxSpec) -> Sandbox:
        return await self.factory()


class ModelJudgment(BaseModel):
    """model 档的一次独立判读（W3-14：每个补丁判多次测稳定性）。"""

    verdict: VerdictLabel
    confidence: float | None = None
    path: str | None = None
    cost_cny: float = 0.0
    gaps: list[str] = Field(default_factory=list)


def majority(labels: list[VerdictLabel]) -> VerdictLabel:
    """多数票；并列时取更保守的（fail > inconclusive > pass）。"""
    top = max(labels.count(lb) for lb in labels)
    tied: list[VerdictLabel] = [lb for lb in labels if labels.count(lb) == top]
    return combine(*tied)


class VerificationOutcome(BaseModel):
    mode: VerifierMode
    verdict: VerdictLabel
    deterministic: VerdictLabel
    model_verdict: VerdictLabel | None = None
    model_confidence: float | None = None
    verifier_path: str | None = None  # tool_call / repair / content_json / failed
    repro_status: str
    clean_env: str
    risk_score: int
    risk_level: str
    anticheat_flags: list[str] = Field(default_factory=list)
    claim_flags: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    test_runs: list[TestRun] = Field(default_factory=list)
    cost_cny: float = 0.0
    model_judgments: list[ModelJudgment] = Field(default_factory=list)
    thin_evidence: list[str] = Field(default_factory=list)  # 确定性 pass 的证据薄在哪（决定 model 档是否调用）
    model_skipped: str | None = None  # model 档没调用模型的原因


async def verify_attempt(
    *,
    issue: str,
    diff: str,
    finish: FinishReport | None,
    backend: FactoryBackend,
    mode: VerifierMode,
    test_cmd: str | None = None,
    run_regression: bool = True,
    router: RouterLike | None = None,
    task_id: str | None = None,
    timeout_s: int = 600,
    model_repeats: int = 1,
    model_policy: ModelPolicy = "thin_pass",
) -> VerificationOutcome:
    assert mode != "none"
    spec = SandboxSpec()
    ac = anticheat.check(diff)
    claim = verify_claim(issue=issue, claim=finish, patch=diff) if finish is not None else None
    reasons: list[str] = []
    try:
        rr = await rerun_repro(backend, spec, diff, finish.repro if finish else None, timeout_s=timeout_s)
        repro_status, clean_env, runs = rr.repro_status, rr.clean_env, list(rr.test_runs)
        reasons += rr.notes
    except PatchApplyError as e:
        repro_status, clean_env, runs = "inconclusive", "verified", []
        reasons.append(str(e)[:300])
    if run_regression and test_cmd and diff.strip():
        try:
            run, res = await regression(backend, spec, diff, test_cmd, timeout_s=timeout_s)
            runs.append(run)
            reasons += res.notes
        except PatchApplyError as e:
            reasons.append(str(e)[:300])
    det, why = deterministic_verdict(repro_status, runs, ac, claim)
    reasons = why + reasons
    thin = thin_evidence(runs, ac, claim, finish.open_risks if finish else None)
    base = VerificationOutcome(mode="deterministic", verdict=det, deterministic=det, repro_status=repro_status,
                               clean_env=clean_env, risk_score=0, risk_level="L0", anticheat_flags=ac.codes,
                               claim_flags=claim.flags if claim else [], reasons=reasons, test_runs=runs,
                               thin_evidence=thin if det == "pass" else [])  # fmt: skip
    if mode == "model":
        if router is None:
            raise ValueError("verifier=model 需要 router")
        return await judge_with_model(base, issue=issue, diff=diff, finish=finish, router=router,
                                      repeats=model_repeats, task_id=task_id, policy=model_policy)  # fmt: skip
    return _finalize(base, diff=diff, ac=ac, claim_flags=base.claim_flags, final=det, conf=None)


def _finalize(
    base: VerificationOutcome, *, diff: str, ac: anticheat.AntiCheatReport, claim_flags: list[str],
    final: VerdictLabel, conf: float | None, **update: object,
) -> VerificationOutcome:  # fmt: skip
    risk = assess(RiskInputs(patch=diff, anticheat=ac, repro_status=base.repro_status, verdict=final,  # type: ignore[arg-type]
                             verifier_confidence=conf if conf is not None else 1.0, clean_env=base.clean_env,  # type: ignore[arg-type]
                             claim_flags=claim_flags))  # fmt: skip
    return base.model_copy(update={"verdict": final, "risk_score": risk.score, "risk_level": risk.level,
                                   "model_confidence": conf, **update})  # fmt: skip


async def judge_with_model(
    base: VerificationOutcome,
    *,
    issue: str,
    diff: str,
    finish: FinishReport | None,
    router: RouterLike,
    repeats: int = 1,
    task_id: str | None = None,
    policy: ModelPolicy = "thin_pass",
) -> VerificationOutcome:
    """在已有的确定性证据（base）上做 model 档判读：独立判 `repeats` 次，多数票（并列取保守），
    最终结论 = combine(确定性结论, 模型多数票)。W3-14 reverify 用它复用 deterministic 档的复跑结果，不再重跑沙箱。

    policy=thin_pass（默认，W3-14 结论）：只在确定性 pass 且证据薄时调用模型；否则直接用确定性结论（¥0）。"""
    if repeats < 1:
        raise ValueError("repeats 至少为 1")
    ac = anticheat.check(diff)
    claim = verify_claim(issue=issue, claim=finish, patch=diff) if finish is not None else None
    thin = thin_evidence(base.test_runs, ac, claim, finish.open_risks if finish else None)
    base = base.model_copy(update={"thin_evidence": thin if base.deterministic == "pass" else []})
    if not needs_model(base.deterministic, thin, policy):
        why = "确定性结论不是 pass（模型只会更保守）" if base.deterministic != "pass" else "确定性 pass 且证据充分"
        return _finalize(base, diff=diff, ac=ac, claim_flags=base.claim_flags, final=base.deterministic, conf=None,
                         mode="model", model_skipped=why)  # fmt: skip
    inp = VerifierInput(
        issue=issue, diff=diff, repro_status=base.repro_status, test_runs=base.test_runs, notes=base.reasons,
        anticheat_flags=ac.codes, claim_flags=base.claim_flags,
        executor_summary=finish.summary if finish else "", executor_open_risks=finish.open_risks if finish else [],
    )  # fmt: skip
    js: list[ModelJudgment] = []
    for _ in range(repeats):
        vr = await run_verifier(router, inp, mode="eval", task_id=task_id)
        js.append(ModelJudgment(verdict=vr.verdict.verdict, confidence=vr.verdict.confidence, path=vr.path,
                                cost_cny=vr.cost_cny, gaps=vr.verdict.evidence_gaps[:3]))  # fmt: skip
    mv = majority([j.verdict for j in js])
    agree = [j for j in js if j.verdict == mv]
    conf = round(sum(j.confidence or 0.0 for j in agree) / len(agree), 4)
    final = combine(base.deterministic, mv)
    reasons = list(base.reasons) + [f"Verifier 缺口：{g}" for g in agree[0].gaps]
    return _finalize(base, diff=diff, ac=ac, claim_flags=base.claim_flags, final=final, conf=conf, mode="model",
                     model_verdict=mv, verifier_path=agree[0].path, reasons=reasons, model_judgments=js,
                     cost_cny=round(sum(j.cost_cny for j in js), 6))  # fmt: skip


async def verify_run(
    *,
    issue: str,
    diff: str,
    finish: FinishReport | None,
    new_sandbox: Callable[[], Awaitable[Sandbox]],
    mode: VerifierMode,
    test_cmd: str | None,
    run_regression: bool = True,
    router: RouterLike | None = None,
    task_id: str | None = None,
    model_repeats: int = 1,
    model_policy: ModelPolicy = "thin_pass",
) -> VerificationOutcome:
    """评测一次 attempt 的验证（`tw eval run` 与 `tw eval reverify` 共用）。没有改动直接判 fail。"""
    if not diff.strip():
        return VerificationOutcome(
            mode=mode, verdict="fail", deterministic="fail", repro_status="not_applicable",
            clean_env="verified", risk_score=0, risk_level="L0", reasons=["没有改动"],
        )  # fmt: skip
    return await verify_attempt(
        issue=issue, diff=diff, finish=finish, backend=FactoryBackend(new_sandbox), mode=mode, test_cmd=test_cmd,
        run_regression=run_regression, router=router, task_id=task_id, model_repeats=model_repeats,
        model_policy=model_policy,
    )  # fmt: skip


# ---------------------------------------------------------------- 指标


class VerifierMetrics(BaseModel):
    n: int  # 有验证结果、且不是 infra_error 的 attempt
    verified_pass: int
    true_pass: int  # verifier pass 且隐藏测试通过
    resolved: int
    precision: float | None  # verifier 说 pass 的里面，真正解决的比例
    recall: float | None  # 真正解决的里面，verifier 说 pass 的比例
    false_success_claimed: int  # Agent 声称修好但隐藏测试不过
    false_success_verified: int  # verifier pass 但隐藏测试不过（验证后的假成功）
    by_risk: dict[str, tuple[int, float]]  # 等级 → (数量, 实际通过率)


def verifier_metrics(rows: list[tuple[bool, bool, str | None, str | None]]) -> VerifierMetrics | None:
    """rows：(resolved, agent_claimed_success, verifier_verdict, risk_level)；verifier_verdict 为 None 的跳过。"""
    rs = [r for r in rows if r[2] is not None]
    if not rs:
        return None
    vp = [r for r in rs if r[2] == "pass"]
    tp = sum(r[0] for r in vp)
    resolved = sum(r[0] for r in rs)
    by: dict[str, tuple[int, float]] = {}
    for lv in sorted({r[3] for r in rs if r[3]}):
        xs = [r for r in rs if r[3] == lv]
        by[lv] = (len(xs), round(sum(r[0] for r in xs) / len(xs), 4))
    return VerifierMetrics(
        n=len(rs), verified_pass=len(vp), true_pass=tp, resolved=resolved,
        precision=round(tp / len(vp), 4) if vp else None,
        recall=round(tp / resolved, 4) if resolved else None,
        false_success_claimed=sum(r[1] and not r[0] for r in rs),
        false_success_verified=len(vp) - tp, by_risk=by,
    )  # fmt: skip


__all__ = [
    "FactoryBackend",
    "ModelJudgment",
    "VerificationOutcome",
    "VerifierMetrics",
    "VerifierMode",
    "judge_with_model",
    "majority",
    "verifier_metrics",
    "verify_attempt",
    "verify_run",
]
