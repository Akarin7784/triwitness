"""W1-25：CostLedger 实时累加、CostReport（AC3）、PR 成本账单 Markdown 快照（AC7）。"""

from __future__ import annotations

from pathlib import Path

from triwitness.core.models import CostLine, CostReport, Usage
from triwitness.cost.report import CostLedger, fmt_tokens, render_cost_markdown
from triwitness.telemetry.trajectory import Trajectory

ROOT = Path(__file__).resolve().parents[3]


def test_ledger_tracks_fixture_events() -> None:
    evs = Trajectory.read_events(ROOT / "evals" / "fixtures" / "events" / "success.jsonl")
    fin = evs[-1].payload["cost_report"]
    led = CostLedger(task_id=evs[0].task_id, budget_cny=0.8, pricing_version=fin["pricing_version"])
    for e in evs:
        led.observe(e)
    rep = led.report()
    total = sum(e.payload["cost_cny"] for e in evs if e.kind == "model_call")
    assert abs(rep.total_cny - total) < 1e-4 and abs(led.total_cny - total) < 1e-9
    assert [ln.role for ln in rep.lines] == ["planner", "executor", "verifier", "reviewer"]
    hit = sum(ln.usage.cache_hit_tokens for ln in rep.lines) / sum(ln.usage.input_tokens for ln in rep.lines)
    assert abs(rep.cache_hit_rate - hit) < 1e-6


def test_fmt_tokens() -> None:
    assert [fmt_tokens(n) for n in (950, 1234, 41_000, 1_600_000)] == ["950", "1.2K", "41K", "1.6M"]


SNAPSHOT = """### 💰 成本（本地估算，非厂商账单）
| 角色 | 模型 | 调用 | 输入（命中） | 输出 | 费用 |
|---|---|---|---|---|---|
| executor | deepseek-flash | 23（高峰 2） | 1.6M（82%） | 41K | ¥1.05 |
| reviewer | deepseek-flash | 1 | 24K（60%） | 1.0K | ¥0.014 |
| 沙箱 | — | — | — | — | ¥0.010 |
**合计 ¥1.07**｜缓存命中率 82%｜价格表版本 2026-10-10
"""


def test_ac7_markdown_snapshot() -> None:
    lines = [
        CostLine(role="executor", vendor="deepseek", model="deepseek-flash", calls=23, peak_calls=2, cost_cny=1.05,
                 usage=Usage(input_tokens=1_600_000, cache_hit_tokens=1_312_000, cache_miss_tokens=288_000,
                             output_tokens=41_000)),
        CostLine(role="reviewer", vendor="deepseek", model="deepseek-flash", calls=1, cost_cny=0.0139,
                 usage=Usage(input_tokens=24_000, cache_hit_tokens=14_400, cache_miss_tokens=9_600,
                             output_tokens=1_000)),
    ]  # fmt: skip
    rep = CostReport.from_lines("t", lines, budget_cny=2.0, pricing_version="deepseek-2026-10-10",
                                sandbox_cost_cny=0.01)  # fmt: skip
    assert render_cost_markdown(rep) == SNAPSHOT
