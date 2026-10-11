"""高峰时段标注与估算（W1-14）。

0.3.2（Eva 19:14）起不再拦截：高峰时段照常启动 / 派发，只在报告里标注“含高峰价（2×）调用”。
估算同时给出空闲价与高峰价，供 `tw eval estimate` 展示。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from triwitness.llm.pricing import is_peak, rates


@dataclass
class PeakGate:
    allow_peak: bool = False
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    started_in_peak: bool = False

    def check_start(self, what: str = "批量任务") -> None:
        """不再拒绝；高峰时段启动只做标注。`allow_peak` 只为兼容旧调用方保留。"""
        del what
        if is_peak(self.now()):
            self.started_in_peak = True

    def may_dispatch(self) -> bool:
        """不再因高峰停止派发；跨入高峰同样只做标注。"""
        if is_peak(self.now()):
            self.started_in_peak = True
        return True

    @property
    def report_flag(self) -> str | None:
        return "本次运行包含高峰时段调用（2× 价）" if self.started_in_peak else None


@dataclass(frozen=True)
class Estimate:
    calls_tasks: int
    off_peak_cny: float
    peak_cny: float
    input_tokens: int
    output_tokens: int


def estimate_run(
    *,
    tasks: int,
    configs: int = 1,
    attempts: int = 1,
    avg_input_tokens: int,
    avg_output_tokens: int,
    cache_hit_rate: float = 0.9,
    model: str = "deepseek-flash",
) -> Estimate:
    """评测花费估算：任务 × 配置 × 尝试 × 每任务平均用量，分别按空闲价与高峰价计。"""
    n = tasks * configs * attempts
    inp, out = n * avg_input_tokens, n * avg_output_tokens
    hit = inp * cache_hit_rate

    def cost(peak: bool) -> float:
        r = rates("deepseek", model, peak=peak)
        return (hit * r.cache_hit + (inp - hit) * r.cache_miss + out * r.output) / 1_000_000

    return Estimate(n, round(cost(False), 4), round(cost(True), 4), inp, out)
