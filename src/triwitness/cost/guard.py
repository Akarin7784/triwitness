"""单任务预算守卫（ADR-0002；spec 003 §2.4 的五种上限）。

调用前 `precheck(estimate)`，调用后 `record(usage, cost)`；任一上限触发即抛 BudgetExceeded。
回放模式下也按价格表记账（模拟预算行为），但不进全局账本。
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

    def _check(self, *, extra_cost: float = 0.0) -> None:
        b = self.budget
        checks = (
            ("max_cost_cny", self.cost_cny + extra_cost, b.max_cost_cny),
            ("max_input_tokens", self.usage.input_tokens, b.max_input_tokens),
            ("max_output_tokens", self.usage.output_tokens, b.max_output_tokens),
            ("max_turns", self.turns, b.max_turns),
            ("max_wall_seconds", self.clock() - self.started, b.max_wall_seconds),
        )
        for name, used, cap in checks:
            if used >= cap if name != "max_cost_cny" else used > cap:
                raise BudgetExceeded(f"单任务预算 {name} 已用尽：{used:.4g} / {cap:g}", limit=name, used=used, cap=cap)

    def precheck(self, estimate_cny: float = 0.0) -> None:
        """调用前：已花 + 预估 > 上限，或其他上限已触发 → 拒绝。"""
        self._check(extra_cost=estimate_cny)

    def record(self, usage: Usage, cost_cny: float) -> None:
        self.turns += 1
        self.usage = self.usage + usage
        self.cost_cny += cost_cny
        if not self.warned and self.cost_cny >= self.budget.warn_ratio * self.budget.max_cost_cny:
            self.warned = True
        self._check()

    @property
    def should_wrap_up(self) -> bool:
        """达到 warn_ratio：提醒模型收尾（AgentLoop 使用）。"""
        return self.warned
