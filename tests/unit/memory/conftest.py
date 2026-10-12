from __future__ import annotations

from pathlib import Path

import pytest

from triwitness.memory.skills import Skill
from triwitness.memory.store import MemoryStore

SKILL_BODY = (
    "1. 先跑 `python -m unittest discover -s tests` 看现状。\n2. 写最小复现测试。\n3. 只改相关函数，再跑全量。\n"
)


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "mem" / "local__demo", repo="/repos/demo")


def make_skill(name: str = "py-unittest-repro", body: str = SKILL_BODY, scope: str = "repo") -> Skill:
    return Skill(name, "仓库用 unittest 而非 pytest 时，如何写复现测试并跑全量。", body, {"tw-scope": scope})
