"""W2-26：Executor 流程默认 repro-first；显式写 baseline.yaml 的 RunConfig 仍是 W2-25 基线。"""

from __future__ import annotations

from pathlib import Path

from triwitness.core.models import Budget
from triwitness.eval.agents import LLMAgent
from triwitness.eval.runner import RunConfig
from triwitness.harness.config import DEFAULT_HARNESS, HarnessConfig
from triwitness.harness.run import run_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

ROOT = Path(__file__).resolve().parents[3]


def test_default_harness_is_repro_first() -> None:
    assert DEFAULT_HARNESS == "harness/repro-first.yaml"
    h = HarnessConfig.default()
    assert h.name == "repro-first"
    assert "submit_repro" in h.tools and h.prompts["executor"] == "executor-repro-first"
    assert "submit_repro" not in HarnessConfig.load().tools  # baseline 不变


def test_w2_26_run_configs_use_repro_first_and_flash() -> None:
    for name in ("w2-26-deepseek.yaml", "w2-26-deepseek-nothink.yaml"):
        cfg = RunConfig.load(ROOT / "configs" / "runs" / name)
        assert cfg.harness == "configs/harness/repro-first.yaml"
        assert cfg.executor["model"] == "deepseek-flash"
        assert cfg.verifier == "deterministic"
    base = RunConfig.load(ROOT / "configs" / "runs" / "baseline-deepseek.yaml")
    assert base.harness == "configs/harness/baseline.yaml"  # W2-25 基线可复跑


async def test_run_task_without_config_runs_repro_first() -> None:
    """不传 config：走 repro-first —— 没复现就 finish 会被拒，状态里有 reproducing。"""
    from .test_repro_first import FIX, REPRO, WRITE_REPRO, finish, handler, states, tool_results

    rec = TrajectoryRecorder("t_d", "r_d")
    sb = FakeSandbox({"calc.py": "def add(a, b):\n    return a - b\n"}, exec_handler=handler)
    script = [say(FIX), say(finish()), say(WRITE_REPRO), say(call("submit_repro", path=REPRO, cmd=f"pytest {REPRO}")),
              say(call("run_tests")), say(finish())]  # fmt: skip
    res = await run_task(recorder=rec, router=FakeRouter(script),
                         registry=ToolRegistry(default_tools(names=HarnessConfig.default().tools)), sandbox=sb,
                         issue_title="add 是减法", task_prompt="修", repo="o/r", budget=Budget(), config_hash="c",
                         issue_number=3, test_command="pytest -q")  # fmt: skip
    started = next(e for e in rec.events if e.kind == "task_started")
    assert started.payload["harness"] == "repro-first"
    assert tool_results(rec, "finish")[0]["ok"] is False
    assert "reproducing" in states(rec) and res.repro_status is not None


def test_llm_agent_without_harness_uses_default() -> None:
    a = LLMAgent(lambda: FakeRouter([]))
    assert a.harness is None  # solve() 时解析为 HarnessConfig.default()
