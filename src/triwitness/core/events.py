"""轨迹事件 = UI↔core 契约 `tw-events/1`（docs/design/event-protocol.md）。

- 信封 `TrajectoryEvent` 与 spec 005 §4 一致，新增 `v: 1`。
- 每个已知 `kind` 有一个 payload 模型；payload 允许额外字段（v1 只增不改）。
- 读取方（UI）遇到未知 `kind` 必须忽略；core 写入时只写已知 `kind`。
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, create_model

from triwitness.core.models import CostReport, Finding, FinishReport, Role, TaskState, Usage

PROTOCOL = "tw-events/1"
PROTOCOL_VERSION = 1
DISPLAY_MAX = 200
PREVIEW_MAX = 2000
DELTA_MAX = 4000

EventKind = Literal[
    "task_started",
    "model_call",
    "tool_call",
    "state_change",
    "checkpoint",
    "loop_warning",
    "context_event",
    "hitl_request",
    "hitl_response",
    "approval_requested",
    "approval_resolved",
    "mode_changed",
    "verification",
    "review",
    "task_finished",
    "error",
    "environment_prepared",
    "model_delta",
    "reasoning_delta",
    "user_message",
    "turn_finished",
]
RoleHint = Literal["planner", "executor", "verifier", "reviewer", "system"]
PermissionDecision = Literal["allow", "ask", "deny"]
SandboxBackendName = Literal["none", "docker", "wsl2", "remote"]
# spec 006 v3：四种模式；auto_edit / auto / unrestricted 是旧值，只为读取 0.2.0 及更早的轨迹保留
ApprovalMode = Literal["plan", "ask", "auto_review", "full_access", "auto_edit", "auto", "unrestricted"]


# ---------------------------------------------------------------- payloads


class Payload(BaseModel):
    """所有 payload 的公共字段。`display` 写入前必须已脱敏。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    display: str | None = Field(default=None, max_length=DISPLAY_MAX)
    role_hint: RoleHint | None = None


class TaskStartedPayload(Payload):
    issue_title: str
    repo: str
    config_hash: str
    issue_number: int | None = None
    harness: str | None = None  # configs/harness/<name>.yaml（W2-15）
    harness_hash: str | None = None  # 规范化配置 + 提示版本的哈希
    prompt_versions: dict[str, str] | None = None  # 角色 → name@vN（04 §3.3 原则 4）
    mode: Literal["background", "interactive", "eval"] = "background"
    # 可选：本次注入的记忆摘要（桌面端芯片）；完整列表见 artifacts/memory.json
    memory: dict[str, Any] | None = None


class StateChangePayload(Payload):
    from_: TaskState = Field(alias="from")
    to: TaskState


class ModelCallPayload(Payload):
    call_id: str | None = None  # 与本次调用的 model_delta / reasoning_delta、后续 tool_call 对应
    model: str
    served_model: str | None = None
    thinking: bool
    usage: Usage
    cost_cny: float = Field(ge=0)  # 实付（与账本一致；本地缓存命中为 0）
    nominal_cost_cny: float | None = Field(default=None, ge=0)  # 名义价（与实付不同才写）
    cached: bool = False  # 本地 llm-cache 命中
    peak: bool | None = None
    latency_ms: int = Field(ge=0)
    finish_reason: str | None = None
    request_ref: str | None = None  # artifacts/<seq>-request.json（完整请求，不内联）
    response_ref: str | None = None  # artifacts/<seq>-response.json


def billing(resp: Any) -> dict[str, Any]:
    """LLMResponse → ModelCallPayload 的计费字段（实付 / 名义价 / 是否缓存命中）。"""
    cost = float(getattr(resp, "cost_cny", 0.0) or 0.0)
    nominal = float(getattr(resp, "nominal_cost_cny", 0.0) or 0.0)
    return {"cost_cny": cost, "cached": bool(getattr(resp, "cached", False)),
            "nominal_cost_cny": nominal if nominal and abs(nominal - cost) > 1e-12 else None}  # fmt: skip


class ToolCallPayload(Payload):
    tool: str
    ok: bool
    exit_code: int | None = None
    duration_ms: int = Field(ge=0)
    output_ref: str | None = None  # 只放引用，不内联工具原文
    message_ref: str | None = None  # artifacts/<seq>-tool.json：回给模型的工具消息（用于重建历史）
    truncated: bool = False
    error_type: str | None = None
    # 权限判定（spec 006）：allow 由哪条规则放行，便于审计；ask 时另有 approval_* 事件
    permission: PermissionDecision | None = None
    permission_rule: str | None = None
    # 对话流里的工具行（UI 可展开）：发起它的模型调用、参数与输出预览（均已脱敏、截断）
    call_id: str | None = None
    args_preview: str | None = Field(default=None, max_length=PREVIEW_MAX)
    output_preview: str | None = Field(default=None, max_length=PREVIEW_MAX)


class CheckpointPayload(Payload):
    label: str
    ref: str | None = None


class LoopWarningPayload(Payload):
    signal: Literal["repeat_action", "consecutive_failures", "no_progress"]
    level: int = Field(ge=1, le=3)
    detail: str | None = None


