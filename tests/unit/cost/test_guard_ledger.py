import json
from pathlib import Path

import pytest

from triwitness.core.errors import BudgetExceeded, PeakHourBlocked
from triwitness.core.models import Budget, Usage
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.cost.ledger import GlobalLedger, KillSwitchEngaged
from triwitness.llm import cases

from ..llm.helpers import FIXTURES, WED_PEAK, CannedTransport, client_with, replay_client

U = Usage(input_tokens=1000, cache_hit_tokens=900, cache_miss_tokens=100, output_tokens=50)


def _raw(name: str = "text_nonthinking") -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["response"]


# ---------------------------------------------------------------- 单任务守卫


def test_guard_cost_cap_and_warn() -> None:
    g = TaskBudgetGuard(Budget(max_cost_cny=0.01))
    g.record(U, 0.0085)
    assert g.should_wrap_up
    with pytest.raises(BudgetExceeded) as e:
        g.precheck(0.002)
    assert e.value.limit == "max_cost_cny"


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


def _ledger(tmp_path: Path, **kw) -> GlobalLedger:
    return GlobalLedger(tmp_path / "l.sqlite", stop_file=tmp_path / "STOP", **kw)


def test_ledger_defaults_from_budget_yaml(tmp_path: Path) -> None:
    lg = _ledger(tmp_path)
    assert lg.total_cny == 100 and lg.envelopes["dev"] == 6


def test_ledger_total_envelope_and_record(tmp_path: Path) -> None:
    lg = _ledger(tmp_path, total_cny=1.0, envelopes={"dev": 0.5})
    lg.record(category="dev", model="deepseek-flash", usage=U, cost_cny=0.45, peak=False, pricing_version="v")
    with pytest.raises(BudgetExceeded) as e:
        lg.precheck(0.1, "dev")
    assert e.value.limit == "envelope:dev"
    lg.precheck(0.1, "smoke")
    lg.record(category="smoke", model="deepseek-flash", usage=U, cost_cny=0.5, peak=True, pricing_version="v")
    with pytest.raises(BudgetExceeded) as e:
        lg.precheck(0.1, "smoke")
    assert e.value.limit == "total_cny"
    s = lg.summary()
    assert (s.calls, s.peak_calls, round(s.total_cny, 2)) == (2, 1, 0.95)
    assert s.cache_hit_rate == pytest.approx(0.9) and lg.warn


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


def test_kill_switch_file_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lg = _ledger(tmp_path)
    (tmp_path / "STOP").touch()
    with pytest.raises(KillSwitchEngaged):
        lg.precheck(0.0, "dev")
    (tmp_path / "STOP").unlink()
    monkeypatch.setenv("TW_KILL_SWITCH", "1")
    with pytest.raises(KillSwitchEngaged):
        lg.precheck(0.0, "dev")


# ---------------------------------------------------------------- 组合：LLMClient 护栏链


async def test_peak_gate_blocks_live_before_network(tmp_path: Path) -> None:
    inner = CannedTransport(_raw())
    c, _ = client_with(inner, "record", tmp_path, now=WED_PEAK, ledger=_ledger(tmp_path))
    with pytest.raises(PeakHourBlocked):
        await c.complete(cases.text_nonthinking(), cases.MODEL)
    assert inner.calls == 0


async def test_peak_gate_can_be_overridden(tmp_path: Path) -> None:
    inner = CannedTransport(_raw())
    lg = _ledger(tmp_path)
    c, _ = client_with(inner, "live", tmp_path, now=WED_PEAK, ledger=lg, allow_peak=True)
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


async def test_budget_precheck_refuses_before_network(tmp_path: Path) -> None:
    inner = CannedTransport(_raw())
    c, _ = client_with(inner, "live", tmp_path, ledger=_ledger(tmp_path, total_cny=0.00001))
    with pytest.raises(BudgetExceeded):
        await c.complete(cases.text_nonthinking(), cases.MODEL)
    assert inner.calls == 0


async def test_task_guard_counts_replayed_cost_and_stops() -> None:
    c = replay_client()
    g = TaskBudgetGuard(Budget(max_cost_cny=0.004))
    await c.complete(cases.cache_prefix(cases.CACHE_Q1), cases.MODEL, guard=g)  # ≈ ¥0.0035
    assert g.cost_cny == pytest.approx(0.003527, rel=1e-3) and g.should_wrap_up
    with pytest.raises(BudgetExceeded):
        g.record(U, 0.001)
