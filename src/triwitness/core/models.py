"""核心数据模型（docs/architecture.md §8 + ADR-0001 / ADR-0002）。

字段名就是契约；修改时同步更新 spec 与 ADR。所有时间字段必须带时区。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Vendor = Literal["deepseek", "qwen", "zhipu"]  # v0.1 只用 deepseek；后两个为保留值（ADR-0002）
Role = Literal["planner", "executor", "verifier", "reviewer", "summarizer", "classifier"]
RiskLevel = Literal["L0", "L1", "L2", "L3"]
VendorPolicy = Literal["single_vendor", "cross_vendor"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskState(StrEnum):
    RECEIVED = "received"
    PREPARING = "preparing"
    PLANNING = "planning"
    AWAIT_PLAN_APPROVAL = "await_plan_approval"
    REPRODUCING = "reproducing"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    PACKAGING = "packaging"
    AWAIT_PR_APPROVAL = "await_pr_approval"
    PR_OPENED = "pr_opened"
    CI_WATCH = "ci_watch"
    DONE = "done"
    NEEDS_HUMAN = "needs_human"
    BUDGET_EXCEEDED = "budget_exceeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------- 预算（ADR-0002）


class Budget(_Model):
    """单任务预算。默认值为 eval 档；`tw run` / dogfooding 用 `Budget.for_run()`。"""

    max_cost_cny: float = Field(default=0.8, gt=0)
    # W2-26：W2-25 里 3M 总输入（含缓存命中）总是先于 ¥ 上限触发（触发时才花 ¥0.2–0.4，未命中仅 ~10 万）。
    # 总量放到 6M 作兜底，另按未命中（真正计价的输入）设上限；¥ 上限才是真正的闸门。
    max_input_tokens: int = Field(default=6_000_000, gt=0)  # 含缓存命中，兜底
    max_uncached_input_tokens: int = Field(default=400_000, gt=0)  # 缓存未命中
    max_output_tokens: int = Field(default=100_000, gt=0)
    max_turns: int = Field(default=100, gt=0)
    max_wall_seconds: int = Field(default=1800, gt=0)
    warn_ratio: float = Field(default=0.8, gt=0, le=1)

    @classmethod
    def for_eval(cls) -> Budget:
        return cls()

    @classmethod
    def for_run(cls) -> Budget:
        return cls(max_cost_cny=1.0, max_wall_seconds=2700)


# ---------------------------------------------------------------- 任务与计划


class RepoRef(_Model):
    platform: Literal["github", "local"] = "github"
    full_name: str  # "owner/repo"
    base_commit: str
    clone_url: str | None = None


class Task(_Model):
    id: str  # "t_<ULID>"
    source: Literal["github_issue", "cli", "eval"]
    repo: RepoRef
    title: str
    body: str  # 不可信内容；渲染时一律包 <untrusted>
    issue_number: int | None = None
    mode: Literal["background", "interactive", "eval"] = "background"
    budget: Budget = Field(default_factory=Budget)
    harness_config: str
    config_hash: str
    state: TaskState = TaskState.RECEIVED
    created_at: AwareDatetime


class AcceptanceCriterion(_Model):
    id: str
    description: str
    check: Literal["test", "command", "manual"]
    detail: str


class PlanStep(_Model):
    id: str
    goal: str
    files: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    parallelizable: bool = False


class Plan(_Model):
    task_id: str
    root_cause_hypothesis: str
    affected_files: list[str]
    repro_strategy: Literal["test", "script", "not_applicable"]
    acceptance_criteria: list[AcceptanceCriterion]
    steps: list[PlanStep]
    estimated_risk: RiskLevel
    needs_approval: bool = False
    open_questions: list[str] = Field(default_factory=list)
    model: str


# ---------------------------------------------------------------- 完成契约（ADR-0001 #3）


class FileChange(_Model):
    path: str
    kind: Literal["added", "modified", "deleted"]
    note: str = ""


class ReproRef(_Model):
    path: str  # 目标仓库内 tests/tw_repro/test_issue_<n>.py（ADR-0001 #8）
    cmd: str


class FinishReport(_Model):
    summary: str = Field(min_length=1)
    changes: list[FileChange]
    repro: ReproRef | None = None
    tests_run: list[str] = Field(default_factory=list)
    tests_passed: bool
    confidence: float = Field(ge=0, le=1)
    open_risks: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- 用量与成本（ADR-0001 #5）


class Usage(_Model):
    input_tokens: int = Field(default=0, ge=0)  # 总输入（含缓存命中）
    cache_hit_tokens: int = Field(default=0, ge=0)
    cache_miss_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)  # 含推理 token（若厂商合并计费）
    reasoning_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_split(self) -> Usage:
        if self.cache_hit_tokens + self.cache_miss_tokens != self.input_tokens:
            raise ValueError("input_tokens 必须等于 cache_hit_tokens + cache_miss_tokens")
        return self

    def __add__(self, other: Usage) -> Usage:
        r = None
        if self.reasoning_tokens is not None or other.reasoning_tokens is not None:
            r = (self.reasoning_tokens or 0) + (other.reasoning_tokens or 0)
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            cache_hit_tokens=self.cache_hit_tokens + other.cache_hit_tokens,
            cache_miss_tokens=self.cache_miss_tokens + other.cache_miss_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=r,
        )

    @property
    def cache_hit_rate(self) -> float:
        return self.cache_hit_tokens / self.input_tokens if self.input_tokens else 0.0


class CostLine(_Model):
    role: Role
    vendor: Vendor
    model: str
    calls: int = Field(ge=0)
    usage: Usage
    cost_cny: float = Field(ge=0)
    peak_calls: int = Field(default=0, ge=0)  # DeepSeek 高峰时段调用次数


class CostReport(_Model):
    task_id: str
    lines: list[CostLine]
    sandbox_cost_cny: float = Field(default=0.0, ge=0)
    total_cny: float = Field(ge=0)
    budget_cny: float = Field(gt=0)
    cache_hit_rate: float = Field(ge=0, le=1)
    pricing_version: str
    estimated: bool = False  # True = 用户量缺失时的估算

    @classmethod
    def from_lines(
        cls,
        task_id: str,
        lines: list[CostLine],
        *,
        budget_cny: float,
        pricing_version: str,
        sandbox_cost_cny: float = 0.0,
        estimated: bool = False,
    ) -> CostReport:
        total_usage = sum((ln.usage for ln in lines), Usage())
        return cls(
            task_id=task_id,
            lines=lines,
            sandbox_cost_cny=sandbox_cost_cny,
            total_cny=round(sum(ln.cost_cny for ln in lines) + sandbox_cost_cny, 6),
            budget_cny=budget_cny,
            cache_hit_rate=round(total_usage.cache_hit_rate, 6),
            pricing_version=pricing_version,
            estimated=estimated,
        )

    def to_flat(self) -> dict[str, Any]:
        """拍平成一行（评测汇总 / CSV 用）。"""
        u = sum((ln.usage for ln in self.lines), Usage())
        return {
            "task_id": self.task_id,
            "total_cny": self.total_cny,
            "sandbox_cost_cny": self.sandbox_cost_cny,
            "budget_cny": self.budget_cny,
            "calls": sum(ln.calls for ln in self.lines),
            "peak_calls": sum(ln.peak_calls for ln in self.lines),
            "input_tokens": u.input_tokens,
            "cache_hit_tokens": u.cache_hit_tokens,
            "cache_miss_tokens": u.cache_miss_tokens,
            "output_tokens": u.output_tokens,
            "cache_hit_rate": self.cache_hit_rate,
            "pricing_version": self.pricing_version,
            "estimated": self.estimated,
        }


# ---------------------------------------------------------------- 步骤与轨迹


class ToolCall(_Model):
    id: str
    name: str
    arguments: dict[str, Any]
    policy_decision: Literal["allow", "deny", "approved", "rejected"] = "allow"
    policy_reason: str | None = None
    started_at: AwareDatetime | None = None
    duration_ms: int | None = None
    ok: bool | None = None
    result_preview: str | None = None
    result_ref: str | None = None
    refetchable: bool = False
    error_type: str | None = None


class ModelCall(_Model):
    vendor: Vendor
    model: str
    served_model: str | None = None
    role: Role
    thinking: bool
    effort: Literal["low", "high", "max"] | None = None
    usage: Usage
    cost_cny: float = Field(ge=0)
    peak: bool | None = None
    latency_ms: int = Field(ge=0)
    finish_reason: str | None = None
    prompt_version: str


class Step(_Model):
    index: int = Field(ge=0)
    agent: Role
    kind: Literal["model_call", "tool_call", "context_event", "state_change", "human"]
    model_call: ModelCall | None = None
    tool_call: ToolCall | None = None
    context_event: Literal["clear", "compact", "notes_injected", "reflection"] | None = None
    note: str | None = None
    ts: AwareDatetime


class TestRun(_Model):
    __test__ = False  # 防止 pytest 当成测试类收集

    scope: Literal["repro_base", "repro_patched", "related", "full", "hidden"]
    command: str
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    new_failures: list[str] = Field(default_factory=list)
    flaky: list[str] = Field(default_factory=list)
    duration_s: float = Field(ge=0)
    log_ref: str


class RiskFactor(_Model):
    code: str
    points: int
    detail: str


class Finding(_Model):
    severity: Literal["blocker", "major", "minor", "nit"]
    file: str | None = None
    line: int | None = None
    message: str
    suggestion: str | None = None
    status: Literal["open", "fixed", "wontfix"] = "open"


class Evidence(_Model):
    task_id: str
    summary: str
    root_cause: str
    repro_status: Literal["reproduced", "not_applicable", "inconclusive", "failed"]
    repro_path: str | None = None
    base_ref: str | None = None  # 复现对照的基线提交
    clean_env: Literal["verified", "unverified"] = "verified"  # 无沙箱 → unverified（ADR-0005 §3.3）
    unverified_reason: str | None = None
    test_runs: list[TestRun]
    static_checks: dict[str, Literal["pass", "fail", "skipped"]]
    anticheat_flags: list[str] = Field(default_factory=list)
    claim_flags: list[str] = Field(default_factory=list)  # 完成声明审计（verify.claim）
    verdict: Literal["pass", "fail", "inconclusive"]
    verifier_model: str
    criteria_results: dict[str, Literal["met", "unmet", "unknown"]]
    review_model: str | None = None
    review_variant: str | None = None  # v0.1 同厂商异构评审的变体名
    vendor_policy: VendorPolicy = "single_vendor"
    findings: list[Finding] = Field(default_factory=list)
    risk_score: int
    risk_level: RiskLevel
    risk_factors: list[RiskFactor]
    diff_stats: dict[str, int]
    cost: CostReport
    trace_url: str | None = None
    config_hash: str


class Trajectory(_Model):
    task_id: str
    run_id: str
    config_hash: str
    harness_config: str
    prompt_versions: dict[str, str]
    model_routing: dict[Role, str]
    steps: list[Step]
    final_state: TaskState
    diff: str | None = None
    evidence: Evidence | None = None
    hidden_test_result: Literal["resolved", "unresolved", "infra_error"] | None = None
    failure_category: str | None = None
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
