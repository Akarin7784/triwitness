"""组装 Evidence 并渲染 PR 正文（04 §4.8，W3-12）。

`build_evidence` 只做汇总：防作弊、风险分都在这里统一跑一遍，保证 PR 正文里的
等级与 evidence.json 一致。`render_pr` 是纯函数，输出稳定（快照测试）。
"""

from __future__ import annotations

from typing import Literal

from triwitness.core.models import (
    CostReport,
    Evidence,
    Finding,
    FinishReport,
    TestRun,
)
from triwitness.verify import anticheat
from triwitness.verify.claim import ClaimVerdict
from triwitness.verify.diffutil import added_lines, removed_lines, split_patch
from triwitness.verify.rerun import RerunResult
from triwitness.verify.risk import RiskInputs, RiskPolicy, RiskResult, assess

Check = Literal["pass", "fail", "skipped"]

ROLE_NAMES = {
    "planner": "Planner",
    "executor": "Executor",
    "verifier": "Verifier",
    "reviewer": "Reviewer",
    "summarizer": "Summarizer",
    "classifier": "Classifier",
}
SCOPE_NAMES = {
    "repro_base": "复现（基线）",
    "repro_patched": "复现（本 PR）",
    "related": "相关测试",
    "full": "全量",
    "hidden": "隐藏测试",
}
ANTICHEAT_LABELS = {
    "existing_test_modified": "未修改已有测试",
    "skip_or_xfail_added": "无新增 skip",
    "test_infra_modified": "未改测试基础设施",
    "test_special_casing": "无测试特判",
    "assertion_weakened": "未削弱断言",
}


def diff_stats(patch: str) -> dict[str, int]:
    files = split_patch(patch)
    return {
        "files": len(files),
        "added": sum(len(added_lines(fp)) for fp in files),
        "removed": sum(len(removed_lines(fp)) for fp in files),
    }


def build_evidence(
    *,
    task_id: str,
    finish: FinishReport,
    patch: str,
    rerun: RerunResult,
    regression: TestRun | None = None,
    root_cause: str = "",
    static_checks: dict[str, Check] | None = None,
    verdict: Literal["pass", "fail", "inconclusive"],
    verifier_model: str,
    verifier_confidence: float = 1.0,
    criteria_results: dict[str, Literal["met", "unmet", "unknown"]] | None = None,
    claim: ClaimVerdict | None = None,
    findings: list[Finding] | None = None,
    review_model: str | None = None,
    review_variant: str | None = None,
    coverage_changed: float | None = None,
    bandit_medium_high: int = 0,
    cost: CostReport,
    config_hash: str,
    base_ref: str | None = None,
    trace_url: str | None = None,
    policy: RiskPolicy | None = None,
) -> tuple[Evidence, RiskResult]:
    findings = findings or []
    ac = anticheat.check(patch)
    claim_flags = list(claim.flags) if claim else []
    # 声明审计判为证据不足时，整体结论不能高于 inconclusive
    if claim is not None and verdict == "pass" and claim.evidence_verdict != "pass":
        verdict = claim.evidence_verdict
    if ac.blocked and verdict == "pass":
        verdict = "fail"
    risk = assess(
        RiskInputs(
            patch=patch,
            anticheat=ac,
            repro_status=rerun.repro_status,
            verdict=verdict,
            verifier_confidence=verifier_confidence,
            review_major_open=sum(1 for f in findings if f.status == "open" and f.severity in ("major", "blocker")),
            coverage_changed=coverage_changed,
            bandit_medium_high=bandit_medium_high,
            clean_env=rerun.clean_env,
            claim_flags=claim_flags,
        ),
        policy,
    )
    runs = list(rerun.test_runs) + ([regression] if regression else [])
    ev = Evidence(
        task_id=task_id,
        summary=finish.summary,
        root_cause=root_cause,
        repro_status=rerun.repro_status,
        repro_path=finish.repro.path if finish.repro else None,
        base_ref=base_ref,
        clean_env=rerun.clean_env,
        unverified_reason=rerun.unverified_reason,
        test_runs=runs,
        static_checks=static_checks or {},
        anticheat_flags=ac.codes,
        claim_flags=claim_flags,
        verdict=verdict,
        verifier_model=verifier_model,
        criteria_results=criteria_results or {},
        review_model=review_model,
        review_variant=review_variant,
        findings=findings,
        risk_score=risk.score,
        risk_level=risk.level,
        risk_factors=risk.factors,
        diff_stats=diff_stats(patch),
        cost=cost,
        trace_url=trace_url,
        config_hash=config_hash,
    )
    return ev, risk


# ---------------------------------------------------------------- 渲染


def _ok(b: bool) -> str:
    return "✅" if b else "❌"


