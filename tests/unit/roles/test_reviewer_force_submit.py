"""W4-14 后续（Eva 2026-10-12 01:01）：评审最后一次调用强制提交；上限那次调用也写轨迹（账本缺口）。

FakeRouter + FakeSandbox，不调用模型。
"""

from __future__ import annotations

from typing import Any

from triwitness.core.models import Budget
from triwitness.harness.config import HarnessConfig
from triwitness.harness.loop import AgentLoop
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.llm.types import Message
from triwitness.roles.common import read_only_registry
from triwitness.roles.contracts import submit_review_tool
from triwitness.roles.reviewer import ReviewInput, run_variant
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools.base import ToolContext

READ = say(call("read_file", path="calc.py"))
SUBMIT = say(call("submit_review", verdict="approve", summary="没问题", findings=[]))


def _cfg(max_turns: int, *, force: bool = True) -> HarnessConfig:
    c = HarnessConfig.load("harness/orchestrated-1m.yaml")
    c.orchestration.reviewer.max_turns = max_turns
    c.orchestration.reviewer.force_submit = force
    return c


def _ctx() -> ToolContext:
    return ToolContext(sandbox=FakeSandbox({"calc.py": "def add(a, b):\n    return a + b\n"}), task_id="t", run_id="r")


async def _review(script: list[Message], cfg: HarnessConfig, tmp: Any, variant: str = "checklist") -> Any:
    router = FakeRouter(script)
    rec = TrajectoryRecorder("t", "r", run_dir=tmp / "run")
    vr = await run_variant(variant, ReviewInput(issue="add 应该是加法", diff="--- a/calc.py\n+++ b/calc.py\n"),  # type: ignore[arg-type]
                           router=router, rec=rec, ctx=_ctx(), cfg=cfg, budget=Budget())  # fmt: skip
    return vr, router, rec


async def test_final_turn_forces_submit_without_thinking(tmp_path: Any) -> None:
    vr, router, rec = await _review([READ, READ, SUBMIT], _cfg(3), tmp_path)
    assert vr.review is not None and vr.review.verdict == "approve"
    early, last = router.requests[:2], router.requests[2]
    assert all(r.tool_choice == "auto" for r in early)
    assert last.tool_choice == {"type": "function", "function": {"name": "submit_review"}}
    assert last.thinking_override is False and last.temperature is None  # 强制工具必须关思考（DeepSeek 400）
    assert "最后一次调用" in (last.messages[-1].content or "")
    # 前两次 checklist 变体：非思考 t=1.0
    assert early[0].thinking_override is False and early[0].temperature == 1.0
    # 3 次调用全部写进轨迹（含触发上限的那次）
    assert sum(1 for e in rec.events if e.kind == "model_call") == 3


async def test_force_also_for_thinking_variant(tmp_path: Any) -> None:
    """adversarial（思考）在最后一次调用也关思考强制提交；之前沿用路由的思考配置。"""
    _, router, _ = await _review([READ, SUBMIT], _cfg(2), tmp_path, variant="adversarial")
    assert router.requests[0].thinking_override is None and router.requests[0].tool_choice == "auto"
    assert router.requests[1].thinking_override is False and router.requests[1].tool_choice != "auto"


async def test_no_force_when_disabled_keeps_protocol(tmp_path: Any) -> None:
    """消融脚本关掉 force_submit（与第一轮协议一致）：最后一次也是 auto。"""
    vr, router, rec = await _review([READ, READ], _cfg(2, force=False), tmp_path)
    assert vr.review is None and all(r.tool_choice == "auto" for r in router.requests)
    assert sum(1 for e in rec.events if e.kind == "model_call") == 2


async def test_submission_on_capped_call_is_kept_and_billed(tmp_path: Any) -> None:
    """第 N 次（= max_turns）调用里提交：以前记账后抛 BudgetExceeded，回复和提交都丢了（W4-14 的 ¥0.14 缺口）。"""
    router = FakeRouter([READ, SUBMIT], cost_cny=0.01)
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path / "run")
    loop = AgentLoop(router, read_only_registry(submit_review_tool()), system_prompt="评审", emitter=rec,
                     budget=Budget().model_copy(update={"max_turns": 2}), config=HarnessConfig.load(),
                     role="reviewer")  # fmt: skip
    out = await loop.run("评审", _ctx())
    assert out.status == "finished" and out.submission is not None
    calls = [e for e in rec.events if e.kind == "model_call"]
    assert len(calls) == 2 and sum(float(e.payload["cost_cny"]) for e in calls) == 0.02
    assert [e.payload["tool"] for e in rec.events if e.kind == "tool_call"] == ["read_file", "submit_review"]


async def test_capped_call_without_submit_still_recorded(tmp_path: Any) -> None:
    router = FakeRouter([READ, READ], cost_cny=0.01)
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path / "run")
    loop = AgentLoop(router, read_only_registry(submit_review_tool()), system_prompt="评审", emitter=rec,
                     budget=Budget().model_copy(update={"max_turns": 2}), config=HarnessConfig.load(),
                     role="reviewer")  # fmt: skip
    out = await loop.run("评审", _ctx())
    assert out.status == "budget_exhausted" and out.steps == 2
    assert sum(1 for e in rec.events if e.kind == "model_call") == 2
    # 超限那次回复里的工具调用没执行，补了“未执行”结果，历史仍合法
    assert loop.messages[-1].role == "tool" and "未执行" in (loop.messages[-1].content or "")
