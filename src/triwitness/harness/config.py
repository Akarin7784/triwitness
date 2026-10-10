"""Harness 配置（spec 003 §8、spec 007，W2-15）：所有阈值 / 工具集 / 截断 / 上下文参数从 configs/harness/*.yaml 读。

- `extends: baseline.yaml`：消融配置只写差异，深合并到父配置上。
- `config_hash`：规范化后的配置 + 提示版本的 sha256 前 12 位，写进 task_started（消融可追溯）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field, model_validator

from triwitness.config import load_config
from triwitness.core.errors import ConfigError
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


class ContextConfig(BaseModel):
    working_budget_tokens: int = 128_000  # 不按 1M 用满（04 §3.5）
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

    @model_validator(mode="after")
    def _check(self) -> ContextConfig:
        if not 0 < self.clear_to < self.clear_at <= self.compact_at <= 1:
            raise ValueError("需要 0 < clear_to < clear_at ≤ compact_at ≤ 1")
        a = self.allocation
        fixed = a.prefix + a.task + a.notes + a.summary
        if fixed > self.clear_at * self.working_budget_tokens:
            raise ValueError(f"固定分配 {fixed} token 超过清理阈值 {self.clear_at:.0%} × {self.working_budget_tokens}")
        return self

    def chars(self, tokens: int) -> int:
        return int(tokens * self.chars_per_token)


# W2-26：Executor 流程默认先复现（submit_repro + finish 校验）。`baseline.yaml` 仍是 W2-25 基线与消融的父配置，
# 显式写 `harness: configs/harness/baseline.yaml` 的 RunConfig（W2-25 基线复跑）不受影响。
DEFAULT_HARNESS = "harness/repro-first.yaml"


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
        known = {"loop", "loop_detection", "reminders", "context", "tools", "prompts", "name", "extends"}
        unknown = set(raw) - known
        if unknown:
            raise ConfigError(f"harness 配置有未知字段：{', '.join(sorted(unknown))}")
        kw: dict[str, Any] = {**(raw.get("loop") or {}), **(raw.get("loop_detection") or {})}
        for k in ("reminders", "context", "tools", "prompts"):
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
        blob = json.dumps({"cfg": self.model_dump(mode="json", exclude={"name"}), "prompts": self.prompt_versions()},
                          sort_keys=True, ensure_ascii=False)  # fmt: skip
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]

    def reminder(self, key: str, **kw: str) -> str:
        defaults = {
            "no_tool": "请调用工具继续，或调用 finish 结束。",
            "wrap_up": "预算已用到警戒线，请尽快收尾。",
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


__all__ = ["DEFAULT_TOOLS", "ContextConfig", "HarnessConfig", "TokenAllocation"]
