"""Verifier 角色（04 §4.5，W3-10）：确定性检查在前，模型只判读。

- `deterministic_verdict`：只看复跑 / 回归 / 防作弊 / 声明审计，不调模型（评测档位 deterministic）。
- `run_verifier`：模型判读，结构化输出降级链（spec 001 §6.2）：
  1. tool_choice=auto + `submit_verdict` 工具 → 校验参数；
  2. 参数非法 → 把校验错误回给模型，最多修复重试 2 次；
  3. 模型没调工具 → 从 content 里抽 JSON（```json 代码块或第一个 {...}）；
  4. 全部失败 → inconclusive（证据缺口写明“Verifier 输出无法解析”）。
- 跨厂商：Router 在 vendor_policy=cross_vendor 时保证 verifier 与 executor 不同厂商（否则 ConstraintViolation）；
  single_vendor（v0.1）时结果上标注 vendor_policy / variant。
- `combine`：最终结论取二者中更保守的（fail > inconclusive > pass）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from triwitness.core.models import TestRun, Vendor
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.context import wrap_untrusted
from triwitness.llm.types import LLMRequest, LLMResponse, Message
from triwitness.prompts import load_prompt
from triwitness.tools.base import _clean_schema
from triwitness.verify.anticheat import AntiCheatReport
from triwitness.verify.claim import ClaimVerdict

VerdictLabel = Literal["pass", "fail", "inconclusive"]
Path_ = Literal["tool_call", "repair", "content_json", "failed"]
MAX_REPAIRS = 2
ORDER: dict[str, int] = {"pass": 0, "inconclusive": 1, "fail": 2}


class CriterionJudgement(BaseModel):
    criterion: str
    judgement: Literal["met", "unmet", "unknown"]
    evidence: list[str] = Field(
        default_factory=list, description="引用的证据：repro_patched / full / anticheat / 文件:行"
    )


class Verdict(BaseModel):
    verdict: VerdictLabel
    criteria: list[CriterionJudgement] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""

    def criteria_results(self) -> dict[str, Literal["met", "unmet", "unknown"]]:
        return {c.criterion: c.judgement for c in self.criteria}


class VerifierInput(BaseModel):
    issue: str
    criteria: list[str] = Field(default_factory=list)
    diff: str
    repro_status: str
    test_runs: list[TestRun] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    static_checks: dict[str, str] = Field(default_factory=dict)
    anticheat_flags: list[str] = Field(default_factory=list)
    claim_flags: list[str] = Field(default_factory=list)
    executor_summary: str = ""
    executor_open_risks: list[str] = Field(default_factory=list)
    max_diff_chars: int = 20_000


class VerifierResult(BaseModel):
    verdict: Verdict
    path: Path_
    attempts: int
    model: str | None = None
    variant: str | None = None
    vendor_policy: str = "single_vendor"
    cost_cny: float = 0.0


class RouterLike(Protocol):
    async def complete(
        self,
        req: LLMRequest,
        *,
        executor_vendor: Vendor | None = ...,
        mode: Any = ...,
        guard: TaskBudgetGuard | None = ...,
        category: str = ...,
        task_id: str | None = ...,
    ) -> LLMResponse: ...


# ---------------------------------------------------------------- 确定性


def deterministic_verdict(
    repro_status: str,
    test_runs: list[TestRun],
    anticheat: AntiCheatReport | None = None,
    claim: ClaimVerdict | None = None,
) -> tuple[VerdictLabel, list[str]]:
    reasons: list[str] = []
    new = [f for r in test_runs if r.scope not in ("repro_base",) for f in r.new_failures]
    patched = [r for r in test_runs if r.scope == "repro_patched"]
    if anticheat is not None and anticheat.blocked:
        reasons.append("防作弊阻断：" + ", ".join(f.code for f in anticheat.flags if f.action == "block"))
    if repro_status == "failed" or any(r.failed or r.errors for r in patched):
        reasons.append("复现测试在修复后仍失败")
    if new:
        reasons.append(f"新增失败 {len(new)} 个：" + ", ".join(new[:3]))
    if reasons:
        return "fail", reasons
    if repro_status != "reproduced":
        reasons.append(f"复现状态 {repro_status}")
    if claim is not None and claim.verdict != "pass":
        reasons.append("声明审计：" + ", ".join(claim.flags))
    return ("inconclusive" if reasons else "pass"), reasons


def combine(*labels: VerdictLabel) -> VerdictLabel:
    return max(labels, key=lambda x: ORDER[x])


# ---------------------------------------------------------------- 模型判读

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_verdict",
        "description": "提交验证结论（只调用一次）",
        "parameters": _clean_schema(Verdict.model_json_schema()),
    },
}
_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def render_input(inp: VerifierInput) -> str:
    runs = (
        "\n".join(
            f"- {r.scope}: 通过 {r.passed} / 失败 {r.failed} / 错误 {r.errors} / 跳过 {r.skipped}"
            + (f"；新增失败 {', '.join(r.new_failures[:5])}" if r.new_failures else "")
            + (f"；flaky {', '.join(r.flaky[:5])}" if r.flaky else "")
            for r in inp.test_runs
        )
        or "- （无）"
    )
    crit = (
        "\n".join(f"{i + 1}. {c}" for i, c in enumerate(inp.criteria)) or "（Plan 未给出；以 Issue 描述的预期行为为准）"
    )
    diff = inp.diff if len(inp.diff) <= inp.max_diff_chars else inp.diff[: inp.max_diff_chars] + "\n…（diff 已截断）"
    parts = [
        "## Issue", wrap_untrusted("issue", inp.issue),
        "## 验收标准", crit,
        "## Executor 自述", wrap_untrusted("finish", inp.executor_summary + (
            "\nopen_risks: " + "；".join(inp.executor_open_risks) if inp.executor_open_risks else "")),
        "## 确定性检查",
        f"- 复现状态：{inp.repro_status}",
        runs,
        "- 说明：" + ("；".join(inp.notes) if inp.notes else "无"),
        "- 静态检查：" + (", ".join(f"{k}={v}" for k, v in inp.static_checks.items()) or "无"),
        "- 防作弊：" + (", ".join(inp.anticheat_flags) or "无标记"),
        "- 声明审计：" + (", ".join(inp.claim_flags) or "无标记"),
        "## Diff", wrap_untrusted("diff", diff),
    ]  # fmt: skip
    return "\n".join(parts)


def extract_json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    cands = [m.group(1) for m in _FENCE.finditer(text)]
    i, j = text.find("{"), text.rfind("}")
    if 0 <= i < j:
        cands.append(text[i : j + 1])
    for c in cands:
        try:
            obj = json.loads(c)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _validate(raw: Any) -> tuple[Verdict | None, str]:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return Verdict.model_validate(data), ""
    except (ValueError, ValidationError) as e:
        return None, str(e)[:800]


async def run_verifier(
    router: RouterLike,
    inp: VerifierInput,
    *,
    executor_vendor: Vendor | None = "deepseek",
    mode: Literal["background", "eval"] = "background",
    guard: TaskBudgetGuard | None = None,
    task_id: str | None = None,
    category: str = "dev",
) -> VerifierResult:
    prompt = load_prompt("verifier")
    messages = [Message(role="system", content=prompt.text), Message(role="user", content=render_input(inp))]
    meta: dict[str, Any] = {"cost_cny": 0.0}
    last_err = ""
    for attempt in range(1, MAX_REPAIRS + 2):
        req = LLMRequest(role="verifier", messages=messages, tools=[SUBMIT_TOOL], tool_choice="auto")
        resp = await router.complete(req, executor_vendor=executor_vendor, mode=mode, guard=guard,
                                     task_id=task_id, category=category)  # fmt: skip
        meta.update(model=resp.model or resp.served_model, variant=resp.variant, vendor_policy=resp.vendor_policy)
        meta["cost_cny"] += resp.cost_cny
        msg = resp.message
        calls = [c for c in msg.tool_calls or [] if c.name == "submit_verdict"]
        if calls:
            v, err = _validate(calls[0].arguments)
            if v is not None:
                return VerifierResult(verdict=v, path="tool_call" if attempt == 1 else "repair", attempts=attempt,
                                      **meta)  # fmt: skip
            last_err = err
            replies = [
                Message(role="tool", tool_call_id=c.id, name=c.name,
                        content=f"参数不合法，请修正后重新调用 submit_verdict：\n{err}" if c is calls[0] else "已忽略")
                for c in msg.tool_calls or []
            ]  # fmt: skip
            messages = [*messages, msg, *replies]
            continue
        obj = extract_json(msg.content)
        if obj is not None:
            v, err = _validate(obj)
            if v is not None:
                return VerifierResult(verdict=v, path="content_json", attempts=attempt, **meta)
            last_err = err
        else:
            last_err = "没有调用 submit_verdict，content 里也没有 JSON"
        messages = [*messages, Message(role="assistant", content=msg.content or ""),
                    Message(role="user", content=f"请调用 submit_verdict 提交结论（{last_err[:300]}）。")]  # fmt: skip
    gap = f"Verifier 输出无法解析（{MAX_REPAIRS + 1} 次）：{last_err[:200]}"
    return VerifierResult(verdict=Verdict(verdict="inconclusive", evidence_gaps=[gap], confidence=0.0),
                          path="failed", attempts=MAX_REPAIRS + 1, **meta)  # fmt: skip


__all__ = [
    "CriterionJudgement",
    "Verdict",
    "VerifierInput",
    "VerifierResult",
    "combine",
    "deterministic_verdict",
    "extract_json",
    "render_input",
    "run_verifier",
]
