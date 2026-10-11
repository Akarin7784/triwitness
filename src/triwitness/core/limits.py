"""窗口与由此推导的上限：纯计算（Eva 2026-10-11：核心架构面向约 1M 上下文的模型）。

读 configs/models.yaml 的部分在 `triwitness.llm.limits`（core 不依赖 triwitness 其他包）。
- 输入硬上限 = 窗口 − 本角色单次输出预留 − 3% 估算余量（DeepSeek：输入 + 生成 ≤ 上下文长度）。
  deepseek-flash 的 Executor：1,048,576 − 65,536 − 31,458 = 951,582（约 950K）= `DEFAULT_WORKING_BUDGET`。
- 单任务防失控上限（非金钱）由工作预算推导，见 `runaway_limits()`。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SAFETY_SHARE = 0.03  # 估算误差余量（字符估算 / 真实 tokenizer 偏差；1M 下 3% ≈ 3 万 token）
INPUT_SHARE_PER_TURN = 0.63  # 累计输入兜底：平均每轮按工作预算的 63% 算（只追加 + 批量清理的锯齿均值）
UNCACHED_WINDOWS = 3  # 未命中兜底：允许约 3 次整段重新预填充（清理 / 压缩会让改写点之后全部未命中）
DEFAULT_MAX_TURNS = 100


@dataclass(frozen=True)
class ModelLimits:
    context_window: int
    max_output: int


FALLBACK = ModelLimits(context_window=1_048_576, max_output=393_216)  # deepseek-flash（2026-10-11 官方价格页）
FALLBACK_ROLE_OUTPUT = 65_536  # DeepSeek 思考模式不传 max_tokens 时的默认值；Executor 显式传这个值


def hard_limit_for(context_window: int, output_reserve: int) -> int:
    """单次请求输入的硬上限：窗口 − 输出预留 − 余量。"""
    return context_window - output_reserve - math.ceil(context_window * SAFETY_SHARE)


DEFAULT_WORKING_BUDGET = hard_limit_for(FALLBACK.context_window, FALLBACK_ROLE_OUTPUT)  # 951,582


def runaway_limits(working_budget: int | None = None, max_turns: int = DEFAULT_MAX_TURNS) -> tuple[int, int]:
    """(累计输入兜底, 未命中兜底)，由工作预算推导；951,582 → 59,949,666（≈60M）/ 2,854,746（≈2.85M）。"""
    wb = working_budget or DEFAULT_WORKING_BUDGET
    return int(max_turns * wb * INPUT_SHARE_PER_TURN), int(UNCACHED_WINDOWS * wb)


__all__ = [
    "DEFAULT_WORKING_BUDGET",
    "FALLBACK",
    "FALLBACK_ROLE_OUTPUT",
    "SAFETY_SHARE",
    "ModelLimits",
    "hard_limit_for",
    "runaway_limits",
]