def _k(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{round(n / 1_000)}K"
    return str(n)


def _run(ev: Evidence, scope: str) -> TestRun | None:
    return next((r for r in ev.test_runs if r.scope == scope), None)


def _repro(ev: Evidence) -> list[str]:
    out = ["### 复现"]
    if ev.repro_status == "not_applicable":
        out.append("- 无复现测试（任务不适用）")
        return out
    if ev.repro_path:
        out.append(f"- 复现测试：`{ev.repro_path}`")
    base, patched = _run(ev, "repro_base"), _run(ev, "repro_patched")
    ref = f"（{ev.base_ref[:7]}）" if ev.base_ref else ""
    if base:
        out.append(f"- 基线{ref}：{'❌ 失败' if base.failed or base.errors else '⚠️ 通过（未能复现）'}")
    if patched:
        out.append(f"- 本 PR：{'✅ 通过' if not (patched.failed or patched.errors) else '❌ 仍失败'}")
    status = {
        "reproduced": "已复现并修复",
        "inconclusive": "不确定",
        "failed": "修复未通过复现测试",
    }[ev.repro_status]
    out.append(f"- 结论：{status}")
    return out


def _tests(ev: Evidence) -> list[str]:
    rows = [r for r in ev.test_runs if r.scope not in ("repro_base", "repro_patched")]
    if not rows:
        return []
    out = ["### 测试", "| 范围 | 通过 | 失败 | 跳过 | 新增失败 |", "|---|---|---|---|---|"]
    for r in rows:
        total = r.passed + r.failed + r.skipped + r.errors
        failed = r.failed + r.errors
        new = str(len(r.new_failures))
        old = failed - len(r.new_failures) - len(r.flaky)
        notes = []
        if old > 0:
            notes.append(f"{old} 个为基线已有失败")
        if r.flaky:
            notes.append(f"{len(r.flaky)} 个不稳定")
        if notes:
            new += f"（{'，'.join(notes)}）"
        out.append(f"| {SCOPE_NAMES[r.scope]}（{total}） | {r.passed} | {failed} | {r.skipped} | {new} |")
    return out


def _checks(ev: Evidence) -> list[str]:
    sym = {"pass": "✅", "fail": "❌", "skipped": "⏭️"}
    parts = [f"{name} {sym[v]}" for name, v in ev.static_checks.items()]
    flags = set(ev.anticheat_flags)
    parts += [f"{label} {_ok(code not in flags)}" for code, label in ANTICHEAT_LABELS.items()]
    out = ["### 静态检查与防作弊", " · ".join(parts)]
    extra = sorted(flags - set(ANTICHEAT_LABELS))
    if extra:
        out.append(f"其他标记：{', '.join(f'`{c}`' for c in extra)}")
    if ev.claim_flags:
        out.append(f"声明审计：{', '.join(f'`{c}`' for c in ev.claim_flags)}")
    return out


def _risk(ev: Evidence) -> list[str]:
    out = ["### 风险因子"]
    scored = [f for f in ev.risk_factors if f.points]
    floors = [f for f in ev.risk_factors if f.code.startswith("floor:")]
    if not scored and not floors:
        out.append("无")
    out += [f"- +{f.points} {f.detail}" for f in scored]
    out += [f"- 等级下限：{f.detail}" for f in floors]
    return out


def _review(ev: Evidence) -> list[str]:
    if not ev.review_model:
        return []
    who = ev.review_model + (f" · {ev.review_variant}" if ev.review_variant else "")
    note = "与执行者不同厂商" if ev.vendor_policy == "cross_vendor" else "同厂商异构评审"
    out = [f"### 评审（{who}，{note}）"]
    status = {"open": "未处理", "fixed": "已修复", "wontfix": "不修复"}
    if not ev.findings:
        out.append("- 无问题")
    for f in ev.findings:
        loc = f" `{f.file}{f':{f.line}' if f.line else ''}`" if f.file else ""
        out.append(f"- [{f.severity}][{status[f.status]}]{loc} {f.message}")
    return out


def _cost(ev: Evidence) -> list[str]:
    c = ev.cost
    out = [
        "### 成本",
        "| 角色 | 模型 | 输入（缓存命中率） | 输出 | 费用 |",
        "|---|---|---|---|---|",
    ]
    for ln in c.lines:
        u = ln.usage
        hit = f"{u.cache_hit_tokens / u.input_tokens:.0%}" if u.input_tokens else "–"
        out.append(
            f"| {ROLE_NAMES[ln.role]} | {ln.model} | {_k(u.input_tokens)}（{hit}） "
            f"| {_k(u.output_tokens)} | ¥{ln.cost_cny:.2f} |"
        )
    if c.sandbox_cost_cny:
        out.append(f"| 沙箱 | | | | ¥{c.sandbox_cost_cny:.2f} |")
    est = "，估算" if c.estimated else ""
    out.append(f"| **合计** | | | | **¥{c.total_cny:.2f}**（预算 ¥{c.budget_cny:g}{est}） |")
    return out


def render_pr(ev: Evidence, *, issue_ref: str | None = None, version: str = "") -> str:
    head = f"## TriWitness 证据包 · 风险等级 {ev.risk_level}（{ev.risk_score} 分）"
    verdict = {"pass": "通过", "fail": "未通过", "inconclusive": "证据不足"}[ev.verdict]
    target = f"，关联 {issue_ref}" if issue_ref else ""
    concl = f"**结论**（{verdict}{target}）：{ev.summary}"
    if ev.root_cause:
        concl += f"根因：{ev.root_cause}"
    blocks: list[list[str]] = [[head, concl]]
    if ev.clean_env == "unverified":
        reason = {"no_sandbox": "未启用沙箱"}.get(ev.unverified_reason or "", ev.unverified_reason or "")
        blocks[0].append(f"\n> ⚠️ 干净环境未验证（{reason}）：复跑在本机新工作区完成，不排除本机环境影响；不自动合并。")
    if ev.risk_level == "L3":
        blocks[0].append("\n> 🛑 L3：需要人工处理，不会自动提交合并。")
    for part in (_repro(ev), _tests(ev), _checks(ev), _risk(ev), _review(ev), _cost(ev)):
        if part:
            blocks.append(part)
    tail = []
    if ev.trace_url:
        tail.append(f"轨迹回放：{ev.trace_url}")
    tail.append(f"配置哈希：`{ev.config_hash}`")
    if version:
        tail.append(f"TriWitness v{version}")
    blocks.append([" · ".join(tail)])
    return "\n\n".join("\n".join(b) for b in blocks) + "\n"
