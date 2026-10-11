"""1M 上下文档（Eva 2026-10-11 20:26）：窗口推导、默认 harness、冻结哈希、防抖、窗口硬上限、超限重试、
压缩后重读文件、NOTES 完整注入、附件不二次截断、AGENTS.md 不再写死 4000。全部离线。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from triwitness.core.errors import ContextOverflow, LLMUnavailable
from triwitness.core.limits import DEFAULT_WORKING_BUDGET, runaway_limits
from triwitness.core.models import Budget, Usage
from triwitness.harness.config import HarnessConfig
from triwitness.harness.context import ContextManager
from triwitness.harness.events import EventEmitter
from triwitness.harness.inputs import compose_task
from triwitness.harness.loop import AgentLoop
from triwitness.harness.run import run_task
from triwitness.harness.testing import FakeRouter, FakeSandbox, call, say
from triwitness.llm.deepseek import DeepSeekAdapter
from triwitness.llm.http import http_error
from triwitness.llm.limits import hard_input_limit, role_max_output
from triwitness.llm.router import Router
from triwitness.llm.types import LLMRequest, LLMResponse, Message
from triwitness.sandbox.base import ExecResult
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolContext, ToolRegistry, ToolResult, default_tools
from triwitness.tools.workspace import NOTES_MAX_CHARS

FINISH = {"summary": "完成", "changes": [], "tests_run": [], "tests_passed": False, "confidence": 0.5}


# ---------------------------------------------------------------- 窗口推导
def test_window_derivation_from_models_yaml() -> None:
    assert role_max_output("executor") == 65_536 and role_max_output("reviewer") == 131_072
    assert hard_input_limit("executor") == DEFAULT_WORKING_BUDGET == 1_048_576 - 65_536 - 31_458 == 951_582
    assert hard_input_limit("reviewer") == 1_048_576 - 131_072 - 31_458
    caps = DeepSeekAdapter().capabilities("deepseek-flash")
    assert (caps.context_window, caps.max_output_tokens) == (1_048_576, 393_216)
    assert runaway_limits() == (59_949_666, 2_854_746)


def test_default_harness_is_1m_and_frozen_hashes_unchanged() -> None:
    h = HarnessConfig.default()
    c = h.context
    assert h.name == "long-context-1m" and c.working_budget_tokens == "auto"
    assert c.budget_tokens() == 951_582
    assert (c.clear_at, c.clear_to, c.compact_at, c.keep_recent) == (0.5, 0.25, 0.75, 16)
    assert (c.tail_max_tokens, c.summary_input_tokens, c.reread_recent_files.max_files) == (120_000, 120_000, 5)
    assert 8_000 <= c.allocation.summary <= 12_000
    # W2-25 / W2-26 的 harness_hash 必须能复现（baseline.yaml / repro-first.yaml 冻结）
    assert HarnessConfig.load("harness/baseline.yaml").config_hash() == "bd9e633b20e4"
    assert HarnessConfig.load("harness/repro-first.yaml").config_hash() == "b10ba3e07403"
    assert HarnessConfig.load("harness/context-stress.yaml").config_hash() == "507ae95b7302"
    assert HarnessConfig.load("harness/baseline.yaml").context.budget_tokens() == 128_000


def test_new_fields_change_hash_when_set() -> None:
    base = HarnessConfig.load()
    ctx = base.context.model_copy(update={"tail_max_tokens": 50_000})
    assert base.model_copy(update={"context": ctx}).config_hash() != base.config_hash()


# ---------------------------------------------------------------- 角色输出预留 / 超限分类
class _Client:
    def __init__(self) -> None:
        self.reqs: list[LLMRequest] = []

    async def complete(self, req: LLMRequest, model: str, **_: Any) -> LLMResponse:
        self.reqs.append(req)
        return LLMResponse(message=Message(role="assistant", content="ok"), usage=Usage(), served_model="fake",
                           raw={}, source="fake", finish_reason="stop", model="deepseek-flash")  # fmt: skip


async def test_router_sets_explicit_per_role_max_output() -> None:
    c = _Client()
    r = Router.from_config({"deepseek": c})
    for role in ("executor", "reviewer", "summarizer"):
        await r.complete(LLMRequest(role=role, messages=[Message(role="user", content="hi")]))  # type: ignore[arg-type]
    await r.complete(LLMRequest(role="classifier", max_output_tokens=200, messages=[Message(role="user", content="x")]))
    assert [q.max_output_tokens for q in c.reqs] == [65_536, 131_072, 16_384, 200]
    payload = DeepSeekAdapter().build_request("deepseek-flash", c.reqs[0])
    assert payload["max_tokens"] == 65_536


def test_http_400_context_length_is_context_overflow() -> None:
    e = http_error(400, '{"error":{"message":"This model\'s maximum context length is 1048576 tokens."}}')
    assert isinstance(e, ContextOverflow)
    assert isinstance(http_error(400, '{"error":{"message":"invalid tool schema"}}'), LLMUnavailable)
    assert isinstance(http_error(401, "maximum context length"), LLMUnavailable)


# ---------------------------------------------------------------- ContextManager：防抖 / 尾部上限 / 重读 / NOTES
def _cfg(**ctx: Any) -> HarnessConfig:
    base = HarnessConfig.load()
    alloc = {"prefix": 600, "task": 300, "notes": 200, "summary": 300, "tool_result": 2000, "repo_map": 500}
    context = {**base.context.model_dump(), "working_budget_tokens": 6000, "keep_recent": 3, "keep_recent_turns": 2,
               "allocation": alloc, **ctx}  # fmt: skip
    return base.model_copy(update={"context": type(base.context).model_validate(context)})


def _history(last_tool_chars: int, turns: int = 4) -> list[Message]:
    msgs = [Message(role="system", content="sys"), Message(role="user", content="task")]
    for i in range(turns):
        tc = call("bash", command=f"echo {i}")
        msgs.append(say(tc))
        size = last_tool_chars if i == turns - 1 else 300
        msgs.append(Message(role="tool", content="y" * size, tool_call_id=tc.id, name="bash"))
    return msgs


async def test_thrash_guard_after_two_ineffective_compactions() -> None:
    cm = ContextManager(_cfg(), hard_limit=10**9)
    ctx = ToolContext(sandbox=FakeSandbox({}), tw_dir="/workspace/.tw")
    msgs = _history(30_000)  # 最后一轮一个超大结果：原样保留的尾部至少 1 轮 → 压完仍超压缩线
    out = await cm.compact(msgs, 10, ctx)
    assert out is not None and cm.ineffective == 1 and not cm.thrashing
    tc = call("bash", command="cat big.log")  # 又一个超大结果：压完马上又满
    again = [*out[0], say(tc), Message(role="tool", content="y" * 30_000, tool_call_id=tc.id, name="bash")]
    out2 = await cm.compact(again, 20, ctx)
    assert out2 is not None and cm.thrashing
    ok = ContextManager(_cfg(), hard_limit=10**9)
    await ok.compact(_history(300), 10, ctx)
    assert ok.ineffective == 0


def test_tail_absolute_cap() -> None:
    msgs = _history(300, turns=6)
    loose = ContextManager(_cfg(keep_recent_turns=5), hard_limit=10**9)._cut(msgs)
    tight = ContextManager(_cfg(keep_recent_turns=5, tail_max_tokens=150), hard_limit=10**9)._cut(msgs)
    assert loose is not None and tight is not None and tight > loose


async def test_compaction_rereads_recent_files_and_injects_full_notes() -> None:
    notes = "## 计划\n" + "n" * (NOTES_MAX_CHARS - 100)
    sb = FakeSandbox({"a.py": "print('a')\n", "b.py": "print('b')\n", "/workspace/.tw/NOTES.md": notes})
    ctx = ToolContext(sandbox=sb, tw_dir="/workspace/.tw")
    cm = ContextManager(_cfg(reread_recent_files={"max_files": 1, "max_tokens": 1000}), hard_limit=10**9)
    for p in ("a.py", "b.py"):
        cm.record_tool(call("edit_file", path=p, old_str="x", new_str="y"), ToolResult(ok=True, content="ok"))
    out = await cm.compact(_history(300), 10, ctx)
    assert out is not None
    body = out[0][2].content or ""
    assert 'source="file:b.py"' in body and "print('b')" in body and "file:a.py" not in body  # 最近的 1 个
    assert notes in body  # allocation.notes=200 token（600 字符）也按 NOTES 写入上限完整注入
    assert "重读 1 个文件" in (out[1].display or "")


# ---------------------------------------------------------------- AgentLoop：窗口硬上限 / 超限重试
def _loop(router: FakeRouter, cfg: HarnessConfig, hard_limit: int | None) -> tuple[AgentLoop, EventEmitter]:
    em = EventEmitter("t_1", "r_1")
    loop = AgentLoop(router, ToolRegistry(default_tools(names=cfg.tools)), system_prompt="你是执行者。",
                     budget=Budget(), emitter=em, config=cfg, hard_limit=hard_limit)  # fmt: skip
    return loop, em


async def test_over_window_ends_gracefully_without_calling_model() -> None:
    r = FakeRouter([say(call("finish", **FINISH))])
    loop, _ = _loop(r, HarnessConfig.load(), hard_limit=10)
    out = await loop.run("修复 bug", ToolContext(sandbox=FakeSandbox({}), tw_dir="/workspace/.tw"))
    assert out.status == "context_overflow" and "窗口硬上限" in (out.reason or "")
    assert r.requests == []  # 不把注定被拒的请求发给厂商


class _OverflowRouter(FakeRouter):
    def __init__(self, script: list[Message], fails: int) -> None:
        super().__init__(script)
        self.fails = fails

    async def complete(self, req: LLMRequest, **kw: Any) -> LLMResponse:
        if req.role != "summarizer" and self.fails > 0:
            self.fails -= 1
            self.requests.append(req)
            raise ContextOverflow("HTTP 400: maximum context length exceeded")
        return await super().complete(req, **kw)


@pytest.mark.parametrize(("fails", "status"), [(1, "finished"), (2, "context_overflow")])
async def test_context_overflow_retried_once(fails: int, status: str) -> None:
    r = _OverflowRouter([say(call("finish", **FINISH))], fails=fails)
    loop, _ = _loop(r, HarnessConfig.load(), hard_limit=None)
    out = await loop.run("修复 bug", ToolContext(sandbox=FakeSandbox({}), tw_dir="/workspace/.tw"))
    assert out.status == status


async def test_window_guard_forces_compaction_then_continues() -> None:
    script = [say(call("bash", command=f"cat m{i}.py")) for i in range(8)] + [say(call("finish", **FINISH))]
    r = FakeRouter(script, usage=Usage())  # 没有真实用量：纯字符估算，上下文随步数增长
    cfg = _cfg(clear=False, compact=False)  # 常规清理 / 压缩都关：只有窗口硬上限在起作用
    tools_tok = len(json.dumps(ToolRegistry(default_tools(names=cfg.tools)).schemas(), ensure_ascii=False)) // 3
    loop, em = _loop(r, cfg, hard_limit=tools_tok + 2_500)
    big = "z = 1\n" * 300  # bash 输出不可清理 → 只能靠压缩
    sb = FakeSandbox({}, exec_handler=lambda c, s: ExecResult(exit_code=0, stdout=big, stderr="", duration_ms=1,
                                                              timed_out=False))  # fmt: skip
    out = await loop.run("修复 bug", ToolContext(sandbox=sb, test_command="pytest -q", tw_dir="/workspace/.tw"))
    actions = [e.payload.get("action") for e in em.events if e.kind == "context_event"]
    assert "compact" in actions and out.status in ("finished", "context_overflow", "context_thrash")


# ---------------------------------------------------------------- 输入：附件 / AGENTS.md
def test_attachments_fit_task_allocation(tmp_path: Any) -> None:
    files = []
    for i in range(3):
        p = tmp_path / f"f{i}.txt"
        p.write_text(f"BEGIN{i}\n" + "a" * 40_000 + f"\nEND{i}\n", encoding="utf-8")
        files.append(p)
    cfg = HarnessConfig.load()  # 基线 task=8000 token ≈ 24,000 字符
    cap = cfg.context.chars(cfg.context.allocation.task)
    t = compose_task("修 bug", attachments=files, max_chars=cap)
    assert len(t.prompt) <= cap and t.truncated  # 截断发生在附件里（带标注），不会被 task_message 再切中段
    cm = ContextManager(cfg, hard_limit=10**9)
    assert "中间已省略" not in cm.task_message(t.prompt)
    big = HarnessConfig.default()
    t2 = compose_task("修 bug", attachments=files, max_chars=big.context.chars(big.context.allocation.task))
    assert all(f"END{i}" in t2.prompt for i in range(3))  # 1M 档：3 × 4 万字符的附件完整内联


async def test_agents_md_not_capped_at_4000_chars() -> None:
    long_md = "规则：" + "r" * 9_000 + "末尾标记"
    r = FakeRouter([say(call("finish", **FINISH))])
    cfg = HarnessConfig.load()
    await run_task(recorder=TrajectoryRecorder("t_a", "r_a"), router=r,
                   registry=ToolRegistry(default_tools(names=cfg.tools)), sandbox=FakeSandbox({}),
                   issue_title="t", task_prompt="修", repo="o/r", budget=Budget(), config_hash="c",
                   agents_md=long_md, config=cfg)  # fmt: skip
    assert "末尾标记" in (r.requests[0].messages[0].content or "")


def test_summary_input_cap_follows_config() -> None:
    msgs = _history(300, turns=40)
    small = ContextManager(_cfg(), hard_limit=10**9)._transcript(msgs)
    big = ContextManager(_cfg(summary_input_tokens=200), hard_limit=10**9)._transcript(msgs)
    assert len(big) <= 200 * 3 + 50 < len(small)
