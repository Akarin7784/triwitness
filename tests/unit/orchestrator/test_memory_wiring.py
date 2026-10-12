"""spec 013 §4（W6-03）：记忆接进编排——事实 + 技能目录进前缀、Planner 检索经验、load_skill 读正文。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from triwitness.core.models import Budget
from triwitness.harness.run import TaskResult, run_task
from triwitness.harness.testing import say
from triwitness.llm.types import ToolCallSpec
from triwitness.memory.context import MemoryContext
from triwitness.memory.skills import Skill, SkillPool
from triwitness.memory.store import Episode, MemoryStore
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandboxBackend
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.verify.testing import make_repo

from .test_inprocess import ISSUE, PY, RIGHT, WRITE_REPRO, RoleRouter, cfg, finish, plan, review


@pytest.fixture
def env(tmp_path: Path) -> tuple[LocalSandboxBackend, Path]:
    repo = make_repo(tmp_path, {"calc.py": "def add(a, b):\n    return a - b\n", "tests/__init__.py": "",
                                "tests/tw_repro/__init__.py": ""})  # fmt: skip
    return LocalSandboxBackend(home=tmp_path / "home"), repo


SKILL = Skill("calc-fix-flow", "改 calc 这类小函数时的复现 → 修复 → 全量流程。", "1. 先写复现测试。\n2. 再改实现。",
              {"tw-scope": "repo"})  # fmt: skip


def names(tools: Any) -> list[str]:
    return [(t.get("function") or t).get("name") for t in (tools or [])]


def memory(tmp_path: Path) -> MemoryContext:
    st = MemoryStore(tmp_path / "mem" / "o__r", repo="o/r")
    st.add_fact("测试用 pytest -q，测试在 tests/ 下", kind="test", source="tw://run/r_prev")
    st.add_episode(Episode("运算符写错", "add 用了减法", "改回加法并补复现测试"), source="tw://run/r_prev")
    pool = SkillPool(st.root)
    pool.add_candidate(SKILL, source="tw://run/r_prev", added="2026-10-12")
    pool.promote("calc-fix-flow", 1, gate_report="# ok")
    return MemoryContext.from_store(st)


async def go(env: tuple, router: Any, mem: MemoryContext | None) -> tuple[TaskResult, TrajectoryRecorder]:  # type: ignore[type-arg]
    backend, repo = env
    sb = await backend.create(SandboxSpec(repo=repo, run_id="exec1"))
    rec = TrajectoryRecorder("t_m", "r_m", run_dir=repo.parent / "run")
    try:
        res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools()), sandbox=sb,
                             issue_title="add 是减法", task_prompt=ISSUE, repo="o/r", budget=Budget(),
                             config_hash="c", test_command=PY, tw_dir=str(sb.tw_dir),  # type: ignore[attr-defined]
                             config=cfg(), memory=mem)  # fmt: skip
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
    return res, rec


async def test_memory_in_prefix_planner_and_load_skill(env: tuple, tmp_path: Path) -> None:  # type: ignore[type-arg]
    router = RoleRouter(
        planner=[plan()],
        executor=[
            say(ToolCallSpec(id="call_ls", name="load_skill", arguments=json.dumps({"name": "calc-fix-flow"}))),
            say(WRITE_REPRO),
            say(RIGHT),
            finish(),
        ],
        reviewer=[review()],
    )
    res, rec = await go(env, router, memory(tmp_path))
    assert res.status == "done", res.outcome
    p_sys = router.r["planner"].requests[0].messages[0].content or ""
    p_in = router.r["planner"].requests[0].messages[1].content or ""
    assert "## 仓库事实" in p_sys and "pytest -q" in p_sys and "## 可用技能" not in p_sys
    assert '<memory source="episodes">' in p_in and "add 用了减法" in p_in
    e_req = router.r["executor"].requests[0]
    e_sys = e_req.messages[0].content or ""
    assert "## 仓库事实" in e_sys and "- calc-fix-flow：" in e_sys and "先写复现测试" not in e_sys
    assert "load_skill" in names(e_req.tools)
    (ls,) = [e.payload for e in rec.events if e.kind == "tool_call" and e.payload["tool"] == "load_skill"]
    assert ls["ok"] is True
    # load_skill 的结果（正文）回到了 Executor 的上下文
    second = "\n".join(m.content or "" for m in router.r["executor"].requests[1].messages)
    assert "# 技能 calc-fix-flow（v1）" in second and "先写复现测试" in second
    meta = json.loads((env[1].parent / "run" / "artifacts" / "memory.json").read_text(encoding="utf-8"))
    assert meta["skills"] == [{"name": "calc-fix-flow", "version": 1}] and meta["episodes"] is True


async def test_no_memory_keeps_prompts_clean(env: tuple) -> None:  # type: ignore[type-arg]
    router = RoleRouter(planner=[plan()], executor=[say(WRITE_REPRO), say(RIGHT), finish()], reviewer=[review()])
    res, _ = await go(env, router, None)
    assert res.status == "done", res.outcome
    e_req = router.r["executor"].requests[0]
    assert "仓库事实" not in (e_req.messages[0].content or "")
    assert "load_skill" not in names(e_req.tools)
    assert "<memory" not in (router.r["planner"].requests[0].messages[1].content or "")
