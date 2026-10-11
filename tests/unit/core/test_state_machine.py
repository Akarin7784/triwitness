"""spec 010 §4 / AC1：显式状态机——每条合法迁移、非法迁移、终态、重放、评测自动策略。"""

from __future__ import annotations

import pytest

from triwitness.core.errors import IllegalTransition
from triwitness.core.models import TaskState as S
from triwitness.core.state_machine import (
    TERMINAL,
    TRANSITIONS,
    TaskStateMachine,
    Transition,
    eval_auto_decision,
    is_legal,
)

LEGAL = [(a, b) for a, bs in TRANSITIONS.items() for b in bs]


@pytest.mark.parametrize(("src", "dst"), LEGAL, ids=[f"{a.value}->{b.value}" for a, b in LEGAL])
def test_every_legal_transition(src: S, dst: S) -> None:
    seen: list[Transition] = []
    sm = TaskStateMachine(src, on_transition=seen.append)
    sm.go(dst, "x")
    assert sm.state == dst and seen == [Transition(src, dst, "x")] and sm.history == seen


def test_design_doc_edges_present() -> None:
    """04 §3.1 的迁移都在表里。"""
    for a, b in [(S.RECEIVED, S.PREPARING), (S.PREPARING, S.NEEDS_HUMAN), (S.PLANNING, S.AWAIT_PLAN_APPROVAL),
                 (S.AWAIT_PLAN_APPROVAL, S.REPRODUCING), (S.AWAIT_PLAN_APPROVAL, S.CANCELLED),
                 (S.PLANNING, S.REPRODUCING), (S.REPRODUCING, S.EXECUTING), (S.REPRODUCING, S.NEEDS_HUMAN),
                 (S.EXECUTING, S.VERIFYING), (S.VERIFYING, S.EXECUTING), (S.VERIFYING, S.REVIEWING),
                 (S.REVIEWING, S.EXECUTING), (S.REVIEWING, S.PACKAGING), (S.PACKAGING, S.AWAIT_PR_APPROVAL),
                 (S.PACKAGING, S.PR_OPENED), (S.AWAIT_PR_APPROVAL, S.PR_OPENED), (S.PR_OPENED, S.CI_WATCH),
                 (S.CI_WATCH, S.EXECUTING), (S.CI_WATCH, S.DONE), (S.EXECUTING, S.BUDGET_EXCEEDED),
                 (S.EXECUTING, S.NEEDS_HUMAN)]:  # fmt: skip
        assert is_legal(a, b), (a, b)


@pytest.mark.parametrize(
    ("src", "dst"),
    [(S.RECEIVED, S.EXECUTING), (S.PREPARING, S.VERIFYING), (S.EXECUTING, S.DONE), (S.PLANNING, S.REVIEWING),
     (S.REVIEWING, S.VERIFYING), (S.EXECUTING, S.EXECUTING), (S.REPRODUCING, S.PLANNING), (S.VERIFYING, S.DONE)],
)  # fmt: skip
def test_illegal_transition_raises(src: S, dst: S) -> None:
    sm = TaskStateMachine(src)
    with pytest.raises(IllegalTransition, match="非法迁移"):
        sm.go(dst)
    assert sm.state == src and sm.history == []


@pytest.mark.parametrize("term", sorted(TERMINAL))
def test_terminal_states_have_no_exit(term: S) -> None:
    sm = TaskStateMachine(term)
    assert sm.terminal and TRANSITIONS[term] == frozenset()
    for dst in S:
        with pytest.raises(IllegalTransition, match="终态"):
            sm.go(dst)


def test_any_live_state_can_escape() -> None:
    for s in S:
        if s in TERMINAL:
            continue
        for esc in (S.NEEDS_HUMAN, S.BUDGET_EXCEEDED, S.FAILED, S.CANCELLED):
            assert is_legal(s, esc), (s, esc)


def test_replay_rebuilds_state_without_callbacks() -> None:
    path = [("received", "preparing"), ("preparing", "planning"), ("planning", "reproducing"),
            ("reproducing", "executing"), ("executing", "verifying"), ("verifying", "reviewing"),
            ("reviewing", "executing")]  # fmt: skip
    seen: list[Transition] = []
    sm = TaskStateMachine.replay(path, on_transition=seen.append)
    assert sm.state == S.EXECUTING and len(sm.history) == 7 and seen == []
    sm.go(S.VERIFYING)  # 重放后接着走才回调
    assert [t.dst for t in seen] == [S.VERIFYING]


def test_replay_rejects_illegal_or_inconsistent_history() -> None:
    with pytest.raises(IllegalTransition):
        TaskStateMachine.replay([("received", "preparing"), ("preparing", "done")])
    with pytest.raises(IllegalTransition, match="起点"):
        TaskStateMachine.replay([("received", "preparing"), ("planning", "executing")])


@pytest.mark.parametrize("risk", ["L0", "L1", "L2", "L3"])
def test_eval_auto_decision_default(risk: str) -> None:
    """Eva 2026-10-11 21:36：评测里计划全部自动批准（含 L3）。"""
    assert eval_auto_decision(risk) == "approve"


def test_eval_auto_decision_configurable() -> None:
    assert eval_auto_decision("L2", reject_from="L2") == "reject"
    assert eval_auto_decision("L1", reject_from="L2") == "approve"
    assert eval_auto_decision("L3", reject_from="L3") == "reject"
