"""角色输出契约（spec 010 §5，04 §3.3 原则 3，W4-04）。

- `PlanSubmission` / `Review`：Planner、Reviewer 通过终止工具 `submit_plan` / `submit_review` 提交。
- `SubmitTool`：在 AgentLoop 里用的终止工具；参数非法走普通工具错误（带字段名），成功时结果放进 `data.submission`。
- `structured_call`：单次调用的降级链（auto + 校验 + 最多 2 次修复 + content 抽 JSON），Verifier 复用。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, Field, ValidationError

from triwitness.core.models import AcceptanceCriterion, Finding, Plan, PlanStep, RiskLevel, Vendor
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.llm.types import LLMRequest, LLMResponse, Message
from triwitness.tools.base import SideEffects, ToolContext, ToolResult, _clean_schema

MAX_REPAIRS = 2
T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)

# ---------------------------------------------------------------- 契约模型


class PlanSubmission(BaseModel):
    """Planner 提交的计划（= core.models.Plan 去掉 task_id / model，由编排器补）。"""

    root_cause_hypothesis: str = Field(min_length=1, description="根因假设：先定位再假设，引用文件与函数")
    affected_files: list[str] = Field(default_factory=list, description="预计要改的文件（仓库相对路径）")
    repro_strategy: Literal["test", "script", "not_applicable"] = Field(
        description="复现策略：test = 写失败的复现测试；script = 脚本；not_applicable = 无法用测试复现（说明原因）"
    )
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        min_length=1, description="可执行的验收标准：check=test 写测试名，command 写命令，manual 写人工检查说明"
    )
    steps: list[PlanStep] = Field(default_factory=list, description="实施步骤（小步）")
    estimated_risk: RiskLevel = Field(description="风险预估 L0–L3（构建 / CI / 依赖 / 鉴权 / 公共 API 至少 L2）")
    needs_approval: bool = Field(default=False, description="需要人确认计划再动手时为 true")
    open_questions: list[str] = Field(default_factory=list, description="Issue 没说清、需要人回答的问题")

    def to_plan(self, *, task_id: str, model: str) -> Plan:
        return Plan(task_id=task_id, model=model, **self.model_dump())


class ReviewFinding(BaseModel):
    severity: Literal["blocker", "major", "minor", "nit"] = Field(
        description=(
            "blocker = 必须改否则不能合并（错误行为、回归、改弱测试、安全问题）；major = 应该改；minor / nit 可忽略"
        )
    )
    file: str | None = Field(default=None, description="仓库相对路径")
    line: int | None = Field(default=None, description="diff 新版本中的行号")
    message: str = Field(min_length=1, description="问题与依据（引用代码或测试结果）")
    suggestion: str | None = Field(default=None, description="具体修复建议")

    def to_finding(self) -> Finding:
        return Finding(**self.model_dump())


class Review(BaseModel):
    verdict: Literal["approve", "request_changes"] = Field(
        description="有 blocker 时必须 request_changes；否则 approve"
    )
    summary: str = Field(default="", description="一两句话的总体评价")
    findings: list[ReviewFinding] = Field(default_factory=list)

    @property
    def blockers(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.severity == "blocker"]

    @property
    def blocking(self) -> bool:
        return bool(self.blockers)


def check_review(r: BaseModel) -> str | None:
    """request_changes 必须至少带一条 blocker / major，approve 不能带 blocker（契约一致性）。"""
    assert isinstance(r, Review)
    if r.verdict == "approve" and r.blocking:
        return "verdict=approve 但 findings 里有 blocker：有 blocker 就必须 request_changes"
    if r.verdict == "request_changes" and not any(f.severity in ("blocker", "major") for f in r.findings):
        return "verdict=request_changes 但没有 blocker / major 级别的 finding：请写出问题，或改为 approve"
    return None


# ---------------------------------------------------------------- 工具 schema / 终止工具


def submit_tool_schema(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    return {"type": "function",
            "function": {"name": name, "description": description,
                         "parameters": _clean_schema(model.model_json_schema())}}  # fmt: skip


class SubmitTool[M: BaseModel]:
    """AgentLoop 里的终止工具：校验通过 → ok=True、`data.submission`；否则返回带原因的错误让模型改。"""

    side_effects: SideEffects = "none"
    refetchable = False
    terminal = True

    def __init__(
        self, name: str, model: type[M], description: str, *, check: Callable[[BaseModel], str | None] | None = None
    ) -> None:
        self.name = name
        self.Params = model
        self.description = description
        self.check = check

    async def run(self, params: Any, ctx: ToolContext) -> ToolResult:
        if self.check is not None and (err := self.check(params)) is not None:
            return ToolResult(ok=False, content=f"{self.name} 不一致：{err}", error_code="bad_args")
        ctx.state[f"{self.name}_submission"] = params.model_dump(mode="json")
        return ToolResult(ok=True, content="已提交。", data={"submission": params.model_dump(mode="json")})


def submit_plan_tool() -> SubmitTool[PlanSubmission]:
    return SubmitTool("submit_plan", PlanSubmission, "提交计划（只调用一次；提交后规划结束）")


def submit_review_tool() -> SubmitTool[Review]:
    return SubmitTool("submit_review", Review, "提交评审结论（只调用一次；提交后评审结束）", check=check_review)


# ---------------------------------------------------------------- 文本里抽 JSON

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def extract_json(text: str | None) -> dict[str, Any] | None:
    """```json 代码块优先，其次第一个 { 到最后一个 }。"""
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


def parse_model[M: BaseModel](
    model: type[M], raw: Any, check: Callable[[BaseModel], str | None] | None = None
) -> tuple[M | None, str]:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        v = model.model_validate(data)
    except (ValueError, ValidationError) as e:
        return None, str(e)[:800]
    if check is not None and (err := check(v)) is not None:
        return None, err
    return v, ""


# ---------------------------------------------------------------- 单次调用降级链

StructuredPath = Literal["tool_call", "repair", "content_json", "failed"]


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


@dataclass
class StructuredResult[T]:
    value: T | None
    path: StructuredPath
    attempts: int
    last_error: str = ""
    meta: dict[str, Any] = field(default_factory=lambda: {"cost_cny": 0.0})


async def structured_call[T](
    router: RouterLike,
    *,
    role: Any,
    messages: list[Message],
    tool: dict[str, Any],
    validate: Callable[[Any], tuple[T | None, str]],
    executor_vendor: Vendor | None = "deepseek",
    mode: Literal["background", "eval"] = "background",
    guard: TaskBudgetGuard | None = None,
    task_id: str | None = None,
    category: str = "dev",
    max_repairs: int = MAX_REPAIRS,
) -> StructuredResult[T]:
    """tool_choice=auto + 提交工具 → 参数非法回传校验错误（最多 max_repairs 次）→ 没调工具时从 content 抽 JSON。

    不能强制 tool_choice（Qwen 思考模式不支持 required / 指定函数，04 §3.3），所以是“auto + 校验 + 修复 + 抽取”。
    """
    name = tool["function"]["name"]
    meta: dict[str, Any] = {"cost_cny": 0.0}
    last_err = ""
    for attempt in range(1, max_repairs + 2):
        req = LLMRequest(role=role, messages=messages, tools=[tool], tool_choice="auto")
        resp = await router.complete(req, executor_vendor=executor_vendor, mode=mode, guard=guard,
                                     task_id=task_id, category=category)  # fmt: skip
        meta.update(model=resp.model or resp.served_model, variant=resp.variant, vendor_policy=resp.vendor_policy)
        meta["cost_cny"] += resp.cost_cny
        msg = resp.message
        calls = [c for c in msg.tool_calls or [] if c.name == name]
        if calls:
            v, err = validate(calls[0].arguments)
            if v is not None:
                return StructuredResult(v, "tool_call" if attempt == 1 else "repair", attempt, meta=meta)
            last_err = err
            replies = [
                Message(role="tool", tool_call_id=c.id, name=c.name,
                        content=f"参数不合法，请修正后重新调用 {name}：\n{err}" if c is calls[0] else "已忽略")
                for c in msg.tool_calls or []
            ]  # fmt: skip
            messages = [*messages, msg, *replies]
            continue
        obj = extract_json(msg.content)
        if obj is not None:
            v, err = validate(obj)
            if v is not None:
                return StructuredResult(v, "content_json", attempt, meta=meta)
            last_err = err
        else:
            last_err = f"没有调用 {name}，content 里也没有 JSON"
        messages = [*messages, Message(role="assistant", content=msg.content or ""),
                    Message(role="user", content=f"请调用 {name} 提交结论（{last_err[:300]}）。")]  # fmt: skip
    return StructuredResult(None, "failed", max_repairs + 1, last_error=last_err, meta=meta)


__all__ = [
    "MAX_REPAIRS",
    "PlanSubmission",
    "Review",
    "ReviewFinding",
    "StructuredResult",
    "SubmitTool",
    "check_review",
    "extract_json",
    "parse_model",
    "structured_call",
    "submit_plan_tool",
    "submit_review_tool",
    "submit_tool_schema",
]
