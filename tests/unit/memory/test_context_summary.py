"""task_started.memory 摘要（桌面端「本次用了哪些记忆」）。"""

from __future__ import annotations

from triwitness.memory.context import MemoryContext
from triwitness.memory.format import Entry
from triwitness.memory.skills import Skill


def test_summary_lists_facts_and_skills_with_source() -> None:
    long = "测试命令是 uv run pytest -q " + "x" * 300
    ctx = MemoryContext(
        repo_key="github.com_o_r",
        facts="…",
        fact_items=[Entry(long, {"id": "f1", "kind": "test_cmd", "source": "tw://run/r_1"})],
        skills=[Skill("fix-ci", "修 CI", "body", {"tw-version": "2", "tw-source": "tw://run/r_2"})],
    )
    s = ctx.summary()
    assert s["facts_total"] == 1 and s["skills_total"] == 1 and s["episodes"] is False
    f = s["facts"][0]  # type: ignore[index]
    assert f["id"] == "f1" and f["source"] == "tw://run/r_1" and len(f["text"]) <= 160 and f["text"].endswith("…")
    sk = s["skills"][0]  # type: ignore[index]
    assert sk == {"name": "fix-ci", "version": 2, "description": "修 CI", "source": "tw://run/r_2"}


def test_summary_empty() -> None:
    s = MemoryContext().summary()
    assert s["facts"] == [] and s["skills"] == []
