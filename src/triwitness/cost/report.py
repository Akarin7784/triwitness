"""从轨迹事件汇总 CostReport（spec 005 §5.3；W1-25 会在此基础上加 CostLedger 实时累加与 PR 账单渲染）。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from triwitness.core.events import TrajectoryEvent
from triwitness.core.models import CostLine, CostReport, Role, Usage, Vendor


@dataclass
class _Acc:
    calls: int = 0
    usage: Usage = field(default_factory=Usage)
    cost: float = 0.0
    peak: int = 0


def cost_report_from_events(
    events: Iterable[TrajectoryEvent],
    *,
    task_id: str,
    budget_cny: float | None = None,
    pricing_version: str,
    sandbox_cost_cny: float = 0.0,
) -> CostReport:
    acc: dict[tuple[Role, Vendor, str], _Acc] = {}
    for e in events:
        if e.kind != "model_call" or e.role is None:
            continue
        p = e.payload
        a = acc.setdefault((e.role, p.get("vendor", "deepseek"), p["model"]), _Acc())
        a.calls += 1
        a.usage = a.usage + Usage.model_validate(p["usage"])
        a.cost += float(p["cost_cny"])
        a.peak += 1 if p.get("peak") else 0
    lines = [
        CostLine(role=r, vendor=v, model=m, calls=a.calls, usage=a.usage, cost_cny=round(a.cost, 6), peak_calls=a.peak)
        for (r, v, m), a in acc.items()
    ]
    return CostReport.from_lines(task_id, lines, budget_cny=budget_cny, pricing_version=pricing_version,
                                 sandbox_cost_cny=sandbox_cost_cny)  # fmt: skip


class CostLedger:
    """订阅轨迹事件、实时累加 model_call（spec 005 §5.3）。`TrajectoryRecorder.subscribe(ledger.observe)`。"""

    def __init__(self, *, task_id: str, pricing_version: str, budget_cny: float | None = None) -> None:
        self.task_id = task_id
        self.budget_cny = budget_cny
        self.pricing_version = pricing_version
        self.events: list[TrajectoryEvent] = []
        self.total_cny = 0.0

    def observe(self, ev: TrajectoryEvent) -> None:
        if ev.kind == "model_call":
            self.events.append(ev)
            self.total_cny += float(ev.payload["cost_cny"])

    def report(self, *, sandbox_cost_cny: float = 0.0) -> CostReport:
        return cost_report_from_events(
            self.events,
            task_id=self.task_id,
            budget_cny=self.budget_cny,
            pricing_version=self.pricing_version,
            sandbox_cost_cny=sandbox_cost_cny,
        )


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}K"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def fmt_cny(c: float) -> str:
    return f"¥{c:.2f}" if c >= 1 else f"¥{c:.3f}"


def render_cost_markdown(rep: CostReport) -> str:
    """PR 成本账单（spec 005 §5.6）。"""
    rows = [
        "### 💰 成本（本地估算，非厂商账单）",
        "| 角色 | 模型 | 调用 | 输入（命中） | 输出 | 费用 |",
        "|---|---|---|---|---|---|",
    ]
    for ln in rep.lines:
        u = ln.usage
        calls = f"{ln.calls}" + (f"（高峰 {ln.peak_calls}）" if ln.peak_calls else "")
        rows.append(f"| {ln.role} | {ln.model} | {calls} | {fmt_tokens(u.input_tokens)}（{u.cache_hit_rate:.0%}） | "
                    f"{fmt_tokens(u.output_tokens)} | {fmt_cny(ln.cost_cny)} |")  # fmt: skip
    if rep.sandbox_cost_cny:
        rows.append(f"| 沙箱 | — | — | — | — | {fmt_cny(rep.sandbox_cost_cny)} |")
    version = rep.pricing_version.removeprefix("deepseek-")
    total = f"**合计 {fmt_cny(rep.total_cny)}**｜缓存命中率 {rep.cache_hit_rate:.0%}"
    rows.append(f"{total}｜价格表版本 {version}")
    return "\n".join(rows) + "\n"
