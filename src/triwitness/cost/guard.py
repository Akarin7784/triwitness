"""单任务安全上限守卫（ADR-0002；spec 003 §2.4）。

0.3.2（Eva 19:14）起不再有 ¥ 上限：只保留防失控的非金钱上限——轮数、墙钟时间、输入 / 未命中输入 / 输出 token 兜底。
调用前 `precheck()`，调用后 `record(usage, cost)`；任一上限触发即抛 BudgetExceeded（limit 指明是哪一项）。
花费仍累加在 `cost_cny` 里，只用于展示。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from triwitness.core.errors import BudgetExceeded
from triwitness.core.models import Budget, Usage


@dataclass
class TaskBudgetGuard:
    budget: Budget = field(default_factory=Budget)
    clock: Callable[[], float] = time.monotonic
    cost_cny: float = 0.0
    usage: Usage = field(default_factory=Usage)
    turns: int = 0
    started: float = field(init=False)
    warned: bool = False

    def __post_init__(self) -> None:
        self.started = self.clock()

    def _usage(self) -> tuple[tuple[str, float, float], ...]:
        b = self.budget
        return (
            ("max_input_tokens", self.usage.input_tokens, b.max_input_tokens),
            ("max_uncached_input_tokens", self.usage.cache_miss_tokens, b.max_uncached_input_tokens),
            ("max_output_tokens", self.usage.output_tokens, b.max_output_tokens),
            ("max_turns", self.turns, b.max_turns),
            ("max_wall_seconds", self.clock() - self.started, b.max_wall_seconds),
        )

    def _check(self) -> None:
        for name, used, cap in self._usage():
            if used >= cap:
                msg = f"单任务安全上限 {name} 已用尽：{used:.4g} / {cap:g}"
                raise BudgetExceeded(msg, limit=name, used=used, cap=cap)

    def precheck(self, estimate_cny: float = 0.0) -> None:
        """调用前：任一安全上限已触发 → 拒绝。`estimate_cny` 只为兼容旧调用方，忽略。"""
        del estimate_cny
        self._check()

    def record(self, usage: Usage, cost_cny: float) -> None:
        self.turns += 1
        self.usage = self.usage + usage
        self.cost_cny += cost_cny
        if not self.warned and any(used >= self.budget.warn_ratio * cap for _, used, cap in self._usage()):
            self.warned = True
        self._check()

    @property
    def should_wrap_up(self) -> bool:
        """任一安全上限用到 warn_ratio：提醒模型收尾（AgentLoop 使用）。"""
        return self.warned
