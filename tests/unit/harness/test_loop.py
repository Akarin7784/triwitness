"""AgentLoop：spec 003 AC1、AC5、AC6 及截断、stuck、错误处理（FakeRouter + FakeSandbox）。"""

from __future__ import annotations

import pytest

from triwitness.core.errors import LLMUnavailable
from triwitness.core.models import Budget
from triwitness.harness.events import EventEmitter
from triwitness.harness.loop import AgentLoop, HarnessConfig, build_system_prompt, truncate_for_model
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.llm.types import Message
from triwitness.sandbox.base import ExecResult
from triwitness.tools import ToolContext, ToolRegistry, default_tools

PASS = "==== 3 passed in 0.1s ===="
FINISH = {
    "summary": "修复 add",
    "changes": [{"path": "calc.py", "kind": "modified"}],
    "tests_run": ["pytest -q"],
    "tests_passed": True,
    "confidence": 0.9,
}


def make(script: list[Message], *, budget: Budget | None = None, sb: FakeSandbox | None = None, **kw: object):  # type: ignore[no-untyped-def]
    em = EventEmitter("t_1", "r_1")
    router = FakeRouter(script, **kw)  # type: ignore[arg-type]
    loop = AgentLoop(
        router,
        ToolRegistry(default_tools()),
        system_prompt="你是执行者。",
        budget=budget or Budget(),
        emitter=em,
        config=HarnessConfig.load(),
    )
    sandbox = sb or FakeSandbox(
        {"calc.py": "def add(a, b):\n    return a - b\n"},
        exec_handler=lambda c, s: ExecResult(exit_code=0, stdout=PASS, stderr="", duration_ms=3, timed_out=False),
    )
    return loop, ToolContext(sandbox=sandbox, test_command="pytest -q"), em, router


async def test_ac1_read_edit_test_finish() -> None:
    loop, ctx, em, router = make(
        [
            say(call("read_file", path="calc.py")),
            say(call("edit_file", path="calc.py", old_str="return a - b", new_str="return a + b")),
            say(call("run_tests")),
            say(call("finish", **FINISH)),
        ]
    )
    out = await loop.run("修复 add 的 bug", ctx)
    assert out.status == "finished" and out.steps == 4
    assert out.finish and out.finish.summary == "修复 add"
    assert ctx.sandbox.files["calc.py"].endswith(b"return a + b\n")  # type: ignore[attr-defined]
    assert em.kinds() == ["model_call", "tool_call"] * 4
    # 稳定前缀：每次请求的 system 消息与工具定义完全相同
    assert len({r.messages[0].content for r in router.requests}) == 1
    assert len({str(r.tools) for r in router.requests}) == 1
    tool_msgs = [m for m in loop.messages if m.role == "tool"]
    assert [m.name for m in tool_msgs] == ["read_file", "edit_file", "run_tests", "finish"]


def test_ac6_budget_defaults() -> None:
    b = Budget()
    assert (b.max_cost_cny, b.max_input_tokens, b.max_output_tokens, b.max_turns, b.max_wall_seconds, b.warn_ratio) == (
        None,  # 0.3.2：不再有 ¥ 上限
        59_949_666,  # 1M 档：100 轮 × 工作预算 951,582 × 0.63
        100_000,
        100,
        1800,
        0.8,
    )
    assert b.max_uncached_input_tokens == 2_854_746  # 1M 档：3 × 工作预算（W2-26 时为 400K）


async def test_ac6_budget_exhausted_after_first_call() -> None:
    loop, ctx, _, router = make(
        [say(call("read_file", path="calc.py"))] * 5, budget=Budget(max_cost_cny=0.01, max_turns=1), cost_cny=0.02
    )
    out = await loop.run("x", ctx)
    assert out.status == "budget_exhausted" and len(router.requests) == 1
    assert "max_turns" in (out.reason or "") and "max_cost_cny" not in (out.reason or "")


async def test_max_turns() -> None:
    loop, ctx, *_ = make(
        [say(call("read_file", path="calc.py", start_line=i)) for i in range(1, 9)], budget=Budget(max_turns=3)
    )
    out = await loop.run("x", ctx)
    assert out.status == "budget_exhausted" and out.steps <= 3


async def test_ac5_repeat_reminder_then_stuck() -> None:
    same = say(call("bash", command="ls"))
    loop, ctx, em, _ = make([same.model_copy(deep=True) for _ in range(20)])
    out = await loop.run("x", ctx)
    assert out.status == "stuck" and "死循环" in (out.reason or "")
    warnings = [e for e in em.events if e.kind == "loop_warning"]
    assert [w.payload["level"] for w in warnings] == [1, 2, 3]
    assert warnings[0].payload["signal"] == "repeat_action"
    # 第一次警告后，下一次请求里出现提醒
    reminders = [m for m in loop.messages if m.role == "user" and "重复" in (m.content or "")]
    assert len(reminders) == 2
    assert out.steps == 9


