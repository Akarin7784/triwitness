"""Harness 配置（spec 003 §8、spec 007，W2-15）：所有阈值 / 工具集 / 截断 / 上下文参数从 configs/harness/*.yaml 读。

- `extends: baseline.yaml`：消融配置只写差异，深合并到父配置上。
- `config_hash`：规范化后的配置 + 提示版本的 sha256 前 12 位，写进 task_started（消融可追溯）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from triwitness.config import load_config
from triwitness.core.errors import ConfigError
from triwitness.llm.limits import auto_working_budget
from triwitness.prompts import load_prompt

DEFAULT_TOOLS = [
    "bash", "edit_file", "finish", "git", "grep", "list_files", "notes", "read_file", "run_tests", "write_file",
]  # fmt: skip


class TokenAllocation(BaseModel):
    """工作预算的分配（token）。固定部分之和必须 ≤ clear_at × 工作预算，否则清理永远压不下来。"""

    prefix: int = 12_000  # system 提示 + AGENTS.md 摘要 + 工具 schema
    task: int = 8_000  # Issue 正文（超出则头尾截断）
    notes: int = 2_000  # 压缩后重新注入的 NOTES.md
    summary: int = 4_000  # 压缩摘要
    tool_result: int = 8_000  # 单条工具结果（超出则截断，全文写 .tw/outputs/）
    repo_map: int = 2_000  # repo_map 默认 max_tokens


class RereadConfig(BaseModel):
    """压缩后重新读入最近修改的文件（CC 报告 §4：官方压缩后会重读最近改过的文件）。max_files=0 关闭。"""

    max_files: int = Field(default=0, ge=0, le=20)
    max_tokens: int = Field(default=40_000, ge=0)


class ContextConfig(BaseModel):
    # 128K 是 W2 基线（baseline.yaml 冻结）；1M 档（long-context-1m.yaml，默认）写 auto = 窗口 − 输出预留 − 3%（≈950K）
    working_budget_tokens: int | Literal["auto"] = 128_000
    clear: bool = True
    compact: bool = True
    clear_at: float = 0.6  # 估算上下文 > 60% 工作预算 → 批量清理
    clear_to: float = 0.35  # 一旦清理就清到 35% 以下（滞回）：保证下次清理前有足够的只追加区间
    compact_at: float = 0.8  # 清理后仍 > 80% → 压缩
    keep_recent: int = 8  # 清理时保留最近 K 条工具结果
    # 一次清理至少省下这么多（占工作预算的比例），或能清到 clear_to 以下，才值得让缓存前缀失效；
    # 否则不清，留给压缩（真跑发现：可清内容不足时会退化成每隔几步清 1 条，spec 007 变更记录）
    min_clear_gain: float = Field(default=0.1, ge=0, le=1)
    keep_recent_turns: int = 4  # 压缩时原样保留最近 N 轮（assistant + 其工具结果）
    clearable_tools: list[str] = Field(
        default_factory=lambda: ["git", "grep", "list_files", "notes", "read_file", "repo_map", "run_tests"]
    )
    untrusted_wrap: bool = True  # Issue / 工具输出包 <untrusted source=...>
    trusted_tools: list[str] = Field(default_factory=lambda: ["edit_file", "finish", "write_file"])
    chars_per_token: float = 3.0  # 没有真实用量时的估算（中英混排偏保守）
    min_steps_between_compactions: int = 3
    allocation: TokenAllocation = Field(default_factory=TokenAllocation)
    # ---- 1M 档新增（默认值 = 旧行为；等于默认值时不进 config_hash，W2 基线哈希不变）
    tail_max_tokens: int | None = Field(default=None, gt=0)  # 压缩时原样保留尾部的绝对上限（另有 40% 预算的比例上限）
    summary_input_tokens: int = Field(default=24_000, gt=0)  # 交给 summarizer 的历史转录上限
    max_ineffective_compactions: int = Field(default=2, ge=1)  # 连续 N 次压完仍高于压缩线 → context_thrash 结束
    reread_recent_files: RereadConfig = Field(default_factory=RereadConfig)

    @model_validator(mode="after")
    def _check(self) -> ContextConfig:
        if not 0 < self.clear_to < self.clear_at <= self.compact_at <= 1:
            raise ValueError("需要 0 < clear_to < clear_at ≤ compact_at ≤ 1")
        if isinstance(self.working_budget_tokens, int) and self.working_budget_tokens <= 0:
            raise ValueError("working_budget_tokens 必须 > 0 或写 auto")
        a = self.allocation
        fixed = a.prefix + a.task + a.notes + a.summary
        if fixed > self.clear_at * self.budget_tokens():
            raise ValueError(f"固定分配 {fixed} token 超过清理阈值 {self.clear_at:.0%} × {self.budget_tokens()}")
        return self

    def budget_tokens(self, role: str = "executor") -> int:
        """实际工作预算：auto = 该角色的输入硬上限（core/limits.py）。"""
        if self.working_budget_tokens == "auto":
            return auto_working_budget(role)
        return self.working_budget_tokens

    def chars(self, tokens: int) -> int:
        return int(tokens * self.chars_per_token)


class PlannerConfig(BaseModel):
    enabled: bool = False
    max_turns: int = Field(default=30, gt=0)  # Planner 自己的回合上限（只读调查 + submit_plan）


class ReviewerConfig(BaseModel):
    enabled: bool = False
    max_rounds: int = Field(default=2, ge=0)  # blocker → 返工的次数上限（CC Stop hook 式“有上限的不许停”）
    max_turns: int = Field(default=20, gt=0)
    consensus: bool = False  # 两个异构变体都给 blocker 才阻断（行业扫描建议，可选；W4-14 不建议默认开）
    max_diff_chars: int = Field(default=60_000, gt=0)
    # 单评审用哪个变体（共识模式固定 adversarial + checklist）。W4-14 消融后 Eva 2026-10-12 01:01 定为 checklist
    # （flash 非思考 temperature 1.0 + 清单式提示）
    variant: Literal["adversarial", "checklist", "plain"] = "checklist"
    force_submit: bool = True  # 最后一次允许的调用强制 submit_review（关思考）；W4-14 消融脚本关掉以保持协议可比


class PlanApprovalConfig(BaseModel):
    """计划确认（04 §3.7；spec 010 §8 / §11 Q1——待 Eva 拍板，默认取 04 的 L2，可配置）。"""

    min_risk: Literal["L0", "L1", "L2", "L3"] = "L2"
    on_open_questions: bool = True  # Planner 列了待回答问题 → 需要确认
    on_sensitive_files: bool = True  # affected_files 命中 risk.yaml 的 build_files / sensitive_paths → 需要确认
    unattended: Literal["needs_human", "approve"] = "needs_human"  # 没有审批通道（终端 tw run）时
    # 评测自动策略（§11 Q2，Eva 21:36）：never = 全部批准（含 L3）；L1–L3 = ≥ 它拒绝
    eval_reject_from: Literal["L1", "L2", "L3", "never"] = "never"


class HitlConfig(BaseModel):
    """人工确认点（04 §3.7，W4-10；spec 010 §8.3 / §11 Q7——默认开，待 Eva 审）：交互运行必须由人确认，
    不交给审核模型；非交互拒绝；评测与 full_access 不经过。"""

    dependency_changes: bool = True  # 改依赖声明（pyproject / requirements / package.json / lock …；uv add 等）
    ci_changes: bool = True  # 改 CI / 构建配置（.github/workflows、Makefile、Dockerfile、tox.ini …）


class OrchestrationConfig(BaseModel):
    """角色开关（spec 010 §8）：默认全关 = W3 行为（基线可复现）；orchestrated-1m.yaml 打开 Planner + Reviewer。"""

    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    reviewer: ReviewerConfig = Field(default_factory=ReviewerConfig)
    plan_approval: PlanApprovalConfig = Field(default_factory=PlanApprovalConfig)
    hitl: HitlConfig = Field(default_factory=HitlConfig)
    # 断点续跑时从事件日志重放 Executor 的历史（spec 011 §3，W4-09）；false = 旧方式（新开历史 + 续跑说明）
    replay_on_resume: bool = True


PrAction = Literal["auto", "confirm", "draft", "none"]


class CiWatchConfig(BaseModel):
    """PR 分支的 CI 回流（spec 012 §6，W5-06）：gh 轮询检查结果，失败把精简日志交给 Executor 修，最多 N 轮。"""

    watch: bool = True
    max_fix_rounds: int = Field(default=2, ge=0, le=5)
    timeout_s: int = Field(default=1800, ge=30)  # 单轮等待 CI 的上限
    poll_s: int = Field(default=30, ge=1)
    no_checks_grace_s: int = Field(default=120, ge=0)  # 这么久还没有任何检查 → 认为仓库没配 CI
    log_max_chars: int = Field(default=6000, ge=500)


class GithubConfig(BaseModel):
    """开 PR 的风险分级决策（04 §3.7 / §4.6，spec 012 §5，W5-05）。只在 `tw run --open-pr` 时生效。

    auto = 直接开 PR；confirm = 先确认再开；draft = 先确认再开 Draft PR；
    none = 不开 PR（保留分支，可手动 `tw pr open`）。
    默认 L0 也要确认（对外可见的动作，Eva 未授权自动开）；可在 harness 里改成 auto。
    """

    pr_policy: dict[Literal["L0", "L1", "L2", "L3"], PrAction] = Field(
        default_factory=lambda: {"L0": "confirm", "L1": "confirm", "L2": "draft", "L3": "none"}
    )
    unknown_risk: Literal["L0", "L1", "L2", "L3"] = "L2"  # 没有验证结论也没有计划时按这个等级
    ci: CiWatchConfig = Field(default_factory=CiWatchConfig)


# W2-26：Executor 流程默认先复现（submit_repro + finish 校验）。`baseline.yaml` 仍是 W2-25 基线与消融的父配置，
# 显式写 `harness: configs/harness/baseline.yaml` 的 RunConfig（W2-25 基线复跑）不受影响。
# 1M 档（Eva 2026-10-11 20:26）：默认 long-context-1m.yaml（继承 repro-first，只改上下文参数）；
# baseline.yaml / repro-first.yaml 冻结，W2-25 / W2-26 的 harness_hash 不变。
DEFAULT_HARNESS = "harness/long-context-1m.yaml"

# 这些字段在 1M 档时新增：等于默认值时不进 config_hash，旧配置的哈希保持不变
_HASH_COMPAT_CONTEXT = ("tail_max_tokens", "summary_input_tokens", "max_ineffective_compactions", "reread_recent_files")
# W4 新增的顶层字段：同样等于默认值时不进 config_hash
_HASH_COMPAT_TOP = ("parallel_read_tools", "orchestration", "github")


class HarnessConfig(BaseModel):
    name: str = "baseline"
    # loop
    stuck_after_no_tool: int = 3
    tool_result_max_chars: int | None = None  # 兼容旧字段；默认由 allocation.tool_result 推出
    head_ratio: float = 0.6
    head_ratio_by_tool: dict[str, float] = Field(default_factory=lambda: {"bash": 0.3, "powershell": 0.3,
                                                                          "run_tests": 0.25})  # fmt: skip
    # loop_detection
    window: int = 8
    repeat_threshold: int = 3
    failure_threshold: int = 5
    no_progress_threshold: int = 6
    max_warnings: int = 3
    parallel_read_tools: bool = True  # 同一轮连续的只读工具并发执行（spec 010 §7；只影响耗时）
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    github: GithubConfig = Field(default_factory=GithubConfig)  # W5：开 PR 决策与 CI 回流（默认不开 PR）
    reminders: dict[str, str] = Field(default_factory=dict)
    context: ContextConfig = Field(default_factory=ContextConfig)
    tools: list[str] = Field(default_factory=lambda: list(DEFAULT_TOOLS))
    prompts: dict[str, str] = Field(default_factory=lambda: {"executor": "executor", "summarizer": "summarizer"})

    @classmethod
    def default(cls) -> HarnessConfig:
        """Executor 流程的默认 harness（W2-26 起为 repro-first：先复现、后修复）。"""
        return cls.load(DEFAULT_HARNESS)

    @classmethod
    def load(cls, name: str = "harness/baseline.yaml") -> HarnessConfig:
        raw = _resolve(name, set())
        stem = name.rsplit("/", 1)[-1].removesuffix(".yaml")
        return cls.from_dict(raw, default_name=stem)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, default_name: str = "custom") -> HarnessConfig:
        known = {
            "loop",
            "loop_detection",
            "reminders",
            "context",
            "tools",
            "prompts",
            "name",
            "extends",
            "orchestration",
        }
        unknown = set(raw) - known
        if unknown:
            raise ConfigError(f"harness 配置有未知字段：{', '.join(sorted(unknown))}")
        kw: dict[str, Any] = {**(raw.get("loop") or {}), **(raw.get("loop_detection") or {})}
        for k in ("reminders", "context", "tools", "prompts", "orchestration"):
            if raw.get(k) is not None:
                kw[k] = raw[k]
        try:
            return cls(name=raw.get("name", default_name), **kw)
        except ValueError as e:
            raise ConfigError(f"harness 配置无效：{e}") from e

    # ---------------------------------------------------------------- 派生
    @property
    def max_tool_result_chars(self) -> int:
        return self.tool_result_max_chars or self.context.chars(self.context.allocation.tool_result)

    def head_ratio_for(self, tool: str) -> float:
        return self.head_ratio_by_tool.get(tool, self.head_ratio)

    def prompt_versions(self) -> dict[str, str]:
        return {role: load_prompt(n).tag for role, n in sorted(self.prompts.items())}

    def config_hash(self) -> str:
        cfg = self.model_dump(mode="json", exclude={"name"})
        defaults = ContextConfig.model_fields
        for k in _HASH_COMPAT_CONTEXT:
            d = defaults[k].get_default(call_default_factory=True)
            if cfg["context"][k] == (d.model_dump(mode="json") if isinstance(d, BaseModel) else d):
                del cfg["context"][k]
        for k in _HASH_COMPAT_TOP:
            d = HarnessConfig.model_fields[k].get_default(call_default_factory=True)
            if cfg[k] == (d.model_dump(mode="json") if isinstance(d, BaseModel) else d):
                del cfg[k]
        blob = json.dumps({"cfg": cfg, "prompts": self.prompt_versions()}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]

    def reminder(self, key: str, **kw: str) -> str:
        defaults = {
            "no_tool": "请调用工具继续，或调用 finish 结束。",
            "wrap_up": "预算已用到警戒线，请尽快收尾。",
            "final_submit": "这是最后一次调用：现在必须调用 {tool} 提交结论"
            "（拿不准的写进 summary 或 findings），不能再调用其他工具。",
            "repeat": "你在重复同样的动作（{detail}），请换个思路。",
            "failures": "连续多次工具调用失败（{detail}），请换一种做法。",
            "no_progress": "已经 {detail}，请修改代码、运行测试或调用 finish。",
        }
        return self.reminders.get(key, defaults[key]).format(**kw)


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _resolve(name: str, seen: set[str]) -> dict[str, Any]:
    if name in seen:
        raise ConfigError(f"harness 配置 extends 成环：{name}")
    seen.add(name)
    own = dict(load_config(name))
    parent = own.pop("extends", None)
    if not parent:
        return own
    folder = name.rsplit("/", 1)[0] + "/" if "/" in name else ""
    raw = _merge(_resolve(folder + parent, seen), own)
    if "name" not in own:
        raw.pop("name", None)  # 名字不继承：默认取文件名
    return raw


__all__ = [
    "DEFAULT_TOOLS",
    "CiWatchConfig",
    "ContextConfig",
    "GithubConfig",
    "HarnessConfig",
    "OrchestrationConfig",
    "PlanApprovalConfig",
    "PlannerConfig",
    "PrAction",
    "RereadConfig",
    "ReviewerConfig",
    "TokenAllocation",
]
