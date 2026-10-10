"""批量 / 评测层的空闲闸门（W1-14 剩余部分）。调用级闸门在 LLMClient.check_peak_gate。

- 启动：高峰时段拒绝启动 eval / 批量 / 录制 / dogfooding（allow_peak 需显式确认，并在报告标注）。
- 运行中：跨入高峰后不再派发新任务；已在跑的任务允许完成（任务内的调用由 run 级别的 allow_in_flight 放行）。
- 估算：同时给出空闲价与高峰价，供 `tw eval estimate` 展示。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from triwitness.core.errors import PeakHourBlocked
from triwitness.llm.pricing import is_peak, next_off_peak, rates, to_shanghai


@dataclass
class PeakGate:
    allow_peak: bool = False
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    started_in_peak: bool = False

    def check_start(self, what: str = "批量任务") -> None:
        at = self.now()
        if is_peak(at):
            if not self.allow_peak:
                raise PeakHourBlocked(
                    f"{what}在 DeepSeek 高峰时段（北京时间 {to_shanghai(at):%m-%d %H:%M}）拒绝启动；"
                    f"下一个空闲时刻约 {next_off_peak(at):%m-%d %H:%M}。确需运行请加 --allow-peak（报告会标注）"
                )
            self.started_in_peak = True

    def may_dispatch(self) -> bool:
        """派发下一个任务前调用：跨入高峰（且未显式允许）就停止派发。"""
        return self.allow_peak or not is_peak(self.now())

    @property
    def report_flag(self) -> str | None:
        return "allow_peak：本次运行包含高峰时段调用（2× 价）" if self.started_in_peak else None


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