class ContextEventPayload(Payload):
    """上下文管理（spec 007，W2-13/14）：clear = 批量把较早的可重取工具结果换成占位符；compact = 摘要压缩。"""

    action: Literal["clear", "compact"]
    tokens_before: int = Field(ge=0)
    tokens_after: int = Field(ge=0)
    cleared: int = Field(default=0, ge=0)
    summary_chars: int | None = None
    notes_chars: int | None = None
    failures_recorded: int = Field(default=0, ge=0)
    summarizer: Literal["model", "fallback"] | None = None


class HitlRequestPayload(Payload):
    request_id: str
    question: str
    options: list[str]
    blocking: bool = True


class HitlResponsePayload(Payload):
    request_id: str
    answer: str
    by: str


class ApprovalRequestedPayload(Payload):
    """权限引擎判为 ask 时发出（spec 006 §7、ADR-0005）。

    eval / 非交互模式不发此事件，直接写 approval_resolved(by=policy)。
    """

    request_id: str
    tool: str  # 规则里的工具类别：Bash / PowerShell / Read / Edit / Fetch / Mcp
    action: str  # 已脱敏、已规范化的命令或路径（≤ 2000 字）
    reason: str  # 为什么要问：命中的 ask 规则、出工作区、网络、不可解析……
    rule: str | None = None  # 命中的规则原文，如 "Bash(git push *)"
    rule_source: Literal["default", "user", "project", "local", "session", "managed"] | None = None
    risk: Literal["L0", "L1", "L2", "L3"] = "L1"
    options: list[Literal["allow_once", "allow_session", "allow_always", "deny"]] = Field(
        default_factory=lambda: ["allow_once", "allow_session", "allow_always", "deny"]
    )
    suggested_rule: str | None = None  # “总是允许”时将写入 local 的规则
    backend: SandboxBackendName = "none"
    timeout_s: int | None = None  # None = 一直等（后台任务进入 needs_human）


class ApprovalResolvedPayload(Payload):
    request_id: str
    decision: Literal["allow", "deny"]
    scope: Literal["once", "session", "always"] = "once"
    by: Literal["user", "policy", "timeout", "cancelled", "reviewer"]  # reviewer：模型自动审批（auto_review）
    saved_rule: str | None = None  # scope=always 时写入的规则
    comment: str | None = None  # 用户附言（拒绝理由会回传给模型）


class ModeChangedPayload(Payload):
    """审批模式切换（spec 006 §4.6）。risk=high（full_access）时 UI 显示常驻红色横幅，直到切回。"""

    from_mode: ApprovalMode
    to_mode: ApprovalMode
    scope: Literal["task", "session"] = "task"
    risk: Literal["normal", "high"] = "normal"
    by: Literal["user", "system", "auto_revert"] = "user"
    backend: SandboxBackendName = "none"
    reason: str | None = None


class VerificationPayload(Payload):
    verdict: Literal["pass", "fail", "inconclusive"]
    evidence_ref: str | None = None
    tests_passed: bool | None = None
    risk_level: Literal["L0", "L1", "L2", "L3"] | None = None
    # 干净环境复跑证人（spec 002 §8 / ADR-0005）：无沙箱时为 unverified，不得自动合并
    clean_env: Literal["verified", "failed", "unverified"] | None = None
    unverified_reason: Literal["no_sandbox", "backend_unavailable", "skipped"] | None = None


class EnvironmentPreparedPayload(Payload):
    """PREPARING 结束（W3-03）：依赖来源、安装结果、修改前就失败的测试集合（回归对比的基线）。"""

    setup_source: Literal["repo", "cache", "model", "heuristic", "none"]
    install_commands: list[str] = Field(default_factory=list)
    installed: bool = False  # 实际执行了安装命令
    ok: bool = True
    test_command: str | None = None
    baseline_failures: list[str] = Field(default_factory=list)  # 最多 200 个；完整列表见 baseline_ref
    baseline_failure_count: int = Field(default=0, ge=0)
    baseline_duration_s: float | None = None
    baseline_ref: str | None = None
    notes: list[str] = Field(default_factory=list)


class ReviewPayload(Payload):
    model: str
    variant: str  # v0.1 同厂商异构评审的变体名
    vendor_policy: Literal["single_vendor", "cross_vendor"] = "single_vendor"
    findings: list[Finding] = Field(default_factory=list)


class TaskFinishedPayload(Payload):
    status: Literal["done", "failed", "budget_exceeded", "stuck", "needs_human", "cancelled"]
    finish_report: FinishReport | None = None
    cost_report: CostReport | None = None


class ErrorPayload(Payload):
    type: str
    message: str


class DeltaPayload(Payload):
    """流式增量（tw-events/1 增补，v 仍为 1）：一次模型调用的回复正文 / 推理片段，按 index 顺序拼接。

    只在交互运行（`tw run --jsonl`）里写；片段已按约 50ms 合并。调用结束后照常有 model_call 事件。
    """

    call_id: str
    index: int = Field(ge=0)
    text: str = Field(max_length=DELTA_MAX)


