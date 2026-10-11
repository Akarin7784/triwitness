import json
from pathlib import Path

import pytest

from triwitness.core.errors import BudgetExceeded
from triwitness.core.models import Budget, Usage
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.cost.ledger import GlobalLedger
from triwitness.llm import cases

from ..llm.helpers import FIXTURES, WED_PEAK, CannedTransport, client_with, replay_client

U = Usage(input_tokens=1000, cache_hit_tokens=900, cache_miss_tokens=100, output_tokens=50)


def _raw(name: str = "text_nonthinking") -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["response"]


# ---------------------------------------------------------------- 单任务守卫


def test_guard_has_no_money_cap_but_warns_on_turns() -> None:
    """0.3.2：没有 ¥ 上限（旧配置的 max_cost_cny 读入后忽略）；收尾提醒按非金钱上限的 warn_ratio。"""
    g = TaskBudgetGuard(Budget(max_cost_cny=0.01, max_turns=10))
    for _ in range(7):
        g.record(U, 5.0)
    g.precheck(100.0)  # 花多少都不拦
    assert g.cost_cny == pytest.approx(35.0) and not g.should_wrap_up
    g.record(U, 0)
    assert g.should_wrap_up  # 8 / 10 轮 = warn_ratio
    with pytest.raises(BudgetExceeded) as e:
        g.record(U, 0)
        g.record(U, 0)
    assert e.value.limit == "max_turns"


def test_guard_turns_tokens_wall() -> None:
    g = TaskBudgetGuard(Budget(max_turns=2))
    g.record(U, 0)
    with pytest.raises(BudgetExceeded):
        g.record(U, 0)
    g = TaskBudgetGuard(Budget(max_input_tokens=1500))
    g.record(U, 0)
    with pytest.raises(BudgetExceeded):
        g.record(U, 0)
    t = [0.0]
    g = TaskBudgetGuard(Budget(max_wall_seconds=10), clock=lambda: t[0])
    t[0] = 11
    with pytest.raises(BudgetExceeded):
        g.precheck()


# ---------------------------------------------------------------- 全局账本


def _ledger(tmp_path: Path) -> GlobalLedger:
    return GlobalLedger(tmp_path / "l.sqlite")


def test_ledger_is_usage_log_only(tmp_path: Path) -> None:
    """0.3.2：账本只记录，没有总额 / 信封 / 预检。"""
    lg = _ledger(tmp_path)
    assert not hasattr(lg, "precheck") and not hasattr(lg, "envelopes") and not hasattr(lg, "total_cny")
    lg.record(category="dev", model="deepseek-flash", usage=U, cost_cny=0.45, peak=False, pricing_version="v")
    lg.record(category="smoke", model="deepseek-flash", usage=U, cost_cny=150.0, peak=True, pricing_version="v")
    s = lg.summary()
    assert (s.calls, s.peak_calls, round(s.total_cny, 2)) == (2, 1, 150.45)
    assert s.cache_hit_rate == pytest.approx(0.9) and lg.spent("dev") == pytest.approx(0.45)


def test_breakdown(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    lg = _ledger(tmp_path)
    at = datetime(2026, 10, 11, 15, 30, tzinfo=UTC)  # 北京时间 10-11 23:30（周日，W41）
    lg.record(category="dev", model="deepseek-flash", usage=U, cost_cny=0.1, peak=False, pricing_version="v", at=at)
    lg.record(category="smoke", model="deepseek-flash", usage=U, cost_cny=0.2, peak=True, pricing_version="v", at=at)
    assert lg.breakdown("category") == {"dev": 0.1, "smoke": 0.2}
    assert lg.breakdown("model") == {"deepseek-flash": pytest.approx(0.3)}
    assert lg.breakdown("week") == {"2026-W41": pytest.approx(0.3)}
    assert lg.breakdown("peak") == {"off_peak": 0.1, "peak": 0.2}


# ---------------------------------------------------------------- 组合：LLMClient 护栏链


async def test_peak_hours_no_longer_block_and_are_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """0.3.2：高峰时段不拦（STOP / TW_KILL_SWITCH 也不拦），照常计价并在账本里标注高峰。"""
    monkeypatch.setenv("TW_KILL_SWITCH", "1")
    (tmp_path / "STOP").touch()
    inner = CannedTransport(_raw())
    lg = _ledger(tmp_path)
    c, _ = client_with(inner, "record", tmp_path, now=WED_PEAK, ledger=lg)
    r = await c.complete(cases.text_nonthinking(), cases.MODEL)
    assert r.peak is True and lg.summary().peak_calls == 1


async def test_replay_is_free_even_in_peak() -> None:
    c = replay_client()
    c.now = lambda: WED_PEAK
    r = await c.complete(cases.text_nonthinking(), cases.MODEL)
    assert r.source == "replay" and r.peak is True  # 回放不花钱，闸门不拦；计价仍按调用时刻


async def test_live_call_recorded_in_ledger_with_cost(tmp_path: Path) -> None:
    inner = CannedTransport(_raw("cache_prefix_2"))
    lg = _ledger(tmp_path)
    c, _ = client_with(inner, "live", tmp_path, ledger=lg)
    r = await c.complete(cases.cache_prefix(cases.CACHE_Q2), cases.MODEL, category="smoke")
    s = lg.summary()
    assert s.calls == 1 and s.total_cny == pytest.approx(r.cost_cny) and r.cost_cny > 0
    assert s.cache_hit_tokens == r.usage.cache_hit_tokens


async def test_task_guard_counts_cost_for_display_and_stops_on_turns() -> None:
    c = replay_client()
    g = TaskBudgetGuard(Budget(max_turns=2))
    await c.complete(cases.cache_prefix(cases.CACHE_Q1), cases.MODEL, guard=g)  # ≈ ¥0.0035
    assert g.cost_cny == pytest.approx(0.003527, rel=1e-3) and not g.should_wrap_up
    with pytest.raises(BudgetExceeded) as e:
        await c.complete(cases.cache_prefix(cases.CACHE_Q1), cases.MODEL, guard=g)
    assert e.value.limit == "max_turns"
