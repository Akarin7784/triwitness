"""spec 010 §7 / AC6–AC7：只读工具并行、不越过有副作用的工具重排；中断时补结果；续写返工。"""

from __future__ import annotations

import asyncio

from triwitness.core.models import Budget
from triwitness.harness.events import EventEmitter
from triwitness.harness.loop import AgentLoop, HarnessConfig
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.llm.types import Message
from triwitness.tools import ToolContext, ToolRegistry, default_tools

FINISH = {"summary": "修复 add", "changes": [{"path": "calc.py", "kind": "modified"}], "tests_run": ["pytest -q"],
          "tests_passed": True, "confidence": 0.9}  # fmt: skip
FILES = {"a.py": "A = 1\n", "b.py": "B = 2\n", "c.py": "C = 3\n", "calc.py": "def add(a, b):\n    return a - b\n"}


class SlowSandbox(FakeSandbox):
    def __init__(self) -> None:
        super().__init__(dict(FILES))
        self.active = 0
        self.peak = 0
        self.order: list[str] = []

    async def read_file(self, path: str) -> bytes:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.03)
        self.active -= 1
        self.order.append(path)
        return await super().read_file(path)


def make(script: list[Message], cfg: HarnessConfig | None = None) -> tuple[AgentLoop, FakeRouter]:
    router = FakeRouter(script)
    loop = AgentLoop(router, ToolRegistry(default_tools()), system_prompt="s", budget=Budget(),
                     emitter=EventEmitter("t", "r"), config=cfg or HarnessConfig.load())  # fmt: skip
    return loop, router


def tool_ids(msgs: list[Message]) -> list[str]:
    return [m.tool_call_id or "" for m in msgs if m.role == "tool"]


def assert_valid_history(msgs: list[Message]) -> None:
    """每个 assistant 的 tool_call 后面紧跟它的结果（中间不插 user / assistant）。"""
    for i, m in enumerate(msgs):
        if m.role == "assistant" and m.tool_calls:
            want = [c.id for c in m.tool_calls]
            got = [x.tool_call_id for x in msgs[i + 1 : i + 1 + len(want)]]
            assert got == want and all(x.role == "tool" for x in msgs[i + 1 : i + 1 + len(want)]), (want, got)


async def test_reads_run_concurrently_and_keep_order() -> None:
    reads = [call("read_file", path=p) for p in ("a.py", "b.py", "c.py")]
    loop, _ = make([say(*reads), say(call("finish", **FINISH))])
    sb = SlowSandbox()
    out = await loop.run("修 add", ToolContext(sandbox=sb))
    assert out.status == "finished"
    assert sb.peak == 3  # 3 个读并发
    assert tool_ids(loop.messages)[:3] == [c.id for c in reads]  # 结果按调用顺序写回
    assert_valid_history(loop.messages)


async def test_side_effect_tool_is_a_barrier() -> None:
    edit = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")
    calls = [call("read_file", path="a.py"), edit, call("read_file", path="calc.py")]
    loop, _ = make([say(*calls), say(call("finish", **FINISH))])
    sb = SlowSandbox()
    await loop.run("修 add", ToolContext(sandbox=sb))
    assert sb.peak == 1  # 单个读 + 写 + 单个读：不并发
    # 写之后的读看到的是修改后的内容（没有被提前到写之前执行）
    third = next(m for m in loop.messages if m.role == "tool" and m.tool_call_id == calls[2].id)
    assert "a + b" in (third.content or "")


async def test_parallel_can_be_disabled() -> None:
    cfg = HarnessConfig.load()
    cfg.parallel_read_tools = False
    loop, _ = make([say(*[call("read_file", path=p) for p in ("a.py", "b.py")]), say(call("finish", **FINISH))], cfg)
    sb = SlowSandbox()
    await loop.run("x", ToolContext(sandbox=sb))
    assert sb.peak == 1


def test_default_parallel_flag_not_in_baseline_hash() -> None:
    a = HarnessConfig.load()
    b = HarnessConfig.load()
    b.parallel_read_tools = False
    assert a.config_hash() != b.config_hash()
    data = a.model_dump(mode="json")
    assert data["parallel_read_tools"] is True  # 默认值不进哈希（W2 基线哈希不变，见 test_config_hash_*）


async def test_finish_mid_batch_seals_later_calls_and_continue_is_valid() -> None:
    after = call("read_file", path="a.py")
    loop, router = make([
        say(call("finish", **FINISH), after),
        say(call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")),
        say(call("finish", **FINISH)),
    ])  # fmt: skip
    ctx = ToolContext(sandbox=FakeSandbox(dict(FILES)))
    out = await loop.run("修 add", ctx)
    assert out.status == "finished"
    sealed = next(m for m in loop.messages if m.role == "tool" and m.tool_call_id == after.id)
    assert (sealed.content or "").startswith("[未执行：")
    assert_valid_history(loop.messages)
    n = len(loop.messages)
    out2 = await loop.run("修 add", ctx, continue_with="评审发现阻断问题：请修复")
    assert out2.status == "finished"
    req = router.requests[1]
    assert len(req.messages) == n + 1 and req.messages[-1].content == "评审发现阻断问题：请修复"
    assert_valid_history(list(req.messages))


async def test_needs_human_mid_batch_seals_remaining() -> None:
    from triwitness.harness.approvals import NeedsHuman
    from triwitness.tools.base import GateOutcome

    async def gate(tool, params, ctx, call_):  # type: ignore[no-untyped-def]
        if tool.name == "edit_file":
            raise NeedsHuman("h_1", "需要审批")
        return GateOutcome(allowed=True)

    edit = call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")
    later = call("read_file", path="b.py")
    router = FakeRouter([say(call("read_file", path="a.py"), edit, later)])
    loop = AgentLoop(router, ToolRegistry(default_tools(), gate=gate), system_prompt="s", budget=Budget(),
                     emitter=EventEmitter("t", "r"), config=HarnessConfig.load())  # fmt: skip
    out = await loop.run("x", ToolContext(sandbox=FakeSandbox(dict(FILES))))
    assert out.status == "needs_human"
    assert_valid_history(loop.messages)
    contents = {m.tool_call_id: m.content for m in loop.messages if m.role == "tool"}
    assert contents[edit.id].startswith("[未执行：等待人工审批") and contents[later.id].startswith("[未执行")  # type: ignore[union-attr]
