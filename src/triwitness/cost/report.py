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
    budget_cny: float,
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