class ModelDeltaPayload(DeltaPayload):
    pass


class ReasoningDeltaPayload(DeltaPayload):
    pass


class UserMessagePayload(Payload):
    """对话轮的用户消息（0.3.1）：每轮第一条事件；`parent_run` 指向上一轮（多轮历史）。"""

    text: str = Field(max_length=PREVIEW_MAX)
    repo: str | None = None
    parent_run: str | None = None


class TurnFinishedPayload(Payload):
    """一轮对话结束：`kind=chat` 是直接回复（无工具、无产物）；`kind=task` 表示本轮转成了仓库任务。"""

    kind: Literal["chat", "task"]
    status: str
    reply: str | None = Field(default=None, max_length=PREVIEW_MAX)
    cost_cny: float = Field(default=0.0, ge=0)


PAYLOADS: dict[str, type[Payload]] = {
    "task_started": TaskStartedPayload,
    "state_change": StateChangePayload,
    "model_call": ModelCallPayload,
    "tool_call": ToolCallPayload,
    "checkpoint": CheckpointPayload,
    "loop_warning": LoopWarningPayload,
    "context_event": ContextEventPayload,
    "hitl_request": HitlRequestPayload,
    "hitl_response": HitlResponsePayload,
    "approval_requested": ApprovalRequestedPayload,
    "approval_resolved": ApprovalResolvedPayload,
    "mode_changed": ModeChangedPayload,
    "verification": VerificationPayload,
    "review": ReviewPayload,
    "task_finished": TaskFinishedPayload,
    "error": ErrorPayload,
    "environment_prepared": EnvironmentPreparedPayload,
    "model_delta": ModelDeltaPayload,
    "reasoning_delta": ReasoningDeltaPayload,
    "user_message": UserMessagePayload,
    "turn_finished": TurnFinishedPayload,
}


# ---------------------------------------------------------------- 信封


class TrajectoryEvent(BaseModel):
    """spec 005 §4 的通用信封（payload 为 dict）。写盘 / 读盘都用它。"""

    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = PROTOCOL_VERSION
    seq: int = Field(ge=0)  # 单调递增
    ts: AwareDatetime  # 存 UTC，展示转 Asia/Shanghai
    task_id: str
    run_id: str
    role: Role | None = None
    kind: EventKind
    payload: dict[str, Any]
    trace_id: str | None = None
    span_id: str | None = None

    def typed_payload(self) -> Payload:
        """按 kind 校验并返回强类型 payload。"""
        return PAYLOADS[self.kind].model_validate(self.payload)

    def to_json_line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))


def make_event(
    *,
    seq: int,
    ts: Any,
    task_id: str,
    run_id: str,
    role: Role | None,
    payload: Payload,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> TrajectoryEvent:
    """从强类型 payload 构造事件（kind 由 payload 类型推出）。"""
    kind = next(k for k, cls in PAYLOADS.items() if type(payload) is cls)
    return TrajectoryEvent(
        seq=seq,
        ts=ts,
        task_id=task_id,
        run_id=run_id,
        role=role,
        kind=kind,  # type: ignore[arg-type]
        payload=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
        trace_id=trace_id,
        span_id=span_id,
    )


def parse_event_line(line: str) -> TrajectoryEvent:
    """解析一行 JSONL，并校验 payload 与 kind 匹配。"""
    ev = TrajectoryEvent.model_validate_json(line)
    ev.typed_payload()
    return ev


# ---------------------------------------------------------------- JSON Schema（强类型，按 kind 区分）


def _typed_event_model(kind: str, payload_cls: type[Payload]) -> type[BaseModel]:
    name = "".join(p.capitalize() for p in kind.split("_")) + "Event"
    fields: dict[str, Any] = {
        "v": (Literal[1], PROTOCOL_VERSION),
        "seq": (int, Field(ge=0)),
        "ts": (AwareDatetime, ...),
        "task_id": (str, ...),
        "run_id": (str, ...),
        "role": (Role | None, None),
        "kind": (Literal[kind], ...),  # type: ignore[valid-type]
        "payload": (payload_cls, ...),
        "trace_id": (str | None, None),
        "span_id": (str | None, None),
    }
    return create_model(name, __config__=ConfigDict(extra="forbid"), **fields)


_TYPED = [_typed_event_model(k, c) for k, c in PAYLOADS.items()]


def tw_events_json_schema() -> dict[str, Any]:
    """导出 `schemas/tw-events-1.schema.json` 的内容（按 kind 判别的 oneOf）。"""
    from typing import Union

    union = Annotated[Union[tuple(_TYPED)], Field(discriminator="kind")]  # type: ignore[valid-type]  # noqa: UP007
    schema = TypeAdapter(union).json_schema(by_alias=True)  # pyright: ignore[reportArgumentType]
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://triwitness.dev/schemas/tw-events-1.schema.json"
    schema["title"] = PROTOCOL
    schema["description"] = "TriWitness 轨迹事件（一行一个 JSON 对象）。读取方遇到未知 kind 必须忽略。"
    return schema


def dump_schema() -> str:
    return json.dumps(tw_events_json_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
