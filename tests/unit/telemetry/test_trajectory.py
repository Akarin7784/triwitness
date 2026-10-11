"""W1-24 TrajectoryRecorder / Trajectory.load / run_task：spec 005 AC1、AC2（AC3 的汇总部分）。"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from triwitness.core.events import DISPLAY_MAX, StateChangePayload, parse_event_line
from triwitness.core.models import Budget
from triwitness.harness.loop import AgentLoop
from triwitness.harness.run import run_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.sandbox.base import ExecResult
from triwitness.telemetry.trajectory import Trajectory, TrajectoryRecorder
from triwitness.tools import ToolContext, ToolRegistry, default_tools

FIN = {"summary": "修复", "changes": [{"path": "a.py", "kind": "modified"}], "tests_passed": True, "confidence": 0.9}
PASS = "3 passed in 0.1s"
SECRET = "sk-test0123456789abcdef0123456789"


def ok_exec(cmd: str, sb: FakeSandbox) -> ExecResult:
    return ExecResult(exit_code=0, stdout=PASS if "pytest" in cmd else f"out {SECRET}", stderr="", duration_ms=1,
                      timed_out=False)  # fmt: skip


def five_steps() -> list:  # type: ignore[type-arg]
    return [
        say(call("read_file", path="a.py"), text="读代码"),
        say(call("bash", command="cat a.py"), text="看看"),
        say(call("edit_file", path="a.py", old_str="x = 1", new_str="x = 2")),
        say(call("run_tests")),
        say(call("finish", **FIN), text="完成"),
    ]


async def test_ac1_seq_kinds_and_rebuild(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t_1", "r_1", run_dir=tmp_path / "run")
    loop = AgentLoop(FakeRouter(five_steps()), ToolRegistry(default_tools()), system_prompt="s", budget=Budget(),
                     emitter=rec)  # fmt: skip
    clean = lambda c, sb: ExecResult(exit_code=0, stdout=PASS, stderr="", duration_ms=1, timed_out=False)  # noqa: E731
    out = await loop.run("修 bug", ToolContext(sandbox=FakeSandbox({"a.py": "x = 1\n"}, exec_handler=clean),
                                               test_command="pytest -q"))  # fmt: skip
    assert out.status == "finished" and out.steps == 5
    traj = Trajectory.load(tmp_path / "run" / "trajectory.jsonl")
    assert [e.seq for e in traj.events] == list(range(10))
    assert [e.kind for e in traj.events] == ["model_call", "tool_call"] * 5
    assert traj.messages == loop.messages
    mc = traj.events[0].payload
    assert mc["request_ref"] == "artifacts/0-request.json" and mc["response_ref"] == "artifacts/0-response.json"
    assert traj.events[1].payload["output_ref"] == "artifacts/1-output.txt"
    assert all(e.payload["role_hint"] == "executor" for e in traj.events)
    assert traj.events[0].payload["display"] == "读代码"
    assert traj.events[1].payload["display"] == "$ read_file a.py"


async def test_secrets_redacted_everywhere(tmp_path: Path) -> None:
    run = tmp_path / "run"
    rec = TrajectoryRecorder("t", "r", run_dir=run)
    script = [say(call("bash", command=f"echo {SECRET}"), text=f"key {SECRET}"), say(call("finish", **FIN))]
    loop = AgentLoop(FakeRouter(script), ToolRegistry(default_tools()), system_prompt="s", budget=Budget(),
                     emitter=rec)  # fmt: skip
    await loop.run(f"task {SECRET}", ToolContext(sandbox=FakeSandbox(exec_handler=ok_exec)))
    for f in run.rglob("*"):
        if f.is_file():
            assert SECRET not in f.read_text(encoding="utf-8"), f.name


def test_display_trimmed_and_role_hint(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r")
    shown = f"第一行\n  第二行 TOKEN={SECRET}"
    ev = rec.emit(StateChangePayload.model_validate({"from": "received", "to": "preparing", "display": shown}))
    assert ev.payload["display"] == "第一行 第二行 TOKEN=***" and ev.payload["role_hint"] == "system"
    assert len(ev.payload["display"]) <= DISPLAY_MAX


def test_resume_continues_seq(tmp_path: Path) -> None:
    p = StateChangePayload.model_validate({"from": "received", "to": "preparing"})
    r1 = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    r1.emit(p)
    r1.emit(p)
    r2 = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    assert r2.emit(p).seq == 2
    assert [e.seq for e in Trajectory.read_events(tmp_path / "trajectory.jsonl")] == [0, 1, 2]


def test_partial_last_line_ignored(tmp_path: Path) -> None:
    rec = TrajectoryRecorder("t", "r", run_dir=tmp_path)
    rec.emit(StateChangePayload.model_validate({"from": "received", "to": "preparing"}))
    with (tmp_path / "trajectory.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"v":1,"seq":1,"ts":"2026-')
    traj = Trajectory.load(tmp_path / "trajectory.jsonl")
    assert len(traj.events) == 1 and traj.truncated_tail


def test_ac2_killed_at_step_3(tmp_path: Path) -> None:
    run = tmp_path / "run"
    script = textwrap.dedent(f"""
        import asyncio, os
        from pathlib import Path
        from triwitness.core.models import Budget
        from triwitness.harness.loop import AgentLoop
        from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
        from triwitness.sandbox.base import ExecResult
        from triwitness.telemetry.trajectory import TrajectoryRecorder
        from triwitness.tools import ToolContext, ToolRegistry, default_tools
        n = 0
        def h(cmd, sb):
            global n
            n += 1
            if n == 3:
                os._exit(137)  # 模拟第 3 步时进程被杀
            return ExecResult(exit_code=0, stdout="ok", stderr="", duration_ms=1, timed_out=False)
        rec = TrajectoryRecorder("t", "r", run_dir=Path({str(run)!r}), fsync=True)
        loop = AgentLoop(FakeRouter([say(call("bash", command=f"echo {{i}}")) for i in range(5)]),
                         ToolRegistry(default_tools()), system_prompt="s", budget=Budget(), emitter=rec)
        asyncio.run(loop.run("x", ToolContext(sandbox=FakeSandbox(exec_handler=h))))
    """)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 137, r.stderr
    lines = (run / "trajectory.jsonl").read_text(encoding="utf-8").splitlines()
    events = [parse_event_line(ln) for ln in lines]  # 每行都是合法事件
    assert [e.kind for e in events][:4] == ["model_call", "tool_call", "model_call", "tool_call"]
    assert events[-1].kind == "model_call" and len(events) == 5


# ------------------------------------------------------------------ run_task
def _tick() -> object:
    t = [datetime(2026, 10, 10, 13, 0, tzinfo=UTC)]

    def now() -> datetime:
        t[0] += timedelta(seconds=1)
        return t[0]

    return now


async def _run(script: list, *, budget: Budget | None = None, exec_handler=ok_exec, cost: float = 0.001):  # type: ignore[no-untyped-def, type-arg]
    rec = TrajectoryRecorder("t_9", "r_9", clock=_tick())  # type: ignore[arg-type]
    sb = FakeSandbox({"a.py": "x = 1\n"}, exec_handler=exec_handler)
    res = await run_task(recorder=rec, router=FakeRouter(script, cost_cny=cost), registry=ToolRegistry(default_tools()),
                         sandbox=sb, issue_title="bug", task_prompt="修", repo="o/r", budget=budget or Budget(),
                         config_hash="c", issue_number=3, test_command="pytest -q")  # fmt: skip
    return res, rec


def _assert_contract(rec: TrajectoryRecorder) -> None:
    """与 golden fixture 相同的约束（tests/unit/core/test_event_fixtures.py）。"""
    evs = rec.events
    assert [e.seq for e in evs] == list(range(len(evs)))
    assert evs[0].kind == "task_started" and evs[-1].kind == "task_finished"
    assert [e.ts for e in evs] == sorted(e.ts for e in evs)
    for e in evs:
        p = e.typed_payload()
        assert p.role_hint is not None and (p.display is None or len(p.display) <= DISPLAY_MAX)
        if e.kind == "model_call":
            assert e.payload["model"] == "deepseek-flash"
    json.dumps([e.model_dump(mode="json") for e in evs])


async def test_run_task_done_with_diff_and_cost() -> None:
    res, rec = await _run(five_steps())
    _assert_contract(rec)
    assert res.status == "done" and "+x = 2" in res.diff
    kinds = rec.kinds()
    assert kinds[:4] == ["task_started", "state_change", "checkpoint", "state_change"]
    assert kinds[-4:] == ["checkpoint", "state_change", "state_change", "task_finished"]
    fin = rec.events[-1].payload
    assert fin["status"] == "done" and fin["finish_report"]["summary"] == "修复"
    total = sum(e.payload["cost_cny"] for e in rec.events if e.kind == "model_call")
    assert abs(fin["cost_report"]["total_cny"] - total) < 1e-4
    assert fin["cost_report"]["lines"][0]["calls"] == 5
    assert rec.events[0].payload["display"] == "Issue #3 · bug"


async def test_run_task_honest_failure() -> None:
    res, rec = await _run([say(call("finish", **{**FIN, "tests_passed": False}))])
    assert res.status == "failed" and rec.events[-2].payload["to"] == "failed"
    _assert_contract(rec)


async def test_run_task_budget_exceeded() -> None:
    res, rec = await _run([say(call("read_file", path="a.py"))] * 3, budget=Budget(max_turns=1), cost=0.02)
    assert res.status == "budget_exceeded"
    assert "error" in rec.kinds() and rec.events[-2].payload["to"] == "budget_exceeded"
    _assert_contract(rec)


async def test_run_task_stuck() -> None:
    res, rec = await _run([say(text="嗯") for _ in range(4)])
    assert res.status == "stuck"
    _assert_contract(rec)


@pytest.mark.parametrize("name", ["success", "failure", "budget_exceeded", "recorded"])
def test_cost_report_matches_fixture(name: str) -> None:
    from triwitness.cost.report import cost_report_from_events

    root = Path(__file__).resolve().parents[3]
    evs = Trajectory.read_events(root / "evals" / "fixtures" / "events" / f"{name}.jsonl")
    fin = evs[-1].payload["cost_report"]
    cr = cost_report_from_events(evs, task_id=evs[0].task_id, budget_cny=fin.get("budget_cny"),
                                 pricing_version=fin["pricing_version"])  # fmt: skip
    assert abs(cr.total_cny - fin["total_cny"]) < 1e-4
    assert abs(cr.cache_hit_rate - fin["cache_hit_rate"]) < 1e-4
