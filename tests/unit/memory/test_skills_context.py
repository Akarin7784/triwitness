"""spec 013 §4 / §5（W6-03 / 04）：SKILL.md 格式与版本元数据、候选池、前缀注入、load_skill 渐进加载。"""

from __future__ import annotations

import pytest

from triwitness.harness.loop import build_system_prompt
from triwitness.memory.context import MemoryContext, open_memory
from triwitness.memory.skills import Skill, SkillError, SkillPool, catalog_block
from triwitness.memory.store import Episode, MemoryStore
from triwitness.tools.base import ToolContext
from triwitness.tools.skills import LoadSkill, LoadSkillParams

from .conftest import make_skill


def test_skill_md_roundtrip_agent_skills_format() -> None:
    sk = make_skill()
    sk.extra["license"] = "MIT"
    text = sk.render()
    assert text.startswith("---\nname: py-unittest-repro\ndescription: ")
    assert "metadata:\n  tw-scope: repo" in text and "license: MIT" in text
    back = Skill.parse(text)
    assert (back.name, back.description, back.body, back.metadata, back.extra) == (
        sk.name, sk.description, sk.body.strip(), sk.metadata, {"license": "MIT"})  # fmt: skip
    with pytest.raises(SkillError):
        Skill.parse("no frontmatter")
    assert Skill("Bad_Name", "d", "b").validate()


def test_pool_versions_promote_rollback(store: MemoryStore) -> None:
    store.init()
    pool = SkillPool(store.root)
    v1 = pool.add_candidate(make_skill(), source="tw://run/r_1", added="2026-10-12")
    assert v1.version == 1 and v1.status == "candidate" and pool.active() == []
    pool.promote("py-unittest-repro", 1, gate_report="# ok", summary={"rate_a": 0.5})
    (act,) = pool.active()
    assert act.version == 1 and act.status == "active" and act.metadata["tw-gate"].endswith("v1/gate.md")
    assert (store.root / "skills" / "py-unittest-repro" / "SKILL.md").is_file()
    assert not (store.root / "skills" / "py-unittest-repro" / "gate.md").exists()
    v2 = pool.add_candidate(make_skill(body="新版步骤"), source="tw://run/r_2", added="2026-10-13")
    assert v2.version == 2
    pool.promote("py-unittest-repro", 2, gate_report="# ok2")
    assert pool.load("py-unittest-repro").body == "新版步骤"
    assert pool.state()["py-unittest-repro"]["versions"]["1"]["status"] == "superseded"
    # 回滚：换回 v1；再回滚：移除
    assert pool.rollback("py-unittest-repro", reason="退化") == 1
    assert pool.load("py-unittest-repro").version == 1
    assert pool.rollback("py-unittest-repro", reason="再退化") is None
    assert pool.active() == []
    hist = [h["action"] for h in pool.state()["py-unittest-repro"]["history"]]
    assert hist == ["candidate", "promote", "candidate", "promote", "rollback", "rollback"]
    with pytest.raises(SkillError):
        pool.rollback("py-unittest-repro", reason="x")


def test_reject_keeps_reason(store: MemoryStore) -> None:
    pool = SkillPool(store.root)
    pool.add_candidate(make_skill(), source="s", added="2026-10-12")
    pool.reject("py-unittest-repro", 1, reason="成功率没有提升", gate_report="# no")
    assert pool.get("py-unittest-repro", 1).status == "rejected"
    assert (pool.version_dir("py-unittest-repro", 1) / "reject.txt").read_text(encoding="utf-8").startswith("成功率")


def _filled(store: MemoryStore) -> MemoryContext:
    store.add_fact("测试命令：python -m unittest discover -s tests", kind="test", source="tw://run/r_1")
    store.add_episode(Episode("空输入", "mean 除以 len(xs) 未判空", "先判空并补测试"), source="tw://run/r_1")
    pool = SkillPool(store.root)
    pool.add_candidate(make_skill(), source="tw://run/r_1", added="2026-10-12")
    pool.promote("py-unittest-repro", 1, gate_report="# ok")
    return MemoryContext.from_store(store)


def test_prefix_has_facts_and_catalog_only(store: MemoryStore) -> None:
    mem = _filled(store)
    secs = mem.prefix_sections()
    assert len(secs) == 2 and "python -m unittest discover" in secs[0]
    assert "py-unittest-repro：" in secs[1]
    assert "写最小复现测试" not in "\n".join(secs)  # 正文不进前缀（渐进加载）
    base = build_system_prompt("角色", agents_md="约定", tool_names=["bash"])
    with_mem = build_system_prompt("角色", agents_md="约定", tool_names=["bash"], memory_sections=secs)
    stripped = with_mem
    for sec in secs:
        stripped = stripped.replace(sec + "\n\n", "")
    assert stripped == base and with_mem != base  # 只多了记忆段（在 AGENTS.md 之后、工具列表之前）
    # 无记忆 / 空记忆：前缀逐字节不变；同一记忆：前缀稳定（缓存命中）
    assert build_system_prompt("角色", agents_md="约定", tool_names=["bash"], memory_sections=[]) == base
    again = build_system_prompt("角色", agents_md="约定", tool_names=["bash"],
                                memory_sections=MemoryContext.from_store(store).prefix_sections())  # fmt: skip
    assert again == with_mem


def test_planner_block_retrieves_episodes(store: MemoryStore) -> None:
    mem = _filled(store)
    block = mem.planner_block("mean([]) 抛 ZeroDivisionError，空列表应返回 0.0")
    assert block.startswith('<memory source="episodes">') and "未判空" in block and "tw://run/r_1" in block
    assert mem.planner_block("完全无关的 websocket 握手超时") == ""


CTX = ToolContext(sandbox=None)  # type: ignore[arg-type]


async def test_load_skill_tool(store: MemoryStore) -> None:
    mem = _filled(store)
    tool = LoadSkill(mem)
    ok = await tool.run(LoadSkillParams(name="py-unittest-repro"), CTX)
    assert ok.ok and ok.content.startswith("# 技能 py-unittest-repro（v1）") and "写最小复现测试" in ok.content
    miss = await tool.run(LoadSkillParams(name="nope"), CTX)
    assert not miss.ok and miss.error_code == "not_found" and "py-unittest-repro" in miss.content


def test_with_skills_isolates_gate_arm(store: MemoryStore) -> None:
    mem = MemoryContext.with_skills([make_skill()])
    assert mem.facts == "" and mem.search is None and len(mem.prefix_sections()) == 1
    assert "py-unittest-repro" in catalog_block(mem.skills)


def test_open_memory_respects_session(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home = tmp_path / "home"
    repo = tmp_path / "r"
    repo.mkdir()
    assert open_memory(str(repo), home=home) is None  # 没有记忆
    MemoryStore.for_repo(str(repo), home).add_fact("用 tox", source="tw://manual")
    assert open_memory(str(repo), home=home) is not None
    assert open_memory(str(repo), home=home, mode="eval", category="baseline") is None
    assert open_memory(str(repo), home=home, override=False) is None
