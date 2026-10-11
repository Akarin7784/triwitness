"""任务状态机（spec 010 §4，04 §3.1，W4-03）：显式、可审计、可重放。

- 合法迁移是一张表（`TRANSITIONS`）；只有编排器调用 `go()` 迁移，角色只返回结构化结果。
- 每次迁移通过注入的 `on_transition` 回调写 `state_change` 事件（core 不依赖 telemetry）。
- `replay()` 按事件顺序重放并逐条校验：续跑 / 审计时重建当前状态，历史里有非法迁移直接报错。
- 评测模式的 AWAIT_* 自动策略：`eval_auto_decision()`。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from triwitness.core.errors import IllegalTransition
from triwitness.core.models import RiskLevel, TaskState

S = TaskState

TERMINAL: frozenset[TaskState] = frozenset({S.DONE, S.NEEDS_HUMAN, S.BUDGET_EXCEEDED, S.FAILED, S.CANCELLED})
# 任一非终态都可以进入的“异常出口”
_ESCAPES: frozenset[TaskState] = frozenset({S.NEEDS_HUMAN, S.BUDGET_EXCEEDED, S.FAILED, S.CANCELLED})

_EDGES: dict[TaskState, frozenset[TaskState]] = {
    S.RECEIVED: frozenset({S.PREPARING}),
    S.PREPARING: frozenset({S.PLANNING, S.REPRODUCING, S.EXECUTING}),
    S.PLANNING: frozenset({S.AWAIT_PLAN_APPROVAL, S.REPRODUCING, S.EXECUTING}),
    S.AWAIT_PLAN_APPROVAL: frozenset({S.REPRODUCING, S.EXECUTING}),
    S.REPRODUCING: frozenset({S.EXECUTING}),
    S.EXECUTING: frozenset({S.VERIFYING, S.REVIEWING, S.PACKAGING}),
    S.VERIFYING: frozenset({S.EXECUTING, S.REVIEWING, S.PACKAGING}),
    S.REVIEWING: frozenset({S.EXECUTING, S.PACKAGING}),
    S.PACKAGING: frozenset({S.AWAIT_PR_APPROVAL, S.PR_OPENED, S.DONE}),
    S.AWAIT_PR_APPROVAL: frozenset({S.PR_OPENED, S.DONE}),
    S.PR_OPENED: frozenset({S.CI_WATCH, S.DONE}),
    S.CI_WATCH: frozenset({S.EXECUTING, S.DONE}),
}

TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    s: (frozenset() if s in TERMINAL else _EDGES.get(s, frozenset()) | _ESCAPES) for s in TaskState
}


def is_legal(src: TaskState, dst: TaskState) -> bool:
    return dst in TRANSITIONS[src]


@dataclass(frozen=True)
class Transition:
    src: TaskState
    dst: TaskState
    display: str = ""


OnTransition = Callable[[Transition], None]


class TaskStateMachine:
    """一个任务的状态。`go()` 校验后迁移并回调（写事件）；`history` 是全部迁移（审计）。"""

    def __init__(self, state: TaskState = S.RECEIVED, *, on_transition: OnTransition | None = None) -> None:
        self.state = state
        self.on_transition = on_transition
        self.history: list[Transition] = []

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL

    def can(self, dst: TaskState) -> bool:
        return is_legal(self.state, dst)

    def go(self, dst: TaskState, display: str = "") -> Transition:
        if not self.can(dst):
            why = (
                "终态不能迁出"
                if self.terminal
                else f"允许：{', '.join(sorted(s.value for s in TRANSITIONS[self.state]))}"
            )
            raise IllegalTransition(f"非法迁移 {self.state.value} → {dst.value}（{why}）")
        t = Transition(self.state, dst, display)
        self.state = dst
        self.history.append(t)
        if self.on_transition is not None:
            self.on_transition(t)
        return t

    @classmethod
    def replay(
        cls, changes: Iterable[tuple[TaskState | str, TaskState | str]], *, on_transition: OnTransition | None = None
    ) -> TaskStateMachine:
        """按顺序重放 (from, to)：每条的 from 必须等于当前状态且迁移合法；返回的状态机不回调（重放不重写事件）。"""
        sm = cls()
        for i, (a, b) in enumerate(changes):
            src, dst = TaskState(a), TaskState(b)
            if src != sm.state:
                raise IllegalTransition(f"第 {i + 1} 条迁移的起点 {src.value} 与当前状态 {sm.state.value} 不一致")
            sm.go(dst)
        sm.on_transition = on_transition
        return sm


Decision = Literal["approve", "reject"]
_ORDER: dict[str, int] = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def risk_at_least(level: RiskLevel | str, floor: RiskLevel | str) -> bool:
    return _ORDER[str(level)] >= _ORDER[str(floor)]


def eval_auto_decision(risk: RiskLevel | str, *, reject_from: RiskLevel = "L3") -> Decision:
    """评测模式的 AWAIT_* 自动策略（04 §3.1；spec 010 §11 Q2）：默认 L0–L2 批准、L3 拒绝。"""
    return "reject" if risk_at_least(risk, reject_from) else "approve"


__all__ = [
    "TERMINAL",
    "TRANSITIONS",
    "Decision",
    "TaskStateMachine",
    "Transition",
    "eval_auto_decision",
    "is_legal",
    "risk_at_least",
]
