"""W3-04：repro-first（submit_repro + finish 校验 + REPRODUCING 状态），FakeRouter 驱动，不调用模型。"""

from __future__ import annotations

from typing import Any

from triwitness.core.models import Budget
from triwitness.harness.config import HarnessConfig
from triwitness.harness.run import TaskResult, run_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.sandbox.base import ExecResult
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

CFG = HarnessConfig.load("harness/repro-first.yaml")
REPRO = "tests/tw_repro/test_issue_3.py"
BUGGY, FIXED = "def add(a, b):\n    return a - b\n", "def add(a, b):\n    return a + b\n"


def handler(cmd: str, sb: FakeSandbox) -> ExecResult:
    """“测试”看 calc.py 是否已修好；`true` 命令永远通过（模拟没复现出问题的测试）。"""
    if cmd.startswith("python "):  # 0.3.1：机器上没有 `python`
        return ExecResult(exit_code=127, stdout="", stderr="bash: python: command not found", duration_ms=1,
                          timed_out=False)  # fmt: skip
    code = 0 if cmd.startswith("true") or sb.files.get("calc.py") == FIXED.encode() else 1
    return ExecResult(exit_code=code, stdout="1 failed" if code else "1 passed", stderr="", duration_ms=1,
                      timed_out=False)  # fmt: skip


def finish(**kw: Any) -> Any:
    args: dict[str, Any] = dict(summary="修好 add", changes=[{"path": "calc.py", "kind": "modified"}],
                                tests_run=["pytest"], tests_passed=True, confidence=0.9)  # fmt: skip
    args.update(kw)
    return call("finish", **args)


async def run(script: list, cfg: HarnessConfig = CFG) -> tuple[TaskResult, TrajectoryRecorder, FakeSandbox]:  # type: ignore[type-arg]
    rec = TrajectoryRecorder("t_r", "r_r")
    sb = FakeSandbox({"calc.py": BUGGY}, exec_handler=handler)
    res = await run_task(recorder=rec, router=FakeRouter(script), registry=ToolRegistry(default_tools(names=cfg.tools)),
                         sandbox=sb, issue_title="add 是减法", task_prompt="修", repo="o/r", budget=Budget(),
                         config_hash="c", issue_number=3, test_command="pytest -q", config=cfg)  # fmt: skip
    return res, rec, sb


def states(rec: TrajectoryRecorder) -> list[str]:
    return [str(e.payload["to"]) for e in rec.events if e.kind == "state_change"]


def tool_results(rec: TrajectoryRecorder, name: str) -> list[dict[str, Any]]:
    return [e.payload for e in rec.events if e.kind == "tool_call" and e.payload["tool"] == name]


FIX = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")
WRITE_REPRO = call(
    "write_file", path=REPRO, content="from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
)


async def test_base_pass_rejected_then_reproduced_then_fixed() -> None:
    res, rec, _ = await run([
        say(WRITE_REPRO),
        say(call("submit_repro", path=REPRO, cmd="true")),  # 基线通过 → 拒绝
        say(call("submit_repro", path=REPRO, cmd=f"pytest {REPRO}")),  # 基线失败 → 接受
        say(FIX),
        say(call("run_tests")),
        say(finish()),
    ])  # fmt: skip
    subs = tool_results(rec, "submit_repro")
    assert [s["ok"] for s in subs] == [False, True]
    assert subs[0]["error_type"] == "repro_passes_on_base"
    assert res.status == "done" and res.repro_status == "reproduced"
    assert res.finish is not None and res.finish.repro is not None and res.finish.repro.path == REPRO  # finish 自动补上
    assert states(rec) == ["preparing", "reproducing", "executing", "packaging", "done"]


