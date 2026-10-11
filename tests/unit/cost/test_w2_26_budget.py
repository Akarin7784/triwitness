"""W2-26：输入 token 上限“总量 6M 兜底 + 未命中 400K”；0.3.2 起没有 ¥ 上限，轮数 / token 是防失控兜底。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from triwitness.core.errors import BudgetExceeded
from triwitness.core.models import Budget, Usage
from triwitness.cost.guard import TaskBudgetGuard

ROOT = Path(__file__).resolve().parents[3]


def _u(hit: int, miss: int) -> Usage:
    return Usage(input_tokens=hit + miss, cache_hit_tokens=hit, cache_miss_tokens=miss, output_tokens=0)


def test_w2_25_shape_no_longer_trips_input_cap() -> None:
    """W2-25 典型：3M 输入、97% 命中、¥0.3 → 旧上限会停，新上限不停。"""
    g = TaskBudgetGuard(Budget())
    for _ in range(30):
        g.record(_u(97_000, 3_000), 0.01)
    assert g.usage.input_tokens == 3_000_000 and g.cost_cny == pytest.approx(0.3)
    g.precheck(0.0)  # 不抛


def test_uncached_cap_trips_on_cache_misses() -> None:
    g = TaskBudgetGuard(Budget(max_uncached_input_tokens=1_000))
    g.record(_u(10_000, 600), 0.0)
    with pytest.raises(BudgetExceeded) as e:
        g.record(_u(10_000, 600), 0.0)
    assert e.value.limit == "max_uncached_input_tokens"


def test_no_money_cap_turns_backstop_runaway() -> None:
    """0.3.2：高命中长任务不再因 ¥ 停下，失控循环由轮数上限兜住。"""
    g = TaskBudgetGuard(Budget())
    with pytest.raises(BudgetExceeded) as e:
        for _ in range(100):
            g.record(_u(48_500, 1_500), 0.009)
    assert e.value.limit == "max_turns" and g.cost_cny == pytest.approx(0.9)
    assert g.usage.input_tokens < 6_000_000 and g.usage.cache_miss_tokens < 400_000


def test_total_input_cap_still_backstops() -> None:
    g = TaskBudgetGuard(Budget(max_input_tokens=5_000))
    with pytest.raises(BudgetExceeded) as e:
        g.record(_u(5_000, 0), 0.0)
    assert e.value.limit == "max_input_tokens"


def test_budget_yaml_matches_model_defaults() -> None:
    cfg = yaml.safe_load((ROOT / "configs" / "budget.yaml").read_text(encoding="utf-8"))
    ev, b = cfg["per_task"]["eval"], Budget.for_eval()
    assert "max_cost_cny" not in ev and "envelopes_cny" not in cfg and "total_cny" not in cfg
    for k in ("max_input_tokens", "max_uncached_input_tokens", "max_output_tokens", "max_turns"):
        assert ev[k] == getattr(b, k), k
    assert cfg["per_task"]["run"]["max_uncached_input_tokens"] == Budget.for_run().max_uncached_input_tokens