async def test_reminder_after_all_parallel_tool_results() -> None:
    """W2-25 真跑发现：并行 tool_calls 中途触发警告时，提醒插在两条 tool 消息之间 → DeepSeek HTTP 400。"""
    first = say(call("bash", command="ls"), call("bash", command="ls"))
    loop, ctx, em, _ = make(
        [first, say(call("bash", command="ls"), call("bash", command="ls")), say(call("finish", **FINISH))]
    )
    out = await loop.run("x", ctx)
    assert out.status == "finished"
    assert any(e.kind == "loop_warning" for e in em.events)
    for i, m in enumerate(loop.messages):
        if m.role == "assistant" and m.tool_calls:
            n = len(m.tool_calls)
            assert [x.role for x in loop.messages[i + 1 : i + 1 + n]] == ["tool"] * n


async def test_consecutive_failures() -> None:
    loop, ctx, em, _ = make([say(call("read_file", path=f"missing{i}.py")) for i in range(30)])
    out = await loop.run("x", ctx)
    assert out.status == "stuck"
    assert any(e.payload.get("signal") == "consecutive_failures" for e in em.events if e.kind == "loop_warning")


async def test_no_tool_calls_stuck() -> None:
    loop, ctx, *_ = make([say(text="我想想") for _ in range(5)])
    out = await loop.run("x", ctx)
    assert out.status == "stuck" and out.steps == 3
    assert sum(1 for m in loop.messages if m.role == "user" and "调用工具" in (m.content or "")) == 2


async def test_tool_result_truncated_and_saved() -> None:
    big = "x" * 50_000 + "END"
    sb = FakeSandbox(
        {"big.txt": "\n".join([big])},
        exec_handler=lambda c, s: ExecResult(exit_code=0, stdout=big, stderr="", duration_ms=1, timed_out=False),
    )
    loop, ctx, em, _ = make(
        [say(call("bash", command="cat big.txt")), say(call("finish", **{**FINISH, "tests_passed": False}))], sb=sb
    )
    ctx.tw_dir = "/workspace/.tw"
    out = await loop.run("x", ctx)
    assert out.status == "finished"
    tool_msg = next(m for m in loop.messages if m.role == "tool")
    assert len(tool_msg.content or "") < 33_000 and "省略" in (tool_msg.content or "")
    assert (tool_msg.content or "").rstrip().endswith("可用 read_file 查看）\n</untrusted>")  # 工具输出包不可信块
    ev = next(e for e in em.events if e.kind == "tool_call")
    assert ev.payload["truncated"] and ev.payload["output_ref"].endswith("/outputs/1.txt")
    assert any(k.endswith("outputs/1.txt") for k in sb.files)


def test_truncate_head_tail() -> None:
    t, cut = truncate_for_model("a" * 60 + "b" * 40 + "c" * 100, 100, 0.6)
    assert cut and t.startswith("a" * 60) and t.endswith("c" * 40)


async def test_llm_error() -> None:
    class Down(FakeRouter):
        async def complete(self, req, **kw):  # type: ignore[no-untyped-def, override]
            raise LLMUnavailable("503")

    em = EventEmitter("t", "r")
    loop = AgentLoop(Down([]), ToolRegistry(default_tools()), system_prompt="s", budget=Budget(), emitter=em)
    out = await loop.run("x", ToolContext(sandbox=FakeSandbox()))
    assert out.status == "error" and "503" in (out.reason or "")


async def test_wrap_up_reminder() -> None:
    loop, ctx, *_ = make(
        [
            say(call("read_file", path="calc.py", start_line=1)),
            say(call("finish", **{**FINISH, "tests_passed": False})),
        ],
        budget=Budget(max_turns=4, warn_ratio=0.25),
        cost_cny=0.006,
    )
    out = await loop.run("x", ctx)
    assert out.status == "finished"
    assert any("收尾" in (m.content or "") for m in loop.messages if m.role == "user")


def test_system_prompt_stable() -> None:
    a = build_system_prompt("角色", agents_md="约定", tool_names=["grep", "bash"])
    assert a == build_system_prompt("角色", agents_md="约定", tool_names=["bash", "grep"])
    assert "bash、grep" in a


@pytest.mark.parametrize("key", ["no_tool", "wrap_up", "repeat", "failures"])
def test_config_reminders(key: str) -> None:
    assert HarnessConfig.load().reminder(key, detail="d")


async def test_no_progress_signal() -> None:
    tests = [say(call("run_tests", selector=f"tests/test_{i}.py")) for i in range(30)]
    loop, ctx, em, _ = make(tests)
    out = await loop.run("x", ctx)
    assert out.status == "stuck"
    warns = [e for e in em.events if e.kind == "loop_warning"]
    assert [w.payload["signal"] for w in warns] == ["no_progress"] * 3
    assert warns[0].payload["display"] == "⚠ 无进展"
    assert out.steps == 18  # 每 6 步一次警告，第 3 次 stuck
    assert any("没有修改文件" in (m.content or "") for m in loop.messages if m.role == "user")


async def test_edits_and_new_reads_reset_no_progress() -> None:
    rt = [say(call("run_tests", selector=f"t{i}")) for i in range(5)]
    rt2 = [say(call("run_tests", selector=f"u{i}")) for i in range(5)]
    reads = [say(call("read_file", path="calc.py", start_line=1))]
    edit = [say(call("edit_file", path="calc.py", old_str="a - b", new_str="a + b"))]
    fin = [say(call("finish", **{**FINISH, "tests_passed": False}))]
    loop, ctx, em, _ = make(rt + edit + rt2 + reads + rt + fin)
    out = await loop.run("x", ctx)
    assert out.status == "finished" and "loop_warning" not in em.kinds()
