"""端到端（离线）：AgentLoop + 真实 LocalSandbox（none 后端）。硬底线在 unrestricted 下仍生效。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from triwitness.core.models import Budget
from triwitness.harness.events import EventEmitter
from triwitness.harness.loop import AgentLoop
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.sandbox.base import SandboxSpec
from triwitness.sandbox.local import LocalSandbox, LocalSandboxBackend
from triwitness.tools import ToolContext, ToolRegistry, default_tools

SECRET = "sk-live-0123456789abcdef0123456789abcdef"


def git(repo: Path, *a: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True
    )


async def test_loop_on_local_worktree_unrestricted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", SECRET)
    monkeypatch.setenv("MY_ALIAS", SECRET)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calc.py").write_bytes(b"def add(a, b):\n    return a - b\n")
    (repo / "test_calc.py").write_bytes(b"from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    sb = await LocalSandboxBackend(home=tmp_path / "home").create(SandboxSpec(repo=repo, run_id="r_e2e"))
    assert isinstance(sb, LocalSandbox)
    test_cmd = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'

    fin = {
        "summary": "修复 add",
        "changes": [{"path": "calc.py", "kind": "modified"}],
        "tests_passed": True,
        "confidence": 0.9,
    }
    script = [
        say(call("bash", command="env; echo ALIAS=${MY_ALIAS:-none}")),
        say(call("edit_file", path="calc.py", old_str="a - b", new_str="a + b")),
        say(call("run_tests")),
        say(call("finish", **fin)),
    ]
    em = EventEmitter("t", "r_e2e")
    loop = AgentLoop(
        FakeRouter(script), ToolRegistry(default_tools()), system_prompt="s", budget=Budget(), emitter=em
    )  # 无权限门 = unrestricted 等效
    out = await loop.run("x", ToolContext(sandbox=sb, test_command=test_cmd, run_id="r_e2e", tw_dir=str(sb.tw_dir)))
    try:
        assert out.status == "finished"
        env_out = next(m for m in loop.messages if m.role == "tool").content or ""
        assert SECRET not in env_out and "DEEPSEEK_API_KEY" not in env_out and "ALIAS=none" in env_out
        assert "1 passed" in (loop.messages[-1].content or "") or any(
            "1 passed" in (m.content or "") for m in loop.messages if m.role == "tool"
        )
        assert "a + b" not in (repo / "calc.py").read_text()  # 用户仓库未被改动
        diff = await sb.diff("base")
        assert "+    return a + b" in diff
    finally:
        await sb.finish("discard")  # type: ignore[attr-defined]