async def test_finish_without_repro_is_rejected() -> None:
    res, rec, _ = await run([say(FIX), say(finish()),
                             say(call("submit_repro", not_applicable=True, reason="")),
                             say(call("submit_repro", not_applicable=True, reason="纯重构，没有可观察行为变化")),
                             say(finish())])  # fmt: skip
    fins = tool_results(rec, "finish")
    assert [f["ok"] for f in fins] == [False, True] and fins[0]["error_type"] == "repro_missing"
    assert res.repro_status == "not_applicable"
    assert res.finish is not None and res.finish.repro is None
    assert any("not_applicable" in r for r in res.finish.open_risks)
    assert "executing" in states(rec)


async def test_repro_after_source_change_is_rejected() -> None:
    res, rec, _ = await run([
        say(FIX, WRITE_REPRO),
        say(call("submit_repro", path=REPRO, cmd=f"pytest {REPRO}")),
        say(call("submit_repro", path=REPRO, cmd=f"pytest {REPRO}")),
    ])  # fmt: skip
    subs = tool_results(rec, "submit_repro")
    assert [s["error_type"] for s in subs] == ["repro_after_fix", "repro_after_fix"]
    assert res.repro_status == "missing" and states(rec)[:2] == ["preparing", "reproducing"]


async def test_missing_file_and_bad_args() -> None:
    _, rec, _ = await run([say(call("submit_repro", path="nope.py", cmd="pytest nope.py")),
                           say(call("submit_repro", path=REPRO))])  # fmt: skip
    assert [s["error_type"] for s in tool_results(rec, "submit_repro")] == ["not_found", "bad_args"]


async def test_baseline_config_unchanged() -> None:
    base = HarnessConfig.load()
    assert "submit_repro" not in base.tools and base.prompts["executor"] == "executor"
    res, rec, _ = await run([say(FIX), say(finish())], cfg=base)
    assert res.status == "done" and res.repro_status is None
    assert states(rec) == ["preparing", "executing", "packaging", "done"]


def test_submit_repro_command_goes_through_permission_gate() -> None:
    from triwitness.harness.approvals import action_for
    from triwitness.tools.base import ToolContext
    from triwitness.tools.repro import SubmitRepro, SubmitReproParams

    ctx = ToolContext(sandbox=FakeSandbox())
    a = action_for(SubmitRepro(), SubmitReproParams(path=REPRO, cmd="pytest x; rm -rf /"), ctx)
    assert a is not None and a.tool == "submit_repro" and "rm -rf" in a.value and a.category == "Bash"
    assert action_for(SubmitRepro(), SubmitReproParams(not_applicable=True, reason="r"), ctx) is None


async def test_broken_command_is_not_a_repro() -> None:
    """0.3.1 真实 key 首跑：`python: command not found`（exit 127）曾被当成复现成立。"""
    res, rec, _ = await run([
        say(WRITE_REPRO),
        say(call("submit_repro", path=REPRO, cmd=f"python -m pytest {REPRO}")),  # 命令跑不起来 → 拒绝
        say(call("submit_repro", path=REPRO, cmd=f"pytest {REPRO}")),
        say(FIX),
        say(call("run_tests")),
        say(finish()),
    ])  # fmt: skip
    subs = tool_results(rec, "submit_repro")
    assert [s["ok"] for s in subs] == [False, True]
    assert subs[0]["error_type"] == "repro_cmd_broken"
    assert res.status == "done" and res.repro_status == "reproduced"


def test_broken_command_classifier() -> None:
    from triwitness.tools.repro import broken_command

    assert broken_command("python -m pytest t.py", 127, "") is not None
    assert broken_command("python3 -m pytest t.py", 1, "/usr/bin/python3: No module named pytest") is not None
    assert broken_command("python t.py", 1, "'python' is not recognized as an internal or external command")
    assert broken_command("pytest -q nope.py", 4, "ERROR: file or directory not found") is not None
    assert broken_command("pytest -q t.py", 1, "1 failed") is None
    assert broken_command("python3 -m unittest t", 1, "AssertionError: 4 != 2") is None
    assert broken_command("python3 -m unittest t", 1, "ModuleNotFoundError: No module named 'calc'") is None
